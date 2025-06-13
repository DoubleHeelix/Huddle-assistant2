# chroma_client.py
import os
from chromadb import PersistentClient

def get_chroma_client():
    storage_path = (
        "/mnt/data/chroma_memory" if os.getenv("ENV") == "prod" else "local_chroma_db"
    )
    return PersistentClient(path=storage_path)
