import unittest
from datetime import date, timedelta

from ml.matcher import rank_matches


class RankMatchesTests(unittest.TestCase):
    def setUp(self):
        self.lost = {
            "id": 1,
            "type": "LOST",
            "status": "OPEN",
            "title": "Blue water bottle",
            "description": "A steel bottle with a mountain sticker.",
            "category": "Water Bottles",
            "location": "North Library",
            "date": date(2026, 11, 10),
        }
        self.similar_found = {
            "id": 2,
            "type": "FOUND",
            "status": "OPEN",
            "title": "Blue bottle found",
            "description": "Steel water bottle with mountain sticker.",
            "category": "Water Bottles",
            "location": "North Library entrance",
            "date": date(2026, 11, 11),
        }

    def test_similar_lost_and_found_reports_rank_first(self):
        unrelated = {
            "id": 3,
            "type": "FOUND",
            "status": "OPEN",
            "title": "Red umbrella",
            "description": "Foldable umbrella left in the gym.",
            "category": "Accessories",
            "location": "Gym",
            "date": date(2026, 8, 1),
        }

        results = rank_matches(self.lost, [unrelated, self.similar_found])

        self.assertEqual(results[0]["candidate"]["id"], self.similar_found["id"])
        self.assertGreater(results[0]["similarity_score"], results[1]["similarity_score"])
        self.assertGreaterEqual(results[0]["similarity_score"], 0)
        self.assertLessEqual(results[0]["similarity_score"], 100)

    def test_unrelated_reports_receive_a_low_score(self):
        unrelated = {
            **self.similar_found,
            "title": "Red umbrella",
            "description": "Foldable umbrella.",
            "category": "Accessories",
            "location": "Gym",
            "date": date(2026, 8, 1),
        }

        result = rank_matches(self.lost, [unrelated])[0]

        self.assertLess(result["similarity_score"], 20)

    def test_category_and_colour_differences_lower_match_score(self):
        wrong_category = {
            **self.similar_found,
            "id": 4,
            "category": "Electronics",
        }
        wrong_colour = {
            **self.similar_found,
            "id": 5,
            "title": "Red water bottle",
            "description": "A steel bottle with a mountain sticker.",
        }

        results = rank_matches(self.lost, [wrong_category, wrong_colour, self.similar_found])
        scores = {result["candidate"]["id"]: result["similarity_score"] for result in results}

        self.assertGreater(scores[self.similar_found["id"]], scores[wrong_category["id"]])
        self.assertGreater(scores[self.similar_found["id"]], scores[wrong_colour["id"]])

    def test_location_and_date_differences_are_reported_and_affect_score(self):
        distant = {
            **self.similar_found,
            "id": 6,
            "location": "South sports field",
            "date": self.lost["date"] - timedelta(days=75),
        }

        results = rank_matches(self.lost, [distant, self.similar_found])
        distant_result = next(result for result in results if result["candidate"]["id"] == 6)
        near_result = next(result for result in results if result["candidate"]["id"] == 2)

        self.assertLess(distant_result["similarity_score"], near_result["similarity_score"])
        self.assertEqual(distant_result["matching_details"]["date_difference_days"], 75)
        self.assertLess(
            distant_result["matching_details"]["location_similarity"],
            near_result["matching_details"]["location_similarity"],
        )

    def test_missing_descriptions_and_structured_features_are_safe(self):
        source = {"id": 10, "type": "LOST", "title": "Wallet"}
        candidate = {"id": 11, "type": "FOUND", "title": "Wallet"}

        results = rank_matches(source, [candidate])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["matching_details"]["text_similarity"], 1.0)
        self.assertIsNone(results[0]["matching_details"]["date_similarity"])

    def test_same_type_closed_and_same_report_candidates_are_excluded(self):
        candidates = [
            self.similar_found,
            {**self.similar_found, "id": 7, "type": "LOST"},
            {**self.similar_found, "id": 8, "status": "RESOLVED"},
            {**self.similar_found, "id": self.lost["id"]},
        ]

        results = rank_matches(self.lost, candidates)

        self.assertEqual([result["candidate"]["id"] for result in results], [2])

    def test_invalid_source_or_candidate_report_type_is_rejected(self):
        with self.assertRaises(ValueError):
            rank_matches({**self.lost, "type": "UNKNOWN"}, [self.similar_found])
        with self.assertRaises(ValueError):
            rank_matches(self.lost, [{**self.similar_found, "type": "UNKNOWN"}])

    def test_limit_returns_top_ranked_results(self):
        second = {**self.similar_found, "id": 12, "title": "Blue bottle"}

        candidates = [second, self.similar_found]
        all_results = rank_matches(self.lost, candidates)
        results = rank_matches(self.lost, candidates, limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], all_results[0])


if __name__ == "__main__":
    unittest.main()