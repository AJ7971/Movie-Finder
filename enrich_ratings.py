import argparse
import csv
import os
import re
from statistics import median
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - optional dependency
    pass


DEFAULT_CATALOG = Path(__file__).parent / "data" / "wikidata_movies.csv"
WIKIDATA_QUERY_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_REVIEWERS = {
    "Q37312": "IMDb",
    "Q150248": "Metacritic",
    "Q105584": "Rotten Tomatoes",
}
RATING_SOURCE_PRIORITY = ("IMDb", "Metacritic", "Rotten Tomatoes")


def _normalize_rating(value):
    if value in (None, "", "N/A"):
        return None
    try:
        rating = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if 0 <= rating <= 10:
        return rating
    return None


def _normalize_title(value):
    text = (value or "").strip().casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _has_api_key(environment_name):
    value = os.getenv(environment_name, "").strip()
    placeholders = {"demo_key", "your_omdb_key_here", "your_tmdb_key_here", "changeme", "placeholder"}
    return bool(value) and value.casefold() not in placeholders


def configured_provider():
    requested = os.getenv("MOVIE_RATINGS_PROVIDER", "").strip().lower()
    if requested == "wikidata":
        return requested
    if requested == "omdb" and _has_api_key("OMDB_API_KEY"):
        return requested
    if requested == "tmdb" and _has_api_key("TMDB_API_KEY"):
        return requested
    if _has_api_key("OMDB_API_KEY"):
        return "omdb"
    if _has_api_key("TMDB_API_KEY"):
        return "tmdb"
    return "wikidata"


def _normalize_wikidata_rating(value):
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*", str(value or ""))
    if not match:
        return None
    score, maximum = (float(part.replace(",", ".")) for part in match.groups())
    if maximum <= 0 or score < 0 or score > maximum:
        return None
    return round(score / maximum * 10, 1)


def _ratings_from_wikidata_bindings(bindings):
    scores_by_movie = {}
    for binding in bindings:
        movie_id = binding.get("item", {}).get("value", "").rsplit("/", 1)[-1]
        reviewer_id = binding.get("reviewer", {}).get("value", "").rsplit("/", 1)[-1]
        source = WIKIDATA_REVIEWERS.get(reviewer_id)
        rating = _normalize_wikidata_rating(binding.get("score", {}).get("value"))
        if source and rating is not None:
            scores_by_movie.setdefault(movie_id, {}).setdefault(source, []).append(rating)

    selected = {}
    for movie_id, sources in scores_by_movie.items():
        source = next((name for name in RATING_SOURCE_PRIORITY if name in sources), None)
        if source:
            selected[movie_id] = (f"{median(sources[source]):.1f}", source)
    return selected


def _fetch_wikidata_ratings(movie_ids, client=requests):
    valid_ids = sorted({movie_id for movie_id in movie_ids if re.fullmatch(r"Q\d+", movie_id or "")})
    if not valid_ids:
        return {}

    items = " ".join(f"wd:{movie_id}" for movie_id in valid_ids)
    query = f"""
SELECT ?item ?score ?reviewer WHERE {{
  VALUES ?item {{ {items} }}
  VALUES ?reviewer {{ wd:Q37312 wd:Q150248 wd:Q105584 }}
  ?item p:P444 ?statement.
  ?statement ps:P444 ?score; pq:P447 ?reviewer.
}}
"""
    response = client.post(
        WIKIDATA_QUERY_ENDPOINT,
        data={"query": query, "format": "json"},
        headers={
            "User-Agent": "ReelGuideStudentProject/1.0 (educational movie catalog import)",
            "Accept": "application/sparql-results+json",
        },
        timeout=(10, 120),
    )
    response.raise_for_status()
    return _ratings_from_wikidata_bindings(response.json()["results"]["bindings"])


def _fetch_raw_movie_rating(title, year=None, provider=None):
    provider_name = (provider or configured_provider()).lower()

    if provider_name == "omdb":
        return _fetch_omdb_rating(title, year)
    if provider_name == "tmdb":
        return _fetch_tmdb_rating(title, year)
    return None


def _fetch_omdb_rating(title, year=None):
    api_key = os.getenv("OMDB_API_KEY")
    if not api_key or not title:
        return None

    params = {"apikey": api_key, "t": title}
    if year:
        try:
            params["y"] = str(int(float(year)))
        except (TypeError, ValueError):
            params["y"] = str(year)

    try:
        response = requests.get("https://www.omdbapi.com/", params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException:
        return None

    payload = response.json()
    if payload.get("Response") == "False":
        return None
    return _normalize_rating(payload.get("imdbRating"))


def _fetch_tmdb_rating(title, year=None):
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key or not title:
        return None

    params = {
        "api_key": api_key,
        "query": title,
        "include_adult": "false",
        "language": "en-US",
    }
    if year:
        try:
            params["year"] = str(int(float(year)))
        except (TypeError, ValueError):
            params["year"] = str(year)

    try:
        response = requests.get("https://api.themoviedb.org/3/search/movie", params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException:
        return None

    results = response.json().get("results") or []
    if not results:
        return None

    ranked_results = []
    normalized_title = _normalize_title(title)
    for item in results:
        result_title = _normalize_title(item.get("title") or item.get("original_title"))
        release_year = (item.get("release_date") or "")[:4]
        match_score = 2 if result_title == normalized_title else 0
        if year and release_year and str(year) == str(release_year):
            match_score += 1
        ranked_results.append((match_score, item))

    selected = max(ranked_results, key=lambda item: item[0], default=(0, None))[1] if ranked_results else None
    if selected is None:
        return None
    vote_average = selected.get("vote_average")
    return _normalize_rating(vote_average)


def fill_missing_ratings(rows, fetcher=None):
    fetch = fetcher or _fetch_raw_movie_rating
    updated = []
    for row in rows:
        record = dict(row)
        current_rating = record.get("rating")
        if current_rating not in (None, "", "N/A"):
            updated.append(record)
            continue

        title = record.get("title") or ""
        year = record.get("year") or ""
        rating = fetch(title, year)
        record["rating"] = str(rating) if rating is not None else ""
        updated.append(record)
    return updated


def fill_missing_wikidata_ratings(rows, fetcher=None):
    fetch = fetcher or _fetch_wikidata_ratings
    missing_ids = [
        row.get("movie_id", "") for row in rows
        if row.get("rating") in (None, "", "N/A")
    ]
    fetched = fetch(missing_ids)
    updated = []
    for row in rows:
        record = dict(row)
        result = fetched.get(record.get("movie_id", ""))
        if record.get("rating") in (None, "", "N/A") and result:
            record["rating"], record["rating_source"] = result
        updated.append(record)
    return updated


def enrich_catalog(path, provider=None, write_back=True):
    catalog_path = Path(path)
    with catalog_path.open(newline="", encoding="utf-8") as catalog_file:
        rows = list(csv.DictReader(catalog_file))

    original_count = sum(1 for row in rows if row.get("rating") in (None, "", "N/A"))
    if original_count == 0:
        return rows, 0, False

    provider_name = (provider or configured_provider()).lower()
    for row in rows:
        row.setdefault("rating_source", "")

    if provider_name == "wikidata":
        updated_rows = fill_missing_wikidata_ratings(rows)
    else:
        updated_rows = fill_missing_ratings(rows, lambda title, year: _fetch_raw_movie_rating(title, year, provider=provider))
        source_name = "OMDb" if provider_name == "omdb" else "TMDb"
        for before, after in zip(rows, updated_rows):
            if before.get("rating") != after.get("rating") and after.get("rating") not in (None, "", "N/A"):
                after["rating_source"] = source_name
    filled_count = sum(1 for before, after in zip(rows, updated_rows) if before.get("rating") != after.get("rating") and after.get("rating") not in (None, "", "N/A"))

    if write_back:
        with catalog_path.open("w", newline="", encoding="utf-8") as catalog_file:
            fieldnames = list(rows[0].keys()) if rows else []
            writer = csv.DictWriter(catalog_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

    return updated_rows, filled_count, True


def main():
    parser = argparse.ArgumentParser(description="Best-effort movie rating enrichment for local catalogs.")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="Path to the CSV catalog to enrich.")
    parser.add_argument("--provider", choices=["omdb", "tmdb", "wikidata"], default=None, help="Override the provider used for enrichment.")
    parser.add_argument("--dry-run", action="store_true", help="Preview which rows could be filled without writing to disk.")
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog not found: {catalog_path}")

    provider = args.provider or configured_provider()
    if (provider == "omdb" and not _has_api_key("OMDB_API_KEY")) or (provider == "tmdb" and not _has_api_key("TMDB_API_KEY")):
        print(
            f"No {provider.upper()} API key found. Missing ratings were left unchanged. "
            "Set OMDB_API_KEY or TMDB_API_KEY before running this script."
        )
        return 0

    _, filled_count, had_missing = enrich_catalog(catalog_path, provider=provider, write_back=not args.dry_run)
    if not had_missing:
        print(f"No missing ratings found in {catalog_path}. Nothing to do.")
    elif args.dry_run:
        print(f"Dry run: {filled_count} missing ratings could be filled in {catalog_path}.")
    else:
        print(f"Updated {filled_count} missing ratings in {catalog_path} using {provider.upper()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
