import csv
from itertools import product
from pathlib import Path


OUTPUT = Path(__file__).parent / "data" / "movies.csv"

TITLES = [
    "After the Last Train", "A Map of Quiet Places", "Beneath a Copper Sky",
    "The Borrowed Season", "Bright Water, Dark Shore", "A Certain Kind of Winter",
    "The City Between Us", "Clouds Over Marigold Bay", "A Compass for Wolves",
    "The Distance to Morning", "Every Little Orbit", "The Far Side of June",
    "A Field Guide to Ghosts", "Fireflies at Noon", "The Garden of Small Wonders",
    "A Good Place to Begin", "Halfway to the Moon", "The House Without Clocks",
    "How the River Remembers", "An Impossible Weekend", "The Island of Second Chances",
    "A Kindness of Strangers", "The Last Paper Kingdom", "Letters from Elsewhere",
    "A Long Way Around", "The Midnight Orchard", "A Moment in the Sun",
    "The Museum of Lost Days", "The Name of the Windmill", "A Nearly Perfect Plan",
    "North of the Blue Line", "The Other Side of Summer", "A Pocket Full of Stars",
    "The Quiet Part of Town", "A River Made of Glass", "The Shape of Leaving",
    "A Small Adventure", "Somewhere, Still", "The Sound of Open Doors",
    "A Story for Tomorrow", "The Trouble with Tuesday", "Under a Paper Moon",
    "The Very Last Lighthouse", "A View from the Footbridge", "What We Keep",
    "When the Lights Come Back", "The Year of the Wild Garden", "Young Hearts, Old Roads",
    "Zero Hour at the Museum", "An Atlas of Ordinary Things",
]

GENRES = ["Drama", "Comedy", "Mystery", "Science Fiction", "Romance", "Adventure", "Thriller", "Family", "Fantasy", "Documentary"]
MOODS = ["uplifting", "thoughtful", "suspenseful", "cozy", "bittersweet", "playful", "inspiring", "meditative"]
LANGUAGES = ["English", "Spanish", "French", "Japanese", "Korean", "Hindi"]
PLATFORMS = ["StreamFlix", "CineNow", "ViewPlus", "Public Library", "Rental"]
CONTENT_RATINGS = ["G", "PG", "PG-13", "R"]


def build_catalog():
    films = []
    for index, (title, genre) in enumerate(product(TITLES, GENRES)):
        secondary_genre = GENRES[(index * 3 + 2) % len(GENRES)]
        genres = genre if secondary_genre == genre else f"{genre}|{secondary_genre}"
        films.append({
            "movie_id": f"M{index + 1:03}",
            "title": title,
            "year": 1985 + (index * 7) % 42,
            "genres": genres,
            "runtime_min": 78 + (index * 13) % 91,
            "rating": round(5.5 + ((index * 17) % 45) / 10, 1),
            "language": LANGUAGES[(index // len(GENRES) + index % len(GENRES)) % len(LANGUAGES)],
            "mood": MOODS[(index * 3) % len(MOODS)],
            "streaming_platforms": "|".join(PLATFORMS[(index + offset) % len(PLATFORMS)] for offset in range(2)),
            "content_rating": CONTENT_RATINGS[(index * 3) % len(CONTENT_RATINGS)],
            "description": f"A synthetic {genre.lower()} story with a {MOODS[(index * 3) % len(MOODS)]} tone.",
            "data_note": "SYNTHETIC: fictional title and illustrative metadata; not real-world film facts.",
        })
    return films


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    films = build_catalog()
    with OUTPUT.open("w", newline="", encoding="utf-8") as catalog_file:
        writer = csv.DictWriter(catalog_file, fieldnames=films[0].keys())
        writer.writeheader()
        writer.writerows(films)
    print(f"Wrote {len(films)} synthetic movie records to {OUTPUT}")