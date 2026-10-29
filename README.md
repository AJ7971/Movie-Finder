# Reel Guide

Reel Guide is a conversational movie discovery app. It interprets preferences, calls deterministic Python catalog tools, filters hard constraints, ranks matches, compares the shortlist, and retains preferences for follow-up questions.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python generate_catalog.py
python import_wikidata.py
streamlit run app.py
```

Run the evaluation tests with:

```bash
python -m unittest discover -s tests -v
```

## Example requests

- `The Last Paper Kingdom` (free-text title search)
- `synthetic uplifting story` (searches catalog descriptions and other metadata)
- `A thoughtful mystery under 2 hours`
- `A family-friendly comedy rated at least 7`
- `A Japanese fantasy film after 2010`
- `Which of those has the shortest runtime?`
- `Under 90 minutes` (updates the current filters without losing the genre)

The movie domain replaces shopping price/budget constraints with runtime, release-year, rating, language, content-rating, and streaming-platform constraints.

Recommendation results can be sorted by the agent's ranking, title (A–Z), or catalog rating (highest first). Unrated titles are placed after rated titles; if no matches have ratings, the app explains that and shows them alphabetically.

## Catalog

The app includes two catalog choices. `data/movies.csv` contains 500 generated records; the titles and associated metadata are fictional and clearly labeled. `generate_catalog.py` recreates this no-network fallback.

`data/wikidata_movies.csv` contains the imported real-data snapshot. `import_wikidata.py` uses three bounded Wikidata Query Service requests, joins records by QID, and deduplicates multiple release-date statements. The current snapshot has 3,953 unique films. It includes title and earliest listed release year; genre and runtime are included when Wikidata has them. Missing rating, language, platform, and content-rating fields stay blank rather than being invented. To refresh it, run `python import_wikidata.py`; this requires network access and may take a few minutes. Structured Wikidata data is CC0. Source links are stored per record and the app attributes Wikidata in its sidebar. Respect the service's current access guidance and terms.

## Agent and tools

`MovieAgent` maintains conversation preferences and runs an observable workflow:

1. `search_movies` searches the local catalog by genre and keywords.
2. `filter_movies` enforces runtime, year, rating, language, content-rating, and platform constraints in Python. Missing values do not satisfy an active hard constraint.
3. `rank_movies` scores eligible films with a normalized weighted feature score. Genre fit has weight 0.45, mood fit 0.25, catalog rating 0.20, and proximity to a preferred runtime 0.10; weights for unavailable preferences are removed and the remaining weights are normalized.
4. `compare_movies` retrieves full catalog records for the selected films.

Each executed tool and its arguments, result count, and sample IDs are shown in the Streamlit trace. Free-text terms search titles and all available catalog metadata; recognized constraints are applied separately. The agent and ranking are local and deterministic; no model API key is needed. Constraint interpretation recognizes a documented set of natural-language phrase patterns.

## Evaluation

The test suite contains 24 cases covering both catalogs, the Wikidata import/join, title and metadata keyword searches, hard constraints, tool-call order, retained follow-up context, independent repeated searches, missing metadata, result sorting, empty results, and the three-recommendation minimum. On the current implementation all 24 pass. See [PROJECT_REPORT.md](PROJECT_REPORT.md) for the evaluation summary, sample trace, limitations, and report outline.