import json
import hashlib
import anthropic
from database import get_db, new_id, now_iso

client = anthropic.Anthropic()

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


def run_extraction(run_id: str, source_code: str, language: str = "COBOL") -> dict:
    """Extract business rules from source code. Store rules and requirements doc in DB."""

    prompt = EXTRACTION_USER_PROMPT.format(language=language, source_code=source_code)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw_text = response.content[0].text
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

    result = json.loads(cleaned)
    rules = result.get("rules", [])
    req_doc_text = result.get("requirements_document", "")

    db = get_db()

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
