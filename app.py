import streamlit as st
import anthropic
import requests
import json
import logging
import os
import time
from html import escape
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# --- Page Config ---
st.set_page_config(
    page_title="recommended: — What Should You Watch?",
    page_icon="🎬",
    layout="centered",
)

# --- Custom CSS ---
st.markdown("""
<style>
    .stApp {
        max-width: 720px;
        margin: 0 auto;
    }
    div[data-testid="stMarkdownContainer"] h1 {
        text-align: center;
    }
    div[data-testid="stMarkdownContainer"] h3 {
        text-align: center;
        font-weight: 400;
        color: #888;
    }
    /* Polished recommendation cards */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
        overflow: hidden;
    }
    .provider-pill {
        display: inline-block;
        background: #3a3a4a;
        color: #e0e0e0;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.78rem;
        margin: 2px 4px 2px 0;
        white-space: nowrap;
    }
    .provider-section {
        margin-top: 8px;
    }
    .no-providers {
        color: #888;
        font-size: 0.82rem;
        font-style: italic;
        margin-top: 8px;
    }
    .rating-badge {
        display: inline-block;
        background: #1a1a2e;
        border: 1px solid #e6c619;
        color: #e6c619;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-left: 6px;
        vertical-align: middle;
    }
    .trailer-link {
        display: inline-block;
        margin-top: 8px;
        font-size: 0.85rem;
    }
    .trailer-link a {
        color: #ff4b4b;
        text-decoration: none;
        font-weight: 500;
    }
    .trailer-link a:hover {
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)

# --- Constants ---
MOOD_OPTIONS = [
    "😊 Happy / Upbeat",
    "😢 Sad / Emotional",
    "😰 Stressed / Need to Unwind",
    "🤔 Curious / Want to Learn",
    "😂 Want to Laugh",
    "😒 Bored / Need Excitement",
    "🥰 Romantic",
    "😱 Want to Be Scared",
    "🤷 I Don't Know / Surprise Me",
]

GENRE_OPTIONS = [
    "Action", "Comedy", "Goofball Comedy", "Drama", "Sci-Fi", "Horror",
    "Romance", "Thriller", "Documentary", "Animation", "Fantasy",
    "Mystery", "Crime", "Western", "Whodunnit", "Film Noir",
    "Oscar-Winning", "Female-Led", "No Preference"
]


TIME_OPTIONS = [
    "Under 30 minutes (episodes or short films)",
    "Under 1 hour (TV show episodes or comedy specials)",
    "Under 90 minutes (shorter movies)",
    "90 minutes – 2h30 (movies or mini-series)",
    "Over 2h30 (long movies, series, or mini-series)",
    "I have all day",
]

CONTENT_TYPE_OPTIONS = ["Movies only", "TV Shows only", "Both"]

DECADE_OPTIONS = [
    "No preference",
    "Old Hollywood (1920s-1950s)",
    "Classic (before 1980)",
    "80s & 90s",
    "2000s & 2010s",
    "Recent (2020+)",
]

COUNTRY_OPTIONS = {
    "United States": "US",
    "United Kingdom": "GB",
    "Germany": "DE",
    "Austria": "AT",
    "Switzerland": "CH",
    "France": "FR",
    "Netherlands": "NL",
    "Belgium": "BE",
    "Spain": "ES",
    "Italy": "IT",
    "Portugal": "PT",
    "Ireland": "IE",
    "Sweden": "SE",
    "Norway": "NO",
    "Denmark": "DK",
    "Finland": "FI",
    "Canada": "CA",
    "Australia": "AU",
    "New Zealand": "NZ",
    "Mexico": "MX",
    "Brazil": "BR",
    "India": "IN",
    "Japan": "JP",
    "South Korea": "KR",
}

# --- Helper: Build prompt ---
def build_prompt(mood, genres, time_available, content_type, decade, recent_favorites, preferred_actors, extra_notes):
    genre_text = ", ".join(genres) if "No Preference" not in genres else "any genre"
    decade_text = ", ".join(decade) if "No preference" not in decade else "any era"

    prompt = f"""You are recommended:, an expert movie and TV show recommendation engine. Based on the user's preferences below, suggest exactly 3 personalized recommendations.

USER PREFERENCES:
- Current mood: {mood}
- Preferred genres: {genre_text}
- Time available: {time_available}
- Content type: {content_type}
- Era preference: {decade_text}
- Recently enjoyed: {recent_favorites if recent_favorites else "Not specified"}
- Preferred actors: {preferred_actors if preferred_actors else "No preference"}
- Additional notes: {extra_notes if extra_notes else "None"}

IMPORTANT: If the user listed movies/shows they recently enjoyed, use those as strong signals for taste and recommend similar quality, tone, or style. If they listed preferred actors, prioritize films/shows featuring those actors where possible.

HANDLING IMPOSSIBLE COMBINATIONS: If the user's exact combination of preferences is too narrow to find good matches (e.g., a specific actor in a specific genre with a very short runtime), be honest about it. Still recommend 3 things, but mark them as not being exact matches and explain in "why_it_fits" which preferences you relaxed and why the suggestion is still worth watching.

CRITICAL: Never claim that an actor, director, or creator "hasn't released anything" since a certain year or has a limited filmography. Your training data may be incomplete or outdated. Just recommend what you know without making claims about what does or doesn't exist. Never set no_exact_match to true solely because you think someone hasn't been active recently — just recommend their best work that fits the preferences.

Respond with ONLY a valid JSON object. No markdown, no explanation, no code fences — just the raw JSON.

The JSON object must have these fields:
- "no_exact_match": boolean — true if the exact combination of preferences was too narrow and you had to relax some criteria, false if all recommendations fit the preferences well
- "no_match_reason": string or null — if no_exact_match is true, a short friendly explanation of why (e.g., "There aren't really any short comedy films starring Daniel Craig, but here are some close picks you might enjoy"). null if no_exact_match is false
- "recommendations": an array of exactly 3 objects, each with:
  - "title": the title of the movie or TV show (string)
  - "year": the release year (integer)
  - "type": either "Movie" or "TV Show" (string)
  - "runtime": approximate runtime as a human-readable string (e.g., "2h 15m" or "4 seasons, ~50m/episode")
  - "why_it_fits": a 2-3 sentence explanation connecting to the user's mood and preferences. If no_exact_match is true, explain which preference was relaxed and why this is still a great pick
  - "vibe_check": one sentence setting expectations (e.g., "Expect to cry in the best way")

Keep the tone warm, conversational, and enthusiastic — like a knowledgeable friend who loves recommending things. Avoid spoilers."""

    return prompt


# --- Helper: Get recommendations ---
def get_recommendations(prompt):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    raw_text = message.content[0].text.strip()

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


# --- Helper: Fetch TMDB info (poster + watch providers) ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tmdb_info(title, year, content_type, country_code="US"):
    """Search TMDB for a movie/TV show and return poster URL, providers, rating, and trailer."""
    api_key = os.getenv("TMDB_API_KEY")
    result = {"poster_url": None, "providers": [], "tmdb_link": None, "rating": None, "trailer_url": None}
    if not api_key:
        return result

    # 1. Search for the title
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

        # 2. Fetch watch providers
        provider_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers"
        provider_params = {"api_key": api_key}
        prov_resp = requests.get(provider_url, params=provider_params, timeout=5)
        prov_resp.raise_for_status()
        prov_data = prov_resp.json().get("results", {})

        country_data = prov_data.get(country_code, {})
        flatrate = country_data.get("flatrate", [])
        result["providers"] = [p["provider_name"] for p in flatrate]

        # 3. Fetch trailer
        videos_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/videos"
        videos_params = {"api_key": api_key}
        vid_resp = requests.get(videos_url, params=videos_params, timeout=5)
        vid_resp.raise_for_status()
        videos = vid_resp.json().get("results", [])

        # Prefer official YouTube trailers, fall back to teasers
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

    with ThreadPoolExecutor(max_workers=3) as executor:
        return list(executor.map(_fetch, recommendations))


# --- Helper: Render recommendation card ---
def render_recommendation_card(rec, tmdb_info, country_name="United States"):
    """Render a single recommendation as a card with poster, text, and providers."""
    with st.container(border=True):
        col_poster, col_text = st.columns([1, 2])

        with col_poster:
            if tmdb_info["poster_url"]:
                st.image(tmdb_info["poster_url"], use_container_width=True)
            else:
                st.markdown(
                    "<div style='background:#262730;border-radius:12px;height:270px;"
                    "display:flex;align-items:center;justify-content:center;"
                    "color:#888;font-size:2.5rem;'>🎬</div>",
                    unsafe_allow_html=True,
                )

        with col_text:
            # Title + rating on the same line (escape untrusted data to prevent XSS)
            title_text = escape(rec['title'])
            if tmdb_info["tmdb_link"]:
                tmdb_link = escape(tmdb_info["tmdb_link"], quote=True)
                title_html = f'<a href="{tmdb_link}" target="_blank" style="color:inherit;text-decoration:none;font-weight:700;">{title_text}</a>'
            else:
                title_html = f'<strong>{title_text}</strong>'

            rating_html = ""
            if tmdb_info.get("rating"):
                rating_html = f' <span class="rating-badge">★ {escape(str(tmdb_info["rating"]))}</span>'

            year_text = escape(str(rec["year"]))
            st.markdown(
                f'{title_html} ({year_text}){rating_html}',
                unsafe_allow_html=True,
            )
            st.caption(f"{escape(rec['type'])}  •  {escape(rec['runtime'])}")
            st.markdown(rec["why_it_fits"])
            st.markdown(f"*{rec['vibe_check']}*")

            # Streaming providers (escape provider names from TMDB)
            if tmdb_info["providers"]:
                pills_html = "".join(
                    f'<span class="provider-pill">{escape(p)}</span>' for p in tmdb_info["providers"]
                )
                st.markdown(
                    f'<div class="provider-section"><strong>Where to watch:</strong><br>{pills_html}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="no-providers">Not available for streaming in {escape(country_name)}</div>',
                    unsafe_allow_html=True,
                )

            # Trailer link (only allow YouTube URLs to prevent javascript: injection)
            trailer_url = tmdb_info.get("trailer_url", "")
            if trailer_url and trailer_url.startswith("https://www.youtube.com/"):
                st.markdown(
                    f'<div class="trailer-link"><a href="{escape(trailer_url, quote=True)}" target="_blank">▶ Watch Trailer</a></div>',
                    unsafe_allow_html=True,
                )


# --- App UI ---
st.markdown("# 🎬 recommended:")
st.markdown("### Tell us your vibe. We'll tell you what to watch.")
st.divider()

# Initialize session state
if "recommendations" not in st.session_state:
    st.session_state.recommendations = None
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "history" not in st.session_state:
    st.session_state.history = []
if "tmdb_infos" not in st.session_state:
    st.session_state.tmdb_infos = []
if "country_name" not in st.session_state:
    st.session_state.country_name = "United States"
if "last_request_time" not in st.session_state:
    st.session_state.last_request_time = 0.0

# --- Questionnaire ---
with st.form("preferences_form"):
    st.subheader("What's your mood right now?")
    mood = st.radio(
        "Pick the closest match:",
        MOOD_OPTIONS,
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

    submitted = st.form_submit_button("🎯 Get My Recommendations", use_container_width=True)

# --- Handle submission ---
REQUEST_COOLDOWN_SECONDS = 10

if submitted:
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("API key not found. Make sure your `.env` file has `ANTHROPIC_API_KEY` set.")
    elif time.time() - st.session_state.last_request_time < REQUEST_COOLDOWN_SECONDS:
        st.warning("Please wait a few seconds between requests.")
    else:
        country_code = COUNTRY_OPTIONS[country_name]
        prompt = build_prompt(mood, genres, time_available, content_type, decade, recent_favorites, preferred_actors, extra_notes)
        with st.spinner("Finding the perfect picks for you..."):
            try:
                st.session_state.last_request_time = time.time()
                result = get_recommendations(prompt)
                recs = result.get("recommendations", [])
                tmdb_infos = fetch_all_tmdb_info(recs, country_code)

                # Save to history before overwriting (keep last 5)
                if st.session_state.recommendations:
                    old_recs = st.session_state.recommendations.get("recommendations", [])
                    if old_recs:
                        st.session_state.history.append({
                            "mood": st.session_state.get("last_mood", ""),
                            "genres": st.session_state.get("last_genres", []),
                            "recommendations": old_recs,
                            "timestamp": st.session_state.get("last_timestamp", ""),
                        })
                        st.session_state.history = st.session_state.history[-5:]

                st.session_state.recommendations = result
                st.session_state.tmdb_infos = tmdb_infos
                st.session_state.country_name = country_name
                st.session_state.last_mood = mood
                st.session_state.last_genres = list(genres)
                st.session_state.last_timestamp = datetime.now().strftime("%H:%M")
                st.session_state.submitted = True
            except anthropic.APIError as e:
                logger.error(f"Anthropic API error: {e}")
                st.error("Our recommendation engine is temporarily unavailable. Please try again.")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                st.error("We received an unexpected response. Please try again.")

# --- Display results ---
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

    # --- Download button ---
    def build_download_text(recs, tmdb_infos, country_name):
        lines = ["recommended: — Your Recommendations\n", "=" * 40 + "\n"]
        for i, rec in enumerate(recs):
            info = tmdb_infos[i] if i < len(tmdb_infos) else {"providers": [], "rating": None, "trailer_url": None}
            rating_str = f"  •  ★ {info['rating']}/10" if info.get("rating") else ""
            lines.append(f"\n{i + 1}. {rec['title']} ({rec['year']}){rating_str}")
            lines.append(f"   {rec['type']}  •  {rec['runtime']}")
            lines.append(f"   {rec['why_it_fits']}")
            lines.append(f"   Vibe check: {rec['vibe_check']}")
            if info["providers"]:
                lines.append(f"   Where to watch ({country_name}): {', '.join(info['providers'])}")
            else:
                lines.append(f"   Not available for streaming in {country_name}")
            if info.get("trailer_url"):
                lines.append(f"   Trailer: {info['trailer_url']}")
            lines.append("")
        return "\n".join(lines)

    st.download_button(
        label="Save Recommendations",
        data=build_download_text(recs, tmdb_infos, st.session_state.country_name),
        file_name="recommended_picks.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.caption("Not feeling these? Tweak your answers above and try again!")

# --- Recommendation history ---
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
if "email_submitted" not in st.session_state:
    st.session_state.email_submitted = False

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
        formspree_url = os.getenv("FORMSPREE_ENDPOINT")
        if not formspree_url:
            st.error("Email capture is not configured yet.")
        elif not email or "@" not in email:
            st.warning("Please enter a valid email address.")
        else:
            try:
                resp = requests.post(
                    formspree_url,
                    json={"email": email},
                    headers={"Accept": "application/json"},
                    timeout=5,
                )
                if resp.ok:
                    st.session_state.email_submitted = True
                    st.rerun()
                else:
                    st.error("Something went wrong. Please try again.")
            except requests.RequestException:
                st.error("Could not submit. Please try again later.")

# --- Footer ---
st.divider()
st.caption("recommended: v0.1 — Built with Streamlit & Claude | © 2026")
