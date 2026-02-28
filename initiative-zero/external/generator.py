# ⚠ SECURITY BOUNDARY: This module is in the external zone.
# It MUST NOT import from internal/. It receives ONLY plain-text
# requirements via the database. No source code, no schemas, no IP.

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

GENERATION_SYSTEM_PROMPT = """You are a code generation agent for a financial services modernization pipeline. You generate production-ready Python applications from plain-text business requirements.

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
  - For trade/rebalance systems: "action" (e.g. "SELL", "BUY", "HOLD"), and optionally "trade_amount", "reason", "error_code", "tlh_flag"
  - For claims/approval systems: "status" (e.g. "APPROVED", "DENIED"), and optionally "payout", "error_code", "reason"
- Convert all Decimal results to string in the return dict
- On any error, return {"error": "description", "error_code": <int>} — never raise

OUTPUT FORMAT CONTRACT:
The process() method must return a dict with these exact keys and value types:
- For claims/approval systems:
  "status": str — uppercase, e.g. "APPROVED" or "DENIED"
  "payout": str — Decimal as string to 2dp, e.g. "4500.00" (present when APPROVED)
  "error_code": int — numeric code (present when DENIED)
- For trade/rebalance systems:
  "action": str — uppercase, e.g. "SELL", "BUY", "HOLD"
  "trade_amount": str — Decimal as string to 2dp, e.g. "7000.00" (present when SELL/BUY)
  "reason": str — uppercase explanation (present when HOLD)
  "tlh_flag": bool — True/False (present when tax-loss harvest applies)
  "error_code": int — numeric code (present on validation failures)
- On any error: {"error": str, "error_code": int}
All financial values MUST be Decimal converted to str with exactly 2 decimal places.
Boolean fields MUST be Python bool (True/False), not strings.
Do NOT invent additional output keys beyond those listed above.

SUPPLEMENTAL CONTEXT:
The requirements document may include a "SUPPLEMENTAL CONTEXT FROM SYSTEM ANALYSIS" section. Use this to:
- Understand data sensitivity requirements and add appropriate validation
- Address the specific untested edge cases listed (add defensive handling)
- Implement mitigations for the listed migration risks where possible in code
- Follow the security requirements listed"""

GENERATION_USER_PROMPT = """Generate a complete, production-ready Python module that implements ALL of the following business requirements.

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
9. Return values must use the EXACT key names from the OUTPUT FORMAT CONTRACT (e.g. "payout" not "amount", "trade_amount" not "trade_value")
10. Boolean fields (tlh_flag, wash_sale_flag) must be Python bool True/False, never strings "true"/"false"

Return ONLY the Python code. No markdown fences, no explanations."""


def run_generation(run_id: str, requirements_doc_id: str, target_language: str = "python") -> dict:
    """Generate code from requirements document ONLY. No source code access."""

    db = get_db()

    # Fetch requirements doc — this is the ONLY data this module can access
    row = db.execute(
        "SELECT content, approved_by FROM requirements_docs WHERE id = ? AND run_id = ?",
        (requirements_doc_id, run_id)
    ).fetchone()

    if not row:
        db.close()
        return {"error": f"Requirements doc {requirements_doc_id} not found for run {run_id}"}

    if not row["approved_by"]:
        db.close()
        return {"error": "Requirements document has not been approved. Cannot generate."}

    requirements_text = row["content"]

    # Build the prompt — store it for auditability
    full_prompt = GENERATION_USER_PROMPT.format(requirements_text=requirements_text)

    # TODO(prod): Implement retry with exponential backoff for transient API failures
    # TODO(prod): Cache generation results by content_hash to avoid redundant API calls
    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=GENERATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": full_prompt}]
        )
    except anthropic.AuthenticationError as e:
        db.close()
        return {"error": f"API key authentication failed: {e}. Check that ANTHROPIC_API_KEY is set to a valid key."}
    except Exception as e:
        db.close()
        return {"error": f"Claude API call failed: {e}"}

    generated_code = strip_json_fences(response.content[0].text)

    # Store in DB — including the exact prompt for audit trail
    gen_id = new_id()
    db.execute(
        """INSERT INTO generated_code
           (id, run_id, requirements_doc_id, language, code, generation_prompt)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (gen_id, run_id, requirements_doc_id, target_language, generated_code, full_prompt)
    )

    db.execute("UPDATE pipeline_runs SET status = 'generated' WHERE id = ?", (run_id,))
    db.commit()
    db.close()

    return {
        "generation_id": gen_id,
        "code": generated_code,
        "language": target_language,
        "generation_prompt": full_prompt  # Exposed to UI to PROVE no source code was included
    }
