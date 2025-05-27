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
from memory_vector import embed_and_store_interaction, retrieve_similar_examples
from suggestor import suggest_reply, adjust_tone
from ocr import extract_text_from_image
from doc_embedder import embed_documents_parallel
from notion_embedder import embed_huddles_qdrant
from qdrant_client import QdrantClient

load_dotenv()

PDF_DIR = "public"
COLLECTION_NAME = "docs_memory"
VECTOR_SIZE = 1536

st.set_page_config(page_title="Test Auth", layout="centered")

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
    min_words = st.slider("Minimum words in draft", 5, 20, 8)
    min_chars = st.slider("Minimum characters in screenshot text", 10, 100, 20)
    require_question = st.checkbox("Require a question in the draft?", value=False)

with st.sidebar.expander("⚙️ Admin Controls", expanded=False):
    st.markdown("#### AI Memory & Model Settings")
    model_choice = st.radio(
        "🤖 Choose AI Model",
        options=["gpt-4o", "gpt-3.5-turbo"],
        help="GPT-4o: best quality, GPT-3.5: fastest/cheapest"
    )
    st.markdown("---")
    embed_col, notion_col = st.columns(2)
    with embed_col:
        if st.button("📚 Re-embed Docs"):
            with st.spinner("Embedding communication docs..."):
                embed_documents_parallel(PDF_DIR, COLLECTION_NAME, VECTOR_SIZE)
            st.success("✅ Docs embedded successfully!")
    with notion_col:
        if st.button("🧠 Re-sync Notion"):
            with st.spinner("Syncing Notion huddles..."):
                embed_huddles_qdrant()
            st.success("✅ Notion memory embedded successfully!")

# ---- Polished Card Renderer ----
def render_polished_card(label, text, auto_copy=False):
    def format_text_html(text):
        text = re.sub(r"^\s*\n*", "", text.strip())
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.replace('\n', '<br>')
    unique_id = uuid.uuid4().hex[:8]
    safe_text = text.replace("\\", "\\\\").replace("`", "\\`").replace('"', '\\"').replace("\n", "\\n")
    formatted_html = format_text_html(text)
    fixed_height = 400
    auto_copy_script = f"""
    <script>
        window.addEventListener('DOMContentLoaded', () => {{
            navigator.clipboard.writeText(`{safe_text}`);
            const alertBox = document.getElementById('copyAlert-{unique_id}');
            if (alertBox) {{
                alertBox.style.display = 'inline-block';
                setTimeout(() => {{
                    alertBox.style.display = 'none';
                }}, 1500);
            }}
        }});
    </script>
    """ if auto_copy else ""
    full_html = f"""
    <div style="
        max-width: 100vw; background-color: #1e1e1e; border: 1px solid #333;
        border-radius: 12px; box-shadow: 0 20px 6px rgba(0,0,0,0.1); padding: 16px; margin: 0;
        font-family: 'Segoe UI', sans-serif; font-size: 16px; color: #f0f0f0;">
        <h4 style="margin: 0 0 12px 0;">{label}</h4>
        <div id="copyText-{unique_id}" style="
            background: #2a2a2a; border-radius: 8px; padding: 12px;
            white-space: normal; line-height: 1.6; border: 1px solid #444;
            overflow-y: auto; height: {fixed_height}px;">
            {formatted_html}
        </div>
        <button onclick="
            navigator.clipboard.writeText(document.getElementById('copyText-{unique_id}').innerText);
            const alertBox = document.getElementById('copyAlert-{unique_id}');
            alertBox.style.display = 'inline-block';
            setTimeout(() => {{
                alertBox.style.display = 'none';
            }}, 1500);
        " style="
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
    components.html(full_html, height=fixed_height + 70, scrolling=True)

# ---- Main Tabs ----
tab1, tab2, tab3 = st.tabs(["Huddle Play", "View Documents", "📚 View Past Huddles"])

# =============== TAB 1: HUDDLE PLAY ===============
with tab1:
    with st.container():
        st.markdown("<div id='tab1-wrapper'>", unsafe_allow_html=True)
        # Session state for outputs and scroll triggers
        session_keys = ["final_reply", "adjusted_reply", "doc_matches", "screenshot_text", "user_draft", "similar_examples"]
        for key in session_keys:
            if key not in st.session_state:
                st.session_state[key] = None if key != "doc_matches" else []
        if "scroll_to_draft" not in st.session_state:
            st.session_state.scroll_to_draft = False
        if "last_uploaded_filename" not in st.session_state:
            st.session_state.last_uploaded_filename = None

        # ---- Upload UI ----
        uploaded_image = st.file_uploader(
            "Upload image", type=["jpg", "jpeg", "png"],
            label_visibility="collapsed", key=f"upload_img_{st.session_state.uploader_key}"
        )
        if uploaded_image:
            image = Image.open(uploaded_image)
            st.image(image, use_container_width=True)
        if uploaded_image:
            current_filename = uploaded_image.name
            if st.session_state.last_uploaded_filename != current_filename:
                st.session_state.scroll_to_draft = True
                st.session_state.last_uploaded_filename = current_filename
        if st.session_state.scroll_to_draft:
            st.components.v1.html("""
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
        user_draft = st.text_area("Your Draft Message", label_visibility="collapsed", height=110, key="user_draft")
        # ---- Generate AI Reply ----
        if st.button("🚀 Generate AI Reply") and uploaded_image and user_draft:
            st.session_state.adjusted_reply = None
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(uploaded_image.getvalue())
                tmp_path = tmp_file.name
        
            # ⏳ Show spinner while extracting text (OCR)
            with st.spinner("🔍 Extracting text from screenshot..."):
                start = time.time()
                screenshot_text = extract_text_from_image(tmp_path)
                print(f"OCR time: {time.time() - start:.2f}s")
            if not screenshot_text.strip():
                st.warning("⚠️ Screenshot text couldn't be read clearly. Please try a clearer image.")
            else:
                similar_examples = retrieve_similar_examples(screenshot_text, user_draft)
                st.session_state.similar_examples = similar_examples
                principles = '''1. Be clear and confident. 2. Ask questions, don’t convince. 3. Use connection > persuasion. 4. Keep it short, warm, and human. 5. Stick to the Huddle flow and tone.'''
                with st.spinner("🤖 Generating AI reply..."):
                    ai_start = time.time()
                    final_reply, doc_matches = suggest_reply(
                        screenshot_text=screenshot_text,
                        user_draft=user_draft,
                        principles=principles,
                        model_name=model_choice
                    )
                print(f"AI reply time: {time.time() - ai_start:.2f}s")
                print(f"Total time: {time.time() - start:.2f}s")
                st.session_state.final_reply = final_reply
                st.session_state.doc_matches = doc_matches
                st.session_state.screenshot_text = screenshot_text

            # ---- Save or Fail Reason ----
            failure_reasons = []
            if len(user_draft.strip().split()) < min_words:
                failure_reasons.append(f"- Your draft only has {len(user_draft.strip().split())} words (min required: {min_words})")
            if len(screenshot_text.strip()) < min_chars:
                failure_reasons.append(f"- Screenshot text has only {len(screenshot_text.strip())} characters (min required: {min_chars})")
            if require_question and "?" not in user_draft:
                failure_reasons.append("- Draft doesn't include a question")
            is_quality = len(failure_reasons) == 0
            if is_quality:
                with st.spinner("💾 Saving huddle..."):
                    embed_and_store_interaction(
                        screenshot_text=screenshot_text,
                        user_draft=user_draft,
                        ai_suggested=final_reply
                    )
                    save_huddle_to_notion(
                        screenshot_text,
                        user_draft,
                        final_reply,
                        st.session_state.get("adjusted_reply", "")
                    )
                st.success("💾 Huddle saved successfully.")
            else:
                st.warning("⚠️ This huddle wasn't saved due to the following reason(s):")
                for reason in failure_reasons:
                    st.markdown(f"• {reason}")

        # ---- Display Final Reply and Tone Controls ----
        if st.session_state.final_reply:
            st.subheader("✅ Suggested Reply")
            render_polished_card("", st.session_state.final_reply, auto_copy=True)
            tone = st.selectbox("🎨 Adjust Tone", ["None", "Professional", "Casual", "Inspiring", "Empathetic", "Direct"], key="tone")
            if tone != "None" and st.button("🎯 Regenerate with Tone"):
                with st.spinner("🎨 Adjusting tone..."):
                    st.session_state.adjusted_reply = adjust_tone(st.session_state.final_reply, tone)
                # Repeat quality check for adjusted reply
                failure_reasons = []
                if len(user_draft.strip().split()) < min_words:
                    failure_reasons.append(f"- Your draft only has {len(user_draft.strip().split())} words (min required: {min_words})")
                if len(screenshot_text.strip()) < min_chars:
                    failure_reasons.append(f"- Screenshot text has only {len(screenshot_text.strip())} characters (min required: {min_chars})")
                if require_question and "?" not in user_draft:
                    failure_reasons.append("- Draft doesn't include a question")
                is_quality = len(failure_reasons) == 0
                if is_quality:
                    embed_and_store_interaction(
                        screenshot_text=screenshot_text,
                        user_draft=user_draft,
                        ai_suggested=st.session_state.adjusted_reply
                    )
                    save_huddle_to_notion(
                        screenshot_text,
                        user_draft,
                        st.session_state.final_reply,
                        st.session_state.adjusted_reply
                    )
                    st.success("💾 Tone-adjusted reply saved to Notion and Qdrant.")
                else:
                    st.warning("⚠️ This huddle wasn't saved due to the following reason(s):")
                    for reason in failure_reasons:
                        st.markdown(f"• {reason}")
        if st.session_state.adjusted_reply:
            st.subheader(f"🎉 Regenerated Reply ({st.session_state.tone})")
            render_polished_card("Adjusted Reply", st.session_state.adjusted_reply, auto_copy=True)

        # ---- Show Used Docs and Examples ----
        st.markdown("<div id='suggestedAnchor'></div>", unsafe_allow_html=True)
        if st.session_state.doc_matches:
            st.subheader("📄 Relevant Communication Docs Used")
            for match in st.session_state.doc_matches:
                with st.expander(f"🧠 From: {match.get('source', 'Unknown')}"):
                    st.markdown(f"> {match.get('document', '')}")
        else:
            st.info("No relevant document matches found.")

        qdrant = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        if st.session_state.get("similar_examples"):
            st.subheader("🧠 Similar Past Huddle Plays Used")
            for idx, example in enumerate(st.session_state.similar_examples):
                if not any([example.get("screenshot_text"), example.get("user_draft"), example.get("ai_reply")]):
                    continue
                with st.expander(f"🔁 Past Huddle {idx + 1}"):
                    st.markdown("**🖼 Screenshot Text**")
                    st.markdown(example.get("screenshot_text") or "_Not available_")
                    st.markdown("**✍️ User Draft**")
                    st.markdown(example.get("user_draft") or "_Not available_")
                    st.markdown("**🤖 Final AI Reply**")
                    st.markdown(example.get("ai_reply") or "_Not available_")
                    boost = example.get("boost", 1.0)
                    if st.button(f"🔼 Boost This Example {idx + 1}", key=f"boost_{idx}"):
                        new_boost = boost + 1.0
                        try:
                            qdrant.set_payload(
                                collection_name="huddle_memory",
                                points=[example["point_id"]],
                                payload={"boost": new_boost}
                            )
                            st.success(f"✅ Boosted to {new_boost}x — refresh to apply")
                        except Exception as e:
                            st.error(f"⚠️ Failed to boost: {e}")
        if st.button("➕ Start New Huddle", key="new_huddle_button_tab1"):
            for k in session_keys + ["last_uploaded_filename"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state.uploader_key += 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)  # End tab1-wrapper

# =============== TAB 2: VIEW DOCUMENTS ===============
with tab2:
    st.markdown("### 📚 Key Documents")
    st.caption("Tap the tabs below to browse important Huddle tools.")
    doc_tabs = st.tabs(["One Line Bridge", "Make People Aware", "Door to Mentorship", "FAQ"])
    doc_pdf_links = [
        ("OLB.pdf", "One Line Bridge"), ("MPA.pdf", "Make People Aware"),
        ("DTM.pdf", "Door to Mentorship"), ("FAQ.pdf", "FAQ")
    ]
    for i, tab in enumerate(doc_tabs):
        with tab:
            st.markdown(f"## {doc_pdf_links[i][1]}")
            st.markdown(f"[📄 Tap here to view the {doc_pdf_links[i][1]} PDF](./public/{doc_pdf_links[i][0]})", unsafe_allow_html=True)

# =============== TAB 3: PAST HUDDLES ===============
with tab3:
    st.subheader("📖 Past Huddle Interactions")
    huddles = load_all_interactions()
    sorted_huddles = sorted(huddles, key=lambda h: h.get("timestamp", ""), reverse=True)
    if not huddles:
        st.info("No huddles saved yet.")
    else:
        for idx, huddle in enumerate(sorted_huddles):
            with st.expander(f"Huddle {len(huddles) - idx}: {huddle['timestamp']}"):
                st.markdown("**🖼 Screenshot Text**")
                st.write(huddle['screenshot_text'])
                st.markdown("**📝 User Draft**")
                st.write(huddle['user_draft'])
                st.markdown("**🤖 AI Suggested Reply**")
                st.write(huddle['ai_suggested'])
                if huddle.get('user_final'):
                    st.markdown("**🧠 Final Edit (You)**")
                    st.write(huddle['user_final'])
        st.markdown("</div>", unsafe_allow_html=True)
