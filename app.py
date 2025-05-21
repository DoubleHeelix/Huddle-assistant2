import streamlit as st
from memory import load_all_interactions
from suggestor import suggest_reply
from ocr import extract_text_from_image
import tempfile

st.set_page_config(page_title="Huddle Assistant with Memory", layout="centered")
st.title("🤝 Huddle Assistant")

tab1, tab2 = st.tabs(["New Huddle Play", "📚 View Past Huddles"])

with tab1:
    uploaded_image = st.file_uploader("📸 Upload screenshot", type=["jpg", "jpeg", "png"])

    if uploaded_image:
        from PIL import Image
        image = Image.open(uploaded_image)
        st.image(image, caption="Uploaded Screenshot", use_column_width=True)

    user_draft = st.text_area("✍️ Your Draft Message")

    if uploaded_image and user_draft:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(uploaded_image.getvalue())
            tmp_path = tmp_file.name

        screenshot_text = extract_text_from_image(tmp_path)

        # Hardcoded principles for now
        principles = '''
1. Be clear and confident.
2. Ask questions, don’t convince.
3. Use connection > persuasion.
4. Keep it short, warm, and human.
5. Stick to the Huddle flow and tone.
'''

        final_reply = suggest_reply(screenshot_text, user_draft, principles)
        st.subheader("✅ Suggested Final Reply")
        st.write(final_reply)


with tab2:
    st.subheader("📖 Past Huddle Interactions")
    huddles = load_all_interactions()

    if not huddles:
        st.info("No huddles saved yet.")
    else:
        for idx, huddle in enumerate(reversed(huddles)):
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
