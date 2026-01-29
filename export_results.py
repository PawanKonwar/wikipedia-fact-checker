"""
Export fact-check results to JSON or CSV with timestamp, claim, verdict, evidence, sources.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import get_export_config


def _ensure_export_dir() -> Path:
    cfg = get_export_config()
    directory = cfg.get("directory", "exports")
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _result_payload(
    claim: str,
    verdict: str,
    evidence: List[str],
    sources: List[Dict[str, Any]],
    timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:
    ts = timestamp or datetime.now(timezone.utc)
    return {
        "timestamp": ts.isoformat(),
        "claim": claim,
        "verdict": verdict,
        "evidence": evidence,
        "sources": sources,
    }


def export_json(
    claim: str,
    verdict: str,
    evidence: List[str],
    sources: List[Dict[str, Any]],
    filepath: Optional[Path] = None,
    timestamp: Optional[datetime] = None,
) -> Path:
    """Write result to a JSON file. Returns path of written file."""
    directory = _ensure_export_dir()
    ts = timestamp or datetime.now(timezone.utc)
    if filepath is None:
        safe_claim = "".join(c if c.isalnum() or c in " -_" else "_" for c in claim[:50])
        filepath = directory / f"fact_check_{ts.strftime('%Y%m%d_%H%M%S')}_{safe_claim}.json"
    payload = _result_payload(claim, verdict, evidence, sources, timestamp)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return filepath


def export_csv(
    claim: str,
    verdict: str,
    evidence: List[str],
    sources: List[Dict[str, Any]],
    filepath: Optional[Path] = None,
    timestamp: Optional[datetime] = None,
) -> Path:
    """Write result to a CSV file (one row summary + evidence/sources as concatenated strings). Returns path."""
    directory = _ensure_export_dir()
    ts = timestamp or datetime.now(timezone.utc)
    if filepath is None:
        safe_claim = "".join(c if c.isalnum() or c in " -_" else "_" for c in claim[:50])
        filepath = directory / f"fact_check_{ts.strftime('%Y%m%d_%H%M%S')}_{safe_claim}.csv"
    payload = _result_payload(claim, verdict, evidence, sources, timestamp)
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "claim", "verdict", "evidence", "sources"])
        evidence_str = " | ".join(evidence) if evidence else ""
        sources_str = " | ".join(
            s.get("title", "") + " (" + s.get("url", "") + ")" for s in sources
        ) if sources else ""
        writer.writerow([
            payload["timestamp"],
            claim,
            verdict,
            evidence_str,
            sources_str,
        ])
    return filepath


def export_result(
    claim: str,
    verdict: str,
    evidence: List[str],
    sources: List[Dict[str, Any]],
    format: str = "json",
    filepath: Optional[Path] = None,
    timestamp: Optional[datetime] = None,
) -> Path:
    """Export to JSON or CSV based on format. Returns path of written file."""
    format = (format or "json").lower()
    if format == "csv":
        return export_csv(claim, verdict, evidence, sources, filepath, timestamp)
    return export_json(claim, verdict, evidence, sources, filepath, timestamp)
