"""Given tests for the tools (Task 5, and the review-case stretch). Run from disputes/:
    python -m unittest discover -s tests -v
"""
import tempfile
import unittest
from pathlib import Path

from triage import tools


class SearchPolicyTests(unittest.TestCase):
    def test_finds_the_not_received_section(self):
        found = tools.search_policy("NOT_RECEIVED", "DSP-31")
        self.assertEqual((found["outcome"], found["section"]), ("ok", "DP-3.1"))

    def test_outage_returns_unavailable(self):
        found = tools.search_policy("NOT_RECEIVED", "DSP-34", ("search_policy:unavailable",))
        self.assertEqual(found, {"outcome": "unavailable"})

    def test_slow_search_returns_unavailable(self):
        found = tools.search_policy("NOT_RECEIVED", "DSP-34", ("search_policy:slow",))
        self.assertEqual(found, {"outcome": "unavailable"})


class OpenReviewCaseTests(unittest.TestCase):
    def test_rerun_returns_the_same_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "cases.json"
            first = tools.open_review_case("DSP-19", "FRAUD_CLAIM", store)
            second = tools.open_review_case("DSP-19", "FRAUD_CLAIM", store)
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(first["review_case_id"], second["review_case_id"])


if __name__ == "__main__":
    unittest.main()
