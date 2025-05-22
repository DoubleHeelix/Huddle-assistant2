import streamlit as st
from memory import save_huddle_to_notion, load_all_interactions
from suggestor import suggest_reply
from memory_vector import retrieve_similar_examples
from ocr import extract_text_from_image
import tempfile
import base64
from PIL import Image
from doc_embedder import embed_documents
from notion_embedder import embed_huddles


def load_markdown(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def embed_pdf(path):
    with open(path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    return f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600px" type="application/pdf"></iframe>'

st.set_page_config(page_title="Huddle Assistant with Learning Memory", layout="centered")

#----------------- Side bar ------------------------
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
        embed_huddles()
        st.success("✅ Notion memory embedded successfully.")


st.title("🤝 Huddle Assistant 🤝")

tab1, tab2, tab3 = st.tabs(["New Huddle Play","View Documents", "📚 View Past Huddles"])

# ------------------- Tab 1 -------------------
with tab1:
    uploaded_image = st.file_uploader("📸 Upload screenshot", type=["jpg", "jpeg", "png"])

    if uploaded_image:
        image = Image.open(uploaded_image)
        st.image(image, caption="Uploaded Screenshot", use_container_width=True)

    user_draft = st.text_area("✍️ Your Draft Message")

    if st.button("Generate AI Reply") and uploaded_image and user_draft:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(uploaded_image.getvalue())
            tmp_path = tmp_file.name

        screenshot_text = extract_text_from_image(tmp_path)
        if not screenshot_text.strip():
            st.warning("⚠️ Screenshot text couldn't be read clearly. Please try a clearer image.")


        principles = '''
1. Be clear and confident.
2. Ask questions, don’t convince.
3. Use connection > persuasion.
4. Keep it short, warm, and human.
5. Stick to the Huddle flow and tone.
'''

        similar_examples = retrieve_similar_examples(screenshot_text, user_draft)
        examples_prompt = ""
        for ex in similar_examples:
            examples_prompt += f"EXAMPLE\nScreenshot: {ex['screenshot']}\nDraft: {ex['draft']}\nReply Sent: {ex['final'] or ex['ai']}\n---\n"

        final_reply, doc_matches = suggest_reply(
            screenshot_text=screenshot_text,
            user_draft=user_draft,
            principles=principles + "\n\nHere are some similar past plays:\n" + examples_prompt,
            model_name=model_choice
        )

        st.subheader("✅ Suggested Final Reply")
        st.write(final_reply)

        # Show document insights used
        st.subheader("📄 Relevant Communication Docs Used")

        if not doc_matches: 
            st.info("No relevant document matches found.")
        else:
            for match in doc_matches:
                with st.expander(f"🧠 From: {match.get('source', 'Unknown')}"):
                    st.markdown(f"> {match.get('document', '')}")

        # Show similar examples used
        st.subheader("🔍 Similar Past Huddles Found")
        for ex in similar_examples:
            with st.expander("🧠 Example from Memory"):
                st.markdown("**🖼 Screenshot Text**")
                st.write(ex.get("screenshot", ""))
                st.markdown("**📝 Draft**")
                st.write(ex.get("draft", ""))
                st.markdown("**✅ Final Sent**")
                st.write(ex.get("final") or ex.get("ai", ""))

         # Save to Notion
        save_huddle_to_notion(
            screenshot_text=screenshot_text,
            user_draft=user_draft,
            ai_reply=final_reply,
            user_final=None
        )

        st.success("✅ Huddle logged to Notion!")

# ------------------- Tab 2 -------------------
with tab2:
    st.markdown("### 📚 Key Documents")
    st.caption("Tap the tabs below to browse important Huddle tools.")

    doc_tabs = st.tabs([
        "One Line Bridge", 
        "Make People Aware", 
        "Door to Mentorship", 
        "FAQ"
    ])

    with doc_tabs[0]:
        st.markdown("## One Line Bridge", help="Use these warm openers to reconnect")
        st.markdown("[📄 Tap here to view the OLB PDF](./public/OLB.pdf)", unsafe_allow_html=True)

    with doc_tabs[1]:
        st.markdown("## Make People Aware", help="Spark interest with clear awareness")
        st.markdown("[📄 Tap here to view the MPA PDF](./public/MPA.pdf)", unsafe_allow_html=True)

    with doc_tabs[2]:
        st.markdown("## Door to Mentorship", help="Invite interest into next steps")
        st.markdown("[📄 Tap here to view the DTM PDF](./public/DTM.pdf)", unsafe_allow_html=True)

    with doc_tabs[3]:
        st.markdown("## FAQ", help="Handle common questions confidently")
        st.markdown("[📄 Tap here to view the FAQ PDF](./public/FAQ.pdf)", unsafe_allow_html=True)

# ------------------- Tab 3 -------------------
with tab3:
    st.subheader("📖 Past Huddle Interactions")
    huddles = load_all_interactions()
    sorted_huddles = sorted(huddles, key=lambda h: h.get("timestamp", ""), reverse=True)
    if not huddles:
        st.info("No huddles saved yet.")
    else:
        for idx, huddle in enumerate(huddles):
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
