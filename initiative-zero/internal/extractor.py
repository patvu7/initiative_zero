import os
import json
import hashlib
import anthropic
from database import get_db, new_id, now_iso, strip_json_fences


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

EXTRACTION_SYSTEM_PROMPT = """You are a business rule extraction agent for a financial services
code modernization pipeline. You extract business rules from legacy source code and produce
technology-agnostic specifications.

CRITICAL RULES:
- Output must contain ZERO implementation details (no variable names, no language syntax,
  no database references, no internal API names)
- A developer who has never seen the source language must understand every rule
- Distinguish between explicit rules (directly in code) and behavioral observations
  (inferred from patterns, comments, or anomalies)
- The requirements document must be complete enough to build a new system from scratch"""

EXTRACTION_USER_PROMPT = """Extract all business rules from this {language} source code.

Return a JSON object with exactly this structure. No markdown fences — just JSON.

{{
  "rules": [
    {{
      "id": "BR-001",
      "rule_text": "Plain English description — no code, no variable names",
      "source_reference": "Which section/paragraph this came from",
      "rule_type": "explicit" or "behavioral",
      "confidence": "high" or "medium" or "low"
    }}
  ],
  "requirements_document": "A complete plain-text requirements document. This is what will be sent to a code generation system that has NO access to the source code. It must contain:\n- Every business rule as a numbered requirement\n- Data types and constraints (currency precision, rounding rules)\n- Error handling behavior\n- Audit/logging requirements\n- Any behavioral observations from comments or patterns\n\nFormat as clean plain text with rule IDs (BR-001, BR-002, etc.)."
}}

For behavioral observations (patterns you infer from comments, dead code, or anomalies),
use IDs starting with OBS- instead of BR-.

SOURCE CODE:
```{language}
{source_code}
```"""


def build_enrichment_section(metrics: dict) -> str:
    """Build a technology-agnostic plain-text appendix from analysis metrics.

    Returns structured text to append to the requirements document.
    Omits any section that has no data.
    """
    sections = []

    # --- Header ---
    sections.append(
        "---\n"
        "SUPPLEMENTAL CONTEXT FROM SYSTEM ANALYSIS\n"
        "(This section provides additional context for code generation. "
        "All information is technology-agnostic.)\n"
        "---"
    )

    # --- SYSTEM PROFILE ---
    app = metrics.get("app_analysis")
    if app and isinstance(app, dict):
        lines = ["SYSTEM PROFILE"]
        if app.get("purpose"):
            lines.append(f"- Purpose: {app['purpose']}")
        if app.get("domain"):
            lines.append(f"- Domain: {app['domain']}")
        if app.get("criticality"):
            crit = app["criticality"]
            rationale = app.get("criticality_rationale", "")
            lines.append(f"- Criticality: {crit} — {rationale}" if rationale else f"- Criticality: {crit}")
        if app.get("data_sensitivity"):
            ds = app["data_sensitivity"]
            ds_rationale = app.get("data_sensitivity_rationale", "")
            lines.append(f"- Data Sensitivity: {ds} — {ds_rationale}" if ds_rationale else f"- Data Sensitivity: {ds}")
        if len(lines) > 1:
            sections.append("\n".join(lines))

    # --- DATA HANDLING REQUIREMENTS ---
    if app and isinstance(app, dict):
        ds = app.get("data_sensitivity", "")
        domain = app.get("domain", "")
        dh_lines = ["DATA HANDLING REQUIREMENTS"]
        if ds:
            dh_lines.append(f"- This system processes {ds}-sensitivity data")
        if ds and ds.lower() == "high":
            dh_lines.append(
                "- All data handling must include audit trails, "
                "access logging, and encryption-at-rest considerations"
            )
        domain_lower = domain.lower() if domain else ""
        if any(kw in domain_lower for kw in ("finance", "portfolio", "wealth")):
            dh_lines.append(
                "- Financial calculations require Decimal precision "
                "with explicit rounding modes"
            )
        if len(dh_lines) > 1:
            sections.append("\n".join(dh_lines))

    # --- KNOWN TESTING GAPS ---
    test = metrics.get("test_analysis")
    if test and isinstance(test, dict):
        edge_cases = test.get("untested_edge_cases", [])
        if edge_cases:
            lines = [
                "KNOWN TESTING GAPS",
                "The following edge cases were identified as untested in the legacy system.",
                "The generated implementation SHOULD include defensive handling for these:",
            ]
            for item in edge_cases:
                lines.append(f"- {item}")
            sections.append("\n".join(lines))

    # --- TESTING RISKS ---
    if test and isinstance(test, dict):
        risks = test.get("testing_risks", [])
        if risks:
            lines = ["TESTING RISKS"]
            for item in risks:
                lines.append(f"- {item}")
            sections.append("\n".join(lines))

    # --- MIGRATION RISKS ---
    mig_risks = metrics.get("migration_risks")
    if mig_risks and isinstance(mig_risks, list):
        non_empty = [r for r in mig_risks if isinstance(r, dict) and r.get("risk")]
        if non_empty:
            lines = ["MIGRATION RISKS"]
            for risk in non_empty:
                severity = risk.get("severity", "Unknown")
                desc = risk.get("risk", "")
                mitigation = risk.get("mitigation", "")
                lines.append(f"- [{severity}] {desc}")
                if mitigation:
                    lines.append(f"  Mitigation: {mitigation}")
            sections.append("\n".join(lines))

    # --- SECURITY REQUIREMENTS ---
    code = metrics.get("code_analysis")
    if code and isinstance(code, dict):
        sec_items = code.get("security_detail", [])
        if sec_items:
            lines = ["SECURITY REQUIREMENTS"]
            for item in sec_items:
                lines.append(f"- {item}")
            sections.append("\n".join(lines))

    # --- CODE QUALITY GUIDANCE ---
    if code and isinstance(code, dict):
        quality_notes = code.get("code_quality_notes", [])
        good_notes = [n for n in quality_notes if "Good" in n]
        if good_notes:
            lines = ["CODE QUALITY GUIDANCE"]
            for item in good_notes:
                lines.append(f"- Preserve: {item}")
            sections.append("\n".join(lines))

    # Only return enrichment if we have content beyond the header
    if len(sections) <= 1:
        return ""

    return "\n\n".join(sections)


def run_extraction(run_id: str, source_code: str, language: str = "COBOL") -> dict:
    """Extract business rules from source code. Store rules and requirements doc in DB."""

    prompt = EXTRACTION_USER_PROMPT.format(language=language, source_code=source_code)

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
    except anthropic.AuthenticationError as e:
        return {"error": f"API key authentication failed: {e}. Check that ANTHROPIC_API_KEY is set to a valid key."}
    except Exception as e:
        return {"error": f"Claude API call failed: {e}"}

    raw_text = response.content[0].text

    try:
        cleaned = strip_json_fences(raw_text)
        result = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as e:
        return {"error": f"Failed to parse extraction response: {e}", "raw_response": raw_text}
    rules = result.get("rules", [])
    req_doc_text = result.get("requirements_document", "")

    # Enrich requirements document with Zone 2 analysis data (if available)
    db = get_db()
    analysis_row = db.execute(
        "SELECT metrics FROM analyses WHERE run_id = ?", (run_id,)
    ).fetchone()

    if analysis_row and analysis_row["metrics"]:
        try:
            metrics = json.loads(analysis_row["metrics"])
            enrichment = build_enrichment_section(metrics)
            if enrichment:
                req_doc_text = req_doc_text + "\n\n" + enrichment
        except (json.JSONDecodeError, ValueError):
            pass  # Skip enrichment silently on parse error

    # Store each rule
    for rule in rules:
        db.execute(
            """INSERT OR REPLACE INTO business_rules
               (id, run_id, rule_text, source_reference, rule_type, status)
               VALUES (?, ?, ?, ?, ?, 'extracted')""",
            (rule["id"], run_id, rule["rule_text"],
             rule.get("source_reference", ""), rule.get("rule_type", "explicit"))
        )

    # Store requirements document
    req_id = new_id()
    content_hash = hashlib.sha256(req_doc_text.encode()).hexdigest()[:16]
    db.execute(
        """INSERT INTO requirements_docs (id, run_id, content, content_hash)
           VALUES (?, ?, ?, ?)""",
        (req_id, run_id, req_doc_text, content_hash)
    )

    db.execute("UPDATE pipeline_runs SET status = 'extracted' WHERE id = ?", (run_id,))
    db.commit()
    db.close()

    return {
        "rules": rules,
        "requirements_doc_id": req_id,
        "requirements_preview": req_doc_text[:500] + "..." if len(req_doc_text) > 500 else req_doc_text,
        "content_hash": content_hash
    }


def approve_spec(run_id: str, operator: str, rationale: str = "") -> dict:
    """Human gate: approve the requirements spec for firewall crossing."""
    db = get_db()
    ts = now_iso()

    # Update requirements doc
    db.execute(
        "UPDATE requirements_docs SET approved_by = ?, approved_at = ? WHERE run_id = ?",
        (operator, ts, run_id)
    )

    # Update all rules to validated
    db.execute(
        "UPDATE business_rules SET status = 'validated', validated_by = ?, validated_at = ? WHERE run_id = ?",
        (operator, ts, run_id)
    )

    # Record decision
    decision_id = new_id()
    db.execute(
        """INSERT INTO decisions (id, run_id, zone, gate_name, decision, rationale, operator)
           VALUES (?, ?, 3, 'sme_validation', 'approve', ?, ?)""",
        (decision_id, run_id, rationale, operator)
    )

    db.execute("UPDATE pipeline_runs SET status = 'approved' WHERE id = ?", (run_id,))
    db.commit()

    # Return the requirements doc ID for the next zone
    row = db.execute("SELECT id, content_hash FROM requirements_docs WHERE run_id = ?", (run_id,)).fetchone()
    db.close()

    return {
        "decision": "approved",
        "operator": operator,
        "timestamp": ts,
        "requirements_doc_id": row["id"],
        "content_hash": row["content_hash"]
    }
