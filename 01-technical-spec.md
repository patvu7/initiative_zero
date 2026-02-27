# Initiative Zero — Technical Specification

> **Purpose:** This document is the implementation reference for building Initiative Zero as a full-stack application. It contains the complete file structure, database schema, API contracts, AI prompts, and code for every module. A coding agent or developer should be able to build the entire system from this spec.

---

## 1. Stack & Environment

- **Runtime:** Python 3.11+
- **Framework:** Flask 3.x (with flask-cors)
- **Database:** SQLite 3 (file: `decisions.db`)
- **AI:** Anthropic Python SDK (`anthropic` package)
- **Model:** `claude-sonnet-4-20250514` for all API calls
- **Frontend:** Static HTML/CSS/JS served by Flask (port from existing `prototype.html`)
- **Execution:** Python `subprocess` for sandboxed code execution in Zone 5
- **Deployment target:** Replit (Python template)

### Dependencies (requirements.txt)

```
flask>=3.0
flask-cors>=4.0
anthropic>=0.40
gunicorn>=21.2
```

---

## 2. File Structure

```
initiative-zero/
├── app.py                        # Flask application, all route definitions
├── database.py                   # SQLite initialization, helper functions
├── requirements.txt
│
├── internal/                     # ZONES 1–3: Has access to source code
│   ├── __init__.py               # Empty
│   ├── analyzer.py               # Zone 2: Code analysis via Claude
│   ├── extractor.py              # Zone 3: Business rule extraction via Claude
│   └── legacy_store.py           # Zone 1: Read/list files from samples/
│
├── external/                     # ZONES 4–5: NEVER imports from internal/
│   ├── __init__.py               # Empty
│   ├── generator.py              # Zone 4: Code generation from requirements only
│   ├── tester.py                 # Zone 5: Drift testing and classification
│   └── executor.py               # Sandboxed Python execution
│
├── static/                       # Frontend assets
│   ├── index.html                # Ported from prototype.html
│   ├── style.css                 # Extracted from prototype <style> block
│   └── app.js                    # Extracted from prototype <script> block, refactored to call APIs
│
├── samples/                      # Legacy code files for demo
│   ├── claims_processing.cbl     # Insurance example (existing)
│   └── portfolio_rebalance.cbl   # Wealthsimple-relevant example (primary demo)
│
└── decisions.db                  # Created at runtime by database.py
```

### Critical Architectural Constraint

**`external/` must NEVER import from `internal/`.** The `external/` package accesses legacy data ONLY through the `requirements_docs` table in the database. This is the security firewall — the code generation module never has access to source code, schemas, or internal implementation details.

Enforce this with a comment at the top of every file in `external/`:

```python
# ⚠ SECURITY BOUNDARY: This module is in the external zone.
# It MUST NOT import from internal/. It receives ONLY plain-text
# requirements via the database. No source code, no schemas, no IP.
```

---

## 3. Database Schema

File: `database.py`

```python
import sqlite3
import uuid
import json
from datetime import datetime, timezone

DB_PATH = "decisions.db"

def get_db():
    """Get a database connection with row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id TEXT PRIMARY KEY,
            source_file TEXT NOT NULL,
            source_language TEXT NOT NULL,
            target_language TEXT DEFAULT 'python',
            status TEXT DEFAULT 'initiated',
            created_at TEXT DEFAULT (datetime('now')),
            operator TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
            raw_response TEXT,
            metrics TEXT,
            confidence_score REAL,
            recommendation TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS business_rules (
            id TEXT NOT NULL,
            run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
            rule_text TEXT NOT NULL,
            source_reference TEXT,
            rule_type TEXT DEFAULT 'explicit',
            status TEXT DEFAULT 'extracted',
            validated_by TEXT,
            validated_at TEXT,
            PRIMARY KEY (id, run_id)
        );

        CREATE TABLE IF NOT EXISTS requirements_docs (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
            content TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT,
            content_hash TEXT
        );

        CREATE TABLE IF NOT EXISTS generated_code (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
            requirements_doc_id TEXT REFERENCES requirements_docs(id),
            language TEXT DEFAULT 'python',
            code TEXT NOT NULL,
            generation_prompt TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS test_results (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
            test_case TEXT NOT NULL,
            input_data TEXT,
            legacy_output TEXT,
            modern_output TEXT,
            drift_type INTEGER,
            drift_classification TEXT,
            adjudicated_by TEXT,
            adjudicated_at TEXT,
            adjudication_decision TEXT
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
            zone INTEGER NOT NULL,
            gate_name TEXT NOT NULL,
            decision TEXT NOT NULL,
            rationale TEXT,
            operator TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

def new_id():
    return str(uuid.uuid4())[:8]

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')
```

---

## 4. Module Implementations

### 4.1 `internal/legacy_store.py` — Zone 1

```python
import os
import pathlib

SAMPLES_DIR = pathlib.Path(__file__).parent.parent / "samples"

def list_files():
    """Return list of available legacy files with metadata."""
    files = []
    for f in SAMPLES_DIR.glob("*.cbl"):
        stat = f.stat()
        content = f.read_text()
        lines = content.strip().split('\n')
        # Extract metadata from header comments
        files.append({
            "filename": f.name,
            "language": "COBOL",
            "loc": len(lines),
            "size_bytes": stat.st_size,
            "content": content
        })
    return files

def get_file(filename: str):
    """Return contents and metadata of a specific file."""
    path = SAMPLES_DIR / filename
    if not path.exists() or not path.suffix == '.cbl':
        return None
    content = path.read_text()
    lines = content.strip().split('\n')
    return {
        "filename": filename,
        "language": "COBOL",
        "loc": len(lines),
        "content": content
    }
```

### 4.2 `internal/analyzer.py` — Zone 2

```python
import json
import anthropic
from database import get_db, new_id, now_iso

client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

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
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=ANALYSIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    
    raw_text = response.content[0].text
    
    # Parse JSON — strip markdown fences if present
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    
    metrics = json.loads(cleaned)
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
```

### 4.3 `internal/extractor.py` — Zone 3

```python
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
```

### 4.4 `external/generator.py` — Zone 4

```python
# ⚠ SECURITY BOUNDARY: This module is in the external zone.
# It MUST NOT import from internal/. It receives ONLY plain-text
# requirements via the database. No source code, no schemas, no IP.

import json
import anthropic
from database import get_db, new_id

client = anthropic.Anthropic()

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
        raise ValueError(f"Requirements doc {requirements_doc_id} not found for run {run_id}")
    
    if not row["approved_by"]:
        raise ValueError("Requirements document has not been approved. Cannot generate.")
    
    requirements_text = row["content"]
    
    # Build the prompt — store it for auditability
    full_prompt = GENERATION_USER_PROMPT.format(requirements_text=requirements_text)
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=GENERATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": full_prompt}]
    )
    
    generated_code = response.content[0].text.strip()
    # Strip markdown fences if present
    if generated_code.startswith("```"):
        generated_code = generated_code.split("\n", 1)[1]
        if generated_code.endswith("```"):
            generated_code = generated_code[:-3]
    
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
```

### 4.5 `external/executor.py` — Sandboxed Execution

```python
# ⚠ SECURITY BOUNDARY: This module is in the external zone.

import subprocess
import tempfile
import json
import os

TIMEOUT_SECONDS = 10

def execute_python(code: str, test_harness: str) -> dict:
    """Execute generated Python code with a test harness in a subprocess sandbox.
    
    Args:
        code: The generated Python module code
        test_harness: Python code that imports the module, runs a test case, 
                      and prints JSON result to stdout
    
    Returns:
        {"success": bool, "output": dict or str, "stderr": str}
    """
    tmpdir = tempfile.mkdtemp(prefix="iz_exec_")
    module_path = os.path.join(tmpdir, "generated_module.py")
    harness_path = os.path.join(tmpdir, "test_harness.py")
    
    try:
        # Write the generated module
        with open(module_path, 'w') as f:
            f.write(code)
        
        # Write the test harness
        with open(harness_path, 'w') as f:
            f.write(f"import sys\nsys.path.insert(0, '{tmpdir}')\n")
            f.write(test_harness)
        
        # Execute in subprocess with timeout
        result = subprocess.run(
            ['python3', harness_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=tmpdir,
            env={**os.environ, "PYTHONPATH": tmpdir}
        )
        
        if result.returncode == 0:
            try:
                output = json.loads(result.stdout.strip())
                return {"success": True, "output": output, "stderr": result.stderr}
            except json.JSONDecodeError:
                return {"success": True, "output": result.stdout.strip(), "stderr": result.stderr}
        else:
            return {"success": False, "output": result.stdout, "stderr": result.stderr}
    
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "stderr": "Execution timed out"}
    except Exception as e:
        return {"success": False, "output": "", "stderr": str(e)}
    finally:
        # Cleanup
        for f in [module_path, harness_path]:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(tmpdir):
            os.rmdir(tmpdir)
```

### 4.6 `external/tester.py` — Zone 5

```python
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
                "legacy_output": {"action": "SELL", "trade_amount": "7000.00", "tlh_flag": true}
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
```

---

## 5. Flask Application — `app.py`

```python
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from database import init_db, get_db, new_id, now_iso
from internal.legacy_store import list_files, get_file
from internal.analyzer import run_analysis
from internal.extractor import run_extraction, approve_spec
from external.generator import run_generation
from external.tester import run_tests
import json
import threading

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

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
    results = run_tests(run_id)
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
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
```

---

## 6. Frontend Refactoring Notes

The existing `prototype.html` must be split into `static/index.html`, `static/style.css`, and `static/app.js`. The JS must be refactored to:

### 6.1 State Management

Replace the current zone-based `setTimeout` simulation with an API-driven state machine:

```javascript
// Core state
let state = {
    runId: null,
    currentZone: 1,
    sourceFile: null,
    requirementsDocId: null,
    analysis: null,
    rules: null,
    generatedCode: null,
    testResults: null
};
```

### 6.2 Key Function Replacements

| Current Function | Replacement |
|---|---|
| `runAnalysis()` with `setTimeout` | `fetch('/api/analysis/run', {method: 'POST', body: {run_id}})` → poll or await |
| `runStrainer()` with `setTimeout` + hardcoded `RULES` | `fetch('/api/extraction/run', ...)` → populate table from response |
| `smeSign()` writing inline HTML | `fetch('/api/extraction/{id}/approve', ...)` → update UI from response |
| `runGeneration()` with `setTimeout` | `fetch('/api/generation/run', ...)` → display real generated code |
| `runTesting()` with `setTimeout` | `fetch('/api/testing/run', ...)` → populate test table from real results |
| `adjudicate()` writing inline HTML | `fetch('/api/testing/{id}/adjudicate', ...)` → record in DB |

### 6.3 New UI Elements

1. **Zone 1 file selector:** Dropdown to choose between `claims_processing.cbl` and `portfolio_rebalance.cbl`. Populated from `/api/legacy/files`.

2. **Zone 4 "View Generation Prompt" panel:** Collapsible section below the generated code that shows the exact prompt sent to Claude. This is the firewall proof — the reviewer can see zero source code was included.

3. **Zone 5 test results from real execution:** Replace the hardcoded `<table>` rows with dynamically generated rows from `/api/testing/{run_id}/results`. Color-code by drift_type.

4. **Loading states:** Each API call takes 3–10 seconds. Show the existing processing animation (dots) during each call. The latency actually helps the demo — it shows real work happening.

### 6.4 API Helper

```javascript
async function api(path, method = 'GET', body = null) {
    const opts = {
        method,
        headers: {'Content-Type': 'application/json'}
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}
```

---

## 7. Sample Files

### 7.1 `samples/claims_processing.cbl`

Use the existing COBOL from the prototype (the `code-body` content in Zone 1).

### 7.2 `samples/portfolio_rebalance.cbl`

Use the `portfolio_rebalance.cbl` file already created in the project.

---

## 8. Environment Variables

Set in Replit Secrets:

```
ANTHROPIC_API_KEY=sk-ant-...
```

No other env vars required. SQLite is file-based. Flask runs on port 5000 (Replit auto-detects).

---

## 9. Startup

`app.py` calls `init_db()` on startup, which creates all tables if they don't exist. No migration step needed.

Run command: `python app.py` (or `gunicorn app:app` for Replit deployment).
