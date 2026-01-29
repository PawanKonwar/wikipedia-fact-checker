# Wikipedia Fact-Checker

[![Tests](https://github.com/pawankonwar/wikipedia-fact-checker/actions/workflows/test.yml/badge.svg)](https://github.com/pawankonwar/wikipedia-fact-checker/actions/workflows/test.yml)

A Python AI agent that fact-checks claims using Wikipedia. Supports **keyword-based** (Phase 1) and **LLM-based** (Phase 2) analysis with configurable settings, export, and history.

---

## Setup

### Prerequisites

- **Python 3.8+**
- pip

### Installation

```bash
git clone <repo-url>
cd wikipedia-fact-checker
pip install -r requirements.txt
```

### Setup by mode

#### Keyword mode (default)

- No extra setup. Uses Wikipedia API only.
- Optional: edit `config.yaml` for timeouts, number of articles, logging level.

#### LLM mode (OpenAI)

1. Install dependencies (already in `requirements.txt`): `openai`, `python-dotenv`.
2. Create a `.env` file in the project root:
   ```bash
   OPENAI_API_KEY=sk-your-openai-api-key
   ```
3. In `config.yaml`, set `analyzer_mode: "llm"` and under `llm` set `provider: "openai"` (optional; default is already `openai`).
4. Run the app or CLI; the LLM analyzer will use your API key from `.env`.

#### LLM mode (Ollama, local)

1. Install [Ollama](https://ollama.com) and pull a model, e.g.:
   ```bash
   ollama pull llama3.2
   ```
2. Install the Python client: `pip install ollama` (in `requirements.txt`).
3. In `config.yaml`, set `analyzer_mode: "llm"` and under `llm` set `provider: "ollama"`. Optionally set `ollama_model: "llama3.2"`.
4. Run the app or CLI; the LLM analyzer will call your local Ollama server.

---

## Configuration

- **`config.yaml`** — Wikipedia API (base URL, timeout, max articles, user agent), fact-check behavior (max evidence sentences, min keyword length), export (directory, default format), logging (level, format), analyzer mode, and LLM settings (provider, models, confidence).
- **Analyzer mode:** `keyword` (default) or `llm`.
- **LLM:** `config.yaml` → `llm.provider` (`openai` | `ollama`), `llm.openai_model`, `llm.ollama_model`, `llm.confidence_enabled`. For OpenAI, use `.env` with `OPENAI_API_KEY`.

See `config.yaml` in the project root for all options.

---

## Usage

### Web UI (Streamlit)

```bash
streamlit run app.py
```

- Enter a claim to fact-check.
- **Settings (sidebar):** choose **Keyword** or **LLM** analyzer.
- View verdict, evidence, and sources; in LLM mode also **explanation** and **confidence**.
- **Export:** save the current result as JSON or CSV.
- **History:** view past fact-checks in the sidebar (persisted in `history.json` when present).

### Command line

```bash
python fact_checker.py
```

- Prompts for claims; type `quit` or `exit` to stop.
- Uses analyzer mode from `config.yaml` (keyword or llm).
- Prints verdict, evidence, sources; in LLM mode also confidence and explanation.

### Programmatic API

```python
from fact_checker import WikipediaFactChecker

checker = WikipediaFactChecker()

# Single claim (returns dict: verdict, evidence, sources, explanation?, confidence?)
result = checker.run_fact_check_with_analyzer("The first marathon runner died")

# Keyword-only (returns tuple: verdict, evidence, sources)
verdict, evidence, sources = checker.run_fact_check("Paris is the capital of France")

# Multi-claim (list of result dicts)
results = checker.run_multi_claim_fact_check(
    ["Claim A.", "Claim B."],
    analyzer_mode="llm"
)
```

---

## Features

### Core

- **Wikipedia integration** — Search and fetch article content via the Wikipedia API; configurable base URL, timeout, max articles, user agent.
- **Verdicts** — **TRUE**, **FALSE**, **MIXED**, **INSUFFICIENT_EVIDENCE** (aligned across keyword and LLM analyzers).
- **Error handling** — Timeouts, rate limits (429), connection and JSON errors; `WikipediaAPIError` for API failures.
- **Logging** — Configurable level and format; no print statements in library code.
- **Type hints** — Full type hints in `fact_checker.py`, `app.py`, `config.py`, `export_results.py`, `llm_analyzer.py`.

### Keyword mode (Phase 1)

- Keyword-based evidence extraction (configurable min keyword length, max evidence sentences).
- Negation and location-aware logic for supporting/contradicting evidence.
- Configurable via `config.yaml` (fact_check section).

### LLM mode (Phase 2)

- **Pluggable analyzer** — Choose **keyword** or **llm** in config or Streamlit sidebar.
- **OpenAI (GPT)** or **Ollama** (local) — configurable provider and model names.
- **Semantic analysis** — LLM judges support/contradiction from meaning, not just keywords.
- **Natural language explanation** — Short explanation for each verdict.
- **Confidence score** — 0–100 (optional via config).
- **Citations** — Short excerpts from evidence in the LLM response.
- **Multi-claim** — `run_multi_claim_fact_check(claims)` for multiple claims in one call.
- **API key** — OpenAI key from `.env` via `python-dotenv`; no `proxies` parameter (OpenAI client v1.x compatible).

### Export & history

- **Export** — Save result to JSON or CSV (timestamp, claim, verdict, evidence, sources); directory and default format in `config.yaml`.
- **History** — Streamlit: in-memory + optional `history.json`; sidebar shows last fact-checks.

### Testing

- **`tests/test_fact_checker.py`** — Mocked Wikipedia API; no network required.
- Covers all verdict types, search/page fetch, timeout and rate-limit handling, `run_fact_check` and `run_fact_check_with_analyzer`.

---

## Testing

```bash
pytest tests/ -v
```

- Uses mocked Wikipedia API responses.
- Covers verdicts (TRUE, FALSE, MIXED, INSUFFICIENT_EVIDENCE), API errors, and analyzer return shape.

---

## Project structure

| Path | Description |
|------|-------------|
| `app.py` | Streamlit UI: claim input, verdict, evidence, sources, export, history, analyzer mode selector |
| `config.py` | Load and merge `config.yaml` with defaults; typed helpers for each config section |
| `config.yaml` | All settings: Wikipedia, fact-check, export, logging, analyzer mode, LLM |
| `export_results.py` | Export result to JSON/CSV with timestamp, claim, verdict, evidence, sources |
| `fact_checker.py` | Wikipedia client, keyword analyzer, `run_fact_check` / `run_fact_check_with_analyzer` / `run_multi_claim_fact_check` |
| `llm_analyzer.py` | LLM analyzer (OpenAI/Ollama), semantic verdict, explanation, confidence, citations |
| `requirements.txt` | Dependencies: requests, streamlit, PyYAML, pytest, openai, ollama, python-dotenv |
| `tests/test_fact_checker.py` | Tests with mocked API |

---

## Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required for LLM mode when using OpenAI; load from `.env` via python-dotenv |

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.
