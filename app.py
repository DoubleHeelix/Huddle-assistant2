import streamlit as st
from memory import save_huddle_to_notion, load_all_interactions
from memory_vector import embed_and_store_interaction, retrieve_similar_examples
from suggestor import suggest_reply, adjust_tone
from ocr import extract_text_from_image
import tempfile
import base64
from PIL import Image
from doc_embedder import embed_documents
from notion_embedder import embed_huddles_qdrant
import os
from openai import OpenAI
import streamlit.components.v1 as components
import re
import math

st.set_page_config(page_title="Huddle Assistant with Learning Memory", layout="centered")

# Global spacing fix (helps Render match local layout)
st.markdown("""
<style>
/* Universal spacing normalizer for Render */
section.main > div {
    padding-top: 0rem !important;
    padding-bottom: 0rem !important;
}

/* Tighten spacing under selectbox and subheaders */
.css-1kyxreq, .stSelectbox, .stMarkdown, .stSubheader {
    margin-bottom: 0.5rem !important;
    margin-top: 0.5rem !important;
}

/* Reduce expander top spacing */
.st-expander {
    margin-top: -0.5rem !important;
}

/* Optional: shrink spacing between AI reply and tone dropdown */
div[data-testid='stVerticalBlock'] > div:nth-child(2) {
    margin-top: -1rem !important;
}
</style>
""", unsafe_allow_html=True)


# ----------- Mobile Device Detection -----------
st.markdown("""
<script>
    const isMobile = /iPhone|iPad|Android/i.test(navigator.userAgent);
    window.parent.postMessage({ type: 'MOBILE_DEVICE', value: isMobile }, "*");
</script>
""", unsafe_allow_html=True)

if "is_mobile" not in st.session_state:
    st.session_state.is_mobile = False

_ = st.query_params

st.markdown("""
<script>
    window.addEventListener("message", (event) => {
        if (event.data?.type === "MOBILE_DEVICE") {
            window.parent.postMessage({ streamlitSetComponentValue: { key: "is_mobile", value: event.data.value }}, "*");
        }
    });
</script>
""", unsafe_allow_html=True)

def format_text_html(text):
    text = re.sub(r"^\s*\n*", "", text.strip())          # Remove leading newlines
    text = re.sub(r"\n{3,}", "\n\n", text)               # Normalize multiple newlines
    return text.replace('\n', '<br>')                    # Replace newlines with <br>

def render_polished_card(label, text, auto_copy=False):
    safe_text = text.replace("`", "\\`").replace("\\", "\\\\").replace('"', '\\"')
    formatted_html = format_text_html(text)

    avg_chars_per_line = 80
    base_height = 160
    line_height = 22
    line_count = math.ceil(len(text) / avg_chars_per_line)
    dynamic_height = base_height + (line_count * line_height)

    min_height = 400
    max_height = 1200
    final_height = min(max(dynamic_height + 200, min_height), max_height)

    auto_copy_script = f"""
        <script>
            window.addEventListener('DOMContentLoaded', () => {{
                navigator.clipboard.writeText(`{safe_text}`);
                const alertBox = document.getElementById('copyAlert');
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
    <div id="replyCardWrapper" style="
        max-width: 100vw;
        background-color: #1e1e1e;
        border: 1px solid #333;
        border-radius: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        padding: 16px;
        margin-bottom: 0px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 16px;
        color: #f0f0f0;
    ">
        <h4 style="margin: 0 0 12px 0;">{label}</h4>
        <div id="copyText" style="
            background: #2a2a2a;
            border-radius: 8px;
            padding: 4px 12px 12px 12px;
            white-space: normal;
            line-height: 1.6;
            border: 1px solid #444;
            overflow-y: auto;
        ">
            {formatted_html}
        </div>
        <button onclick="
            navigator.clipboard.writeText(document.getElementById('copyText').innerText);
            const alertBox = document.getElementById('copyAlert');
            alertBox.style.display = 'inline-block';
            setTimeout(() => {{
                alertBox.style.display = 'none';
            }}, 1500);
        " style="
            margin-top: 12px;
            padding: 6px 12px;
            background-color: #22c55e;
            color: white;
            border: none;
            border-radius: 6px;
            font-weight: 500;
            cursor: pointer;
        ">
            📋 Copy to Clipboard
        </button>
        <span id="copyAlert" style="display: none; margin-left: 10px; color: #22c55e; font-weight: 500;">
            ✅ Copied!
        </span>
        {auto_copy_script}
    </div>
    """

    # Inject CSS to reduce bottom spacing between the HTML component and the next Streamlit element
    st.markdown("""
        <style>
        div:has(> iframe[title="streamlit.components.v1.html"]) + div {
            margin-top: -1rem !important;
        }
        </style>
    """, unsafe_allow_html=True)

    components.html(full_html, height=final_height, scrolling=True)


# ----------- Sidebar -----------
with st.sidebar.expander("⚙️ Admin Controls", expanded=False):
    st.markdown("Use these to manually refresh AI memory.")

    model_choice = st.sidebar.radio(
        "🤖 Choose AI Model",
        options=["gpt-4", "gpt-3.5-turbo"],
        help="Use GPT-3.5 for faster, cheaper replies. GPT-4 is better for nuance and accuracy."
    )

    if st.button("📚 Re-embed Communication Docs"):
        embed_documents()
        st.success("✅ Docs embedded successfully.")

    if st.button("🧠 Re-sync Notion Huddles"):
        embed_huddles_qdrant()
        st.success("✅ Notion memory embedded successfully.")

# ----------- Main App Tabs -----------
st.title("🤝 Huddle Assistant 🤝")
tab1, tab2, tab3 = st.tabs(["New Huddle Play", "View Documents", "📚 View Past Huddles"])

# ----------- Tab 1: New Huddle Play -----------
with tab1:
    for key in ["final_reply", "adjusted_reply", "doc_matches", "screenshot_text", "user_draft", "similar_examples"]:
        if key not in st.session_state:
            st.session_state[key] = None if key != "doc_matches" else []

    uploaded_image = st.file_uploader("📸 Upload screenshot", type=["jpg", "jpeg", "png"])

    if uploaded_image:
        image = Image.open(uploaded_image)
        st.image(image, caption="Uploaded Screenshot", use_container_width=True)

    user_draft = st.text_area("✍️ Your Draft Message", value=st.session_state.user_draft or "")

    if st.button("Generate AI Reply") and uploaded_image and user_draft:
        st.session_state.adjusted_reply = None

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(uploaded_image.getvalue())
            tmp_path = tmp_file.name

        screenshot_text = extract_text_from_image(tmp_path)

        if not screenshot_text.strip():
            st.warning("⚠️ Screenshot text couldn't be read clearly. Please try a clearer image.")
        else:
            from memory_vector import retrieve_similar_examples
            similar_examples = retrieve_similar_examples(screenshot_text, user_draft)
            st.session_state.similar_examples = similar_examples

            principles = '''
1. Be clear and confident.
2. Ask questions, don’t convince.
3. Use connection > persuasion.
4. Keep it short, warm, and human.
5. Stick to the Huddle flow and tone.
'''

            final_reply, doc_matches = suggest_reply(
                screenshot_text=screenshot_text,
                user_draft=user_draft,
                principles=principles,
                model_name=model_choice
            )

            st.session_state.final_reply = final_reply
            st.session_state.doc_matches = doc_matches
            st.session_state.screenshot_text = screenshot_text
            st.session_state.user_draft = user_draft

    if st.session_state.final_reply:
        st.subheader("✅ Suggested Final Reply")
        height = 400 if st.session_state.get("is_mobile", False) else 540
        render_polished_card("", st.session_state.final_reply, auto_copy=True)

        st.markdown("<style>div[data-testid='stVerticalBlock'] > div:nth-child(2) { margin-top: -0.5rem !important; }</style>", unsafe_allow_html=True)

        tone = st.selectbox("🎨 Adjust Tone", ["None", "Professional", "Casual", "Inspiring", "Empathetic", "Direct"], key="tone")

        if tone != "None" and st.button("🎯 Regenerate with Tone"):
            tone_prompt = f"Rewrite the reply to sound more {tone.lower()}."
            revised_messages = [
                {"role": "system", "content": "You are a helpful and concise assistant."},
                {"role": "user", "content": f"""
Here is the original reply:
{st.session_state.final_reply}

{tone_prompt}
"""}
            ]
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            tone_response = client.chat.completions.create(
                model=model_choice,
                messages=revised_messages,
                temperature=0.7
            )
            st.session_state.adjusted_reply = tone_response.choices[0].message.content.strip()

    if st.session_state.adjusted_reply:
        st.subheader(f"🎉 Regenerated Reply ({st.session_state.tone})")
        height = 400 if st.session_state.get("is_mobile", False) else 540
        render_polished_card("", st.session_state.adjusted_reply)

    # 📄 Relevant Documents
    if st.session_state.doc_matches:
        st.subheader("📄 Relevant Communication Docs Used")
        for match in st.session_state.doc_matches:
            with st.expander(f"🧠 From: {match.get('source', 'Unknown')}"):
                st.markdown(f"> {match.get('document', '')}")
    else:
        st.info("No relevant document matches found.")

    # 🔁 Similar Past Huddle Plays
    if st.session_state.get("similar_examples"):
        st.subheader("🧠 Similar Past Huddle Plays Used")
        for idx, example in enumerate(st.session_state.similar_examples):
            with st.expander(f"🔁 Past Huddle {idx + 1}"):
                st.markdown("**🖼 Screenshot Text**")
                st.markdown(example.get("screenshot_text", "_Not available_"))
                st.write("🔍 DEBUG - Similar example payload:", example)

                st.markdown("**✍️ User Draft**")
                st.markdown(example.get("user_draft", "_Not available_"))

                st.markdown("**🤖 Final AI Reply**")
                st.markdown(example.get("ai_reply", "_Not available_"))

    if st.session_state.final_reply:
        save_huddle_to_notion(
            screenshot_text=st.session_state.screenshot_text,
            user_draft=st.session_state.user_draft,
            ai_reply=st.session_state.final_reply,
            user_final=st.session_state.adjusted_reply
        )

        from memory_vector import embed_and_store_interaction
        embed_and_store_interaction(
            screenshot_text=st.session_state.screenshot_text,
            user_draft=st.session_state.user_draft,
            ai_suggested=st.session_state.final_reply,
            user_final=st.session_state.adjusted_reply
        )

        st.success("✅ Huddle logged to Notion and Qdrant!")


# ----------- Tab 2: View Documents -----------
with tab2:
    st.markdown("### 📚 Key Documents")
    st.caption("Tap the tabs below to browse important Huddle tools.")

    doc_tabs = st.tabs(["One Line Bridge", "Make People Aware", "Door to Mentorship", "FAQ"])

    with doc_tabs[0]:
        st.markdown("## One Line Bridge")
        st.markdown("[📄 Tap here to view the OLB PDF](./public/OLB.pdf)", unsafe_allow_html=True)

    with doc_tabs[1]:
        st.markdown("## Make People Aware")
        st.markdown("[📄 Tap here to view the MPA PDF](./public/MPA.pdf)", unsafe_allow_html=True)

    with doc_tabs[2]:
        st.markdown("## Door to Mentorship")
        st.markdown("[📄 Tap here to view the DTM PDF](./public/DTM.pdf)", unsafe_allow_html=True)

    with doc_tabs[3]:
        st.markdown("## FAQ")
        st.markdown("[📄 Tap here to view the FAQ PDF](./public/FAQ.pdf)", unsafe_allow_html=True)

# ----------- Tab 3: Past Interactions -----------
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

                if huddle['user_final']:
                    st.markdown("**🧠 Final Edit (You)**")
                    st.write(huddle['user_final'])
