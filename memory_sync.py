# memory_sync.py (Qdrant-based)

from doc_embedder import embed_documents  # make sure this is the Qdrant version
from notion_embedder import embed_huddles_qdrant  # your updated Qdrant embedder

print("🧠 Starting full memory sync using Qdrant...")

try:
    embed_documents()
    print("✅ Docs memory embedded in Qdrant.")
except Exception as e:
    print("❌ Failed to embed docs:", e)

try:
    embed_huddles_qdrant()
    print("✅ Huddle memory embedded in Qdrant.")
except Exception as e:
    print("❌ Failed to embed huddles:", e)
