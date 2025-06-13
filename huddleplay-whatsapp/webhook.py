from fastapi import FastAPI, Request
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
print("Loaded VERIFY_TOKEN:", VERIFY_TOKEN)

@app.get("/webhook")
async def verify(request: Request):
    params = dict(request.query_params)
    print("🟡 Meta webhook verification received:")
    print(params)

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        print("🟢 Verification passed. Returning challenge...")
        return int(challenge)
    else:
        print("🔴 Verification failed.")
        return {"status": "invalid token"}, 403
    
@app.post("/webhook")
async def webhook_post(request: Request):
    data = await request.json()
    print("🟢 Webhook POST received:")
    print(data)
    
    # Optional: Insert your actual message processing logic here

    return {"status": "received"}
