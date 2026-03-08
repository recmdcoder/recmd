import logging
import os
import time
from datetime import datetime

import anthropic
import json
import streamlit as st

from api import build_prompt, get_recommendations, fetch_all_tmdb_info, submit_email
from config import COUNTRY_OPTIONS, REQUEST_COOLDOWN_SECONDS
from state import save_to_history

logger = logging.getLogger(__name__)


def _fetch_and_process(prompt, country_code, is_retry=False):
    """Shared logic: call Claude API, fetch TMDB data, update session state.

    Returns True on success, False on exhaustion or error.
    """
    try:
        st.session_state.last_request_time = time.time()
        result = get_recommendations(prompt)

        if result is None:
            st.session_state.exhausted = True
            if is_retry:
                st.rerun()
            else:
                st.session_state.recommendations = None
                st.session_state.tmdb_infos = []
            return False

        recs = result.get("recommendations", [])
        tmdb_infos = fetch_all_tmdb_info(recs, country_code)

        save_to_history()

        if is_retry:
            st.session_state.excluded_titles.extend(r["title"] for r in recs)
        else:
            st.session_state.excluded_titles = [r["title"] for r in recs]

        st.session_state.recommendations = result
        st.session_state.tmdb_infos = tmdb_infos
        st.session_state.last_timestamp = datetime.now().strftime("%H:%M")

        if is_retry:
            st.rerun()

        return True

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        st.error("Our recommendation engine is temporarily unavailable. Please try again.")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        st.error("We received an unexpected response. Please try again.")
        return False


def handle_submission(moods, genres, time_available, content_type, decade,
                      recent_favorites, preferred_actors, extra_notes,
                      underrated, country_name):
    """Handle the main preferences form submission."""
    if not moods:
        st.error("Please select at least one mood before getting recommendations.")
        return
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("API key not found. Make sure your `.env` file has `ANTHROPIC_API_KEY` set.")
        return
    if time.time() - st.session_state.last_request_time < REQUEST_COOLDOWN_SECONDS:
        st.warning("Please wait a few seconds between requests.")
        return

    # Fresh search: reset state
    st.session_state.excluded_titles = []
    st.session_state.exhausted = False

    country_code = COUNTRY_OPTIONS[country_name]
    prompt = build_prompt(moods, genres, time_available, content_type, decade,
                          recent_favorites, preferred_actors, extra_notes, underrated)

    with st.spinner("Finding the perfect picks for you..."):
        success = _fetch_and_process(prompt, country_code, is_retry=False)

    if success:
        st.session_state.country_name = country_name
        st.session_state.last_mood = ", ".join(moods)
        st.session_state.last_genres = list(genres)

    # Save form inputs for re-rolls regardless of outcome
    st.session_state.last_form_inputs = {
        "moods": list(moods),
        "genres": list(genres),
        "time_available": time_available,
        "content_type": content_type,
        "decade": list(decade),
        "recent_favorites": recent_favorites,
        "preferred_actors": preferred_actors,
        "extra_notes": extra_notes,
        "underrated": underrated,
        "country_name": country_name,
    }


def handle_try_again():
    """Handle the 'Try Again' button: re-roll with exclusions."""
    inputs = st.session_state.last_form_inputs
    if not inputs:
        st.warning("Please get your first recommendations using the form above.")
        return
    if time.time() - st.session_state.last_request_time < REQUEST_COOLDOWN_SECONDS:
        st.warning("Please wait a few seconds between requests.")
        return

    country_code = COUNTRY_OPTIONS[inputs["country_name"]]
    prompt = build_prompt(
        inputs["moods"], inputs["genres"], inputs["time_available"],
        inputs["content_type"], inputs["decade"], inputs["recent_favorites"],
        inputs["preferred_actors"], inputs["extra_notes"], inputs["underrated"],
        excluded_titles=list(st.session_state.excluded_titles),
    )

    with st.spinner("Finding fresh picks for you..."):
        _fetch_and_process(prompt, country_code, is_retry=True)


def handle_email_submission(email):
    """Handle the email capture form submission."""
    if not email or "@" not in email:
        st.warning("Please enter a valid email address.")
        return

    success, error_msg = submit_email(email)
    if success:
        st.session_state.email_submitted = True
        st.rerun()
    else:
        st.error(error_msg)
