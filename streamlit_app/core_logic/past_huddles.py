# logic/past_huddles.py

import streamlit as st
from memory import load_all_interactions

def get_category(huddle):
    text = (huddle.get('screenshot_text', '') + ' ' + 
            huddle.get('user_draft', '') + ' ' + 
            huddle.get('ai_suggested', '')).lower()

    if any(keyword in text for keyword in ["what's the business", "what is it", "what do you do", "side hustle", "what is this"]):
        return "💼 What's the business?"
    if any(keyword in text for keyword in ["property", "shares", "trading", "dropshipping", "like...?"]):
        return "🤔 Is it like...?"
    if any(keyword in text for keyword in ["make money", "how much", "charge", "income", "revenue", "profit"]):
        return "💰 How do you make money?"
    if any(keyword in text for keyword in ["mentor", "mentors", "mentorship", "coach", "coaching"]):
        return "👥 Who are your mentors?"
    if any(keyword in text for keyword in ["get connected", "get involved", "how did you get in", "how do i join", "selection process"]):
        return "🤝 How do I get involved?"
    if any(keyword in text for keyword in ["pyramid scheme", "ponzi"]):
        return "⚠️ Is it a pyramid scheme?"
    if any(keyword in text for keyword in ["skincare", "energy drinks", "makeup", "products", "selling", "sell"]):
        return "💄 Product-related questions"
    return "💬 General"

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

        categorized_huddles = {
            "💼 What's the business?": [],
            "🤔 Is it like...?": [],
            "💰 How do you make money?": [],
            "👥 Who are your mentors?": [],
            "🤝 How do I get involved?": [],
            "⚠️ Is it a pyramid scheme?": [],
            "💄 Product-related questions": [],
            "💬 General": []
        }

        for huddle in filtered_huddles:
            category = get_category(huddle)
            categorized_huddles[category].append(huddle)

        for category, huddles in categorized_huddles.items():
            if huddles:
                with st.expander(f"{category} ({len(huddles)})"):
                    for huddle_item in huddles:
                        with st.container(border=True):
                            st.markdown(f"**Huddle {len(sorted_huddles_list) - sorted_huddles_list.index(huddle_item)}**")
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
