import os
import requests
from dotenv import load_dotenv

# Get absolute path to project root .env file
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ENV_PATH = os.path.join(BASE_DIR, '.env')

load_dotenv(dotenv_path=ENV_PATH)

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

def send_message(recipient_number, message_text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "text",
        "text": {"body": message_text}
    }

    response = requests.post(url, headers=headers, json=payload)
    print("📡 WhatsApp API Response:", response.status_code, response.text)

    if response.status_code != 200:
        print("❌ WhatsApp API error")

# ✅ New function: download image media
def download_media(media_id):
    # Step 1: Get media URL
    media_url_endpoint = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    params = {"fields": "url"}

    res = requests.get(media_url_endpoint, headers=headers, params=params)
    res.raise_for_status()

    media_url = res.json().get("url")

    # Step 2: Download actual media file
    media_res = requests.get(media_url, headers=headers)
    media_res.raise_for_status()

    print("📥 Image successfully downloaded from WhatsApp")

    return media_res.content  # return raw image bytes
