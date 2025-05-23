from notion_client import Client
import os
from dotenv import load_dotenv
from chroma_client import get_chroma_client

load_dotenv()

notion = Client(auth=os.getenv("NOTION_API_KEY"))
database_id = os.getenv("NOTION_MEMORY_DB_ID")
collection_name = "huddle_memory"  # <-- 🔧 required to fix the error



def fetch_huddles():
    pages = notion.databases.query(database_id=database_id).get("results", [])
    huddles = []

    for page in pages:
        props = page["properties"]
        page_id = page["id"]
        last_edited = page["last_edited_time"]

        # Safely extract text from properties
        screenshot_text = props["Screenshot Text"]["rich_text"][0]["plain_text"] if props["Screenshot Text"]["rich_text"] else ""
        user_draft = props["User Draft"]["rich_text"][0]["plain_text"] if props["User Draft"]["rich_text"] else ""
        ai_suggested = props["AI Suggested"]["rich_text"][0]["plain_text"] if props["AI Suggested"]["rich_text"] else ""
        user_final = props["User Final"]["rich_text"][0]["plain_text"] if props["User Final"]["rich_text"] else ""

        # Compose the full body of text to embed
        full_text = f"""Screenshot: {screenshot_text}

User Draft: {user_draft}

AI Suggested: {ai_suggested}

User Final: {user_final}"""

        huddles.append({
            "id": page_id,
            "text": full_text,
            "last_edited": last_edited
        })

    return huddles

def embed_huddles():
    chroma_client = get_chroma_client()

    if collection_name not in [c.name for c in chroma_client.list_collections()]:
        collection = chroma_client.create_collection(name=collection_name)
        print(f"📁 Created new collection: {collection_name}")
    else:
        collection = chroma_client.get_collection(collection_name)

    print("📥 Fetching Notion huddles...")
    huddles = fetch_huddles()  # must return: id, text, last_edited

    existing_ids = set(collection.get(ids=None)["ids"])  # All currently embedded
    new_count = 0

    for idx, h in enumerate(huddles):
        huddle_id = f"notion_{h['id']}"
        if huddle_id in existing_ids:
            continue  # already embedded

        collection.add(
            documents=[h["text"]],
            ids=[huddle_id],
            metadatas=[{
                "source": "notion",
                "page_id": h["id"]
                # optionally store last_edited timestamp
            }]
        )
        new_count += 1

    print(f"✅ Embedded {new_count} new huddles into '{collection_name}'")