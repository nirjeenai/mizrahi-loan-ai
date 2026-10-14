"""SQLite persistence — one durable file for case state, documents, runs, findings,
conversation, jobs and audit. A single process-wide connection guarded by a lock
(the worker thread and the API share it); WAL keeps reads cheap."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, borrower_id TEXT, requirement_code TEXT,
  filename TEXT NOT NULL, mime TEXT, sha256 TEXT NOT NULL, bytes INTEGER, pages INTEGER,
  text_layer_chars INTEGER, storage_path TEXT NOT NULL, uploaded_at TEXT NOT NULL, uploaded_by TEXT,
  channel TEXT, status TEXT NOT NULL, stage TEXT, current_run_id TEXT, error TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_documents_case_sha ON documents(case_id, sha256);
CREATE TABLE IF NOT EXISTS review_runs (
  run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, document_id TEXT, scope TEXT NOT NULL,
  provider TEXT NOT NULL, models TEXT, rubric_id TEXT, rubric_version TEXT, prompt_version TEXT,
  status TEXT NOT NULL, stage TEXT, started_at TEXT NOT NULL, finished_at TEXT, error TEXT,
  input_hash TEXT, result TEXT, trigger TEXT
);
CREATE INDEX IF NOT EXISTS ix_runs_case ON review_runs(case_id, started_at);
CREATE TABLE IF NOT EXISTS findings (
  finding_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, key TEXT NOT NULL, code TEXT NOT NULL,
  severity TEXT NOT NULL, review_state TEXT NOT NULL, status TEXT NOT NULL, borrower_id TEXT,
  document_id TEXT, period TEXT, title_he TEXT, message_he TEXT, detail TEXT, evidence TEXT,
  created_run_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, resolved_run_id TEXT,
  resolved_at TEXT, resolution TEXT, resolution_note TEXT, superseded_by TEXT, history TEXT
);
CREATE INDEX IF NOT EXISTS ix_findings_case ON findings(case_id, status);
CREATE TABLE IF NOT EXISTS statements (
  statement_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, finding_id TEXT, channel TEXT, text TEXT NOT NULL,
  actor TEXT, created_at TEXT NOT NULL, request_id TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS turns (
  turn_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, conversation_id TEXT NOT NULL, channel TEXT NOT NULL,
  role TEXT NOT NULL, text TEXT NOT NULL, provenance TEXT, tool_calls TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_turns_case ON turns(case_id, created_at);
CREATE TABLE IF NOT EXISTS audit (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, case_id TEXT, actor TEXT NOT NULL,
  action TEXT NOT NULL, target TEXT, detail TEXT, trace_id TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_case ON audit(case_id, event_id);
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY, kind TEXT NOT NULL, case_id TEXT NOT NULL, document_id TEXT,
  idempotency_key TEXT UNIQUE, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
  not_before TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS llm_calls (
  call_id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, model TEXT, purpose TEXT, run_id TEXT,
  prompt_tokens INTEGER, output_tokens INTEGER, thought_tokens INTEGER, latency_ms INTEGER, ok INTEGER, error TEXT
);
CREATE TABLE IF NOT EXISTS case_state (
  case_id TEXT PRIMARY KEY, readiness TEXT, updated_at TEXT, last_case_run_id TEXT
);
CREATE TABLE IF NOT EXISTS handoffs (
  package_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
  created_by TEXT, channel TEXT, note TEXT, package TEXT, request_id TEXT UNIQUE,
  banker_decision TEXT, decided_at TEXT, decided_note TEXT
);
CREATE TABLE IF NOT EXISTS upload_intents (
  document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, requirement_code TEXT, expected_period TEXT,
  action_id TEXT, origin_turn_id TEXT, created_new INTEGER NOT NULL, created_at TEXT NOT NULL, followup_turn_id TEXT,
  replaces_document_id TEXT
);
CREATE TABLE IF NOT EXISTS banker_decisions (
  decision_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_kind TEXT NOT NULL, document_id TEXT, finding_id TEXT,
  borrower_id TEXT, period TEXT, action TEXT NOT NULL, previous_status TEXT, new_status TEXT, rationale TEXT,
  customer_message TEXT, customer_request_id TEXT, finding_ids TEXT, evidence_refs TEXT,
  actor_id TEXT NOT NULL, actor_name TEXT, created_at TEXT NOT NULL, request_id TEXT UNIQUE, reason_code TEXT
);
CREATE INDEX IF NOT EXISTS ix_decisions_case ON banker_decisions(case_id, created_at);
CREATE TABLE IF NOT EXISTS customer_requests (
  customer_request_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, kind TEXT NOT NULL, borrower_id TEXT,
  requirement_code TEXT, period TEXT, document_id TEXT, finding_id TEXT, title_he TEXT, message_he TEXT NOT NULL,
  status TEXT NOT NULL, created_at TEXT NOT NULL, created_by TEXT, created_by_name TEXT, decision_id TEXT,
  responded_document_id TEXT, responded_at TEXT, updated_at TEXT NOT NULL, responded_statement_id TEXT, closed_reason TEXT
);
CREATE INDEX IF NOT EXISTS ix_requests_case ON customer_requests(case_id, status);
-- loan completion: versioned configuration (policy and Talk prompt), per-case pin, orchestration and contact
CREATE TABLE IF NOT EXISTS config_versions (
  version_id TEXT PRIMARY KEY, kind TEXT NOT NULL, scope TEXT NOT NULL, number INTEGER, status TEXT NOT NULL,
  config TEXT NOT NULL, schema_version TEXT, hash TEXT, revision INTEGER NOT NULL DEFAULT 1, author TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, published_at TEXT, published_by TEXT, based_on TEXT,
  change_reason TEXT, validation TEXT, last_editor TEXT
);
CREATE INDEX IF NOT EXISTS ix_config_kind ON config_versions(kind, scope, status);
CREATE TABLE IF NOT EXISTS case_profile (
  case_id TEXT PRIMARY KEY, requirement_set_version TEXT, pinned_at TEXT, profile TEXT
);
CREATE TABLE IF NOT EXISTS demo_applications (
  case_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, application TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS completion_tasks (
  task_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, requirement_code TEXT NOT NULL, reason_code TEXT NOT NULL,
  status TEXT NOT NULL, issue_key TEXT, document_id TEXT, title_he TEXT, customer_text_he TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, resolved_at TEXT, history TEXT
);
CREATE INDEX IF NOT EXISTS ix_tasks_case ON completion_tasks(case_id, status);
CREATE TABLE IF NOT EXISTS contact_plans (
  case_id TEXT PRIMARY KEY, state TEXT NOT NULL, decision TEXT, next_eligible_at TEXT, policy_version TEXT,
  plan_version INTEGER NOT NULL DEFAULT 0, nudge INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contact_attempts (
  attempt_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, channel TEXT NOT NULL, provider TEXT NOT NULL,
  simulated INTEGER NOT NULL, idempotency_key TEXT UNIQUE, status TEXT NOT NULL, outcome TEXT,
  provider_call_id TEXT, task_ids TEXT, policy_version TEXT, prompt_version TEXT, link_id TEXT, request TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, history TEXT, actor TEXT
);
CREATE INDEX IF NOT EXISTS ix_attempts_case ON contact_attempts(case_id, created_at);
CREATE TABLE IF NOT EXISTS policy_decisions (
  decision_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, action TEXT NOT NULL, blocked_by TEXT, rule_ids TEXT,
  next_eligible_at TEXT, policy_version TEXT, explanation_he TEXT, trigger TEXT, evaluated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_policy_decisions_case ON policy_decisions(case_id, evaluated_at);
CREATE TABLE IF NOT EXISTS customer_presence (
  case_id TEXT NOT NULL, session_id TEXT NOT NULL, state TEXT NOT NULL, last_seen_at TEXT, last_activity_at TEXT,
  last_upload_action_at TEXT, picker_open_until TEXT, ended_at TEXT, seq INTEGER NOT NULL DEFAULT 0, visible INTEGER,
  started_at TEXT, PRIMARY KEY (case_id, session_id)
);
CREATE TABLE IF NOT EXISTS contact_preferences (
  case_id TEXT PRIMARY KEY, consent_voice INTEGER, consent_message INTEGER, opt_out_voice INTEGER NOT NULL DEFAULT 0,
  opt_out_message INTEGER NOT NULL DEFAULT 0, snooze_until TEXT, preferred_channel TEXT, updated_at TEXT, updated_by TEXT
);
CREATE TABLE IF NOT EXISTS provider_events (
  event_id TEXT PRIMARY KEY, provider TEXT NOT NULL, received_at TEXT NOT NULL, attempt_id TEXT, payload TEXT, result TEXT
);
CREATE TABLE IF NOT EXISTS case_events (
  event_id TEXT PRIMARY KEY, type TEXT NOT NULL, case_id TEXT, occurred_at TEXT NOT NULL, actor TEXT,
  correlation_id TEXT, payload TEXT
);
CREATE INDEX IF NOT EXISTS ix_case_events_case ON case_events(case_id, occurred_at);
CREATE TABLE IF NOT EXISTS case_overrides (
  override_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, type TEXT NOT NULL, reason TEXT NOT NULL, actor TEXT NOT NULL,
  created_at TEXT NOT NULL, expires_at TEXT, revoked_at TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS upload_links (
  link_id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, case_id TEXT NOT NULL, task_ids TEXT,
  requirement_code TEXT, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT, attempt_id TEXT,
  demo_token TEXT
);
CREATE TABLE IF NOT EXISTS simulation_runs (
  run_id TEXT PRIMARY KEY, version_id TEXT, created_at TEXT NOT NULL, actor TEXT, results TEXT, passed INTEGER
);
CREATE TABLE IF NOT EXISTS system_flags (
  key TEXT PRIMARY KEY, value TEXT, updated_at TEXT, updated_by TEXT
);
"""
# columns added after a table first shipped; CREATE TABLE IF NOT EXISTS does not add them to an existing file
ADDED_COLUMNS = {"banker_decisions": ["reason_code"], "customer_requests": ["responded_statement_id", "closed_reason"],
                 "upload_intents": ["replaces_document_id"],
                 "customer_presence": ["screen"]}

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        settings.renders_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.db_path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        for table, columns in ADDED_COLUMNS.items():
            have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            for column in columns:
                if column not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        _conn = conn
    return _conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """One atomic write transaction."""
    conn = connect()
    with _lock:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def query(sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
    conn = connect()
    with _lock:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def jdump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def jload(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)
