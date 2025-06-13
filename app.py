import streamlit as st
from components.card import render_polished_card
from logic.huddle_play import huddle_play_tab
from logic.interruptions import interruptions_tab
from logic.past_huddles import past_huddles_tab
from logic.landingpage import show_landing_page
from utils.state import init_session_state

from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(page_title="Huddle Play Assistant", page_icon="🤝", layout="centered")

# --- Show landing page or main app based on session_state ---
if "started_app" not in st.session_state:
    st.session_state.started_app = False

if not st.session_state.started_app:
    show_landing_page()
else:
    # --- Main App ONLY ---

    # Override any gradient background left from landing page
    with open("styles/styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # Header
    st.markdown(
        """
        <div class="header-container">
            <h2>🤝 Huddle Assistant</h2>
            <p>Lead confident convos on the go</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    init_session_state()  # Ensures session state defaults set

    tab1, tab2, tab3 = st.tabs(["Huddle Play", "Interruptions", "📚 View Past Huddles"])

    with tab1:
        huddle_play_tab(render_polished_card)
    with tab2:
        interruptions_tab(render_polished_card)
    with tab3:
        past_huddles_tab()
