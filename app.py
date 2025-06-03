import streamlit as st
import os
import tempfile
import time
import re
import uuid
from PIL import Image
from dotenv import load_dotenv
import io
from ocr import extract_text_from_image 
import streamlit.components.v1 as components
from openai import OpenAI
import openai
import base64
import html
from notion_client import Client

# === Internal imports ====
from memory import save_huddle_to_notion, load_all_interactions
from memory_vector import embed_and_store_interaction, retrieve_similar_examples # For displaying similar examples
# Updated imports from suggestor.py
from suggestor import (
    get_context_for_reply,
    generate_suggested_reply,
    generate_adjusted_tone,
    clean_reply  # Import clean_reply
)
from ocr import extract_text_from_image
from doc_embedder import embed_documents_parallel
from notion_embedder import embed_huddles_qdrant
from qdrant_client import QdrantClient

try:
    load_dotenv()
except Exception as e:
    st.warning(f"Error loading .env file: {e}")

PDF_DIR = "public"
COLLECTION_NAME = "docs_memory" # For embedding general documents
HUDDLE_MEMORY_COLLECTION = "huddle_memory" # For past huddles
VECTOR_SIZE = 1536

st.set_page_config(page_title="Huddle Assistant", layout="centered")

# ---- HEADER ----
st.markdown("""
    <div style="
        background: linear-gradient(135deg, #8a3ffc, #b88cff);
        padding: 20px; border-radius: 12px; color: white;
        text-align: center; font-family: 'Segoe UI', sans-serif;
        margin-bottom: 24px;">
        <h2 style="margin: 0;">🤝 Huddle Assistant</h2>
        <p style="margin: 4px 0 0 0; font-size: 14px;">
            Lead confident convos on the go
        </p>
    </div>
""", unsafe_allow_html=True)

# ---- Session State Initialization ----
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ---- CSS for Spacing & Tabs ----
st.markdown("""
<style>
section.main > div {padding-top: 0rem !important; padding-bottom: 0rem !important;}
.css-1kyxreq, .stSelectbox, .stMarkdown, .stSubheader {margin-bottom: 0.5rem !important; margin-top: 0.5rem !important;}
.st-expander {margin-top: -0.5rem !important;}
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem !important; background: none !important;
    border-bottom: 2px solid #27273a !important; margin-bottom: 0px !important;
    padding: 0 6vw !important; justify-content: left;
}
.stTabs [data-baseweb="tab"] {
    color: #8a3ffc !important; font-weight: 600; font-size: 1.05rem;
    padding: 8px 16px !important; border-radius: 16px 16px 0 0;
    background: none !important; transition: background 0.18s;
    margin-bottom: -2px;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(90deg, #8a3ffc 65%, #b88cff 100%) !important;
    color: #fff !important; border-bottom: 2.5px solid #8a3ffc !important;
    box-shadow: 0 2px 8px rgba(138,63,252,0.08);
}
.stTabs [aria-selected="false"]:hover {
    background: #ede9fe !important; color: #5d27c1 !important;
}
</style>
""", unsafe_allow_html=True)

# ---- Sidebar Settings ----
with st.sidebar.expander("🛠️ Quality Save Settings", expanded=False):
    min_words = st.slider("Minimum words in draft", 5, 20, 8, key="min_words_slider")
    min_chars = st.slider("Minimum characters in screenshot text", 10, 100, 20, key="min_chars_slider")
    require_question = st.checkbox("Require a question in the draft?", value=False, key="require_question_checkbox")

with st.sidebar.expander("⚙️ Admin Controls", expanded=False):
    st.markdown("#### AI Memory & Model Settings")
    model_choice = st.radio(
        "🤖 Choose AI Model",
        options=["gpt-4o", "gpt-3.5-turbo"],
        help="GPT-4o: best quality, GPT-3.5: fastest/cheapest",
        key="model_choice_radio"
    )
    st.markdown("---")
    embed_col, notion_col = st.columns(2)
    with embed_col:
        if st.button("📚 Re-embed Docs", key="re_embed_docs_button"):
            with st.spinner("Embedding communication docs..."):
                embed_documents_parallel(PDF_DIR, COLLECTION_NAME, VECTOR_SIZE)
            st.success("✅ Docs embedded successfully!")
    with notion_col:
        if st.button("🧠 Re-sync Notion", key="re_sync_notion_button"):
            with st.spinner("Syncing Notion huddles..."):
                embed_huddles_qdrant() # This should embed into HUDDLE_MEMORY_COLLECTION
            st.success("✅ Notion memory embedded successfully!")

#============tab 2 method==============
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_visual_and_generate_message(image):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You're a warm, human-sounding friend who sees a story on Instagram and wants to strike up a conversation based on what you see."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here's an Instagram story. Write a warm, casual, and real message that could start a conversation."},
                    {"type": "image_url", "image_url": {"url": image}},
                ]
            }
        ]
    )
    return response.choices[0].message.content

import streamlit as st
import re
import uuid
from html import escape # For displaying HTML safely
import streamlit.components.v1 as components # For reliable script execution

def render_polished_card(label, text_content, auto_copy=True): # Default auto_copy to True
    # 1. Prepare text for safe HTML display
    def format_text_html(text_to_format): # Renamed internal variable for clarity
        cleaned_text = str(text_to_format).strip()
        normalized = re.sub(r"\n{2,}", "\n\n", cleaned_text)
        html_ready = normalized.replace('\n', '<br>')
        return re.sub(r"^(<br\s*/?>\s*)+", "", html_ready, flags=re.IGNORECASE | re.MULTILINE)

    safe_html_text_for_display = format_text_html(text_content)

    # 2. Prepare text for JavaScript clipboard
    js_escaped_text_for_clipboard = str(text_content).replace("\\", "\\\\") \
                                                     .replace("`", "\\`") \
                                                     .replace('"', '\\"') \
                                                     .replace("\n", "\\n")

    # 3. Generate unique IDs
    card_instance_id = uuid.uuid4().hex[:8]
    unique_button_id = f"copy_btn_{card_instance_id}"
    unique_alert_id = f"copy_alert_{card_instance_id}"

    # 4. HTML for the button and alert
    copy_button_html_structure = f"""
        <button id="{unique_button_id}"
                title="Copy to clipboard"
                style="float: right; background: #444; color: white; border: none; 
                       padding: 6px 10px; border-radius: 6px; cursor: pointer;
                       font-size: 14px; line-height: 1;">
            📋 Copy
        </button>
        <span id="{unique_alert_id}" 
              style="display:none; float: right; margin-right: 8px; color: #90ee90; 
                     font-size: 13px; line-height: 1; padding-top: 7px;">
            Copied!
        </span>
    """

    # 5. Main card HTML structure
    st.markdown(f"""
    <style>
    .card-header-h4 {{
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    .card-header-h4 > span:first-of-type {{ margin-right: auto; }}
    .card-header-h4 > div.button-container {{ display: flex; align-items: center; }}
    </style>

    <div style="border-radius: 16px; padding: 20px; background-color: #1e1e1e; color: white; font-size: 16px; line-height: 1.6; box-shadow: 0 0 8px rgba(255,255,255,0.05);">
        <div class="card-header-h4">
            <span>✉️ {label}</span>
            <div class="button-container">{copy_button_html_structure}</div>
        </div>
        <div style="clear: both;"></div>
        <div>{safe_html_text_for_display}</div>
    </div>
    """, unsafe_allow_html=True)

    # 6. JavaScript for functionality, run via components.html
    script_to_run = f"""
    <script>
    (function() {{ // IIFE
        const textToCopy = `{js_escaped_text_for_clipboard}`;
        const copyButton = window.parent.document.getElementById('{unique_button_id}');
        const alertBox = window.parent.document.getElementById('{unique_alert_id}');

        function fallbackCopyTextToClipboard(text) {{
            const tempTextArea = document.createElement('textarea');
            tempTextArea.value = text;
            tempTextArea.style.position = 'absolute';
            tempTextArea.style.left = '-9999px';
            tempTextArea.style.top = '0';
            
            const doc = window.parent.document || document;
            doc.body.appendChild(tempTextArea);
            
            tempTextArea.focus();
            tempTextArea.select();

            let success = false;
            try {{
                success = doc.execCommand('copy');
                if (success) {{
                    alertBox.textContent = 'Copied!';
                    alertBox.style.color = '#90ee90';
                    console.log('Text copied via fallback (execCommand)');
                }} else {{
                    alertBox.textContent = 'Copy Failed';
                    alertBox.style.color = 'orange';
                    console.error('Fallback copy using execCommand failed (returned false).');
                }}
            }} catch (err) {{
                alertBox.textContent = 'Copy Error!';
                alertBox.style.color = 'red';
                console.error('Error during fallback copy using execCommand:', err);
            }}

            alertBox.style.display = 'inline-block';
            setTimeout(() => {{ alertBox.style.display = 'none'; }}, success ? 1500 : 2500);
            doc.body.removeChild(tempTextArea);
        }}

        if (copyButton && alertBox) {{
            copyButton.onclick = function() {{
                if (navigator && navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(textToCopy).then(() => {{
                        alertBox.textContent = 'Copied!';
                        alertBox.style.color = '#90ee90';
                        alertBox.style.display = 'inline-block';
                        setTimeout(() => {{ alertBox.style.display = 'none'; }}, 1500);
                        console.log('Text copied via navigator.clipboard');
                    }}).catch(err => {{
                        console.warn('navigator.clipboard.writeText failed with error:', err, '. Attempting fallback.');
                        fallbackCopyTextToClipboard(textToCopy);
                    }});
                }} else {{
                    console.warn('Clipboard API (navigator.clipboard) not available. Attempting fallback.');
                    fallbackCopyTextToClipboard(textToCopy);
                }}
            }};
        }} else {{
            if (!copyButton) console.error('Copy button ID {unique_button_id} not found in DOM.');
            if (!alertBox) console.error('Alert box ID {unique_alert_id} not found in DOM.');
        }}
        
        if ({str(auto_copy).lower()}) {{ // Handles the auto_copy parameter
            if (navigator && navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(textToCopy)
                    .then(() => console.log('Text auto-copied via navigator.clipboard'))
                    .catch(err => {{
                        console.warn('Auto-copy with navigator.clipboard failed:', err, '. Fallback for auto-copy might be too intrusive or not work without direct gesture.');
                        // Consider if fallback is appropriate for auto-copy or just log.
                        // fallbackCopyTextToClipboard(textToCopy); // Example: could try fallback
                    }});
            }} else {{
                console.warn('navigator.clipboard not available for auto-copy. Fallback generally not suitable for auto-copy.');
                // fallbackCopyTextToClipboard(textToCopy); // Generally avoid fallback for auto-copy
            }}
        }}
    }})();
    </script>
    """
    components.html(script_to_run, height=0)

# ---- Main Tabs ----
tab1, tab2, tab3 = st.tabs(["Huddle Play", "Interruptions", "📚 View Past Huddles"])

# =============== TAB 1: HUDDLE PLAY ===============

with tab1:
    with st.container():
        st.markdown("<div id='tab1-wrapper'>", unsafe_allow_html=True)
        
        # Define default session state values (includes keys for regeneration context)
        session_keys_defaults = {
            "final_reply_collected": None,
            "adjusted_reply_collected": None,
            "doc_matches_for_display": [],
            "screenshot_text_content": None,
            "user_draft_current": "", 
            "similar_examples_retrieved": None, # This is the key we want to manage
            "user_draft_widget_key": "user_draft_initial", 
            "current_tone_selection": "None",
            "last_uploaded_filename": None,
            "scroll_to_draft": False,
            "scroll_to_interruption": False,
            "huddle_context_for_regen": None, 
            "doc_context_for_regen": None,
            "principles_for_regen": None,
        }
        for key, default_value in session_keys_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value

        # --- Helper function for AI generation and saving ---
        def _handle_ai_generation_and_save(current_uploaded_image, is_regeneration=False):
            # ... (initial checks for current_uploaded_image and user_draft_current) ...
            # As in your provided code.

            # Make sure sidebar settings are accessed via st.session_state if needed within this function
            # e.g., st.session_state.min_words_slider

            if not current_uploaded_image and not st.session_state.screenshot_text_content:
                st.warning("Please upload an image.")
                return
            if not st.session_state.user_draft_current:
                st.warning("Please enter your draft message.")
                return

            st.session_state.adjusted_reply_collected = None 
            if not is_regeneration: 
                st.session_state.final_reply_collected = None  

            overall_processing_start_time = time.time()
            
            # --- OCR Handling ---
            if not is_regeneration or not st.session_state.screenshot_text_content:
                if current_uploaded_image: 
                    tmp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file: 
                            tmp_file.write(current_uploaded_image.getvalue())
                            tmp_path = tmp_file.name
                        
                        ocr_start_time = time.time()
                        with st.spinner("🔍 Extracting text from screenshot..."):
                            st.session_state.screenshot_text_content = extract_text_from_image(tmp_path)
                        print(f"OCR time: {(time.time() - ocr_start_time):.2f}s")
                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            os.remove(tmp_path)
                elif not st.session_state.screenshot_text_content: 
                    st.error("Critical Error: Screenshot text is missing and no image provided for OCR.")
                    return 

            if not st.session_state.screenshot_text_content or not st.session_state.screenshot_text_content.strip():
                st.warning("⚠️ Screenshot text couldn't be read clearly. Please try again or use a clearer image.")
                return

            # *********************************************************************
            # MODIFICATION: Retrieve similar_examples_retrieved FOR DISPLAY HERE
            # This runs only on initial generation.
            # *********************************************************************
            if not is_regeneration:
                with st.spinner("🧠 Retrieving similar past huddles for your reference..."):
                    examples_retrieval_start_time = time.time()
                    # This uses retrieve_similar_examples from memory_vector.py
                    st.session_state.similar_examples_retrieved = retrieve_similar_examples(
                        st.session_state.screenshot_text_content, 
                        st.session_state.user_draft_current
                    )
                    print(f"Similar examples (for display) retrieval: {(time.time() - examples_retrieval_start_time):.2f}s")
            # *********************************************************************
            # END OF MODIFICATION
            # *********************************************************************

            # --- Context Retrieval for LLM (from suggestor.py) ---
            context_spinner_msg = "📚 Retrieving context for AI..." 
            # (This section remains the same as your provided code, using stored context for regeneration)
            with st.spinner(context_spinner_msg):
                context_retrieval_start_time = time.time()
                if is_regeneration and st.session_state.huddle_context_for_regen is not None and \
                   st.session_state.doc_context_for_regen is not None and \
                   st.session_state.principles_for_regen is not None:
                    huddle_ctx_to_use = st.session_state.huddle_context_for_regen
                    doc_ctx_to_use = st.session_state.doc_context_for_regen
                    principles_to_use = st.session_state.principles_for_regen
                else: 
                    huddle_ctx_to_use, doc_ctx_to_use, doc_matches_disp = get_context_for_reply(
                        st.session_state.screenshot_text_content,
                        st.session_state.user_draft_current
                    )
                    st.session_state.doc_matches_for_display = doc_matches_disp
                    principles_to_use = '''
                    1.  **Clarity & Impact:** Is the core message instantly understandable and engaging?
                    2.  **Curiosity, Not Persuasion:** Does the reply invite dialogue with genuine questions rather than trying to sell or convince?
                    3.  **Build Rapport:** Does it strengthen the connection with the recipient, reflecting empathy and understanding?
                    4.  **Concise & Authentic:** Is it brief, warm, and does it sound like a real person, not a script?
                    5.  **Strategic Next Step:** Does it naturally guide the conversation towards understanding their needs or openness, in line with the Huddle flow?
                    '''
                    st.session_state.huddle_context_for_regen = huddle_ctx_to_use
                    st.session_state.doc_context_for_regen = doc_ctx_to_use
                    st.session_state.principles_for_regen = principles_to_use
                print(f"Context retrieval for LLM: {(time.time() - context_retrieval_start_time):.2f}s")


            # --- AI Reply Generation ---
            # (This section remains the same as your provided code)
            ai_spinner_msg = "🧠 Thinking of a new angle..." if is_regeneration else "🤖 Generating AI reply..."
            ai_gen_start_time = time.time()
            with st.spinner(ai_spinner_msg):
                generated_reply = generate_suggested_reply(
                    screenshot_text=st.session_state.screenshot_text_content,
                    user_draft=st.session_state.user_draft_current,
                    principles=principles_to_use,
                    model_name=st.session_state.model_choice_radio, 
                    huddle_context_str=huddle_ctx_to_use,
                    doc_context_str=doc_ctx_to_use,
                    is_regeneration=is_regeneration 
                )
            st.session_state.final_reply_collected = generated_reply 
            print(f"AI generation (is_regen={is_regeneration}): {(time.time() - ai_gen_start_time):.2f}s")

            if isinstance(generated_reply, str) and generated_reply.startswith("Error:"):
                st.error(f"AI Generation Failed: {generated_reply}")
                return 

            if is_regeneration:
                st.success("💡 New suggestion generated!")

            # --- Save or Fail Reason ---
            # (This section remains the same as your provided code)
            failure_reasons = []
            if len(st.session_state.user_draft_current.strip().split()) < st.session_state.min_words_slider:
                failure_reasons.append(f"- Draft: {len(st.session_state.user_draft_current.strip().split())} words (min: {st.session_state.min_words_slider})")
            # ... (rest of failure reasons and saving logic) ...
            if len(st.session_state.screenshot_text_content.strip()) < st.session_state.min_chars_slider: # Added from your original
                failure_reasons.append(f"- Screenshot: {len(st.session_state.screenshot_text_content.strip())} chars (min: {st.session_state.min_chars_slider})")
            if st.session_state.require_question_checkbox and "?" not in st.session_state.user_draft_current: # Added from your original
                failure_reasons.append("- Draft needs a question")
            
            is_quality = len(failure_reasons) == 0
            if is_quality:
                with st.spinner("💾 Saving huddle..."):
                    embed_and_store_interaction(
                        screenshot_text=st.session_state.screenshot_text_content,
                        user_draft=st.session_state.user_draft_current,
                        ai_suggested=st.session_state.final_reply_collected
                    )
                    save_huddle_to_notion(
                        st.session_state.screenshot_text_content,
                        st.session_state.user_draft_current,
                        st.session_state.final_reply_collected,
                        st.session_state.get("adjusted_reply_collected", "") 
                    )
                # Moved success message outside the 'if is_quality' if you want it always shown after attempting save
                st.success("💾 Stored Memory.") 
            else:
                st.warning("⚠️ This huddle wasn't saved:")
                for reason in failure_reasons: st.markdown(f"• {reason}")
            print(f"Total processing for generation step: {(time.time() - overall_processing_start_time):.2f}s")
        # --- End of _handle_ai_generation_and_save function ---

        # ---- Upload UI ----
        # (This section remains the same as your provided code)
        uploaded_image = st.file_uploader(
            "Upload image", type=["jpg", "jpeg", "png"],
            label_visibility="collapsed", key=f"upload_img_{st.session_state.uploader_key}"
        )
        if uploaded_image:
            try:
                st.image(uploaded_image, use_container_width=True) 
            except Exception as e:
                st.error(f"Error displaying image: {e}")

            current_filename = uploaded_image.name
            if st.session_state.last_uploaded_filename != current_filename:
                st.session_state.scroll_to_draft = True
                st.session_state.last_uploaded_filename = current_filename
                keys_to_reset_for_new_image = [
                    "final_reply_collected", "adjusted_reply_collected", "doc_matches_for_display",
                    "screenshot_text_content", "similar_examples_retrieved", # Make sure this is reset
                    "huddle_context_for_regen", "doc_context_for_regen", "principles_for_regen"
                ]
                for key_to_clear in keys_to_reset_for_new_image:
                    if key_to_clear in st.session_state: # Check if key exists before assigning from defaults
                        st.session_state[key_to_clear] = session_keys_defaults[key_to_clear]
                
                st.session_state.user_draft_current = "" 
                st.session_state.user_draft_widget_key = f"user_draft_new_img_{uuid.uuid4().hex[:6]}"

        # ---- Draft Anchor ----
        if st.session_state.scroll_to_draft: # Corrected condition
            components.html("""
                <script>
                    setTimeout(function() {
                        const el = window.parent.document.getElementById("draftAnchor");
                        if (el) {el.scrollIntoView({ behavior: "smooth", block: "start" });}
                    }, 400);
                </script>
            """, height=0)
            st.session_state.scroll_to_draft = False
        st.markdown("<div id='draftAnchor'></div>", unsafe_allow_html=True)

        # ---- Draft UI ----
        # (This section remains the same as your provided code)
        st.markdown(
            """<p style='margin-bottom: 4px; font-size: 1em; color: inherit; font-weight: normal; padding: 0; line-height: 1.5;'>Your Draft Message</p>""", 
            unsafe_allow_html=True
        )
        st.session_state.user_draft_current = st.text_area(
            "Internal draft message label for accessibility", 
            value=st.session_state.user_draft_current,
            label_visibility="collapsed", height=110, 
            key=st.session_state.user_draft_widget_key 
        )
        
        # ---- Action Buttons ----
        # (This section remains the same as your provided code)
        col1_gen, col2_regen = st.columns(2)
        with col1_gen:
            if st.button("🚀 Generate AI Reply", key="generate_reply_button_main", use_container_width=True):
                _handle_ai_generation_and_save(uploaded_image, is_regeneration=False) 
        with col2_regen:
            can_regenerate = bool(
                st.session_state.final_reply_collected and \
                st.session_state.screenshot_text_content and \
                st.session_state.user_draft_current and \
                st.session_state.huddle_context_for_regen is not None and \
                st.session_state.doc_context_for_regen is not None and \
                st.session_state.principles_for_regen is not None
            )
            if st.button("🔄 Regenerate", key="regenerate_button_again", use_container_width=True, disabled=not can_regenerate):
                if can_regenerate:
                    _handle_ai_generation_and_save(uploaded_image, is_regeneration=True) 
                else:
                    st.info("Generate an initial reply first, or ensure all inputs (image, draft) are present for context.")

        # ---- Display Final Reply and Tone Controls ----
        # (This section remains the same as your provided code)
        # ... (make sure to check for "Error:" in final_reply_collected before rendering) ...
        if st.session_state.final_reply_collected and not (isinstance(st.session_state.final_reply_collected, str) and st.session_state.final_reply_collected.startswith("Error:")):
            st.subheader("✅ Suggested Reply")
            # ... rest of the display and tone adjustment logic ...
            render_polished_card("Suggested Reply", st.session_state.final_reply_collected, auto_copy=True)
            
            if "current_tone_selection" not in st.session_state: 
                st.session_state.current_tone_selection = "None"

            tone_options = ["None", "Professional", "Casual", "Inspiring", "Empathetic", "Direct"]
            try:
                current_tone_idx = tone_options.index(st.session_state.current_tone_selection) if st.session_state.current_tone_selection in tone_options else 0
            except ValueError: 
                current_tone_idx = 0 

            st.session_state.current_tone_selection = st.selectbox(
                "🎨 Adjust Tone", 
                tone_options, 
                index=current_tone_idx,
                key="tone_selectbox_key"
            )
            
            if st.session_state.current_tone_selection != "None" and st.button("🎯 Regenerate with Tone", key="regenerate_tone_button"):
                st.session_state.adjusted_reply_collected = None 
                
                tone_generation_start_time = time.time()
                with st.spinner("🎨 Adjusting tone... Please wait."):
                    adjusted_reply = generate_adjusted_tone(
                        st.session_state.final_reply_collected, 
                        st.session_state.current_tone_selection,
                        st.session_state.model_choice_radio 
                    )
                st.session_state.adjusted_reply_collected = adjusted_reply
                print(f"Tone adjustment time: {(time.time() - tone_generation_start_time):.2f}s")

                if st.session_state.adjusted_reply_collected and not (isinstance(st.session_state.adjusted_reply_collected, str) and st.session_state.adjusted_reply_collected.startswith("Error:")):
                    failure_reasons_adj = []
                    if len(st.session_state.user_draft_current.strip().split()) < st.session_state.min_words_slider:
                        failure_reasons_adj.append(f"- Draft: {len(st.session_state.user_draft_current.strip().split())} words (min: {st.session_state.min_words_slider})")
                    if st.session_state.screenshot_text_content and len(st.session_state.screenshot_text_content.strip()) < st.session_state.min_chars_slider:
                        failure_reasons_adj.append(f"- Screenshot: {len(st.session_state.screenshot_text_content.strip())} chars (min: {st.session_state.min_chars_slider})")
                    elif not st.session_state.screenshot_text_content:
                         failure_reasons_adj.append("- Screenshot text not available for quality check.")
                    if st.session_state.require_question_checkbox and "?" not in st.session_state.user_draft_current:
                        failure_reasons_adj.append("- Draft needs a question")
                    
                    is_quality_adjusted = len(failure_reasons_adj) == 0
                    if is_quality_adjusted:
                        with st.spinner("💾 Saving adjusted huddle..."):
                            embed_and_store_interaction(
                                screenshot_text=st.session_state.screenshot_text_content,
                                user_draft=st.session_state.user_draft_current,
                                ai_suggested=st.session_state.adjusted_reply_collected
                            )
                            save_huddle_to_notion(
                                st.session_state.screenshot_text_content,
                                st.session_state.user_draft_current,
                                st.session_state.final_reply_collected, 
                                st.session_state.adjusted_reply_collected
                            )
                        st.success("💾 Memory Stored") # Corrected success message
                    else:
                        st.warning("⚠️ This adjusted huddle wasn't saved:")
                        for reason_adj in failure_reasons_adj: st.markdown(f"• {reason_adj}")
                elif st.session_state.adjusted_reply_collected and (isinstance(st.session_state.adjusted_reply_collected, str) and st.session_state.adjusted_reply_collected.startswith("Error:")):
                     st.error(f"Tone Adjustment Failed: {st.session_state.adjusted_reply_collected}")
        
        if st.session_state.adjusted_reply_collected and not (isinstance(st.session_state.adjusted_reply_collected, str) and st.session_state.adjusted_reply_collected.startswith("Error:")):
            st.subheader(f"🎉 Regenerated Reply ({st.session_state.current_tone_selection})")
            render_polished_card("Adjusted Reply", st.session_state.adjusted_reply_collected, auto_copy=True)

        # ---- Show Used Docs and Examples ----
        # (This section remains the same as your provided code, including the suggestedAnchor)
        st.markdown("<div id='suggestedAnchor'></div>", unsafe_allow_html=True)
        if st.session_state.doc_matches_for_display:
            # ... display logic ...
            st.subheader("📄 Relevant Communication Docs Used by AI")
            for match in st.session_state.doc_matches_for_display:
                if isinstance(match, dict): 
                    with st.expander(f"🧠 From: {match.get('source', 'Unknown')}"):
                        st.markdown(f"> {match.get('document', '')}")
                else:
                    st.warning(f"Unexpected document match format: {match}")
        elif st.session_state.final_reply_collected and not (isinstance(st.session_state.final_reply_collected, str) and st.session_state.final_reply_collected.startswith("Error:")): 
             st.info("No specific external documents were heavily weighted by the AI for this reply.")


        if st.session_state.similar_examples_retrieved: # This is the key part for your request
            st.subheader("🧠 Similar Past Huddle Plays (For Your Reference)")
            # ... (rest of the display logic for similar_examples_retrieved remains the same) ...
            examples_to_show = st.session_state.similar_examples_retrieved
            if isinstance(st.session_state.similar_examples_retrieved, tuple) and len(st.session_state.similar_examples_retrieved) > 0:
                 examples_to_show = st.session_state.similar_examples_retrieved[0] 

            if not examples_to_show:
                 st.info("No highly similar past huddle plays found in memory.")
            else:
                for idx, example in enumerate(examples_to_show):
                    payload = example.get("payload", example) if isinstance(example, dict) else {}
                    if not (isinstance(payload, dict) and \
                            any([payload.get(k) for k in ["screenshot_text", "user_draft", "ai_reply", "ai_suggested"]])):
                        continue 

                    with st.expander(f"🔁 Past Huddle {idx + 1} (Score: {example.score:.2f})" if hasattr(example, 'score') else f"🔁 Past Huddle {idx + 1}"):
                        st.markdown("**🖼 Screenshot Text**")
                        st.markdown(payload.get("screenshot_text") or "_Not available_")
                        st.markdown("**✍️ User Draft**")
                        st.markdown(payload.get("user_draft") or "_Not available_")
                        st.markdown("**🤖 Final AI Reply**")
                        st.markdown(payload.get("ai_reply") or payload.get("ai_suggested") or "_Not available_") 
                        
                        current_boost = float(payload.get("boost", 1.0))
                        point_id_val = example.id if hasattr(example, 'id') else payload.get("point_id")

                        if point_id_val and st.button(f"🔼 Boost This Example ({current_boost:.1f}x) {idx + 1}", key=f"boost_{point_id_val}_{idx}"):
                            new_boost = current_boost + 0.5 
                            try:
                                q_client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
                                q_client.set_payload(
                                    collection_name=HUDDLE_MEMORY_COLLECTION, 
                                    points=[point_id_val],
                                    payload={"boost": new_boost},
                                    wait=True
                                )
                                st.success(f"✅ Boosted to {new_boost:.1f}x. Effect visible on next generation.")
                                if 'payload' in example and isinstance(example['payload'], dict) : example['payload']['boost'] = new_boost
                                elif isinstance(example, dict): example['boost'] = new_boost
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ Failed to boost: {e}")
        elif st.session_state.final_reply_collected and not (isinstance(st.session_state.final_reply_collected, str) and st.session_state.final_reply_collected.startswith("Error:")): 
            st.info("No similar past huddle examples were retrieved for display during the initial generation.") # Clarified message

        # ---- Start New Huddle Button ----
        # (This section remains the same as your provided code)
        if st.button("➕ Start New Huddle", key="new_huddle_button_tab1", use_container_width=True):
            keys_to_potentially_delete = [k for k in st.session_state.keys() if k.startswith("upload_img_") or k.startswith("boost_") or k.startswith("tone_selectbox_key")]
            for k_del in keys_to_potentially_delete:
                if k_del in st.session_state:
                    del st.session_state[k_del]
            
            for k_clear in session_keys_defaults.keys(): 
                if k_clear in st.session_state:
                    st.session_state[k_clear] = session_keys_defaults[k_clear]
            
            st.session_state.uploader_key += 1 
            st.session_state.user_draft_current = ""  
            st.session_state.user_draft_widget_key = f"user_draft_{uuid.uuid4().hex[:6]}" 
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)  # End tab1-wrapper

# =============== TAB 2: VIEW DOCUMENTS ===============
def generate_conversation_starter(text, image_url=None):
    """
    Generates a conversation starter based on story text and/or image,
    without relying on a pre-classified tone/category tag, and with more
    directive prompting for image analysis.
    """
    guidance_line = ""
    # Attempt to get guidance IF text is present.
    if text.strip():
        print(f"DEBUG: Text present. Attempting to get guidance for text: '{text[:50]}...'")
        try:
            from tone_fetcher import retrieve_similar_tone_example # Ensure this is correctly imported
            # Pass an empty string or a very generic tag if your function expects one but shouldn't rely on it heavily here
            human_example, matched_tone_for_guidance = retrieve_similar_tone_example(text, "") # Passing empty tag
            if human_example:
                guidance_line = f"Previously, for similar text content, a human-like reply was: \"{human_example}\""
            else:
                guidance_line = "No specific similar past reply example found for guidance based on text."
        except ImportError:
            print("DEBUG: tone_fetcher or retrieve_similar_tone_example not found. Skipping text-based guidance.")
            guidance_line = "Guidance retrieval for text content is unavailable."
        except Exception as e:
            print(f"DEBUG: Error retrieving guidance for text: {e}")
            guidance_line = "Could not retrieve guidance for text content."
    else:
        print("DEBUG: Image-only story. No text-based guidance fetch.")
        guidance_line = "No text provided for specific guidance retrieval."

    system_prompt = (
        "You are an observant and thoughtful friend crafting Instagram story replies. "
        "Your primary goal is to initiate genuine, warm, and curious interactions based **directly and literally** on the story's visible content. "
        "Emphasize authenticity and a natural, human touch. Avoid overly enthusiastic, generic, or speculative responses. "
        "Use emojis very sparingly (max 1, if any) and only if they truly enhance the message's warmth or curiosity naturally. "
        "Focus on sounding like a real friend who is genuinely interested in what they are actually seeing."
    )

    user_prompt_header = "A friend posted an Instagram story."
    story_content_line = f"Story Content: {text if text.strip() else 'This story is an IMAGE. Your first step is to carefully describe the main visual elements of this image to yourself. What objects, setting, or activity is clearly depicted? Base your reply *only* on these concrete visual observations.'}"
    
    guidance_line_to_include = guidance_line # Use the fetched guidance_line

    user_prompt = f"""
    {user_prompt_header}
    
    {story_content_line}
    
    Guidance from past similar interactions:
    {guidance_line_to_include}
    
    Your Task:
    Write a short, warm, and curious reply based strictly on the visible story (or text, if present). The reply should feel human and authentic.
    
    Instructions:
    - **If image only:** Mention or ask about something clearly visible. Don't speculate beyond what's shown. If unclear, use a general but positive line (e.g., "Looks like a great moment!").
    - **If text is present:** Respond thoughtfully to the text. Use guidance from similar past replies if helpful.
    - **Keep it grounded:** Curiosity should arise from what you actually see or read. (E.g., for a food photo: That looks delicious! Is that avocado toast?)
    - **Be authentic and simple:** Avoid being clever, eccentric, or bubbly. Use real, friendly language.
    - **Use at most one emoji, only if it truly fits.**
    - **Don't include Quatation marks in your draft.
    - **Where possible based on your understanding of the uploaded story, include a question at the end to promote a conversation.
    - **Be concise and conversational.**
    
    **Do not use any preamble. Write the message directly.**
    
    **Good reply (for breakfast photo):** "That breakfast looks amazing! Enjoy!"  
    **Bad reply:** "Cool project! What are you building?"
"""

    messages_for_api = [
        {"role": "system", "content": system_prompt}
    ]

    # Construct the user message part for the API
    user_content_list = [{"type": "text", "text": user_prompt.strip()}]
    if image_url:
        user_content_list.append({"type": "image_url", "image_url": {"url": image_url}})
    
    messages_for_api.append({"role": "user", "content": user_content_list if image_url else user_prompt.strip()})


    try:
        response = client.chat.completions.create(
            model="gpt-4o", # GPT-4o is multimodal and can handle both text and image in content list
            messages=messages_for_api,
            max_tokens=150 # Adjust as needed, 150 should be plenty for short DMs
        )
        generated_reply = response.choices[0].message.content
        status_info = "text_based" if text.strip() else "image_based"
        return generated_reply.strip(), status_info

    except Exception as e:
        error_message = f"Error in generate_conversation_starter OpenAI call: {e}"
        print(error_message)
        # Log the full exception for detailed debugging if needed
        # import traceback
        # print(traceback.format_exc())
        return f"Sorry, an error occurred while generating a reply. Please check logs. ({type(e).__name__})", "error"


# Notion client initialization for saving overrides
try:
    notion_api_key_env = os.getenv("NOTION_API_KEY")
    if not notion_api_key_env:
        print("Warning: NOTION_API_KEY environment variable not set. Notion integration will be disabled.")
        notion = None
        NOTION_DATABASE_ID = None
    else:
        notion = Client(auth=notion_api_key_env)
        db_id_raw = os.getenv("NOTION_TONE_DB_ID", "") # This DB might now store general interactions
        NOTION_DATABASE_ID = db_id_raw.replace("-", "") if db_id_raw else None
        if not NOTION_DATABASE_ID:
            print("Warning: NOTION_TONE_DB_ID (or equivalent for saving) is not set. Saving overrides will fail.")
except Exception as e:
    print(f"Error initializing Notion client for Tab 2: {e}")
    notion = None
    NOTION_DATABASE_ID = None

def save_human_override(story_text, image_url_provided, ai_message, human_message, analysis_type="unknown"):
    if not notion or not NOTION_DATABASE_ID:
        st.error("Notion client not configured correctly. Cannot save override.")
        print("Error: Notion client or DB ID not available for save_human_override.")
        return
    image_url_for_notion = "N/A" # Default
    if image_url_provided and image_url_provided.startswith("data:image"):
        # It's a base64 string
        image_url_for_notion = "Image data provided (Base64)" # Placeholder indicating data was present
        # If you want to store a tiny part of it for identification (still risky for length)
        # image_url_for_notion = image_url_provided[:100] + "..." # Example: truncate
    elif image_url_provided: # It might be an actual URL or other placeholder
        image_url_for_notion = str(image_url_provided)[:2000] # Truncate any other string

    try:
        properties_payload = {
            "Story Text": {"rich_text": [{"text": {"content": str(story_text)[:1000] or "N/A"}}]},
            "Image URL": {"rich_text": [{"text": {"content": image_url_for_notion}}]},
            "AI Message": {"rich_text": [{"text": {"content": str(ai_message) or "N/A"}}]},
            "Your message": {"rich_text": [{"text": {"content": str(human_message) or "N/A"}}]},
            "Tone": {"rich_text": [{"text": {"content": str(analysis_type)}}]} # Storing analysis_type in 'Tone' column
        }
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties_payload
        )
        st.success("✅ Your version saved to Notion!")
        print("✅ Override saved to Notion.")
    except Exception as e:
        st.error(f"Notion save failed: {e}")
        print(f"❌ Notion save failed: {e}")
        # import traceback
        # print(traceback.format_exc())


# ------------- TAB 2: STORY INTERRUPTION GENERATOR --------------

with tab2:
    st.markdown('<div style="text-align:center;"><h4>📸 Story Interruption Generator</h4></div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;"><span style="font-size:15px; color:#ccc;">Upload an Instagram story. The Huddle bot will suggest 3 warm, curious, and authentic replies based on the content.</span></div>', unsafe_allow_html=True)

    if "uploader_key_tab2" not in st.session_state:
        st.session_state.uploader_key_tab2 = 0

    uploaded_file = st.file_uploader(
        "",
        type=["jpg", "jpeg", "png"],
        key=f"story_image_tab2_{st.session_state.uploader_key_tab2}"
    )

    if uploaded_file:
        image_bytes = uploaded_file.read()
        image = Image.open(io.BytesIO(image_bytes))
        st.image(image, caption="Uploaded Story", use_container_width=True)

        text = extract_text_from_image(image_bytes)
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{base64_image}"
        

        st.markdown('<div id="storyTextAnchor"></div>', unsafe_allow_html=True)

        if "last_uploaded_story_name" not in st.session_state or st.session_state.last_uploaded_story_name != uploaded_file.name:
            st.session_state.scroll_to_story_text = True
            st.session_state.last_uploaded_story_name = uploaded_file.name

        if st.session_state.get("scroll_to_story_text", False):
            components.html("""
                <script>
                setTimeout(function() {
                    const el = window.parent.document.getElementById("storyTextAnchor");
                    if (el) {
                        el.scrollIntoView({ behavior: "smooth", block: "start" });
                    }
                }, 400);
                </script>
            """, height=0)
            st.session_state.scroll_to_story_text = False

        # ------------ MULTIPLE REPLIES LOGIC ------------

        def generate_multiple_conversation_starters(text, image_url=None, n=3):
            """
            Generates n high-quality conversation starters using your prompt,
            each tightly grounded in literal image/text content, no tone tags.
            """
            guidance_line = ""
            if text.strip():
                try:
                    from tone_fetcher import retrieve_similar_tone_example
                    human_example, _ = retrieve_similar_tone_example(text, "")
                    if human_example:
                        guidance_line = f"Previously, a human reply to similar text was: {human_example}"
                    else:
                        guidance_line = "No similar past reply available."
                except Exception:
                    guidance_line = "No guidance available."
            else:
                guidance_line = "No text provided for specific guidance retrieval."
            
            system_prompt = (
                "You are an observant and thoughtful friend crafting Instagram story replies. "
                "Your goal is to start genuine, warm, and curious conversations based strictly on the visible content. "
                "Always reference what's actually there—no guessing or speculation. "
                "Keep replies authentic, friendly, and simple. Use at most one emoji, only if it fits naturally."
            )
        
            user_prompt_header = "A friend posted an Instagram story."
            story_content_line = (
                f"Story Content: {text.strip() if text.strip() else 'This is an IMAGE. Before replying, list to yourself the main objects, scene, or food you *see*. Your reply must mention or ask about one of these visible elements.'}"
            )
            guidance_line_to_include = guidance_line
        
            user_prompt = f"""
        {user_prompt_header}
        
        {story_content_line}
        
        Guidance from past similar interactions:
        {guidance_line_to_include}
        
        Your Task:
        Write a short, warm, and curious reply based strictly on the visible story (or text, if present). The reply should feel human and authentic.
        
        Instructions:
        - If image only: Mention or ask about something clearly visible. Don't speculate beyond what's shown. If unclear, use a general but positive line.
        - If text: Respond thoughtfully to the text. Use past guidance if helpful.
        - Where possible, include a question at the end to prompt conversation.
        - Be authentic and simple. Avoid being overly clever, eccentric, or bubbly.
        - Use at most one emoji, only if it fits.
        - Do **not** use quotation marks in your draft.
        - Do **not** use any preamble—just write the message directly.
        - If the image contains overlays, music tags, or device UI, **ignore** them and focus only on the central, main scene or food.
        
        
        
        Examples:
        Good: "That breakfast looks amazing! Enjoy!"  
        Bad: "Cool project! What are you building?"
        """
        
            # Build API message list
            messages_for_api = [{"role": "system", "content": system_prompt}]
            user_content_list = [{"type": "text", "text": user_prompt.strip()}]
            if image_url:
                user_content_list.append({"type": "image_url", "image_url": {"url": image_url}})
            messages_for_api.append({
                "role": "user",
                "content": user_content_list if image_url else user_prompt.strip()
            })
        
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages_for_api,
                max_tokens=150,
                n=n,
                temperature=1.0
            )
            # Return all completions as a list
            completions = [choice.message.content.strip() for choice in response.choices]
            return completions
        

        # Store completions in session state to avoid rerun issues
        if "conversation_starters" not in st.session_state:
            with st.spinner("🤖 Generating 3 options..."):
                st.session_state.conversation_starters = generate_multiple_conversation_starters(text, image_url, n=3)
        
        for idx, reply in enumerate(st.session_state.conversation_starters):
            render_polished_card(f"Conversation Starter #{idx+1}", reply, auto_copy=True)
        
        # Editable field to choose and edit any suggestion
        st.markdown("#### ✏️ Your Adjusted Message")
        # Prefill with the first suggestion by default, or whatever last used
        if "user_edit" not in st.session_state:
            st.session_state.user_edit = st.session_state.conversation_starters[0]
        st.session_state.user_edit = st.text_area(
            "",
            value=st.session_state.user_edit,
            height=120
        )
        
        # Save edited message
        col1_gen, col2_regen = st.columns(2)
        with col1_gen:
            if st.button("✅ Save My Version", use_container_width=True):
                image_url_safe = image_url if image_url else "N/A"
                save_human_override(
                    text,
                    image_url_safe,
                    "N/A",  # No tone/tag
                    "\n".join(st.session_state.conversation_starters),
                    st.session_state.user_edit
                )
                st.success("✅ Saved to Notion! Your edits will influence future responses.")
        
        with col2_regen:
            if st.button("🔄 Regenerate All", use_container_width=True):
                replies = generate_multiple_conversation_starters(text, image_url)
                st.session_state.conversation_starters = replies
                # Reset user edit to first new reply
                st.session_state.user_edit = replies[0]
                st.rerun()
        
        if st.button("➕ Start New Interruption", key="new_story_button", use_container_width=True):
            # Reset relevant state
            for key in ["conversation_starters", "last_uploaded_story_name", "scroll_to_story_text", "user_edit"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.uploader_key_tab2 += 1
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)


# =============== TAB 3: PAST HUDDLES ===============
with tab3:
    st.subheader("📖 Past Huddle Interactions")
    try:
        huddles_data = load_all_interactions() # From memory.py (likely Notion)
        if not isinstance(huddles_data, list):
            st.error("Error: Could not load huddles correctly. Expected a list from `load_all_interactions`.")
            huddles_data = []
    except Exception as e:
        st.error(f"Failed to load huddles from Notion: {e}")
        huddles_data = []

    if not huddles_data:
        st.info("No huddles saved yet or unable to load them.")
    else:
        try:
            # Ensure huddles are dicts and have a timestamp for sorting
            valid_huddles = [h for h in huddles_data if isinstance(h, dict) and "timestamp" in h]
            sorted_huddles_list = sorted(valid_huddles, key=lambda h: h.get("timestamp", ""), reverse=True)
        except Exception as e:
            st.error(f"Error sorting huddles: {e}. Displaying unsorted.")
            sorted_huddles_list = [h for h in huddles_data if isinstance(h, dict)]


        for idx, huddle_item in enumerate(sorted_huddles_list):
            # Use a more unique title for expander if timestamp is not always unique or present
            # Default to index if timestamp is missing from a specific huddle dict
            timestamp_str = huddle_item.get('timestamp', f"Unknown Timestamp - Item {len(sorted_huddles_list) - idx}")
            expander_title = f"Huddle {len(sorted_huddles_list) - idx}: {timestamp_str}"
            
            with st.expander(expander_title):
                st.markdown("**🖼 Screenshot Text**")
                st.write(huddle_item.get('screenshot_text', '_Not available_'))
                st.markdown("**📝 User Draft**")
                st.write(huddle_item.get('user_draft', '_Not available_'))
                st.markdown("**🤖 AI Suggested Reply (Original)**")
                st.write(huddle_item.get('ai_suggested', '_Not available_'))
                
                # Check for the adjusted reply field used in save_huddle_to_notion
                # The key was 'user_final' in your original code, let's clarify.
                # Assuming 'ai_adjusted_reply' is what save_huddle_to_notion(..., ..., ..., adjusted_reply) saves.
                if huddle_item.get('ai_adjusted_reply'): # This key should match what save_huddle_to_notion saves
                    st.markdown("**🗣️ Tone Adjusted Reply**")
                    st.write(huddle_item.get('ai_adjusted_reply'))
                elif huddle_item.get('user_final'): # Fallback or alternative field
                    st.markdown("**🧠 User's Final Version (if different from AI)**")
                    st.write(huddle_item.get('user_final'))