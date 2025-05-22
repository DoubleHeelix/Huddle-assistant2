import os
from notion_client import Client
from chromadb import PersistentClient
from dotenv import load_dotenv

load_dotenv()
notion = Client(auth=os.getenv("NOTION_API_KEY"))
database_id = os.getenv("NOTION_MEMORY_DB_ID")

def fetch_huddles():
    results = notion.databases.query(database_id=database_id).get("results", [])
    print("✅ Notion rows found:", len(results))
    huddles = []

    for page in results:
        try:
            props = page["properties"]
            get_text = lambda field: props.get(field, {}).get("rich_text", [])
            combined_text = f"""
Screenshot: {get_text("Screenshot Text")[0]['plain_text'] if get_text("Screenshot Text") else ""}
Draft: {get_text("User Draft")[0]['plain_text'] if get_text("User Draft") else ""}
AI Reply: {get_text("AI Suggested")[0]['plain_text'] if get_text("AI Suggested") else ""}
Final Edit: {get_text("User Final")[0]['plain_text'] if get_text("User Final") else ""}
""".strip()
            huddles.append({"id": page["id"], "text": combined_text})
        except Exception as e:
            print(f"⚠️ Skipped a row due to error: {e}")

    return huddles


def embed_huddles():
    #chroma_client = PersistentClient(path="local_chroma_db")  # local dev path
    chroma_client = PersistentClient(path="/mnt/data/chroma_memory") # Prod
    collection_name = "huddle_memory"
    if collection_name in [c.name for c in chroma_client.list_collections()]:
        chroma_client.delete_collection(name=collection_name)
    collection = chroma_client.create_collection(name=collection_name)

    huddles = fetch_huddles()
    for idx, h in enumerate(huddles):
        collection.add(
            documents=[h["text"]],
            ids=[f"notion_{idx}"],
            metadatas=[{"source": "notion", "page_id": h["id"]}]
        )
    print(f"✅ Embedded {collection.count()} huddles into '{collection_name}'")


# ✅ This block must be outside any function
if __name__ == "__main__":
    print("📥 Running Notion embedder...")
    huddles = fetch_huddles()
    print("📦 Previewing first huddle:", huddles[0] if huddles else "No huddles found.")
    embed_huddles()


