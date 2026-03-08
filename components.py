from html import escape

import streamlit as st


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
            # Title + rating
            title_text = escape(rec["title"])
            if tmdb_info["tmdb_link"]:
                tmdb_link = escape(tmdb_info["tmdb_link"], quote=True)
                title_html = (
                    f'<a href="{tmdb_link}" target="_blank" '
                    f'style="color:inherit;text-decoration:none;font-weight:700;">'
                    f'{title_text}</a>'
                )
            else:
                title_html = f"<strong>{title_text}</strong>"

            rating_html = ""
            if tmdb_info.get("rating"):
                rating_html = f' <span class="rating-badge">★ {escape(str(tmdb_info["rating"]))}</span>'

            year_text = escape(str(rec["year"]))
            st.markdown(
                f"{title_html} ({year_text}){rating_html}",
                unsafe_allow_html=True,
            )
            st.caption(f"{escape(rec['type'])}  •  {escape(rec['runtime'])}")
            st.markdown(rec["why_it_fits"])
            st.markdown(f"*{rec['vibe_check']}*")

            # Streaming providers
            if tmdb_info["providers"]:
                pills_html = "".join(
                    f'<span class="provider-pill">{escape(p)}</span>'
                    for p in tmdb_info["providers"]
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

            # Trailer link (only allow YouTube URLs)
            trailer_url = tmdb_info.get("trailer_url", "")
            if trailer_url and trailer_url.startswith("https://www.youtube.com/"):
                st.markdown(
                    f'<div class="trailer-link">'
                    f'<a href="{escape(trailer_url, quote=True)}" target="_blank">▶ Watch Trailer</a>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


def build_download_text(recs, tmdb_infos, country_name):
    """Build a plain-text summary of recommendations for download."""
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
