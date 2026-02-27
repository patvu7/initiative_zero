# Initiative Zero — Application Package

**Applicant:** Patrick Vu

---

## Deliverables

### 1. Written Explanation — `Initiative_Zero.md`

The 500-word written response covering:

- **What the human can now do:** A 3-person pod modernizes a portfolio rebalancing engine in 8 weeks instead of 18 months, without risking the live system.
- **What AI is responsible for:** Comprehension, business rule extraction, code generation, testing, and drift classification. AI also serves as an architectural thought partner throughout.
- **Where AI must stop:** The specification sign-off. AI can extract what code *does*, but only a domain expert can confirm what it *should* do. This validated spec is the sole artifact that crosses the security firewall.
- **What breaks first at scale:** The SME validation bottleneck. Each extraction requires ~2 weeks of expert review, and the review queue becomes the critical path across multiple systems.

### 2. Working Prototype — `initiative-zero/`

A fully functional Flask application that demonstrates the complete six-zone modernization pipeline. This is not a mockup. It makes real Claude API calls to analyze COBOL, extract business rules, generate Python, and classify drift.

**To run:**

```bash
cd initiative-zero
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here
python main.py
# Open http://localhost:5000
```

**Architecture:**

```
initiative-zero/
├── app.py                  # Flask routes, all 6 zones
├── main.py                 # Entry point
├── database.py             # SQLite schema + helpers
├── requirements.txt        # Python dependencies
│
├── internal/               # INSIDE the security firewall
│   ├── legacy_store.py     #   Zone 1: Legacy file access
│   ├── analyzer.py         #   Zone 2: AI analysis engine (Claude API)
│   └── extractor.py        #   Zone 3: Business rule extraction (Claude API)
│
├── external/               # OUTSIDE the firewall, no source code access
│   ├── generator.py        #   Zone 4: Code generation from requirements only
│   ├── tester.py           #   Zone 5: Drift classification + test execution
│   └── executor.py         #   Sandboxed Python execution for generated code
│
├── samples/                # Sample legacy COBOL files
│   ├── claims_processing.cbl      # Insurance claims (demo default)
│   └── portfolio_rebalance.cbl    # Wealth management rebalancing engine
│
└── static/                 # Frontend
    ├── index.html          # Single-page app
    ├── style.css           # Dark theme, engineering-tool aesthetic
    └── app.js              # Zone navigation, API calls, UI state
```

**Key design decisions:**

- The `internal/` and `external/` directory separation physically mirrors the security firewall. The generator module (`external/generator.py`) has no imports from `internal/`. It receives only plain-text requirements via the database.
- Every human decision (spec approval, drift adjudication, production authorization) is recorded in a `decisions` table with operator, timestamp, and rationale.
- Generated code is executed in a subprocess sandbox with a 10-second timeout.
- The coexistence simulator in Zone 6 runs real transactions through both legacy behavioral models and AI-generated code, comparing outputs in real time.

**Three human gates in the pipeline:**

1. **Specification Sign-Off** (Zone 3): SME validates extracted business rules before they cross the firewall
2. **Drift Adjudication** (Zone 5): Human classifies semantic differences (e.g., COBOL truncation vs. Python rounding)
3. **Production Authorization** (Zone 6): Tech lead approves canary promotion with staged rollout

### 3. Architecture Diagram — `architecture.drawio`

Open in [draw.io](https://app.diagrams.net/) or import into any diagrams.net-compatible tool. Shows the full pipeline: legacy environment → analysis → rule extraction → security firewall → generation → testing → production, with feedback loops and human gates marked.

### 4. Demo Video

Recorded separately. The walkthrough follows the prototype through all six zones using the `portfolio_rebalance.cbl` sample, demonstrating:

- Legacy code inspection
- AI-powered analysis with confidence scoring
- Business rule extraction and SME review flow
- Firewall crossing (requirements only, zero source code)
- Code generation from requirements
- Drift classification and human adjudication
- Coexistence simulator in shadow mode
