"""
Tests for fact_checker with mocked Wikipedia API and all verdict types.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fact_checker import WikipediaAPIError, WikipediaFactChecker


def _mock_wikipedia_config():
    return {
        "base_url": "https://en.wikipedia.org/w/api.php",
        "timeout_seconds": 10,
        "max_articles": 5,
        "user_agent": "WikipediaFactChecker/1.0",
    }


def _mock_fact_check_config():
    return {"max_evidence_sentences": 10, "min_keyword_length": 3}


def _mock_logging_config():
    return {"level": "INFO", "format": "%(message)s"}


@patch("fact_checker.get_fact_check_config", side_effect=_mock_fact_check_config)
@patch("fact_checker.get_wikipedia_config", side_effect=_mock_wikipedia_config)
@patch("fact_checker.get_config", return_value={})
class TestWikipediaFactChecker(unittest.TestCase):
    """Test WikipediaFactChecker with mocked config and requests."""

    def test_extract_relevant_sentences(self, *_mocks) -> None:
        checker = WikipediaFactChecker()
        text = "The marathon is a long race. Pheidippides ran to Athens. He died after the run."
        claim = "marathon runner died"
        out = checker.extract_relevant_sentences(text, claim)
        self.assertIsInstance(out, list)
        self.assertGreater(len(out), 0)
        self.assertTrue(any("died" in s.lower() or "marathon" in s.lower() for s in out))

    def test_analyze_evidence_true(self, *_mocks) -> None:
        checker = WikipediaFactChecker()
        evidence = [
            "Pheidippides ran the first marathon and died after finishing.",
            "The first marathon runner collapsed and died.",
        ]
        verdict, relevant = checker.analyze_evidence(evidence, "The first marathon runner died after finishing")
        self.assertEqual(verdict, "TRUE")
        self.assertGreater(len(relevant), 0)

    def test_analyze_evidence_false(self, *_mocks) -> None:
        checker = WikipediaFactChecker()
        evidence = [
            "The first marathon runner did not die; he survived and lived many years.",
        ]
        verdict, relevant = checker.analyze_evidence(evidence, "The first marathon runner died")
        self.assertEqual(verdict, "FALSE")
        self.assertGreater(len(relevant), 0)

    def test_analyze_evidence_mixed(self, *_mocks) -> None:
        checker = WikipediaFactChecker()
        evidence = [
            "Pheidippides died after the run.",
            "Some sources say the runner did not die and survived.",
        ]
        verdict, relevant = checker.analyze_evidence(evidence, "The marathon runner died after the run")
        self.assertEqual(verdict, "MIXED")
        self.assertGreater(len(relevant), 0)

    def test_analyze_evidence_insufficient(self, *_mocks) -> None:
        checker = WikipediaFactChecker()
        evidence = []  # No evidence
        verdict, relevant = checker.analyze_evidence(evidence, "The moon is made of cheese")
        self.assertEqual(verdict, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(len(relevant), 0)

    def test_analyze_evidence_insufficient_irrelevant(self, *_mocks) -> None:
        checker = WikipediaFactChecker()
        evidence = ["The weather today is sunny."]  # No keyword overlap with claim
        verdict, relevant = checker.analyze_evidence(evidence, "The marathon runner died")
        self.assertEqual(verdict, "INSUFFICIENT_EVIDENCE")

    @patch("fact_checker.requests.Session")
    def test_search_wikipedia_success(self, mock_session_class, *_mocks) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query": {
                "search": [
                    {"pageid": 123, "title": "Marathon"},
                    {"pageid": 456, "title": "Pheidippides"},
                ]
            }
        }
        mock_session_class.return_value.get.return_value = mock_response

        checker = WikipediaFactChecker()
        results = checker.search_wikipedia("marathon runner")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["pageid"], 123)
        self.assertEqual(results[0]["title"], "Marathon")

    @patch("fact_checker.requests.Session")
    def test_search_wikipedia_rate_limit(self, mock_session_class, *_mocks) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_session_class.return_value.get.return_value = mock_response
        mock_response.raise_for_status.side_effect = Exception("429")

        checker = WikipediaFactChecker()
        with self.assertRaises(WikipediaAPIError):
            checker.search_wikipedia("test")

    @patch("fact_checker.requests.Session")
    def test_search_wikipedia_timeout(self, mock_session_class, *_mocks) -> None:
        import requests
        mock_session_class.return_value.get.side_effect = requests.Timeout("timed out")

        checker = WikipediaFactChecker()
        with self.assertRaises(WikipediaAPIError):
            checker.search_wikipedia("test")

    @patch("fact_checker.requests.Session")
    def test_get_page_content_success(self, mock_session_class, *_mocks) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query": {
                "pages": {
                    "123": {"pageid": 123, "extract": "The marathon is a long-distance race. Pheidippides died."}
                }
            }
        }
        mock_session_class.return_value.get.return_value = mock_response

        checker = WikipediaFactChecker()
        content = checker.get_page_content(123)
        self.assertIn("marathon", content)
        self.assertIn("Pheidippides", content)

    @patch("fact_checker.requests.Session")
    def test_run_fact_check_end_to_end(self, mock_session_class, *_mocks) -> None:
        def fake_get(url, params=None, timeout=10):
            r = MagicMock()
            r.status_code = 200
            if params and params.get("list") == "search":
                r.json.return_value = {"query": {"search": [{"pageid": 100, "title": "Marathon"}]}}
            else:
                r.json.return_value = {
                    "query": {
                        "pages": {
                            "100": {"pageid": 100, "extract": "Pheidippides ran the first marathon. He died after finishing."}
                        }
                    }
                }
            return r

        mock_session_class.return_value.get.side_effect = fake_get
        mock_session_class.return_value.headers = {}

        checker = WikipediaFactChecker()
        verdict, evidence, sources = checker.run_fact_check("The first marathon runner died")
        self.assertIn(verdict, ("TRUE", "FALSE", "MIXED", "INSUFFICIENT_EVIDENCE"))
        self.assertIsInstance(evidence, list)
        self.assertIsInstance(sources, list)
        if sources:
            self.assertIn("title", sources[0])
            self.assertIn("url", sources[0])

    @patch("fact_checker.get_analyzer_mode", return_value="keyword")
    @patch("fact_checker.requests.Session")
    def test_run_fact_check_with_analyzer_returns_dict(self, mock_session_class, *_mocks) -> None:
        def fake_get(url, params=None, timeout=10):
            r = MagicMock()
            r.status_code = 200
            if params and params.get("list") == "search":
                r.json.return_value = {"query": {"search": [{"pageid": 100, "title": "Marathon"}]}}
            else:
                r.json.return_value = {
                    "query": {
                        "pages": {
                            "100": {"pageid": 100, "extract": "Pheidippides ran the first marathon. He died."}
                        }
                    }
                }
            return r

        mock_session_class.return_value.get.side_effect = fake_get
        mock_session_class.return_value.headers = {}

        checker = WikipediaFactChecker()
        result = checker.run_fact_check_with_analyzer("The first marathon runner died")
        self.assertIsInstance(result, dict)
        self.assertIn("verdict", result)
        self.assertIn("evidence", result)
        self.assertIn("sources", result)
        self.assertIn(result["verdict"], ("TRUE", "FALSE", "MIXED", "INSUFFICIENT_EVIDENCE"))


if __name__ == "__main__":
    unittest.main()
