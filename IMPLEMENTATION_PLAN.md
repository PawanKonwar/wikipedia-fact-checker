# Wikipedia Fact-Checker — Implementation Plan

## Overview
This document outlines the step-by-step plan to complete Phase 1 enhancements and Phase 2 LLM integration.

---

## PHASE 1 — Enhancements (First Priority)

### 1.1 Code Quality
| Task | Description |
|------|-------------|
| Type hints | Add to all functions in `fact_checker.py` and `app.py` (params + return types) |
| Error handling | Wikipedia API: timeouts, rate limits (429), connection errors, empty/invalid JSON |
| Logging | Replace `print` with `logging`; log search, fetch, analyze steps; configurable level via config |

### 1.2 Configuration
| Task | Description |
|------|-------------|
| config.yaml | API base URL, timeout_seconds, max_articles, user_agent; optional verdict thresholds |
| Config loader | New `config.py`: load YAML, validate, expose typed settings; fallback defaults if file missing |

### 1.3 Features
| Task | Description |
|------|-------------|
| Export | Save result to JSON/CSV: timestamp, claim, verdict, evidence list, sources list; path configurable or default `exports/` |
| History | Streamlit: persist fact-checks in session state + optional file (e.g. `history.json`); sidebar or expander to view past claims, verdicts, timestamps |

### 1.4 Testing
| Task | Description |
|------|-------------|
| tests/ | Create `tests/` with `test_fact_checker.py` |
| Mocks | Use `unittest.mock` to mock `requests.Session.get`; fixture responses for search + page content |
| Verdict tests | Test all four verdicts: TRUE, FALSE, MIXED, INSUFFICIENT_EVIDENCE via controlled mocked data |

---

## PHASE 2 — LLM Integration

### 2.1 Architecture
| Task | Description |
|------|-------------|
| llm_analyzer.py | New module: class that takes (evidence, claim) → (verdict, explanation, confidence, citations) |
| Pluggable mode | Config: `analyzer_mode: "keyword" | "llm"`. FactChecker calls keyword or LLM analyzer based on config |
| Extend FactChecker | Optional method `fact_check_with_llm()` or inject analyzer in constructor; keep existing keyword path unchanged |

### 2.2 LLM Implementation
| Task | Description |
|------|-------------|
| Provider | Support OpenAI (GPT) and Ollama; config: `llm_provider`, `openai_model`, `ollama_model`, API keys from env |
| Semantic analysis | Prompt LLM to judge support/contradiction based on meaning; return structured output (verdict + explanation) |
| Explanations | Natural language explanation for each verdict |
| Citations | Prompt or parse to extract page/section references from Wikipedia text where possible |

### 2.3 Advanced Features
| Task | Description |
|------|-------------|
| Multi-claim | Accept list of claims; batch API calls; return list of results with optional cross-reference in explanation |
| Confidence | LLM or heuristic: add confidence percentage to verdict (e.g. TRUE 85%) |
| Cross-verification | Optional: query other Wikipedia language APIs (e.g. es, de); aggregate in explanation or separate section |

### 2.4 Deliverables
- Updated README: features, config options, env vars, usage for both modes
- requirements.txt: openai, ollama (or httpx for Ollama)
- Configuration: analyzer_mode, LLM provider settings
- Tests: mock LLM for verdict + confidence

---

## Execution Order
1. **Phase 1.2** — config.yaml + config.py (needed by 1.1)
2. **Phase 1.1** — fact_checker.py: type hints, errors, logging, use config
3. **Phase 1.1** — app.py: type hints, error handling, logging
4. **Phase 1.3** — Export (JSON/CSV) + History in Streamlit
5. **Phase 1.4** — tests/ with mocks and verdict tests
6. **Phase 2.1–2.4** — LLM module, pluggable system, README, requirements, tests
