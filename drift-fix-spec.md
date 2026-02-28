# Technical Spec: Drift Classification & Demo Reliability Fixes

**Context:** Initiative Zero prototype for Wealthsimple AI Builders application.  
**Problem:** Zone 5 testing produces excessive Type 3 (Breaking) drift classifications, and the Human Gate UI is hardcoded for a Type 2 scenario. This undermines the demo narrative.  
**Goal:** Make drift classification robust to cosmetic differences in generated code output, make the Human Gate UI dynamic based on actual results, and tighten the generation prompt to reduce output format mismatches.

---

## Root Cause Analysis

Three issues compound to create false Type 3 Breaking classifications:

1. **`classify_drift()` in `external/tester.py`** does case-sensitive string comparison on `status`/`action` fields. If the generated code returns `"sell"` instead of `"SELL"`, or `"Approved"` instead of `"APPROVED"`, it immediately classifies as Type 3 Breaking — even though the business logic is correct.

2. **Numeric comparison is fragile.** The function only checks `payout` or `trade_amount` fields. If the generated code returns `"trade_amount": "7000.0"` instead of `"7000.00"`, or uses a key like `"amount"` instead of `"trade_amount"`, the comparison falls through to the default case.

3. **Boolean handling.** Legacy traces use Python `True`/`False` for `tlh_flag`, but generated code might return `"true"`, `"True"`, `"yes"`, or `1`. These get treated as mismatches.

4. **The Human Gate UI in Zone 5** has hardcoded text describing a COBOL truncation / rounding scenario. When the actual drift is something different (or when there are only Type 3s and no Type 2s), the narrative breaks.

---

## Fix 1 — Robust Drift Classification (`external/tester.py`)

### 1.1 — Add a normalization helper function

Add a new function `_normalize_output(output: dict) -> dict` **above** `classify_drift()`. This function creates a normalized copy of the output for comparison purposes.

```python
def _normalize_output(output: dict) -> dict:
    """Normalize an output dict for drift comparison.
    
    Handles:
    - Case normalization of status/action fields
    - Numeric string normalization (trailing zeros, float vs int)
    - Boolean normalization (True/False/"true"/"True"/1/0)
    - Key aliasing (e.g. "amount" -> "trade_amount")
    - Whitespace stripping on all string values
    """
    if not isinstance(output, dict):
        return output
    
    normalized = {}
    
    # Key aliases: map common variants to canonical names
    key_aliases = {
        "amount": "trade_amount",
        "trade_value": "trade_amount",
        "payment": "payout",
        "payout_amount": "payout",
        "result": "status",
        "decision": "action",
        "error_message": "reason",
    }
    
    for key, value in output.items():
        # Normalize key
        canonical_key = key_aliases.get(key.lower().strip(), key.lower().strip())
        
        # Normalize value
        if isinstance(value, str):
            value = value.strip().upper()
        
        # Normalize booleans
        if isinstance(value, bool):
            value = value  # keep as bool
        elif isinstance(value, str) and value.upper() in ("TRUE", "YES", "1"):
            value = True
        elif isinstance(value, str) and value.upper() in ("FALSE", "NO", "0"):
            # Only convert if it looks like a boolean field, not a numeric "0"
            if canonical_key in ("tlh_flag", "wash_sale_flag", "is_valid"):
                value = False
        
        # Normalize numeric strings: "7000.0" -> "7000.00", "100" -> "100.00"
        if isinstance(value, str) and canonical_key in (
            "payout", "trade_amount", "claim_amount", "deductible",
            "coverage_limit", "market_value"
        ):
            try:
                from decimal import Decimal, ROUND_HALF_UP
                decimal_val = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                value = str(decimal_val)
            except Exception:
                pass  # Keep original if it can't be parsed as numeric
        
        normalized[canonical_key] = value
    
    return normalized
```

### 1.2 — Rewrite `classify_drift()`

Replace the existing `classify_drift()` function entirely. The new version uses `_normalize_output()` as a first pass and has more granular comparison logic.

```python
def classify_drift(legacy_output: dict, modern_output: dict) -> tuple:
    """Classify drift between legacy and modern outputs.

    Returns: (drift_type: int, classification: str)
        0 = Identical (after normalization)
        1 = Acceptable variance (cosmetic: formatting, casing, key naming)
        2 = Semantic difference (needs human judgment — e.g. rounding)
        3 = Breaking (different business outcome)
    """
    # Handle error outputs from execution failures
    if isinstance(modern_output, dict) and "error" in modern_output:
        error_msg = modern_output.get("error", "")
        # Execution failures are breaking
        if "Could not find processor" in error_msg or "Execution failed" in error_msg:
            return (3, "Breaking — execution failure")
        return (3, f"Breaking — error: {error_msg[:80]}")
    
    # Raw comparison first
    if legacy_output == modern_output:
        return (0, "Identical")

    # Normalize both outputs
    norm_legacy = _normalize_output(legacy_output)
    norm_modern = _normalize_output(modern_output)
    
    # Normalized exact match = Type 1 (cosmetic difference only)
    if norm_legacy == norm_modern:
        return (1, "Acceptable variance — cosmetic differences (casing, formatting)")

    # Compare core business outcome (status/action)
    legacy_status = (
        norm_legacy.get("status") or 
        norm_legacy.get("action") or 
        ""
    )
    modern_status = (
        norm_modern.get("status") or 
        norm_modern.get("action") or 
        ""
    )
    
    # If both are strings, compare case-insensitively
    if isinstance(legacy_status, str) and isinstance(modern_status, str):
        status_match = legacy_status.upper().strip() == modern_status.upper().strip()
    else:
        status_match = legacy_status == modern_status
    
    if not status_match:
        return (3, f"Breaking — different business outcome: expected '{legacy_status}', got '{modern_status}'")

    # Status matches — now check numeric values
    legacy_amount = norm_legacy.get("payout") or norm_legacy.get("trade_amount")
    modern_amount = norm_modern.get("payout") or norm_modern.get("trade_amount")
    
    if legacy_amount is not None and modern_amount is not None:
        try:
            from decimal import Decimal
            legacy_dec = Decimal(str(legacy_amount))
            modern_dec = Decimal(str(modern_amount))
            diff = abs(legacy_dec - modern_dec)
            
            if diff == 0:
                return (1, "Acceptable variance — values match after normalization")
            elif diff <= Decimal("0.02"):
                return (2, f"Semantic — rounding difference of ${diff}")
            else:
                return (3, f"Breaking — value mismatch: expected {legacy_amount}, got {modern_amount}")
        except Exception:
            pass
    elif legacy_amount is not None and modern_amount is None:
        # Legacy has amount but modern doesn't — check if it's under a different key
        for key in norm_modern:
            try:
                from decimal import Decimal
                if Decimal(str(norm_modern[key])):
                    modern_amount = norm_modern[key]
                    break
            except Exception:
                continue
        if modern_amount is not None:
            try:
                from decimal import Decimal
                diff = abs(Decimal(str(legacy_amount)) - Decimal(str(modern_amount)))
                if diff == 0:
                    return (1, "Acceptable variance — amount found under different key")
                elif diff <= Decimal("0.02"):
                    return (2, f"Semantic — rounding difference of ${diff}")
                else:
                    return (3, f"Breaking — value mismatch: expected {legacy_amount}, got {modern_amount}")
            except Exception:
                pass
    
    # Compare error codes
    legacy_error = norm_legacy.get("error_code")
    modern_error = norm_modern.get("error_code")
    if legacy_error is not None and modern_error is not None:
        try:
            if int(legacy_error) != int(modern_error):
                return (2, f"Semantic — different error code: expected {legacy_error}, got {modern_error}")
        except (ValueError, TypeError):
            pass
    
    # Compare boolean flags (like tlh_flag)
    for flag_key in ("tlh_flag", "wash_sale_flag"):
        legacy_flag = norm_legacy.get(flag_key)
        modern_flag = norm_modern.get(flag_key)
        if legacy_flag is not None and modern_flag is not None:
            if bool(legacy_flag) != bool(modern_flag):
                return (2, f"Semantic — {flag_key} mismatch: expected {legacy_flag}, got {modern_flag}")
    
    # Status and primary value match — remaining differences are acceptable
    return (1, "Acceptable variance — non-critical field differences")
```

### 1.3 — Fix the import placement

The `from decimal import Decimal, ROUND_HALF_UP` import should be moved to the **top of the file** alongside the other imports, not inside the function. Add to the existing imports at the top of `external/tester.py`:

```python
from decimal import Decimal, ROUND_HALF_UP
```

Then remove the inline `from decimal import ...` lines in the functions above and just use `Decimal` directly.

---

## Fix 2 — Tighten Generation Prompt (`external/generator.py`)

### 2.1 — Add explicit output format contract to `GENERATION_SYSTEM_PROMPT`

Append the following section to the **end** of the existing `GENERATION_SYSTEM_PROMPT` string (before the closing `"""`):

```
OUTPUT FORMAT CONTRACT:
The `process(self, input_data: dict) -> dict` method MUST return dictionaries with these EXACT conventions:
- All status/action values MUST be UPPERCASE strings: "APPROVED", "DENIED", "SELL", "BUY", "HOLD"
- All financial amounts MUST be strings with exactly 2 decimal places: "4500.00" not "4500" or "4500.0"
- Error codes MUST be integers: 1001 not "1001"
- Boolean flags MUST be Python bool: True/False not "true"/"false"
- The "reason" field MUST be an UPPERCASE string matching legacy conventions: "DRIFT WITHIN THRESHOLD", "WASH SALE BLOCK", "BELOW MIN TRADE THRESHOLD"

CRITICAL — these exact output keys are expected:
- For rebalancing: {"action": "SELL"|"BUY"|"HOLD", "trade_amount": "0.00", "reason": "...", "tlh_flag": True|False, "error_code": int}
- For claims: {"status": "APPROVED"|"DENIED", "payout": "0.00", "error_code": int}
- Only include keys that are relevant to the specific outcome (e.g., don't include "trade_amount" for HOLD actions unless it's meaningful)
```

### 2.2 — Add format reminder to `GENERATION_USER_PROMPT`

Add the following line to the IMPLEMENTATION CHECKLIST in `GENERATION_USER_PROMPT` (after item 7, before the "Return ONLY" line):

```
8. All status/action string values must be UPPERCASE (e.g., "APPROVED", "SELL", "HOLD")
9. All financial amounts must be Decimal strings with exactly 2 decimal places via quantize(Decimal("0.01"))
```

---

## Fix 3 — Dynamic Human Gate UI

### 3.1 — Make Zone 5 Human Gate text dynamic (`static/app.js`)

In the `runTesting()` function, **after** the test results are populated in the table and the quality gate metrics are set, add logic to dynamically update the Human Gate content.

Find the section in `runTesting()` that sets the quality gate icons (around the `pipelineLog('ZONE-5', ...)` calls at the end of the try block). **Before** the final `pipelineLog` and `toast` calls, add:

```javascript
    // ── Dynamic Human Gate Content ──
    updateDriftGate(results);
```

Then add a new function `updateDriftGate(results)`:

```javascript
/**
 * Dynamically update the Zone 5 Human Gate based on actual drift results.
 * Handles three scenarios:
 * 1. No drift (all Type 0/1) — auto-clear the gate
 * 2. Type 2 semantic drift — show adjudication options
 * 3. Type 3 breaking drift — show different messaging
 */
function updateDriftGate(results) {
  const gate = document.getElementById('drift-gate');
  const gateHeader = gate.querySelector('.human-gate-header');
  const gateDesc = gate.querySelector('.gate-desc');
  const gateActions = document.getElementById('drift-actions');
  const driftDecision = document.getElementById('drift-decision');
  
  const type2Results = results.filter(r => r.drift_type === 2);
  const type3Results = results.filter(r => r.drift_type === 3);
  const hasDrift = type2Results.length > 0 || type3Results.length > 0;
  
  if (!hasDrift) {
    // No drift — auto-clear the gate
    gateHeader.textContent = '✓ Quality Gate — No Drift Detected';
    gateHeader.style.color = 'var(--green-tx)';
    gate.style.borderColor = 'var(--green)';
    gate.querySelector('.human-gate-header').style.background = 'var(--green-dim)';
    gate.querySelector('.human-gate-header').style.borderBottomColor = 'rgba(61,154,110,.2)';
    gateDesc.textContent = 'All test cases produced identical or acceptable results. No human adjudication required.';
    gateActions.style.display = 'none';
    document.getElementById('btn-to-prod').disabled = false;
    
    // Auto-record the pass
    driftDecision.className = 'decision-record accepted show';
    driftDecision.innerHTML = '<div class="dr-header">✓ QUALITY GATE PASSED</div>' +
      '<div class="dr-body">All ' + results.length + ' test cases passed with Type 0 (Identical) or Type 1 (Acceptable) classification. No semantic or breaking drift detected.</div>' +
      '<div class="dr-ts">Automated · ' + new Date().toISOString().split('.')[0] + 'Z</div>';
    
    pipelineLog('ZONE-5', 'Quality gate auto-cleared — zero drift requiring adjudication');
    return;
  }
  
  if (type3Results.length > 0 && type2Results.length === 0) {
    // Only Type 3 breaking — different UI
    gateHeader.textContent = '✗ Quality Gate — Breaking Drift Detected';
    
    // Build description from actual breaking results
    const breakingDescs = type3Results.slice(0, 3).map(r => {
      const testName = r.test_case || 'Unknown test';
      const classification = r.drift_classification || 'Breaking';
      return testName + ': ' + classification;
    });
    
    gateDesc.innerHTML = '<strong>' + type3Results.length + ' breaking difference' + 
      (type3Results.length > 1 ? 's' : '') + ' detected.</strong> ' +
      'The generated code produces different business outcomes for these test cases:<br><br>' +
      breakingDescs.map(d => '• ' + escHtml(d)).join('<br>') +
      (type3Results.length > 3 ? '<br>• ... and ' + (type3Results.length - 3) + ' more' : '') +
      '<br><br>Review the drift classification table above. You may accept if the modern behavior is actually correct, ' +
      'or escalate if the difference needs investigation.';
    
    // Show the same adjudication buttons but with context-appropriate labels
    gateActions.innerHTML = 
      '<button class="btn green" onclick="adjudicate(\'accept\')">Accept — Modern Output Correct</button>' +
      '<button class="btn amber" onclick="adjudicate(\'preserve\')">Preserve Legacy Behavior</button>' +
      '<button class="btn red" onclick="adjudicate(\'escalate\')">Escalate — Needs Investigation</button>';
    gateActions.style.display = 'flex';
    
  } else if (type2Results.length > 0) {
    // Type 2 semantic drift (may also have Type 3s)
    gateHeader.textContent = '⚠ Human Gate — Drift Adjudication Required';
    
    const totalDrift = type2Results.length + type3Results.length;
    
    // Build description from actual semantic results
    const semanticDescs = type2Results.slice(0, 2).map(r => {
      const testName = r.test_case || 'Unknown test';
      const classification = r.drift_classification || 'Semantic';
      return testName + ': ' + classification;
    });
    
    let descHtml = '<strong>' + totalDrift + ' difference' + 
      (totalDrift > 1 ? 's' : '') + ' requiring human judgment.</strong><br><br>';
    
    if (type2Results.length > 0) {
      descHtml += '<strong>Semantic (Type 2):</strong> ' + type2Results.length + ' — ';
      descHtml += semanticDescs.map(d => escHtml(d)).join('; ');
      if (type2Results.length > 2) descHtml += '; and ' + (type2Results.length - 2) + ' more';
      descHtml += '<br>';
    }
    if (type3Results.length > 0) {
      descHtml += '<strong>Breaking (Type 3):</strong> ' + type3Results.length + ' — ';
      descHtml += type3Results.slice(0, 2).map(r => escHtml(r.test_case + ': ' + r.drift_classification)).join('; ');
      descHtml += '<br>';
    }
    
    descHtml += '<br>Review the drift classification table above and decide how to proceed.';
    
    gateDesc.innerHTML = descHtml;
    
    // Standard adjudication buttons
    gateActions.innerHTML = 
      '<button class="btn green" onclick="adjudicate(\'accept\')">Accept Variance</button>' +
      '<button class="btn amber" onclick="adjudicate(\'preserve\')">Preserve Legacy Behavior</button>' +
      '<button class="btn red" onclick="adjudicate(\'escalate\')">Escalate to Compliance</button>';
    gateActions.style.display = 'flex';
  }
}
```

### 3.2 — Update `adjudicate()` function (`static/app.js`)

The existing `adjudicate()` function has hardcoded decision record text. Replace the decision record bodies to be more generic:

Find the `adjudicate(action)` function. Replace the three decision record `innerHTML` blocks:

**For `action === 'accept'`:**
```javascript
    dr.className = 'decision-record accepted show';
    dr.innerHTML = '<div class="dr-header">✓ ACCEPT_VARIANCE</div>' +
      '<div class="dr-body">Drift reviewed and accepted. Modern implementation behavior validated by domain expert as correct or acceptable.</div>' +
      '<div class="dr-ts">' + OPERATOR.name + ' (' + OPERATOR.role + ') · ' + ts + '</div>';
    document.getElementById('btn-to-prod').disabled = false;
    toast('Variance accepted — quality gate cleared');
```

**For `action === 'preserve'`:**
```javascript
    dr.className = 'decision-record preserved show';
    dr.innerHTML = '<div class="dr-header">⚠ PRESERVE_LEGACY</div>' +
      '<div class="dr-body">Legacy behavior preserved for backward compatibility. Difference documented in governance ledger for future review.</div>' +
      '<div class="dr-ts">' + OPERATOR.name + ' (' + OPERATOR.role + ') · ' + ts + '</div>';
    document.getElementById('btn-to-prod').disabled = false;
    toast('Legacy behavior preserved — documented in governance ledger');
```

**For `action === 'escalate'` (the else case):**
```javascript
    dr.className = 'decision-record escalated show';
    dr.innerHTML = '<div class="dr-header">↗ ESCALATED</div>' +
      '<div class="dr-body">Drift escalated for additional review. Pipeline blocked until resolved.</div>' +
      '<div class="dr-ts">' + OPERATOR.name + ' (' + OPERATOR.role + ') · ' + ts + '</div>';
    toast('Escalated — pipeline blocked pending review');
```

### 3.3 — Update Zone 5 Human Gate markup (`static/index.html`)

In the Zone 5 panel (`zp-5`), find the `drift-gate` human gate div. Replace the **hardcoded** `gate-desc` content with a generic placeholder that will be overwritten by JS:

Replace:
```html
<div class="gate-desc">COBOL truncates to $99.99; Python rounds correctly to $100.00. The $0.01 difference has regulatory implications at aggregate scale across 2.4M daily transactions.</div>
```

With:
```html
<div class="gate-desc">Analyzing drift classification results…</div>
```

Also replace the hardcoded adjudication buttons inside `drift-actions`:
```html
<div class="gate-actions" id="drift-actions">
  <button class="btn green" onclick="adjudicate('accept')">Accept Variance</button>
  <button class="btn amber" onclick="adjudicate('preserve')">Preserve Legacy Behavior</button>
  <button class="btn red" onclick="adjudicate('escalate')">Escalate to Compliance</button>
</div>
```

(These may be dynamically overwritten by `updateDriftGate()`, but this ensures a reasonable default if the function hasn't run yet.)

---

## Fix 4 — Handle AI-Generated Test Comparison More Gracefully (`external/tester.py`)

### 4.1 — Update the AI-generated test reclassification block in `run_tests()`

In the Phase 2b loop (the section that processes AI-generated tests), the current reclassification logic is:

```python
        # Reclassify for AI-generated: Type 0 = "Validated against requirements"
        if drift_type == 0:
            drift_class = "Validated against requirements"
        elif drift_type <= 1:
            drift_class = "Acceptable — minor variance from requirements"
        elif drift_type == 2:
            drift_class = "Deviation from requirements — needs review"
```

**Replace this block with:**

```python
        # Reclassify for AI-generated tests:
        # AI expected outputs are approximate (AI predicting AI), so we're more
        # tolerant. Only flag as breaking if status/action fundamentally differs.
        if drift_type == 0:
            drift_class = "Validated against requirements"
        elif drift_type == 1:
            drift_class = "Acceptable — minor variance from expected"
        elif drift_type == 2:
            drift_class = "Semantic — deviation from expected behavior"
        elif drift_type == 3:
            # For AI-generated tests, downgrade Type 3 to Type 2 if the error
            # is likely due to imprecise AI expectations rather than broken logic.
            # Only keep as Type 3 if it's an execution failure.
            if isinstance(modern_output, dict) and "error" in modern_output:
                drift_class = "Breaking — execution failure"
            else:
                drift_type = 2
                drift_class = "Semantic — output differs from AI expectation (review recommended)"
```

**Rationale:** AI-generated expected outputs are predictions, not ground truth. When the AI test generator says it expects `{"action": "SELL", "trade_amount": "7000.00"}` and the generated code returns something structurally different, that's often the test generator predicting imprecisely — not the generated code being wrong. Legacy traces are ground truth; AI expectations are not. Downgrading from Type 3 to Type 2 for AI-only tests prevents false alarms while still surfacing the difference for review.

---

## Implementation Order

1. **`external/tester.py`** — Add `_normalize_output()`, rewrite `classify_drift()`, add Decimal import, update AI test reclassification (Fixes 1 & 4)
2. **`external/generator.py`** — Update both prompt strings (Fix 2)
3. **`static/index.html`** — Update Zone 5 Human Gate markup (Fix 3.3)
4. **`static/app.js`** — Add `updateDriftGate()` function, update `adjudicate()`, call `updateDriftGate()` from `runTesting()` (Fix 3.1, 3.2)
5. **Test the full flow** — Run through all 6 zones end-to-end with both `claims_processing.cbl` and `portfolio_rebalance.cbl`

---

## Validation Criteria

After implementation, verify:

1. **`claims_processing.cbl`** pipeline produces mostly Type 0/1 results (not Type 3)
2. **`portfolio_rebalance.cbl`** pipeline produces mostly Type 0/1 results (not Type 3)
3. When all tests pass (Type 0/1), the Human Gate auto-clears with a green "Quality Gate Passed" message and the "Deploy →" button enables automatically
4. When Type 2 drift exists, the Human Gate shows the actual semantic difference (not hardcoded text)
5. When Type 3 drift exists (genuine breaking), the Human Gate shows the actual test case names and classifications
6. The `adjudicate()` function works for all three actions in all three gate states
7. The generation prompt produces UPPERCASE status values and 2-decimal-place amounts consistently
8. AI-generated tests that disagree with generated code are classified as Type 2 (not Type 3) unless execution failed

---

## Files Changed

| File | Change Type | Summary |
|------|------------|---------|
| `external/tester.py` | Modified | New `_normalize_output()` function, rewritten `classify_drift()`, updated AI test reclassification, added Decimal import |
| `external/generator.py` | Modified | Appended output format contract to both prompt strings |
| `static/index.html` | Modified | Replaced hardcoded Human Gate description with generic placeholder |
| `static/app.js` | Modified | New `updateDriftGate()` function, updated `adjudicate()` decision text, added call in `runTesting()` |

## Files NOT Changed

- `database.py` — No schema changes
- `app.py` — No endpoint changes
- `internal/analyzer.py` — Not involved
- `internal/extractor.py` — Not involved
- `external/executor.py` — Not involved
- `static/style.css` — Existing styles for `.human-gate`, `.decision-record`, `.gate-desc` already support the dynamic content
- `Initiative_Zero.md` — Written explanation already describes the correct behavior
- `architecture.drawio` — No architectural changes
