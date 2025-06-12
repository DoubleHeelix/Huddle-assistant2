# logic/past_huddles.py

import streamlit as st
from memory import load_all_interactions

def past_huddles_tab():
    st.subheader("📖 Past Huddle Interactions")
    try:
        huddles_data = load_all_interactions()
        # Guarantee it's a list (even if None or something else is returned)
        if not huddles_data or not isinstance(huddles_data, list):
            huddles_data = []
    except Exception as e:
        st.error(f"Failed to load huddles from Notion: {e}")
        huddles_data = []

    if not huddles_data:
        st.info("No huddles saved yet or unable to load them.")
    else:
        try:
            valid_huddles = [h for h in huddles_data if isinstance(h, dict) and "timestamp" in h]
            sorted_huddles_list = sorted(valid_huddles, key=lambda h: h.get("timestamp", ""), reverse=True)
        except Exception as e:
            st.error(f"Error sorting huddles: {e}. Displaying unsorted.")
            sorted_huddles_list = [h for h in huddles_data if isinstance(h, dict)]

        for idx, huddle_item in enumerate(sorted_huddles_list):
            timestamp_str = huddle_item.get('timestamp', f"Unknown Timestamp - Item {len(sorted_huddles_list) - idx}")
            expander_title = f"Huddle {len(sorted_huddles_list) - idx}: {timestamp_str}"
            
            with st.expander(expander_title):
                st.markdown("**🖼 Screenshot Text**")
                st.write(huddle_item.get('screenshot_text', '_Not available_'))
                st.markdown("**📝 User Draft**")
                st.write(huddle_item.get('user_draft', '_Not available_'))
                st.markdown("**🤖 AI Suggested Reply (Original)**")
                st.write(huddle_item.get('ai_suggested', '_Not available_'))

                # Tone adjusted reply or user's final message
                if huddle_item.get('ai_adjusted_reply'):
                    st.markdown("**🗣️ Tone Adjusted Reply**")
                    st.write(huddle_item.get('ai_adjusted_reply'))
                elif huddle_item.get('user_final'):
                    st.markdown("**🧠 User's Final Version (if different from AI)**")
                    st.write(huddle_item.get('user_final'))
