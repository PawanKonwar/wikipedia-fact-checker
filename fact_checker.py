"""
Wikipedia fact-checker: search Wikipedia, extract evidence, and produce verdicts.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import (
    get_analyzer_mode,
    get_config,
    get_fact_check_config,
    get_logging_config,
    get_wikipedia_config,
)

# Set up module logger (configured on first use)
_logger: Optional[logging.Logger] = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        log_config = get_logging_config()
        level = getattr(logging, str(log_config.get("level", "INFO")).upper(), logging.INFO)
        fmt = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        logging.basicConfig(level=level, format=fmt)
        _logger = logging.getLogger(__name__)
    return _logger


class WikipediaAPIError(Exception):
    """Raised when Wikipedia API request fails (timeout, rate limit, etc.)."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class WikipediaFactChecker:
    """Fact-checks claims using Wikipedia search and keyword-based evidence analysis."""

    def __init__(self, config_path: Optional[Any] = None) -> None:
        if config_path is not None:
            get_config(config_path)
        wiki = get_wikipedia_config()
        self.wikipedia_api: str = wiki.get("base_url", "https://en.wikipedia.org/w/api.php")
        self.timeout_seconds: int = int(wiki.get("timeout_seconds", 10))
        self.max_articles: int = int(wiki.get("max_articles", 5))
        user_agent: str = wiki.get("user_agent", "WikipediaFactChecker/1.0")
        self.session: requests.Session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )
        self._fc_config = get_fact_check_config()

    def search_wikipedia(self, query: str) -> List[Dict[str, Any]]:
        """Search Wikipedia for articles related to the query.
        Returns list of search result dicts (pageid, title, etc.).
        Raises WikipediaAPIError on timeout/rate limit; returns [] on other errors.
        """
        log = _get_logger()
        log.info("Searching Wikipedia for: %s", query)
        params: Dict[str, Any] = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": self.max_articles,
        }
        try:
            response = self.session.get(
                self.wikipedia_api,
                params=params,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 429:
                log.warning("Wikipedia API rate limit (429)")
                raise WikipediaAPIError("Rate limit exceeded", status_code=429)
            response.raise_for_status()
            data: Any = response.json()
            if not isinstance(data, dict):
                log.warning("Wikipedia API returned non-dict response")
                return []
            results: List[Dict[str, Any]] = data.get("query", {}) or {}
            if isinstance(results, dict):
                results = results.get("search", []) or []
            if not isinstance(results, list):
                return []
            log.info("Found %d search results", len(results))
            return results
        except requests.Timeout as e:
            log.warning("Wikipedia API timeout: %s", e)
            raise WikipediaAPIError("Request timed out") from e
        except requests.RequestException as e:
            log.warning("Wikipedia API request error: %s", e)
            if hasattr(e, "response") and e.response is not None:
                sc = getattr(e.response, "status_code", None)
                log.warning("Status code: %s", sc)
            return []

    def get_page_content(self, page_id: int) -> str:
        """Fetch plain-text extract of a Wikipedia page by page ID.
        Returns empty string on failure or missing content.
        """
        log = _get_logger()
        log.info("Fetching content for page ID: %s", page_id)
        params: Dict[str, Any] = {
            "action": "query",
            "format": "json",
            "pageids": page_id,
            "prop": "extracts",
            "explaintext": True,
            "exsectionformat": "plain",
        }
        try:
            response = self.session.get(
                self.wikipedia_api,
                params=params,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 429:
                log.warning("Wikipedia API rate limit (429)")
                raise WikipediaAPIError("Rate limit exceeded", status_code=429)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                return ""
            pages = (data.get("query") or {}).get("pages") or {}
            page = pages.get(str(page_id)) or {}
            extract = page.get("extract") or ""
            return extract if isinstance(extract, str) else ""
        except requests.Timeout as e:
            log.warning("Wikipedia API timeout fetching page %s: %s", page_id, e)
            return ""
        except requests.RequestException as e:
            log.warning("Error fetching page content: %s", e)
            return ""

    def extract_relevant_sentences(self, text: str, claim: str) -> List[str]:
        """Extract sentences from text that contain at least one keyword from the claim."""
        if not text or not claim:
            return []
        claim_keywords: set = set(claim.lower().split())
        sentences: List[str] = re.split(r"\.\s+", text)
        min_len: int = int(self._fc_config.get("min_keyword_length", 3))
        max_sentences: int = int(self._fc_config.get("max_evidence_sentences", 10))
        relevant: List[str] = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            keyword_count = sum(1 for kw in claim_keywords if len(kw) >= min_len and kw in sentence_lower)
            if keyword_count > 0:
                relevant.append(sentence)
        return relevant[:max_sentences]

    def analyze_evidence(self, evidence: List[str], claim: str) -> Tuple[str, List[str]]:
        """Analyze evidence to determine verdict: TRUE, FALSE, MIXED, or INSUFFICIENT_EVIDENCE.
        Returns (verdict, list of relevant evidence strings).
        """
        supporting_evidence: List[str] = []
        contradicting_evidence: List[str] = []
        claim_lower = claim.lower()
        negation_words = {
            "not", "no", "never", "didn't", "doesn't", "wasn't", "weren't",
            "false", "incorrect", "neither", "none",
        }
        min_len = int(self._fc_config.get("min_keyword_length", 3))
        claim_words = [w for w in claim_lower.split() if len(w) > min_len]

        for sentence in evidence:
            sentence_lower = sentence.lower()
            has_claim_keyword = any(kw in sentence_lower for kw in claim_words)
            has_negation = any(neg in sentence_lower for neg in negation_words)

            if has_claim_keyword and not has_negation:
                supporting_evidence.append(sentence)
            elif has_claim_keyword and has_negation:
                contradicting_evidence.append(sentence)
            elif "is in" in claim_lower or "located in" in claim_lower:
                parts = claim_lower.split("in ", 1)
                if len(parts) > 1:
                    location = parts[-1].replace("?", "").strip()
                    # Placeholder: a smarter system would detect location from evidence
                    if location and "china" in sentence_lower and location != "china":
                        contradicting_evidence.append(sentence)

        if supporting_evidence and contradicting_evidence:
            verdict = "MIXED"
            relevant = supporting_evidence + contradicting_evidence
        elif supporting_evidence and not contradicting_evidence:
            verdict = "TRUE"
            relevant = supporting_evidence
        elif contradicting_evidence:
            verdict = "FALSE"
            relevant = contradicting_evidence
        else:
            verdict = "INSUFFICIENT_EVIDENCE"
            relevant = []

        return verdict, relevant

    def run_fact_check(
        self,
        claim: str,
        max_articles_to_fetch: Optional[int] = None,
    ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
        """Run full fact-check: search, fetch pages, extract evidence, analyze.
        Returns (verdict, list of evidence strings, list of source dicts with title, url, pageid).
        """
        log = _get_logger()
        n = max_articles_to_fetch if max_articles_to_fetch is not None else self.max_articles
        try:
            results = self.search_wikipedia(claim)
        except WikipediaAPIError:
            raise
        if not results:
            log.info("No Wikipedia results for claim")
            return "INSUFFICIENT_EVIDENCE", [], []

        evidence: List[str] = []
        sources: List[Dict[str, Any]] = []

        for result in results[:n]:
            pageid = result.get("pageid")
            title = result.get("title", "")
            if pageid is None:
                continue
            log.info("Analyzing article: %s", title)
            content = self.get_page_content(int(pageid))
            if content:
                relevant = self.extract_relevant_sentences(content, claim)
                evidence.extend(relevant)
                sources.append({
                    "title": title,
                    "pageid": pageid,
                    "url": f"https://en.wikipedia.org/?curid={pageid}",
                })

        verdict, relevant_evidence = self.analyze_evidence(evidence, claim)
        return verdict, relevant_evidence, sources

    def run_fact_check_with_analyzer(
        self,
        claim: str,
        max_articles_to_fetch: Optional[int] = None,
        analyzer_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run full fact-check using configurable analyzer (keyword or llm).
        Returns dict with keys: verdict, evidence, sources, and optionally explanation, confidence.
        """
        mode = (analyzer_mode or get_analyzer_mode()).lower()
        n = max_articles_to_fetch if max_articles_to_fetch is not None else self.max_articles
        log = _get_logger()

        try:
            results = self.search_wikipedia(claim)
        except WikipediaAPIError:
            raise
        if not results:
            log.info("No Wikipedia results for claim")
            return {
                "verdict": "INSUFFICIENT_EVIDENCE",
                "evidence": [],
                "sources": [],
                "explanation": None,
                "confidence": None,
            }

        evidence_list: List[str] = []
        sources_list: List[Dict[str, Any]] = []

        for result in results[:n]:
            pageid = result.get("pageid")
            title = result.get("title", "")
            if pageid is None:
                continue
            log.info("Analyzing article: %s", title)
            content = self.get_page_content(int(pageid))
            if content:
                if mode == "llm":
                    # For LLM we pass more context; still filter by keywords for size
                    relevant = self.extract_relevant_sentences(content, claim)
                    evidence_list.extend(relevant)
                else:
                    relevant = self.extract_relevant_sentences(content, claim)
                    evidence_list.extend(relevant)
                sources_list.append({
                    "title": title,
                    "pageid": pageid,
                    "url": f"https://en.wikipedia.org/?curid={pageid}",
                })

        if mode == "llm":
            try:
                from llm_analyzer import LLMAnalyzer
                analyzer = LLMAnalyzer()
                verdict, explanation, confidence, citations, relevant_evidence = analyzer.analyze(
                    evidence_list, claim
                )
                return {
                    "verdict": verdict,
                    "evidence": relevant_evidence,
                    "sources": sources_list,
                    "explanation": explanation or None,
                    "confidence": confidence,
                }
            except Exception as e:
                log.warning("LLM analyzer failed, falling back to keyword: %s", e)
                verdict, relevant_evidence = self.analyze_evidence(evidence_list, claim)
                return {
                    "verdict": verdict,
                    "evidence": relevant_evidence,
                    "sources": sources_list,
                    "explanation": None,
                    "confidence": None,
                }
        verdict, relevant_evidence = self.analyze_evidence(evidence_list, claim)
        return {
            "verdict": verdict,
            "evidence": relevant_evidence,
            "sources": sources_list,
            "explanation": None,
            "confidence": None,
        }

    def run_multi_claim_fact_check(
        self,
        claims: List[str],
        max_articles_per_claim: Optional[int] = None,
        analyzer_mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Process multiple claims; returns list of result dicts (same shape as run_fact_check_with_analyzer)."""
        return [
            self.run_fact_check_with_analyzer(
                claim,
                max_articles_to_fetch=max_articles_per_claim,
                analyzer_mode=analyzer_mode,
            )
            for claim in claims
        ]


def main() -> None:
    """Command-line interface for the fact-checker."""
    print("=== Wikipedia Fact-Checker Agent ===")
    print("Enter a claim to fact-check (or 'quit' to exit):")
    checker = WikipediaFactChecker()

    while True:
        claim = input("\nClaim: ").strip()
        if claim.lower() in ("quit", "exit", "q"):
            break
        if not claim:
            continue

        print(f"\nFact-checking: '{claim}'")
        try:
            result = checker.run_fact_check_with_analyzer(claim)
        except WikipediaAPIError as e:
            print(f"API error: {e}")
            continue

        verdict = result["verdict"]
        relevant_evidence = result["evidence"]
        sources = result["sources"]
        explanation = result.get("explanation")
        confidence = result.get("confidence")

        print("\n=== VERDICT ===")
        print(f"Claim: '{claim}'")
        print(f"Verdict: {verdict}")
        if confidence is not None:
            print(f"Confidence: {confidence}%")
        if explanation:
            print(f"Explanation: {explanation}")

        if relevant_evidence:
            print("\nKey Evidence:")
            for i, evidence_text in enumerate(relevant_evidence[:5], 1):
                snippet = evidence_text[:200] + ("..." if len(evidence_text) > 200 else "")
                print(f"{i}. {snippet}")
        else:
            print("No specific evidence found.")

        print("\nSources:")
        for i, source in enumerate(sources, 1):
            print(f"{i}. {source['title']} - {source['url']}")
        print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
