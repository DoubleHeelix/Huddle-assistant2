import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os
from dotenv import load_dotenv
from suggestor import generate_suggested_reply



load_dotenv()

# ============================
# WhatsApp-specific wrapper
# ============================

def generate_whatsapp_reply(user_text, user_id=None):
    """
    Simplified wrapper for WhatsApp integration.
    """

    # Basic principles we always want applied in WhatsApp context
    default_principles = (
        "1. Focus on curiosity, not persuasion.\n"
        "2. Keep it natural and personal.\n"
        "3. Invite dialogue with soft open-ended questions.\n"
        "4. Avoid sounding like a pitch or sales script.\n"
        "5. Be warm, human and conversational."
    )

    # Since we don't have screenshot + draft separation in WhatsApp,
    # we simply use user_text for both inputs
    screenshot_text = user_text
    user_draft = user_text

    # No external document or huddle context yet — can be expanded later
    huddle_context_str = "No prior huddles found."
    doc_context_str = "No relevant documents found."

    reply = generate_suggested_reply(
        screenshot_text,
        user_draft,
        default_principles,
        model_name=None,  # Uses default model from your .env or suggestor
        huddle_context_str=huddle_context_str,
        doc_context_str=doc_context_str
    )

    return reply

# ============================
# Main entry point for webhook
# ============================

def huddle_generate_reply(user_id, message_text):
    """
    Entry point called by webhook.py.
    """
    reply = generate_whatsapp_reply(message_text, user_id)
    return reply
