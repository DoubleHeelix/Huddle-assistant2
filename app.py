# app.py

import streamlit as st
from components.card import render_polished_card
from logic.huddle_play import huddle_play_tab
from logic.interruptions import interruptions_tab
from logic.past_huddles import past_huddles_tab
from utils.state import init_session_state

# Load env, setup page, CSS, etc.
from dotenv import load_dotenv
import os

load_dotenv()
st.set_page_config(page_title="Huddle Assistant", layout="wide")

# Styles
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
