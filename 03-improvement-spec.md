# Initiative Zero — Improvement Spec (Round 2)

> **Purpose:** This document is a Claude Code–executable specification for the second round of improvements to the Initiative Zero prototype. Each section contains the problem, the solution, affected files, and exact implementation details.

---

## Summary of Changes

| # | Zone | Issue | Fix |
|---|------|-------|-----|
| 1 | Zone 1 | Filename overflows its container when long | CSS truncation + tooltip |
| 2 | Zone 2 | Analysis cards are too shallow; no scoring rubric; no downloadable report | Expand analysis prompt, add rubric, generate downloadable report |
| 3 | Zone 3 | No real SME review flow; no viewable/downloadable tech-agnostic PRD | Add SME review modal, PRD generation, download endpoint |
| 4 | Cross-cutting | `app.js` is duplicated (inline in `index.html` AND as separate file) | Remove inline `<script>` block from `index.html`, keep only `<script src>` |

---

## 1. Zone 1 — Filename Overflow Fix

### Problem
When a long filename like `portfolio_rebalance.cbl` is selected, the `code-filename-display` and `meta-filename` text overflows or pushes layout. The file selector dropdown also doesn't truncate.

### Files to Modify
- `static/style.css`
- `static/index.html` (minor attribute)

### CSS Changes — `static/style.css`

Add the following rules (append or integrate into existing selectors):

```css
/* ─── FILENAME OVERFLOW FIX ─── */
.code-filename {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
  vertical-align: middle;
}

.file-meta-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

#file-selector {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Tooltip on hover for truncated filenames */
.code-filename[title]:hover {
  cursor: default;
}
```

### JS Change — `static/app.js`

In the `onFileSelected` function, add a `title` attribute so hovering reveals the full path:

```javascript
// Inside onFileSelected(), after setting textContent:
const filenameEl = document.getElementById('code-filename-display');
filenameEl.textContent = 'src/' + filename;
filenameEl.title = 'src/' + filename;  // ← ADD THIS LINE
```

---

## 2. Zone 2 — Expanded Analysis, Scoring Rubric, Downloadable Report

### 2.1 Problem
- The analysis cards show minimal data (one line per metric). Reviewers need richer context.
- There is no scoring rubric explaining how `confidence_score` was computed.
- There is no way to download or retrieve the full analysis as a standalone document.

### 2.2 Solution Overview
1. **Expand the Claude analysis prompt** to return more detail per category and a scoring rubric breakdown.
2. **Expand the UI data cards** to render the additional detail (sub-items, risk notes, rubric).
3. **Add a `/api/analysis/<run_id>/report` endpoint** that returns a downloadable Markdown analysis report.
4. **Add a "Download Report" button** in the Zone 2 UI.

### 2.3 Files to Modify
- `internal/analyzer.py` — prompt + response parsing
- `app.py` — new report endpoint
- `static/index.html` — expanded UI cards + download button
- `static/style.css` — styling for expanded cards + rubric
- `static/app.js` — render expanded data + download handler

---

### 2.4 `internal/analyzer.py` — New Prompt & Parser

Replace `ANALYSIS_USER_PROMPT` with the expanded version below. The system prompt stays the same.

```python
ANALYSIS_USER_PROMPT = """Analyze this {language} source code and return a JSON object
with exactly this structure. No markdown fences, no explanation — just the JSON object.

{{
  "app_analysis": {{
    "purpose": "one-line description of what this system does",
    "stack": "e.g. COBOL → DB2 → JCL",
    "dependencies_upstream": <integer>,
    "dependencies_downstream": <integer>,
    "criticality": "Tier 1" or "Tier 2" or "Tier 3",
    "criticality_rationale": "why this tier was assigned",
    "domain": "e.g. Claims Processing, Portfolio Management",
    "data_sensitivity": "High" or "Medium" or "Low",
    "data_sensitivity_rationale": "why — mention PII, financial data, etc."
  }},
  "code_analysis": {{
    "cyclomatic_complexity": <integer>,
    "cyclomatic_detail": "brief explanation of most complex control paths",
    "dead_code_pct": <float, 0-100>,
    "dead_code_detail": "what appears to be dead and why",
    "security_issues": <integer>,
    "security_detail": ["list each security concern with severity"],
    "workarounds_identified": <integer>,
    "workaround_details": ["list of identified workarounds with context"],
    "code_quality_notes": ["list of code quality observations — naming, structure, comments"]
  }},
  "test_analysis": {{
    "estimated_coverage_pct": <float, 0-100>,
    "coverage_rationale": "how this was estimated",
    "has_unit_tests": "Exists (sparse)" or "Comprehensive" or "None",
    "has_integration_tests": "Yes" or "None",
    "untested_edge_cases": ["list of specific edge cases not covered"],
    "testing_risks": ["list of testing risks for migration — e.g. no regression baseline"]
  }},
  "migration_economics": {{
    "estimated_annual_maintenance": "$X.XM/yr",
    "maintenance_breakdown": "what drives this cost — staffing, vendor, infra",
    "estimated_ai_migration_cost": "$XXXK",
    "estimated_manual_migration_cost": "$X.XM / XX mo",
    "roi_breakeven_months": <integer>,
    "hidden_costs": ["list of costs often missed — retraining, parallel running, etc."]
  }},
  "migration_risks": [
    {{
      "risk": "description of the risk",
      "severity": "High" or "Medium" or "Low",
      "mitigation": "suggested mitigation"
    }}
  ],
  "confidence_rubric": {{
    "code_clarity": {{
      "score": <float 0.0-1.0>,
      "weight": 0.20,
      "rationale": "how readable and well-structured the code is"
    }},
    "business_rule_extractability": {{
      "score": <float 0.0-1.0>,
      "weight": 0.25,
      "rationale": "how clearly business rules can be identified and isolated"
    }},
    "test_coverage_confidence": {{
      "score": <float 0.0-1.0>,
      "weight": 0.20,
      "rationale": "confidence in verifying migration correctness"
    }},
    "dependency_isolation": {{
      "score": <float 0.0-1.0>,
      "weight": 0.15,
      "rationale": "how isolated this module is from upstream/downstream systems"
    }},
    "migration_complexity": {{
      "score": <float 0.0-1.0>,
      "weight": 0.20,
      "rationale": "inverse complexity — higher means simpler migration"
    }}
  }},
  "confidence_score": <float between 0.0 and 1.0 — MUST equal weighted sum of rubric scores>,
  "recommendation": "Proceed" or "Caution" or "Block",
  "recommendation_rationale": "2-3 sentences explaining the recommendation, referencing specific rubric scores"
}}

SOURCE CODE:
```{language}
{source_code}
```"""
```

Update `run_analysis` to increase `max_tokens` to handle the larger response:

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4000,  # ← increased from 2000
    system=ANALYSIS_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": prompt}]
)
```

Add a report generation function at the bottom of `analyzer.py`:

```python
def generate_report_markdown(run_id: str) -> str:
    """Generate a downloadable Markdown analysis report from stored analysis data."""
    db = get_db()
    run_row = db.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    analysis_row = db.execute("SELECT * FROM analyses WHERE run_id = ?", (run_id,)).fetchone()
    db.close()

    if not analysis_row or not analysis_row["metrics"]:
        return None

    m = json.loads(analysis_row["metrics"])
    app = m.get("app_analysis", {})
    code = m.get("code_analysis", {})
    test = m.get("test_analysis", {})
    econ = m.get("migration_economics", {})
    risks = m.get("migration_risks", [])
    rubric = m.get("confidence_rubric", {})
    conf = analysis_row["confidence_score"]
    rec = analysis_row["recommendation"]
    rationale = m.get("recommendation_rationale", "")

    report = f"""# Initiative Zero — Analysis Report

**Source File:** {run_row["source_file"]}
**Language:** {run_row["source_language"]}
**Run ID:** {run_id}
**Generated:** {analysis_row["created_at"]}
**Recommendation:** {rec}
**Confidence Score:** {conf:.0%}

---

## Executive Summary

{rationale}

---

## 1. Application Analysis

| Attribute | Value |
|-----------|-------|
| Purpose | {app.get("purpose", "—")} |
| Stack | {app.get("stack", "—")} |
| Upstream Dependencies | {app.get("dependencies_upstream", "—")} |
| Downstream Dependencies | {app.get("dependencies_downstream", "—")} |
| Criticality | {app.get("criticality", "—")} |
| Criticality Rationale | {app.get("criticality_rationale", "—")} |
| Domain | {app.get("domain", "—")} |
| Data Sensitivity | {app.get("data_sensitivity", "—")} |
| Data Sensitivity Rationale | {app.get("data_sensitivity_rationale", "—")} |

---

## 2. Code Analysis

| Metric | Value |
|--------|-------|
| Cyclomatic Complexity | {code.get("cyclomatic_complexity", "—")} |
| Dead Code | {code.get("dead_code_pct", 0):.0f}% |
| Security Issues | {code.get("security_issues", 0)} |
| Workarounds | {code.get("workarounds_identified", 0)} |

**Complexity Detail:** {code.get("cyclomatic_detail", "—")}

**Dead Code Detail:** {code.get("dead_code_detail", "—")}

**Security Concerns:**
"""
    for item in code.get("security_detail", []):
        report += f"- {item}\n"

    report += f"""
**Workaround Details:**
"""
    for item in code.get("workaround_details", []):
        report += f"- {item}\n"

    report += f"""
**Code Quality Notes:**
"""
    for item in code.get("code_quality_notes", []):
        report += f"- {item}\n"

    report += f"""
---

## 3. Test Analysis

| Metric | Value |
|--------|-------|
| Estimated Coverage | {test.get("estimated_coverage_pct", 0):.0f}% |
| Coverage Rationale | {test.get("coverage_rationale", "—")} |
| Unit Tests | {test.get("has_unit_tests", "—")} |
| Integration Tests | {test.get("has_integration_tests", "—")} |

**Untested Edge Cases:**
"""
    for item in test.get("untested_edge_cases", []):
        report += f"- {item}\n"

    report += """
**Testing Risks:**
"""
    for item in test.get("testing_risks", []):
        report += f"- {item}\n"

    report += f"""
---

## 4. Migration Economics

| Metric | Value |
|--------|-------|
| Annual Maintenance | {econ.get("estimated_annual_maintenance", "—")} |
| AI Migration Cost | {econ.get("estimated_ai_migration_cost", "—")} |
| Manual Migration Cost | {econ.get("estimated_manual_migration_cost", "—")} |
| ROI Breakeven | {econ.get("roi_breakeven_months", "—")} months |

**Maintenance Breakdown:** {econ.get("maintenance_breakdown", "—")}

**Hidden Costs:**
"""
    for item in econ.get("hidden_costs", []):
        report += f"- {item}\n"

    report += """
---

## 5. Migration Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
"""
    for r in risks:
        report += f"| {r.get('risk', '—')} | {r.get('severity', '—')} | {r.get('mitigation', '—')} |\n"

    report += """
---

## 6. Confidence Scoring Rubric

| Dimension | Score | Weight | Weighted | Rationale |
|-----------|-------|--------|----------|-----------|
"""
    total_weighted = 0.0
    for key, label in [
        ("code_clarity", "Code Clarity"),
        ("business_rule_extractability", "Rule Extractability"),
        ("test_coverage_confidence", "Test Coverage Confidence"),
        ("dependency_isolation", "Dependency Isolation"),
        ("migration_complexity", "Migration Complexity"),
    ]:
        dim = rubric.get(key, {})
        s = dim.get("score", 0)
        w = dim.get("weight", 0)
        weighted = s * w
        total_weighted += weighted
        rat = dim.get("rationale", "—")
        report += f"| {label} | {s:.0%} | {w:.0%} | {weighted:.2f} | {rat} |\n"

    report += f"| **Total** | | | **{total_weighted:.2f} ({total_weighted:.0%})** | |\n"

    report += f"""
---

*Report generated by Initiative Zero Analysis Engine. Run ID: {run_id}*
"""
    return report
```

---

### 2.5 `app.py` — New Report Endpoint

Add this route after the existing `api_get_analysis` route:

```python
from flask import Response

@app.route('/api/analysis/<run_id>/report')
def api_get_analysis_report(run_id):
    """Return a downloadable Markdown analysis report."""
    from internal.analyzer import generate_report_markdown
    report = generate_report_markdown(run_id)
    if not report:
        return jsonify({"error": "No analysis found for this run"}), 404
    return Response(
        report,
        mimetype='text/markdown',
        headers={'Content-Disposition': f'attachment; filename=analysis-report-{run_id}.md'}
    )
```

---

### 2.6 `static/index.html` — Expanded Zone 2 UI

Replace the entire Zone 2 panel (`id="zp-2"`) with the following. Key changes:
- Each data card now has expandable sub-detail sections
- New "Confidence Rubric" section with per-dimension breakdown
- New "Migration Risks" section
- "Download Report" button in the action bar

```html
<!-- ═══════ ZONE 2: ANALYSIS ═══════ -->
<div class="zone-panel" id="zp-2">
  <div class="zone-title-row">
    <span class="zone-tag">Zone 02</span>
    <h2 class="zone-title">Analysis Engine</h2>
  </div>

  <div class="processing" id="a-proc">
    <div class="processing-dots"><span></span><span></span><span></span></div>
    <span class="processing-text">Explainer Agent performing deep analysis…</span>
  </div>

  <div id="a-results" style="display:none">
    <!-- ─── DATA GRID ─── -->
    <div class="data-grid" id="analysis-grid">
      <!-- App Analysis -->
      <div class="data-card">
        <div class="data-card-title"><span class="dot"></span>App Analysis</div>
        <div class="data-row"><span class="data-label">Purpose</span><span class="data-val" id="a-purpose">—</span></div>
        <div class="data-row"><span class="data-label">Stack</span><span class="data-val" id="a-stack">—</span></div>
        <div class="data-row"><span class="data-label">Dependencies</span><span class="data-val" id="a-deps">—</span></div>
        <div class="data-row"><span class="data-label">Criticality</span><span class="data-val" id="a-criticality">—</span></div>
        <div class="data-row"><span class="data-label">Domain</span><span class="data-val" id="a-domain">—</span></div>
        <div class="data-row"><span class="data-label">Data Sensitivity</span><span class="data-val" id="a-data-sensitivity">—</span></div>
        <div class="data-detail" id="a-criticality-detail"></div>
        <div class="data-detail" id="a-sensitivity-detail"></div>
      </div>

      <!-- Code Analysis -->
      <div class="data-card">
        <div class="data-card-title"><span class="dot"></span>Code Analysis</div>
        <div class="data-row"><span class="data-label">Cyclomatic</span><span class="data-val" id="a-cyclomatic">—</span></div>
        <div class="data-row"><span class="data-label">Dead code</span><span class="data-val" id="a-deadcode">—</span></div>
        <div class="data-row"><span class="data-label">Security</span><span class="data-val" id="a-security">—</span></div>
        <div class="data-row"><span class="data-label">Workarounds</span><span class="data-val" id="a-workarounds">—</span></div>
        <div class="data-detail" id="a-cyclomatic-detail"></div>
        <div class="data-detail" id="a-deadcode-detail"></div>
        <div class="data-detail-list" id="a-security-list"></div>
        <div class="data-detail-list" id="a-workaround-list"></div>
        <div class="data-detail-list" id="a-quality-list"></div>
      </div>

      <!-- Test Analysis -->
      <div class="data-card">
        <div class="data-card-title"><span class="dot"></span>Test Analysis</div>
        <div class="data-row"><span class="data-label">Coverage</span><span class="data-val" id="a-coverage">—</span></div>
        <div class="data-row"><span class="data-label">Unit tests</span><span class="data-val" id="a-unit">—</span></div>
        <div class="data-row"><span class="data-label">Integration</span><span class="data-val" id="a-integration">—</span></div>
        <div class="data-row"><span class="data-label">Edge cases</span><span class="data-val" id="a-edgecases">—</span></div>
        <div class="data-detail" id="a-coverage-rationale"></div>
        <div class="data-detail-list" id="a-edgecase-list"></div>
        <div class="data-detail-list" id="a-testing-risks-list"></div>
      </div>

      <!-- Cost Analysis -->
      <div class="data-card">
        <div class="data-card-title"><span class="dot"></span>Cost Analysis</div>
        <div class="data-row"><span class="data-label">Annual maint.</span><span class="data-val" id="a-annual">—</span></div>
        <div class="data-row"><span class="data-label">AI migration</span><span class="data-val" id="a-ai-cost">—</span></div>
        <div class="data-row"><span class="data-label">Manual migration</span><span class="data-val" id="a-manual-cost">—</span></div>
        <div class="data-row"><span class="data-label">ROI breakeven</span><span class="data-val" id="a-roi">—</span></div>
        <div class="data-detail" id="a-maintenance-breakdown"></div>
        <div class="data-detail-list" id="a-hidden-costs-list"></div>
      </div>
    </div>

    <!-- ─── MIGRATION RISKS ─── -->
    <div class="section-label" id="a-risks-label" style="display:none">Migration Risks</div>
    <div class="code-viewer" id="a-risks-table-wrap" style="display:none;margin-bottom:0">
      <table class="rules-table">
        <thead><tr><th>Risk</th><th>Severity</th><th>Mitigation</th></tr></thead>
        <tbody id="a-risks-tbody"></tbody>
      </table>
    </div>

    <!-- ─── CONFIDENCE RUBRIC ─── -->
    <div class="section-label">Confidence Scoring Rubric</div>
    <div class="rubric-grid" id="rubric-grid">
      <!-- Populated by JS -->
    </div>

    <!-- ─── CONFIDENCE BAR ─── -->
    <div class="confidence-block">
      <div class="confidence-bar-wrap">
        <div class="confidence-label">Migration Confidence (Weighted Score)</div>
        <div class="confidence-bar"><div class="confidence-fill" id="conf-fill"></div></div>
        <div class="confidence-rec" id="conf-rec"></div>
      </div>
      <div class="confidence-score" id="conf-score">—</div>
    </div>

    <div class="action-bar" style="gap:10px">
      <button class="btn" onclick="downloadAnalysisReport()">↓ Download Report</button>
      <button class="btn-advance" onclick="advanceZone(3)">Extract Rules →</button>
    </div>
  </div>
</div>
```

---

### 2.7 `static/style.css` — New Styles for Expanded Analysis

Append the following to the CSS file:

```css
/* ─── DATA DETAIL (sub-text under data rows) ─── */
.data-detail {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--tx3);
  line-height: 1.5;
  padding: 4px 0 2px;
  border-top: 1px solid var(--border-subtle);
  margin-top: 4px;
}
.data-detail:empty { display: none; }

.data-detail-list {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--tx3);
  line-height: 1.5;
  padding: 4px 0 2px;
}
.data-detail-list:empty { display: none; }
.data-detail-list .detail-item {
  padding: 2px 0 2px 10px;
  border-left: 2px solid var(--border);
  margin: 3px 0;
  color: var(--tx2);
}
.data-detail-list .detail-item.severity-high { border-left-color: var(--red); }
.data-detail-list .detail-item.severity-medium { border-left-color: var(--amber); }
.data-detail-list .detail-item.severity-low { border-left-color: var(--green); }

.data-detail-list .detail-label {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--tx4);
  margin-top: 6px;
  margin-bottom: 2px;
}

/* ─── RUBRIC GRID ─── */
.rubric-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  margin: 10px 0 16px;
}
.rubric-item {
  background: var(--bg-surface);
  padding: 12px 10px;
  text-align: center;
}
.rubric-dim {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--tx3);
  margin-bottom: 6px;
}
.rubric-score {
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 2px;
}
.rubric-score.high { color: var(--green-tx); }
.rubric-score.mid { color: var(--amber-tx); }
.rubric-score.low { color: var(--red-tx); }
.rubric-weight {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--tx4);
  margin-bottom: 4px;
}
.rubric-rationale {
  font-size: 10px;
  color: var(--tx3);
  line-height: 1.4;
  text-align: left;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--border-subtle);
}

@media (max-width: 1100px) {
  .rubric-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 700px) {
  .rubric-grid { grid-template-columns: repeat(2, 1fr); }
}
```

---

### 2.8 `static/app.js` — Expanded `runAnalysis()` and Download Handler

Replace the `runAnalysis()` function entirely. Key additions:
- Renders expanded sub-detail for each card
- Renders rubric grid
- Renders migration risks table
- Renders full recommendation rationale

```javascript
// ═══ ZONE 2: ANALYSIS ═══
async function runAnalysis() {
  updateStatus(2, 'running', '●');
  try {
    const result = await api('/api/analysis/run', 'POST', { run_id: state.runId });
    state.analysis = result;
    const m = result.metrics;
    if (!m) {
      throw new Error(result.error || 'Analysis returned no metrics');
    }

    document.getElementById('a-proc').style.display = 'none';
    document.getElementById('a-results').style.display = 'block';

    // ── App Analysis ──
    const app = m.app_analysis || {};
    document.getElementById('a-purpose').textContent = app.purpose || '—';
    document.getElementById('a-stack').textContent = app.stack || '—';
    document.getElementById('a-deps').textContent =
      (app.dependencies_upstream || 0) + ' upstream, ' + (app.dependencies_downstream || 0) + ' downstream';
    const critEl = document.getElementById('a-criticality');
    critEl.textContent = app.criticality || '—';
    if (app.criticality === 'Tier 1') critEl.classList.add('bad');
    document.getElementById('a-domain').textContent = app.domain || '—';
    const dsEl = document.getElementById('a-data-sensitivity');
    dsEl.textContent = app.data_sensitivity || '—';
    if (app.data_sensitivity === 'High') dsEl.classList.add('bad');
    document.getElementById('a-criticality-detail').textContent = app.criticality_rationale || '';
    document.getElementById('a-sensitivity-detail').textContent = app.data_sensitivity_rationale || '';

    // ── Code Analysis ──
    const code = m.code_analysis || {};
    const cyc = document.getElementById('a-cyclomatic');
    cyc.textContent = code.cyclomatic_complexity || '—';
    if ((code.cyclomatic_complexity || 0) > 20) cyc.classList.add('warn');
    const dead = document.getElementById('a-deadcode');
    dead.textContent = '~' + (code.dead_code_pct || 0).toFixed(0) + '%';
    if ((code.dead_code_pct || 0) > 10) dead.classList.add('warn');
    const sec = document.getElementById('a-security');
    sec.textContent = (code.security_issues || 0) + ' issues';
    if ((code.security_issues || 0) > 0) sec.classList.add('bad');
    document.getElementById('a-workarounds').textContent = (code.workarounds_identified || 0) + ' identified';

    document.getElementById('a-cyclomatic-detail').textContent = code.cyclomatic_detail || '';
    document.getElementById('a-deadcode-detail').textContent = code.dead_code_detail || '';
    renderDetailList('a-security-list', 'Security Concerns', code.security_detail || []);
    renderDetailList('a-workaround-list', 'Workaround Details', code.workaround_details || []);
    renderDetailList('a-quality-list', 'Code Quality', code.code_quality_notes || []);

    // ── Test Analysis ──
    const test = m.test_analysis || {};
    const cov = document.getElementById('a-coverage');
    cov.textContent = (test.estimated_coverage_pct || 0).toFixed(0) + '%';
    if ((test.estimated_coverage_pct || 0) < 50) cov.classList.add('bad');
    document.getElementById('a-unit').textContent = test.has_unit_tests || '—';
    const integ = document.getElementById('a-integration');
    integ.textContent = test.has_integration_tests || '—';
    if (test.has_integration_tests === 'None') integ.classList.add('bad');
    const edgeCases = test.untested_edge_cases || [];
    document.getElementById('a-edgecases').textContent = edgeCases.length + ' identified';
    if (edgeCases.length > 0) document.getElementById('a-edgecases').classList.add('bad');

    document.getElementById('a-coverage-rationale').textContent = test.coverage_rationale || '';
    renderDetailList('a-edgecase-list', 'Untested Edge Cases', edgeCases);
    renderDetailList('a-testing-risks-list', 'Testing Risks', test.testing_risks || []);

    // ── Cost Analysis ──
    const econ = m.migration_economics || {};
    document.getElementById('a-annual').textContent = econ.estimated_annual_maintenance || '—';
    const aiCost = document.getElementById('a-ai-cost');
    aiCost.textContent = econ.estimated_ai_migration_cost || '—';
    aiCost.classList.add('good');
    document.getElementById('a-manual-cost').textContent = econ.estimated_manual_migration_cost || '—';
    const roi = document.getElementById('a-roi');
    roi.textContent = (econ.roi_breakeven_months || '—') + ' months';
    roi.classList.add('good');
    document.getElementById('a-maintenance-breakdown').textContent = econ.maintenance_breakdown || '';
    renderDetailList('a-hidden-costs-list', 'Hidden Costs', econ.hidden_costs || []);

    // ── Migration Risks ──
    const risks = m.migration_risks || [];
    if (risks.length > 0) {
      document.getElementById('a-risks-label').style.display = '';
      document.getElementById('a-risks-table-wrap').style.display = '';
      const rtbody = document.getElementById('a-risks-tbody');
      rtbody.innerHTML = '';
      risks.forEach(r => {
        const tr = document.createElement('tr');
        const sevCls = r.severity === 'High' ? 'bad' : r.severity === 'Medium' ? 'warn' : '';
        tr.innerHTML =
          '<td>' + escHtml(r.risk) + '</td>' +
          '<td><span class="data-val ' + sevCls + '">' + escHtml(r.severity) + '</span></td>' +
          '<td>' + escHtml(r.mitigation) + '</td>';
        rtbody.appendChild(tr);
      });
    }

    // ── Confidence Rubric ──
    const rubric = m.confidence_rubric || {};
    const rubricGrid = document.getElementById('rubric-grid');
    rubricGrid.innerHTML = '';
    const dimLabels = {
      code_clarity: 'Code Clarity',
      business_rule_extractability: 'Rule Extractability',
      test_coverage_confidence: 'Test Coverage',
      dependency_isolation: 'Dep. Isolation',
      migration_complexity: 'Migration Simplicity'
    };
    for (const [key, label] of Object.entries(dimLabels)) {
      const dim = rubric[key] || {};
      const scorePct = Math.round((dim.score || 0) * 100);
      const scoreCls = scorePct >= 70 ? 'high' : scorePct >= 40 ? 'mid' : 'low';
      const item = document.createElement('div');
      item.className = 'rubric-item';
      item.innerHTML =
        '<div class="rubric-dim">' + escHtml(label) + '</div>' +
        '<div class="rubric-score ' + scoreCls + '">' + scorePct + '%</div>' +
        '<div class="rubric-weight">Weight: ' + Math.round((dim.weight || 0) * 100) + '%</div>' +
        '<div class="rubric-rationale">' + escHtml(dim.rationale || '—') + '</div>';
      rubricGrid.appendChild(item);
    }

    // ── Confidence bar ──
    const confPct = Math.round((result.confidence_score || 0) * 100);
    setTimeout(() => {
      document.getElementById('conf-fill').style.width = confPct + '%';
      let v = 0;
      const iv = setInterval(() => {
        v++;
        document.getElementById('conf-score').textContent = v + '%';
        if (v >= confPct) {
          clearInterval(iv);
          const rec = result.recommendation || 'Caution';
          const rationale = m.recommendation_rationale || '';
          document.getElementById('conf-rec').textContent =
            'Recommendation: ' + rec + (rationale ? ' — ' + rationale : '');
        }
      }, 16);
    }, 200);

    toast('Analysis complete — confidence ' + confPct + '%');
  } catch (e) {
    document.getElementById('a-proc').style.display = 'none';
    toast('Analysis error: ' + e.message);
  }
}

function renderDetailList(containerId, label, items) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';
  if (!items || items.length === 0) return;
  const labelEl = document.createElement('div');
  labelEl.className = 'detail-label';
  labelEl.textContent = label;
  container.appendChild(labelEl);
  items.forEach(item => {
    const div = document.createElement('div');
    div.className = 'detail-item';
    div.textContent = typeof item === 'string' ? item : JSON.stringify(item);
    container.appendChild(div);
  });
}

function downloadAnalysisReport() {
  if (!state.runId) {
    toast('No analysis available');
    return;
  }
  window.open('/api/analysis/' + state.runId + '/report', '_blank');
}
```

---

## 3. Zone 3 — SME Review Flow + Downloadable PRD

### 3.1 Problem
- Clicking "Approve Spec" is instant with no review step. There's no way to see the full requirements document or review individual OBS rules before approving.
- There is no downloadable tech-agnostic PRD output.

### 3.2 Solution Overview
1. **Replace the one-click approval** with a two-step flow:
   - Step 1: "Review Spec →" opens a review panel showing the full requirements document and all OBS/behavioral rules that need SME attention, with per-rule accept/flag controls.
   - Step 2: After all flagged rules are reviewed, "Approve & Cross Firewall" button becomes enabled.
2. **Add a `/api/extraction/<run_id>/prd` endpoint** that returns the requirements doc as a downloadable Markdown PRD.
3. **Add a "Download PRD" button** in the Zone 3 review panel.

### 3.3 Files to Modify
- `app.py` — new PRD endpoint
- `static/index.html` — new SME review panel
- `static/style.css` — review panel styles
- `static/app.js` — review flow logic

---

### 3.4 `app.py` — PRD Endpoint

Add after the existing extraction routes:

```python
@app.route('/api/extraction/<run_id>/prd')
def api_get_prd(run_id):
    """Return the requirements document as a downloadable Markdown PRD."""
    db = get_db()
    req_row = db.execute("SELECT content FROM requirements_docs WHERE run_id = ?", (run_id,)).fetchone()
    rules_rows = db.execute("SELECT * FROM business_rules WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
    run_row = db.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    db.close()

    if not req_row:
        return jsonify({"error": "No requirements document found"}), 404

    prd = f"""# Technology-Agnostic Product Requirements Document

**System:** {run_row["source_file"]}
**Source Language:** {run_row["source_language"]}
**Run ID:** {run_id}
**Status:** {run_row["status"]}

---

## Business Rules Summary

| ID | Rule | Type | Status |
|----|------|------|--------|
"""
    for r in rules_rows:
        prd += f"| {r['id']} | {r['rule_text']} | {r['rule_type']} | {r['status']} |\n"

    prd += f"""
---

## Full Requirements Specification

{req_row["content"]}

---

*Generated by Initiative Zero Business Rule Strainer. This document contains zero implementation details.*
*No source code, variable names, database schemas, or internal API references are included.*
"""
    return Response(
        prd,
        mimetype='text/markdown',
        headers={'Content-Disposition': f'attachment; filename=prd-{run_id}.md'}
    )
```

---

### 3.5 `static/index.html` — New SME Review Panel

Replace the `human-gate` section inside `zp-3` (the `<div class="human-gate" id="sme-gate">` block) with the expanded version below:

```html
<!-- ─── SME Review Panel ─── -->
<div class="human-gate" id="sme-gate">
  <div class="human-gate-header">⚠ Human Gate — SME Validation Required</div>
  <div class="human-gate-body">
    <div class="gate-desc">
      Review the extracted specification before it crosses the security firewall.
      All behavioral observations (OBS-*) require explicit SME confirmation.
    </div>

    <!-- Step 1: Review trigger -->
    <div id="sme-pre-review">
      <div class="gate-actions">
        <button class="btn primary" onclick="openSmeReview()">Review Spec →</button>
        <button class="btn" onclick="downloadPrd()">↓ Download PRD</button>
      </div>
    </div>

    <!-- Step 2: Review panel (hidden until triggered) -->
    <div id="sme-review-panel" style="display:none">
      <!-- Requirements doc preview -->
      <div class="section-label" style="margin-top:12px">Requirements Document Preview</div>
      <div class="code-viewer" style="margin-bottom:12px">
        <div class="code-header">
          <span class="code-filename">requirements-spec.txt</span>
          <span style="font-family:var(--mono);font-size:9px;color:var(--tx3)">TECH-AGNOSTIC</span>
        </div>
        <div class="code-body" style="max-height:300px">
          <pre id="sme-req-doc-preview">Loading…</pre>
        </div>
      </div>

      <!-- Flagged rules for review -->
      <div class="section-label" id="sme-flagged-label" style="display:none">Items Requiring SME Review</div>
      <div id="sme-flagged-rules"></div>

      <!-- Approval actions (enabled after all flags reviewed) -->
      <div class="gate-actions" style="margin-top:14px" id="sme-actions">
        <button class="btn green" id="btn-approve-spec" disabled onclick="smeSign('approve')">
          ✓ Approve & Cross Firewall — S. Chen, Staff Eng
        </button>
        <button class="btn amber" onclick="smeSign('flag')">Flag for BA Review</button>
      </div>
    </div>

    <div class="decision-record" id="sme-decision"></div>
  </div>
</div>
```

---

### 3.6 `static/style.css` — SME Review Panel Styles

Append:

```css
/* ─── SME REVIEW ITEMS ─── */
.sme-review-item {
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 14px;
  margin-bottom: 8px;
}
.sme-review-item.reviewed {
  border-color: var(--green);
  background: var(--green-dim);
}
.sme-review-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.sme-review-item-id {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--amber-tx);
}
.sme-review-item.reviewed .sme-review-item-id {
  color: var(--green-tx);
}
.sme-review-item-type {
  font-family: var(--mono);
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 3px;
  color: var(--amber-tx);
  background: var(--amber-dim);
}
.sme-review-item-text {
  font-size: 12px;
  color: var(--tx);
  line-height: 1.6;
  margin-bottom: 6px;
}
.sme-review-item-source {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--tx4);
  margin-bottom: 8px;
}
.sme-review-item-actions {
  display: flex;
  gap: 6px;
}
.sme-review-item-actions .btn {
  font-size: 10px;
  padding: 4px 10px;
}
.sme-review-item-status {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--green-tx);
  margin-top: 6px;
}
```

---

### 3.7 `static/app.js` — SME Review Flow Logic

Add these new functions (place before or after existing Zone 3 functions):

```javascript
// ═══ ZONE 3: SME REVIEW FLOW ═══

let smeReviewState = {
  flaggedRules: [],
  reviewedCount: 0
};

async function openSmeReview() {
  document.getElementById('sme-pre-review').style.display = 'none';
  document.getElementById('sme-review-panel').style.display = 'block';

  // Fetch full requirements doc
  try {
    const reqDoc = await api('/api/extraction/' + state.runId + '/requirements');
    document.getElementById('sme-req-doc-preview').textContent = reqDoc.content || 'No content available';
  } catch (e) {
    document.getElementById('sme-req-doc-preview').textContent = 'Error loading requirements: ' + e.message;
  }

  // Identify rules that need SME review (behavioral/OBS rules)
  const allRules = state.rules || [];
  const flagged = allRules.filter(r =>
    r.rule_type === 'behavioral' || (r.id && r.id.startsWith('OBS'))
  );

  smeReviewState.flaggedRules = flagged;
  smeReviewState.reviewedCount = 0;

  const container = document.getElementById('sme-flagged-rules');
  container.innerHTML = '';

  if (flagged.length === 0) {
    // No behavioral rules — can approve immediately
    document.getElementById('sme-flagged-label').style.display = 'none';
    document.getElementById('btn-approve-spec').disabled = false;
    toast('No behavioral observations found — ready for approval');
    return;
  }

  document.getElementById('sme-flagged-label').style.display = '';
  document.getElementById('sme-flagged-label').textContent =
    flagged.length + ' Item' + (flagged.length > 1 ? 's' : '') + ' Requiring SME Review';

  flagged.forEach((r, i) => {
    const div = document.createElement('div');
    div.className = 'sme-review-item';
    div.id = 'sme-item-' + i;
    div.innerHTML =
      '<div class="sme-review-item-header">' +
        '<span class="sme-review-item-id">' + escHtml(r.id) + '</span>' +
        '<span class="sme-review-item-type">Behavioral Observation</span>' +
      '</div>' +
      '<div class="sme-review-item-text">' + escHtml(r.rule_text) + '</div>' +
      '<div class="sme-review-item-source">Source: ' + escHtml(r.source_reference || 'Inferred from code patterns') + '</div>' +
      '<div class="sme-review-item-actions" id="sme-actions-' + i + '">' +
        '<button class="btn green" onclick="reviewSmeItem(' + i + ', \'confirm\')">✓ Confirm Accurate</button>' +
        '<button class="btn amber" onclick="reviewSmeItem(' + i + ', \'modify\')">Modify & Confirm</button>' +
        '<button class="btn red" onclick="reviewSmeItem(' + i + ', \'reject\')">✗ Reject</button>' +
      '</div>' +
      '<div class="sme-review-item-status" id="sme-status-' + i + '"></div>';
    container.appendChild(div);
  });
}

function reviewSmeItem(index, action) {
  const item = document.getElementById('sme-item-' + index);
  const actions = document.getElementById('sme-actions-' + index);
  const status = document.getElementById('sme-status-' + index);
  const ts = new Date().toISOString().split('.')[0] + 'Z';

  actions.style.display = 'none';
  item.classList.add('reviewed');

  if (action === 'confirm') {
    status.textContent = '✓ Confirmed by S. Chen at ' + ts;
    status.style.color = 'var(--green-tx)';
  } else if (action === 'modify') {
    status.textContent = '✎ Modified & confirmed by S. Chen at ' + ts;
    status.style.color = 'var(--amber-tx)';
  } else {
    status.textContent = '✗ Rejected by S. Chen at ' + ts;
    status.style.color = 'var(--red-tx)';
    item.style.borderColor = 'var(--red)';
    item.style.background = 'var(--red-dim)';
  }

  smeReviewState.reviewedCount++;

  // Enable approve button once all flagged items are reviewed
  if (smeReviewState.reviewedCount >= smeReviewState.flaggedRules.length) {
    document.getElementById('btn-approve-spec').disabled = false;
    toast('All observations reviewed — ready for approval');
  } else {
    const remaining = smeReviewState.flaggedRules.length - smeReviewState.reviewedCount;
    toast(remaining + ' item' + (remaining > 1 ? 's' : '') + ' remaining for review');
  }
}

function downloadPrd() {
  if (!state.runId) {
    toast('No extraction available');
    return;
  }
  window.open('/api/extraction/' + state.runId + '/prd', '_blank');
}
```

Update the existing `smeSign` function to also hide the review panel:

```javascript
async function smeSign(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('sme-decision');
  document.getElementById('sme-actions').style.display = 'none';
  document.getElementById('sme-review-panel').style.display = 'none';
  document.getElementById('sme-pre-review').style.display = 'none';

  if (action === 'approve') {
    try {
      const result = await api('/api/extraction/' + state.runId + '/approve', 'POST', {
        operator: 'S. Chen',
        rationale: 'Requirements document validated after SME review'
      });
      state.requirementsDocId = result.requirements_doc_id;
      dr.className = 'decision-record accepted show';
      dr.innerHTML = '<div class="dr-header">✓ SPEC APPROVED</div>' +
        '<div class="dr-body">Requirements document validated after SME review. ' +
        smeReviewState.flaggedRules.length + ' behavioral observation(s) reviewed. ' +
        'Cleared to cross security firewall.</div>' +
        '<div class="dr-ts">' + escHtml(result.operator) + ' (Staff Eng) · ' + escHtml(result.timestamp) + '</div>';
      document.getElementById('btn-to-gen').disabled = false;
      toast('Spec approved — firewall crossing authorized');
    } catch (e) {
      document.getElementById('sme-actions').style.display = '';
      document.getElementById('sme-review-panel').style.display = 'block';
      toast('Approval error: ' + e.message);
    }
  } else {
    dr.className = 'decision-record preserved show';
    dr.innerHTML = '<div class="dr-header">⚠ FLAGGED FOR BA REVIEW</div>' +
      '<div class="dr-body">Behavioral observations require business analyst confirmation before proceeding.</div>' +
      '<div class="dr-ts">S. Chen (Staff Eng) · ' + ts + '</div>';
    toast('Spec flagged — awaiting BA review');
  }
}
```

---

## 4. Cross-Cutting — Remove Duplicated JS

### Problem
`index.html` contains the full JS both inline (in a `<script>` block at the bottom) AND links to `app.js` via `<script src>`. This means every change needs to be made in two places.

### Fix
**Remove the entire inline `<script>...</script>` block from the bottom of `index.html`.** Ensure the `<script src="/static/app.js"></script>` tag is present just before `</body>`. The `app.js` file is the single source of truth.

In `index.html`, the end of the file should look like:

```html
  </div><!-- /content -->
</div><!-- /main -->

<div class="toast" id="toast"></div>

<script src="/static/app.js"></script>
</body>
</html>
```

**Delete everything between `<script>` and `</script>` in the current inline block (approximately lines starting after `<div class="toast"...>` to end of file).** Replace with the single `<script src>` tag above.

---

## 5. Implementation Order

Execute these changes in this order:

1. **Fix #4 first** (remove duplicate JS) — prevents merge conflicts with all other JS changes.
2. **Fix #1** (filename overflow CSS) — quick CSS-only fix.
3. **Fix #2** (expanded analysis) — `analyzer.py` prompt → `app.py` route → CSS → JS → HTML.
4. **Fix #3** (SME review flow) — `app.py` route → CSS → JS → HTML.

---

## 6. Testing Checklist

After implementation, verify:

- [ ] Zone 1: Select `portfolio_rebalance.cbl` — filename should truncate with ellipsis, full path shows on hover
- [ ] Zone 2: Run analysis — all 4 cards show expanded detail with sub-items
- [ ] Zone 2: Rubric grid renders 5 dimensions with scores, weights, and rationale
- [ ] Zone 2: Migration risks table appears if risks are returned
- [ ] Zone 2: "Download Report" opens a Markdown file in a new tab
- [ ] Zone 2: Confidence bar and recommendation display full rationale (2-3 sentences)
- [ ] Zone 3: "Review Spec →" opens the review panel with requirements doc preview
- [ ] Zone 3: Behavioral/OBS rules appear as individual review items with confirm/modify/reject buttons
- [ ] Zone 3: Approve button only enables after all OBS items are reviewed
- [ ] Zone 3: "Download PRD" opens a Markdown file with all rules and requirements
- [ ] Zone 3: After approval, "Generate Code →" enables and pipeline continues normally
- [ ] Full pipeline: Run end-to-end from Zone 1 → Zone 6 with `portfolio_rebalance.cbl` — no regressions
- [ ] No duplicate JS: Confirm the inline `<script>` block has been removed from `index.html`
