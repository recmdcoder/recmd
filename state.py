import streamlit as st

SESSION_DEFAULTS = {
    "recommendations": None,
    "history": [],
    "tmdb_infos": [],
    "country_name": "United States",
    "last_request_time": 0.0,
    "excluded_titles": [],
    "last_form_inputs": {},
    "exhausted": False,
    "email_submitted": False,
    "last_mood": "",
    "last_genres": [],
    "last_timestamp": "",
}


def init_session_state():
    """Initialize all session state keys with defaults (idempotent)."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def save_to_history():
    """Push current recommendations into history (max 5 entries), if any exist."""
    if not st.session_state.recommendations:
        return
    old_recs = st.session_state.recommendations.get("recommendations", [])
    if old_recs:
        st.session_state.history.append({
            "mood": st.session_state.last_mood,
            "genres": st.session_state.last_genres,
            "recommendations": old_recs,
            "timestamp": st.session_state.last_timestamp,
        })
        st.session_state.history = st.session_state.history[-5:]
