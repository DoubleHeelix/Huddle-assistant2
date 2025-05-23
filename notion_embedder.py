def embed_huddles_qdrant():
    from huddle_fetcher import fetch_huddles
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, VectorParams, Distance
    from vectorizer import embed_batch
    from uuid import uuid4
    import os

    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )

    collection_name = "huddle_memory"
    VECTOR_SIZE = 1536

    try:
        client.get_collection(collection_name)
    except:
        print(f"📁 Creating collection: {collection_name}")
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    huddles = fetch_huddles()
    print(f"🔎 Found {len(huddles)} huddles to embed")

    batch_size = 20
    for i in range(0, len(huddles), batch_size):
        batch = huddles[i:i+batch_size]
        texts = [h["text"] for h in batch]
        vectors = embed_batch(texts)

        points = []
        for h, vec in zip(batch, vectors):
            points.append(
                PointStruct(
                    id=str(uuid4()),
                    vector=vec,
                    payload={
                        "source": "notion",
                        "page_id": h["id"],
                        "last_edited": h["last_edited"]
                    }
                )
            )

        client.upsert(collection_name=collection_name, points=points)
        print(f"✅ Uploaded batch {i//batch_size + 1} with {len(points)} huddles")

    print(f"✅ All {len(huddles)} huddles embedded into Qdrant.")
