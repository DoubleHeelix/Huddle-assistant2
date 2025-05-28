import openai
import os
import base64
from dotenv import load_dotenv
from PIL import Image
import pytesseract
import numpy as np
import time
from google.cloud import vision # Main import
import io

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

def extract_text_from_image(image_path_or_bytes):
    """
    Extracts text from an image using Google Cloud Vision API.
    :param image_path_or_bytes: Path to the image file or the image bytes.
    :return: Extracted text as a string.
    """
    start_time = time.time()
    
    try:
        # Option 2: Initialize client per call (more robust for dynamic environments)
        client = vision.ImageAnnotatorClient()

        content = None
        if isinstance(image_path_or_bytes, str): # If it's a file path
            if not os.path.exists(image_path_or_bytes):
                print(f"Error: Image path does not exist: {image_path_or_bytes}")
                return ""
            with io.open(image_path_or_bytes, 'rb') as image_file:
                content = image_file.read()
        elif isinstance(image_path_or_bytes, bytes): # If it's already image bytes
            content = image_path_or_bytes
        # elif isinstance(image_path_or_bytes, Image.Image): # If you pass a PIL Image object
        #     byte_arr = io.BytesIO()
        #     image_path_or_bytes.save(byte_arr, format='PNG') # Or appropriate format
        #     content = byte_arr.getvalue()
        else:
            print("Error: Invalid input type for OCR. Must be image path or bytes.")
            return ""

        if not content:
            print("Error: Image content is empty.")
            return ""

        image = vision.Image(content=content)

        # Perform text detection
        # TEXT_DETECTION is good for sparse text in images.
        # DOCUMENT_TEXT_DETECTION is better for dense text, like documents/pages (often more accurate for screenshots with lots of text).
        # Choose the one that fits your typical screenshots better. Let's use DOCUMENT_TEXT_DETECTION.
        response = client.document_text_detection(image=image)
        # response = client.text_detection(image=image) # Alternative

        if response.error.message:
            raise Exception(
                f'{response.error.message}\nFor more info on error messages, check: '
                'https://cloud.google.com/apis/design/errors'
            )

        # The fullTextAnnotation contains the entire recognized text.
        # For text_detection, you might iterate through response.text_annotations and take the first one's description.
        extracted_text = response.full_text_annotation.text if response.full_text_annotation else ""
        
        end_time = time.time()
        print(f"Google Cloud Vision OCR completed in {end_time - start_time:.2f} seconds.")
        return extracted_text.strip()

    except Exception as e:
        end_time = time.time()
        print(f"Error during Google Cloud Vision API call (took {end_time - start_time:.2f}s): {e}")
        return ""

# Example Usage (for testing ocr.py directly):
# if __name__ == '__main__':
#     # Ensure GOOGLE_APPLICATION_CREDENTIALS is set in your environment
#     # And you have a test image e.g., 'test_screenshot.png'
#     if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
#         print("Error: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
#     else:
#         # Create a dummy image file for testing if you don't have one
#         # from PIL import Image, ImageDraw
#         # img = Image.new('RGB', (400, 100), color = (200, 200, 200))
#         # d = ImageDraw.Draw(img)
#         # d.text((10,10), "Hello from Test Image", fill=(0,0,0))
#         # img.save("test_screenshot.png")
#
#         test_image_path = "test_screenshot.png" # Replace with your test image
#         if os.path.exists(test_image_path):
#             text = extract_text_from_image(test_image_path)
# print(f"Extracted Text:\n---\n{text}\n---")
# else:
# print(f"Test image {test_image_path} not found.")

