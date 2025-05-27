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

# ====== CONSTANTS & PROMPT ======

MAX_HUDDLES = 3    # Only the most relevant huddle
MAX_DOCS = 2       # Only the most relevant doc
MAX_CHUNK_LEN = 400  # Further trimmed for faster/cheaper inference
VECTOR_SIZE = 1536

SYSTEM_PROMPT = (
    "You are a warm, emotionally intelligent, and concise network marketing assistant. "
    "Write replies that feel personal, natural, and human. "
    "Mirror the user's tone and follow the 5 Huddle principles: Clarity, Connection, Brevity, Flow, Empathy. "
    "Avoid generic greetings (e.g., 'Hey there'), scripted language, or robotic/formal openers. "
    "NEVER start with 'Draft:', 'Here's a suggestion', etc. "
    "Write directly as if sending a message to the recipient in the conversation context."
)

# ====== UTILITIES ======

def clean_reply(text):
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)
    for phrase in [
        "This is a draft", "Draft:", "Suggested reply:", "Here is your response:", "Rewritten Message:"
    ]:
        text = text.replace(phrase, "")
    return text.strip()

def zip_qdrant_results(results):
    """Zip Qdrant payloads into usable short chunks."""
    out = []
    seen = set()
    for r in results:
        doc = r.payload.get("document", "")
        if doc and doc[:MAX_CHUNK_LEN] not in seen:
            out.append({
                "document": doc[:MAX_CHUNK_LEN],
                "source": r.payload.get("source", "unknown")
            })
            seen.add(doc[:MAX_CHUNK_LEN])
    return out

# ====== RETRIEVAL LOGIC ======

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

# ====== PROMPT CONSTRUCTION & SUGGESTION ======

def suggest_reply(screenshot_text, user_draft, principles, model_name=None):
    # --- Fetch context (de-duped & trimmed) ---
    huddle_matches, doc_matches = retrieve_similar_examples(screenshot_text, user_draft)
    # Deduplicate docs if any overlap
    seen_docs = set()
    doc_context_lines = []
    for m in doc_matches:
        key = (m['source'], m['document'])
        if key not in seen_docs:
            doc_context_lines.append(f"📄 {m['source']}:\n{m['document']}")
            seen_docs.add(key)
    huddle_context_lines = []
    for m in huddle_matches:
        key = (m['source'], m['document'])
        if key not in seen_docs:  # Don't repeat docs that appeared above
            huddle_context_lines.append(f"🧠 {m['source']}:\n{m['document']}")
            seen_docs.add(key)

    # Build the prompt only with the most relevant pieces
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Context for reply:\n"
        f"{' '.join(huddle_context_lines)}\n"
        f"{' '.join(doc_context_lines)}\n\n"
        f"Conversation context (from screenshot):\n{screenshot_text[:700]}\n\n"
        f"User's draft reply (for inspiration):\n{user_draft[:400]}\n\n"
        "Rewrite the best, most natural, and most human reply you would send in this scenario. "
        "Be direct—never reference that this is a draft. Just write the message as you would send it."
    )

    selected_model = model_name or os.getenv("OPENAI_MODEL", "gpt-4o")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=selected_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        max_tokens=300
    )
    final_reply = clean_reply(response.choices[0].message.content)

    # Quality check for saving (keep as-is)
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

# ====== TONE ADJUSTMENT (SHORT PROMPT, ONLY THE REPLY) ======

def adjust_tone(original_reply, selected_tone):
    if not selected_tone or selected_tone == "None":
        return original_reply

    prompt = (
        f"Rewrite this message in a more {selected_tone.lower()} tone, while still sounding like a human having a natural conversation. "
        f"\n\nMessage:\n{original_reply[:600]}"
    )

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert at rephrasing text to match a conversational tone with emotional intelligence."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=300
    )
    return clean_reply(response.choices[0].message.content)
