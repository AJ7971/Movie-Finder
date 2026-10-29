import unittest
from pathlib import Path

from movie_agent import MovieAgent, extract_search_terms, filter_movies, load_catalog, parse_request, search_movies


class MovieAgentTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.agent = MovieAgent(self.catalog)

    def test_catalog_has_at_least_one_hundred_disclosed_records(self):
        self.assertGreaterEqual(len(self.catalog), 100)
        self.assertTrue(all(row["data_note"].startswith("SYNTHETIC:") for row in self.catalog))

    def test_hard_constraints_are_enforced(self):
        preferences = parse_request("comedy under 100 minutes rated at least 7")
        matches = filter_movies(self.catalog, preferences)
        self.assertTrue(matches)
        self.assertTrue(all("Comedy" in movie["genres"].split("|") for movie in matches))
        self.assertTrue(all(int(movie["runtime_min"]) <= 100 for movie in matches))
        self.assertTrue(all(float(movie["rating"]) >= 7 for movie in matches))

    def test_request_runs_multiple_logged_tools(self):
        response = self.agent.respond("A thoughtful mystery under 2 hours")
        self.assertGreaterEqual(len(response["recommendations"]), 3)
        self.assertEqual(
            [call["tool"] for call in response["trace"]],
            ["search_movies", "filter_movies", "rank_movies", "compare_movies"],
        )
        self.assertTrue(all(int(movie["runtime_min"]) <= 120 for movie in response["recommendations"]))

    def test_follow_up_keeps_previously_selected_genre(self):
        self.agent.respond("Recommend a family-friendly adventure")
        response = self.agent.respond("Which has the shortest runtime?")
        self.assertEqual(response["preferences"]["genre"], "Adventure")
        self.assertEqual(response["preferences"]["family_friendly"], True)
        self.assertIn("shortest listed runtime", response["answer"])
        self.assertIn(response["recommendations"][0]["content_rating"], ("G", "PG"))
        self.assertEqual(response["recommendations"][0]["runtime_min"], min(
            movie["runtime_min"] for movie in response["recommendations"]
        ))

    def test_conflicting_constraints_are_not_relaxed(self):
        response = self.agent.respond("Find a mystery under 1 minute")
        self.assertEqual(response["recommendations"], [])
        self.assertIn("Which constraint would you like to relax?", response["answer"])
        self.assertEqual(response["trace"][-1]["tool"], "filter_movies")

    def test_year_constraint_is_enforced(self):
        response = self.agent.respond("Show me drama films after 2010")
        self.assertTrue(response["recommendations"])
        self.assertTrue(all(int(movie["year"]) >= 2010 for movie in response["recommendations"]))

    def test_platform_constraint_is_enforced(self):
        response = self.agent.respond("A comedy on Public Library")
        self.assertTrue(response["recommendations"])
        self.assertTrue(all("Public Library" in movie["streaming_platforms"].split("|") for movie in response["recommendations"]))

    def test_language_constraint_is_enforced(self):
        response = self.agent.respond("A Japanese fantasy film")
        self.assertTrue(response["recommendations"])
        self.assertTrue(all(movie["language"] == "Japanese" for movie in response["recommendations"]))

    def test_rating_constraint_is_enforced(self):
        response = self.agent.respond("A drama rating at least 8")
        self.assertTrue(response["recommendations"])
        self.assertTrue(all(float(movie["rating"]) >= 8 for movie in response["recommendations"]))

    def test_runtime_follow_up_updates_existing_preferences(self):
        self.agent.respond("A comedy")
        response = self.agent.respond("Under 90 minutes")
        self.assertEqual(response["preferences"]["genre"], "Comedy")
        self.assertTrue(all(int(movie["runtime_min"]) <= 90 for movie in response["recommendations"]))

    def test_missing_rating_does_not_crash_or_get_invented(self):
        movie = dict(next(row for row in self.catalog if "Mystery" in row["genres"].split("|")))
        movie["rating"] = ""
        response = MovieAgent([movie]).respond("mystery")
        self.assertEqual(len(response["recommendations"]), 1)
        self.assertFalse(any("catalog rating" in reason for reason in response["recommendations"][0]["reasons"]))

    def test_missing_runtime_is_not_invented(self):
        movie = dict(next(row for row in self.catalog if "Mystery" in row["genres"].split("|")))
        movie["runtime_min"] = ""
        response = MovieAgent([movie]).respond("mystery")
        self.assertEqual(len(response["recommendations"]), 1)
        self.assertIn("runtime is not listed", response["recommendations"][0]["tradeoffs"])

    def test_unconstrained_request_returns_three_or_more(self):
        response = self.agent.respond("Recommend a movie")
        self.assertGreaterEqual(len(response["recommendations"]), 3)

    def test_unconstrained_request_keeps_full_match_set(self):
        response = self.agent.respond("Recommend a movie")
        self.assertGreater(len(response["recommendations"]), 5)
        self.assertIn("I found", response["answer"])

    def test_free_text_title_search_returns_matching_title(self):
        response = self.agent.respond("The Last Paper Kingdom")
        self.assertTrue(response["recommendations"])
        self.assertEqual(len(response["recommendations"]), 1)
        self.assertTrue(all("The Last Paper Kingdom" in movie["title"] for movie in response["recommendations"]))
        self.assertEqual(response["trace"][0]["arguments"]["keywords"], ["last", "paper", "kingdom"])

    def test_free_text_metadata_search_matches_description(self):
        terms = extract_search_terms("uplifting synthetic story")
        self.assertEqual(terms, ["synthetic", "story"])
        matches = search_movies(self.catalog, keywords=terms)
        self.assertTrue(matches)
        self.assertTrue(all("synthetic" in movie["description"].casefold() for movie in matches))

    def test_new_search_does_not_retain_previous_title_keywords(self):
        self.agent.respond("The Last Paper Kingdom")
        response = self.agent.respond("Which has the shortest runtime?")
        self.assertEqual(response["trace"][0]["arguments"]["keywords"], [])
        self.assertTrue(response["recommendations"])

    def test_new_title_search_clears_old_filters(self):
        self.agent.respond("A thriller under 90 minutes")
        response = self.agent.respond("The Last Paper Kingdom")
        self.assertEqual(response["preferences"], {})
        self.assertTrue(response["recommendations"])
        self.assertTrue(all(movie["title"] == "The Last Paper Kingdom" for movie in response["recommendations"]))

    def test_wikidata_snapshot_contains_thousands_of_real_qids(self):
        path = Path(__file__).parents[1] / "data" / "wikidata_movies.csv"
        movies = load_catalog(path)
        self.assertGreaterEqual(len(movies), 1000)
        self.assertTrue(all(movie["movie_id"].startswith("Q") for movie in movies))
        self.assertTrue(all("CC0" in movie["data_note"] for movie in movies))

    def test_distinct_wikidata_ids_with_same_title_are_kept(self):
        first, second = dict(self.catalog[0]), dict(self.catalog[1])
        first.update(movie_id="Q100", title="Shared title", genres="Drama")
        second.update(movie_id="Q200", title="Shared title", genres="Drama")
        results = filter_movies([first, second], {})
        self.assertEqual([movie["movie_id"] for movie in results], ["Q100", "Q200"])

    def test_shortest_follow_up_handles_all_missing_runtimes(self):
        movie = dict(next(row for row in self.catalog if "Mystery" in row["genres"].split("|")))
        movie["runtime_min"] = ""
        agent = MovieAgent([movie])
        agent.respond("mystery")
        response = agent.respond("Which has the shortest runtime?")
        self.assertIn("None of the", response["answer"])
        self.assertIn("listed runtime", response["answer"])

    def test_title_sort_orders_full_candidate_set_alphabetically(self):
        response = self.agent.respond("Recommend a movie", sort_by="title")
        titles = [movie["title"] for movie in response["recommendations"]]
        self.assertEqual(titles, sorted(titles, key=str.casefold))
        self.assertIn("A–Z", response["answer"])

    def test_rating_sort_orders_highest_first_and_unrated_last(self):
        movies = [dict(movie) for movie in self.catalog[:3]]
        for index, movie in enumerate(movies):
            movie.update(movie_id=f"Q{index + 1}", title=f"Film {index + 1}", genres="Drama")
        movies[0]["rating"] = "8.1"
        movies[1]["rating"] = "9.2"
        movies[2]["rating"] = ""
        response = MovieAgent(movies).respond("Recommend a movie", sort_by="rating")
        self.assertEqual([movie["movie_id"] for movie in response["recommendations"]], ["Q2", "Q1", "Q3"])
        self.assertIn("unrated titles follow", response["answer"])

    def test_rating_sort_handles_catalog_without_ratings(self):
        movies = [dict(movie) for movie in self.catalog[:2]]
        for index, movie in enumerate(movies):
            movie.update(movie_id=f"Q{index + 1}", title=f"Film {2 - index}", genres="Drama", rating="")
        response = MovieAgent(movies).respond("Recommend a movie", sort_by="rating")
        self.assertEqual([movie["title"] for movie in response["recommendations"]], ["Film 1", "Film 2"])
        self.assertIn("no ratings", response["answer"])


if __name__ == "__main__":
    unittest.main()