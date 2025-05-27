# memory_sync.py (Qdrant-based)

from doc_embedder import embed_documents_parallel   # make sure this is the Qdrant version
from notion_embedder import embed_huddles_qdrant  # your updated Qdrant embedder

pdf_dir = "public"
collection_name = "docs_memory"
VECTOR_SIZE = 1536
print("🧠 Starting full memory sync using Qdrant...")

try:
    embed_documents_parallel(pdf_dir, collection_name, VECTOR_SIZE)
    print("✅ Docs memory embedded in Qdrant.")
except Exception as e:
    print("❌ Failed to embed docs:", e)

try:
    embed_huddles_qdrant()
    print("✅ Huddle memory embedded in Qdrant.")
except Exception as e:
    print("❌ Failed to embed huddles:", e)
