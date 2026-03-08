import streamlit as st
from dotenv import load_dotenv

from config import (
    MOOD_OPTIONS, GENRE_OPTIONS, TIME_OPTIONS,
    CONTENT_TYPE_OPTIONS, DECADE_OPTIONS, COUNTRY_OPTIONS,
    inject_styles,
)
from state import init_session_state
from components import render_recommendation_card, build_download_text
from handlers import handle_submission, handle_try_again, handle_email_submission

load_dotenv()

# --- Page Config (must be the first Streamlit call) ---
st.set_page_config(
    page_title="recommended: — What Should You Watch?",
    page_icon="🎬",
    layout="centered",
)

inject_styles()
init_session_state()

# --- Header ---
st.markdown("# 🎬 recommended:")
st.markdown("### Tell us your vibe. We'll tell you what to watch.")
st.divider()

# --- Preferences Form ---
with st.form("preferences_form"):
    st.subheader("What's your mood right now?")
    moods = st.multiselect(
        "Pick one or more moods:",
        MOOD_OPTIONS,
        default=[],
        label_visibility="collapsed",
    )

    st.subheader("Any genre preferences?")
    genres = st.multiselect(
        "Select one or more (or 'No Preference'):",
        GENRE_OPTIONS,
        default=["No Preference"],
        label_visibility="collapsed",
    )

    st.subheader("How much time do you have?")
    time_available = st.radio(
        "Pick one:",
        TIME_OPTIONS,
        label_visibility="collapsed",
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Movies or TV?")
        content_type = st.radio(
            "Content type:",
            CONTENT_TYPE_OPTIONS,
            label_visibility="collapsed",
        )
    with col2:
        st.subheader("Era preference?")
        decade = st.multiselect(
            "Select one or more (or 'No preference'):",
            DECADE_OPTIONS,
            default=["No preference"],
            label_visibility="collapsed",
        )

    st.subheader("What have you watched recently that you loved?")
    recent_favorites = st.text_area(
        "Name some movies or TV shows you've enjoyed lately:",
        label_visibility="collapsed",
        placeholder="E.g., The Bear, Knives Out, Severance...",
        max_chars=500,
    )

    st.subheader("Any actors you'd love to see?")
    preferred_actors = st.text_input(
        "Type actor names separated by commas:",
        label_visibility="collapsed",
        placeholder="Optional — e.g., Florence Pugh, Pedro Pascal, Viola Davis",
        max_chars=200,
    )

    st.subheader("Anything else we should know?")
    extra_notes = st.text_area(
        "E.g., 'I just watched Interstellar and loved it' or 'nothing too violent'",
        label_visibility="collapsed",
        placeholder="Optional — but helps us dial it in...",
        max_chars=500,
    )

    st.subheader("Where are you watching from?")
    country_name = st.selectbox(
        "Select your country for streaming availability:",
        list(COUNTRY_OPTIONS.keys()),
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("")  # spacing
    underrated = st.toggle("💎 Show me more underrated / under the radar picks", value=False)

    submitted = st.form_submit_button("🎯 Get My Recommendations", use_container_width=True)

# --- Handle Submission ---
if submitted:
    handle_submission(
        moods, genres, time_available, content_type, decade,
        recent_favorites, preferred_actors, extra_notes,
        underrated, country_name,
    )

# --- Display Results ---
if st.session_state.recommendations and isinstance(st.session_state.recommendations, dict):
    data = st.session_state.recommendations
    recs = data.get("recommendations", [])
    tmdb_infos = st.session_state.tmdb_infos

    st.divider()

    if data.get("no_exact_match") and data.get("no_match_reason"):
        st.warning(data["no_match_reason"])
        st.markdown("## But You Might Like These")
    else:
        st.markdown("## Your Recommendations")

    for i, rec in enumerate(recs):
        info = tmdb_infos[i] if i < len(tmdb_infos) else {"poster_url": None, "providers": [], "tmdb_link": None}
        render_recommendation_card(rec, info, st.session_state.country_name)

    st.download_button(
        label="Save Recommendations",
        data=build_download_text(recs, tmdb_infos, st.session_state.country_name),
        file_name="recommended_picks.txt",
        mime="text/plain",
        use_container_width=True,
    )

    if st.button("🔄 Try Again — Show Me 5 More", use_container_width=True):
        handle_try_again()

    st.caption("Not feeling these? Hit 'Try Again' or tweak your answers above!")

# --- Exhaustion Message ---
if st.session_state.exhausted:
    st.divider()
    st.info("🎬 We've run out of matching recommendations — try adjusting your filters!")

# --- Recommendation History ---
if st.session_state.history:
    with st.expander("Previous Recommendations"):
        for entry in reversed(st.session_state.history):
            mood_label = entry.get("mood", "")
            genres_label = ", ".join(entry.get("genres", []))
            time_label = entry.get("timestamp", "")
            st.markdown(f"**{mood_label}** • {genres_label} {'(' + time_label + ')' if time_label else ''}")
            for rec in entry.get("recommendations", []):
                st.markdown(f"- {rec['title']} ({rec['year']})")
            st.divider()

# --- Email Capture ---
st.divider()
if st.session_state.email_submitted:
    st.success("You're on the list! We'll let you know when something new drops.")
else:
    st.subheader("Stay in the loop")
    st.markdown("Get notified when we launch new features and the big redesign.")
    with st.form("email_form"):
        email = st.text_input(
            "Your email:",
            label_visibility="collapsed",
            placeholder="you@example.com",
            max_chars=254,
        )
        email_submitted = st.form_submit_button("Notify Me", use_container_width=True)

    if email_submitted:
        handle_email_submission(email)

# --- Footer ---
st.divider()
st.caption("recommended: v0.1 — Built with Streamlit & Claude | © 2026")
