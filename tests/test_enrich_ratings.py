import unittest
from unittest.mock import patch

from enrich_ratings import (
    configured_provider,
    _normalize_wikidata_rating,
    _ratings_from_wikidata_bindings,
    fill_missing_ratings,
    fill_missing_wikidata_ratings,
)


class RatingsEnrichmentTests(unittest.TestCase):
    def test_fill_missing_ratings_replaces_blank_values(self):
        rows = [
            {"movie_id": "M1", "title": "Example Film", "year": "2020", "rating": ""},
            {"movie_id": "M2", "title": "Already Rated", "year": "2021", "rating": "8.2"},
        ]

        updated = fill_missing_ratings(rows, lambda title, year: 7.9 if title == "Example Film" else None)

        self.assertEqual(updated[0]["rating"], "7.9")
        self.assertEqual(updated[1]["rating"], "8.2")

    def test_fill_missing_ratings_keeps_blank_on_missing_result(self):
        rows = [{"movie_id": "M3", "title": "Missing Film", "year": "2019", "rating": ""}]

        updated = fill_missing_ratings(rows, lambda title, year: None)

        self.assertEqual(updated[0]["rating"], "")

    def test_wikidata_scores_normalize_explicit_scales_only(self):
        self.assertEqual(_normalize_wikidata_rating("8.6/10"), 8.6)
        self.assertEqual(_normalize_wikidata_rating("32/100"), 3.2)
        self.assertEqual(_normalize_wikidata_rating("4,4/5"), 8.8)
        self.assertIsNone(_normalize_wikidata_rating("91%"))
        self.assertIsNone(_normalize_wikidata_rating("12/10"))

    def test_demo_api_key_falls_back_to_wikidata(self):
        with patch.dict("os.environ", {"OMDB_API_KEY": "demo_key", "TMDB_API_KEY": ""}, clear=True):
            self.assertEqual(configured_provider(), "wikidata")

    def test_wikidata_prefers_imdb_and_ignores_rotten_tomatoes_percent(self):
        def binding(movie_id, score, reviewer_id):
            return {
                "item": {"value": f"http://www.wikidata.org/entity/{movie_id}"},
                "score": {"value": score},
                "reviewer": {"value": f"http://www.wikidata.org/entity/{reviewer_id}"},
            }

        ratings = _ratings_from_wikidata_bindings([
            binding("Q1", "90%", "Q105584"),
            binding("Q1", "7.2/10", "Q150248"),
            binding("Q1", "8.6/10", "Q37312"),
            binding("Q2", "88%", "Q105584"),
        ])

        self.assertEqual(ratings, {"Q1": ("8.6", "IMDb")})

    def test_fill_missing_wikidata_ratings_preserves_existing_values(self):
        rows = [
            {"movie_id": "Q1", "title": "Example Film", "rating": "", "rating_source": ""},
            {"movie_id": "Q2", "title": "Already Rated", "rating": "8.2", "rating_source": "IMDb"},
        ]
        updated = fill_missing_wikidata_ratings(rows, lambda ids: {"Q1": ("7.9", "Metacritic")})

        self.assertEqual(updated[0]["rating"], "7.9")
        self.assertEqual(updated[0]["rating_source"], "Metacritic")
        self.assertEqual(updated[1]["rating"], "8.2")
        self.assertEqual(updated[1]["rating_source"], "IMDb")


if __name__ == "__main__":
    unittest.main()
