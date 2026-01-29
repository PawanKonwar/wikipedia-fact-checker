"""
Streamlit web UI for the Wikipedia fact-checker: claim input, verdict, evidence, export, history.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from config import get_analyzer_mode, get_export_config, get_logging_config
from export_results import export_result
from fact_checker import WikipediaAPIError, WikipediaFactChecker

# Configure logging once
def _setup_logging() -> None:
    log_cfg = get_logging_config()
    level_name = str(log_cfg.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level)
    logging.getLogger(__name__).setLevel(level)


_setup_logging()
logger = logging.getLogger(__name__)

# History file (optional persistence)
HISTORY_FILE = Path("history.json")


def load_history() -> List[Dict[str, Any]]:
    """Load history from file if present."""
    if not HISTORY_FILE.exists():
        return []
    try:
        import json
        with open(HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not load history: %s", e)
        return []


def save_history(history: List[Dict[str, Any]]) -> None:
    """Append latest run to file (load, append, save)."""
    try:
        import json
        existing = load_history()
        existing.extend(history)
        # Keep last N entries
        keep = 100
        if len(existing) > keep:
            existing = existing[-keep:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not save history: %s", e)


def run_fact_check_ui(claim: str, analyzer_mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Run fact-check for claim; return result dict or None on API error."""
    checker = WikipediaFactChecker()
    try:
        result = checker.run_fact_check_with_analyzer(claim, analyzer_mode=analyzer_mode)
        result["claim"] = claim
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        return result
    except WikipediaAPIError as e:
        logger.warning("API error: %s", e)
        st.error(f"Wikipedia API error: {e}. Try again later.")
        return None


def render_history(history: List[Dict[str, Any]]) -> None:
    """Render past fact-checks in an expander."""
    if not history:
        st.info("No past fact-checks yet.")
        return
    for i, entry in enumerate(reversed(history[-20:]), 1):  # last 20
        with st.expander(f"{i}. {entry.get('claim', '')[:60]}... — {entry.get('verdict', '')}"):
            st.write("**Claim:**", entry.get("claim", ""))
            st.write("**Verdict:**", entry.get("verdict", ""))
            st.write("**When:**", entry.get("timestamp", ""))
            if entry.get("evidence"):
                st.write("**Evidence (sample):**", entry["evidence"][0][:200] + "...")


def main() -> None:
    st.set_page_config(page_title="Wikipedia Fact-Checker", page_icon="🔍")
    st.title("🔍 Wikipedia Fact-Checker Agent")
    st.write("Enter a claim to verify using Wikipedia")

    # Session state for history (in-memory)
    if "history" not in st.session_state:
        st.session_state["history"] = load_history()

    # Analyzer mode: config default or user override in sidebar
    default_mode = get_analyzer_mode()
    with st.sidebar:
        st.header("Settings")
        analyzer_mode_ui = st.selectbox(
            "Analyzer mode",
            options=["keyword", "llm"],
            index=0 if default_mode == "keyword" else 1,
            help="Keyword: fast, rule-based. LLM: semantic analysis, explanation, confidence (requires OpenAI or Ollama).",
        )

    claim: str = st.text_input(
        "Claim to fact-check:",
        placeholder="e.g., The first marathon runner died after finishing",
    )

    if claim:
        st.write(f"**Fact-checking:** '{claim}' (mode: {analyzer_mode_ui})")
        with st.spinner("Researching on Wikipedia..."):
            result = run_fact_check_ui(claim, analyzer_mode=analyzer_mode_ui)

        if result is not None:
            verdict = result["verdict"]
            evidence = result["evidence"]
            sources = result["sources"]
            explanation = result.get("explanation")
            confidence = result.get("confidence")

            st.subheader(f"Verdict: {verdict}")
            if confidence is not None:
                st.caption(f"Confidence: {confidence}%")
            if explanation:
                st.info(explanation)

            if evidence:
                st.write("**Key Evidence:**")
                for i, evidence_text in enumerate(evidence[:5], 1):
                    snippet = evidence_text[:300] + ("..." if len(evidence_text) > 300 else "")
                    st.write(f"{i}. {snippet}")

            st.write("**Sources:**")
            for i, source in enumerate(sources, 1):
                st.write(f"{i}. [{source['title']}]({source['url']})")

            # Export
            export_format = get_export_config().get("default_format", "json")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Export as JSON"):
                    path = export_result(
                        claim, verdict, evidence, sources, format="json"
                    )
                    st.success(f"Saved to {path}")
            with col2:
                if st.button("Export as CSV"):
                    path = export_result(
                        claim, verdict, evidence, sources, format="csv"
                    )
                    st.success(f"Saved to {path}")

            # Append to history
            st.session_state["history"].append(result)
            save_history([result])

    # Sidebar: history
    with st.sidebar:
        st.header("History")
        render_history(st.session_state["history"])


if __name__ == "__main__":
    main()
