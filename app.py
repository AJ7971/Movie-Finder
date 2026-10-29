import importlib
import inspect
import os
from pathlib import Path
from html import escape

import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - optional dependency
    pass

import enrich_ratings
import movie_agent


if "sort_by" not in inspect.signature(movie_agent.MovieAgent.respond).parameters:
    movie_agent = importlib.reload(movie_agent)

CATALOG_PATH = movie_agent.CATALOG_PATH
MovieAgent = movie_agent.MovieAgent
load_catalog = movie_agent.load_catalog


WIKIDATA_CATALOG_PATH = Path(__file__).parent / "data" / "wikidata_movies.csv"


st.set_page_config(page_title="Reel Guide", page_icon="🎬", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');
    :root { --ink: #18211e; --paper: #f3f1e9; --accent: #e35b38; --green: #527a68; }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
    .stApp { background: var(--paper); }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1240px; padding-top: 1rem; }
    .hero {
      min-height: 250px; display: flex; align-items: end; padding: 30px 38px;
      color: #fff; border-radius: 5px; overflow: hidden;
      background-image: linear-gradient(90deg, rgba(18,25,22,.91), rgba(18,25,22,.2)),
        url('https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=1800&q=85');
      background-size: cover; background-position: center 56%;
    }
    .hero h1 { font: 700 56px/0.98 'Barlow Condensed', sans-serif; margin: 6px 0 8px; color: white; letter-spacing: 0; }
    .hero p { max-width: 550px; margin: 0; font-size: 15px; color: #e4e8df; }
    .eyebrow { color: #ef9b77; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.4px; }
    h2, h3 { font-family: 'Barlow Condensed', sans-serif !important; letter-spacing: 0 !important; }
    .movie-poster {
      height: 150px; padding: 12px; border-radius: 3px; display: flex; align-items: end;
      color: white; font: 600 20px/1.02 'Barlow Condensed', sans-serif;
      background: linear-gradient(155deg, #72907e, #253d39 62%, #17211f);
    }
    .movie-meta { color: #56615a; font-size: 13px; line-height: 1.7; }
    .movie-reason { font-size: 13px; line-height: 1.55; min-height: 42px; }
    .tag { color: #315644; font-size: 11px; font-weight: 700; text-transform: uppercase; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-color: #d6d8cf; border-radius: 4px; }
    .stButton > button[kind="primary"] { background: var(--accent); border-color: var(--accent); }
    @media (max-width: 700px) { .hero { min-height: 210px; padding: 22px; } .hero h1 { font-size: 42px; } }
    </style>
    <section class="hero">
      <div><div class="eyebrow">REEL GUIDE · YOUR PERSONAL FILM FINDER</div>
      <h1>Make tonight<br>movie night.</h1>
      <p>Tell me what you’re in the mood for. I’ll search, filter, compare, and explain every pick.</p></div>
    </section>
    """,
    unsafe_allow_html=True,
)

catalog_sources = {"Synthetic demo · 500 fictional films": CATALOG_PATH}
if WIKIDATA_CATALOG_PATH.exists():
    with WIKIDATA_CATALOG_PATH.open(encoding="utf-8") as catalog_file:
        wikidata_count = max(0, sum(1 for _ in catalog_file) - 1)
    catalog_sources[f"Wikidata · {wikidata_count:,} films (CC0)"] = WIKIDATA_CATALOG_PATH

selected_catalog = st.sidebar.selectbox(
    "Movie catalog",
    list(catalog_sources),
    index=len(catalog_sources) - 1,
)
if st.session_state.get("catalog_selection") != selected_catalog:
    st.session_state.catalog_selection = selected_catalog
    st.session_state.movie_agent = MovieAgent(load_catalog(catalog_sources[selected_catalog]))
    st.session_state.movie_history = []
elif "movie_agent" not in st.session_state:
    st.session_state.movie_agent = MovieAgent(load_catalog(catalog_sources[selected_catalog]))
    st.session_state.movie_history = []
elif not isinstance(st.session_state.movie_agent, MovieAgent):
    preferences = getattr(st.session_state.movie_agent, "preferences", {})
    st.session_state.movie_agent = MovieAgent(load_catalog(catalog_sources[selected_catalog]))
    st.session_state.movie_agent.preferences = preferences

if "movie_history" not in st.session_state:
    st.session_state.movie_history = []
if "last_sort" not in st.session_state:
    st.session_state.last_sort = "recommended"
if "visible_movie_count" not in st.session_state:
    st.session_state.visible_movie_count = 3
if "filter_min_rating" not in st.session_state:
    st.session_state.filter_min_rating = 0.0
if "filter_max_runtime" not in st.session_state:
    st.session_state.filter_max_runtime = 240
if "filter_min_year" not in st.session_state:
    st.session_state.filter_min_year = 1900
if "filter_max_year" not in st.session_state:
    st.session_state.filter_max_year = int(__import__("datetime").datetime.now().year)
if "filter_language" not in st.session_state:
    st.session_state.filter_language = "Any"
if "filter_platform" not in st.session_state:
    st.session_state.filter_platform = "Any"
if "filter_family_friendly" not in st.session_state:
    st.session_state.filter_family_friendly = False

st.write("")
st.markdown("### What are you in the mood for?")
st.caption("Search any movie title or catalog keyword, then use the filters below to narrow the results to exactly the kind of film you want.")

with st.form("movie_request", clear_on_submit=True):
    request = st.text_input(
        "Movie request",
        placeholder="Try a title or keyword, e.g. The Last Paper Kingdom, or a thoughtful mystery under 2 hours",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Find films", type="primary", use_container_width=True)

    st.caption("Quick filters")
    filter_cols = st.columns(2)
    with filter_cols[0]:
        st.session_state.filter_min_rating = st.slider("Minimum rating", min_value=0.0, max_value=10.0, value=float(st.session_state.filter_min_rating), step=0.5)
        st.session_state.filter_language = st.selectbox("Language", ["Any", "English", "Spanish", "French", "Japanese", "Korean", "Hindi"], index=["Any", "English", "Spanish", "French", "Japanese", "Korean", "Hindi"].index(st.session_state.filter_language))
    with filter_cols[1]:
        st.session_state.filter_platform = st.selectbox("Streaming", ["Any", "StreamFlix", "CineNow", "ViewPlus", "Public Library", "Rental"], index=["Any", "StreamFlix", "CineNow", "ViewPlus", "Public Library", "Rental"].index(st.session_state.filter_platform))
        st.session_state.filter_max_runtime = st.slider("Max runtime (minutes)", min_value=60, max_value=240, value=int(st.session_state.filter_max_runtime), step=15)

    filter_year_cols = st.columns(2)
    with filter_year_cols[0]:
        st.session_state.filter_min_year = st.number_input("From year", min_value=1900, max_value=2030, value=int(st.session_state.filter_min_year), step=1)
    with filter_year_cols[1]:
        current_year = int(__import__("datetime").datetime.now().year)
        st.session_state.filter_max_year = st.number_input("To year", min_value=1900, max_value=current_year, value=int(st.session_state.filter_max_year), step=1)

    st.session_state.filter_family_friendly = st.checkbox("Family friendly only", value=bool(st.session_state.filter_family_friendly))
    st.caption("Tip: you can combine free text with these filters for precise searches.")

sort_labels = {
    "Recommended": "recommended",
    "Title A–Z": "title",
    "Rating high–low": "rating",
}
selected_sort = st.radio("Sort results", list(sort_labels), horizontal=True)
sort_by = sort_labels[selected_sort]

if submitted and request.strip():
    filter_phrases = []
    if st.session_state.filter_min_rating > 0:
        filter_phrases.append(f"rated at least {st.session_state.filter_min_rating}")
    if st.session_state.filter_max_runtime < 240:
        filter_phrases.append(f"under {st.session_state.filter_max_runtime} minutes")
    if st.session_state.filter_min_year > 1900:
        filter_phrases.append(f"after {st.session_state.filter_min_year}")
    current_year = int(__import__("datetime").datetime.now().year)
    if st.session_state.filter_max_year < current_year:
        filter_phrases.append(f"before {st.session_state.filter_max_year + 1}")
    if st.session_state.filter_language != "Any":
        filter_phrases.append(st.session_state.filter_language)
    if st.session_state.filter_platform != "Any":
        filter_phrases.append(f"on {st.session_state.filter_platform}")
    if st.session_state.filter_family_friendly:
        filter_phrases.append("family friendly")

    full_request = request.strip()
    if filter_phrases:
        full_request = f"{full_request} {' '.join(filter_phrases)}" if full_request else ' '.join(filter_phrases)

    response = st.session_state.movie_agent.respond(full_request, sort_by=sort_by)
    st.session_state.movie_history.append({"request": full_request, "response": response})
elif st.session_state.movie_history and st.session_state.last_sort != sort_by:
    last_request = st.session_state.movie_history[-1]["request"]
    response = st.session_state.movie_agent.respond(last_request, sort_by=sort_by)
    st.session_state.movie_history[-1]["response"] = response
st.session_state.last_sort = sort_by

if st.session_state.movie_history:
    latest = st.session_state.movie_history[-1]["response"]
    st.markdown("### Your picks")
    st.write(latest["answer"])

    if latest["recommendations"]:
        if len(latest["recommendations"]) != st.session_state.get("last_recommendation_count"):
            st.session_state.visible_movie_count = min(3, len(latest["recommendations"]))
            st.session_state.last_recommendation_count = len(latest["recommendations"])

        visible_movies = latest["recommendations"][: st.session_state.visible_movie_count]
        columns = st.columns(min(3, len(visible_movies)))
        for index, movie in enumerate(visible_movies):
            with columns[index % len(columns)]:
                with st.container(border=True):
                    display_rating = f'{movie["rating"]}/10' if movie.get("rating") else "Not listed"
                    display_runtime = f'{movie["runtime_min"]} min' if movie.get("runtime_min") else "Runtime not listed"
                    title = escape(movie["title"])
                    st.markdown(f'<div class="movie-poster">{title}</div>', unsafe_allow_html=True)
                    st.markdown(f'**{title}**')
                    year_value = movie.get("year")
                    year_text = str(year_value) if year_value is not None else "Year not listed"
                    st.markdown(
                        f'<div class="movie-meta">{escape(year_text)} · {escape(display_runtime)} · '
                        f'{escape(display_rating)} · Rated {escape(movie.get("content_rating") or "Not listed")}<br>'
                        f'{escape(" / ".join(movie["genres_list"]) or "Genres not listed")}<br>'
                        f'On {escape(" · ".join(movie["platforms_list"]) or "Platforms not listed")}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Why it fits**")
                    st.markdown('<div class="movie-reason">' + escape("; ".join(movie["reasons"])) + "</div>", unsafe_allow_html=True)
                    st.caption("Tradeoff: " + "; ".join(movie["tradeoffs"]))

        if st.session_state.visible_movie_count < len(latest["recommendations"]):
            if st.button(
                "Show all results" if st.session_state.visible_movie_count + 3 >= len(latest["recommendations"]) else "Show more movies",
                use_container_width=True,
            ):
                st.session_state.visible_movie_count = len(latest["recommendations"])
                st.rerun()

        with st.expander("Compare these movies"):
            comparison = [
                {
                    "Title": movie["title"], "Year": movie["year"], "Genres": ", ".join(movie["genres_list"]),
                    "Runtime": f'{movie["runtime_min"]} min' if movie.get("runtime_min") else "Not listed",
                    "Rating": f'{movie["rating"]}/10' if movie.get("rating") else "Not listed",
                    "Language": movie["language"], "Content rating": movie["content_rating"],
                    "Streaming": ", ".join(movie["platforms_list"]),
                }
                for movie in latest["recommendations"]
            ]
            st.dataframe(comparison, hide_index=True, use_container_width=True)

    with st.expander("Agent tool trace"):
        for call in latest["trace"]:
            st.markdown(f'**{call["tool"]}** · {call["result_count"]} results')
            st.json({"arguments": call["arguments"], "sample_ids": call["sample_ids"]}, expanded=False)

    with st.expander("Conversation"):
        for turn in st.session_state.movie_history:
            st.markdown(f'**You:** {turn["request"]}')
            st.markdown(f'**Reel Guide:** {turn["response"]["answer"]}')

with st.sidebar:
    st.markdown("## Reel Guide")
    if "Wikidata" in selected_catalog:
        st.caption("Movie data from Wikidata (CC0). Some records have incomplete metadata.")
        st.caption("Source: [Wikidata](https://www.wikidata.org/)")
    else:
        st.caption("500 fictional catalog entries · all metadata is synthetic")
    st.markdown("### Current preferences")
    if st.session_state.movie_agent.preferences:
        for name, value in st.session_state.movie_agent.preferences.items():
            label = str(name).replace("_", " ").title()
            st.write(f"**{label}:** {value}")
    else:
        st.write("No filters yet")
    if st.button("Start a new search", use_container_width=True):
        st.session_state.movie_agent = MovieAgent(load_catalog(catalog_sources[selected_catalog]))
        st.session_state.movie_history = []
        st.session_state.visible_movie_count = 3
        st.session_state.last_recommendation_count = 0
        st.session_state.filter_min_rating = 0.0
        st.session_state.filter_max_runtime = 240
        st.session_state.filter_min_year = 1900
        st.session_state.filter_max_year = int(__import__("datetime").datetime.now().year)
        st.session_state.filter_language = "Any"
        st.session_state.filter_platform = "Any"
        st.session_state.filter_family_friendly = False
        st.rerun()

    provider = "omdb" if os.getenv("OMDB_API_KEY") else "tmdb" if os.getenv("TMDB_API_KEY") else None
    if st.button("Refresh ratings", use_container_width=True):
        if not provider:
            st.warning(
                "No ratings API key is configured. Add OMDB_API_KEY or TMDB_API_KEY to a local .env file or export it in your shell, then refresh again."
            )
        else:
            try:
                with st.spinner("Refreshing ratings from the configured provider..."):
                    _, filled_count, _ = enrich_ratings.enrich_catalog(catalog_sources[selected_catalog], provider=provider)
                if filled_count:
                    st.success(f"Added {filled_count} ratings.")
                    st.session_state.movie_agent = MovieAgent(load_catalog(catalog_sources[selected_catalog]))
                    st.session_state.movie_history = []
                    st.rerun()
                else:
                    st.info("No missing ratings could be filled from the configured source.")
            except Exception as exc:
                st.error(f"Ratings refresh failed: {exc}")

    st.markdown("---")
    st.caption("Recommendations use deterministic Python tools. No account or model API key required.")