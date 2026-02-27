import os
import json
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

ANALYSIS_SYSTEM_PROMPT = """You are a legacy code analysis agent for a financial services
code modernization pipeline. You analyze source code and return structured assessments.
Always return valid JSON. Be conservative with confidence scores. Estimate where exact
data isn't available but flag estimates clearly."""

ANALYSIS_USER_PROMPT = """Analyze this {language} source code and return a JSON object
with exactly this structure. No markdown fences, no explanation — just the JSON object.

{{
  "app_analysis": {{
    "purpose": "one-line description of what this system does",
    "stack": "e.g. COBOL → DB2 → JCL",
    "dependencies_upstream": <integer>,
    "dependencies_downstream": <integer>,
    "criticality": "Tier 1" or "Tier 2" or "Tier 3"
  }},
  "code_analysis": {{
    "cyclomatic_complexity": <integer>,
    "dead_code_pct": <float, 0-100>,
    "security_issues": <integer>,
    "workarounds_identified": <integer>,
    "workaround_details": ["list of identified workarounds"]
  }},
  "test_analysis": {{
    "estimated_coverage_pct": <float, 0-100>,
    "has_unit_tests": "Exists (sparse)" or "Comprehensive" or "None",
    "has_integration_tests": "Yes" or "None",
    "untested_edge_cases": ["list of identified gaps"]
  }},
  "migration_economics": {{
    "estimated_annual_maintenance": "$X.XM/yr",
    "estimated_ai_migration_cost": "$XXXK",
    "estimated_manual_migration_cost": "$X.XM / XX mo",
    "roi_breakeven_months": <integer>
  }},
  "confidence_score": <float between 0.0 and 1.0>,
  "recommendation": "Proceed" or "Caution" or "Block",
  "recommendation_rationale": "one sentence explaining why"
}}

SOURCE CODE:
```{language}
{source_code}
```"""


def run_analysis(run_id: str, source_code: str, language: str = "COBOL") -> dict:
    """Send source code to Claude for analysis. Store results in DB. Return analysis dict."""

    prompt = ANALYSIS_USER_PROMPT.format(language=language, source_code=source_code)

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
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

    confidence = metrics.get("confidence_score", 0.0)
    recommendation = metrics.get("recommendation", "Caution")

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
