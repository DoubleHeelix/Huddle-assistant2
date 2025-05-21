import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def suggest_reply(screenshot_text, user_draft, principles):
    prompt = f"""
You are a Huddle Coach. You are helping refine replies for network marketers.

Screenshot text:
{screenshot_text}

User's draft reply:
{user_draft}

Principles to follow:
{principles}

Return a refined message that improves clarity, tone, and leadership.
"""
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6
    )
    return response.choices[0].message.content.strip()