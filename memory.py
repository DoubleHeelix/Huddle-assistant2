import csv
import os
from datetime import datetime

MEMORY_FILE = "huddle_memory.csv"

def save_interaction(screenshot_text, user_draft, ai_suggested, user_final=None):
    exists = os.path.isfile(MEMORY_FILE)
    with open(MEMORY_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not exists:
            writer.writerow(["timestamp", "screenshot_text", "user_draft", "ai_suggested", "user_final"])
        writer.writerow([datetime.now(), screenshot_text, user_draft, ai_suggested, user_final or ""])

def load_all_interactions():
    if not os.path.isfile(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return list(reader)