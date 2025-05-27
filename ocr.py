import openai
import os
import base64
from dotenv import load_dotenv
from PIL import Image
import pytesseract
import numpy as np

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def auto_crop_chat_area(img: Image.Image, margin: int = 12) -> Image.Image:
    """
    Attempts to auto-crop the main chat content area from a screenshot.
    - margin: extra pixels to add as border (default 12)
    """
    # Convert to grayscale and get numpy array
    gray = img.convert('L')
    arr = np.array(gray)

    # Treat "content" as any pixel darker than near-white (e.g. <230)
    content_mask = arr < 230

    # Sum non-white pixels per row/column
    rows_content = np.sum(content_mask, axis=1)
    cols_content = np.sum(content_mask, axis=0)

    # Find bounds where content exists
    def first_true(a): return np.argmax(a)
    def last_true(a): return len(a) - np.argmax(a[::-1]) - 1

    top = first_true(rows_content > 5)
    bottom = last_true(rows_content > 5)
    left = first_true(cols_content > 5)
    right = last_true(cols_content > 5)

    # Add margin, clamp to image size
    top = max(0, top - margin)
    left = max(0, left - margin)
    bottom = min(arr.shape[0] - 1, bottom + margin)
    right = min(arr.shape[1] - 1, right + margin)

    # Return cropped image
    return img.crop((left, top, right, bottom))


def image_path_to_base64(image_path):
    # Read the image file in full, no resizing, for best OCR accuracy
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    return base64.b64encode(image_bytes).decode("utf-8")

def extract_text_from_image(image_path, tesseract_min_length=8, crop_chat=True):
    # --- Step 1: Fast Local OCR (Tesseract) ---
    try:
        with Image.open(image_path) as img:
            if crop_chat:
                img = auto_crop_chat_area(img)
            text = pytesseract.image_to_string(img).strip()
            print(f"[DEBUG] Tesseract OCR result: '{text}'")
            # Simple check: if text is not just whitespace and has some length, use it
            if len(text) >= tesseract_min_length and any(c.isalnum() for c in text):
                return text
    except Exception as e:
        print(f"[Tesseract Error] {e}")
        pass  # If Tesseract fails, fallback below

    # --- Step 2: Fallback to OpenAI GPT-4o OCR ---
    try:
        image_base64 = image_path_to_base64(image_path)
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
    except Exception as e:
        print(f"[OpenAI Vision OCR Error] {e}")
        return ""

