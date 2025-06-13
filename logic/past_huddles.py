# logic/past_huddles.py

import streamlit as st
from memory import load_all_interactions

def past_huddles_tab():
    st.subheader("📖 Past Huddle Interactions")
    try:
        huddles_data = load_all_interactions()
        if not huddles_data or not isinstance(huddles_data, list):
            huddles_data = []
    except Exception as e:
        st.error(f"Failed to load huddles from Notion: {e}")
        huddles_data = []

    if not huddles_data:
        st.info("No huddles saved yet or unable to load them.")
    else:
        search_query = st.text_input("🔍 Search Huddles", placeholder="Search by keyword...")
        
        filter_options = ["All", "Tone Adjusted", "User Final Version"]
        reply_type_filter = st.selectbox("Filter by Reply Type", filter_options)

        try:
            valid_huddles = [h for h in huddles_data if isinstance(h, dict) and "timestamp" in h]
            sorted_huddles_list = sorted(valid_huddles, key=lambda h: h.get("timestamp", ""), reverse=True)
        except Exception as e:
            st.error(f"Error sorting huddles: {e}. Displaying unsorted.")
            sorted_huddles_list = [h for h in huddles_data if isinstance(h, dict)]

        filtered_huddles = sorted_huddles_list
        if search_query:
            query = search_query.lower()
            filtered_huddles = [
                h for h in filtered_huddles if
                query in h.get('screenshot_text', '').lower() or
                query in h.get('user_draft', '').lower() or
                query in h.get('ai_suggested', '').lower() or
                query in h.get('ai_adjusted_reply', '').lower() or
                query in h.get('user_final', '').lower()
            ]

        if reply_type_filter == "Tone Adjusted":
            filtered_huddles = [h for h in filtered_huddles if h.get('ai_adjusted_reply')]
        elif reply_type_filter == "User Final Version":
            filtered_huddles = [h for h in filtered_huddles if h.get('user_final')]

        if not filtered_huddles:
            st.info("No huddles match your search criteria.")
            return

        st.markdown(f"**Displaying {len(filtered_huddles)} of {len(sorted_huddles_list)} huddles.**")

        for idx, huddle_item in enumerate(filtered_huddles):
            expander_title = f"Huddle {len(sorted_huddles_list) - sorted_huddles_list.index(huddle_item)}"
            
            with st.expander(expander_title):
                st.markdown("**🖼 Screenshot Text**")
                st.write(huddle_item.get('screenshot_text', '_Not available_'))
                st.markdown("**📝 User Draft**")
                st.write(huddle_item.get('user_draft', '_Not available_'))
                st.markdown("**🤖 AI Suggested Reply (Original)**")
                st.write(huddle_item.get('ai_suggested', '_Not available_'))

                if huddle_item.get('ai_adjusted_reply'):
                    st.markdown("**🗣️ Tone Adjusted Reply**")
                    st.write(huddle_item.get('ai_adjusted_reply'))
                elif huddle_item.get('user_final'):
                    st.markdown("**🧠 User's Final Version (if different from AI)**")
                    st.write(huddle_item.get('user_final'))
