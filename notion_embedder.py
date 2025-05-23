from chroma_client import get_chroma_client
from notion_embedder import fetch_huddles  # make sure this returns `id`, `text`, and `last_edited`

collection_name = "huddle_memory"

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
