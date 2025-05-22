import os
from notion_client import Client
from dotenv import load_dotenv
from chroma_client import get_chroma_client  # Local/prod selector

load_dotenv()

notion = Client(auth=os.getenv("NOTION_API_KEY"))
database_id = os.getenv("NOTION_MEMORY_DB_ID")
collection_name = "huddle_memory"

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
    chroma_client = get_chroma_client()

    # Safely delete and recreate the collection
    existing = [c.name for c in chroma_client.list_collections()]
    if collection_name in existing:
        chroma_client.delete_collection(name=collection_name)
        print(f"🗑️ Deleted existing collection: {collection_name}")
    
    collection = chroma_client.create_collection(name=collection_name)
    print(f"📁 Created new collection: {collection_name}")

    huddles = fetch_huddles()

    for idx, h in enumerate(huddles):
        collection.add(
            documents=[h["text"]],
            ids=[f"notion_{idx}"],
            metadatas=[{"source": "notion", "page_id": h["id"]}]
        )

    print(f"✅ Embedded {collection.count()} huddles into '{collection_name}'")


if __name__ == "__main__":
    print("📥 Running Notion embedder...")
    embed_huddles()
