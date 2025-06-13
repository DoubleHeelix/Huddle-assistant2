def embed_huddles_qdrant():
    from huddle_fetcher import fetch_huddles
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        PointStruct, VectorParams, Distance,
        Filter, FieldCondition, MatchValue
    )
    from vectorizer import embed_batch
    from uuid import uuid4
    import os

    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )

    collection_name = "huddle_memory"
    VECTOR_SIZE = 1536

    reset = os.getenv("QDRANT_RESET_COLLECTION", "false").lower() == "true"
    
    if reset:
        print(f"⚠️ Deleting existing collection: {collection_name}")
        try:
            client.delete_collection(collection_name=collection_name)
            print("✅ Collection deleted successfully.")
        except Exception as e:
            print(f"⚠️ Could not delete collection (may not exist): {e}")

    # Always recreate collection if it doesn't exist
    try:
        client.get_collection(collection_name)
    except:
        print(f"📁 Creating collection: {collection_name}")
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print("✅ Collection created.")

        # ✅ Add index so filtering by page_id works
        client.create_payload_index(
            collection_name=collection_name,
            field_name="page_id",
            field_schema="keyword"
        )
        print("✅ Index created on page_id.")

    # ✅ Optional: ensure index exists even if collection wasn't recreated
    try:
        indexes = client.get_collection(collection_name).payload_schema
        if "page_id" not in indexes:
            client.create_payload_index(
                collection_name=collection_name,
                field_name="page_id",
                field_schema="keyword"
            )
            print("✅ Index created on page_id (post-check).")
    except Exception as e:
        print(f"⚠️ Failed to verify or create index: {e}")

    all_huddles = fetch_huddles()
    print(f"🔎 Found {len(all_huddles)} huddles from Notion")

    huddles_to_embed = []

    for huddle in all_huddles:
        try:
            existing = client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="page_id", match=MatchValue(value=huddle["id"]))
                    ]
                ),
                limit=1
            )
            existing_payload = existing[0][0].payload if existing[0] else None
        except Exception as e:
            print(f"⚠️ Scroll failed for huddle {huddle['id']}: {e}")
            existing_payload = None

        if (
            not existing_payload or
            existing_payload.get("last_edited") != huddle["last_edited"]
        ):
            huddles_to_embed.append(huddle)

    print(f"🧠 {len(huddles_to_embed)} new or updated huddles to embed")

    batch_size = 20
    for i in range(0, len(huddles_to_embed), batch_size):
        batch = huddles_to_embed[i:i+batch_size]
        texts = [h["text"] for h in batch]
        vectors = embed_batch(texts)

        points = [
            PointStruct(
                id=str(uuid4()),
                vector=vec,
                payload={
                    "source": "notion",
                    "page_id": h["id"],
                    "last_edited": h["last_edited"]
                }
            )
            for h, vec in zip(batch, vectors)
        ]

        client.upsert(collection_name=collection_name, points=points)
        print(f"✅ Uploaded batch {i // batch_size + 1} with {len(points)} huddles")

    print(f"✅ Sync complete. {len(huddles_to_embed)} huddles embedded.")
