import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.getenv("NOTION_API_KEY"))
database_id = os.getenv("NOTION_MEMORY_DB_ID")

# Text you want to remove
FIND_TEXT = "[Your Name]"
REPLACE_WITH = ""  # Leave empty to remove

# Fields you want to clean
FIELDS_TO_CLEAN = ["Screenshot Text", "User Draft", "AI Suggested", "User Final"]

def clean_text(text):
    return text.replace(FIND_TEXT, REPLACE_WITH)

def update_page_if_needed(page_id, updated_props):
    if updated_props:
        notion.pages.update(page_id=page_id, properties=updated_props)

def clean_notion_database():
    print("🔍 Scanning database...")
    response = notion.databases.query(database_id=database_id)
    pages = response.get("results", [])

    for page in pages:
        page_id = page["id"]
        props = page["properties"]
        updated_props = {}

        for field in FIELDS_TO_CLEAN:
            if field in props and props[field]["type"] == "rich_text":
                text_array = props[field]["rich_text"]
                if not text_array:
                    continue

                old_text = text_array[0]["plain_text"]
                new_text = clean_text(old_text)

                if old_text != new_text:
                    updated_props[field] = {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": new_text}
                        }]
                    }

        update_page_if_needed(page_id, updated_props)

    print("✅ Cleanup complete!")

if __name__ == "__main__":
    clean_notion_database()
