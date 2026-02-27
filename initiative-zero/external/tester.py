# ⚠ SECURITY BOUNDARY: This module is in the external zone.

import json
from database import get_db, new_id, now_iso
from external.executor import execute_python

# Legacy behavior simulation — replicates COBOL truncation/quirks
# This is NOT the source code. It's a behavioral model of known legacy outputs.
LEGACY_BEHAVIORS = {
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


def build_test_harness(code: str, test_input: dict) -> str:
    """Build a Python test harness that imports the generated module and runs one test case.

    This dynamically inspects the generated code to find the processor class/function
    and invoke it with the test input. Returns a harness string.
    """
    # The harness needs to be adaptable since we don't know exact class/function names
    # We use a pattern that searches for common patterns in the generated code
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


def run_tests(run_id: str) -> list:
    """Execute all test cases for a pipeline run. Returns list of test results."""
    db = get_db()

    # Get the generated code
    gen_row = db.execute(
        "SELECT code FROM generated_code WHERE run_id = ?", (run_id,)
    ).fetchone()

    if not gen_row:
        raise ValueError(f"No generated code found for run {run_id}")

    generated_code = gen_row["code"]

    # Get the source file to determine which test suite to use
    run_row = db.execute(
        "SELECT source_file FROM pipeline_runs WHERE id = ?", (run_id,)
    ).fetchone()

    source_key = run_row["source_file"].replace(".cbl", "")
    test_suite = LEGACY_BEHAVIORS.get(source_key, {}).get("test_cases", [])

    results = []
    for tc in test_suite:
        # Execute the generated code against this test case
        harness = build_test_harness(generated_code, tc["input"])
        exec_result = execute_python(generated_code, harness)

        if exec_result["success"] and isinstance(exec_result["output"], dict):
            modern_output = exec_result["output"]
        else:
            modern_output = {"error": exec_result.get("stderr", "Execution failed")}

        # Classify drift
        drift_type, drift_class = classify_drift(tc["legacy_output"], modern_output)

        # Store result
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
            "drift_classification": drift_class
        })

    db.execute("UPDATE pipeline_runs SET status = 'tested' WHERE id = ?", (run_id,))
    db.commit()
    db.close()

    return results
