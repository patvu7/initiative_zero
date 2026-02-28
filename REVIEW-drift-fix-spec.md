# Review: drift-fix-spec.md

**Reviewer:** Claude (automated)
**Date:** 2026-02-28
**Verdict:** Approve with required changes — 3 bugs, 4 issues to address before implementation

---

## Executive Summary

The spec is well-structured, clearly motivated, and correctly identifies the root causes of false Type 3 drift classifications. The four fixes are logically sound and the implementation order is sensible. However, I found **3 bugs** in the proposed code, **1 numbering error** in the prompt instructions, and **3 consistency issues** that should be resolved before implementation.

---

## Fix 1 — Robust Drift Classification (`external/tester.py`)

### 1.1 — `_normalize_output()` — Mostly correct, one concern

**Correct:**
- Key aliasing logic is well-designed; `key.lower().strip()` plus the alias map handles generated code returning `"Amount"`, `"amount"`, `"trade_value"`, etc.
- Boolean normalization correctly guards against converting numeric `"0"` strings in non-boolean fields (line 71 checks `canonical_key in ("tlh_flag", "wash_sale_flag", "is_valid")`).
- Decimal quantization with `ROUND_HALF_UP` to 2 decimal places is correct for financial comparisons.

**Concern — value mutation ordering (lines 61–84):**
The code first uppercases ALL string values on line 62 (`value = value.strip().upper()`), then checks for boolean conversion on lines 67–72. This *works* because `"true".upper()` → `"TRUE"` which matches the boolean check, but the flow is counterintuitive. A reader might expect boolean detection to happen on the original value. Consider adding a brief comment explaining the intentional ordering, e.g. `# Note: boolean check happens after uppercasing; "true" → "TRUE" → True`.

### 1.2 — Rewritten `classify_drift()` — Contains a bug

**BUG 1 — Fallback numeric search matches non-financial fields (lines 166–186):**

When `legacy_amount` exists but `modern_amount` is `None`, the code iterates over ALL keys in `norm_modern` looking for any value that parses as a `Decimal`:

```python
for key in norm_modern:
    try:
        from decimal import Decimal
        if Decimal(str(norm_modern[key])):
            modern_amount = norm_modern[key]
            break
    except Exception:
        continue
```

This will match `error_code: 1001`, boolean `True` (which becomes `Decimal('1')`), or any other numeric field. For example, if legacy expects `{"status": "DENIED", "payout": "4500.00", "error_code": 1001}` and modern returns `{"status": "DENIED", "error_code": 1001}` (missing payout), the fallback would pick up `error_code: 1001` as the "amount", then compute `abs(4500.00 - 1001) = 3499.00` → Type 3 Breaking. This is incorrect; it should be Type 3 because the amount is missing, not because `error_code` doesn't match.

**Fix:** Filter the fallback search to only check string-typed values from known financial key patterns:

```python
financial_key_patterns = ("amount", "payout", "value", "cost", "price", "total")
for key in norm_modern:
    if not any(p in key for p in financial_key_patterns):
        continue
    try:
        if Decimal(str(norm_modern[key])):
            modern_amount = norm_modern[key]
            break
    except Exception:
        continue
```

**Minor — redundant double-uppercasing (lines 138–139):**
After normalization, all string values are already uppercased by `_normalize_output()`. Lines 138–139 do `legacy_status.upper().strip()` again, which is unnecessary. Not a bug, but adds confusion about whether normalization is trusted.

**Minor — `<=` vs `<` threshold change (line 159):**
The current code uses `diff < 0.02` (Type 3 at exactly $0.02 difference). The spec uses `diff <= Decimal("0.02")` (Type 2 at exactly $0.02). This is a deliberate semantic change — worth calling out in the spec as intentional, since it changes classification behavior at the boundary.

### 1.3 — Import placement — Correct

The instruction to move `from decimal import Decimal, ROUND_HALF_UP` to the top of the file and remove inline imports is correct. The current `external/tester.py` has no top-level Decimal import (the only `from decimal import Decimal` is inside a string template in `build_test_harness()` on line 219, which is a different context).

**Suggestion:** Since sections 1.1 and 1.2 show code blocks WITH inline imports, and section 1.3 says to remove them, an implementer reading top-to-bottom might copy the code blocks as-is. Consider adding a note in 1.1 and 1.2 like: `# (this inline import is moved to file-level in section 1.3)`.

---

## Fix 2 — Tighten Generation Prompt (`external/generator.py`)

### 2.1 — Output format contract — Correct

The contract appended to `GENERATION_SYSTEM_PROMPT` is clear, specific, and consistent with the existing MANDATORY INTERFACE section (lines 39–46 of `generator.py`). The exact key names, value formats, and types specified match the legacy traces in `tester.py`.

### 2.2 — Format reminder — **Numbering error**

**BUG 2 — Checklist item numbering is wrong:**

The spec says to add items 8 and 9 "after item 7, before the 'Return ONLY' line." But the existing `GENERATION_USER_PROMPT` already has **8 items** (lines 61–68 of `generator.py`):

```
1. Every business rule (BR-###) must be implemented...
2. Every behavioral observation (OBS-###) should be...
3. The main processing class must have...
4. All financial values must use Decimal...
5. All thresholds must be class constants
6. Error handling must return dicts...
7. Include input validation for missing/empty required fields
8. If "SUPPLEMENTAL CONTEXT" is present...   ← already exists
```

The spec says "Add the following line to the IMPLEMENTATION CHECKLIST (after item 7, before the 'Return ONLY' line)" and numbers the new items as 8 and 9. But item 8 already exists. The new items should be numbered **9 and 10**, inserted after the existing item 8.

---

## Fix 3 — Dynamic Human Gate UI

### 3.1 — `updateDriftGate()` — Correct with minor issues

**All DOM element references are verified against `index.html`:**
- `drift-gate` → line 469 ✓
- `.human-gate-header` → line 470 ✓
- `.gate-desc` → line 472 ✓
- `drift-actions` → line 473 ✓
- `drift-decision` → line 478 ✓
- `btn-to-prod` → line 483 ✓

**All CSS classes/variables are verified against `style.css`:**
- `var(--green-tx)`, `var(--green)`, `var(--green-dim)` → lines 17–19 ✓
- `.decision-record.accepted`, `.decision-record.preserved`, `.decision-record.escalated` → lines 729–731 ✓

**Minor — redundant DOM query (lines 291–294):**
```javascript
gateHeader.textContent = '✓ Quality Gate — No Drift Detected';  // gateHeader = gate.querySelector('.human-gate-header')
gateHeader.style.color = 'var(--green-tx)';
gate.style.borderColor = 'var(--green)';
gate.querySelector('.human-gate-header').style.background = 'var(--green-dim)';     // ← same element as gateHeader
gate.querySelector('.human-gate-header').style.borderBottomColor = 'rgba(...)';     // ← same element as gateHeader
```

Lines 293–294 query `.human-gate-header` again, but `gateHeader` already IS that element. Should use `gateHeader.style.background` and `gateHeader.style.borderBottomColor` instead.

**Placement in `runTesting()` is correct:** Calling `updateDriftGate(results)` before the final `pipelineLog`/`toast` lines (881–884) works correctly. In the no-drift case, `updateDriftGate` logs `'Quality gate auto-cleared...'` first, then the outer code logs the results summary. No duplicate toasts since `updateDriftGate` doesn't call `toast()`.

### 3.2 — Update `adjudicate()` — **Missing a required change**

**BUG 3 — `decisionLabel` const not updated:**

The spec updates the `dr-header` innerHTML from `"⚠ PRESERVE_BUG"` to `"⚠ PRESERVE_LEGACY"`, but does NOT mention updating the `decisionLabel` const on line 906 of `app.js`:

```javascript
const decisionLabel = action === 'accept' ? 'ACCEPT_VARIANCE'
  : action === 'preserve' ? 'PRESERVE_BUG'   // ← still says PRESERVE_BUG
  : 'ESCALATE';
```

This `decisionLabel` is sent to the backend API (line 911: `decision: decisionLabel`) and to the pipeline log (line 925). After the spec's changes, the UI would display `"PRESERVE_LEGACY"` while the API receives `"PRESERVE_BUG"` — an inconsistency in the audit trail.

**Fix:** The spec should also update line 906 to:
```javascript
const decisionLabel = action === 'accept' ? 'ACCEPT_VARIANCE'
  : action === 'preserve' ? 'PRESERVE_LEGACY'
  : 'ESCALATE';
```

Also update the `rationale` for preserve on line 916 from `'Legacy truncation maintained for compatibility'` to something more generic like `'Legacy behavior preserved for backward compatibility'`.

**Good changes:**
- Replacing hardcoded `'BA + Tech Lead · '` with `OPERATOR.name + ' (' + OPERATOR.role + ')'` — more dynamic ✓
- Replacing `"Preserve Bug"` terminology with `"Preserve Legacy Behavior"` — more professional ✓

### 3.3 — Update Zone 5 HTML — Correct

The spec correctly identifies the hardcoded `gate-desc` on line 472 and the hardcoded buttons on lines 473–477 of `index.html`. The replacements are appropriate generic placeholders.

---

## Fix 4 — AI-Generated Test Reclassification

### 4.1 — Correct and well-reasoned

The spec correctly identifies the gap: the existing reclassification block (lines 427–432 of `tester.py`) handles types 0, 1, and 2 but has **no handler for Type 3**. Currently, Type 3 AI-generated test results pass through with the raw `classify_drift()` classification text, which could be alarming ("Breaking — different business outcome") when the "expected" output was just an AI prediction.

The proposed fix:
- Keeps Type 3 for execution failures (`"error" in modern_output`) — correct, since an execution failure is a real problem regardless of who wrote the expected output
- Downgrades other Type 3 to Type 2 with clear labeling ("Semantic — output differs from AI expectation") — correct, since AI expectations are predictions, not ground truth

**Variable scope verified:** `modern_output` is defined at lines 417–420 of the current code and is in scope at the reclassification block. ✓

---

## General Issues

### Editorial: Root cause count mismatch
The "Root Cause Analysis" section header says "Three issues compound to create false Type 3 Breaking classifications" but then lists **four** numbered items (1–4). Item 4 is about the Human Gate UI, not the classification logic. Consider rephrasing to "Three classification issues and one UI issue" or simply numbering without a count claim.

### File paths
The spec references `external/tester.py`, `static/app.js`, etc. The actual files are under the `initiative-zero/` subdirectory (`initiative-zero/external/tester.py`, etc.). The spec is implicitly relative to the project root, which is fine if the implementer knows the project structure, but could cause confusion.

### Missing: `runTesting()` toast/log interaction
In the no-drift scenario, after `updateDriftGate(results)` auto-clears the gate, the existing `runTesting()` code on line 882–884 will still execute:
```javascript
toast(driftCount > 0 ? driftCount + ' Type 2+ drift requires adjudication' : 'All tests passed — zero drift');
```
Since `driftCount` would be 0, this shows `'All tests passed — zero drift'` which is consistent with the auto-clear. ✓ However, the `pipelineLog` on line 881 would show a results summary AFTER the auto-clear log message, which reverses the natural reading order. Consider moving the `updateDriftGate(results)` call to AFTER the results `pipelineLog` line.

---

## Summary of Required Changes

| # | Severity | Fix | Issue |
|---|----------|-----|-------|
| 1 | **Bug** | 1.2 | Fallback numeric search in `classify_drift()` can match `error_code` or booleans as financial amounts. Add key-pattern filtering. |
| 2 | **Bug** | 2.2 | Checklist items numbered 8–9 but item 8 already exists. Should be 9–10, inserted after existing item 8. |
| 3 | **Bug** | 3.2 | `decisionLabel` const not updated from `'PRESERVE_BUG'` to `'PRESERVE_LEGACY'`, creating API/UI audit trail inconsistency. |
| 4 | Minor | 1.2 | Redundant `.upper().strip()` after normalization already uppercases values. |
| 5 | Minor | 3.1 | Redundant DOM query — `gate.querySelector('.human-gate-header')` used where `gateHeader` variable already exists. |
| 6 | Editorial | RCA | "Three issues" heading lists four items. |
| 7 | Suggestion | 1.1/1.2 | Add comments to inline imports noting they move to file-level per section 1.3. |

---

## Files Verified Against

| Spec Reference | Actual Path | Verified |
|---------------|-------------|----------|
| `external/tester.py` | `initiative-zero/external/tester.py` | ✓ All function names, line references, existing code snippets match |
| `external/generator.py` | `initiative-zero/external/generator.py` | ✓ Prompt strings, structure match |
| `static/app.js` | `initiative-zero/static/app.js` | ✓ `runTesting()` at L781, `adjudicate()` at L897, `escHtml()` at L1095 |
| `static/index.html` | `initiative-zero/static/index.html` | ✓ `drift-gate` at L469, hardcoded text at L472, buttons at L473–477 |
| `static/style.css` | `initiative-zero/static/style.css` | ✓ All CSS variables and class selectors exist |
| `app.py` | `initiative-zero/app.py` | ✓ `/api/testing/<run_id>/adjudicate` endpoint at L300 stores `decision` field |
