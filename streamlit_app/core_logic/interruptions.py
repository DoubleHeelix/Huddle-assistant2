# logic/interruptions.py

import streamlit as st
import base64
import io
import os
from PIL import Image
import streamlit.components.v1 as components
from ocr import extract_text_from_image
from openai import OpenAI
from notion_client import Client

def interruptions_tab(render_polished_card):
    # --- Setup OpenAI and Notion clients ---
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Notion setup
    try:
        notion_api_key_env = os.getenv("NOTION_API_KEY")
        if not notion_api_key_env:
            notion = None
            NOTION_DATABASE_ID = None
        else:
            notion = Client(auth=notion_api_key_env)
            db_id_raw = os.getenv("NOTION_TONE_DB_ID", "")
            NOTION_DATABASE_ID = db_id_raw.replace("-", "") if db_id_raw else None
            if not NOTION_DATABASE_ID:
                notion = None
    except Exception:
        notion = None
        NOTION_DATABASE_ID = None

    def save_human_override(story_text, image_url_provided, ai_message, human_message, analysis_type="unknown", prompt_version="unknown"):
        if not notion or not NOTION_DATABASE_ID:
            st.error("Notion client not configured correctly. Cannot save override.")
            return
        image_url_for_notion = "N/A"
        if image_url_provided and image_url_provided.startswith("data:image"):
            image_url_for_notion = "Image data provided (Base64)"
        elif image_url_provided:
            image_url_for_notion = str(image_url_provided)[:2000]
        try:
            properties_payload = {
                "Story Text": {"rich_text": [{"text": {"content": str(story_text)[:1000] or "N/A"}}]},
                "Image URL": {"rich_text": [{"text": {"content": image_url_for_notion}}]},
                "AI Message": {"rich_text": [{"text": {"content": str(ai_message) or "N/A"}}]},
                "Your message": {"rich_text": [{"text": {"content": str(human_message) or "N/A"}}]},
                "Tone": {"rich_text": [{"text": {"content": str(analysis_type)}}]},
                "Prompt Version": {"rich_text": [{"text": {"content": prompt_version}}]}
            }
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties=properties_payload
            )
            st.success("✅ Your version saved to Notion!")
        except Exception as e:
            st.error(f"Notion save failed: {e}")

    st.markdown(
        "<div class='center-text'><h4>📸 Story Interruption Generator</h4></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='center-text'><span class='story-desc'>Upload an Instagram story. The Huddle bot will suggest 3 warm, curious, and authentic replies based on the content.</span></div>",
        unsafe_allow_html=True,
    )

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

        def get_random_prompt():
            import random
            prompt_a = (
                "You are an observant and thoughtful friend crafting Instagram story replies. "
                "Your goal is to start genuine, warm, and curious conversations based strictly on the visible content. "
                "Always reference what's actually there—no guessing or speculation. "
                "Keep replies authentic, friendly, and simple. Use at most one emoji, only if it fits naturally."
            )
            prompt_b = (
                "You are a friendly and engaging buddy replying to Instagram stories. "
                "Your aim is to spark a fun and lighthearted chat by noticing something specific in the story. "
                "Be curious and ask a simple question about what you see. "
                "Keep it casual and use a single emoji to add a bit of personality."
            )
            return random.choice([(prompt_a, "A"), (prompt_b, "B")])

        def generate_multiple_conversation_starters(text, image_url=None, n=3):
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
            
            system_prompt, prompt_version = get_random_prompt()
            st.session_state.prompt_version = prompt_version

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
            completions = [choice.message.content.strip() for choice in response.choices]
            return completions

        conversation_starters = st.session_state.get("conversation_starters")
        if conversation_starters is None:
            with st.spinner("🤖 Generating 3 options..."):
                st.session_state.conversation_starters = generate_multiple_conversation_starters(text, image_url, n=3)
            conversation_starters = st.session_state.conversation_starters

        conversation_starters = conversation_starters or []
        for idx, reply in enumerate(conversation_starters):
            render_polished_card(f"Conversation Starter #{idx+1}", reply, auto_copy=True)

        st.markdown("#### ✏️ Your Adjusted Message")
        if "user_edit" not in st.session_state or not st.session_state.get("user_edit"):
            st.session_state.user_edit = conversation_starters[0] if conversation_starters else ""
        st.session_state.user_edit = st.text_area(
            "",
            value=st.session_state.user_edit,
            height=120
        )

        col1_gen, col2_regen = st.columns(2)
        with col1_gen:
            if st.button("✅ Save My Version", use_container_width=True):
                image_url_safe = image_url if image_url else "N/A"
                save_human_override(
                    text,
                    image_url_safe,
                    "\n".join(conversation_starters),
                    st.session_state.user_edit,
                    "user_edited",
                    st.session_state.get("prompt_version", "unknown")
                )
                st.success("✅ Saved to Notion! Your edits will influence future responses.")

        with col2_regen:
            if st.button("🔄 Regenerate All", use_container_width=True):
                replies = generate_multiple_conversation_starters(text, image_url)
                st.session_state.conversation_starters = replies
                st.session_state.user_edit = replies[0] if replies else ""
                st.rerun()

        if st.button("➕ Start New Interruption", key="new_story_button", use_container_width=True):
            for key in ["conversation_starters", "last_uploaded_story_name", "scroll_to_story_text", "user_edit", "prompt_version"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.uploader_key_tab2 += 1
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
