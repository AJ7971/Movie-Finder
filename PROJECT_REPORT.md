# Reel Guide Project Report

## 1. Introduction and Problem Definition

Reel Guide helps viewers find and compare films from stated preferences. Unlike a one-shot genre list, it carries filters across follow-up messages and runs a traceable sequence of catalog operations. The movie domain uses runtime, release year, rating, language, content rating, and streaming availability instead of shopping price and hardware specifications.

## 2. System Architecture

Streamlit interface → `MovieAgent` → search, filter, rank, and compare Python tools → local CSV catalog. Preference interpretation and state are in `movie_agent.py`; numerical filtering and scoring remain deterministic Python operations. No external API is required.

## 3. Dataset and Preprocessing

Two catalogs are available. The synthetic fallback contains 500 generated records and is clearly disclosed. The real-data snapshot contains 3,953 unique Wikidata films, imported from structured CC0 data with QID source links. Three bounded SPARQL requests collect titles/years, genres, and runtimes, then join locally. Release-date duplicates are collapsed to one record using the earliest listed year. Missing data remains blank; it is not fabricated. Refresh with `python import_wikidata.py`. CSV parsing uses Python's `csv` module, and missing numeric values cannot meet active numeric hard constraints.

## 4. Agent Design and Workflow

The agent parses recognized phrases into persistent preferences, then selects the catalog tool sequence. A standard request calls search → filter → rank → compare. Empty results stop before ranking and ask the user which constraint to relax; filters are never relaxed automatically. Follow-ups modify only the preferences they mention. The trace panel exposes actual Python function calls, arguments, result counts, and sample IDs.

Example: `A thoughtful mystery under 2 hours` sets genre, mood, and a 120-minute ceiling. The agent searches mysteries, filters by genre and runtime, ranks the survivors, and compares up to five records. A follow-up such as `Which has the shortest runtime?` preserves those filters and compares the shortest qualifying films across the full eligible set.

## 5. Implemented Tools

- `search_movies(catalog, category, keywords)` finds catalog candidates.
- `filter_movies(movies, criteria)` applies hard constraints in program logic.
- `rank_movies(movies, preferences)` computes the explicit weighted score.
- `compare_movies(catalog, movie_ids)` retrieves structured details for the shortlist.

## 6. Recommendation Algorithm

Hard constraints are applied before ranking. For each eligible film, available preference components contribute: genre match 0.45, mood match 0.25, rating normalized to 0–1 at 0.20, and proximity to a preferred runtime at 0.10. The weighted sum is divided by the sum of included weights, so absent preference components do not penalize a film. Ties use rating and runtime as deterministic tie-breakers. All numerical work is performed in Python; this is a content-feature ranker, not collaborative filtering.

## 7. Interface and Sample Interactions

The Streamlit screen accepts a natural-language request, displays up to five recommendations with catalog-backed reasons and tradeoffs, provides a comparison table, retains the conversation, and reveals the tool trace. It also shows active preferences and offers a reset action. Sample requests are listed in `README.md`.

## 8. Testing Methods, Metrics, and Results

The automated suite has 24 tests. Current result: 24 passed. It checks both catalogs, Wikidata ID joins/deduplication, free-text title/metadata searches, hard-constraint satisfaction, tool selection/order, follow-up retention, independent repeated searches, year/runtime/rating/language/platform filters, missing metadata, alphabetical/rating sorting, empty results, and recommendation count. These are behavioral checks; recommendation relevance is measured indirectly through deterministic feature matching rather than a human study.

| Evaluation area | Finding |
| --- | --- |
| Constraint satisfaction | Hard filters run before rank; tests verify returned items satisfy active limits. |
| Recommendation relevance | Genre and mood contribute explicit ranking weight; no user-rating history is available. |
| Tool-call correctness | Four real local tools run in sequence and are visible in the trace; multi-tool order is tested. |
| Explanation quality | Reasons and tradeoffs use catalog fields; missing rating is omitted rather than invented. |
| Reliability | No-match requests ask before relaxing constraints; absent imported metadata stays unlisted and cannot satisfy an active hard filter. |

Illustrative trace structure for a normal request: `search_movies (500 or genre-matched candidates) → filter_movies (eligible subset) → rank_movies (eligible subset) → compare_movies (up to 5 IDs)`. Exact counts vary with preferences and are shown by the running app.

## 9. Limitations and Improvements

Wikidata coverage is uneven: many records have no rating, language, synopsis, or current streaming availability, so those filters can return no matches. Wikidata data may also contain errors. Constraint parsing recognizes a finite set of genres, moods, and constraint phrases; arbitrary text is searched literally against available catalog fields. The synthetic catalog is illustrative, not real film metadata. A next iteration could add user feedback and evaluate ranking against a human relevance set.

## 10. Contributions and AI-Assistance Disclosure

Team member contributions: **replace with member names and actual responsibilities before submission**. GitHub Copilot assisted with project scaffolding, implementation, and tests. The team should review, run, explain, and modify the central logic in accordance with course policy.