# CLAUDE.md — Initiative Zero Technical Specification

## What This Is

Initiative Zero is a working Flask application demonstrating an AI-native legacy code modernization pipeline. It is a submission for Wealthsimple's AI Builders program. The prototype makes real Anthropic API calls, uses SQLite for state, executes generated Python code in sandboxed subprocesses, and serves a single-page dark-themed frontend styled as an internal engineering tool.

**This document is the authoritative reference for all development work on this codebase.** Read it fully before making any changes. When in doubt, prioritize not breaking existing functionality.

---

## System Architecture

### Six-Zone Pipeline

The system is organized into six sequential zones with a security firewall between zones 3 and 4:

```
INTERNAL NETWORK                    │ FIREWALL │         EXTERNAL (AI)
                                    │          │
Zone 1: Legacy Environment          │          │  Zone 4: Generation Engine
  └─ File browser, COBOL source     │          │    └─ Claude API generates Python from
                                    │          │       plain-text requirements ONLY
Zone 2: Analysis Engine             │          │
  └─ Claude API analyzes source     │          │  Zone 5: Testing Engine
     code, produces structured      │          │    └─ Executes generated code in sandbox,
     assessment with confidence     │          │       compares against known test vectors
     rubric                         │          │
                                    │          │  Zone 6: Production Deployment
Zone 3: Business Rule Strainer      │          │    └─ Coexistence simulator, canary
  └─ Claude API extracts rules,     │          │       promotion flow
     produces tech-agnostic spec    │          │
  └─ SME review + approval gate     │          │
     (HUMAN DECISION #1)            │          │
```

### Critical Invariant: The Security Firewall

The `external/` directory MUST NEVER import from `internal/`. This is the core architectural insight — proprietary source code stays internal, only plain-text requirements cross the boundary. The file system layout physically mirrors this:

```
initiative-zero/
├── internal/           # Zones 1-3: has access to source code
│   ├── legacy_store.py # Zone 1: reads .cbl files from samples/
│   ├── analyzer.py     # Zone 2: sends source to Claude for analysis
│   └── extractor.py    # Zone 3: extracts rules, builds requirements doc
├── external/           # Zones 4-6: NO source code access
│   ├── generator.py    # Zone 4: generates code from requirements only
│   ├── tester.py       # Zone 5: runs tests, classifies drift
│   └── executor.py     # Zone 5: sandboxed subprocess execution
├── samples/            # Sample COBOL files
├── static/             # Frontend (index.html, style.css, app.js)
├── app.py              # Flask routes for all zones
├── database.py         # SQLite schema, helpers
├── main.py             # Entry point
└── requirements.txt    # Pinned dependencies
```

### Three Human Decision Gates

These are the non-negotiable human gates. AI cannot bypass them:

1. **Zone 3: SME Specification Sign-Off** — Human reviews extracted rules and requirements doc before it crosses the firewall. This is the critical decision named in the submission because errors here propagate through every downstream zone.

2. **Zone 5: Drift Adjudication** — When modern output diverges from legacy behavior (Type 2+ drift), a human must decide: accept the variance, preserve the legacy bug, or escalate to compliance.

3. **Zone 6: Canary Promotion** — Routing live customer traffic from legacy to modern requires human authorization. This cannot be automated in regulated financial services.

### Data Flow

```
COBOL file → Claude analysis (structured JSON) → business rules + requirements doc
  → [HUMAN APPROVES] → requirements cross firewall → Claude generates Python
  → sandbox execution against known test vectors → drift classification
  → [HUMAN ADJUDICATES DRIFT] → coexistence simulation
  → [HUMAN AUTHORIZES CANARY] → staged traffic routing
```

Every human decision is recorded in the `decisions` table with operator, timestamp, rationale, zone, and gate name.

---

## Current State

### What Works End-to-End

- File selection and COBOL source viewing (Zone 1)
- Real Claude API analysis with structured confidence rubric (Zone 2)
- Downloadable analysis report as Markdown (Zone 2)
- Business rule extraction with behavioral observation flagging (Zone 3)
- SME review flow: individual OBS-* review → approve → firewall crossing (Zone 3)
- Downloadable PRD as Markdown (Zone 3)
- Requirements enrichment from Zone 2 analysis data (Zone 3)
- Code generation from requirements-only via Claude API (Zone 4)
- Generation prompt exposed in UI to prove no source code included (Zone 4)
- Sandboxed test execution with drift classification (Zone 5)
- Drift adjudication with three options (Zone 5)
- Coexistence simulator with transaction-by-transaction comparison (Zone 6)
- Aggregate coexistence stats (total, matched, drift, latency delta) (Zone 6)
- Canary promotion / shadow extension decision (Zone 6)
- Run metadata bar with live counters (human decisions, firewall crossings)
- AI Reasoning panel with maturity model reference (Zone 2)
- Full audit trail in SQLite `decisions` table

### What's Already Been Fixed (from review)

These items were identified in a prior review and have been implemented:

- [x] `LEGACY_BEHAVIORS` renamed to `KNOWN_TEST_VECTORS` with explanatory docstring
- [x] Standardized error handling via `api_error()` across all Flask routes
- [x] Version pinning in `requirements.txt`
- [x] Production TODO comments in `app.py`, `executor.py`, `generator.py`
- [x] Simulated latency values named as constants with documentation
- [x] Scale acknowledgment docstring in `legacy_store.py`
- [x] AI Reasoning panel ("Migration Strategy Reasoning") with maturity model
- [x] Run metadata bar (run ID, source, status, human decisions, firewall crossings)
- [x] Coexistence aggregate stats panel
- [x] Dynamic sidebar updates based on selected file

---

## Known Issues & Remaining Work

### Priority 1: Bugs to Fix

#### 1.1 Double variable declaration in `runAnalysis()` (app.js)

In `static/app.js`, the `runAnalysis()` function declares `const rec` and `const rationale` twice — once inside a `setTimeout` callback (~line 237) for the confidence bar animation, and again in the outer scope (~line 253) for the reasoning panel.

This works because the inner declarations are scoped to the `setTimeout` callback, but it's fragile. If someone moves code around, it will break.

**Fix:** Remove the duplicate declarations in the reasoning panel section. Instead, move the reasoning panel population logic inside the existing `setTimeout` callback, after the confidence bar animation completes. Or, rename the outer-scope variables to `recText` and `rationaleText` to avoid shadowing.

**Files:** `static/app.js`

#### 1.2 Zone 6 transaction selector is hardcoded to portfolio_rebalance

The `<select id="coex-txn-selector">` in `index.html` hardcodes five portfolio rebalancing test cases. If a user selects `claims_processing.cbl` as the source file and runs through to Zone 6, the dropdown labels (e.g., "Txn 1: Drift above threshold — SELL") won't match the claims test vectors.

**Fix:** Dynamically populate the transaction selector based on the source file's test vector set. Two approaches:

*Option A (backend):* Add an API route `GET /api/coexistence/<run_id>/test-cases` that returns the available test cases for the run's source file. Call this when entering Zone 6 and populate the selector.

*Option B (frontend-only):* Store the test case metadata in `state` after Zone 5 testing completes (the test results already contain test case names). Use these to rebuild the selector when entering Zone 6.

Option B is simpler and avoids a new route. Implement it by adding to the `runTesting()` function:

```javascript
// After tests complete, populate Zone 6 transaction selector
const selector = document.getElementById('coex-txn-selector');
selector.innerHTML = '';
results.forEach((r, i) => {
  const opt = document.createElement('option');
  opt.value = i;
  opt.textContent = 'Txn ' + (i + 1) + ': ' + r.test_case;
  selector.appendChild(opt);
});
```

**Files:** `static/app.js`, `static/index.html` (remove hardcoded options)

### Priority 2: Demo Video Readiness

#### 2.1 Add loading states for long API calls

Zone 2 (analysis) and Zone 4 (generation) make Claude API calls that can take 5-15 seconds. The current processing indicators (three-dot animation) work, but the demo video would benefit from more descriptive progress text that updates during the wait.

**Fix:** In `runAnalysis()`, update the processing text at intervals:

```javascript
const progressMessages = [
  'Mapping control flow paths…',
  'Identifying business rules in PROCEDURE DIVISION…',
  'Calculating cyclomatic complexity…',
  'Assessing migration economics…',
  'Building confidence rubric…'
];
let msgIndex = 0;
const progressInterval = setInterval(() => {
  msgIndex = (msgIndex + 1) % progressMessages.length;
  document.querySelector('#a-proc .processing-text').textContent = progressMessages[msgIndex];
}, 2500);
// Clear in both success and error paths:
clearInterval(progressInterval);
```

Do the same for Zone 4 generation with appropriate messages.

**Files:** `static/app.js`

#### 2.2 Add keyboard shortcut for zone advancement

During the demo recording, clicking small buttons while narrating is awkward. Adding keyboard shortcuts for common actions would help:

```javascript
document.addEventListener('keydown', (e) => {
  // Right arrow or Enter to advance zone (when advance button is visible and enabled)
  if (e.key === 'ArrowRight' && e.ctrlKey) {
    const activePanel = document.querySelector('.zone-panel.active');
    const advBtn = activePanel?.querySelector('.btn-advance:not(:disabled)');
    if (advBtn) advBtn.click();
  }
});
```

**Files:** `static/app.js`

### Priority 3: Strengthening the Production Narrative

#### 3.1 Add structured logging simulation

The TODO comments mention structured logging, but showing a log panel would strengthen the "this is a real system" narrative.

**Fix:** Add a collapsible "Pipeline Log" panel at the bottom of the content area that accumulates timestamped entries as the pipeline progresses. Each zone transition, API call, and human decision gets a log line:

```
[09:14:22Z] [ZONE-1] Run b3f2a1c7 initiated by S. Chen — source: claims_processing.cbl
[09:14:23Z] [ZONE-2] Analysis started — model: claude-sonnet-4-20250514
[09:14:31Z] [ZONE-2] Analysis complete — confidence: 74% — recommendation: Proceed
[09:14:31Z] [ZONE-3] Extraction started
[09:14:38Z] [ZONE-3] 6 rules extracted (4 explicit, 2 behavioral observations)
[09:15:02Z] [ZONE-3] [HUMAN] SME review: OBS-01 confirmed by S. Chen
[09:15:05Z] [ZONE-3] [HUMAN] Spec approved by S. Chen — firewall crossing authorized
[09:15:06Z] [FIREWALL] Requirements doc (hash: a3f2...) crossed to external zone
[09:15:07Z] [ZONE-4] Generation started — input: requirements only (no source code)
[09:15:19Z] [ZONE-4] Python module generated — 147 lines
[09:15:20Z] [ZONE-5] Test execution started — 5 test cases
[09:15:24Z] [ZONE-5] Results: 3 identical, 1 acceptable, 1 semantic drift
[09:15:30Z] [ZONE-5] [HUMAN] Drift adjudicated: ACCEPT_VARIANCE by S. Chen
[09:15:31Z] [ZONE-6] Entering production deployment
```

Implementation: Add a `pipelineLog(zone, message, isHuman = false)` function that appends to a `<div id="pipeline-log">`. Style it as a terminal-like panel with monospace font, auto-scroll to bottom. Add a toggle button in the topbar to show/hide it.

**Files:** `static/index.html`, `static/style.css`, `static/app.js`

#### 3.2 Add run duration timer

Show elapsed time since run creation in the run metadata bar. This gives the demo video a real-time feel and lets the presenter say "we modernized this system in under 2 minutes."

**Fix:** Add a `<span id="rb-elapsed">` to the run bar. Start a `setInterval` when the run is created:

```javascript
let runStartTime = null;
let elapsedInterval = null;

// In createRunAndAdvance(), after state.runId is set:
runStartTime = Date.now();
elapsedInterval = setInterval(() => {
  const elapsed = Math.floor((Date.now() - runStartTime) / 1000);
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  document.getElementById('rb-elapsed').textContent =
    mins + ':' + String(secs).padStart(2, '0');
}, 1000);
```

**Files:** `static/index.html` (add run-bar-item), `static/app.js`

#### 3.3 Show firewall crossing animation

When the spec is approved and requirements cross the firewall, there's no visual transition. Adding a brief animation would make this moment feel significant in the demo.

**Fix:** When `smeSign('approve')` succeeds, before transitioning to Zone 4:

1. Scroll the firewall divider into view
2. Flash the firewall divider (pulse the red border)
3. Show a brief "Requirements document crossing firewall…" toast
4. 500ms delay, then advance to Zone 4

```javascript
// After successful approval:
const firewallDiv = document.querySelector('.firewall-divider');
firewallDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
firewallDiv.classList.add('crossing');
// Add CSS: .firewall-divider.crossing { animation: firewallPulse 0.6s ease; }
setTimeout(() => {
  firewallDiv.classList.remove('crossing');
}, 600);
```

CSS:
```css
@keyframes firewallPulse {
  0%, 100% { border-color: var(--red); box-shadow: none; }
  50% { box-shadow: 0 0 20px rgba(194,90,75,.3); }
}
.firewall-divider.crossing {
  animation: firewallPulse 0.6s ease;
  padding: 14px 0;
}
```

**Files:** `static/style.css`, `static/app.js`

### Priority 4: Code Quality

#### 4.1 Extract magic strings into constants (app.js)

The operator name `'S. Chen'` appears 8+ times in `app.js`. The session timestamp appears once. Extract these:

```javascript
const OPERATOR = { name: 'S. Chen', role: 'Staff Eng' };
const SESSION_START = new Date().toISOString().split('.')[0] + 'Z';
```

Replace all hardcoded references. This also makes it easy to demonstrate multi-operator scenarios in the future.

**Files:** `static/app.js`

#### 4.2 Add JSDoc comments to key functions

The JavaScript has no documentation. Add JSDoc to the main functions so the codebase reads as professional:

```javascript
/**
 * Run Zone 2 analysis via Claude API.
 * Populates the analysis data grid, confidence rubric, reasoning panel,
 * and migration risk table. Updates run bar status.
 * @throws {Error} If API call fails or returns unparseable response
 */
async function runAnalysis() { ... }
```

At minimum, document: `runAnalysis`, `runStrainer`, `smeSign`, `runGeneration`, `runTesting`, `adjudicate`, `runCoexSimulation`, `canaryDecision`.

**Files:** `static/app.js`

#### 4.3 Add a health check route

```python
@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "version": "0.1.0"})
```

Simple, but signals production awareness.

**Files:** `app.py`

### Priority 5: Playbook Alignment (Stretch)

These enhance the submission's alignment with Anthropic's Code Modernization Playbook but are lower priority than the above.

#### 5.1 Add architectural modernization mention

The Playbook covers monolith → microservices decomposition extensively. The prototype only handles language migration (COBOL → Python). Add a note in the Zone 2 analysis output (or as a TODO in the analysis prompt) that the analysis could identify service boundary decomposition opportunities.

Simplest approach: Add to the `ANALYSIS_USER_PROMPT` in `analyzer.py`:

```
"architectural_recommendations": {{
    "microservice_boundaries": ["list of potential service boundaries if monolith decomposition is applicable"],
    "integration_modernization": ["list of batch-to-streaming or integration upgrade opportunities"]
}}
```

And display these in the Zone 2 UI if present.

**Files:** `internal/analyzer.py`, `static/app.js`, `static/index.html`

#### 5.2 Add ROI framing to analysis report

The Playbook has a full chapter on ROI (speed, risk reduction, knowledge preservation, financial impact). The analysis already captures `migration_economics`, but the downloadable report doesn't frame it as ROI.

**Fix:** Add an "ROI Summary" section to `generate_report_markdown()` that calculates: `ROI = (annual_maintenance_saved - migration_cost) / migration_cost` and frames it alongside the Playbook's four ROI dimensions.

**Files:** `internal/analyzer.py`

---

## Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Run the application
python main.py
# → http://localhost:5000
```

The database (`decisions.db`) is created automatically on first run. Delete it to reset all state.

### Testing

There are no automated tests for the Flask app itself. The testing infrastructure is focused on testing *generated code* (Zone 5). To verify the app is functional:

```bash
# Verify imports
python -c "from app import app; print('✓ App imports clean')"

# Verify database initialization
python -c "from database import init_db; init_db(); print('✓ DB initialized')"

# Verify no stale references
grep -r "LEGACY_BEHAVIORS" . --include="*.py" --include="*.js" && echo "✗ Stale references found" || echo "✓ No stale references"
```

For end-to-end verification, start the app and run through all six zones manually. The verification checklist:

- [ ] Selecting a file shows COBOL source and populates metadata
- [ ] "Run Analysis" creates a run and triggers Zone 2
- [ ] Analysis completes with confidence score, rubric, and reasoning panel
- [ ] Zone 3 extraction produces rules table with OBS-* items flagged
- [ ] SME review flow: open review → review each flag → approve enables
- [ ] Spec approval shows decision record and enables "Generate Code"
- [ ] Zone 4 generation calls Claude API and shows requirements + code side-by-side
- [ ] Zone 5 testing shows drift classification with quality gate metrics
- [ ] Adjudication records decision and enables "Deploy"
- [ ] Zone 6 coexistence simulator processes transactions with stats panel
- [ ] Canary promotion updates slice progression bar
- [ ] Run bar shows correct counts for human decisions and firewall crossings
- [ ] No console errors in browser dev tools throughout

---

## Conventions

- **Error format:** All API errors use `api_error(message, zone, code, status)` → `{"error": str, "error_code": str, "zone": int}`
- **ID generation:** `new_id()` returns 8-char UUID prefix
- **Timestamps:** `now_iso()` returns UTC ISO 8601 with seconds precision
- **JSON from Claude:** Always strip markdown fences via `strip_json_fences()` before parsing
- **CSS variables:** All colors, fonts, and spacing use CSS custom properties defined in `:root`
- **Font stack:** `--mono` (IBM Plex Mono) for data/labels, `--sans` (DM Sans) for body text
- **Security boundary:** Never add imports from `internal/` in any file under `external/`
- **Human gates:** Every human decision must be recorded in the `decisions` table with zone, gate_name, operator, rationale, and timestamp
- **Toast notifications:** Use `toast(msg)` for all user-facing feedback
- **State management:** Global `state` object in `app.js` holds run context; `zoneRan` dict prevents re-running zones on navigation

---

## Submission Context

This prototype is part of a Wealthsimple AI Builders application package. The full submission includes:

1. **Written explanation** (Initiative_Zero.md) — max 500 words
2. **Working prototype** (this codebase) — must actually function
3. **Demo recording** — 2-3 minutes showing the system working

The evaluators are looking for: systems thinking, judgment about where AI should and shouldn't take responsibility, ability to ship end-to-end, and awareness of real-world constraints in regulated financial services. The prototype should feel like a production internal tool, not a marketing demo.
