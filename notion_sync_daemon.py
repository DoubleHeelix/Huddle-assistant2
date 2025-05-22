import schedule
import time
from notion_embedder import embed_huddles

def job():
    print("🧠 Syncing huddles from Notion...")
    embed_huddles()

schedule.every(10).minutes.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
