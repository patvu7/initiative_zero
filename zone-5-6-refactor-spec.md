# Technical Spec: Zone 5 & Zone 6 Refactor

**Context:** Initiative Zero prototype for Wealthsimple AI Builders application.  
**Goal:** Fix the testing zone to actually use Claude API for test generation, and simplify the production zone to focus on the deployment decision rather than re-running tests.

---

## Zone 5 — Testing Engine

### Problem

`external/tester.py` uses hardcoded `KNOWN_TEST_VECTORS` for all test cases. No Claude API call is made. The written explanation claims AI "generates tests from the same requirements," but the prototype doesn't do this. This is the most credible gap in the submission.

### New Architecture

Zone 5 becomes a two-phase process:

**Phase 1 — AI Test Generation (new Claude API call)**
- Read the requirements document from the `requirements_docs` table (same doc that crossed the firewall)
- Send it to Claude with a prompt that asks for structured test cases as JSON
- Claude returns test cases with: `name`, `input` (dict), `expected_behavior` (plain-text description of what should happen), and `category` (e.g. "happy path", "boundary", "error handling", "edge case")
- Store these in a new `ai_generated_tests` table
- The AI does NOT generate legacy outputs — it generates *expected behavior descriptions* based on the requirements

**Phase 2 — Test Execution & Drift Classification (modified existing flow)**
- For each AI-generated test case, execute the generated Python code via the existing sandbox (`executor.py`)
- For test cases that match known legacy execution traces (the existing `KNOWN_TEST_VECTORS`), also compare against legacy outputs and classify drift
- For test cases that DON'T have a legacy trace, validate against the AI's expected behavior description (pass/fail based on whether the output matches the described behavior)
- Drift classification remains the same 4-tier system (Identical, Acceptable, Semantic, Breaking)

### File Changes

#### `external/tester.py`

1. Add a new function `generate_test_cases(run_id: str) -> list` that:
   - Reads the requirements doc from DB (`requirements_docs` table, by `run_id`)
   - Calls Claude API (`claude-sonnet-4-20250514`) with a system prompt instructing it to generate comprehensive test cases as JSON
   - The prompt should request this JSON structure per test case:
     ```json
     {
       "name": "descriptive test name",
       "category": "happy_path|boundary|error_handling|edge_case|regulatory",
       "input": {"field": "value", ...},
       "expected_output": {"status": "...", "payout": "...", ...},
       "rationale": "why this test case matters — references BR-### or OBS-###"
     }
     ```
   - Stores results in a new `ai_generated_tests` table
   - Returns the list of generated test cases

2. Keep `KNOWN_TEST_VECTORS` but rename to `LEGACY_EXECUTION_TRACES` and add a docstring clarifying these represent verified outputs from running the actual legacy system. They serve as the ground truth for drift comparison.

3. Modify `run_tests(run_id)` to:
   - First call `generate_test_cases(run_id)` to get AI-generated tests
   - Execute each AI-generated test against the generated code
   - For each test, check if a matching legacy trace exists (match by comparing input fields). If yes, classify drift against the legacy trace. If no legacy trace, compare against the AI's `expected_output` and classify as "Validated against requirements" (Type 0) or "Deviation from requirements" (Type 2).
   - Return combined results with a `source` field: `"legacy_trace"` or `"ai_generated"`

4. Add Anthropic client setup (same pattern as `generator.py` — import os, anthropic, use `_get_client()`)

#### `database.py`

Add a new table in `init_db()`:

```sql
CREATE TABLE IF NOT EXISTS ai_generated_tests (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
    name TEXT NOT NULL,
    category TEXT,
    input_data TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    rationale TEXT,
    source TEXT DEFAULT 'ai_generated',
    created_at TEXT DEFAULT (datetime('now'))
);
```

#### `app.py`

1. Add a new endpoint `GET /api/testing/<run_id>/generated-tests` that returns AI-generated test cases for display in the UI
2. Modify `POST /api/testing/run` — no route change needed, `run_tests()` already handles the full flow

#### `static/app.js` — Zone 5 UI Changes

1. Add a new Phase 1 processing state after clicking "Run Tests →":
   - Show: "Test Agent generating test cases from requirements…" (with rotating progress messages like Zone 2/4)
   - When test generation completes, show a summary: "X test cases generated (Y from AI, Z from legacy traces)"

2. Add a test case source indicator to the test results table:
   - New column: "Source" showing either a chip `AI Generated` (blue) or `Legacy Trace` (green)
   - This visually proves that AI is doing the test design work

3. Keep the existing drift classification table and quality gate metrics — just add the source column

### Claude API Prompt Design for Test Generation

**System prompt:**
```
You are a test case generation agent for a financial services modernization pipeline.
You generate comprehensive test suites from plain-text business requirements.

CRITICAL CONSTRAINTS:
- Generate test cases that cover ALL business rules (BR-###) in the requirements
- Include edge cases, boundary conditions, error handling, and regulatory scenarios
- Each test case must reference which business rule(s) it validates
- Input fields must match the domain (use realistic financial values)
- Expected outputs must be precise (exact amounts, exact status codes)
- Use Decimal-compatible string values for all financial amounts

Return ONLY valid JSON. No markdown fences, no explanation.
```

**User prompt:**
```
Generate a comprehensive test suite for the following business requirements.

REQUIREMENTS DOCUMENT:
{requirements_text}

Return a JSON array of test cases with this structure:
[
  {
    "name": "descriptive test name",
    "category": "happy_path|boundary|error_handling|edge_case|regulatory",
    "input": {"field_name": "string_value", ...},
    "expected_output": {"field_name": "string_value", ...},
    "rationale": "References BR-### or OBS-### — explains what this tests"
  }
]

Generate at least 8 test cases covering:
- 2+ happy path scenarios
- 2+ boundary/threshold conditions
- 2+ error handling cases (missing fields, invalid values)
- 2+ edge cases or regulatory scenarios specific to this domain

All financial values must be strings (e.g. "5000.00" not 5000).
```

---

## Zone 6 — Production Deployment

### Problem

Zone 6 currently has three issues:
1. The coexistence simulator re-runs Zone 5 tests with a different UI — it adds no new information
2. The slice progression bar has pre-completed stages the user never interacted with
3. Hardcoded simulated latencies presented as measurements undermine the "real tool" aesthetic

### New Architecture

Zone 6 becomes a deployment readiness dashboard + human gate. Remove the coexistence simulator entirely. The zone should answer one question: "Based on everything the pipeline has produced, should we promote to production?"

**Section 1 — Deployment Readiness Summary**
A compact dashboard that pulls data from prior zones:
- **Analysis confidence** (from Zone 2): score + recommendation
- **Rules validated** (from Zone 3): count + SME sign-off status
- **Test results** (from Zone 5): pass rate, drift summary, quality gate status
- **Human decisions made** (from decisions table): list of all gate decisions with timestamps

This is a read-only summary. No new API calls. Just aggregates what already exists.

**Section 2 — Rollout Plan**
A simple visual showing the staged deployment plan:
- Shadow → Canary (3%) → Graduated (25%) → Full Production
- Each stage shows: what happens, what's monitored, what triggers next promotion
- This is static/informational — it communicates the deployment strategy

**Section 3 — Production Authorization (Human Gate)**
The existing canary promotion gate, simplified:
- "Authorize Shadow Deployment" as the primary action (not "Promote to Canary" — shadow comes first)
- "Request Extended Review" as the secondary action
- Decision record with operator, timestamp, rationale
- This is the third and final human gate in the pipeline

### File Changes

#### `app.py`

1. Add a new endpoint `GET /api/deployment/<run_id>/readiness` that aggregates:
   - Analysis confidence + recommendation from `analyses` table
   - Rule count + validation status from `business_rules` table
   - Test pass rate + drift counts from `test_results` table
   - All decisions from `decisions` table
   - Returns a single JSON object with the full readiness picture

2. Keep `POST /api/production/<run_id>/decide` as-is — it already works correctly

3. Remove `POST /api/coexistence/<run_id>/simulate` endpoint entirely

#### `static/index.html` — Zone 6 Markup

Replace the entire Zone 6 panel content with:

```
Section: Deployment Readiness
├── 4-column summary grid (Analysis | Rules | Tests | Decisions)
│   Each card shows: key metric, status chip, detail text
│
Section: Rollout Plan  
├── Horizontal stage visualization (simpler than current slice-bar)
│   Shadow → Canary 3% → Graduated 25% → Full
│   Each stage: name, description, monitoring criteria
│
Section: Human Gate — Production Authorization
├── Gate description (same amber-bordered human-gate style)
├── Two buttons: "Authorize Shadow Deployment" | "Request Extended Review"  
└── Decision record (same dr-* styles)
```

#### `static/app.js` — Zone 6 Logic

1. Remove all coexistence simulator functions:
   - `runCoexSimulation()`
   - All `coexStats` tracking
   - All `coexTxnCount` tracking
   - The Zone 6 transaction selector population from Zone 5

2. Add a new function `loadDeploymentReadiness()` that:
   - Calls `GET /api/deployment/<run_id>/readiness`
   - Populates the 4-column readiness grid
   - Populates the decisions audit trail
   - Called when Zone 6 becomes active (from `runZone(6)`)

3. Simplify `canaryDecision()`:
   - Rename to `productionDecision(action)`
   - "authorize" action → records decision, updates status, shows success record
   - "review" action → records decision, shows "extended review" record
   - Remove the slice-bar stage manipulation
   - Remove the router label updates

#### `static/style.css`

1. Remove all `.coex-*` styles (coexistence simulator)
2. Add styles for the readiness summary grid (reuse existing `.data-grid` / `.data-card` patterns)
3. Keep `.slice-stage` styles but simplify — all stages start as "upcoming" since none are pre-completed

#### `external/tester.py`

1. Remove the coexistence-related imports and functions that Zone 6 was using (`build_test_harness`, `KNOWN_TEST_VECTORS`, `classify_drift` were imported by `app.py` for the simulate endpoint)
2. Actually, `build_test_harness` and `classify_drift` are still needed by Zone 5's `run_tests()` — just remove the simulate endpoint in `app.py` that was calling them

---

## What NOT to Change

- **Zones 1–4**: No changes. They work well.
- **Architecture diagram**: No changes needed.
- **Written explanation (`Initiative_Zero.md`)**: No changes needed — it already describes the correct architecture. The prototype is catching up to the spec.
- **Security boundary**: The test generation prompt receives the requirements doc (which already crossed the firewall). No source code touches the external zone. This is correct.
- **Database schema**: Only additive change (new `ai_generated_tests` table). No migrations needed.
- **Existing test execution**: The sandbox executor, drift classification logic, and adjudication flow all stay. Zone 5 Phase 2 reuses them.

---

## Implementation Order

1. **Database first** — Add the new table
2. **`tester.py`** — Add `generate_test_cases()`, rename vectors, modify `run_tests()`
3. **`app.py`** — Add new endpoints, remove simulate endpoint
4. **`app.js`** — Zone 5 UI updates (two-phase display, source column)
5. **`index.html`** — Replace Zone 6 markup
6. **`app.js`** — Zone 6 logic (readiness loader, simplified decision)
7. **`style.css`** — Remove coex styles, verify readiness grid styling
8. **Test the full flow** — Run through all 6 zones end-to-end to verify nothing breaks

---

## Validation Criteria

After implementation, the full pipeline walkthrough should demonstrate:

1. **Zone 5** makes a real Claude API call to generate test cases
2. **Zone 5** shows both AI-generated and legacy-trace test sources in the results table
3. **Zone 5** drift classification still works correctly (Type 0–3)
4. **Zone 5** quality gate still blocks on unresolved Type 2+ drift
5. **Zone 6** shows a clean readiness summary pulling from all prior zones
6. **Zone 6** does NOT re-run tests or simulate transactions
7. **Zone 6** human gate records the decision in the audit trail
8. **Zone 6** feels like a natural conclusion, not a repetition of Zone 5
