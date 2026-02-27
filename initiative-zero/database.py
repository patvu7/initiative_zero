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

def strip_json_fences(text: str) -> str:
    """Strip markdown code fences from Claude API responses."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence line (```json or ```)
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        # Remove closing fence
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()

def new_id():
    return str(uuid.uuid4())[:8]

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')
