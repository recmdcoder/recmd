import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import anthropic
import requests
import streamlit as st

logger = logging.getLogger(__name__)


# --- Claude API ---

def build_prompt(moods, genres, time_available, content_type, decade,
                 recent_favorites, preferred_actors, extra_notes,
                 underrated=False, excluded_titles=None):
    """Build the Claude API prompt from user preferences."""
    genre_text = ", ".join(genres) if "No Preference" not in genres else "any genre"
    decade_text = ", ".join(decade) if "No preference" not in decade else "any era"

    # Build a natural-language mood phrase from selected moods
    clean_moods = [m.split(" ", 1)[1] if " " in m else m for m in moods]
    if len(clean_moods) == 1:
        mood_text = f"The user is feeling {clean_moods[0].lower()}"
    elif len(clean_moods) == 2:
        mood_text = f"The user is feeling {clean_moods[0].lower()} and {clean_moods[1].lower()}"
    else:
        mood_text = ("The user is feeling "
                     + ", ".join(m.lower() for m in clean_moods[:-1])
                     + f", and {clean_moods[-1].lower()}")

    underrated_text = (
        "ON — The user wants underrated, under-the-radar, or lesser-known picks. "
        "Avoid mainstream blockbusters and widely popular titles. Prioritize hidden gems, "
        "cult favorites, critically overlooked films/shows, indie productions, or international "
        "titles that deserve more attention. Every recommendation should be something most "
        "people haven't seen."
        if underrated
        else "Off — a mix of popular and lesser-known picks is fine"
    )

    prompt = f"""You are recommended:, an expert movie and TV show recommendation engine. Based on the user's preferences below, suggest exactly 5 personalized recommendations.

USER PREFERENCES:
- Current mood: {mood_text}
- Preferred genres: {genre_text}
- Time available: {time_available}
- Content type: {content_type}
- Era preference: {decade_text}
- Recently enjoyed: {recent_favorites if recent_favorites else "Not specified"}
- Preferred actors: {preferred_actors if preferred_actors else "No preference"}
- Additional notes: {extra_notes if extra_notes else "None"}
- Hidden gems mode: {underrated_text}

IMPORTANT: If the user listed movies/shows they recently enjoyed, use those as strong signals for taste and recommend similar quality, tone, or style. If they listed preferred actors, prioritize films/shows featuring those actors where possible.

HANDLING IMPOSSIBLE COMBINATIONS: If the user's exact combination of preferences is too narrow to find good matches (e.g., a specific actor in a specific genre with a very short runtime), be honest about it. Still recommend 3 things, but mark them as not being exact matches and explain in "why_it_fits" which preferences you relaxed and why the suggestion is still worth watching.

CRITICAL: Never claim that an actor, director, or creator "hasn't released anything" since a certain year or has a limited filmography. Your training data may be incomplete or outdated. Just recommend what you know without making claims about what does or doesn't exist. Never set no_exact_match to true solely because you think someone hasn't been active recently — just recommend their best work that fits the preferences.

Respond with ONLY a valid JSON object. No markdown, no explanation, no code fences — just the raw JSON.

The JSON object must have these fields:
- "no_exact_match": boolean — true if the exact combination of preferences was too narrow and you had to relax some criteria, false if all recommendations fit the preferences well
- "no_match_reason": string or null — if no_exact_match is true, a short friendly explanation of why (e.g., "There aren't really any short comedy films starring Daniel Craig, but here are some close picks you might enjoy"). null if no_exact_match is false
- "recommendations": an array of exactly 5 objects, each with:
  - "title": the title of the movie or TV show (string)
  - "year": the release year (integer)
  - "type": either "Movie" or "TV Show" (string)
  - "runtime": approximate runtime as a human-readable string (e.g., "2h 15m" or "4 seasons, ~50m/episode")
  - "why_it_fits": a 2-3 sentence explanation connecting to the user's mood and preferences. If no_exact_match is true, explain which preference was relaxed and why this is still a great pick
  - "vibe_check": one sentence setting expectations (e.g., "Expect to cry in the best way")

Keep the tone warm, conversational, and enthusiastic — like a knowledgeable friend who loves recommending things. Avoid spoilers.

If you cannot find 5 more genuinely fitting recommendations that haven't been excluded, respond with NONE instead of suggesting titles that don't match well."""

    if excluded_titles:
        exclusion_list = ", ".join(excluded_titles)
        prompt += f"\n\nDo not suggest any of the following (already recommended): {exclusion_list}."

    return prompt


def get_recommendations(prompt):
    """Call the Claude API and return parsed recommendations, or None if exhausted."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text.strip()

    if raw_text.upper() == "NONE":
        return None

    # Strip markdown code fences if Claude wraps the JSON despite instructions
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = lines[1:]  # remove opening ```json or ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_text = "\n".join(lines)

    data = json.loads(raw_text)

    # Support both formats: bare array (legacy) or object with recommendations key
    if isinstance(data, list):
        return {"no_exact_match": False, "no_match_reason": None, "recommendations": data}
    return data


# --- TMDB API ---

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tmdb_info(title, year, content_type, country_code="US"):
    """Search TMDB for a movie/TV show and return poster URL, providers, rating, and trailer."""
    api_key = os.getenv("TMDB_API_KEY")
    result = {"poster_url": None, "providers": [], "tmdb_link": None, "rating": None, "trailer_url": None}
    if not api_key:
        return result

    if content_type == "TV Show":
        search_url = "https://api.themoviedb.org/3/search/tv"
        search_params = {"api_key": api_key, "query": title, "first_air_date_year": year}
        media_type = "tv"
    else:
        search_url = "https://api.themoviedb.org/3/search/movie"
        search_params = {"api_key": api_key, "query": title, "year": year}
        media_type = "movie"

    try:
        resp = requests.get(search_url, params=search_params, timeout=5)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return result

        item = results[0]
        tmdb_id = item["id"]

        # Poster
        if item.get("poster_path"):
            result["poster_url"] = f"https://image.tmdb.org/t/p/w500{item['poster_path']}"

        # TMDB link
        result["tmdb_link"] = f"https://www.themoviedb.org/{media_type}/{tmdb_id}"

        # Rating
        vote = item.get("vote_average")
        if vote and vote > 0:
            result["rating"] = round(vote, 1)

        # Watch providers
        prov_resp = requests.get(
            f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers",
            params={"api_key": api_key}, timeout=5,
        )
        prov_resp.raise_for_status()
        country_data = prov_resp.json().get("results", {}).get(country_code, {})
        result["providers"] = [p["provider_name"] for p in country_data.get("flatrate", [])]

        # Trailer
        vid_resp = requests.get(
            f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/videos",
            params={"api_key": api_key}, timeout=5,
        )
        vid_resp.raise_for_status()
        videos = vid_resp.json().get("results", [])

        for video in videos:
            if video.get("site") == "YouTube" and video.get("type") == "Trailer":
                result["trailer_url"] = f"https://www.youtube.com/watch?v={video['key']}"
                break
        if not result["trailer_url"]:
            for video in videos:
                if video.get("site") == "YouTube" and video.get("type") == "Teaser":
                    result["trailer_url"] = f"https://www.youtube.com/watch?v={video['key']}"
                    break

    except (requests.RequestException, KeyError, IndexError) as e:
        logger.warning(f"TMDB fetch failed for '{title}' ({year}): {e}")

    return result


def fetch_all_tmdb_info(recommendations, country_code="US"):
    """Fetch TMDB info for all recommendations concurrently."""
    def _fetch(rec):
        return fetch_tmdb_info(rec["title"], rec["year"], rec["type"], country_code)

    with ThreadPoolExecutor(max_workers=5) as executor:
        return list(executor.map(_fetch, recommendations))


# --- Email (Formspree) ---

def submit_email(email):
    """Submit an email to Formspree. Returns (success, error_message)."""
    formspree_url = os.getenv("FORMSPREE_ENDPOINT")
    if not formspree_url:
        return False, "Email capture is not configured yet."

    try:
        resp = requests.post(
            formspree_url,
            json={"email": email},
            headers={"Accept": "application/json"},
            timeout=5,
        )
        if resp.ok:
            return True, None
        return False, "Something went wrong. Please try again."
    except requests.RequestException:
        return False, "Could not submit. Please try again later."
