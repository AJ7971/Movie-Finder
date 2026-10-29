import unittest

from import_wikidata import fetch_movies


class FakeResponse:
    def __init__(self, bindings):
        self.bindings = bindings

    def raise_for_status(self):
        pass

    def json(self):
        return {"results": {"bindings": self.bindings}}


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)

    def get(self, *_args, **_kwargs):
        return FakeResponse(next(self.responses))


def entity(qid):
    return {"item": {"value": f"http://www.wikidata.org/entity/{qid}"}}


class WikidataImportTests(unittest.TestCase):
    def test_joins_metadata_and_deduplicates_release_dates(self):
        client = FakeClient([
            [
                {**entity("Q1"), "itemLabel": {"value": "Example Film"}, "releaseDate": {"value": "2001-05-01T00:00:00Z"}},
                {**entity("Q1"), "itemLabel": {"value": "Example Film"}, "releaseDate": {"value": "1999-01-01T00:00:00Z"}},
            ],
            [{**entity("Q1"), "genreLabel": {"value": "science fiction film"}}],
            [{**entity("Q1"), "runtime": {"value": "123"}}],
        ])

        movies, release_count = fetch_movies(client)

        self.assertEqual(release_count, 2)
        self.assertEqual(len(movies), 1)
        self.assertEqual(movies[0]["year"], "1999")
        self.assertEqual(movies[0]["genres"], "Science Fiction")
        self.assertEqual(movies[0]["runtime_min"], "123")
        self.assertEqual(movies[0]["rating"], "")
        self.assertIn("CC0", movies[0]["data_note"])


if __name__ == "__main__":
    unittest.main()