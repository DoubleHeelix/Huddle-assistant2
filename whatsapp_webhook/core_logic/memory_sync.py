# memory_sync.py (Qdrant-based)

from doc_embedder import embed_documents_parallel   # make sure this is the Qdrant version
from notion_embedder import embed_huddles_qdrant  # your updated Qdrant embedder
import logging

pdf_dir = "public"
collection_name = "docs_memory"
VECTOR_SIZE = 1536
logging.basicConfig(level=logging.INFO)
print("🧠 Starting full memory sync using Qdrant...")

try:
    logging.info("📄 Embedding documents from /public")
    embed_documents_parallel("public", "docs_memory", 1536)
    logging.info("✅ Docs memory embedded in Qdrant.")
except Exception as e:
    logging.error(f"❌ Failed to embed docs: {e}")

try:
    logging.info("💬 Embedding Notion huddles")
    embed_huddles_qdrant()
    logging.info("✅ Huddle memory embedded in Qdrant.")
except Exception as e:
    logging.error(f"❌ Failed to embed huddles: {e}")
