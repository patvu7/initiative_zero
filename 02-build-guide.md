# Initiative Zero — Build Guide

> **For:** Pat (you)  
> **What this is:** Step-by-step instructions to go from your current HTML prototype to a working full-stack app with real AI. Follow these phases in order. Each phase ends with a checkpoint you can verify before moving on.

---

## Before You Start

### What you need
- [ ] **Replit account** — free tier is fine. Go to [replit.com](https://replit.com) and sign up if you haven't.
- [ ] **Anthropic API key** — you likely already have one. If not, get one at [console.anthropic.com](https://console.anthropic.com). You'll need ~$5 of API credit (Sonnet calls are cheap).
- [ ] **Your current files:** `prototype.html`, `portfolio_rebalance.cbl` (we just created this), the claims processing COBOL from the prototype.

### How to use the technical spec
The other document (`01-technical-spec.md`) is your implementation reference. When you're working in Replit with the AI assistant (or with Claude Code), paste the relevant section of the spec as context. For example, when building Zone 2, paste the `analyzer.py` section. The spec contains every prompt, every schema, every route — the AI coding tool should be able to implement directly from it.

### Time estimate
- **If you're coding with AI assistance (Replit Agent or Claude Code):** 2–3 days
- **If you're coding manually:** 3–5 days
- **Demo recording:** Half day additional

---

## Phase 1: Scaffold the Project

**Goal:** Get a Flask app running on Replit that serves your existing frontend.

### Steps

1. **Create a new Replit project**
   - Go to Replit → "Create Repl"
   - Choose the **Python** template
   - Name it `initiative-zero`

2. **Set up your API key**
   - In Replit, go to the "Secrets" tab (lock icon in the left sidebar)
   - Add a secret: Key = `ANTHROPIC_API_KEY`, Value = your `sk-ant-...` key
   - This keeps your key secure — never put it in code

3. **Install dependencies**
   - Open the Shell tab in Replit and run:
     ```
     pip install flask flask-cors anthropic gunicorn
     ```
   - Or create a `requirements.txt` with those packages

4. **Create the folder structure**
   - In Replit's file browser, create these folders:
     ```
     internal/
     external/
     static/
     samples/
     ```
   - Add empty `__init__.py` files in `internal/` and `external/`

5. **Port your frontend**
   - Copy the `<style>` block from `prototype.html` → `static/style.css`
   - Copy the `<script>` block → `static/app.js`
   - Copy the HTML body → `static/index.html` (update it to link to the external CSS/JS files)
   - Don't refactor the JS yet — just get it loading

6. **Add sample files**
   - Copy the COBOL from the prototype's Zone 1 code display → `samples/claims_processing.cbl`
   - Copy `portfolio_rebalance.cbl` → `samples/portfolio_rebalance.cbl`

7. **Create the database module**
   - Create `database.py` using the schema from the tech spec (Section 3)

8. **Create a minimal `app.py`**
   - Just the Flask setup, the static file serving route, and `init_db()` on startup
   - Test: clicking "Run" in Replit should show your existing prototype UI in the webview

### Checkpoint ✓
- [ ] Replit shows your prototype UI when you hit Run
- [ ] The sidebar, zones, and styling all look correct
- [ ] Your API key is in Replit Secrets (not in any code file)
- [ ] `decisions.db` appears after first run (SQLite initialized)

---

## Phase 2: Zone 1 — Real File Loading

**Goal:** Zone 1 loads actual COBOL files from the `samples/` directory instead of displaying hardcoded HTML.

### Steps

1. **Implement `internal/legacy_store.py`**
   - Reference: Tech spec Section 4.1
   - This reads `.cbl` files from the `samples/` directory

2. **Add the API routes**
   - `GET /api/legacy/files` — returns list of available files
   - `GET /api/legacy/files/<filename>` — returns file content + metadata

3. **Add a file selector to Zone 1 UI**
   - Replace the hardcoded COBOL display with a dropdown
   - On page load, call `/api/legacy/files` to populate the dropdown
   - When a file is selected, call `/api/legacy/files/<name>` and display the code
   - Keep the syntax highlighting from your existing prototype

4. **Create a pipeline run on file selection**
   - When the user selects a file and clicks "Run Analysis →", call `POST /api/runs` to create a new run
   - Store the `run_id` in JS state — every subsequent API call uses this ID

### Checkpoint ✓
- [ ] Zone 1 shows a dropdown with both COBOL files
- [ ] Selecting a file displays its contents with syntax highlighting
- [ ] Clicking "Run Analysis" creates a run (check in the Shell: `sqlite3 decisions.db "SELECT * FROM pipeline_runs"`)

---

## Phase 3: Zone 2 — Real AI Analysis

**Goal:** When you click "Run Analysis," Claude actually analyzes the COBOL and returns structured metrics.

### Steps

1. **Implement `internal/analyzer.py`**
   - Reference: Tech spec Section 4.2
   - This sends the COBOL to Claude with a structured JSON prompt
   - Parses the response and stores it in the `analyses` table

2. **Add the API route**
   - `POST /api/analysis/run` — accepts `{run_id}`, triggers analysis, returns results
   - This runs synchronously (the 3–8 second delay is actually good for the demo — shows real work)

3. **Refactor the Zone 2 frontend**
   - Replace the `runAnalysis()` function that uses `setTimeout`
   - New flow: show processing animation → `fetch('/api/analysis/run')` → hide animation → populate the data grid with real metrics
   - The confidence score, recommendation, and all metrics come from Claude's response

4. **Handle the confidence bar animation**
   - Keep your existing animated confidence bar, but drive it from the real `confidence_score` value

### Checkpoint ✓
- [ ] Clicking "Run Analysis" shows the processing dots for 3–8 seconds
- [ ] Real metrics appear (they'll be different each time — that's correct)
- [ ] The confidence score reflects Claude's actual assessment
- [ ] Check the DB: `sqlite3 decisions.db "SELECT confidence_score, recommendation FROM analyses"`

### Troubleshooting
- If Claude returns malformed JSON, check the prompt — make sure it says "No markdown fences"
- If the API call times out, Replit might need a moment to spin up. Try again.
- If you get a 401 from Anthropic, your API key secret isn't being read — check Replit Secrets

---

## Phase 4: Zone 3 — Real Rule Extraction + Human Gate

**Goal:** Claude extracts business rules from the COBOL and produces a requirements document. The human gate stores decisions in the database.

### Steps

1. **Implement `internal/extractor.py`**
   - Reference: Tech spec Section 4.3
   - This sends COBOL to Claude with the extraction prompt
   - Stores each rule in `business_rules` table
   - Stores the requirements document in `requirements_docs` table
   - Implements `approve_spec()` for the human gate

2. **Add the API routes**
   - `POST /api/extraction/run` — triggers extraction
   - `GET /api/extraction/<run_id>/rules` — returns extracted rules
   - `GET /api/extraction/<run_id>/requirements` — returns the requirements doc
   - `POST /api/extraction/<run_id>/approve` — human approval (stores decision in DB)

3. **Refactor Zone 3 frontend**
   - Replace `runStrainer()` and the hardcoded `RULES` array
   - New flow: processing animation → `fetch('/api/extraction/run')` → populate rules table row by row (keep the staggered animation — it looks great)
   - Show the requirements document text below the rules table

4. **Wire the human gate buttons**
   - "Approve Spec" → `POST /api/extraction/{run_id}/approve`
   - Store the returned `requirements_doc_id` in JS state — Zone 4 needs it
   - Show the decision record from the API response (operator, timestamp)

5. **Update the firewall visualization**
   - The "Passes Through" panel should show the actual requirements document (or a preview)
   - The "Blocked" panel stays the same (source code, schemas, etc.)

### Checkpoint ✓
- [ ] Real rules appear in the table (they'll vary slightly between runs)
- [ ] OBS-type observations may appear (Claude finds behavioral patterns)
- [ ] Clicking "Approve Spec" stores a decision in the DB
- [ ] The `requirements_docs` table has a row with plain-text content and no source code
- [ ] The "Generate Code →" button only enables after approval

---

## Phase 5: Zone 4 — Real Code Generation (The Firewall Moment)

**Goal:** Claude generates Python from the requirements document ONLY. The generation prompt visibly contains zero source code.

### Steps

1. **Implement `external/generator.py`**
   - Reference: Tech spec Section 4.4
   - ⚠ This file is in the `external/` directory — it cannot import from `internal/`
   - It reads ONLY from the `requirements_docs` table
   - It stores the `generation_prompt` in the DB for auditability

2. **Add the API routes**
   - `POST /api/generation/run` — accepts `{run_id, requirements_doc_id}`
   - `GET /api/generation/<run_id>` — returns generated code + the generation prompt

3. **Refactor Zone 4 frontend**
   - Replace `runGeneration()` and its `setTimeout`
   - Left panel: show the requirements text (fetched from `/api/extraction/{run_id}/requirements`)
   - Right panel: show the generated Python code (from `/api/generation/{run_id}`)

4. **Add the "View Generation Prompt" panel** ← THIS IS KEY
   - Below the split view, add a collapsible panel labeled "View Generation Prompt"
   - When expanded, it shows the exact prompt sent to Claude
   - The reviewer can verify: no COBOL, no variable names, no schemas — just business requirements
   - Style it with a subtle border and the `--blue-dim` background from your existing color system

### Checkpoint ✓
- [ ] Generated Python appears in the right panel
- [ ] The code references business rule IDs (BR-001, etc.) in docstrings
- [ ] "View Generation Prompt" shows the prompt — and it contains NO source code
- [ ] Check the DB: the `generation_prompt` column in `generated_code` table has no COBOL

### This is your demo highlight
When you record the video, pause here and say something like: "Open the generation prompt. Zero source code. The generator has never seen the COBOL. This isn't a policy — it's an architectural boundary." Then show the file structure briefly.

---

## Phase 6: Zone 5 — Real Test Execution + Drift

**Goal:** The system actually runs both legacy behavior and generated Python, compares outputs, and classifies drift.

### Steps

1. **Implement `external/executor.py`**
   - Reference: Tech spec Section 4.5
   - Sandboxed Python execution using `subprocess`
   - Writes generated code to a temp file, executes with test harness, captures output

2. **Implement `external/tester.py`**
   - Reference: Tech spec Section 4.6
   - Contains the legacy behavior test cases (known COBOL outputs)
   - Builds test harnesses, executes generated code, classifies drift
   - The drift classification logic compares legacy vs modern outputs

3. **Add the API routes**
   - `POST /api/testing/run` — runs all test cases, returns results
   - `GET /api/testing/<run_id>/results` — returns stored test results
   - `POST /api/testing/<run_id>/adjudicate` — human drift decision

4. **Refactor Zone 5 frontend**
   - Replace `runTesting()` and the hardcoded test table
   - Populate the table from real execution results
   - Color-code drift types using your existing status chips
   - The rounding test case should naturally surface as Type 2 if the generated code uses proper rounding

5. **Wire the drift adjudication gate**
   - "Accept Variance" / "Preserve Bug" / "Escalate" → `POST /api/testing/{run_id}/adjudicate`
   - Store decision in DB, show the decision record

### Checkpoint ✓
- [ ] Test results populate from real execution
- [ ] At least one Type 0 (Identical) result appears
- [ ] The rounding edge case likely shows as Type 2 (Semantic)
- [ ] Drift adjudication stores to the database
- [ ] The "Deploy →" button enables after adjudication

### If code execution fails
This is the riskiest phase. The generated Python might not be directly executable by the test harness. Two fallback options:
- **Option A:** Have Claude generate the code WITH a test interface (add to the generation prompt: "Include a `run_test(input_dict)` method that accepts a dict and returns a dict")
- **Option B:** If execution fails for a test case, show the failure in the UI as a Type 3 (Breaking) drift — this is actually realistic and demonstrates the system handling errors

---

## Phase 7: Zone 6 + Audit Trail

**Goal:** Wire production decisions to the database. Add an audit trail view.

### Steps

1. **Wire Zone 6 human gate**
   - "Promote to Canary" / "Extend Shadow" → `POST /api/production/{run_id}/decide`
   - Keep the existing coexistence diagram and slice progression UI — those are fine as simulated

2. **Add audit trail endpoint**
   - `GET /api/runs/{run_id}/decisions` — returns all human decisions for a run
   - Add a small "Audit Log" button in the sidebar footer that shows all decisions with timestamps

3. **Update sidebar status indicators**
   - As each zone completes (via API responses), update the sidebar nav status chips
   - Use the existing `updateStatus()` function but trigger it from API responses instead of `setTimeout`

### Checkpoint ✓
- [ ] All three human gates store decisions in the `decisions` table
- [ ] The audit trail shows all decisions for a run in chronological order
- [ ] Each decision has: zone, gate name, decision, operator, timestamp

---

## Phase 8: Polish + End-to-End Testing

**Goal:** Make sure the full pipeline runs smoothly from Zone 1 to Zone 6.

### Steps

1. **Full run-through with `portfolio_rebalance.cbl`**
   - This is your primary demo file — it's Wealthsimple-relevant
   - Run the entire pipeline start to finish
   - Note any rough edges in the UI

2. **Full run-through with `claims_processing.cbl`**
   - This shows the system is reusable across different legacy systems
   - You might show this briefly at the end of the demo

3. **Error handling**
   - What happens if the Claude API call fails? Show a user-friendly error, not a stack trace
   - What happens if generated code doesn't execute? Show it as a test failure, not a crash
   - Add try/catch around every API call in the frontend JS

4. **Loading state polish**
   - Each API call takes 3–10 seconds — make sure every call has a visible loading state
   - The processing dots animation from your existing prototype works well

5. **Deploy to Replit hosting**
   - In Replit, click the "Deploy" button (or just use the preview URL)
   - Test the deployed URL in a fresh browser tab
   - Make sure the API key works in the deployed environment

### Checkpoint ✓
- [ ] Full pipeline runs start-to-finish on portfolio rebalancing file without errors
- [ ] Full pipeline runs on claims processing file without errors
- [ ] API errors show user-friendly messages
- [ ] Deployed URL works in a fresh browser

---

## Phase 9: Record the Demo

**Goal:** 2–3 minute video showing the system actually working.

### Prep

- [ ] Do one fresh run-through right before recording so the results are clean
- [ ] Use screen recording (QuickTime on Mac, OBS, or Loom)
- [ ] Record at 1920x1080 or higher
- [ ] Use the portfolio rebalancing file as your primary example

### Script

**[0:00–0:15] Intro**
"This is Initiative Zero — an AI-native pipeline that modernizes legacy financial systems. I'll walk through a live run on a portfolio rebalancing engine written in COBOL."

**[0:15–0:45] Zone 1 → Zone 2**
Select the portfolio file. Click "Run Analysis." Wait for real results. "The AI is analyzing this COBOL in real time — structure, coverage gaps, migration economics. It's never seen this file before."

**[0:45–1:15] Zone 3: Extraction + Human Gate**
Click "Extract Rules." Watch rules populate. "It found [X] business rules including [mention any behavioral observations]. This is why human validation matters — the AI extracts what the code does, but only a domain expert knows what it *should* do." Click approve.

**[1:15–1:35] The Firewall**
"Watch what crosses the security boundary." Show the requirements document. Click "View Generation Prompt." "No COBOL. No variable names. No schemas. The code generator has never seen the source. This is an architectural boundary, not a policy."

**[1:35–2:05] Zone 4 → Zone 5**
Generated Python appears. Click "Run Tests." Results populate. Point out the drift classification. If there's a Type 2: "The system caught a semantic difference — [describe it]. It classified this as needing human judgment."

**[2:05–2:25] Human Decision**
Make the drift decision. "This is the critical gate. The AI does the cognitive heavy lifting, but the risk decision stays human."

**[2:25–2:45] Zone 6 + Closing**
Show coexistence model. "Both systems run in parallel. Legacy serves traffic. Modern shadows. Humans promote when confidence is earned."

**[2:45–3:00] Wrap**
"A 3-person pod does what used to take 15 specialists and 18 months. The AI compresses the comprehension phase from months to days. The humans keep the risk decisions."

### Post-recording
- Trim dead air, especially during API loading times (or speed them up slightly)
- Export as MP4
- Keep it under 3 minutes

---

## Quick Reference: What to Paste into AI Coding Tools

When you're building each phase, paste the relevant section of the tech spec as context:

| Phase | Paste this section from `01-technical-spec.md` |
|---|---|
| Phase 1 (Scaffold) | Sections 1, 2, 3 (Stack, File Structure, Database Schema) |
| Phase 2 (Zone 1) | Section 4.1 (`legacy_store.py`) + Section 5 (Zone 1 routes from `app.py`) |
| Phase 3 (Zone 2) | Section 4.2 (`analyzer.py`) + Section 5 (Zone 2 routes) |
| Phase 4 (Zone 3) | Section 4.3 (`extractor.py`) + Section 5 (Zone 3 routes) |
| Phase 5 (Zone 4) | Section 4.4 (`generator.py`) + Section 5 (Zone 4 routes) + Section 6.3 (new UI panel) |
| Phase 6 (Zone 5) | Sections 4.5 + 4.6 (`executor.py`, `tester.py`) + Section 5 (Zone 5 routes) |
| Phase 7 (Zone 6) | Section 5 (Zone 6 + Audit routes) |
| Phase 8 (Polish) | Section 6 (Frontend Refactoring Notes) |

---

## If Things Go Wrong

| Problem | Fix |
|---|---|
| Claude returns markdown-fenced JSON | The prompts say "no markdown fences" but Claude sometimes ignores this. The code strips fences in the parsing step. If it still fails, add `response_format` or retry once. |
| Generated Python won't execute | Add to the generation prompt: "Include a `process(input_dict: dict) -> dict` function that accepts and returns plain dictionaries." This makes the test harness simpler. |
| API calls take >15 seconds | Sonnet 4 sometimes queues. Retry. If persistent, check your API key tier. |
| Replit won't install anthropic | Try `pip install anthropic --break-system-packages` in the Shell. |
| Frontend shows old cached version | Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows). |
| SQLite "database is locked" | Only one tab should be hitting the app. Close other tabs. |
| Zone 4 somehow gets source code | Check the `external/generator.py` imports. It must NOT import from `internal/`. It only reads from `requirements_docs` table. |
