import openai
import os
import re
from dotenv import load_dotenv
from openai import OpenAI # Updated import
from qdrant_client import QdrantClient
# Assuming vectorizer.py contains embed_single
from vectorizer import embed_single # Make sure this import is correct and vectorizer.py is in your project path

load_dotenv()

# ====== API CLIENT INITIALIZATION ======
# Initialize client once
try:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable not set.")
    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"Critical Error initializing OpenAI client: {e}. Suggestor functions will not work.")
    # In a real app, you might want to raise this or handle it so the app doesn't start
    # or clearly indicates a critical failure. For now, client will be None.
    client = None

# ====== CONSTANTS ======
MAX_HUDDLES_CONTEXT = 3 # Max past huddles to use as context for the LLM
MAX_DOCS_CONTEXT = 2    # Max documents to use as context for the LLM
MAX_CHUNK_LEN_CONTEXT = 400 # Max length of each context chunk
VECTOR_SIZE = 1536 # Ensure this matches your embedding model

# Collection names for Qdrant
HUDDLE_MEMORY_COLLECTION = "huddle_memory"
DOCS_MEMORY_COLLECTION = "docs_memory"

SYSTEM_PROMPT = (
    "You are a warm, emotionally intelligent, and concise network marketing assistant. "
    "Write replies that feel personal, natural, and human. "
    "Mirror the user's tone and follow the 5 Huddle principles: Clarity, Connection, Brevity, Flow, Empathy. "
    "Avoid generic greetings (e.g., 'Hey there'), scripted language, or robotic/formal openers. "
    "NEVER start with 'Draft:', 'Here's a suggestion', etc. "
    "Write directly as if sending a message to the recipient in the conversation context."
)

# ====== UTILITIES ======

def clean_reply(text):
    """
    Cleans the AI-generated reply by removing common boilerplate,
    stripping whitespace, and normalizing newlines.
    This function is called AFTER the full text is streamed and collected.
    """
    if not isinstance(text, str):
        return "" # Return empty string for non-string inputs
        
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text) # Normalize multiple newlines
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE) # Remove leading spaces/tabs
    
    # List of phrases to remove if they appear at the beginning of the text
    phrases_to_remove = [
        "This is a draft", "Draft:", "Suggested reply:", 
        "Here is your response:", "Rewritten Message:", "Okay, here's a draft:",
        "Here's a revised version:", "Here's a suggestion for your reply:",
        "Sure, here's a reply you could use:", "Here's a possible response:",
        "Here is a draft for your reply:", "Response:", "Message:",
        "Reply:"
    ]
    
    # Case-insensitive removal
    for phrase in phrases_to_remove:
        if text.lower().startswith(phrase.lower()):
            # Remove the phrase and any immediately following colon or space
            text = text[len(phrase):].lstrip(": ").lstrip()
            break # Assume only one such prefix needs removal
            
    return text.strip()

def zip_qdrant_results_for_context(results, max_chunk_len):
    """
    Processes Qdrant search results to create formatted context items.
    Each item is a dictionary with 'document' and 'source'.
    Avoids adding literally identical document chunks.
    """
    out = []
    seen_content_for_context = set()
    if not results:
        return out

    for r in results:
        if r.payload: # Ensure payload exists
            doc_content = r.payload.get("document", r.payload.get("text", "")) # Check for 'text' field too
            source_info = r.payload.get("source", "unknown source")
            
            if doc_content and isinstance(doc_content, str):
                truncated_doc = doc_content[:max_chunk_len].strip()
                if truncated_doc and truncated_doc not in seen_content_for_context:
                    out.append({
                        "document": truncated_doc,
                        "source": source_info
                    })
                    seen_content_for_context.add(truncated_doc)
    return out

# ====== RETRIEVAL LOGIC FOR LLM CONTEXT ======

def get_context_for_reply(screenshot_text, user_draft):
    """
    Retrieves similar huddles and documents from Qdrant to build context strings for the LLM.
    Returns:
        - huddle_context_str: Formatted string of huddle examples for the prompt.
        - doc_context_str: Formatted string of document examples for the prompt.
        - doc_matches_for_display: Raw list of document matches (from docs_memory) suitable for UI display.
    """
    try:
        qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
    except Exception as e:
        print(f"Error initializing Qdrant client in get_context_for_reply: {e}")
        return "", "", [] # Return empty context if Qdrant client fails

    combined_query_for_huddles = screenshot_text + "\n" + user_draft
    # For documents, user_draft might be more specific, or a combination. Test what works best.
    query_for_docs = user_draft # Or combine if better: screenshot_text + "\n" + user_draft

    try:
        huddle_query_vector = embed_single(combined_query_for_huddles)
        doc_query_vector = embed_single(query_for_docs)
    except Exception as e:
        print(f"Error embedding query text in get_context_for_reply: {e}")
        return "", "", []

    huddle_matches_qdrant = []
    doc_matches_qdrant = []

    try:
        if huddle_query_vector:
            huddle_matches_qdrant = qdrant_client.search(
                collection_name=HUDDLE_MEMORY_COLLECTION,
                query_vector=huddle_query_vector,
                limit=MAX_HUDDLES_CONTEXT,
                with_payload=True
            )
    except Exception as e:
        print(f"Error searching {HUDDLE_MEMORY_COLLECTION}: {e}")

    try:
        if doc_query_vector:
            doc_matches_qdrant = qdrant_client.search(
                collection_name=DOCS_MEMORY_COLLECTION,
                query_vector=doc_query_vector,
                limit=MAX_DOCS_CONTEXT,
                with_payload=True
            )
    except Exception as e:
        print(f"Error searching {DOCS_MEMORY_COLLECTION}: {e}")
        
    huddle_examples_for_context = zip_qdrant_results_for_context(huddle_matches_qdrant, MAX_CHUNK_LEN_CONTEXT)
    doc_examples_for_context = zip_qdrant_results_for_context(doc_matches_qdrant, MAX_CHUNK_LEN_CONTEXT)

    # doc_matches_for_display should be the raw results from docs_memory for the UI
    # This is slightly different from doc_examples_for_context which is processed.
    # For simplicity, let's pass the processed ones, or you can pass doc_matches_qdrant (raw) if UI needs more.
    # For now, doc_examples_for_context will be used for display.
    doc_matches_for_display = doc_examples_for_context


    # --- Prepare context strings for the LLM prompt ---
    seen_for_llm_prompt = set() # Avoid duplicate *content* in the LLM prompt
    
    huddle_context_lines = []
    for ex in huddle_examples_for_context:
        content = f"🧠 Past Huddle Example (source: {ex['source']}):\n{ex['document']}"
        if ex['document'] not in seen_for_llm_prompt: # Check document content for uniqueness in prompt
            huddle_context_lines.append(content)
            seen_for_llm_prompt.add(ex['document'])
            
    doc_context_lines = []
    for ex in doc_examples_for_context:
        content = f"📄 Relevant Document (source: {ex['source']}):\n{ex['document']}"
        if ex['document'] not in seen_for_llm_prompt: # Check document content for uniqueness
            doc_context_lines.append(content)
            seen_for_llm_prompt.add(ex['document'])

    huddle_context_str = "\n\n".join(huddle_context_lines) if huddle_context_lines else "No relevant past huddle examples found."
    doc_context_str = "\n\n".join(doc_context_lines) if doc_context_lines else "No relevant documents found."
    
    return huddle_context_str, doc_context_str, doc_matches_for_display


# ====== STREAMING SUGGESTION ======

def stream_suggested_reply(screenshot_text, user_draft, principles, model_name, huddle_context_str, doc_context_str):
    """
    Generates an AI reply suggestion as a stream.
    """
    if not client:
        yield "Error: OpenAI client not initialized. Please check API key and ensure `suggestor.py` initialized correctly."
        return

    # Truncate main inputs for the prompt to manage token limits carefully
    # These are maximums; actual content sent will be based on these limits.
    # You might need to adjust these based on typical content length and model context window.
    truncated_screenshot = screenshot_text[:1200] 
    truncated_draft = user_draft[:600]        

    user_prompt_content = (
        f"KEY PRINCIPLES FOR YOUR REPLY (Strictly Follow These):\n{principles}\n\n"
        "CONTEXT FROM SIMILAR PAST HUDDLES:\n"
        f"{huddle_context_str}\n\n" # Already has "not found" message if empty
        "CONTEXT FROM RELEVANT DOCUMENTS:\n"
        f"{doc_context_str}\n\n"     # Already has "not found" message if empty
        "CURRENT CONVERSATION (FROM SCREENSHOT):\n"
        f"{truncated_screenshot}\n\n"
        "USER'S DRAFT IDEA (Use for inspiration on topic/intent. Improve it based on principles and context. Do NOT just rephrase the draft if it's weak or misses the mark.):\n"
        f"{truncated_draft}\n\n"
        "YOUR TASK:\n"
        "Craft the best, most natural, and human reply for this scenario. "
        "Adhere strictly to the system prompt and the key principles. "
        "Be direct—do not reference that this is a draft or a suggestion. "
        "Write the message exactly as if you were sending it to the person in the conversation."
    )

    selected_model = model_name or os.getenv("OPENAI_MODEL", "gpt-4o")
    
    try:
        response_stream = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt_content}
            ],
            temperature=0.65, # Slightly adjusted from 0.6
            max_tokens=400,  # Increased for potentially richer responses
            stream=True
        )
        for chunk in response_stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except openai.APIError as e: # More specific error handling
        error_message = f"OpenAI API Error generating suggestion: {e}"
        print(error_message)
        yield error_message
    except Exception as e:
        error_message = f"Unexpected error generating suggestion: {e}"
        print(error_message)
        yield error_message


# ====== STREAMING TONE ADJUSTMENT ======

def stream_adjusted_tone(original_reply, selected_tone, model_name=None):
    """
    Adjusts the tone of the original reply as a stream.
    """
    if not client:
        yield "Error: OpenAI client not initialized. Please check API key and ensure `suggestor.py` initialized correctly."
        return
        
    if not selected_tone or selected_tone.lower() == "none":
        yield original_reply # If no tone adjustment, just yield the original
        return

    # Truncate original reply to manage token limits for tone adjustment
    truncated_original_reply = original_reply[:1000] # Allow more of the original reply for context

    tone_system_prompt = (
        "You are an expert at rephrasing text to match a specific conversational tone with emotional intelligence. "
        "Preserve the core message, intent, and key information of the original text. "
        "Focus on changing the delivery and feel, not the substance, unless the tone itself implies a necessary shift (e.g. 'more direct' might shorten it). "
        "Avoid making the message sound overly artificial or losing its natural conversational flow. "
        "Do NOT add any preamble like 'Okay, here's the version in a ... tone'. Just provide the rephrased message directly."
    )
    
    tone_user_prompt = (
        f"Please rewrite the following message in a more {selected_tone.lower()} tone. "
        "Ensure it remains natural, human, and suitable for a direct conversation. "
        f"The message should still be concise and clear, reflecting the requested tone.\n\n"
        f"Original Message to rephrase:\n\"\"\"\n{truncated_original_reply}\n\"\"\""
    )

    # Use the main model_choice from app.py by default, or a specific one for tone if desired.
    selected_model_for_tone = model_name or os.getenv("OPENAI_MODEL_TONE", os.getenv("OPENAI_MODEL", "gpt-4o"))

    try:
        response_stream = client.chat.completions.create(
            model=selected_model_for_tone,
            messages=[
                {"role": "system", "content": tone_system_prompt},
                {"role": "user", "content": tone_user_prompt}
            ],
            temperature=0.7, 
            max_tokens=400,  # Match suggestion max_tokens
            stream=True
        )
        for chunk in response_stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except openai.APIError as e: # More specific error handling
        error_message = f"OpenAI API Error adjusting tone: {e}"
        print(error_message)
        yield error_message
    except Exception as e:
        error_message = f"Unexpected error adjusting tone: {e}"
        print(error_message)
        yield error_message