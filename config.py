"""
Load and validate configuration from config.yaml with typed defaults.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# Defaults when config.yaml is missing or invalid
DEFAULTS: dict[str, Any] = {
    "wikipedia": {
        "base_url": "https://en.wikipedia.org/w/api.php",
        "timeout_seconds": 10,
        "max_articles": 5,
        "user_agent": "WikipediaFactChecker/1.0 (https://example.com; pawan@example.com)",
    },
    "fact_check": {
        "max_evidence_sentences": 10,
        "min_keyword_length": 3,
    },
    "export": {
        "directory": "exports",
        "default_format": "json",
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    },
    "analyzer_mode": "keyword",
    "llm": {
        "provider": "openai",
        "openai_model": "gpt-4o-mini",
        "ollama_model": "llama3.2",
        "confidence_enabled": True,
    },
}

_CONFIG: Optional[dict[str, Any]] = None
_CONFIG_PATH: Path = Path(__file__).parent / "config.yaml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override into base recursively. base is not mutated."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """Load config from YAML file and merge with defaults. Returns merged dict."""
    global _CONFIG
    path = config_path or _CONFIG_PATH
    if not path.exists():
        logging.getLogger(__name__).warning("Config file not found at %s, using defaults.", path)
        _CONFIG = dict(DEFAULTS)
        return _CONFIG

    if yaml is None:
        logging.getLogger(__name__).warning("PyYAML not installed, using defaults.")
        _CONFIG = dict(DEFAULTS)
        return _CONFIG

    try:
        with open(path, encoding="utf-8") as f:
            file_config = yaml.safe_load(f) or {}
        _CONFIG = _deep_merge(DEFAULTS, file_config)
        return _CONFIG
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).warning("Failed to load config from %s: %s. Using defaults.", path, e)
        _CONFIG = dict(DEFAULTS)
        return _CONFIG


def get_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """Return cached config or load from file."""
    global _CONFIG
    if _CONFIG is None:
        load_config(config_path)
    assert _CONFIG is not None
    return _CONFIG


def get_wikipedia_config() -> dict[str, Any]:
    """Return Wikipedia API section of config."""
    return get_config().get("wikipedia", DEFAULTS["wikipedia"])


def get_fact_check_config() -> dict[str, Any]:
    """Return fact-check behavior section."""
    return get_config().get("fact_check", DEFAULTS["fact_check"])


def get_export_config() -> dict[str, Any]:
    """Return export section."""
    return get_config().get("export", DEFAULTS["export"])


def get_logging_config() -> dict[str, Any]:
    """Return logging section."""
    return get_config().get("logging", DEFAULTS["logging"])


def get_analyzer_mode() -> str:
    """Return analyzer_mode: 'keyword' or 'llm'."""
    return get_config().get("analyzer_mode", "keyword") or "keyword"


def get_llm_config() -> dict[str, Any]:
    """Return LLM section (Phase 2)."""
    return get_config().get("llm", DEFAULTS["llm"])
