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


def clean_reply(text):
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)
    return text


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
            "content": "You are a helpful and concise network marketing assistant. Follow the 5 Huddle principles: Clarity, Connection, Brevity, Flow, and Empathy."
        },
        {
            "role": "user",
            "content": f"""
Here are some relevant examples:

🧠 Past Huddles:
{huddle_context}

📄 Communication Docs:
{doc_context}

Now, based on this and the input below, generate the best possible reply.

Screenshot: {screenshot_text}
Draft: {user_draft}
"""
        }
    ]

    selected_model = model_name or os.getenv("OPENAI_MODEL", "gpt-4")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=selected_model,
        messages=messages,
        temperature=0.7,
        stream=True  # ✅ Enable streaming
    )
    
    # Collect stream as text (in suggestor.py)
    reply_parts = []
    for chunk in response:
        if "content" in chunk.choices[0].delta:
            reply_parts.append(chunk.choices[0].delta.content)
    
    final_reply = "".join(reply_parts).strip()
    

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
You are a communication assistant. Take the following message and rewrite it to sound more {selected_tone.lower()}:
Do not include any greeting like "Hey [Name]" or "Hi [Name] or draft" — begin the message directly with the key reply. Assume the message will be pasted mid-conversation.

Original Message:
{original_reply}

Rewritten Message:
"""

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert at rephrasing text to match a specific tone."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return clean_reply(response.choices[0].message.content)
