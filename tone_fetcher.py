from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, SearchRequest
from sentence_transformers import SentenceTransformer
import os
from notion_client import Client


client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

model = SentenceTransformer("all-MiniLM-L6-v2")
collection_name = "tone_training_memory"

notion = Client(auth=os.getenv("NOTION_API_KEY"))
TONE_TRAINING_DB = os.getenv("NOTION_TONE_DB_ID")

def fetch_tone_training_examples():
    pages = notion.databases.query(database_id=TONE_TRAINING_DB)["results"]

    examples = []
    for page in pages:
        props = page["properties"]

        examples.append({
            "id": page["id"],
            "text": props["Story Text"]["title"][0]["plain_text"] if props["Story Text"]["title"] else "",
            "tone": props["Tone"]["rich_text"][0]["plain_text"] if props["Tone"]["rich_text"] else "",
            "your_message": props["Your Message"]["rich_text"][0]["plain_text"] if props["Your Message"]["rich_text"] else "",
            "ai_message": props["AI Message"]["rich_text"][0]["plain_text"] if props["AI Message"]["rich_text"] else "",
            "last_edited": page["last_edited_time"]
        })

    return examples


def retrieve_similar_tone_example(query_text, tone, top_k=1):
    # Embed query
    query_vector = model.encode(f"{query_text} — {tone}").tolist()

    # Filter by tone (if present in the payloads)
    search_filter = Filter(
        must=[FieldCondition(key="tone", match=MatchValue(value=tone))]
    )

    try:
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=search_filter,
            with_payload=True
        )

        if results:
            best = results[0].payload
            return best.get("your_message"), best.get("tone")
    except Exception as e:
        print(f"⚠️ Retrieval failed: {e}")

    return None, None

def embed_tone_training_qdrant():
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        PointStruct, VectorParams, Distance,
        Filter, FieldCondition, MatchValue
    )
    from vectorizer import embed_batch
    from uuid import uuid4
    import os
    from tone_fetcher import fetch_tone_training_examples

    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )

    collection_name = "tone_training_memory"
    VECTOR_SIZE = 1536

    try:
        client.get_collection(collection_name)
    except:
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        client.create_payload_index(
            collection_name=collection_name,
            field_name="page_id",
            field_schema="keyword"
        )

    all_examples = fetch_tone_training_examples()
    print(f"🔎 Found {len(all_examples)} tone examples from Notion")

    to_embed = []
    for ex in all_examples:
        try:
            existing = client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="page_id", match=MatchValue(value=ex["id"]))
                    ]
                ),
                limit=1
            )
            existing_payload = existing[0][0].payload if existing[0] else None
        except Exception as e:
            print(f"⚠️ Scroll failed for tone entry {ex['id']}: {e}")
            existing_payload = None

        if (
            not existing_payload or
            existing_payload.get("last_edited") != ex["last_edited"]
        ):
            to_embed.append(ex)

    print(f"🧠 {len(to_embed)} new or updated tone entries to embed")

    batch_size = 20
    for i in range(0, len(to_embed), batch_size):
        batch = to_embed[i:i+batch_size]
        texts = [f"{ex['text']} — {ex['tone']}" for ex in batch]  # include tone for retrieval context
        vectors = embed_batch(texts)

        points = [
            PointStruct(
                id=str(uuid4()),
                vector=vec,
                payload={
                    "source": "notion",
                    "page_id": ex["id"],
                    "last_edited": ex["last_edited"],
                    "tone": ex["tone"],
                    "your_message": ex["your_message"]
                }
            )
            for ex, vec in zip(batch, vectors)
        ]

        client.upsert(collection_name=collection_name, points=points)
        print(f"✅ Uploaded batch {i // batch_size + 1} with {len(points)} examples")

    print(f"✅ Tone training sync complete. {len(to_embed)} examples embedded.")