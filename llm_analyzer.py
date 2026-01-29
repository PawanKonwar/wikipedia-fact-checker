"""
LLM-based evidence analyzer: semantic analysis, natural language explanations, confidence scores.
Supports OpenAI (GPT) and Ollama; configurable via config.yaml and environment variables.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from config import get_llm_config

# Load .env from project root so OPENAI_API_KEY is available
load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)

# Verdicts aligned with keyword analyzer
VERDICTS = ("TRUE", "FALSE", "MIXED", "INSUFFICIENT_EVIDENCE")

SYSTEM_PROMPT = """You are a fact-checking assistant. Given a CLAIM and EVIDENCE excerpts from Wikipedia, determine whether the evidence supports, contradicts, or is mixed/insufficient regarding the claim.

Respond with a JSON object only, no other text:
{
  "verdict": "TRUE" | "FALSE" | "MIXED" | "INSUFFICIENT_EVIDENCE",
  "explanation": "One or two sentences explaining your verdict in plain language.",
  "confidence": 0-100,
  "citations": ["quote or phrase from evidence that supports your verdict", "..."]
}

- TRUE: evidence clearly supports the claim.
- FALSE: evidence clearly contradicts the claim.
- MIXED: some evidence supports and some contradicts.
- INSUFFICIENT_EVIDENCE: evidence does not clearly address the claim.

Be concise. Citations should be short excerpts from the provided evidence."""


def _build_user_message(claim: str, evidence: List[str]) -> str:
    evidence_blob = "\n\n".join(f"[{i+1}] {e}" for i, e in enumerate(evidence[:20]))
    return f"CLAIM: {claim}\n\nEVIDENCE:\n{evidence_blob}\n\nRespond with JSON only."


def _parse_llm_response(text: str) -> Tuple[str, str, int, List[str]]:
    """Parse JSON from LLM response; return (verdict, explanation, confidence, citations)."""
    verdict = "INSUFFICIENT_EVIDENCE"
    explanation = ""
    confidence = 0
    citations: List[str] = []
    # Try to extract JSON block
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start:end])
            verdict = str(obj.get("verdict", verdict)).upper()
            if verdict not in VERDICTS:
                verdict = "INSUFFICIENT_EVIDENCE"
            explanation = str(obj.get("explanation", ""))
            confidence = int(obj.get("confidence", 0))
            if confidence < 0:
                confidence = 0
            elif confidence > 100:
                confidence = 100
            raw_cites = obj.get("citations", [])
            if isinstance(raw_cites, list):
                citations = [str(c).strip() for c in raw_cites if c][:5]
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("LLM response parse error: %s", e)
    return verdict, explanation, confidence, citations


def _call_openai(claim: str, evidence: List[str], model: str, api_key: Optional[str]) -> str:
    """Call OpenAI Chat Completions; return assistant message content.
    Uses OpenAI API v1.x+ syntax only (no deprecated 'proxies' parameter).
    For proxy support, set HTTP_PROXY/HTTPS_PROXY or pass http_client=httpx.Client(proxy=...).
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. pip install openai")
    try:
        import httpx
    except ImportError:
        httpx = None  # type: ignore[assignment]
    # OPENAI_API_KEY can be set in .env (loaded above via load_dotenv) or in the process environment
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set and no api_key passed")
    # Build only kwargs supported by OpenAI Client v1.x (no 'proxies' — use http_client for proxy)
    client_kwargs: Dict[str, Any] = {"api_key": key}
    if httpx is not None:
        client_kwargs["http_client"] = httpx.Client()
    client = OpenAI(**client_kwargs)
    user_msg = _build_user_message(claim, evidence)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=500,
    )
    msg = response.choices[0].message
    return (msg.content or "").strip()


def _call_ollama(claim: str, evidence: List[str], model: str) -> str:
    """Call Ollama chat; return assistant message content."""
    try:
        from ollama import chat
    except ImportError:
        raise RuntimeError("ollama package not installed. pip install ollama")
    user_msg = _build_user_message(claim, evidence)
    response = chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    return (response.message.content or "").strip()


class LLMAnalyzer:
    """Analyze evidence using an LLM (OpenAI or Ollama) for semantic verdict and explanation."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ) -> None:
        cfg = get_llm_config()
        self.provider: str = (provider or cfg.get("provider", "openai")).lower()
        if self.provider == "openai":
            self.model = model or cfg.get("openai_model", "gpt-4o-mini")
        else:
            self.model = model or cfg.get("ollama_model", "llama3.2")
        self.openai_api_key: Optional[str] = openai_api_key
        self.confidence_enabled: bool = bool(cfg.get("confidence_enabled", True))

    def analyze(
        self,
        evidence: List[str],
        claim: str,
    ) -> Tuple[str, str, int, List[str], List[str]]:
        """
        Run LLM analysis on evidence for the claim.
        Returns (verdict, explanation, confidence, citations, relevant_evidence).
        relevant_evidence is the same as input evidence when using LLM (no keyword filter).
        """
        if not evidence:
            return (
                "INSUFFICIENT_EVIDENCE",
                "No evidence was provided to evaluate the claim.",
                0,
                [],
                [],
            )
        try:
            if self.provider == "openai":
                raw = _call_openai(claim, evidence, self.model, self.openai_api_key)
            else:
                raw = _call_ollama(claim, evidence, self.model)
        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            return (
                "INSUFFICIENT_EVIDENCE",
                f"Analysis unavailable: {e}",
                0,
                [],
                evidence,
            )
        verdict, explanation, confidence, citations = _parse_llm_response(raw)
        if not self.confidence_enabled:
            confidence = 0
        return verdict, explanation, confidence, citations, evidence


def extract_citations_from_text(text: str) -> List[str]:
    """Heuristic: extract sentence-like snippets that might reference sources (e.g. 'According to...')."""
    sentences = re.split(r"[.!?]\s+", text)
    out = []
    for s in sentences:
        s = s.strip()
        if not s or len(s) < 20:
            continue
        lower = s.lower()
        if "according to" in lower or "stated" in lower or "reported" in lower or "source" in lower:
            out.append(s)
    return out[:5]
