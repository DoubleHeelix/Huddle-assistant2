import openai
import os
import base64
from dotenv import load_dotenv
from PIL import Image, ImageOps
import io
import pytesseract
import numpy as np

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
    
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import numpy as np

def preprocess_for_tesseract(img):
    # 1. Convert to grayscale (L mode)
    img = img.convert('L')
    # 2. Auto-contrast to stretch black/white
    img = ImageOps.autocontrast(img)
    # 3. Sharpen (helps small fonts)
    img = img.filter(ImageFilter.SHARPEN)
    # 4. Binarize: adaptive threshold for Messenger backgrounds
    np_img = np.array(img)
    threshold = np.mean(np_img) - 30  # Lower threshold, can adjust -10 to -40 if needed
    binarized = np.where(np_img > threshold, 255, 0).astype(np.uint8)
    img = Image.fromarray(binarized, 'L')
    # 5. Optionally enlarge image if text is small (improves OCR accuracy)
    if img.width < 1000:
        img = img.resize((img.width * 2, img.height * 2), Image.BICUBIC)
    return img

def auto_crop_chat_area(img):
    """
    Attempts to crop only the main chat content area of a Messenger screenshot.
    Returns the cropped image.
    """
    # Convert to grayscale and numpy array for analysis
    gray = img.convert('L')
    arr = np.array(gray)

    # Compute horizontal and vertical projections (sum of pixel intensity)
    horiz_proj = np.sum(arr < 240, axis=1)  # "content" rows (not white)
    vert_proj = np.sum(arr < 240, axis=0)

    # Define thresholds: if enough non-white pixels, likely message area
    h_thresh = int(0.02 * arr.shape[1])  # 2% of row has content
    v_thresh = int(0.01 * arr.shape[0])  # 1% of column has content

    # Find top and bottom bounds
    top = np.argmax(horiz_proj > h_thresh)
    bottom = len(horiz_proj) - np.argmax(horiz_proj[::-1] > h_thresh)

    # Find left and right bounds
    left = np.argmax(vert_proj > v_thresh)
    right = len(vert_proj) - np.argmax(vert_proj[::-1] > v_thresh)

    # Add a small margin (optional, for aesthetics)
    margin = 10
    top = max(0, top - margin)
    bottom = min(arr.shape[0], bottom + margin)
    left = max(0, left - margin)
    right = min(arr.shape[1], right + margin)

    cropped = img.crop((left, top, right, bottom))
    return cropped


def extract_text_from_image(image_path, tesseract_min_length=8):
    # Defensive check
    if not image_path or not os.path.isfile(image_path):
        print(f"[ERROR] Invalid image_path passed to extract_text_from_image: {image_path}")
        return ""

    # --- Step 1: Fast Local OCR with Enhanced Preprocessing ---
    try:
        with Image.open(image_path) as img:
            # Auto-crop to chat area!
            cropped_img = auto_crop_chat_area(img)
            pre_img = preprocess_for_tesseract(img)
            text = pytesseract.image_to_string(pre_img, config="--psm 6").strip()
            print(f"[DEBUG] Tesseract OCR result: '{text}'")
            if len(text) >= tesseract_min_length and any(c.isalnum() for c in text):
                return text
    except Exception as e:
        print(f"[ERROR] Tesseract failed: {e}")

    # --- Step 2: Fallback to OpenAI GPT-4o OCR ---
    try:
        print("[INFO] Falling back to OpenAI Vision OCR...")
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
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ERROR] OpenAI Vision fallback failed: {e}")
        return ""
