# memory_sync.py

from doc_embedder import embed_documents
from notion_embedder import embed_huddles

if __name__ == "__main__":
    print("🔁 Syncing memory collections...")

    print("\n📄 Embedding communication docs...")
    embed_documents()

    print("\n🧠 Embedding Notion huddles...")
    embed_huddles()

    print("\n✅ All memory successfully embedded!")
