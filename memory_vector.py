import os
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from openai import OpenAI
from dotenv import load_dotenv
import hashlib

load_dotenv()

# Setup
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

COLLECTION_NAME = "huddle_memory"

# Ensure collection exists
def ensure_collection():
    if COLLECTION_NAME not in [c.name for c in qdrant.get_collections().collections]:
        qdrant.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )

ensure_collection()

# Embed with OpenAI
def get_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

# Store a new huddle
def embed_and_store_interaction(screenshot_text, user_draft, ai_suggested, user_final=None):
    combined_text = f"{screenshot_text}\n\n{user_draft}"
    vector = get_embedding(combined_text)
    metadata = {
        "screenshot": screenshot_text,
        "draft": user_draft,
        "ai": ai_suggested,
        "final": user_final or ""
    }
    uid = hashlib.md5((combined_text + ai_suggested).encode()).hexdigest()
    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=uid, vector=vector, payload=metadata)]
    )

def retrieve_similar_examples(screenshot_text, user_draft, top_k=3, score_threshold=0.7):
    import os
    from qdrant_client import QdrantClient

    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )

    query = f"{screenshot_text}\n\n{user_draft}"
    vector = get_embedding(query)

    search_result = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=top_k,
        with_payload=True,
        with_vectors=False
    )

    examples = []
    for point in search_result:
        payload = point.payload or {}
        score = point.score

        if score < score_threshold:
            continue

        examples.append({
            "screenshot_text": payload.get("screenshot", ""),
            "user_draft": payload.get("draft", ""),
            "ai_reply": payload.get("ai", ""),
            "score": round(score, 3),
            "boost": payload.get("boost", 1.0),
            "point_id": point.id  # ✅ Required for boosting
        })

    return examples

