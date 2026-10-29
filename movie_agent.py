import csv
import re
from pathlib import Path


CATALOG_PATH = Path(__file__).parent / "data" / "movies.csv"
GENRES = (
    "drama", "comedy", "mystery", "science fiction", "romance", "adventure", "thriller",
    "family", "fantasy", "documentary", "action", "horror", "crime", "western", "war",
    "musical", "historical", "biography", "animation", "sport",
)
MOOD_WORDS = {
    "uplifting": "uplifting", "feel-good": "uplifting", "thought-provoking": "thoughtful",
    "thoughtful": "thoughtful", "suspenseful": "suspenseful", "tense": "suspenseful",
    "cozy": "cozy", "bittersweet": "bittersweet", "playful": "playful",
    "inspiring": "inspiring", "meditative": "meditative", "relaxing": "meditative",
}
SEARCH_STOP_WORDS = {
    "a", "about", "after", "all", "an", "and", "any", "at", "before", "best", "between",
    "can", "could", "find", "film", "films", "for", "from", "good", "has", "have", "i",
    "in", "is", "it", "like", "me", "movie", "movies", "my", "of", "on", "one", "or",
    "please", "recommend", "search", "show", "something", "that", "the", "them", "there", "to", "want",
    "looking", "seeking", "am", "im",
    "watch", "what", "which", "with", "under", "below", "less", "than", "at", "most", "no",
    "more", "within", "hour", "hours", "hr", "hrs", "minute", "minutes", "min", "mins",
    "rating", "rated", "score", "least", "above", "over", "since", "year", "earlier", "friendly",
    "family", "kids", "kid", "runtime", "short", "shorter", "shortest", "quickest", "highest",
    "top", "rated", "rating", "any", "genre", "mood", "tone", "preferably", "available", "streaming",
}


def load_catalog(path=CATALOG_PATH):
    with Path(path).open(newline="", encoding="utf-8") as catalog_file:
        return list(csv.DictReader(catalog_file))


def _number(movie, key):
    try:
        return float(movie.get(key, ""))
    except (TypeError, ValueError):
        return None


def search_movies(catalog, category=None, keywords=None):
    terms = [term.casefold() for term in (keywords or []) if term.strip()]
    matches = []
    for movie in catalog:
        searchable = " ".join(str(movie.get(field, "")) for field in (
            "title", "genres", "mood", "description", "language", "streaming_platforms",
            "content_rating", "year", "runtime_min", "rating",
        )).casefold()
        movie_genres = [genre.casefold() for genre in movie.get("genres", "").split("|")]
        has_category = not category or category.casefold() in movie_genres
        has_terms = all(term in searchable for term in terms)
        if has_category and has_terms:
            matches.append(movie)
    return matches


def filter_movies(movies, criteria):
    filtered = []
    seen_titles = set()
    for movie in movies:
        if criteria.get("genre") and criteria["genre"].casefold() not in [genre.casefold() for genre in movie["genres"].split("|")]:
            continue
        numeric_constraints = (("max_runtime", "runtime_min", lambda value, limit: value <= limit),
                               ("min_year", "year", lambda value, limit: value >= limit),
                               ("max_year", "year", lambda value, limit: value <= limit),
                               ("min_rating", "rating", lambda value, limit: value >= limit))
        rejected = False
        for constraint, attribute, is_satisfied in numeric_constraints:
            if criteria.get(constraint) is not None:
                value = _number(movie, attribute)
                if value is None or not is_satisfied(value, criteria[constraint]):
                    rejected = True
                    break
        if rejected:
            continue
        if criteria.get("language") and movie["language"].casefold() != criteria["language"].casefold():
            continue
        if criteria.get("family_friendly") and movie.get("content_rating") not in ("G", "PG"):
            continue
        if criteria.get("platform") and criteria["platform"].casefold() not in movie.get("streaming_platforms", "").casefold().split("|"):
            continue
        if movie.get("movie_id", "").startswith("Q"):
            dedupe_key = movie["movie_id"]
        else:
            dedupe_key = movie.get("title", "").casefold()
        if dedupe_key in seen_titles:
            continue
        filtered.append(movie)
        seen_titles.add(dedupe_key)
    return filtered


def rank_movies(movies, preferences):
    ranked = []
    for movie in movies:
        components = []
        if preferences.get("genre"):
            movie_genres = [genre.casefold() for genre in movie["genres"].split("|")]
            components.append((0.45, float(preferences["genre"].casefold() in movie_genres)))
        if preferences.get("mood") and movie.get("mood"):
            components.append((0.25, float(preferences["mood"].casefold() == movie["mood"].casefold())))
        rating = _number(movie, "rating")
        if rating is not None:
            components.append((0.20, rating / 10))
        runtime = _number(movie, "runtime_min")
        if preferences.get("preferred_runtime") and runtime is not None:
            distance = abs(runtime - preferences["preferred_runtime"])
            components.append((0.10, max(0, 1 - distance / 90)))
        score = sum(weight * value for weight, value in components) / sum(weight for weight, _ in components) if components else 0
        ranked.append((score, movie))
    return [movie for _, movie in sorted(ranked, key=lambda item: (-item[0], -(_number(item[1], "rating") or 0), _number(item[1], "runtime_min") or 0))]


def compare_movies(catalog, movie_ids):
    wanted = set(movie_ids)
    return [movie for movie in catalog if movie["movie_id"] in wanted]


def parse_request(message, existing=None):
    preferences = dict(existing or {})
    text = message.casefold()

    for genre in GENRES:
        if re.search(r"\b" + re.escape(genre) + r"\b", text):
            preferences["genre"] = genre.title() if genre != "science fiction" else "Science Fiction"
            break

    for word, mood in MOOD_WORDS.items():
        if word in text:
            preferences["mood"] = mood
            break

    runtime_match = re.search(r"(?:under|below|less than|at most|no more than|within)\s+(\d+)\s*(hours?|hrs?|minutes?|mins?)\b", text)
    if runtime_match:
        amount = int(runtime_match.group(1))
        preferences["max_runtime"] = amount * 60 if runtime_match.group(2).startswith(("hour", "hr")) else amount
    elif "shorter" in text or "short runtime" in text:
        preferences["preferred_runtime"] = 95

    rating_match = re.search(r"(?:rating|rated|score)\s*(?:of\s*)?(?:at least|above|over|>=)?\s*(\d(?:\.\d)?)", text)
    if rating_match:
        preferences["min_rating"] = float(rating_match.group(1))

    year_match = re.search(r"(?:after|since|from)\s+(19\d{2}|20\d{2})", text)
    if year_match:
        preferences["min_year"] = int(year_match.group(1))
    before_year_match = re.search(r"(?:before|earlier than)\s+(19\d{2}|20\d{2})", text)
    if before_year_match:
        preferences["max_year"] = int(before_year_match.group(1)) - 1

    for language in ("English", "Spanish", "French", "Japanese", "Korean", "Hindi"):
        if re.search(r"\b" + language.casefold() + r"\b", text):
            preferences["language"] = language
            break

    if any(phrase in text for phrase in ("family friendly", "family-friendly", "for kids", "kid friendly")):
        preferences["family_friendly"] = True
    for platform in ("StreamFlix", "CineNow", "ViewPlus", "Public Library", "Rental"):
        if platform.casefold() in text:
            preferences["platform"] = platform
            break

    if "any genre" in text or "no genre" in text:
        preferences.pop("genre", None)
    return preferences


def extract_search_terms(message):
    """Keep user-supplied words not already represented by a structured filter."""
    text = message.casefold()
    text = re.sub(r"(?:under|below|less than|at most|no more than|within)\s+\d+\s*(?:hours?|hrs?|minutes?|mins?)", " ", text)
    text = re.sub(r"(?:after|since|from|before|earlier than)\s+(?:19\d{2}|20\d{2})", " ", text)
    text = re.sub(r"(?:rating|rated|score)\s*(?:of\s*)?(?:at least|above|over|>=)?\s*\d(?:\.\d)?", " ", text)

    known_terms = set(SEARCH_STOP_WORDS)
    known_terms.update(word for genre in GENRES for word in genre.split())
    known_terms.update(MOOD_WORDS)
    known_terms.update(("english", "spanish", "french", "japanese", "korean", "hindi"))
    known_terms.update(word for platform in ("StreamFlix", "CineNow", "ViewPlus", "Public Library", "Rental") for word in platform.casefold().split())
    terms = []
    for term in re.findall(r"[a-z]+(?:-[a-z]+)?", text):
        if term not in known_terms and term not in terms:
            terms.append(term)
    return terms


def is_contextual_follow_up(message):
    text = message.casefold().strip()
    return bool(re.match(
        r"^(which|what about|and\b|also\b|under\b|below\b|less than\b|at most\b|no more than\b|"
        r"within\b|after\s+\d|before\s+\d|increase\b|raise\b|make it\b|shortest\b|quickest\b|"
        r"highest rated\b|best rated\b|top rating\b|more like that\b)",
        text,
    ))


class MovieAgent:
    """A transparent local agent that routes requests through catalog tools."""

    def __init__(self, catalog=None):
        self.catalog = catalog if catalog is not None else load_catalog()
        self.preferences = {}
        self.candidates = []
        self.trace = []

    def _call_tool(self, name, arguments, function):
        result = function()
        self.trace.append({
            "tool": name,
            "arguments": arguments,
            "result_count": len(result),
            "sample_ids": [movie["movie_id"] for movie in result[:5]],
        })
        return result

    def _recommendation_details(self, movie):
        reasons = []
        if self.preferences.get("genre") and self.preferences["genre"].casefold() in movie["genres"].casefold().split("|"):
            reasons.append(f"matches your {self.preferences['genre']} preference")
        if self.preferences.get("mood") and self.preferences["mood"] == movie["mood"]:
            reasons.append(f"has the {movie['mood']} tone you asked for")
        rating = _number(movie, "rating")
        if rating is not None:
            reasons.append(f"catalog rating {rating}/10")
        if self.search_terms:
            reasons.append("matches your search: " + " ".join(self.search_terms))
        tradeoffs = []
        runtime = _number(movie, "runtime_min")
        if self.preferences.get("max_runtime") and runtime is not None and runtime >= self.preferences["max_runtime"] - 10:
            tradeoffs.append(f"near your {self.preferences['max_runtime']}-minute runtime limit")
        if rating is not None and rating < 7:
            tradeoffs.append("lower catalog rating than the highest-rated options")
        if runtime is None:
            tradeoffs.append("runtime is not listed")
        elif not tradeoffs:
            tradeoffs.append(f"runs {int(runtime)} minutes")
        return {"reasons": reasons, "tradeoffs": tradeoffs}

    def respond(self, message, sort_by="recommended"):
        if sort_by not in ("recommended", "title", "rating"):
            raise ValueError("sort_by must be 'recommended', 'title', or 'rating'")
        self.trace = []
        if self.preferences and not is_contextual_follow_up(message):
            self.preferences = {}
        self.preferences = parse_request(message, self.preferences)
        normalized = message.casefold()
        category = self.preferences.get("genre")
        keywords = extract_search_terms(message)
        self.search_terms = keywords
        search_arguments = {"category": category, "keywords": keywords}
        searched = self._call_tool(
            "search_movies",
            search_arguments,
            lambda: search_movies(self.catalog, category=category, keywords=keywords),
        )
        criteria = {
            key: self.preferences.get(key)
            for key in ("genre", "max_runtime", "min_year", "max_year", "min_rating", "language", "family_friendly", "platform")
            if self.preferences.get(key) is not None
        }
        eligible = self._call_tool(
            "filter_movies",
            {"criteria": criteria},
            lambda: filter_movies(searched, criteria),
        )

        if not eligible:
            self.candidates = []
            active = ", ".join(f"{str(key).replace('_', ' ')}: {value}" for key, value in criteria.items()) or "the selected genre"
            return {
                "answer": f"No movies in this catalog satisfy all the hard constraints ({active}). Which constraint would you like to relax? I have not relaxed any automatically.",
                "recommendations": [], "trace": self.trace, "preferences": dict(self.preferences),
            }

        ranked = self._call_tool(
            "rank_movies",
            {"preferences": dict(self.preferences), "candidate_count": len(eligible)},
            lambda: rank_movies(eligible, self.preferences),
        )
        shortest_requested = sort_by == "recommended" and any(
            phrase in normalized for phrase in ("shortest", "shorter", "best runtime", "quickest")
        )
        highest_rated_requested = sort_by == "recommended" and any(
            phrase in normalized for phrase in ("highest rated", "best rated", "top rating")
        )
        if sort_by == "title":
            shortlist = sorted(eligible, key=lambda movie: movie.get("title", "").casefold())
        elif sort_by == "rating":
            rated = sorted(
                (movie for movie in eligible if _number(movie, "rating") is not None),
                key=lambda movie: (-_number(movie, "rating"), movie.get("title", "").casefold()),
            )
            unrated = sorted(
                (movie for movie in eligible if _number(movie, "rating") is None),
                key=lambda movie: movie.get("title", "").casefold(),
            )
            shortlist = rated + unrated
        elif shortest_requested:
            movies_with_runtime = [movie for movie in eligible if _number(movie, "runtime_min") is not None]
            shortlist = sorted(movies_with_runtime, key=lambda movie: _number(movie, "runtime_min")) or ranked
        elif highest_rated_requested:
            shortlist = sorted(eligible, key=lambda movie: _number(movie, "rating") or 0, reverse=True)
        else:
            shortlist = ranked
        compared = self._call_tool(
            "compare_movies",
            {"movie_ids": [movie["movie_id"] for movie in shortlist]},
            lambda: compare_movies(self.catalog, [movie["movie_id"] for movie in shortlist]),
        )
        comparisons = {movie["movie_id"]: movie for movie in compared}
        self.candidates = [comparisons[movie["movie_id"]] for movie in shortlist]

        if shortest_requested:
            self.candidates.sort(key=lambda movie: _number(movie, "runtime_min") or float("inf"))
            runtime = _number(self.candidates[0], "runtime_min")
            if runtime is None:
                answer = f"None of the {len(eligible)} qualifying movies has a listed runtime, so I can't compare their lengths."
            else:
                answer = f"Among the {len(eligible)} qualifying movies, {self.candidates[0]['title']} has the shortest listed runtime at {int(runtime)} minutes."
        elif highest_rated_requested:
            self.candidates.sort(key=lambda movie: _number(movie, "rating") or 0, reverse=True)
            rating = self.candidates[0].get("rating") or "not listed"
            answer = f"Among the {len(eligible)} qualifying movies, {self.candidates[0]['title']} has the highest catalog rating at {rating}/10."
        elif sort_by == "title":
            answer = f"I found {len(eligible)} movies matching your hard constraints. Here are all of them in title order (A–Z)."
        elif sort_by == "rating":
            rated_count = sum(_number(movie, "rating") is not None for movie in eligible)
            if rated_count:
                answer = f"I found {len(eligible)} movies matching your hard constraints. Here are all of them by rating, highest first; unrated titles follow."
            else:
                answer = f"This catalog has no ratings for the {len(eligible)} matching movies, so they are shown in title order (A–Z)."
        else:
            answer = f"I found {len(eligible)} movies matching your hard constraints. Here are all of the strongest matches, ranked by genre and mood fit, catalog rating, and runtime preference."

        recommendations = []
        for movie in self.candidates:
            normalized = dict(movie)
            for key in ("runtime_min", "year", "rating"):
                value = _number(normalized, key)
                if value is not None:
                    normalized[key] = int(value) if key in {"runtime_min", "year"} else float(value)
            details = self._recommendation_details(movie)
            recommendations.append({
                **normalized,
                "genres_list": [genre for genre in movie.get("genres", "").split("|") if genre],
                "platforms_list": [platform for platform in movie.get("streaming_platforms", "").split("|") if platform],
                **details,
            })
        return {
            "answer": answer,
            "recommendations": recommendations,
            "trace": self.trace,
            "preferences": dict(self.preferences),
        }