# suggestor.py

import openai
import os
from dotenv import load_dotenv
from openai import OpenAI
from memory_vector import embed_and_store_interaction
from chroma_client import get_chroma_client

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Helper to flatten Chroma query results with truncation
MAX_HUDDLES = 3
MAX_DOCS = 2
MAX_CHUNK_LEN = 500

def zip_query_results(results):
    return [
        {
            "document": doc[:MAX_CHUNK_LEN].strip(),
            "source": meta.get("source", "unknown")
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]

def retrieve_similar_examples(screenshot_text, user_draft):
    chroma_client = get_chroma_client()

    collections = [c.name for c in chroma_client.list_collections()]
    if "huddle_memory" not in collections:
        raise RuntimeError("🧠 'huddle_memory' not found — please run embed_huddles().")
    if "docs_memory" not in collections:
        raise RuntimeError("📄 'docs_memory' not found — please run embed_documents().")

    huddle_collection = chroma_client.get_collection("huddle_memory")
    docs_collection = chroma_client.get_collection("docs_memory")

    huddle_query = screenshot_text + "\n" + user_draft
    doc_query = user_draft

    huddles = huddle_collection.query(query_texts=[huddle_query], n_results=MAX_HUDDLES)
    docs = docs_collection.query(query_texts=[doc_query], n_results=MAX_DOCS)

    return zip_query_results(huddles), zip_query_results(docs)

def suggest_reply(screenshot_text, user_draft, principles):
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

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.7
    )

    final_reply = response.choices[0].message.content.strip()

    embed_and_store_interaction(
        screenshot_text=screenshot_text,
        user_draft=user_draft,
        ai_suggested=final_reply
    )

    return final_reply, doc_matches
