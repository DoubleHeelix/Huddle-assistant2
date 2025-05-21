import openai
import os
import base64
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_image(image_path):
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    { "type": "text", "text": "Extract all readable text from this image." },
                    { "type": "image_url", "image_url": { "url": f"data:image/png;base64,{image_base64}" } }
                ]
            }
        ]
    )

    return response.choices[0].message.content.strip()
