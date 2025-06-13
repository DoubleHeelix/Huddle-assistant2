from fastapi import FastAPI, Request
import os
from dotenv import load_dotenv
from whatsapp import send_message, download_media

from huddleplay import huddle_generate_reply

from core_logic.ocr import extract_text_from_image

# Get absolute path to project root .env file
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ENV_PATH = os.path.join(BASE_DIR, '.env')

load_dotenv(dotenv_path=ENV_PATH)
app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
print("Loaded VERIFY_TOKEN:", VERIFY_TOKEN)

# In-memory store for user state. A more robust solution like Redis would be better for production.
user_image_state = {}

@app.get("/webhook")
async def verify(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    else:
        return {"status": "invalid token"}, 403

@app.post("/webhook")
async def webhook_post(request: Request):
    data = await request.json()
    print("🟢 Webhook POST received:", data)

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for message in messages:
                    user_id = message.get("from")

                    if message["type"] == "image":
                        media_id = message["image"]["id"]
                        user_image_state[user_id] = media_id
                        print(f"📷 Image received from {user_id}, media ID: {media_id}. Awaiting draft.")
                        send_message(user_id, "Go ahead and draft up a message")

                    elif message["type"] == "text":
                        incoming_text = message["text"]["body"]
                        print(f"💬 Received text from {user_id}: {incoming_text}")

                        if user_id in user_image_state:
                            media_id = user_image_state.pop(user_id)  # Retrieve and clear state
                            print(f"🖼️ Found pending image for {user_id}. Processing image and text together.")

                            image_bytes = download_media(media_id)
                            extracted_text = extract_text_from_image(image_bytes)
                            print(f"📝 OCR Extracted: {extracted_text}")

                            # Combine screenshot text and user draft for the AI
                            # A more sophisticated approach might involve modifying huddle_generate_reply
                            # to accept two distinct arguments.
                            combined_input = f"SCREENSHOT CONTEXT:\n{extracted_text}\n\nDRAFT MESSAGE:\n{incoming_text}"
                            reply_text = huddle_generate_reply(user_id, combined_input)
                            
                        else:
                            # No pending image, process text only
                            print(f"📝 No pending image for {user_id}. Processing text only.")
                            reply_text = huddle_generate_reply(user_id, incoming_text)

                        send_message(user_id, reply_text)

    except Exception as e:
        print("❌ Error processing message:", e)

    return {"status": "received"}
