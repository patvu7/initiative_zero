# Initiative Zero — Improvement Spec (Round 3)

**For:** Claude Code execution  
**Scope:** Three targeted improvements to the existing working prototype  
**Files referenced:** All files in `initiative-zero/` directory

---

## Overview

Three improvements, each scoped to specific files and modules. Execute in order — #1 feeds into #2.

---

## Improvement 1: Enriched Requirements Document (Zone 3 → Zone 4 Handoff)

### Problem

The current `extractor.py` produces a bare requirements document — just business rules as numbered text. It discards all the rich analysis context from Zone 2 that would help the code generator produce better output. The analysis report contains critical information about data sensitivity, security concerns, testing risks, and migration risks that should inform code generation.

### What Changes

**File: `internal/extractor.py`**

After extraction completes and before storing the requirements doc, enrich the requirements document by pulling analysis data from the `analyses` table for the same `run_id` and appending structured context sections.

#### Modified `run_extraction()` function

After the existing extraction logic (Claude call, parsing, storing rules), add a step that:

1. Queries the `analyses` table for the current `run_id`
2. If analysis data exists, parses `metrics` JSON
3. Appends the following sections to `req_doc_text` before storing it in `requirements_docs`:

```python
# After: req_doc_text = result.get("requirements_document", "")
# Add: enrichment from Zone 2 analysis

db = get_db()
analysis_row = db.execute(
    "SELECT metrics FROM analyses WHERE run_id = ?", (run_id,)
).fetchone()

if analysis_row and analysis_row["metrics"]:
    metrics = json.loads(analysis_row["metrics"])
    enrichment = build_enrichment_section(metrics)
    req_doc_text = req_doc_text + "\n\n" + enrichment
```

#### New function: `build_enrichment_section(metrics: dict) -> str`

Build a plain-text appendix from the analysis metrics. This must remain **technology-agnostic** — no COBOL references, no variable names. Structure:

```
---
SUPPLEMENTAL CONTEXT FROM SYSTEM ANALYSIS
(This section provides additional context for code generation.
All information is technology-agnostic.)
---

SYSTEM PROFILE
- Purpose: {app_analysis.purpose}
- Domain: {app_analysis.domain}
- Criticality: {app_analysis.criticality} — {app_analysis.criticality_rationale}
- Data Sensitivity: {app_analysis.data_sensitivity} — {app_analysis.data_sensitivity_rationale}

DATA HANDLING REQUIREMENTS
- This system processes {data_sensitivity}-sensitivity data
- {If data_sensitivity == "High": "All data handling must include audit trails, access logging, and encryption-at-rest considerations"}
- {If domain contains "Portfolio" or "Wealth": "Financial calculations require Decimal precision with explicit rounding modes"}

KNOWN TESTING GAPS (from analysis)
The following edge cases were identified as untested in the legacy system.
The generated implementation SHOULD include defensive handling for these:
{For each item in test_analysis.untested_edge_cases:}
- {item}

TESTING RISKS
{For each item in test_analysis.testing_risks:}
- {item}

MIGRATION RISKS
{For each risk in migration_risks:}
- [{risk.severity}] {risk.risk}
  Mitigation: {risk.mitigation}

SECURITY REQUIREMENTS (from analysis)
{For each item in code_analysis.security_detail:}
- {item}

CODE QUALITY GUIDANCE
{For each item in code_analysis.code_quality_notes that contains "Good":}
- Preserve: {item}
```

#### Key rules for enrichment:
- Only append if analysis data exists (graceful no-op otherwise)
- Strip any language-specific references (the enrichment must pass the same "no implementation details" test as the rest of the doc)
- Keep it as structured plain text, not markdown
- Each section has a clear header so the generation prompt can reference it

### Files Modified
- `internal/extractor.py` — modify `run_extraction()`, add `build_enrichment_section()`

### Verification
- Run a pipeline. Download the PRD from Zone 3.
- Confirm it now has a "SUPPLEMENTAL CONTEXT" section at the bottom
- Confirm the section contains testing gaps, security requirements, and risk context
- Confirm zero COBOL/language-specific references in the enrichment

---

## Improvement 2: Richer Code Generation Prompt (Zone 4)

### Problem

The current generation prompt in `external/generator.py` is generic:
```
"Generate a complete, production-ready Python module that implements ALL of the following business requirements."
```

It doesn't guide Claude to use the enrichment context, doesn't specify a consistent interface for testing, and produces code that the test harness struggles to invoke.

### What Changes

**File: `external/generator.py`**

Replace both `GENERATION_SYSTEM_PROMPT` and `GENERATION_USER_PROMPT` with richer versions that reference the enrichment sections and enforce a testable interface.

#### New `GENERATION_SYSTEM_PROMPT`:

```python
GENERATION_SYSTEM_PROMPT = """You are a code generation agent for a financial services 
modernization pipeline. You generate production-ready Python applications from 
plain-text business requirements.

CRITICAL CONSTRAINTS:
- You have NO access to any source code, database schemas, or implementation details
- You work ONLY from the requirements document provided
- You MUST NOT infer or guess implementation patterns from the original system

CODE QUALITY STANDARDS:
- Use dataclasses and type hints throughout
- Use Decimal with explicit rounding (ROUND_HALF_UP) for ALL currency/financial values
- Each method must have a docstring referencing the business rule ID it implements
- Include comprehensive input validation with meaningful error codes
- Include error handling that returns structured error responses (never raises unhandled)
- Follow clean architecture: separate domain logic from I/O concerns
- All thresholds and configuration values must be class-level constants, not magic numbers

MANDATORY INTERFACE:
Your module MUST include a top-level class with a `process(self, input_data: dict) -> dict` method.
This is the entry point that the testing harness will call.
- input_data: a flat dictionary with string values for all fields
- return value: a dictionary with string values, must include at minimum:
  - For trade/rebalance systems: "action" (e.g. "SELL", "BUY", "HOLD"), 
    and optionally "trade_amount", "reason", "error_code", "tlh_flag"  
  - For claims/approval systems: "status" (e.g. "APPROVED", "DENIED"),
    and optionally "payout", "error_code", "reason"
- Convert all Decimal results to string in the return dict
- On any error, return {"error": "description", "error_code": <int>} — never raise

SUPPLEMENTAL CONTEXT:
The requirements document may include a "SUPPLEMENTAL CONTEXT FROM SYSTEM ANALYSIS" 
section. Use this to:
- Understand data sensitivity requirements and add appropriate validation
- Address the specific untested edge cases listed (add defensive handling)
- Implement mitigations for the listed migration risks where possible in code
- Follow the security requirements listed"""
```

#### New `GENERATION_USER_PROMPT`:

```python
GENERATION_USER_PROMPT = """Generate a complete, production-ready Python module that 
implements ALL of the following business requirements.

REQUIREMENTS DOCUMENT:
{requirements_text}

IMPLEMENTATION CHECKLIST:
1. Every business rule (BR-###) must be implemented and referenced in a docstring
2. Every behavioral observation (OBS-###) should be considered and noted if implemented
3. The main processing class must have a `process(self, input_data: dict) -> dict` method
4. All financial values must use Decimal (import from decimal module)
5. All thresholds must be class constants
6. Error handling must return dicts with "error" key, never raise exceptions
7. Include input validation for missing/empty required fields
8. If "SUPPLEMENTAL CONTEXT" is present, address each listed testing gap defensively

Return ONLY the Python code. No markdown fences, no explanations."""
```

### Files Modified
- `external/generator.py` — replace both prompt constants

### Verification
- Run a full pipeline through Zone 4
- Inspect generated code: confirm it has a class with `process(self, input_data: dict) -> dict`
- Confirm business rule IDs appear in docstrings
- Confirm Decimal usage for financial values
- Confirm thresholds are class constants, not inline numbers
- Open "View Generation Prompt" — confirm it shows the enriched requirements including the supplemental context

---

## Improvement 3: Live Coexistence Simulation (Zone 6)

### Problem

Zone 6 currently shows a static ASCII diagram and buttons. It doesn't demonstrate the coexistence model actually working — both systems processing the same input and comparing outputs in real time. For the demo, this is the weakest zone because it's purely decorative.

### What Changes

**File: `static/index.html`** — Replace the static Zone 6 content  
**File: `static/app.js`** — Add coexistence simulation logic  
**File: `static/style.css`** — Add styles for the new components  
**File: `app.py`** — Add one new API endpoint

### 3A. New API Endpoint

**File: `app.py`**

Add a new route that runs a single test case through both the legacy behavior model AND the generated code, returning both outputs for side-by-side display:

```python
@app.route('/api/coexistence/<run_id>/simulate', methods=['POST'])
def api_coexistence_simulate(run_id):
    """Simulate coexistence: run one transaction through both legacy and modern."""
    data = request.json
    test_index = data.get("test_index", 0)
    
    db = get_db()
    
    # Get generated code
    gen_row = db.execute(
        "SELECT code FROM generated_code WHERE run_id = ?", (run_id,)
    ).fetchone()
    
    # Get source file to find test suite
    run_row = db.execute(
        "SELECT source_file FROM pipeline_runs WHERE id = ?", (run_id,)
    ).fetchone()
    db.close()
    
    if not gen_row or not run_row:
        return jsonify({"error": "Run data not found"}), 404
    
    from external.tester import LEGACY_BEHAVIORS, build_test_harness, classify_drift
    from external.executor import execute_python
    
    source_key = run_row["source_file"].replace(".cbl", "")
    test_cases = LEGACY_BEHAVIORS.get(source_key, {}).get("test_cases", [])
    
    if test_index >= len(test_cases):
        return jsonify({"error": "Test index out of range"}), 400
    
    tc = test_cases[test_index]
    
    # Run modern code
    harness = build_test_harness(gen_row["code"], tc["input"])
    exec_result = execute_python(gen_row["code"], harness)
    
    if exec_result["success"] and isinstance(exec_result["output"], dict):
        modern_output = exec_result["output"]
    else:
        modern_output = {"error": exec_result.get("stderr", "Execution failed")}
    
    # Classify drift
    drift_type, drift_class = classify_drift(tc["legacy_output"], modern_output)
    
    return jsonify({
        "test_case": tc["name"],
        "input": tc["input"],
        "legacy_output": tc["legacy_output"],
        "modern_output": modern_output,
        "drift_type": drift_type,
        "drift_classification": drift_class,
        "legacy_latency_ms": 340,   # Simulated batch latency
        "modern_latency_ms": 12     # Simulated real-time latency
    })
```

### 3B. New Zone 6 HTML

**File: `static/index.html`**

Replace the Zone 6 panel content (everything inside `<div class="zone-panel" id="zp-6">`) with this structure. Keep the existing zone-title-row.

After the zone title row, the new layout has three sections:

**Section 1: Slice Progression Bar** (keep existing, no changes)

**Section 2: Live Coexistence Simulator** (NEW — replaces the static ASCII diagram)

```html
<div class="section-label">Coexistence Simulator — Shadow Mode</div>

<div class="coex-live" id="coex-live">
  <!-- Transaction selector -->
  <div class="coex-controls">
    <select id="coex-txn-selector" class="btn" style="min-width: 280px; padding: 8px 12px;">
      <option value="0">Transaction 1: Drift above threshold</option>
      <option value="1">Transaction 2: Drift within threshold</option>
      <option value="2">Transaction 3: Tax-loss harvest trigger</option>
      <option value="3">Transaction 4: Wash sale block</option>
      <option value="4">Transaction 5: Below minimum trade</option>
    </select>
    <button class="btn primary" onclick="runCoexSimulation()" id="btn-coex-run">▶ Process Transaction</button>
  </div>

  <!-- Routing diagram (dynamic) -->
  <div class="coex-flow" id="coex-flow" style="display:none">
    <!-- Input panel -->
    <div class="coex-input-panel" id="coex-input-panel">
      <div class="coex-panel-header">Incoming Transaction</div>
      <pre id="coex-input-display" class="coex-data"></pre>
    </div>

    <!-- Router arrow -->
    <div class="coex-router">
      <div class="coex-router-label">Router</div>
      <div class="coex-router-arrows">
        <div class="coex-arrow left">
          <span class="coex-arrow-label">100% serves</span>
        </div>
        <div class="coex-arrow right">
          <span class="coex-arrow-label">100% shadows</span>
        </div>
      </div>
    </div>

    <!-- Side-by-side system panels -->
    <div class="coex-systems">
      <div class="coex-system legacy" id="coex-legacy-panel">
        <div class="coex-system-header">
          <span class="coex-system-badge legacy">■ LEGACY</span>
          <span class="coex-system-role">SERVES TRAFFIC</span>
        </div>
        <div class="coex-system-status" id="coex-legacy-status">Idle</div>
        <pre id="coex-legacy-output" class="coex-data">—</pre>
        <div class="coex-latency" id="coex-legacy-latency"></div>
      </div>

      <div class="coex-system modern" id="coex-modern-panel">
        <div class="coex-system-header">
          <span class="coex-system-badge modern">□ MODERN</span>
          <span class="coex-system-role">SHADOW (compare only)</span>
        </div>
        <div class="coex-system-status" id="coex-modern-status">Idle</div>
        <pre id="coex-modern-output" class="coex-data">—</pre>
        <div class="coex-latency" id="coex-modern-latency"></div>
      </div>
    </div>

    <!-- Drift comparator -->
    <div class="coex-comparator" id="coex-comparator" style="display:none">
      <div class="coex-comparator-header">Drift Comparator</div>
      <div class="coex-comparator-result" id="coex-comparator-result"></div>
    </div>
  </div>

  <!-- Transaction log -->
  <div class="section-label" id="coex-log-label" style="display:none">Transaction Log</div>
  <div class="code-viewer" id="coex-log-wrap" style="display:none;margin-bottom:0">
    <table class="test-table">
      <thead><tr><th>#</th><th>Transaction</th><th>Legacy</th><th>Modern</th><th>Drift</th><th>Latency Δ</th></tr></thead>
      <tbody id="coex-log-tbody"></tbody>
    </table>
  </div>
</div>
```

**Section 3: Human Gate** (keep existing canary gate, no changes)

### 3C. Coexistence Simulation JS

**File: `static/app.js`**

Add the following functions:

```javascript
let coexTxnCount = 0;

async function runCoexSimulation() {
  const selector = document.getElementById('coex-txn-selector');
  const testIndex = parseInt(selector.value);
  const btn = document.getElementById('btn-coex-run');
  
  btn.disabled = true;
  btn.textContent = 'Processing…';
  
  // Show the flow diagram
  document.getElementById('coex-flow').style.display = 'block';
  
  // Step 1: Show input (immediate)
  document.getElementById('coex-input-panel').classList.add('active');
  document.getElementById('coex-legacy-status').textContent = 'Processing…';
  document.getElementById('coex-legacy-status').style.color = 'var(--amber-tx)';
  document.getElementById('coex-modern-status').textContent = 'Processing…';
  document.getElementById('coex-modern-status').style.color = 'var(--amber-tx)';
  document.getElementById('coex-legacy-output').textContent = '…';
  document.getElementById('coex-modern-output').textContent = '…';
  document.getElementById('coex-comparator').style.display = 'none';
  
  try {
    const result = await api('/api/coexistence/' + state.runId + '/simulate', 'POST', {
      test_index: testIndex
    });
    
    // Show input data
    document.getElementById('coex-input-display').textContent = 
      JSON.stringify(result.input, null, 2);
    
    // Step 2: Show legacy result (after simulated delay)
    setTimeout(() => {
      document.getElementById('coex-legacy-status').textContent = 'Complete';
      document.getElementById('coex-legacy-status').style.color = 'var(--green-tx)';
      document.getElementById('coex-legacy-output').textContent = 
        JSON.stringify(result.legacy_output, null, 2);
      document.getElementById('coex-legacy-latency').textContent = 
        result.legacy_latency_ms + 'ms (batch)';
      document.getElementById('coex-legacy-panel').classList.add('done');
    }, 400);
    
    // Step 3: Show modern result (faster)
    setTimeout(() => {
      document.getElementById('coex-modern-status').textContent = 'Complete';
      document.getElementById('coex-modern-status').style.color = 'var(--green-tx)';
      document.getElementById('coex-modern-output').textContent = 
        JSON.stringify(result.modern_output, null, 2);
      document.getElementById('coex-modern-latency').textContent = 
        result.modern_latency_ms + 'ms (real-time)';
      document.getElementById('coex-modern-panel').classList.add('done');
    }, 250);
    
    // Step 4: Show comparator result
    setTimeout(() => {
      const comp = document.getElementById('coex-comparator');
      comp.style.display = 'block';
      const driftChips = {
        0: {cls: 'ok',   label: 'MATCH — Type 0 Identical'},
        1: {cls: 'info', label: 'MATCH — Type 1 Acceptable Variance'},
        2: {cls: 'warn', label: 'DRIFT — Type 2 Semantic Difference'},
        3: {cls: 'err',  label: 'DIVERGENCE — Type 3 Breaking'}
      };
      const chip = driftChips[result.drift_type] || driftChips[1];
      document.getElementById('coex-comparator-result').innerHTML = 
        '<span class="status-chip ' + chip.cls + '">' + chip.label + '</span>' +
        '<span class="coex-comparator-detail">' + escHtml(result.drift_classification) + '</span>';
      
      // Add to transaction log
      coexTxnCount++;
      document.getElementById('coex-log-label').style.display = '';
      document.getElementById('coex-log-wrap').style.display = '';
      const tbody = document.getElementById('coex-log-tbody');
      const tr = document.createElement('tr');
      if (result.drift_type >= 2) tr.classList.add('highlight');
      tr.innerHTML = 
        '<td>' + coexTxnCount + '</td>' +
        '<td>' + escHtml(result.test_case) + '</td>' +
        '<td>' + escHtml(formatOutput(result.legacy_output)) + '</td>' +
        '<td>' + escHtml(formatOutput(result.modern_output)) + '</td>' +
        '<td><span class="status-chip ' + chip.cls + '">' + chip.label.split('—')[0].trim() + '</span></td>' +
        '<td style="font-family:var(--mono);font-size:10px;color:var(--green-tx)">-' + 
          (result.legacy_latency_ms - result.modern_latency_ms) + 'ms</td>';
      tbody.insertBefore(tr, tbody.firstChild);
      
      btn.disabled = false;
      btn.textContent = '▶ Process Transaction';
      toast('Transaction processed — ' + chip.label.split('—')[0].trim());
    }, 700);
    
  } catch (e) {
    toast('Simulation error: ' + e.message);
    btn.disabled = false;
    btn.textContent = '▶ Process Transaction';
  }
}
```

### 3D. New CSS for Coexistence Simulator

**File: `static/style.css`**

Add these styles:

```css
/* ─── COEXISTENCE SIMULATOR ─── */
.coex-live {
  margin: 16px 0;
}

.coex-controls {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}

.coex-flow {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 20px;
  margin-bottom: 16px;
}

.coex-input-panel {
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 14px;
  margin-bottom: 16px;
  opacity: 0.5;
  transition: opacity 0.3s;
}
.coex-input-panel.active { opacity: 1; }

.coex-panel-header {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--tx3);
  margin-bottom: 8px;
}

.coex-data {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--tx2);
  line-height: 1.6;
  white-space: pre-wrap;
  margin: 0;
}

.coex-router {
  text-align: center;
  margin-bottom: 16px;
}
.coex-router-label {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--blue-tx);
  background: var(--blue-dim);
  display: inline-block;
  padding: 4px 14px;
  border-radius: 4px;
  margin-bottom: 8px;
}
.coex-router-arrows {
  display: flex;
  justify-content: center;
  gap: 60px;
}
.coex-arrow {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--tx4);
}
.coex-arrow.left .coex-arrow-label { color: var(--green-tx); }
.coex-arrow.right .coex-arrow-label { color: var(--amber-tx); }

.coex-systems {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.coex-system {
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px;
  transition: border-color 0.3s;
}
.coex-system.legacy.done { border-color: var(--green); }
.coex-system.modern.done { border-color: var(--blue); }

.coex-system-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.coex-system-badge {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 3px;
}
.coex-system-badge.legacy { background: var(--green-dim); color: var(--green-tx); }
.coex-system-badge.modern { background: var(--blue-dim); color: var(--blue-tx); }

.coex-system-role {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--tx4);
  letter-spacing: .06em;
}

.coex-system-status {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--tx4);
  margin-bottom: 8px;
}

.coex-latency {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--tx4);
  margin-top: 8px;
  text-align: right;
}

.coex-comparator {
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 14px;
  text-align: center;
}
.coex-comparator-header {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--blue-tx);
  margin-bottom: 8px;
}
.coex-comparator-result {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.coex-comparator-detail {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--tx3);
}
```

### 3E. Update `canaryDecision()` flow

**File: `static/app.js`**

In the existing `canaryDecision('promote')` handler, after updating the slice bar stages, also update the coexistence router labels to show the traffic shift:

```javascript
// Inside canaryDecision, after "stages[3].classList.add('active')" block:
// Update router arrows to reflect canary routing
const leftArrow = document.querySelector('.coex-arrow.left .coex-arrow-label');
const rightArrow = document.querySelector('.coex-arrow.right .coex-arrow-label');
if (leftArrow) leftArrow.textContent = '97% serves';
if (rightArrow) rightArrow.textContent = '3% live traffic';
```

### Verification
- Navigate to Zone 6 after completing Zones 1-5
- Select a transaction from the dropdown
- Click "Process Transaction"
- See: input data appears → both panels show "Processing…" → modern result appears first (250ms) → legacy appears (400ms) → comparator shows drift classification (700ms)
- Transaction log accumulates entries as you process more transactions
- Click "Promote to Canary" — router labels update from "100% serves / 100% shadows" to "97% serves / 3% live traffic"

---

## Execution Order

1. **Improvement 1** first — it changes what gets stored in `requirements_docs`
2. **Improvement 2** second — it changes how the enriched requirements are consumed
3. **Improvement 3** last — it's independent of 1 & 2 but benefits from better generated code

## Files Modified (Summary)

| File | Improvement | Change Type |
|------|------------|-------------|
| `internal/extractor.py` | #1 | Modify `run_extraction()`, add `build_enrichment_section()` |
| `external/generator.py` | #2 | Replace both prompt constants |
| `app.py` | #3 | Add `/api/coexistence/<run_id>/simulate` route |
| `static/index.html` | #3 | Replace Zone 6 panel content |
| `static/app.js` | #3 | Add `runCoexSimulation()`, modify `canaryDecision()` |
| `static/style.css` | #3 | Add coexistence simulator styles |

## What NOT to Change

- Zone 1, Zone 2, Zone 5 — no changes
- `database.py` — no schema changes
- `external/tester.py`, `external/executor.py` — no changes (Zone 3 endpoint reuses their functions)
- Sample COBOL files — no changes
