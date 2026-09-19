import unittest
from tests.eval_harness import score_query_result, run_evaluation

class TestEvalHarness(unittest.TestCase):
    def test_score_query_result_hit_rank_1(self):
        query_item = {
            "id": 1,
            "query": "ঢাকা",
            "expected_keywords": ["ঢাকা"]
        }
        search_results = [
            {"title": "ঢাকা জেলার তথ্য বাতায়ন", "snippet": "ঢাকা বাংলাদেশের রাজধানী", "url": "https://dhaka.gov.bd"}
        ]
        score = score_query_result(query_item, search_results, None)
        self.assertEqual(score["reciprocal_rank"], 1.0)
        self.assertEqual(score["p@1"], 1.0)

    def test_score_query_result_kg_match(self):
        query_item = {
            "id": 2,
            "query": "ঢাকা বিশ্ববিদ্যালয়",
            "expected_keywords": ["ঢাকা বিশ্ববিদ্যালয়"]
        }
        kg = {"title": "ঢাকা বিশ্ববিদ্যালয়", "summary": "প্রাচীনতম বিশ্ববিদ্যালয়"}
        score = score_query_result(query_item, [], kg)
        self.assertTrue(score["kg_matched"])
        self.assertEqual(score["p@1"], 1.0)

    def test_run_evaluation_load(self):
        metrics = run_evaluation()
        self.assertGreater(metrics["total_queries"], 0)

if __name__ == "__main__":
    unittest.main()
