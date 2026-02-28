# ⚠ SECURITY BOUNDARY: This module is in the external zone.
# It MUST NOT import from internal/. It receives ONLY plain-text
# requirements via the database. No source code, no schemas, no IP.

import os
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

BOUNDARY CONDITION PRECISION:
- When requirements say 'strictly greater than' or 'exceeds', use > (NOT >=)
- When requirements say 'greater than or equal to' or 'at least', use >= (NOT >)
- When requirements say 'less than' or 'below', use < (NOT <=)
- Boundary conditions are the #1 source of migration defects — match the requirement EXACTLY
- When a later processing step can override an earlier decision (e.g., wash sale blocking
  a trade that drift analysis triggered), implement the override correctly in sequence

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
- Follow the security requirements listed
- Follow the exact processing order described in the PROCESSING ORDER section of the requirements"""

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

CRITICAL — COMMON MISTAKES TO AVOID:
- Do NOT return negative payout values — if (claim_amount - deductible) is negative, return payout "0.00"
- Do NOT use Decimal's default ROUND_HALF_EVEN — always use ROUND_HALF_UP for financial calculations
- Do NOT forget to convert all Decimal results to strings in the return dict
- Do NOT use key names like "payout_amount", "claim_status", "trade_value" — use EXACTLY: "payout", "status", "trade_amount"
- Do NOT include markdown fences in the output — return raw Python code only
- When claim_amount exceeds coverage_limit, return DENIED with error_code 1001 — do NOT cap the amount
- Empty/blank policy_number must return DENIED with error_code 1002
- For HOLD actions, always include a "reason" field explaining why
- Pay EXTREME attention to comparison operators: > vs >= matters. 'strictly greater than' means >, NOT >=. This is the most common source of migration defects at boundary values.
- Follow the EXACT processing order from requirements — do not reorder validation or calculation steps
- When one rule can override a prior decision (e.g., wash sale check overriding a triggered rebalance to HOLD), implement the override exactly as described in the processing order

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
            max_tokens=12000,
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

    # Post-generation validation: check for required structural elements
    validation_issues = _validate_generated_code(generated_code)
    if validation_issues:
        # Attempt one retry with explicit fix instructions
        fix_prompt = (
            "The previously generated code has structural issues:\n"
            + "\n".join(f"- {issue}" for issue in validation_issues)
            + "\n\nPlease regenerate the COMPLETE module fixing all issues above.\n"
            + full_prompt
        )
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=12000,
                system=GENERATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": fix_prompt}]
            )
            generated_code = strip_json_fences(response.content[0].text)
        except Exception:
            pass  # Use original code if retry fails

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


def _validate_generated_code(code: str) -> list:
    """Validate structural requirements of generated code. Returns list of issues."""
    import re
    issues = []

    # Check for class with process method
    if not re.search(r'class\s+\w+', code):
        issues.append("No class definition found — must have a top-level class")

    if not re.search(r'def\s+process\s*\(\s*self', code):
        issues.append("No process(self, ...) method found — must have process(self, input_data: dict) -> dict")

    # Check for Decimal import
    if 'from decimal import' not in code and 'import decimal' not in code:
        issues.append("No Decimal import — all financial calculations must use Decimal")

    # Check for common key name mistakes
    bad_keys = []
    if '"payout_amount"' in code or "'payout_amount'" in code:
        bad_keys.append('payout_amount (should be "payout")')
    if '"claim_status"' in code or "'claim_status'" in code:
        bad_keys.append('claim_status (should be "status")')
    if '"trade_value"' in code or "'trade_value'" in code:
        bad_keys.append('trade_value (should be "trade_amount")')
    if bad_keys:
        issues.append(f"Non-canonical output keys found: {', '.join(bad_keys)}")

    return issues
