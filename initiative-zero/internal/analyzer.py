import os
import json
import anthropic
from database import get_db, new_id, strip_json_fences


def _get_client():
    """Create Anthropic client on demand so it always reads the current API key."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Please add your API key to Secrets (lock icon in Replit) or "
            "export ANTHROPIC_API_KEY in your environment."
        )
    return anthropic.Anthropic(api_key=api_key)

ANALYSIS_SYSTEM_PROMPT = """You are a legacy code analysis agent for a financial services
code modernization pipeline. You analyze source code and return structured assessments.
Always return valid JSON. Estimate where exact data isn't available but flag estimates clearly.

CONFIDENCE SCORING CALIBRATION:
Score each rubric dimension on a 0.0-1.0 scale using these anchors:
- 0.80-1.00: Code is well-documented, clearly structured, with explicit business rule annotations and named constants
- 0.65-0.79: Code is reasonably clear with some documentation; business rules are identifiable
- 0.50-0.64: Code has significant ambiguity, sparse documentation, or tangled logic
- Below 0.50: Code is obfuscated, undocumented, or severely degraded
Well-maintained legacy code with clear paragraph headers, business rule comments (e.g. BR:),
and explicit threshold constants should score in the 0.70-0.85 range. Do not deflate scores
for well-structured code — rate what you actually observe."""

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
      "rationale": "how readable and well-structured the code is — score 0.70+ for clear section headers, meaningful paragraph names, and inline BR comments"
    }},
    "business_rule_extractability": {{
      "score": <float 0.0-1.0>,
      "weight": 0.25,
      "rationale": "how clearly business rules can be identified — score 0.75+ if rules are annotated with comments or clearly separated into named paragraphs with explicit thresholds"
    }},
    "test_coverage_confidence": {{
      "score": <float 0.0-1.0>,
      "weight": 0.20,
      "rationale": "confidence in verifying migration correctness — score 0.65+ if behavior is deterministic with clearly defined inputs, outputs, and thresholds"
    }},
    "dependency_isolation": {{
      "score": <float 0.0-1.0>,
      "weight": 0.15,
      "rationale": "how isolated this module is — score 0.65+ if dependencies are documented via COPY statements or header comments and interface boundaries are clear"
    }},
    "migration_complexity": {{
      "score": <float 0.0-1.0>,
      "weight": 0.20,
      "rationale": "inverse complexity — higher means simpler migration — score 0.65+ if logic is procedural with clear control flow, explicit thresholds, and no recursive or deeply nested structures"
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


RUBRIC_DIMENSIONS = [
    ("code_clarity", 0.20),
    ("business_rule_extractability", 0.25),
    ("test_coverage_confidence", 0.20),
    ("dependency_isolation", 0.15),
    ("migration_complexity", 0.20),
]


def _validate_and_recompute_confidence(metrics: dict) -> tuple:
    """Server-side validation: recompute confidence from rubric and enforce thresholds.

    Returns (confidence_score, recommendation, metrics) with corrected values.
    The rubric is the source of truth — we never trust the model's pre-computed score.
    """
    rubric = metrics.get("confidence_rubric", {})

    # Ensure all dimensions exist with valid scores and correct weights
    recomputed_score = 0.0
    for dim_key, expected_weight in RUBRIC_DIMENSIONS:
        dim = rubric.get(dim_key, {})
        score = dim.get("score", 0.0)

        # Clamp score to [0.0, 1.0]
        if not isinstance(score, (int, float)):
            score = 0.0
        score = max(0.0, min(1.0, float(score)))

        # Force correct weight (don't trust model weights)
        dim["score"] = score
        dim["weight"] = expected_weight
        rubric[dim_key] = dim

        recomputed_score += score * expected_weight

    recomputed_score = round(recomputed_score, 4)

    # Enforce recommendation thresholds deterministically
    if recomputed_score >= 0.80:
        recommendation = "Proceed"
    elif recomputed_score >= 0.50:
        recommendation = "Caution"
    else:
        recommendation = "Block"

    # Write corrected values back into metrics
    metrics["confidence_rubric"] = rubric
    metrics["confidence_score"] = recomputed_score
    metrics["recommendation"] = recommendation

    return recomputed_score, recommendation, metrics


def run_analysis(run_id: str, source_code: str, language: str = "COBOL") -> dict:
    """Send source code to Claude for analysis. Store results in DB. Return analysis dict."""

    prompt = ANALYSIS_USER_PROMPT.format(language=language, source_code=source_code)

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
    except anthropic.AuthenticationError as e:
        return {"error": f"API key authentication failed: {e}. Check that ANTHROPIC_API_KEY is set to a valid key."}
    except Exception as e:
        return {"error": f"Claude API call failed: {e}"}

    raw_text = response.content[0].text

    try:
        cleaned = strip_json_fences(raw_text)
        metrics = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as e:
        return {"error": f"Failed to parse analysis response: {e}", "raw_response": raw_text}

    # Server-side validation: recompute confidence from rubric, enforce thresholds
    confidence, recommendation, metrics = _validate_and_recompute_confidence(metrics)

    # Store in DB
    db = get_db()
    analysis_id = new_id()
    db.execute(
        """INSERT INTO analyses (id, run_id, raw_response, metrics, confidence_score, recommendation)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (analysis_id, run_id, raw_text, json.dumps(metrics), confidence, recommendation)
    )
    db.execute("UPDATE pipeline_runs SET status = 'analyzed' WHERE id = ?", (run_id,))
    db.commit()
    db.close()

    return {"analysis_id": analysis_id, "metrics": metrics, "confidence_score": confidence, "recommendation": recommendation}


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

    report += """
**Workaround Details:**
"""
    for item in code.get("workaround_details", []):
        report += f"- {item}\n"

    report += """
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

## 4. Migration Economics & ROI

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

    # ROI Summary (Playbook alignment: speed, risk reduction, knowledge preservation, financial impact)
    import re
    annual_str = econ.get("estimated_annual_maintenance", "")
    ai_cost_str = econ.get("estimated_ai_migration_cost", "")
    annual_match = re.search(r'[\d.]+', annual_str.replace(',', ''))
    ai_cost_match = re.search(r'[\d.]+', ai_cost_str.replace(',', ''))
    if annual_match and ai_cost_match:
        annual_val = float(annual_match.group())
        ai_cost_val = float(ai_cost_match.group())
        # Normalize: if annual contains "M" it's millions, if "K" it's thousands
        if 'M' in annual_str:
            annual_val *= 1_000_000
        elif 'K' in annual_str:
            annual_val *= 1_000
        if 'M' in ai_cost_str:
            ai_cost_val *= 1_000_000
        elif 'K' in ai_cost_str:
            ai_cost_val *= 1_000
        if ai_cost_val > 0:
            roi_pct = ((annual_val - ai_cost_val) / ai_cost_val) * 100
            report += f"""
### ROI Summary

| ROI Dimension | Impact |
|--------------|--------|
| **Financial** | {roi_pct:+.0f}% first-year ROI (annual savings vs. migration cost) |
| **Speed** | AI-assisted migration reduces timeline vs. manual rewrite |
| **Risk Reduction** | Automated drift detection catches regressions before production |
| **Knowledge Preservation** | Business rules extracted and documented, reducing key-person dependency |

*ROI = (Annual Maintenance Saved − Migration Cost) / Migration Cost*
"""

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
