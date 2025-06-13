from notion_client import Client
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.getenv("NOTION_API_KEY"))
database_id = os.getenv("NOTION_MEMORY_DB_ID")

def save_huddle_to_notion(screenshot_text, user_draft, ai_reply, user_final=None):
    notion.pages.create(
        parent={"database_id": database_id},
        properties={
            "Timestamp": {
                "date": {"start": datetime.now().isoformat()}
            },
            "Screenshot Text": {
                "rich_text": [{"text": {"content": screenshot_text[:2000]}}]
            },
            "User Draft": {
                "rich_text": [{"text": {"content": user_draft[:2000]}}]
            },
            "AI Suggested": {
                "rich_text": [{"text": {"content": ai_reply[:2000]}}]
            },
            "User Final": {
                "rich_text": [{"text": {"content": user_final[:2000]}}] if user_final else []
            }
        }
    )
def load_all_interactions():
    results = notion.databases.query(database_id=database_id).get("results", [])
    interactions = []

    for page in results:
        props = page["properties"]
        interactions.append({
            "id": page["id"],
            "last_edited": page["last_edited_time"],
            "timestamp": props["Timestamp"]["date"]["start"] if props["Timestamp"]["date"] else "Unknown",
            "screenshot_text": props["Screenshot Text"]["rich_text"][0]["plain_text"] if props["Screenshot Text"]["rich_text"] else "",
            "user_draft": props["User Draft"]["rich_text"][0]["plain_text"] if props["User Draft"]["rich_text"] else "",
            "ai_suggested": props["AI Suggested"]["rich_text"][0]["plain_text"] if props["AI Suggested"]["rich_text"] else "",
            "user_final": props["User Final"]["rich_text"][0]["plain_text"] if props["User Final"]["rich_text"] else "",
        })

    return interactions
