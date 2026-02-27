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

GENERATION_SYSTEM_PROMPT = """You are a code generation agent. You generate production-ready
Python applications from plain-text business requirements.

You have NO access to any source code, database schemas, or implementation details.
You work ONLY from the requirements document provided.

Code quality standards:
- Use dataclasses and type hints throughout
- Use Decimal with explicit rounding for all currency/financial values
- Each method must have a docstring referencing the business rule ID it implements
- Include comprehensive input validation
- Include error handling with meaningful error codes
- Follow clean architecture principles"""

GENERATION_USER_PROMPT = """Generate a complete, production-ready Python module that
implements ALL of the following business requirements.

REQUIREMENTS DOCUMENT:
{requirements_text}

Return ONLY the Python code. No markdown fences, no explanations. Just the complete
Python module that can be saved as a .py file and executed."""


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

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
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
