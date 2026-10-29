import unittest

from enrich_ratings import fill_missing_ratings


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


if __name__ == "__main__":
    unittest.main()
