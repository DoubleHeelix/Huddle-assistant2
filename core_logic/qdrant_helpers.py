from qdrant_client import QdrantClient  # ✅ just use official package
import os
from dotenv import load_dotenv

load_dotenv()

def get_qdrant_client():
    return QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
