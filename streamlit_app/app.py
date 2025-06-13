import streamlit as st
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.card import render_polished_card
from core_logic.huddle_play import huddle_play_tab
from core_logic.interruptions import interruptions_tab
from core_logic.past_huddles import past_huddles_tab
from utils.state import init_session_state

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(page_title="Huddle Play Assistant", page_icon="🤝", layout="centered")

init_session_state()

if "started_app" not in st.session_state:
    st.session_state.started_app = False

if not st.session_state.started_app:
    st.markdown("""
    <style>
    /* General Resets */
    html, body, .stApp, .main .block-container {
        padding: 0 !important;
        margin: 0 !important;
    }
    header[data-testid="stHeader"] {
        display: none !important;
    }

    /* Background */
    .stApp {
        background: linear-gradient(135deg, #1b1332 0%, #8a3ffc 45%, #b88cff 90%) !important;
        min-height: 100vh;
    }

    /* Layout */
    .landing-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 0;
        padding: 2rem;
    }

    /* Text Styles */
    .landing-title {
        font-size: 3.2rem;
        font-weight: 800;
        color: #fff;
        text-align: center;
        margin-bottom: 1.2rem;
    }
    .landing-subtitle {
        color: #f3eaff;
        font-size: 1.35rem;
        text-align: center;
        font-weight: 400;
        line-height: 1.3;
        max-width: 650px;
        margin-bottom: 2.4rem;
    }

    /* Center the button by styling its Streamlit container */
    div[data-testid="stButton"] {
        display: flex;
        justify-content: center;
    }

    /* Styling the Streamlit button */
    div[data-testid="stButton"] > button {
        background: #b88cff !important;
        color: #fff !important;
        border: 2px solid white !important;
        border-radius: 12px !important;
        font-size: 1.09rem !important;
        font-weight: 600 !important;
        padding: 0.85em 1.65em !important;
        box-shadow: 0 2px 8px rgba(138, 63, 252, 0.13) !important;
        margin-bottom: 0.3em !important;
        letter-spacing: 0.01em !important;
        animation: bounce 1.2s infinite cubic-bezier(.68,-0.55,.27,1.55) !important;
        transform-origin: bottom !important;
        transition: none !important;
    }

    div[data-testid="stButton"] > button:hover {
        background: #b88cff !important;
        filter: brightness(0.9) !important;
    }

    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-12px); }
    }

    /* Responsive */
    @media (max-width: 650px) {
        .landing-title {
            font-size: 2.1rem;
        }
        .landing-subtitle {
            font-size: 1.08rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="landing-container">', unsafe_allow_html=True)
        st.markdown('<div class="landing-title">Huddle Play Assistant</div>', unsafe_allow_html=True)
        st.markdown('<div class="landing-subtitle">Lead confident, authentic conversations powered by AI.<br>Start your next connection here.</div>', unsafe_allow_html=True)

        if st.button('Get Started →', key="get_started_btn", help="Enter Huddle Play Assistant"):
            st.session_state.started_app = True
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
else:
    # --- Main App ONLY ---

    # Override any gradient background left from landing page
    load_css("styles/styles.css")

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

    tab1, tab2, tab3 = st.tabs(["Huddle Play", "Interruptions", "📚 View Past Huddles"])

    with tab1:
        huddle_play_tab(render_polished_card)
    with tab2:
        interruptions_tab(render_polished_card)
    with tab3:
        past_huddles_tab()
