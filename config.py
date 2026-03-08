import streamlit as st

# --- Form Options ---

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
    "Oscar-Winning", "Female-Led", "No Preference",
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

REQUEST_COOLDOWN_SECONDS = 10

# --- CSS ---

APP_CSS = """
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
"""


def inject_styles():
    st.markdown(APP_CSS, unsafe_allow_html=True)
