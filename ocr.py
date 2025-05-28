import os
import time
from google.cloud import vision
import io
from dotenv import load_dotenv

# Load environment variables (e.g., for GOOGLE_APPLICATION_CREDENTIALS if not set globally)
load_dotenv()

# Note: The Google Cloud Vision client (vision.ImageAnnotatorClient())
# will automatically use the GOOGLE_APPLICATION_CREDENTIALS environment variable
# if it's set correctly.

def extract_text_from_image(image_path_or_bytes):
    """
    Extracts text from an image using Google Cloud Vision API.
    :param image_path_or_bytes: Path to the image file or the image bytes.
    :return: Extracted text as a string, or an empty string if an error occurs or no text is found.
    """
    start_time = time.time()
    print(f"OCR: Starting text extraction. Input type: {type(image_path_or_bytes)}")

    try:
        # Initialize client per call - generally robust.
        # Ensure GOOGLE_APPLICATION_CREDENTIALS env var is set and points to a valid service account JSON key file.
        gcv_client = vision.ImageAnnotatorClient()

        content = None
        if isinstance(image_path_or_bytes, str):  # If it's a file path
            if not os.path.exists(image_path_or_bytes):
                print(f"OCR Error: Image path does not exist: {image_path_or_bytes}")
                return ""
            try:
                with io.open(image_path_or_bytes, 'rb') as image_file:
                    content = image_file.read()
                print(f"OCR: Successfully read {len(content)} bytes from path: {image_path_or_bytes}")
            except Exception as e:
                print(f"OCR Error: Failed to read image file from path {image_path_or_bytes}: {e}")
                return ""
        elif isinstance(image_path_or_bytes, bytes):  # If it's already image bytes
            content = image_path_or_bytes
            print(f"OCR: Received {len(content)} bytes directly.")
        else:
            print(f"OCR Error: Invalid input type for OCR. Expected image path (str) or bytes. Got {type(image_path_or_bytes)}.")
            return ""

        if not content: # Double check if content is None or empty after trying to load
            print("OCR Error: Image content is empty or could not be loaded.")
            return ""

        # Prepare the image for the Vision API
        image = vision.Image(content=content)

        # Perform document text detection (generally good for screenshots with structured text)
        print("OCR: Sending request to Google Cloud Vision API (document_text_detection)...")
        response = gcv_client.document_text_detection(image=image)

        if response.error.message:
            # This means the API call itself had an issue (e.g., auth, permissions, invalid request)
            print(f"OCR API Error: {response.error.message}")
            # You might want to raise an exception here or handle it more specifically
            raise Exception(f"Google Cloud Vision API Error: {response.error.message}")

        extracted_text = ""
        if response.full_text_annotation:
            extracted_text = response.full_text_annotation.text
            print(f"OCR: Successfully extracted text. Length: {len(extracted_text)}")
            if not extracted_text.strip():
                 print("OCR Warning: Extracted text is empty or only whitespace. Full annotation might have details.")
        else:
            # This means the API call was successful, but it found no text annotations.
            print("OCR Warning: No text found by API (full_text_annotation is missing or empty).")
            print("OCR Debug: Full API Response object for no-text scenario:")
            # Be cautious printing the full response if it could contain sensitive data,
            # but for debugging 'no text' it can be very helpful.
            # For now, let's just indicate its status.
            print(str(response)[:1000]) # Print first 1000 chars of response string

        end_time = time.time()
        processing_time = end_time - start_time
        print(f"OCR: Google Cloud Vision processing completed in {processing_time:.2f} seconds.")
        
        return extracted_text.strip()

    except Exception as e:
        end_time = time.time()
        processing_time = end_time - start_time
        print(f"OCR Error: Unexpected exception during Google Cloud Vision API call (took {processing_time:.2f}s): {e}")
        # Consider logging the full traceback here in a real application for better debugging
        # import traceback
        # print(traceback.format_exc())
        return ""


# --- Functions related to PIL, Pytesseract, and local cropping ---
# These are not currently used by extract_text_from_image but kept for reference
# if you decide to re-introduce local processing steps or fallbacks.

from PIL import Image # PIL is used by auto_crop_chat_area
import numpy as np   # Numpy is used by auto_crop_chat_area

def auto_crop_chat_area(img: Image.Image, margin: int = 12) -> Image.Image:
    """
    Attempts to auto-crop the main chat content area from a screenshot.
    - margin: extra pixels to add as border (default 12)
    """
    try:
        gray = img.convert('L')
        arr = np.array(gray)
        content_mask = arr < 230 # Pixels darker than near-white
        rows_content = np.sum(content_mask, axis=1)
        cols_content = np.sum(content_mask, axis=0)

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

        if top >= bottom or left >= right: # Check for invalid crop box
            print("Auto-crop Warning: Invalid crop box calculated, returning original image.")
            return img
            
        return img.crop((left, top, right, bottom))
    except Exception as e:
        print(f"Auto-crop Error: {e}. Returning original image.")
        return img

# image_path_to_base64 is not typically needed when sending bytes directly
# or using the client library's ability to read from a path.
# import base64
# def image_path_to_base64(image_path):
#     with open(image_path, "rb") as f:
#         image_bytes = f.read()
#     return base64.b64encode(image_bytes).decode("utf-8")


# Example Usage (for testing ocr.py directly):
if __name__ == '__main__':
    print("Running OCR test...")
    # Ensure GOOGLE_APPLICATION_CREDENTIALS is set in your environment
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("CRITICAL OCR TEST ERROR: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
    else:
        print(f"GOOGLE_APPLICATION_CREDENTIALS is set to: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
        
        # --- IMPORTANT: Create a test image named 'test_image.jpeg' in the same directory as ocr.py ---
        # --- Or, change 'test_image_path' to point to your actual input_file_0.jpeg ---
        test_image_path = "input_file_0.jpeg" # <--- MAKE SURE THIS FILE EXISTS where you run the script

        if os.path.exists(test_image_path):
            print(f"\n--- Test 1: Extracting text from image path: {test_image_path} ---")
            extracted_text_from_path = extract_text_from_image(test_image_path)
            print(f"\nExtracted Text (from path):\n---\n{extracted_text_from_path}\n---\n")

            print(f"\n--- Test 2: Extracting text from image bytes (reading from {test_image_path}) ---")
            try:
                with open(test_image_path, "rb") as f:
                    image_bytes_for_test = f.read()
                if image_bytes_for_test:
                    extracted_text_from_bytes = extract_text_from_image(image_bytes_for_test)
                    print(f"\nExtracted Text (from bytes):\n---\n{extracted_text_from_bytes}\n---\n")
                else:
                    print("Failed to read bytes for Test 2.")
            except Exception as e:
                print(f"Error in Test 2 (reading bytes): {e}")
        else:
            print(f"OCR TEST ERROR: Test image '{test_image_path}' not found. Please create it or update the path.")