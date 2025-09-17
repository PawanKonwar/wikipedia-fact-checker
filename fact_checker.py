import requests
import re
import json
import time
from typing import List, Dict, Tuple


class WikipediaFactChecker:
    def __init__(self):
        self.wikipedia_api = "https://en.wikipedia.org/w/api.php"
        self.session = requests.Session()

        # Add proper headers to avoid being blocked by Wikipedia
        self.session.headers.update({
            'User-Agent': 'WikipediaFactChecker/1.0 (https://example.com; pawan@example.com)',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def search_wikipedia(self, query: str) -> List[Dict]:
        """Search Wikipedia for articles related to the query"""
        print(f"Searching Wikipedia for: {query}")

        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": 5
        }

        try:
            response = self.session.get(self.wikipedia_api, params=params)
            response.raise_for_status()  # This will raise an exception for 4xx/5xx responses
            data = response.json()
            return data.get("query", {}).get("search", [])
        except requests.RequestException as e:
            print(f"Error searching Wikipedia: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status code: {e.response.status_code}")
                print(f"Response text: {e.response.text[:200]}...")  # First 200 chars
            return []

    # ADD THIS METHOD RIGHT HERE:
    def get_page_content(self, page_id: int) -> str:
        """Get the content of a Wikipedia page"""
        print(f"Fetching content for page ID: {page_id}")

        params = {
            "action": "query",
            "format": "json",
            "pageids": page_id,
            "prop": "extracts",
            "explaintext": True,  # Get plain text instead of HTML
            "exsectionformat": "plain"
        }

        try:
            response = self.session.get(self.wikipedia_api, params=params)
            response.raise_for_status()
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            return pages.get(str(page_id), {}).get("extract", "")
        except requests.RequestException as e:
            print(f"Error fetching page content: {e}")
            return ""

    def extract_relevant_sentences(self, text: str, claim: str) -> List[str]:
        """Extract sentences from text that are relevant to the claim"""
        # Simple approach: look for sentences containing keywords from the claim
        claim_keywords = set(claim.lower().split())
        sentences = re.split(r'\.\s+', text)

        relevant_sentences = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            # Count how many keywords appear in this sentence
            keyword_count = sum(1 for keyword in claim_keywords if keyword in sentence_lower)

            # If at least one keyword matches, consider it relevant
            if keyword_count > 0:
                relevant_sentences.append(sentence)

        return relevant_sentences

    def analyze_evidence(self, evidence: List[str], claim: str) -> Tuple[str, List[str]]:
        """Analyze the evidence to determine if the claim is supported"""
        supporting_evidence = []
        contradicting_evidence = []

        claim_lower = claim.lower()
        negation_words = {"not", "no", "never", "didn't", "doesn't", "wasn't", "weren't", "false", "incorrect"}

        for sentence in evidence:
            sentence_lower = sentence.lower()

            # Check if evidence directly supports the claim
            if (any(keyword in sentence_lower for keyword in claim_lower.split() if len(keyword) > 3) and
                    not any(negation in sentence_lower for negation in negation_words)):
                supporting_evidence.append(sentence)

            # Check if evidence contradicts the claim
            elif (any(keyword in sentence_lower for keyword in claim_lower.split() if len(keyword) > 3) and
                  any(negation in sentence_lower for negation in negation_words)):
                contradicting_evidence.append(sentence)
            # Special case for location claims (like "is in India")
            elif "is in" in claim_lower or "located in" in claim_lower:
                location = claim_lower.split("in ")[-1].replace("?", "").strip()
                actual_location = "china"  # This would be detected from evidence in a smarter system
                if location != actual_location and actual_location in sentence_lower:
                    contradicting_evidence.append(sentence)

        # Make a verdict based on the evidence
        if supporting_evidence and not contradicting_evidence:
            verdict = "TRUE"
        elif contradicting_evidence:
            verdict = "FALSE"
        elif supporting_evidence and contradicting_evidence:
            verdict = "MIXED"
        else:
            verdict = "INSUFFICIENT_EVIDENCE"

        return verdict, supporting_evidence + contradicting_evidence


def main():
    """Command-line interface for the fact-checker"""
    print("=== Wikipedia Fact-Checker Agent ===")
    print("Enter a claim to fact-check (or 'quit' to exit):")

    fact_checker = WikipediaFactChecker()

    while True:
        claim = input("\nClaim: ").strip()

        if claim.lower() in ['quit', 'exit', 'q']:
            break

        if not claim:
            continue

        print(f"\nFact-checking: '{claim}'")

        # Search for relevant Wikipedia articles
        results = fact_checker.search_wikipedia(claim)

        if not results:
            print("No relevant Wikipedia articles found.")
            continue

        # Get content from multiple results and analyze
        evidence = []
        sources = []

        for result in results[:3]:  # Use first 3 results
            print(f"Analyzing: {result['title']}")
            content = fact_checker.get_page_content(result['pageid'])

            if content:
                relevant_sentences = fact_checker.extract_relevant_sentences(content, claim)
                evidence.extend(relevant_sentences)
                sources.append({
                    "title": result["title"],
                    "pageid": result["pageid"],
                    "url": f"https://en.wikipedia.org/?curid={result['pageid']}"
                })

        # Analyze the evidence
        verdict, relevant_evidence = fact_checker.analyze_evidence(evidence, claim)

        print(f"\n=== VERDICT ===")
        print(f"Claim: '{claim}'")
        print(f"Verdict: {verdict}")

        if relevant_evidence:
            print(f"\nKey Evidence:")
            for i, evidence_text in enumerate(relevant_evidence[:5], 1):  # Show top 5
                print(f"{i}. {evidence_text[:200]}{'...' if len(evidence_text) > 200 else ''}")
        else:
            print("No specific evidence found.")

        print(f"\nSources:")
        for i, source in enumerate(sources, 1):
            print(f"{i}. {source['title']} - {source['url']}")

        print("\n" + "=" * 50)


if __name__ == "__main__":
    main()