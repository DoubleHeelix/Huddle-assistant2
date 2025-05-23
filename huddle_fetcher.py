from notion_client import Client
import os
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.getenv("NOTION_API_KEY"))
database_id = os.getenv("NOTION_MEMORY_DB_ID")

def fetch_huddles():
    pages = notion.databases.query(database_id=database_id).get("results", [])
    huddles = []

    for page in pages:
        props = page["properties"]
        page_id = page["id"]
        last_edited = page["last_edited_time"]

        screenshot_text = props["Screenshot Text"]["rich_text"][0]["plain_text"] if props["Screenshot Text"]["rich_text"] else ""
        user_draft = props["User Draft"]["rich_text"][0]["plain_text"] if props["User Draft"]["rich_text"] else ""
        ai_suggested = props["AI Suggested"]["rich_text"][0]["plain_text"] if props["AI Suggested"]["rich_text"] else ""
        user_final = props["User Final"]["rich_text"][0]["plain_text"] if props["User Final"]["rich_text"] else ""

        full_text = f"""Screenshot: {screenshot_text}\n\nUser Draft: {user_draft}\n\nAI Suggested: {ai_suggested}\n\nUser Final: {user_final}"""

        huddles.append({
            "id": page_id,
            "text": full_text,
            "last_edited": last_edited
        })

    return huddles
