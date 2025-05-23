import os
from dotenv import load_dotenv
import openai
from memory import save_huddle_to_notion
from memory_vector import embed_and_store_interaction

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def suggest_reply(screenshot_text, user_draft, principles):
    prompt = f"""
You are a Huddle Coach helping refine replies in a network marketing setting.
Do not include any greeting like "Hey [Name]" or "Hi [Name]" — begin the message directly with the key reply. Assume the message will be pasted mid-conversation.

Screenshot text:
{screenshot_text}

User's draft reply:
{user_draft}

Huddle principles to follow:
{principles}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6
    )

    final_reply = response.choices[0].message.content.strip()

    # ✅ Save to CSV
    save_huddle_to_notion(
    screenshot_text=screenshot_text,
    user_draft=user_draft,
    ai_reply=final_reply,
    user_final=None
)

    # ✅ Save to vector memory
    embed_and_store_interaction(screenshot_text, user_draft, final_reply)

   

    return final_reply
