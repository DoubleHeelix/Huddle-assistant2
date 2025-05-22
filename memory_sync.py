# memory_sync.py

from doc_embedder import embed_documents
from notion_embedder import embed_huddles

print("🧠 Starting full memory sync...")

try:
    embed_documents()
    print("✅ Docs memory embedded.")
except Exception as e:
    print("❌ Failed to embed docs:", e)

try:
    embed_huddles()
    print("✅ Huddle memory embedded.")
except Exception as e:
    print("❌ Failed to embed huddles:", e)
