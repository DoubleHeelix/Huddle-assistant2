import os
import openai
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

embedding_function = OpenAIEmbeddingFunction(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.PersistentClient(path="chroma_db")
collection = chroma_client.get_or_create_collection(
    name="huddle_memory",
    embedding_function=embedding_function
)

def embed_and_store_interaction(screenshot_text, user_draft, ai_suggested, user_final=None):
    combined_text = f"{screenshot_text}\n\n{user_draft}"
    metadata = {
        "screenshot": screenshot_text,
        "draft": user_draft,
        "ai": ai_suggested,
        "final": user_final or ""
    }
    uid = str(hash(combined_text + ai_suggested))
    collection.add(documents=[combined_text], metadatas=[metadata], ids=[uid])

def retrieve_similar_examples(screenshot_text, user_draft, top_k=3):
    query = f"{screenshot_text}\n\n{user_draft}"
    results = collection.query(query_texts=[query], n_results=top_k)
    return results["metadatas"][0] if results["metadatas"] else []
