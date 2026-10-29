import csv
from datetime import datetime
from pathlib import Path
from time import sleep

import requests


OUTPUT = Path(__file__).parent / "data" / "wikidata_movies.csv"
QUERY_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "ReelGuideStudentProject/1.0 (educational movie catalog import)"
QUERY = """
SELECT ?item ?itemLabel ?releaseDate WHERE {
  ?item wdt:P31 wd:Q11424;
        wdt:P577 ?releaseDate.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 10000
"""
GENRE_QUERY = """
SELECT ?item ?genreLabel WHERE {
    ?item wdt:P31 wd:Q11424;
                wdt:P136 ?genre.
    ?genre rdfs:label ?genreLabel.
    FILTER(LANG(?genreLabel) = "en")
}
LIMIT 10000
"""
RUNTIME_QUERY = """
SELECT ?item ?runtime WHERE {
    ?item wdt:P31 wd:Q11424;
                wdt:P2047 ?runtime.
}
LIMIT 10000
"""
FIELDS = (
    "movie_id", "title", "year", "genres", "runtime_min", "rating", "language",
    "mood", "streaming_platforms", "content_rating", "description", "data_note",
    "source_url",
)


def _fetch_bindings(query, client):
    response = client.get(
        QUERY_ENDPOINT,
        params={"query": query, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=(10, 120),
    )
    response.raise_for_status()
    return response.json()["results"]["bindings"]


def _item_id(binding):
    return binding["item"]["value"].rsplit("/", 1)[-1]


def _normalize_genre(label):
    normalized = label.strip().casefold()
    if normalized.endswith(" film"):
        normalized = normalized[:-5]
    return normalized.title()


def fetch_movies(client=requests):
    bindings = _fetch_bindings(QUERY, client)
    release_record_count = len(bindings)

    movies = {}
    for binding in bindings:
        item_id = _item_id(binding)
        title = binding.get("itemLabel", {}).get("value", "").strip()
        date = binding.get("releaseDate", {}).get("value", "")
        if not item_id.startswith("Q") or not title or not date:
            continue
        movie = movies.setdefault(item_id, {
            "movie_id": item_id,
            "title": title,
            "year": "",
            "genres": "",
            "runtime_min": "",
            "rating": "",
            "language": "",
            "mood": "",
            "streaming_platforms": "",
            "content_rating": "",
            "description": "",
            "data_note": "Wikidata structured data; CC0. Fields not present in this import are left blank.",
            "source_url": f"https://www.wikidata.org/wiki/{item_id}",
        })
        try:
            year = datetime.fromisoformat(date.replace("Z", "+00:00")).year
        except ValueError:
            continue
        if not movie["year"] or year < int(movie["year"]):
            movie["year"] = str(year)

    sleep(1)
    for binding in _fetch_bindings(GENRE_QUERY, client):
        movie = movies.get(_item_id(binding))
        if movie:
            genre = _normalize_genre(binding.get("genreLabel", {}).get("value", ""))
            genres = set(filter(None, movie["genres"].split("|")))
            if genre:
                genres.add(genre)
                movie["genres"] = "|".join(sorted(genres))

    sleep(1)
    for binding in _fetch_bindings(RUNTIME_QUERY, client):
        movie = movies.get(_item_id(binding))
        runtime = binding.get("runtime", {}).get("value")
        if movie and runtime:
            try:
                movie["runtime_min"] = str(round(float(runtime)))
            except ValueError:
                continue
    return list(movies.values()), release_record_count


def write_catalog(output=OUTPUT):
    movies, row_count = fetch_movies()
    if not movies:
        raise RuntimeError("Wikidata returned no usable movie records; existing catalog was not changed.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as catalog_file:
        writer = csv.DictWriter(catalog_file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(movies)
    print(f"Imported {len(movies)} unique movies from {row_count} Wikidata release-date records.")
    print(f"Catalog written to {output}")
    return len(movies)


if __name__ == "__main__":
    write_catalog()