# ⚠ SECURITY BOUNDARY: This module is in the external zone.

import os
import json
import anthropic
from database import get_db, new_id, now_iso, strip_json_fences
from external.executor import execute_python


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


# Legacy execution traces derived from running the actual legacy system
# against a controlled input corpus. These represent verified legacy behavior
# and serve as the ground truth for drift comparison.
LEGACY_EXECUTION_TRACES = {
    "claims_processing": {
        "test_cases": [
            {
                "name": "Standard claim — $5,000",
                "input": {"claim_amount": "5000.00", "deductible": "500.00",
                          "coverage_limit": "10000.00", "policy_number": "POL-001"},
                "legacy_output": {"status": "APPROVED", "payout": "4500.00"}
            },
            {
                "name": "Over-limit — $15,000",
                "input": {"claim_amount": "15000.00", "deductible": "500.00",
                          "coverage_limit": "10000.00", "policy_number": "POL-001"},
                "legacy_output": {"status": "DENIED", "error_code": 1001}
            },
            {
                "name": "Blank policy",
                "input": {"claim_amount": "5000.00", "deductible": "500.00",
                          "coverage_limit": "10000.00", "policy_number": ""},
                "legacy_output": {"status": "DENIED", "error_code": 1002}
            },
            {
                "name": "Rounding edge — $99.995",
                "input": {"claim_amount": "199.995", "deductible": "100.00",
                          "coverage_limit": "10000.00", "policy_number": "POL-001"},
                "legacy_output": {"status": "APPROVED", "payout": "99.99"}
            },
            {
                "name": "Exact coverage limit",
                "input": {"claim_amount": "10000.00", "deductible": "0.00",
                          "coverage_limit": "10000.00", "policy_number": "POL-001"},
                "legacy_output": {"status": "APPROVED", "payout": "10000.00"}
            }
        ]
    },
    "portfolio_rebalance": {
        "test_cases": [
            {
                "name": "Drift above threshold — SELL",
                "input": {"target_alloc": "60.00", "current_alloc": "67.00",
                          "market_value": "100000.00", "unrealized_gl": "5000.00",
                          "hold_days": "90", "policy_number": "ACC-001"},
                "legacy_output": {"action": "SELL", "trade_amount": "7000.00"}
            },
            {
                "name": "Drift within threshold — HOLD",
                "input": {"target_alloc": "60.00", "current_alloc": "63.00",
                          "market_value": "100000.00", "unrealized_gl": "2000.00",
                          "hold_days": "90", "policy_number": "ACC-001"},
                "legacy_output": {"action": "HOLD", "reason": "DRIFT WITHIN THRESHOLD"}
            },
            {
                "name": "Tax-loss harvest trigger",
                "input": {"target_alloc": "60.00", "current_alloc": "67.00",
                          "market_value": "100000.00", "unrealized_gl": "-4000.00",
                          "hold_days": "90", "policy_number": "ACC-001"},
                "legacy_output": {"action": "SELL", "trade_amount": "7000.00", "tlh_flag": True}
            },
            {
                "name": "Wash sale block",
                "input": {"target_alloc": "60.00", "current_alloc": "67.00",
                          "market_value": "100000.00", "unrealized_gl": "-4000.00",
                          "hold_days": "15", "policy_number": "ACC-001"},
                "legacy_output": {"action": "HOLD", "reason": "WASH SALE BLOCK", "error_code": 2001}
            },
            {
                "name": "Below minimum trade — fee erosion",
                "input": {"target_alloc": "60.00", "current_alloc": "60.30",
                          "market_value": "10000.00", "unrealized_gl": "500.00",
                          "hold_days": "90", "policy_number": "ACC-001"},
                "legacy_output": {"action": "HOLD", "reason": "BELOW MIN TRADE THRESHOLD"}
            }
        ]
    }
}


TEST_GENERATION_SYSTEM_PROMPT = """You are a test case generation agent for a financial services modernization pipeline.
You generate comprehensive test suites from plain-text business requirements.

CRITICAL CONSTRAINTS:
- Generate test cases that cover ALL business rules (BR-###) in the requirements
- Include edge cases, boundary conditions, error handling, and regulatory scenarios
- Each test case must reference which business rule(s) it validates
- Input fields must match the domain (use realistic financial values)
- Expected outputs must be precise (exact amounts, exact status codes)
- Use Decimal-compatible string values for all financial amounts

Return ONLY valid JSON. No markdown fences, no explanation."""

TEST_GENERATION_USER_PROMPT = """Generate a comprehensive test suite for the following business requirements.

REQUIREMENTS DOCUMENT:
{requirements_text}

Return a JSON array of test cases with this structure:
[
  {{
    "name": "descriptive test name",
    "category": "happy_path|boundary|error_handling|edge_case|regulatory",
    "input": {{"field_name": "string_value", ...}},
    "expected_output": {{"field_name": "string_value", ...}},
    "rationale": "References BR-### or OBS-### — explains what this tests"
  }}
]

Generate at least 8 test cases covering:
- 2+ happy path scenarios
- 2+ boundary/threshold conditions
- 2+ error handling cases (missing fields, invalid values)
- 2+ edge cases or regulatory scenarios specific to this domain

All financial values must be strings (e.g. "5000.00" not 5000)."""


def generate_test_cases(run_id: str) -> list:
    """Generate test cases from requirements using Claude API.

    Reads the requirements doc from the DB, sends it to Claude to generate
    structured test cases, and stores them in the ai_generated_tests table.
    Returns the list of generated test cases.
    """
    db = get_db()

    # Read the requirements doc
    req_row = db.execute(
        "SELECT content FROM requirements_docs WHERE run_id = ?", (run_id,)
    ).fetchone()

    if not req_row:
        db.close()
        return []

    requirements_text = req_row["content"]

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=TEST_GENERATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": TEST_GENERATION_USER_PROMPT.format(
                requirements_text=requirements_text
            )}]
        )
    except Exception as e:
        db.close()
        return [{"error": f"Test generation API call failed: {e}"}]

    raw_text = strip_json_fences(response.content[0].text)
    try:
        test_cases = json.loads(raw_text)
    except json.JSONDecodeError:
        db.close()
        return [{"error": "Failed to parse AI-generated test cases"}]

    # Store in ai_generated_tests table
    stored = []
    for tc in test_cases:
        tc_id = new_id()
        db.execute(
            """INSERT INTO ai_generated_tests
               (id, run_id, name, category, input_data, expected_output, rationale, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'ai_generated')""",
            (tc_id, run_id, tc.get("name", "Unnamed"),
             tc.get("category", ""),
             json.dumps(tc.get("input", {})),
             json.dumps(tc.get("expected_output", {})),
             tc.get("rationale", ""))
        )
        stored.append({
            "id": tc_id,
            "name": tc.get("name", "Unnamed"),
            "category": tc.get("category", ""),
            "input": tc.get("input", {}),
            "expected_output": tc.get("expected_output", {}),
            "rationale": tc.get("rationale", ""),
            "source": "ai_generated"
        })

    db.commit()
    db.close()
    return stored


def build_test_harness(code: str, test_input: dict) -> str:
    """Build a Python test harness that imports the generated module and runs one test case.

    This dynamically inspects the generated code to find the processor class/function
    and invoke it with the test input. Returns a harness string.
    """
    harness = f"""
import json
import sys
from decimal import Decimal

# Import the generated module
import generated_module as mod

test_input = json.loads('''{json.dumps(test_input)}''')

# Try to find and invoke the main processor
result = None
try:
    # Look for common class patterns
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and name != 'Enum' and not name.startswith('_'):
            # Try to instantiate and find a process/execute/run method
            try:
                instance = obj()
                for method_name in ['process', 'execute', 'run', 'rebalance', 'process_claim']:
                    if hasattr(instance, method_name):
                        method = getattr(instance, method_name)
                        # Build appropriate input based on what the method expects
                        result = method(test_input)
                        break
            except Exception:
                continue
        if result is not None:
            break

    # Serialize result
    if result is not None:
        # Handle dataclass/object serialization
        if hasattr(result, '__dict__'):
            out = {{}}
            for k, v in result.__dict__.items():
                if isinstance(v, Decimal):
                    out[k] = str(v)
                elif hasattr(v, 'value'):  # Enum
                    out[k] = v.value
                else:
                    out[k] = v
            print(json.dumps(out))
        elif isinstance(result, dict):
            print(json.dumps(result))
        else:
            print(json.dumps({{"result": str(result)}}))
    else:
        print(json.dumps({{"error": "Could not find processor"}}))
except Exception as e:
    print(json.dumps({{"error": str(e), "type": type(e).__name__}}))
"""
    return harness


def classify_drift(legacy_output: dict, modern_output: dict) -> tuple:
    """Classify drift between legacy and modern outputs.

    Returns: (drift_type: int, classification: str)
        0 = Identical
        1 = Acceptable variance (formatting, type differences)
        2 = Semantic difference (needs human judgment)
        3 = Breaking (different business outcome)
    """
    if legacy_output == modern_output:
        return (0, "Identical")

    # Normalize for comparison
    legacy_str = json.dumps(legacy_output, sort_keys=True)
    modern_str = json.dumps(modern_output, sort_keys=True)

    if legacy_str == modern_str:
        return (0, "Identical")

    # Check if core business outcome is the same
    legacy_status = legacy_output.get("status") or legacy_output.get("action", "")
    modern_status = modern_output.get("status") or modern_output.get("action", "")

    if legacy_status != modern_status:
        return (3, "Breaking — different business outcome")

    # Check for numeric differences (potential rounding drift)
    legacy_payout = legacy_output.get("payout") or legacy_output.get("trade_amount")
    modern_payout = modern_output.get("payout") or modern_output.get("trade_amount")

    if legacy_payout and modern_payout:
        try:
            diff = abs(float(legacy_payout) - float(modern_payout))
            if diff == 0:
                # Same numbers, other differences are cosmetic
                return (1, "Acceptable variance")
            elif diff < 0.02:
                return (2, "Semantic — rounding difference")
            else:
                return (3, "Breaking — value mismatch")
        except (ValueError, TypeError):
            pass

    # Default: if status matches but other fields differ, it's acceptable
    return (1, "Acceptable variance")


def _match_legacy_trace(ai_input: dict, legacy_traces: list) -> dict | None:
    """Find a matching legacy trace by comparing input fields."""
    for trace in legacy_traces:
        if all(
            str(trace["input"].get(k, "")) == str(ai_input.get(k, ""))
            for k in trace["input"]
        ):
            return trace
    return None


def run_tests(run_id: str) -> list:
    """Execute all test cases for a pipeline run.

    Phase 1: Generate AI test cases from requirements via Claude API.
    Phase 2: Execute each test against generated code.
    For tests with matching legacy traces, classify drift against the trace.
    For AI-only tests, compare against expected output.
    Returns list of test results with a source field.
    """
    db = get_db()

    # Get the generated code
    gen_row = db.execute(
        "SELECT code FROM generated_code WHERE run_id = ?", (run_id,)
    ).fetchone()

    if not gen_row:
        db.close()
        return [{"error": f"No generated code found for run {run_id}"}]

    generated_code = gen_row["code"]

    # Get the source file to determine which legacy traces to use
    run_row = db.execute(
        "SELECT source_file FROM pipeline_runs WHERE id = ?", (run_id,)
    ).fetchone()

    source_key = run_row["source_file"].replace(".cbl", "")
    legacy_traces = LEGACY_EXECUTION_TRACES.get(source_key, {}).get("test_cases", [])

    # Phase 1: Generate AI test cases
    db.close()
    ai_tests = generate_test_cases(run_id)
    db = get_db()

    # If AI generation failed, fall back to legacy traces only
    if ai_tests and isinstance(ai_tests[0], dict) and "error" in ai_tests[0] and len(ai_tests[0]) <= 2:
        ai_tests = []

    results = []

    # Phase 2a: Run legacy trace tests
    for tc in legacy_traces:
        harness = build_test_harness(generated_code, tc["input"])
        exec_result = execute_python(generated_code, harness)

        if exec_result["success"] and isinstance(exec_result["output"], dict):
            modern_output = exec_result["output"]
        else:
            modern_output = {"error": exec_result.get("stderr", "Execution failed")}

        drift_type, drift_class = classify_drift(tc["legacy_output"], modern_output)

        test_id = new_id()
        db.execute(
            """INSERT INTO test_results
               (id, run_id, test_case, input_data, legacy_output, modern_output,
                drift_type, drift_classification)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (test_id, run_id, tc["name"], json.dumps(tc["input"]),
             json.dumps(tc["legacy_output"]), json.dumps(modern_output),
             drift_type, drift_class)
        )

        results.append({
            "test_id": test_id,
            "test_case": tc["name"],
            "legacy_output": tc["legacy_output"],
            "modern_output": modern_output,
            "drift_type": drift_type,
            "drift_classification": drift_class,
            "source": "legacy_trace"
        })

    # Phase 2b: Run AI-generated tests (skip those that duplicate a legacy trace input)
    legacy_inputs = [json.dumps(tc["input"], sort_keys=True) for tc in legacy_traces]
    for tc in ai_tests:
        tc_input = tc.get("input", {})
        tc_input_key = json.dumps(tc_input, sort_keys=True)

        # Skip if this input already covered by a legacy trace
        if tc_input_key in legacy_inputs:
            continue

        harness = build_test_harness(generated_code, tc_input)
        exec_result = execute_python(generated_code, harness)

        if exec_result["success"] and isinstance(exec_result["output"], dict):
            modern_output = exec_result["output"]
        else:
            modern_output = {"error": exec_result.get("stderr", "Execution failed")}

        # Compare against AI expected output
        expected = tc.get("expected_output", {})
        drift_type, drift_class = classify_drift(expected, modern_output)

        # Reclassify for AI-generated: Type 0 = "Validated against requirements"
        if drift_type == 0:
            drift_class = "Validated against requirements"
        elif drift_type <= 1:
            drift_class = "Acceptable — minor variance from requirements"
        elif drift_type == 2:
            drift_class = "Deviation from requirements — needs review"

        test_id = new_id()
        db.execute(
            """INSERT INTO test_results
               (id, run_id, test_case, input_data, legacy_output, modern_output,
                drift_type, drift_classification)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (test_id, run_id, tc.get("name", "AI Test"), json.dumps(tc_input),
             json.dumps(expected), json.dumps(modern_output),
             drift_type, drift_class)
        )

        results.append({
            "test_id": test_id,
            "test_case": tc.get("name", "AI Test"),
            "legacy_output": expected,
            "modern_output": modern_output,
            "drift_type": drift_type,
            "drift_classification": drift_class,
            "source": "ai_generated"
        })

    db.execute("UPDATE pipeline_runs SET status = 'tested' WHERE id = ?", (run_id,))
    db.commit()
    db.close()

    return results
