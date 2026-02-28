from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from database import init_db, get_db, new_id, now_iso
from internal.legacy_store import list_files, get_file
from internal.analyzer import run_analysis
from internal.extractor import run_extraction, approve_spec
from external.generator import run_generation
from external.tester import run_tests
import json

# TODO(prod): Add request authentication (JWT or API key validation)
# TODO(prod): Add rate limiting per operator session
# TODO(prod): Replace SQLite with PostgreSQL for concurrent access
# TODO(prod): Add structured logging (JSON) with correlation IDs per run

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# Initialize database on startup (works for gunicorn, import, and direct run)
init_db()


def api_error(message: str, zone: int, code: str = "UNKNOWN", status: int = 500):
    return jsonify({"error": message, "error_code": code, "zone": zone}), status

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
    try:
        f = get_file(filename)
        if not f:
            return api_error("File not found", zone=1, code="FILE_NOT_FOUND", status=404)
        return jsonify(f)
    except Exception as e:
        return api_error(f"Failed to load file: {e}", zone=1, code="FILE_LOAD_FAILED")

# ─── Pipeline Run Management ───
@app.route('/api/runs', methods=['POST'])
def api_create_run():
    """Create a new pipeline run."""
    try:
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
    except Exception as e:
        return api_error(f"Failed to create run: {e}", zone=1, code="RUN_CREATE_FAILED")

@app.route('/api/runs/<run_id>')
def api_get_run(run_id):
    try:
        db = get_db()
        row = db.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        db.close()
        if not row:
            return api_error("Run not found", zone=1, code="RUN_NOT_FOUND", status=404)
        return jsonify(dict(row))
    except Exception as e:
        return api_error(f"Failed to get run: {e}", zone=1, code="RUN_GET_FAILED")

# ─── Zone 2: Analysis ───
@app.route('/api/analysis/run', methods=['POST'])
def api_run_analysis():
    """Trigger analysis. Runs synchronously for demo simplicity."""
    try:
        data = request.json
        run_id = data["run_id"]

        # Get source code from file
        db = get_db()
        run = db.execute("SELECT source_file, source_language FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        db.close()

        source = get_file(run["source_file"])
        if not source:
            return api_error("Source file not found", zone=2, code="SOURCE_NOT_FOUND", status=404)

        result = run_analysis(run_id, source["content"], run["source_language"])
        if "error" in result:
            return api_error(result["error"], zone=2, code="ZONE_2_ANALYSIS_FAILED")
        return jsonify(result)
    except Exception as e:
        return api_error(f"Analysis failed: {e}", zone=2, code="ZONE_2_ANALYSIS_FAILED")

@app.route('/api/analysis/<run_id>')
def api_get_analysis(run_id):
    try:
        db = get_db()
        row = db.execute("SELECT * FROM analyses WHERE run_id = ?", (run_id,)).fetchone()
        db.close()
        if not row:
            return api_error("No analysis found", zone=2, code="ANALYSIS_NOT_FOUND", status=404)
        return jsonify({
            "analysis_id": row["id"],
            "metrics": json.loads(row["metrics"]) if row["metrics"] else None,
            "confidence_score": row["confidence_score"],
            "recommendation": row["recommendation"]
        })
    except Exception as e:
        return api_error(f"Failed to get analysis: {e}", zone=2, code="ANALYSIS_GET_FAILED")

@app.route('/api/analysis/<run_id>/report')
def api_get_analysis_report(run_id):
    """Return a downloadable Markdown analysis report."""
    try:
        from internal.analyzer import generate_report_markdown
        report = generate_report_markdown(run_id)
        if not report:
            return api_error("No analysis found for this run", zone=2, code="REPORT_NOT_FOUND", status=404)
        return Response(
            report,
            mimetype='text/markdown',
            headers={'Content-Disposition': f'attachment; filename=analysis-report-{run_id}.md'}
        )
    except Exception as e:
        return api_error(f"Failed to generate report: {e}", zone=2, code="REPORT_GENERATION_FAILED")

# ─── Zone 3: Extraction ───
@app.route('/api/extraction/run', methods=['POST'])
def api_run_extraction():
    try:
        data = request.json
        run_id = data["run_id"]

        db = get_db()
        run = db.execute("SELECT source_file, source_language FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        db.close()

        source = get_file(run["source_file"])
        if not source:
            return api_error("Source file not found", zone=3, code="SOURCE_NOT_FOUND", status=404)

        result = run_extraction(run_id, source["content"], run["source_language"])
        return jsonify(result)
    except Exception as e:
        return api_error(f"Extraction failed: {e}", zone=3, code="ZONE_3_EXTRACTION_FAILED")

@app.route('/api/extraction/<run_id>/rules')
def api_get_rules(run_id):
    try:
        db = get_db()
        rows = db.execute("SELECT * FROM business_rules WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return api_error(f"Failed to get rules: {e}", zone=3, code="RULES_GET_FAILED")

@app.route('/api/extraction/<run_id>/requirements')
def api_get_requirements(run_id):
    try:
        db = get_db()
        row = db.execute("SELECT * FROM requirements_docs WHERE run_id = ?", (run_id,)).fetchone()
        db.close()
        if not row:
            return api_error("No requirements doc found", zone=3, code="REQUIREMENTS_NOT_FOUND", status=404)
        return jsonify(dict(row))
    except Exception as e:
        return api_error(f"Failed to get requirements: {e}", zone=3, code="REQUIREMENTS_GET_FAILED")

@app.route('/api/extraction/<run_id>/approve', methods=['POST'])
def api_approve_spec(run_id):
    try:
        data = request.json
        result = approve_spec(run_id, data["operator"], data.get("rationale", ""))
        return jsonify(result)
    except Exception as e:
        return api_error(f"Approval failed: {e}", zone=3, code="SPEC_APPROVAL_FAILED")

@app.route('/api/extraction/<run_id>/prd')
def api_get_prd(run_id):
    """Return the requirements document as a downloadable Markdown PRD."""
    try:
        db = get_db()
        req_row = db.execute("SELECT content FROM requirements_docs WHERE run_id = ?", (run_id,)).fetchone()
        rules_rows = db.execute("SELECT * FROM business_rules WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        run_row = db.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        db.close()

        if not req_row:
            return api_error("No requirements document found", zone=3, code="PRD_NOT_FOUND", status=404)

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
    except Exception as e:
        return api_error(f"Failed to generate PRD: {e}", zone=3, code="PRD_GENERATION_FAILED")

# ─── Zone 4: Generation (EXTERNAL — no source code access) ───
@app.route('/api/generation/run', methods=['POST'])
def api_run_generation():
    try:
        data = request.json
        run_id = data["run_id"]
        requirements_doc_id = data["requirements_doc_id"]

        result = run_generation(run_id, requirements_doc_id)
        if "error" in result:
            return api_error(result["error"], zone=4, code="ZONE_4_GENERATION_FAILED")
        return jsonify(result)
    except Exception as e:
        return api_error(f"Generation failed: {e}", zone=4, code="ZONE_4_GENERATION_FAILED")

@app.route('/api/generation/<run_id>')
def api_get_generated(run_id):
    try:
        db = get_db()
        row = db.execute("SELECT * FROM generated_code WHERE run_id = ?", (run_id,)).fetchone()
        db.close()
        if not row:
            return api_error("No generated code found", zone=4, code="GENERATED_CODE_NOT_FOUND", status=404)
        return jsonify({
            "generation_id": row["id"],
            "code": row["code"],
            "language": row["language"],
            "generation_prompt": row["generation_prompt"]
        })
    except Exception as e:
        return api_error(f"Failed to get generated code: {e}", zone=4, code="GENERATED_CODE_GET_FAILED")

# ─── Zone 5: Testing (EXTERNAL) ───
@app.route('/api/testing/run', methods=['POST'])
def api_run_tests():
    try:
        data = request.json
        run_id = data["run_id"]
        results = run_tests(run_id)
        if results and isinstance(results[0], dict) and "error" in results[0] and len(results[0]) == 1:
            return api_error(results[0]["error"], zone=5, code="ZONE_5_TEST_FAILED")
        return jsonify(results)
    except Exception as e:
        return api_error(f"Test execution failed: {e}", zone=5, code="ZONE_5_TEST_FAILED")

@app.route('/api/testing/<run_id>/results')
def api_get_test_results(run_id):
    try:
        db = get_db()
        rows = db.execute("SELECT * FROM test_results WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return api_error(f"Failed to get test results: {e}", zone=5, code="TEST_RESULTS_GET_FAILED")

@app.route('/api/testing/<run_id>/generated-tests')
def api_get_generated_tests(run_id):
    """Return AI-generated test cases for display in the UI."""
    try:
        db = get_db()
        rows = db.execute("SELECT * FROM ai_generated_tests WHERE run_id = ? ORDER BY created_at", (run_id,)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return api_error(f"Failed to get generated tests: {e}", zone=5, code="GENERATED_TESTS_GET_FAILED")

@app.route('/api/testing/<run_id>/adjudicate', methods=['POST'])
def api_adjudicate(run_id):
    try:
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
    except Exception as e:
        return api_error(f"Adjudication failed: {e}", zone=5, code="ADJUDICATION_FAILED")

# ─── Zone 6: Production decisions ───
@app.route('/api/production/<run_id>/decide', methods=['POST'])
def api_production_decision(run_id):
    try:
        data = request.json
        db = get_db()
        ts = now_iso()

        decision_id = new_id()
        db.execute(
            """INSERT INTO decisions (id, run_id, zone, gate_name, decision, rationale, operator)
               VALUES (?, ?, 6, 'production_auth', ?, ?, ?)""",
            (decision_id, run_id, data["decision"], data.get("rationale", ""), data["operator"])
        )

        if data["decision"] == "authorize":
            db.execute("UPDATE pipeline_runs SET status = 'shadow' WHERE id = ?", (run_id,))

        db.commit()
        db.close()

        return jsonify({"decision": data["decision"], "operator": data["operator"], "timestamp": ts})
    except Exception as e:
        return api_error(f"Production decision failed: {e}", zone=6, code="PRODUCTION_DECISION_FAILED")

@app.route('/api/deployment/<run_id>/readiness')
def api_deployment_readiness(run_id):
    """Aggregate deployment readiness data from all prior zones."""
    try:
        db = get_db()

        # Analysis confidence + recommendation (Zone 2)
        analysis_row = db.execute(
            "SELECT confidence_score, recommendation, metrics FROM analyses WHERE run_id = ?", (run_id,)
        ).fetchone()
        analysis = None
        if analysis_row:
            analysis = {
                "confidence_score": analysis_row["confidence_score"],
                "recommendation": analysis_row["recommendation"],
            }

        # Rule count + validation status (Zone 3)
        rules_rows = db.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN validated_by IS NOT NULL THEN 1 ELSE 0 END) as validated FROM business_rules WHERE run_id = ?", (run_id,)
        ).fetchone()
        req_row = db.execute(
            "SELECT approved_by FROM requirements_docs WHERE run_id = ?", (run_id,)
        ).fetchone()
        rules = {
            "total": rules_rows["total"] if rules_rows else 0,
            "validated": rules_rows["validated"] if rules_rows else 0,
            "spec_approved_by": req_row["approved_by"] if req_row else None,
        }

        # Test pass rate + drift counts (Zone 5)
        test_rows = db.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN drift_type = 0 THEN 1 ELSE 0 END) as identical,
                      SUM(CASE WHEN drift_type = 1 THEN 1 ELSE 0 END) as acceptable,
                      SUM(CASE WHEN drift_type = 2 THEN 1 ELSE 0 END) as semantic,
                      SUM(CASE WHEN drift_type = 3 THEN 1 ELSE 0 END) as breaking,
                      SUM(CASE WHEN adjudication_decision IS NOT NULL THEN 1 ELSE 0 END) as adjudicated
               FROM test_results WHERE run_id = ?""", (run_id,)
        ).fetchone()
        tests = {
            "total": test_rows["total"] if test_rows else 0,
            "identical": test_rows["identical"] if test_rows else 0,
            "acceptable": test_rows["acceptable"] if test_rows else 0,
            "semantic": test_rows["semantic"] if test_rows else 0,
            "breaking": test_rows["breaking"] if test_rows else 0,
            "adjudicated": test_rows["adjudicated"] if test_rows else 0,
        }

        # All decisions (all zones)
        decision_rows = db.execute(
            "SELECT * FROM decisions WHERE run_id = ? ORDER BY created_at", (run_id,)
        ).fetchall()
        decisions = [dict(d) for d in decision_rows]

        db.close()

        return jsonify({
            "analysis": analysis,
            "rules": rules,
            "tests": tests,
            "decisions": decisions,
        })
    except Exception as e:
        return api_error(f"Failed to get deployment readiness: {e}", zone=6, code="READINESS_GET_FAILED")

# ─── Cross-cutting: Audit Trail ───
@app.route('/api/runs/<run_id>/decisions')
def api_get_decisions(run_id):
    try:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM decisions WHERE run_id = ? ORDER BY created_at", (run_id,)
        ).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return api_error(f"Failed to get decisions: {e}", zone=1, code="DECISIONS_GET_FAILED")


@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "version": "0.1.0"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
