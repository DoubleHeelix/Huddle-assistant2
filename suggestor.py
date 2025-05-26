import openai
import os
import re
from dotenv import load_dotenv
from openai import OpenAI
from memory_vector import embed_and_store_interaction
from vectorizer import embed_single
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from vectorizer import embed_batch

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants
MAX_HUDDLES = 3
MAX_DOCS = 2
MAX_CHUNK_LEN = 500
VECTOR_SIZE = 1536

SYSTEM_PROMPT = (

    "You are a warm, concise network marketing assistant. "
    "Your job is to help improve the user's draft reply for a chat or conversation. "
    "Write replies that feel personal, human, and natural—never robotic or generic. "
    "Avoid filler phrases like 'Draft', and never reply to or mention the draft. "
    "Take inspiration from the user's draft to create the best reply for the conversation in the screenshot. "
    "Mirror the user's tone and follow the 5 Huddle principles: clarity, connection, brevity, flow, empathy."
)
def clean_reply(text):
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)
    

    # Remove robotic lead-ins
    replacements = [
        "This is a draft", "Draft:", "Suggested reply:", "Here is your response:", "Rewritten Message:"
    ]
    for phrase in replacements:
        text = text.replace(phrase, "")
    return text.strip()

def zip_qdrant_results(results):
    return [
        {
            "document": r.payload.get("document", "")[:MAX_CHUNK_LEN],
            "source": r.payload.get("source", "unknown")
        }
        for r in results
    ]

def retrieve_similar_examples(screenshot_text, user_draft):
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )

    combined_query = screenshot_text + "\n" + user_draft
    draft_query = user_draft

    huddle_vector = embed_single(combined_query)
    doc_vector = embed_single(draft_query)

    huddles = client.search(
        collection_name="huddle_memory",
        query_vector=huddle_vector,
        limit=MAX_HUDDLES,
        with_payload=True
    )

    docs = client.search(
        collection_name="docs_memory",
        query_vector=doc_vector,
        limit=MAX_DOCS,
        with_payload=True
    )

    return zip_qdrant_results(huddles), zip_qdrant_results(docs)

def suggest_reply(screenshot_text, user_draft, principles, model_name=None):
    huddle_matches, doc_matches = retrieve_similar_examples(screenshot_text, user_draft)

    def format_context(matches):
        return "\n\n".join(
            f"- Source: {m['source']}\n{m['document']}" for m in matches
        )

    huddle_context = format_context(huddle_matches)
    doc_context = format_context(doc_matches)

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": (
                "Here are some relevant examples:\n\n"
                f"🧠 Past Huddles:\n{huddle_context}\n\n"
                f"📄 Communication Docs:\n{doc_context}\n\n"
                "Below is the conversation context and the user's draft reply.\n"
                "Your job is to use the draft as a starting point and rewrite it for the person in the conversation context.\n"
                "Do NOT reply to the draft. Do NOT reference the draft. Write as if you are sending the message to the person in the screenshot context.\n\n"
                f"Conversation context (from screenshot):\n{screenshot_text}\n\n"
                f"User's draft reply (for inspiration):\n{user_draft}\n\n"
                "Write the best, most natural, and most human reply you would send in this scenario."
            )
        }
    ]

    selected_model = model_name or os.getenv("OPENAI_MODEL", "gpt-4")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=selected_model,
        messages=messages,
        temperature=0.7
    )

    final_reply = clean_reply(response.choices[0].message.content)

    # Determine if the huddle is high quality
    is_quality = (
        len(user_draft.strip().split()) >= 8 and
        len(screenshot_text.strip()) >= 20 and
        "lorem ipsum" not in screenshot_text.lower()
    )
    
    if is_quality:
        embed_and_store_interaction(
            screenshot_text=screenshot_text,
            user_draft=user_draft,
            ai_suggested=final_reply
        )
    
    return final_reply, doc_matches

def adjust_tone(original_reply, selected_tone):
    if not selected_tone or selected_tone == "None":
        return original_reply

    prompt = f"""
Take the following message and rewrite it to sound more {selected_tone.lower()}, while still sounding like a human having a natural conversation.

Message:
{original_reply}
"""

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert at rephrasing text to match a conversational tone with emotional intelligence."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return clean_reply(response.choices[0].message.content)