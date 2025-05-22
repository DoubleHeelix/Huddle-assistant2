# suggestor.py

import openai
import os
from chromadb import PersistentClient
from dotenv import load_dotenv
from openai import OpenAI
from memory_vector import embed_and_store_interaction
from memory_vector import retrieve_similar_examples
import os
from chroma_client import get_chroma_client

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Helper to flatten Chroma query results
def zip_query_results(results):
    return [
        {
            "document": doc,
            "source": meta.get("source", "unknown")
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]

def retrieve_similar_examples(screenshot_text, user_draft):
    #chroma_client = PersistentClient(path="local_chroma_db")  # local dev path
    #chroma_client = PersistentClient(path="/mnt/data/chroma_memory") # Prod

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

    huddles = huddle_collection.query(query_texts=[huddle_query], n_results=5)
    docs = docs_collection.query(query_texts=[doc_query], n_results=5)

    return zip_query_results(huddles), zip_query_results(docs)

def suggest_reply(screenshot_text, user_draft, principles):
    huddle_matches, doc_matches = retrieve_similar_examples(screenshot_text, user_draft)

    huddle_context = "\n---\n".join(
        f"Source: {m['source']}\nContent: {m['document']}" for m in huddle_matches
    )
    doc_context = "\n---\n".join(
        f"Source: {m['source']}\nContent: {m['document']}" for m in doc_matches
    )

    prompt = f"""
You are a Huddle Assistant. Here are some memory references:

🧠 From past Huddles:
{huddle_context}

📄 From Communication Docs:
{doc_context}

Based on the screenshot and user draft, generate a reply that follows these principles:
{principles}

Screenshot: {screenshot_text}
Draft: {user_draft}

Reply:
"""

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful and concise network marketing assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    final_reply = response.choices[0].message.content.strip()

    # ✅ Save the interaction to Chroma memory
    embed_and_store_interaction(
        screenshot_text=screenshot_text,
        user_draft=user_draft,
        ai_suggested=final_reply
    )

    return final_reply, doc_matches