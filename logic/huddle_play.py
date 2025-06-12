# logic/huddle_play.py

import streamlit as st
import tempfile
import os
import uuid
import time
import streamlit.components.v1 as components

from memory import save_huddle_to_notion
from memory_vector import embed_and_store_interaction, retrieve_similar_examples
from suggestor import get_context_for_reply, generate_suggested_reply, generate_adjusted_tone
from ocr import extract_text_from_image
from doc_embedder import embed_documents_parallel
from notion_embedder import embed_huddles_qdrant
from qdrant_client import QdrantClient

PDF_DIR = "public"
COLLECTION_NAME = "docs_memory"
HUDDLE_MEMORY_COLLECTION = "huddle_memory"
VECTOR_SIZE = 1536

def huddle_play_tab(render_polished_card):
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
                    embed_huddles_qdrant()
                st.success("✅ Notion memory embedded successfully!")

    st.markdown("<div id='tab1-wrapper'>", unsafe_allow_html=True)

    # --- Upload UI ---
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
                "screenshot_text_content", "similar_examples_retrieved",
                "huddle_context_for_regen", "doc_context_for_regen", "principles_for_regen"
            ]
            for key_to_clear in keys_to_reset_for_new_image:
                if key_to_clear in st.session_state:
                    st.session_state[key_to_clear] = None

            st.session_state.user_draft_current = ""
            st.session_state.user_draft_widget_key = f"user_draft_new_img_{uuid.uuid4().hex[:6]}"

    if st.session_state.scroll_to_draft:
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

    st.markdown(
        """<p class='draft-message-label'>Your Draft Message</p>""",
        unsafe_allow_html=True,
    )
    st.session_state.user_draft_current = st.text_area(
        "Internal draft message label for accessibility",
        value=st.session_state.user_draft_current,
        placeholder="Write your message here...",
        label_visibility="collapsed", height=110,
        key=st.session_state.user_draft_widget_key
    )

    # --- Action Buttons ---
    col1_gen, col2_regen = st.columns(2)
    with col1_gen:
        if st.button("🚀 Generate AI Reply", key="generate_reply_button_main", use_container_width=True):
            _handle_ai_generation_and_save(uploaded_image, render_polished_card, is_regeneration=False)
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
                _handle_ai_generation_and_save(uploaded_image, render_polished_card, is_regeneration=True)
            else:
                st.info("Generate an initial reply first, or ensure all inputs (image, draft) are present for context.")

    # ---- Display Final Reply and Tone Controls ----
    if st.session_state.final_reply_collected and not (isinstance(st.session_state.final_reply_collected, str) and st.session_state.final_reply_collected.startswith("Error:")):
        st.subheader("✅ Suggested Reply")
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
                st.success("💾 Memory Stored")
            else:
                st.warning("⚠️ This adjusted huddle wasn't saved:")
                for reason_adj in failure_reasons_adj:
                    st.markdown(f"• {reason_adj}")
        elif st.session_state.adjusted_reply_collected and (isinstance(st.session_state.adjusted_reply_collected, str) and st.session_state.adjusted_reply_collected.startswith("Error:")):
            st.error(f"Tone Adjustment Failed: {st.session_state.adjusted_reply_collected}")

    if st.session_state.adjusted_reply_collected and not (isinstance(st.session_state.adjusted_reply_collected, str) and st.session_state.adjusted_reply_collected.startswith("Error:")):
        st.subheader(f"🎉 Regenerated Reply ({st.session_state.current_tone_selection})")
        render_polished_card("Adjusted Reply", st.session_state.adjusted_reply_collected, auto_copy=True)

    # ---- Show Used Docs and Examples ----
    st.markdown("<div id='suggestedAnchor'></div>", unsafe_allow_html=True)
    if st.session_state.doc_matches_for_display:
        st.subheader("📄 Relevant Communication Docs Used by AI")
        for match in st.session_state.doc_matches_for_display:
            if isinstance(match, dict):
                with st.expander(f"🧠 From: {match.get('source', 'Unknown')}"):
                    st.markdown(f"> {match.get('document', '')}")
            else:
                st.warning(f"Unexpected document match format: {match}")
    elif st.session_state.final_reply_collected and not (isinstance(st.session_state.final_reply_collected, str) and st.session_state.final_reply_collected.startswith("Error:")):
        st.info("No specific external documents were heavily weighted by the AI for this reply.")

    if st.session_state.similar_examples_retrieved:
        st.subheader("🧠 Similar Past Huddle Plays (For Your Reference)")
        examples_to_show = st.session_state.similar_examples_retrieved
        if isinstance(st.session_state.similar_examples_retrieved, tuple) and len(st.session_state.similar_examples_retrieved) > 0:
            examples_to_show = st.session_state.similar_examples_retrieved[0]

        if not examples_to_show:
            st.info("No highly similar past huddle plays found in memory.")
        else:
            for idx, example in enumerate(examples_to_show):
                payload = example.get("payload", example) if isinstance(example, dict) else {}
                if not (isinstance(payload, dict) and any([payload.get(k) for k in ["screenshot_text", "user_draft", "ai_reply", "ai_suggested"]])):
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
                            if 'payload' in example and isinstance(example['payload'], dict):
                                example['payload']['boost'] = new_boost
                            elif isinstance(example, dict):
                                example['boost'] = new_boost
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Failed to boost: {e}")
    elif st.session_state.final_reply_collected and not (isinstance(st.session_state.final_reply_collected, str) and st.session_state.final_reply_collected.startswith("Error:")):
        st.info("No similar past huddle examples were retrieved for display during the initial generation.")

    # ---- Start New Huddle Button ----
    if st.button("➕ Start New Huddle", key="new_huddle_button_tab1", use_container_width=True):
        keys_to_potentially_delete = [k for k in st.session_state.keys() if k.startswith("upload_img_") or k.startswith("boost_") or k.startswith("tone_selectbox_key")]
        for k_del in keys_to_potentially_delete:
            if k_del in st.session_state:
                del st.session_state[k_del]
        session_keys_defaults = {
            "final_reply_collected": None,
            "adjusted_reply_collected": None,
            "doc_matches_for_display": [],
            "screenshot_text_content": None,
            "user_draft_current": "",
            "similar_examples_retrieved": None,
            "user_draft_widget_key": "user_draft_initial",
            "current_tone_selection": "None",
            "last_uploaded_filename": None,
            "scroll_to_draft": False,
            "scroll_to_interruption": False,
            "huddle_context_for_regen": None,
            "doc_context_for_regen": None,
            "principles_for_regen": None,
        }
        for k_clear in session_keys_defaults.keys():
            if k_clear in st.session_state:
                st.session_state[k_clear] = session_keys_defaults[k_clear]
        st.session_state.uploader_key += 1
        st.session_state.user_draft_current = ""
        st.session_state.user_draft_widget_key = f"user_draft_{uuid.uuid4().hex[:6]}"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def _handle_ai_generation_and_save(current_uploaded_image, render_polished_card, is_regeneration=False):
    # Import as needed to avoid circular imports
    import time

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
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
        elif not st.session_state.screenshot_text_content:
            st.error("Critical Error: Screenshot text is missing and no image provided for OCR.")
            return

    if not st.session_state.screenshot_text_content or not st.session_state.screenshot_text_content.strip():
        st.warning("⚠️ Screenshot text couldn't be read clearly. Please try again or use a clearer image.")
        return

    if not is_regeneration:
        with st.spinner("🧠 Retrieving similar past huddles for your reference..."):
            st.session_state.similar_examples_retrieved = retrieve_similar_examples(
                st.session_state.screenshot_text_content,
                st.session_state.user_draft_current
            )

    # --- Context Retrieval for LLM ---
    context_spinner_msg = "📚 Retrieving context for AI..."
    with st.spinner(context_spinner_msg):
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

    ai_spinner_msg = "🧠 Thinking of a new angle..." if is_regeneration else "🤖 Generating AI reply..."
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

    if isinstance(generated_reply, str) and generated_reply.startswith("Error:"):
        st.error(f"AI Generation Failed: {generated_reply}")
        return

    if is_regeneration:
        st.success("💡 New suggestion generated!")

    failure_reasons = []
    if len(st.session_state.user_draft_current.strip().split()) < st.session_state.min_words_slider:
        failure_reasons.append(f"- Draft: {len(st.session_state.user_draft_current.strip().split())} words (min: {st.session_state.min_words_slider})")
    if len(st.session_state.screenshot_text_content.strip()) < st.session_state.min_chars_slider:
        failure_reasons.append(f"- Screenshot: {len(st.session_state.screenshot_text_content.strip())} chars (min: {st.session_state.min_chars_slider})")
    if st.session_state.require_question_checkbox and "?" not in st.session_state.user_draft_current:
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
        st.success("💾 Stored Memory.")
    else:
        st.warning("⚠️ This huddle wasn't saved:")
        for reason in failure_reasons:
            st.markdown(f"• {reason}")

