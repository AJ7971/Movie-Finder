import argparse
import csv
import os
import re
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - optional dependency
    pass


DEFAULT_CATALOG = Path(__file__).parent / "data" / "wikidata_movies.csv"


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


def _fetch_raw_movie_rating(title, year=None, provider=None):
    provider_name = (provider or os.getenv("MOVIE_RATINGS_PROVIDER") or "omdb").lower()

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


def enrich_catalog(path, provider=None, write_back=True):
    catalog_path = Path(path)
    with catalog_path.open(newline="", encoding="utf-8") as catalog_file:
        rows = list(csv.DictReader(catalog_file))

    original_count = sum(1 for row in rows if row.get("rating") in (None, "", "N/A"))
    if original_count == 0:
        return rows, 0, False

    updated_rows = fill_missing_ratings(rows, lambda title, year: _fetch_raw_movie_rating(title, year, provider=provider))
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
    parser.add_argument("--provider", choices=["omdb", "tmdb"], default=None, help="Override the provider used for enrichment.")
    parser.add_argument("--dry-run", action="store_true", help="Preview which rows could be filled without writing to disk.")
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog not found: {catalog_path}")

    with catalog_path.open(newline="", encoding="utf-8") as catalog_file:
        rows = list(csv.DictReader(catalog_file))
    missing_rows = [row for row in rows if row.get("rating") in (None, "", "N/A")]
    if not missing_rows:
        print(f"No missing ratings found in {catalog_path}. Nothing to do.")
        return 0

    provider = args.provider or os.getenv("MOVIE_RATINGS_PROVIDER") or "omdb"
    if (provider == "omdb" and not os.getenv("OMDB_API_KEY")) or (provider == "tmdb" and not os.getenv("TMDB_API_KEY")):
        print(
            f"No {provider.upper()} API key found. Missing ratings were left unchanged. "
            "Set OMDB_API_KEY or TMDB_API_KEY before running this script."
        )
        return 0

    updated_rows = fill_missing_ratings(rows, lambda title, year: _fetch_raw_movie_rating(title, year, provider=provider))
    filled_count = sum(1 for before, after in zip(rows, updated_rows) if before.get("rating") != after.get("rating") and after.get("rating") not in (None, "", "N/A"))

    if args.dry_run:
        print(f"Dry run: {filled_count} missing ratings could be filled in {catalog_path}.")
        return 0

    with catalog_path.open("w", newline="", encoding="utf-8") as catalog_file:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(catalog_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"Updated {filled_count} missing ratings in {catalog_path} using {provider.upper()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
