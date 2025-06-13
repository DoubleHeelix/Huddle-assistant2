import schedule
import time
"""Background daemon to periodically sync Notion huddles into Qdrant."""

from notion_embedder import embed_huddles_qdrant

def job():
    print("🧠 Syncing huddles from Notion...")
    embed_huddles_qdrant()

schedule.every(10).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
