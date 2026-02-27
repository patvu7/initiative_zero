# Review of Recent PRs (#14, #15, #16)

**Date:** 2026-02-27
**Reviewer:** Claude (automated)
**Status:** All three PRs are functional. Application starts, routes register, and key functions execute correctly.

---

## Verification Summary

| Check | Status |
|---|---|
| All Python files compile | PASS |
| Flask app imports successfully | PASS |
| All 20 routes register | PASS |
| HTML serves with all coexistence simulator elements | PASS |
| Coexistence endpoint returns 404 for missing run | PASS |
| PR #14 `build_enrichment_section()` handles empty/populated metrics | PASS |
| PR #15 prompt template formats without errors | PASS |
| PR #16 imports (LEGACY_BEHAVIORS, build_test_harness, classify_drift, execute_python) | PASS |
| Database schema matches code expectations | PASS |

---

## PR #16 — Add Live Coexistence Simulator to Zone 6

**Commit:** d71ceca | **Files:** app.py, static/app.js, static/index.html, static/style.css (+233, -21)

Replaces the static ASCII coexistence diagram with an interactive simulator. Users can select a transaction, fire it through both legacy and modern code paths, and see a drift comparison.

### Findings

| Severity | Issue |
|---|---|
| Medium | `app.py:289` — `request.json` can be `None` if no JSON body sent, causing `AttributeError` on `.get()` |
| Medium | `app.py:310-318` — No `try/except` around `build_test_harness`/`execute_python` calls. Other endpoints (e.g., testing) wrap execution in try/except. |
| Medium | `app.js:723-772` — Rapid re-clicks during the 700ms animation window can stack `setTimeout` callbacks. Timeout IDs are not tracked/cleared. |
| Low | `app.py:290` — `test_index` type not validated; non-integer values cause `TypeError` |
| Low | `app.py:306` — Negative `test_index` not rejected (Python allows negative list indexing) |
| Low | `app.py:327-328` — Hardcoded latency values (340ms, 12ms) never vary |
| Low | `app.js:717` — No `state.runId` null guard before API call |

### Positives
- All 18 DOM ID references and 2 querySelector references are correct — zero broken selectors
- `escHtml()` is correctly applied to all user-facing data in innerHTML
- CSS is clean and well-organized with proper use of CSS custom properties

---

## PR #15 — Replace Code Generation Prompts with Richer Versions

**Commit:** 119be5b | **Files:** external/generator.py (+41, -14)

Rewrites `GENERATION_SYSTEM_PROMPT` and `GENERATION_USER_PROMPT` with structured sections (CRITICAL CONSTRAINTS, CODE QUALITY STANDARDS, MANDATORY INTERFACE, IMPLEMENTATION CHECKLIST).

### Findings

| Severity | Issue |
|---|---|
| High | `generator.py:101` — `max_tokens=4000` is likely too low for the richer prompts. The new prompts demand dataclasses, type hints, docstrings per business rule, input validation, error handling, and class constants. Truncated output would produce broken code that fails all tests. Consider increasing to 8192+. |
| Medium | `generator.py:32` — `ROUND_HALF_UP` instruction conflicts with legacy test data. Legacy expects truncation behavior (e.g., `99.99` for `99.995`) while `ROUND_HALF_UP` produces `100.00`. This creates predictable drift in test results. |
| Low | `generator.py:42-43` — "string values" instruction conflicts with boolean `tlh_flag: True` in test expectations |

### Positives
- Clear, structured prompt format with scannable section headers
- `MANDATORY INTERFACE` section correctly specifies the `process(self, input_data: dict) -> dict` contract
- `{requirements_text}` placeholder is correctly preserved and formatted
- `SUPPLEMENTAL CONTEXT` reference aligns with PR #14's enrichment output

---

## PR #14 — Add Enriched Requirements Document with Zone 2 Analysis Context

**Commit:** bfb051f | **Files:** internal/extractor.py (+135)

Adds `build_enrichment_section()` that reads Zone 2 analysis metrics and appends a technology-agnostic supplemental context section to the requirements document.

### Findings

| Severity | Issue |
|---|---|
| Low | `extractor.py:165` — Case-sensitive `"Good" in n` filter could miss lowercase variants from LLM output |
| Low | `extractor.py:219-220` — Silent `pass` on JSON parse errors. Consider logging for observability. |
| Very Low | `extractor.py:219-220` — `AttributeError` not caught if `json.loads()` returns non-dict type |

### Positives
- Defensive coding throughout: `.get()` with defaults, `isinstance()` type checks, emptiness guards
- Correctly handles missing analysis data (no analysis row, NULL metrics, empty metrics)
- Clean integration into `run_extraction()` — uses same DB connection, appends only if enrichment is non-empty
- All sections conditionally included — empty data produces no output

---

## Recommendations

1. **Increase `max_tokens`** in `generator.py:101` from 4000 to at least 8192 — this is the highest-risk item
2. **Add `try/except`** around the coexistence simulation execution in `app.py:310-318`
3. **Validate `request.json`** is not `None` in the coexistence endpoint
4. **Clear stacked timeouts** in `app.js` when `runCoexSimulation()` is re-invoked
5. **Consider logging** enrichment parse failures in `extractor.py:219` for production observability
