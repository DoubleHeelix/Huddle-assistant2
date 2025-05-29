import openai
import os
import re
from dotenv import load_dotenv
from openai import OpenAI # Updated import
from qdrant_client import QdrantClient
# Assuming vectorizer.py contains embed_single
from vectorizer import embed_single # Make sure this import is correct and vectorizer.py is in your project path
import google.generativeai as genai

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
    client = None

# ====== CONSTANTS =======
MAX_HUDDLES_CONTEXT = 3 
MAX_DOCS_CONTEXT = 2    
MAX_CHUNK_LEN_CONTEXT = 400 
VECTOR_SIZE = 1536 

# Collection names for Qdrant
HUDDLE_MEMORY_COLLECTION = "huddle_memory"
DOCS_MEMORY_COLLECTION = "docs_memory"

SYSTEM_PROMPT = (
    "You are a warm, emotionally intelligent, and concise assistant trained for network marketing conversations. "
    "Your replies should sound human, personal, and naturally flowing—never robotic, scripted, or overly formal. "
    "Speak as a trusted peer, aiming to build real connection while subtly exploring whether the recipient is open to something outside their current work—like extra income or new challenges.\n\n"

    "KEY GUIDELINES:\n"
    "1. CONTEXT-FIRST: Carefully read both the screenshot and user's draft. Your message should naturally continue the conversation, not just rephrase the draft—refine it with clarity and direction.\n"
    "2. KEEP CONVO GOING: If the draft lacks a question or forward motion, add a natural, open-ended question based on the flow or recipient’s situation to invite response.\n"
    "3. TONE MATCHING: Reflect the recipient’s tone—casual, curious, upbeat, etc.—while staying warm, curious, and non-salesy.\n"
    "4. SOFT OPPORTUNITY FRAMING: The goal is to gently explore if they’re open to new ideas or income streams. Don’t pitch. Focus on curiosity, values, or current priorities.\n"
    "5. AVOID CLICHÉS: Never use terms like 'financial freedom,' 'passive income,' 'amazing opportunity,' or 'mentorship.' Use grounded, relatable language.\n"
    "6. FOLLOW HUDDLE PRINCIPLES: Clarity, Connection, Brevity, Flow, Empathy.\n"
    "7. NO PREFACES: Never start with 'Draft:' or 'Here's a suggestion.' Just write the reply as if you're sending it directly."
)


# ====== UTILITIES ======

def clean_reply(text):
    if not isinstance(text, str):
        return "" 
        
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text) 
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE) 
    
    phrases_to_remove = [
        "This is a draft", "Draft:", "Suggested reply:", 
        "Here is your response:", "Rewritten Message:", "Okay, here's a draft:",
        "Here's a revised version:", "Here's a suggestion for your reply:",
        "Sure, here's a reply you could use:", "Here's a possible response:",
        "Here is a draft for your reply:", "Response:", "Message:",
        "Reply:"
    ]
    
    for phrase in phrases_to_remove:
        if text.lower().startswith(phrase.lower()):
            text = text[len(phrase):].lstrip(": ").lstrip()
            break 
            
    return text.strip()

def zip_qdrant_results_for_context(results, max_chunk_len):
    out = []
    seen_content_for_context = set()
    if not results:
        return out

    for r in results:
        if r.payload: 
            doc_content = r.payload.get("document", r.payload.get("text", "")) 
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
    try:
        qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
    except Exception as e:
        print(f"Error initializing Qdrant client in get_context_for_reply: {e}")
        return "", "", [] 

    combined_query_for_huddles = screenshot_text + "\n" + user_draft
    query_for_docs = user_draft 

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
    
    doc_matches_for_display = doc_examples_for_context # For UI display

    seen_for_llm_prompt = set() 
    
    huddle_context_lines = []
    for ex in huddle_examples_for_context:
        content = f"🧠 Past Huddle Example (source: {ex['source']}):\n{ex['document']}"
        if ex['document'] not in seen_for_llm_prompt: 
            huddle_context_lines.append(content)
            seen_for_llm_prompt.add(ex['document'])
            
    doc_context_lines = []
    for ex in doc_examples_for_context:
        content = f"📄 Relevant Document (source: {ex['source']}):\n{ex['document']}"
        if ex['document'] not in seen_for_llm_prompt: 
            doc_context_lines.append(content)
            seen_for_llm_prompt.add(ex['document'])

    huddle_context_str = "\n\n".join(huddle_context_lines) if huddle_context_lines else "No relevant past huddle examples found."
    doc_context_str = "\n\n".join(doc_context_lines) if doc_context_lines else "No relevant documents found."
    
    return huddle_context_str, doc_context_str, doc_matches_for_display


# ====== NON-STREAMING SUGGESTION (MODIFIED FOR REGENERATION) ======
def generate_suggested_reply(screenshot_text, user_draft, principles, model_name, 
                             huddle_context_str, doc_context_str,
                             is_regeneration=False): # Added is_regeneration flag
    """
    Generates an AI reply suggestion (non-streaming).
    If is_regeneration is True, it adjusts the prompt and temperature for a different angle.
    """
    if not client:
        print("Error: OpenAI client not initialized in suggestor.")
        return "Error: OpenAI client not initialized."

    truncated_screenshot = screenshot_text[:1200] 
    truncated_draft = user_draft[:600]        

    user_prompt_content = (
        f"KEY PRINCIPLES FOR YOUR REPLY (Strictly Follow These):\n{principles}\n\n"
        "CONTEXT FROM SIMILAR PAST HUDDLES:\n"
        f"{huddle_context_str}\n\n" 
        "CONTEXT FROM RELEVANT DOCUMENTS:\n"
        f"{doc_context_str}\n\n"     
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

    current_temperature = 0.65 # Default temperature

    if is_regeneration:
        user_prompt_content += (
            "\n\nIMPORTANT REGENERATION INSTRUCTION:\n"
            "You have provided a suggestion before for this scenario. "
            "Now, please provide a *significantly different* angle or approach. "
            "Explore alternative ways to phrase the core message or focus on different aspects of the user's draft or the conversation context. "
            "Be creative, offer a fresh perspective, and ensure this new suggestion is distinct from any previous ones for this exact request."
        )
        current_temperature = 0.75 # Slightly higher temperature for more varied regeneration
    selected_model = model_name or os.getenv("OPENAI_MODEL", "gpt-4o")
    
    try:
        response = client.chat.completions.create( 
            model=selected_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt_content}
            ],
            temperature=current_temperature, # Use the determined temperature
            max_tokens=400  
        )
        raw_reply = response.choices[0].message.content
        return clean_reply(raw_reply) 
    except openai.APIError as e: 
        error_message = f"OpenAI API Error generating suggestion: {e}"
        print(error_message)
        return f"Error: {error_message}" 
    except Exception as e:
        error_message = f"Unexpected error generating suggestion: {e}"
        print(error_message)
        return f"Error: {error_message}"


# ====== NON-STREAMING TONE ADJUSTMENT ======
def generate_adjusted_tone(original_reply, selected_tone, model_name=None):
    """
    Adjusts the tone of the original reply (non-streaming).
    """
    if not client:
        print("Error: OpenAI client not initialized in suggestor.")
        return original_reply 

    if not selected_tone or selected_tone.lower() == "none":
        return original_reply

    truncated_original_reply = original_reply[:1000] 

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

    selected_model_for_tone = model_name or os.getenv("OPENAI_MODEL_TONE", os.getenv("OPENAI_MODEL", "gpt-4o"))

    try:
        response = client.chat.completions.create( 
            model=selected_model_for_tone,
            messages=[
                {"role": "system", "content": tone_system_prompt},
                {"role": "user", "content": tone_user_prompt}
            ],
            temperature=0.7, 
            max_tokens=400 
        )
        raw_adjusted_reply = response.choices[0].message.content
        return clean_reply(raw_adjusted_reply) 
    except openai.APIError as e: 
        error_message = f"OpenAI API Error adjusting tone: {e}"
        print(error_message)
        return original_reply 
    except Exception as e:
        error_message = f"Unexpected error adjusting tone: {e}"
        print(error_message)
        return original_reply