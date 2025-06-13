# utils/state.py

import streamlit as st

def init_session_state():
    """Set up all required session state keys with default values."""
    defaults = {
        "final_reply_collected": None,
        "adjusted_reply_collected": None,
        "doc_matches_for_display": [],
        "screenshot_text_content": None,
        "user_draft_current": "",
        "similar_examples_retrieved": None,
        "current_tone_selection": "None",
        "last_uploaded_filename": None,
        "scroll_to_draft": False,
        "scroll_to_interruption": False,
        "huddle_context_for_regen": None,
        "doc_context_for_regen": None,
        "principles_for_regen": None,
        "uploader_key": 0,
        # Tab 2
        "uploader_key_tab2": 0,
        "conversation_starters": None,
        "last_uploaded_story_name": None,
        "scroll_to_story_text": False,
        "user_edit": "",
        "draft_feedback": [],
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
