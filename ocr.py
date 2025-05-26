import openai
import os
import base64
from dotenv import load_dotenv
from PIL import Image
import io
import pytesseract  # <-- Make sure this is installed

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def preprocess_image(image_path, max_dim=1080):
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

def extract_text_from_image(image_path, tesseract_min_length=8):
    # --- Step 1: Fast Local OCR ---
    try:
        text = pytesseract.image_to_string(Image.open(image_path)).strip()
        # Simple check: if text is not just whitespace and has some length, use it
        if len(text) >= tesseract_min_length and any(c.isalnum() for c in text):
            return text
    except Exception as e:
        pass  # If Tesseract fails, fallback below

    # --- Step 2: Fallback to OpenAI GPT-4o OCR ---
    image_bytes = preprocess_image(image_path)
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
    