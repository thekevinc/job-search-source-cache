import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from refresh_sources import job_titles, refresh


NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


class RefreshTests(unittest.TestCase):
    def test_job_title_shapes(self):
        self.assertEqual(job_titles("greenhouse", {"jobs": [{"title": "Software Engineer"}]}), ["Software Engineer"])
        self.assertEqual(job_titles("lever", [{"text": "Platform Engineer"}]), ["Platform Engineer"])
        self.assertEqual(job_titles("ashby", {"jobs": [{"title": "Backend Engineer"}]}), ["Backend Engineer"])

    @patch("refresh_sources.request_json")
    def test_relevant_candidate_is_added(self, request_json):
        request_json.return_value = {"jobs": [{"title": "Senior Software Engineer"}]}
        result = refresh({"sources": []}, {("greenhouse", "example-co")}, NOW)
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["board"], "example-co")
        self.assertEqual(result["sources"][0]["active_until"], "2026-11-10T12:00:00Z")

    @patch("refresh_sources.request_json")
    def test_irrelevant_candidate_is_not_added(self, request_json):
        request_json.return_value = {"jobs": [{"title": "Account Executive"}]}
        result = refresh({"sources": []}, {("greenhouse", "example-co")}, NOW)
        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
