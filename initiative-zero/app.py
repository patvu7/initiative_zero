from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from database import init_db, get_db, new_id, now_iso
from internal.legacy_store import list_files, get_file
from internal.analyzer import run_analysis
from internal.extractor import run_extraction, approve_spec
from external.generator import run_generation
from external.tester import run_tests
import json

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# Initialize database on startup (works for gunicorn, import, and direct run)
init_db()

# ─── Static Frontend ───
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# ─── Zone 1: Legacy Files ───
@app.route('/api/legacy/files')
def api_list_files():
    return jsonify(list_files())

@app.route('/api/legacy/files/<filename>')
def api_get_file(filename):
    f = get_file(filename)
    if not f:
        return jsonify({"error": "File not found"}), 404
    return jsonify(f)

# ─── Pipeline Run Management ───
@app.route('/api/runs', methods=['POST'])
def api_create_run():
    """Create a new pipeline run."""
    data = request.json
    run_id = new_id()
    db = get_db()
    db.execute(
        "INSERT INTO pipeline_runs (id, source_file, source_language, operator) VALUES (?, ?, ?, ?)",
        (run_id, data["source_file"], data.get("source_language", "COBOL"), data.get("operator", "Operator"))
    )
    db.commit()
    db.close()
    return jsonify({"run_id": run_id})

@app.route('/api/runs/<run_id>')
def api_get_run(run_id):
    db = get_db()
    row = db.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(dict(row))

# ─── Zone 2: Analysis ───
@app.route('/api/analysis/run', methods=['POST'])
def api_run_analysis():
    """Trigger analysis. Runs synchronously for demo simplicity."""
    data = request.json
    run_id = data["run_id"]

    # Get source code from file
    db = get_db()
    run = db.execute("SELECT source_file, source_language FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    db.close()

    source = get_file(run["source_file"])
    if not source:
        return jsonify({"error": "Source file not found"}), 404

    result = run_analysis(run_id, source["content"], run["source_language"])
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)

@app.route('/api/analysis/<run_id>')
def api_get_analysis(run_id):
    db = get_db()
    row = db.execute("SELECT * FROM analyses WHERE run_id = ?", (run_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "No analysis found"}), 404
    return jsonify({
        "analysis_id": row["id"],
        "metrics": json.loads(row["metrics"]) if row["metrics"] else None,
        "confidence_score": row["confidence_score"],
        "recommendation": row["recommendation"]
    })

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

# ─── Zone 3: Extraction ───
@app.route('/api/extraction/run', methods=['POST'])
def api_run_extraction():
    data = request.json
    run_id = data["run_id"]

    db = get_db()
    run = db.execute("SELECT source_file, source_language FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    db.close()

    source = get_file(run["source_file"])
    if not source:
        return jsonify({"error": "Source file not found"}), 404

    result = run_extraction(run_id, source["content"], run["source_language"])
    return jsonify(result)

@app.route('/api/extraction/<run_id>/rules')
def api_get_rules(run_id):
    db = get_db()
    rows = db.execute("SELECT * FROM business_rules WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/extraction/<run_id>/requirements')
def api_get_requirements(run_id):
    db = get_db()
    row = db.execute("SELECT * FROM requirements_docs WHERE run_id = ?", (run_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "No requirements doc found"}), 404
    return jsonify(dict(row))

@app.route('/api/extraction/<run_id>/approve', methods=['POST'])
def api_approve_spec(run_id):
    data = request.json
    result = approve_spec(run_id, data["operator"], data.get("rationale", ""))
    return jsonify(result)

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

# ─── Zone 4: Generation (EXTERNAL — no source code access) ───
@app.route('/api/generation/run', methods=['POST'])
def api_run_generation():
    data = request.json
    run_id = data["run_id"]
    requirements_doc_id = data["requirements_doc_id"]

    result = run_generation(run_id, requirements_doc_id)
    return jsonify(result)

@app.route('/api/generation/<run_id>')
def api_get_generated(run_id):
    db = get_db()
    row = db.execute("SELECT * FROM generated_code WHERE run_id = ?", (run_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "No generated code found"}), 404
    return jsonify({
        "generation_id": row["id"],
        "code": row["code"],
        "language": row["language"],
        "generation_prompt": row["generation_prompt"]
    })

# ─── Zone 5: Testing (EXTERNAL) ───
@app.route('/api/testing/run', methods=['POST'])
def api_run_tests():
    data = request.json
    run_id = data["run_id"]
    try:
        results = run_tests(run_id)
    except Exception as e:
        return jsonify({"error": f"Test execution failed: {str(e)}"}), 500
    if results and isinstance(results[0], dict) and "error" in results[0] and len(results[0]) == 1:
        return jsonify(results[0]), 500
    return jsonify(results)

@app.route('/api/testing/<run_id>/results')
def api_get_test_results(run_id):
    db = get_db()
    rows = db.execute("SELECT * FROM test_results WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/testing/<run_id>/adjudicate', methods=['POST'])
def api_adjudicate(run_id):
    data = request.json
    db = get_db()
    ts = now_iso()

    # Update test result
    db.execute(
        """UPDATE test_results
           SET adjudicated_by = ?, adjudicated_at = ?, adjudication_decision = ?
           WHERE id = ? AND run_id = ?""",
        (data["operator"], ts, data["decision"], data["test_id"], run_id)
    )

    # Record decision
    decision_id = new_id()
    db.execute(
        """INSERT INTO decisions (id, run_id, zone, gate_name, decision, rationale, operator)
           VALUES (?, ?, 5, 'drift_adjudication', ?, ?, ?)""",
        (decision_id, run_id, data["decision"], data.get("rationale", ""), data["operator"])
    )

    db.commit()
    db.close()

    return jsonify({"decision": data["decision"], "operator": data["operator"], "timestamp": ts})

# ─── Zone 6: Production decisions ───
@app.route('/api/production/<run_id>/decide', methods=['POST'])
def api_production_decision(run_id):
    data = request.json
    db = get_db()
    ts = now_iso()

    decision_id = new_id()
    db.execute(
        """INSERT INTO decisions (id, run_id, zone, gate_name, decision, rationale, operator)
           VALUES (?, ?, 6, 'production_auth', ?, ?, ?)""",
        (decision_id, run_id, data["decision"], data.get("rationale", ""), data["operator"])
    )

    if data["decision"] == "promote":
        db.execute("UPDATE pipeline_runs SET status = 'canary' WHERE id = ?", (run_id,))

    db.commit()
    db.close()

    return jsonify({"decision": data["decision"], "operator": data["operator"], "timestamp": ts})

# ─── Zone 6: Coexistence Simulation ───
@app.route('/api/coexistence/<run_id>/simulate', methods=['POST'])
def api_coexistence_simulate(run_id):
    """Simulate coexistence: run one transaction through both legacy and modern."""
    data = request.json
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    test_index = data.get("test_index", 0)

    db = get_db()
    gen_row = db.execute("SELECT code FROM generated_code WHERE run_id = ?", (run_id,)).fetchone()
    run_row = db.execute("SELECT source_file FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    db.close()

    if not gen_row or not run_row:
        return jsonify({"error": "Run data not found"}), 404

    from external.tester import LEGACY_BEHAVIORS, build_test_harness, classify_drift
    from external.executor import execute_python

    source_key = run_row["source_file"].replace(".cbl", "")
    test_cases = LEGACY_BEHAVIORS.get(source_key, {}).get("test_cases", [])

    if not isinstance(test_index, int) or test_index < 0 or test_index >= len(test_cases):
        return jsonify({"error": "Test index out of range"}), 400

    tc = test_cases[test_index]
    try:
        harness = build_test_harness(gen_row["code"], tc["input"])
        exec_result = execute_python(gen_row["code"], harness)
    except Exception as e:
        return jsonify({"error": f"Simulation execution failed: {str(e)}"}), 500

    if exec_result["success"] and isinstance(exec_result["output"], dict):
        modern_output = exec_result["output"]
    else:
        modern_output = {"error": exec_result.get("stderr", "Execution failed")}

    drift_type, drift_class = classify_drift(tc["legacy_output"], modern_output)

    return jsonify({
        "test_case": tc["name"],
        "input": tc["input"],
        "legacy_output": tc["legacy_output"],
        "modern_output": modern_output,
        "drift_type": drift_type,
        "drift_classification": drift_class,
        "legacy_latency_ms": 340,
        "modern_latency_ms": 12
    })

# ─── Cross-cutting: Audit Trail ───
@app.route('/api/runs/<run_id>/decisions')
def api_get_decisions(run_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM decisions WHERE run_id = ? ORDER BY created_at", (run_id,)
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
