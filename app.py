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
from html import escape

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

# ---- Polished Card Renderer ----
def render_polished_card(label, text_content, auto_copy=True):
    def format_text_html(text):
        cleaned = str(text).strip()
        normalized = re.sub(r"\n{2,}", "\n\n", cleaned)
        html_ready = normalized.replace('\n', '<br>')
        return re.sub(r"^(<br\s*/?>\s*)+", "", html_ready, flags=re.IGNORECASE)

    safe_html_text = format_text_html(text_content)
    
    copy_button_html = f"""
        <button onclick="navigator.clipboard.writeText(`{escape(text_content)}`)"
                style="float: right; background: #444; color: white; border: none; padding: 6px 10px; border-radius: 6px; cursor: pointer;">
            📋 Copy
        </button>
    """ if auto_copy else ""

    st.markdown(f"""
    <style>
    .fade-in {{
        animation: fadeIn 1s ease-out forwards;
        opacity: 0;
    }}
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(8px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    </style>

    <div class="fade-in" style="border-radius: 16px; padding: 20px; background-color: #1e1e1e; color: white; font-size: 16px; line-height: 1.6; box-shadow: 0 0 8px rgba(255,255,255,0.05);">
        <h4 style="margin-bottom: 12px;">✉️ {label} {copy_button_html}</h4>
        <div>{safe_html_text}</div>
    </div>
    """, unsafe_allow_html=True)

    unique_id = uuid.uuid4().hex[:8]
    # Escape text for safe embedding in JavaScript strings for the copy functionality
    js_escaped_text = str(text_content).replace("\\", "\\\\").replace("`", "\\`").replace('"', '\\"').replace("\n", "\\n")
    
    html_formatted_text_for_display = format_text_html(text_content) # Use the refined formatter
    
    fixed_height = 400 # Desired fixed height for the text display area
    
    auto_copy_script = ""
    if auto_copy:
        auto_copy_script = f"""
        <script>
            (function() {{ // IIFE to avoid polluting global scope
                const textToCopy = `{js_escaped_text}`;
                navigator.clipboard.writeText(textToCopy).then(() => {{
                    const alertBox = document.getElementById('copyAlert-{unique_id}');
                    if (alertBox) {{
                        alertBox.style.display = 'inline-block';
                        setTimeout(() => {{ alertBox.style.display = 'none'; }}, 1500);
                    }}
                }}).catch(err => console.error('Auto-copy failed: ', err));
            }})();
        </script>
        """

    copy_button_onclick_js = f"""
        const textToCopy = `{js_escaped_text}`;
        navigator.clipboard.writeText(textToCopy).then(() => {{
            const alertBox = document.getElementById('copyAlert-{unique_id}');
            if (alertBox) {{
                alertBox.style.display = 'inline-block';
                setTimeout(() => {{ alertBox.style.display = 'none'; }}, 1500);
            }}
        }}).catch(err => console.error('Manual copy failed: ', err));
    """

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
                    principles_to_use = '''1. Be clear and confident. 2. Ask questions, don’t convince. 3. Use connection > persuasion. 4. Keep it short, warm, and human. 5. Stick to the Huddle flow and tone.'''
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
from html import escape
import csv
from retriever import retrieve_similar_human_edit

# CSV file location

def render_polished_card(label, text, auto_copy=False):
    safe_text = escape(text).replace("\n", "<br>")
    copy_button_html = f"""
        <button onclick="navigator.clipboard.writeText(`{escape(text)}`)"
                style="float: right; background: #444; color: white; border: none; padding: 6px 10px; border-radius: 6px; cursor: pointer;">
            📋 Copy
        </button>
    """ if auto_copy else ""

    st.markdown(f"""
    <style>
    .fade-in {{
        animation: fadeIn 1s ease-out forwards;
        opacity: 0;
    }}
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(8px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    </style>

    <div class="fade-in" style="border-radius: 16px; padding: 20px; background-color: #1e1e1e; color: white; font-size: 16px; line-height: 1.6; box-shadow: 0 0 8px rgba(255,255,255,0.05);">
        <h4 style="margin-bottom: 12px;">✉️ {label} {copy_button_html}</h4>
        <div>{safe_text}</div>
    </div>
    """, unsafe_allow_html=True)

def classify_story_tone(text, image_url=None):
    system_prompt = """You're an assistant that classifies the emotional or stylistic tone of an Instagram story.
Given the content (text and/or image), return a single keyword tag that best describes the overall vibe. Choose from:
- humor
- gym
- quote
- aesthetic
- food
- travel
- deep
- casual
- celebration
- pet
- random

Respond ONLY with the tag.
"""

    if text.strip():
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        )
    elif image_url:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's the tone of this story?"},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
        )
    else:
        return "random"

    return response.choices[0].message.content.strip().lower()

def generate_conversation_starter(text, image_url=None):
    tag = classify_story_tone(text, image_url)

    # Try to find similar human-written message
    from tone_fetcher import retrieve_similar_tone_example
    human_example, matched_tone = retrieve_similar_tone_example(text, tag)
    

    guidance_line = f"Here’s how this person typically responds to {tag}-toned stories: “{human_example}”" if human_example else ""
    
    prompt = f"""
Someone posted a story with a '{tag}' tone.
{text if text.strip() else "Here is the image."}

{guidance_line}

Write a short, friendly, human message in response that matches the tone and feels natural, like something a friend would DM.
"""

    messages = [
        {"role": "system", "content": "You're a friendly assistant writing warm, human Instagram story replies."},
        {"role": "user", "content": prompt.strip()}
    ]

    if text.strip():
        response = client.chat.completions.create(model="gpt-4o", messages=messages)
    else:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                messages[0],
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
        )

    return response.choices[0].message.content, tag

from notion_client import Client
notion = Client(auth=os.getenv("NOTION_API_KEY"))
db_id_raw = os.getenv("NOTION_TONE_DB_ID", "")
NOTION_DATABASE_ID = db_id_raw.replace("-", "") if db_id_raw else None

def save_human_override(text, image_url, tone, ai_message, human_message):    
    try:
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Story Text": {
                    "rich_text": [{"text": {"content": text[:100] or "Untitled"}}]
                },
                "Image URL": {
                    "rich_text": [{"text": {"content": image_url or "N/A"}}]
                },
                "Tone": {
                    "rich_text": [{"text": {"content": tone or "unspecified"}}]
                },
                "AI Message": {
                    "rich_text": [{"text": {"content": ai_message or "none"}}]
                },
                "Your message": {  # Must match column name in Notion exactly
                    "rich_text": [{"text": {"content": human_message or "none"}}]
                }
            }
        )
        print("✅ Saved to Notion")
    except Exception as e:
        print("❌ Notion save failed:", e)
# ------------------ TAB 2 ------------------ #
with tab2:
    st.markdown("<h4>📸 Story Interruption Generator</h4>", unsafe_allow_html=True)
    if "uploader_key_tab2" not in st.session_state:
        st.session_state.uploader_key_tab2 = 0

    # Use a controlled flag just like in tab1
    if "scroll_to_interruption" not in st.session_state:
        st.session_state.scroll_to_interruption = False

    uploaded_file = st.file_uploader(
        "Upload an Instagram Story Screenshot",
        type=["jpg", "jpeg", "png"],
        key=f"story_image_tab2_{st.session_state.uploader_key_tab2}"
    )
    

    if uploaded_file:
        image_bytes = uploaded_file.read()
        image = Image.open(io.BytesIO(image_bytes))
        st.image(image, caption="Uploaded Story", use_container_width=True)
    
        text = extract_text_from_image(image_bytes)
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{base64_image}" if not text.strip() else None
    
        # ✅ Place the anchor *before* triggering scroll
        st.markdown('<div id="storyTextAnchor"></div>', unsafe_allow_html=True)
    
        # Set flag if new upload
        if "last_uploaded_story_name" not in st.session_state or \
           st.session_state.last_uploaded_story_name != uploaded_file.name:
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
    
        # Proceed with the rest
        if text.strip():
            st.subheader("📝 Detected Story Text")
            st.write(text)
        else:
            st.subheader("🖼 No text detected — analyzing image")
    
        if "conversation_starter" not in st.session_state or "conversation_tone" not in st.session_state:
            with st.spinner("🤖Generating message.."):
                reply, tone_tag = generate_conversation_starter(text, image_url)
                st.session_state.conversation_starter = reply
                st.session_state.conversation_tone = tone_tag
    
        st.markdown(f"🧠 **Detected Tone Tag:** `{st.session_state.conversation_tone}`")
        render_polished_card("Conversation Starter", st.session_state.conversation_starter)
    

        # Editable field
        user_edit = st.text_area("✏️ Your Adjusted Message", value=st.session_state.conversation_starter, height=120)

        # Save edited message
        col1_gen, col2_regen = st.columns(2)
        with col1_gen:
            if st.button("✅ Save My Version", use_container_width=True):
                # Handle image_url fallback gracefully
                image_url_safe = image_url if image_url else "N/A"
            
                save_human_override(
                    text,
                    image_url_safe,
                    st.session_state.conversation_tone,
                    st.session_state.conversation_starter,
                    user_edit
                )
                st.success("✅ Saved to Notion! Your tone will influence future responses.")
        # Regenerate message
        with col2_regen:
            if st.button("🔄 Regenerate Message",use_container_width=True):
                reply, tone_tag = generate_conversation_starter(text, image_url)
                st.session_state.conversation_starter = reply
                st.session_state.conversation_tone = tone_tag
                st.rerun()
    if st.button("➕ Start New Interruption", key="new_story_button",use_container_width=True):
        # Reset relevant state
        for key in ["conversation_starter", "conversation_tone", "last_uploaded_story_name", "scroll_to_story_text"]:
            if key in st.session_state:
                del st.session_state[key]
    
        st.session_state.uploader_key_tab2 += 1
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)  # End tab2-wrapper


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