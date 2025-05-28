import streamlit as st
import os
import tempfile
import time
import re
import uuid
from PIL import Image
from dotenv import load_dotenv
import streamlit.components.v1 as components

# === Internal imports ===
from memory import save_huddle_to_notion, load_all_interactions
from memory_vector import embed_and_store_interaction, retrieve_similar_examples # For displaying similar examples
# Updated imports from suggestor.py
from suggestor import (
    get_context_for_reply,
    stream_suggested_reply,
    stream_adjusted_tone,
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

# ---- Polished Card Renderer ----
def render_polished_card(label, text_content, auto_copy=False):
    # Internal helper to format text for HTML display
    def format_text_html(text_to_format):
        # 1. Remove ALL leading and trailing whitespace (including any newlines)
        #    from the input text. This is the most critical step for the leading space issue.
        cleaned_text = str(text_to_format).strip() # Ensure it's a string and strip it
        
        # 2. Normalize multiple internal newlines to a maximum of two consecutive newlines.
        #    This means there will be at most one blank line between paragraphs of text.
        #    (e.g., "Line1\n\n\nLine2" becomes "Line1\n\nLine2")
        internal_newlines_normalized_text = re.sub(r"\n{2,}", "\n\n", cleaned_text)
        
        # 3. Convert the remaining newline characters (\n) to HTML line break tags (<br>).
        html_ready_text = internal_newlines_normalized_text.replace('\n', '<br>')
        
        # 4. As a final safety net, remove any <br> tags that might still be at the very beginning
        #    of the HTML string. This should be redundant if step 1 worked correctly.
        html_ready_text = re.sub(r"^(<br\s*/?>\s*)+", "", html_ready_text, flags=re.IGNORECASE)
        
        return html_ready_text

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

    full_html = f"""
    <div style="
        max-width: 100vw; background-color: #1e1e1e; border: 1px solid #333;
        border-radius: 12px; box-shadow: 0 20px 6px rgba(0,0,0,0.1); padding: 16px; margin: 0;
        font-family: 'Segoe UI', sans-serif; font-size: 16px; color: #f0f0f0;">
        <h4 style="margin: 0 0 12px 0;">{label}</h4>
        <div id="textDisplay-{unique_id}" style="
            background: #2a2a2a; border-radius: 8px; padding: 12px;
            white-space: normal; word-wrap: break-word;
            line-height: 1.6; border: 1px solid #444;
            overflow-y: auto; height: {fixed_height}px;">
            {html_formatted_text_for_display}
        </div>
        <button onclick="{copy_button_onclick_js}" style="
            margin-top: 12px; padding: 6px 12px; background-color: #22c55e;
            color: white; border: none; border-radius: 6px; font-weight: 500; cursor: pointer;">
            📋 Copy to Clipboard
        </button>
        <span id="copyAlert-{unique_id}" style="display: none; margin-left: 10px; color: #22c55e; font-weight: 500;">
            ✅ Copied!
        </span>
        {auto_copy_script}
    </div>
    """
    components.html(full_html, height=fixed_height + 95, scrolling=True)

# ---- Main Tabs ----
tab1, tab2, tab3 = st.tabs(["Huddle Play", "View Documents", "📚 View Past Huddles"])

# =============== TAB 1: HUDDLE PLAY ===============
with tab1:
    with st.container():
        st.markdown("<div id='tab1-wrapper'>", unsafe_allow_html=True)
        
        # Session state for outputs and scroll triggers
        # Renamed to avoid confusion with streaming placeholders
        session_keys = {
            "final_reply_collected": None,  # Stores the full, cleaned AI reply
            "adjusted_reply_collected": None, # Stores the full, cleaned adjusted AI reply
            "doc_matches_for_display": [],  # Stores document matches from get_context_for_reply
            "screenshot_text_content": None, # Stores OCR extracted text
            "user_draft_current": "",       # Stores the content of the text_area
            "similar_examples_retrieved": None # Stores similar examples from memory_vector
        }
        for key, default_value in session_keys.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
        
        if "scroll_to_draft" not in st.session_state:
            st.session_state.scroll_to_draft = False
        if "last_uploaded_filename" not in st.session_state:
            st.session_state.last_uploaded_filename = None
        if "current_tone_selection": # Stores selected tone
            st.session_state.current_tone_selection = "None"

        # ---- Upload UI ----
        uploaded_image = st.file_uploader(
            "Upload image", type=["jpg", "jpeg", "png"],
            label_visibility="collapsed", key=f"upload_img_{st.session_state.uploader_key}"
        )
        if uploaded_image:
            try:
                image = Image.open(uploaded_image)
                st.image(image, use_container_width=True)
            except Exception as e:
                st.error(f"Error displaying image: {e}")

            current_filename = uploaded_image.name
            if st.session_state.last_uploaded_filename != current_filename:
                st.session_state.scroll_to_draft = True
                st.session_state.last_uploaded_filename = current_filename
                # Clear previous outputs when new image is uploaded
                for key_to_clear in session_keys.keys():
                    st.session_state[key_to_clear] = session_keys[key_to_clear] # Reset to default


        if st.session_state.scroll_to_draft:
            components.html("""  # Corrected: removed the extra .v1
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
        # Use st.session_state.user_draft_current to preserve text area content
        st.session_state.user_draft_current = st.text_area(
            "Your Draft Message", 
            value=st.session_state.user_draft_current,
            label_visibility="collapsed", height=110, key="user_draft_widget"
        )
        
        # ---- Generate AI Reply ----
        if st.button("🚀 Generate AI Reply", key="generate_reply_button"):
            if uploaded_image and st.session_state.user_draft_current:
                st.session_state.adjusted_reply_collected = None # Clear previous adjusted reply
                st.session_state.final_reply_collected = None    # Clear previous final reply

                processing_start_time = time.time()
                tmp_path = None # Initialize to avoid NameError in finally
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                        tmp_file.write(uploaded_image.getvalue())
                        tmp_path = tmp_file.name
                
                    # ⏳ Show spinner while extracting text (OCR)
                    ocr_start_time = time.time()
                    with st.spinner("🔍 Extracting text from screenshot..."):
                        st.session_state.screenshot_text_content = extract_text_from_image(tmp_path)
                    ocr_duration = time.time() - ocr_start_time
                    print(f"OCR time: {ocr_duration:.2f}s")

                    if not st.session_state.screenshot_text_content or not st.session_state.screenshot_text_content.strip():
                        st.warning("⚠️ Screenshot text couldn't be read clearly. Please try a clearer image.")
                    else:
                        # Retrieve similar examples (from memory_vector) for display
                        examples_retrieval_start_time = time.time()
                        with st.spinner("🧠 Retrieving similar past huddles for context..."):
                            st.session_state.similar_examples_retrieved = retrieve_similar_examples(
                                st.session_state.screenshot_text_content, 
                                st.session_state.user_draft_current
                            )
                        print(f"Similar examples (memory_vector) retrieval: {(time.time() - examples_retrieval_start_time):.2f}s")

                        # Get context strings for the LLM prompt (from suggestor.get_context_for_reply)
                        context_retrieval_start_time = time.time()
                        with st.spinner("📚 Retrieving document context for AI..."):
                            huddle_context_str, doc_context_str, doc_matches = get_context_for_reply(
                                st.session_state.screenshot_text_content,
                                st.session_state.user_draft_current
                            )
                        st.session_state.doc_matches_for_display = doc_matches # For UI display
                        print(f"Document context (suggestor) retrieval: {(time.time() - context_retrieval_start_time):.2f}s")

                        principles = '''1. Be clear and confident. 2. Ask questions, don’t convince. 3. Use connection > persuasion. 4. Keep it short, warm, and human. 5. Stick to the Huddle flow and tone.'''
                        
                        st.subheader("⏳ Generating Suggested Reply...")
                        reply_placeholder = st.empty() # Create a placeholder for the streamed response
                        
                        ai_stream_start_time = time.time()
                        # Stream the AI reply
                        reply_stream_generator = stream_suggested_reply(
                            screenshot_text=st.session_state.screenshot_text_content,
                            user_draft=st.session_state.user_draft_current,
                            principles=principles,
                            model_name=st.session_state.model_choice_radio, # From sidebar
                            huddle_context_str=huddle_context_str,
                            doc_context_str=doc_context_str
                        )
                        
                        # Use st.write_stream to display and collect the full response
                        raw_ai_reply = reply_placeholder.write_stream(reply_stream_generator)
                        st.session_state.final_reply_collected = clean_reply(raw_ai_reply)
                        print(f"AI reply stream and clean time: {(time.time() - ai_stream_start_time):.2f}s")
                        
                        # Now that the stream is complete and placeholder is filled, clear it if we use render_polished_card
                        reply_placeholder.empty()

                        # ---- Save or Fail Reason ----
                        failure_reasons = []
                        if len(st.session_state.user_draft_current.strip().split()) < st.session_state.min_words_slider:
                            failure_reasons.append(f"- Your draft only has {len(st.session_state.user_draft_current.strip().split())} words (min required: {st.session_state.min_words_slider})")
                        if len(st.session_state.screenshot_text_content.strip()) < st.session_state.min_chars_slider:
                            failure_reasons.append(f"- Screenshot text has only {len(st.session_state.screenshot_text_content.strip())} characters (min required: {st.session_state.min_chars_slider})")
                        if st.session_state.require_question_checkbox and "?" not in st.session_state.user_draft_current:
                            failure_reasons.append("- Draft doesn't include a question")
                        
                        is_quality = len(failure_reasons) == 0
                        if is_quality:
                            with st.spinner("💾 Saving huddle..."):
                                embed_and_store_interaction( # From memory_vector
                                    screenshot_text=st.session_state.screenshot_text_content,
                                    user_draft=st.session_state.user_draft_current,
                                    ai_suggested=st.session_state.final_reply_collected
                                )
                                save_huddle_to_notion( # From memory
                                    st.session_state.screenshot_text_content,
                                    st.session_state.user_draft_current,
                                    st.session_state.final_reply_collected,
                                    st.session_state.get("adjusted_reply_collected", "") # Pass adjusted if available, else empty
                                )
                            st.success("💾 Huddle saved successfully.")
                        else:
                            st.warning("⚠️ This huddle wasn't saved due to the following reason(s):")
                            for reason in failure_reasons:
                                st.markdown(f"• {reason}")
                        print(f"Total processing time for generate: {(time.time() - processing_start_time):.2f}s")
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path) # Clean up temp file
            elif not uploaded_image:
                st.warning("Please upload an image.")
            elif not st.session_state.user_draft_current:
                st.warning("Please enter your draft message.")

        # ---- Display Final Reply and Tone Controls ----
        if st.session_state.final_reply_collected:
            st.subheader("✅ Suggested Reply")
            render_polished_card("Suggested Reply", st.session_state.final_reply_collected, auto_copy=True)
            
            st.session_state.current_tone_selection = st.selectbox(
                "🎨 Adjust Tone", 
                ["None", "Professional", "Casual", "Inspiring", "Empathetic", "Direct"], 
                index=0, # Default to "None"
                key="tone_selectbox_key"
            )
            
            if st.session_state.current_tone_selection != "None" and st.button("🎯 Regenerate with Tone", key="regenerate_tone_button"):
                st.session_state.adjusted_reply_collected = None # Clear previous
                
                with st.spinner("🎨 Adjusting tone..."):
                    st.subheader("⏳ Generating Tone-Adjusted Reply...")
                    adjusted_reply_placeholder = st.empty()

                    tone_stream_start_time = time.time()
                    adjusted_reply_stream_generator = stream_adjusted_tone(
                        st.session_state.final_reply_collected, 
                        st.session_state.current_tone_selection,
                        st.session_state.model_choice_radio # Pass selected model
                    )
                    
                    raw_adjusted_reply = adjusted_reply_placeholder.write_stream(adjusted_reply_stream_generator)
                    st.session_state.adjusted_reply_collected = clean_reply(raw_adjusted_reply)
                    print(f"Tone adjustment stream and clean time: {(time.time() - tone_stream_start_time):.2f}s")
                    adjusted_reply_placeholder.empty() # Clear placeholder after collecting

                # Quality check and save for adjusted reply
                if st.session_state.adjusted_reply_collected: # Ensure it was generated
                    # Re-check quality criteria (based on original draft and screenshot)
                    failure_reasons = []
                    if len(st.session_state.user_draft_current.strip().split()) < st.session_state.min_words_slider:
                        failure_reasons.append(f"- Your draft only has {len(st.session_state.user_draft_current.strip().split())} words (min required: {st.session_state.min_words_slider})")
                    if st.session_state.screenshot_text_content and len(st.session_state.screenshot_text_content.strip()) < st.session_state.min_chars_slider:
                        failure_reasons.append(f"- Screenshot text has only {len(st.session_state.screenshot_text_content.strip())} characters (min required: {st.session_state.min_chars_slider})")
                    elif not st.session_state.screenshot_text_content:
                         failure_reasons.append(f"- Screenshot text was not available for quality check.")
                    if st.session_state.require_question_checkbox and "?" not in st.session_state.user_draft_current:
                        failure_reasons.append("- Draft doesn't include a question")
                    
                    is_quality_adjusted = len(failure_reasons) == 0
                    if is_quality_adjusted:
                        with st.spinner("💾 Saving adjusted huddle..."):
                            # Update interaction with the adjusted reply
                            # Qdrant: We typically store the latest *best* version.
                            # If you want to store both original and adjusted, memory_vector.py needs modification.
                            # For now, let's assume we update/overwrite with the adjusted one.
                            embed_and_store_interaction(
                                screenshot_text=st.session_state.screenshot_text_content,
                                user_draft=st.session_state.user_draft_current,
                                ai_suggested=st.session_state.adjusted_reply_collected # Save the adjusted one
                            )
                            # Notion: Save both original and adjusted
                            save_huddle_to_notion(
                                st.session_state.screenshot_text_content,
                                st.session_state.user_draft_current,
                                st.session_state.final_reply_collected, # Original AI suggestion
                                st.session_state.adjusted_reply_collected # Tone-adjusted reply
                            )
                        st.success("💾 Tone-adjusted huddle saved.")
                    else:
                        st.warning("⚠️ This adjusted huddle wasn't saved due to the following reason(s):")
                        for reason_adj in failure_reasons:
                            st.markdown(f"• {reason_adj}")
        
        if st.session_state.adjusted_reply_collected:
            st.subheader(f"🎉 Regenerated Reply ({st.session_state.current_tone_selection})")
            render_polished_card("Adjusted Reply", st.session_state.adjusted_reply_collected, auto_copy=True)

        # ---- Show Used Docs and Examples ----
        st.markdown("<div id='suggestedAnchor'></div>", unsafe_allow_html=True)
        if st.session_state.doc_matches_for_display:
            st.subheader("📄 Relevant Communication Docs Used by AI")
            for match in st.session_state.doc_matches_for_display:
                if isinstance(match, dict): # Ensure match is a dictionary
                    with st.expander(f"🧠 From: {match.get('source', 'Unknown')}"):
                        st.markdown(f"> {match.get('document', '')}")
                else:
                    st.warning(f"Unexpected document match format: {match}")
        elif st.session_state.final_reply_collected: # Only show "no docs" if a reply was generated
             st.info("No specific external documents were heavily weighted by the AI for this reply.")


        # Display similar past huddles retrieved by memory_vector.retrieve_similar_examples
        if st.session_state.similar_examples_retrieved:
            st.subheader("🧠 Similar Past Huddle Plays (For Your Reference)")
            # Note: similar_examples_retrieved might be a tuple (huddles, docs) if it's the old one.
            # Assuming retrieve_similar_examples from memory_vector returns a list of huddle examples
            # This depends on the actual implementation of memory_vector.retrieve_similar_examples
            
            examples_to_show = st.session_state.similar_examples_retrieved
            # If it returns a tuple like (huddles, docs) as the old suggestor.retrieve_similar_examples did:
            if isinstance(st.session_state.similar_examples_retrieved, tuple) and len(st.session_state.similar_examples_retrieved) > 0:
                 examples_to_show = st.session_state.similar_examples_retrieved[0] # Assuming first element is huddles

            if not examples_to_show:
                 st.info("No highly similar past huddle plays found in memory.")
            
            for idx, example in enumerate(examples_to_show):
                if not isinstance(example, dict) or not any([
                    example.get("payload", {}).get("screenshot_text"), 
                    example.get("payload", {}).get("user_draft"), 
                    example.get("payload", {}).get("ai_reply")
                ]): # Qdrant search results often have data in 'payload'
                    # Try direct access if payload isn't the structure
                    if not isinstance(example, dict) or not any ([example.get("screenshot_text"), example.get("user_draft"), example.get("ai_reply")]):
                        continue # Skip if not a valid example structure

                payload = example.get("payload", example) # Use payload if exists, else example itself

                with st.expander(f"🔁 Past Huddle {idx + 1} (Score: {example.score:.2f})" if hasattr(example, 'score') else f"🔁 Past Huddle {idx + 1}"):
                    st.markdown("**🖼 Screenshot Text**")
                    st.markdown(payload.get("screenshot_text") or "_Not available_")
                    st.markdown("**✍️ User Draft**")
                    st.markdown(payload.get("user_draft") or "_Not available_")
                    st.markdown("**🤖 Final AI Reply**")
                    st.markdown(payload.get("ai_reply") or payload.get("ai_suggested") or "_Not available_") # Check for ai_suggested too
                    
                    current_boost = float(payload.get("boost", 1.0))
                    point_id_val = example.id if hasattr(example, 'id') else payload.get("point_id")

                    if point_id_val and st.button(f"🔼 Boost This Example ({current_boost:.1f}x) {idx + 1}", key=f"boost_{point_id_val}_{idx}"):
                        new_boost = current_boost + 0.5 # Smaller increment for boost
                        try:
                            q_client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
                            q_client.set_payload(
                                collection_name=HUDDLE_MEMORY_COLLECTION, # Ensure this is your huddle collection
                                points=[point_id_val],
                                payload={"boost": new_boost},
                                wait=True
                            )
                            st.success(f"✅ Boosted to {new_boost:.1f}x. Effect visible on next generation.")
                            # Update in session state for immediate UI reflection if desired (optional)
                            if isinstance(st.session_state.similar_examples_retrieved, tuple):
                                st.session_state.similar_examples_retrieved[0][idx].payload['boost'] = new_boost
                            else:
                                st.session_state.similar_examples_retrieved[idx].payload['boost'] = new_boost
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Failed to boost: {e}")
        elif st.session_state.final_reply_collected: # Only show if a reply was attempted
            st.info("No similar past huddle examples were retrieved for display.")


        if st.button("➕ Start New Huddle", key="new_huddle_button_tab1"):
            # Clear all relevant session state keys
            keys_to_clear_on_new = [
                "final_reply_collected", "adjusted_reply_collected", 
                "doc_matches_for_display", "screenshot_text_content", 
                "user_draft_current", "similar_examples_retrieved",
                "last_uploaded_filename", "current_tone_selection",
                "tone_selectbox_key" # Reset selectbox by clearing its state too
            ] 
            for k_clear in keys_to_clear_on_new:
                if k_clear in st.session_state:
                    # Reset to initial defaults if defined, otherwise delete
                    if k_clear in session_keys:
                         st.session_state[k_clear] = session_keys[k_clear]
                    else:
                         del st.session_state[k_clear]
            
            st.session_state.uploader_key += 1 # Resets file uploader
            st.session_state.user_draft_current = "" # Explicitly clear text area content
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)  # End tab1-wrapper

# =============== TAB 2: VIEW DOCUMENTS ===============
with tab2:
    st.markdown("### 📚 Key Documents")
    st.caption("Tap the tabs below to browse important Huddle tools.")
    doc_pdf_links_data = [
        ("OLB.pdf", "One Line Bridge"), ("MPA.pdf", "Make People Aware"),
        ("DTM.pdf", "Door to Mentorship"), ("FAQ.pdf", "FAQ")
    ]
    
    doc_tab_names = [data[1] for data in doc_pdf_links_data]
    doc_display_tabs = st.tabs(doc_tab_names)

    for i, tab_content_item in enumerate(doc_display_tabs):
        with tab_content_item:
            pdf_filename, pdf_title = doc_pdf_links_data[i]
            st.markdown(f"## {pdf_title}")
            
            # Create a direct link to the PDF if served statically
            # Ensure your Streamlit deployment serves the 'public' directory
            # The path for `st.markdown` link should be relative to the domain root if `public` is served at root
            # Or, if served under a specific path, adjust accordingly.
            # For Render, if 'public' is in your repo root, you might make it a static asset path.
            
            # Assuming 'public' is correctly served:
            public_url_path = f"{pdf_filename}" # Simplest if public is served at root
            # If your app is at `domain.com/app/` and public is `domain.com/public/`
            # then the link might need to be absolute or `../public/{pdf_filename}`.
            # For now, assume simplest case (./public/file.pdf works if streamlit serves it like that)

            # Check if file exists locally to give a better message if not found
            local_file_path = os.path.join(PDF_DIR, pdf_filename)
            if os.path.exists(local_file_path):
                st.markdown(f"[📄 Tap here to view the {pdf_title} PDF](./{PDF_DIR}/{pdf_filename})", unsafe_allow_html=True)
                # Note: Direct embedding of PDFs in Streamlit is tricky. Links are more reliable.
                # You could also read the PDF and display text content if desired.
            else:
                st.warning(f"PDF file '{pdf_filename}' not found in '{PDF_DIR}'. Please ensure it's uploaded and the path is correct.")


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