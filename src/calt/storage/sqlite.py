from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final

SCHEMA_SQL: Final[str] = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    raw_yaml TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, version)
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    step_key TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    risk TEXT NOT NULL DEFAULT 'low',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(plan_id, step_key)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id INTEGER REFERENCES plans(id) ON DELETE SET NULL,
    step_id INTEGER REFERENCES steps(id) ON DELETE SET NULL,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    failure_reason TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    run_id INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_text TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'daemon',
    user_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    run_id INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    step_id INTEGER REFERENCES steps(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id INTEGER REFERENCES plans(id) ON DELETE SET NULL,
    step_id INTEGER REFERENCES steps(id) ON DELETE SET NULL,
    approval_type TEXT NOT NULL CHECK (approval_type IN ('plan', 'step')),
    approved INTEGER NOT NULL CHECK (approved IN (0, 1)),
    source TEXT NOT NULL,
    user_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_registry (
    tool_name TEXT PRIMARY KEY,
    permission_profile TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plans_session_id ON plans(session_id);
CREATE INDEX IF NOT EXISTS idx_steps_plan_id ON steps(plan_id);
CREATE INDEX IF NOT EXISTS idx_runs_session_id ON runs(session_id);
CREATE INDEX IF NOT EXISTS idx_runs_step_id ON runs(step_id);
CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_session_id ON artifacts(session_id);
CREATE INDEX IF NOT EXISTS idx_approvals_session_id ON approvals(session_id);

CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    summary,
    payload_text,
    content = 'events',
    content_rowid = 'id'
);

CREATE TRIGGER IF NOT EXISTS trg_events_fts_insert
AFTER INSERT ON events
BEGIN
    INSERT INTO events_fts(rowid, summary, payload_text)
    VALUES (NEW.id, NEW.summary, NEW.payload_text);
END;

CREATE TRIGGER IF NOT EXISTS trg_events_append_only_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_events_append_only_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events is append-only');
END;

CREATE VIEW IF NOT EXISTS v_run_success_rate_by_tool AS
SELECT
    tool_name,
    COUNT(*) AS run_count,
    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS succeeded_count,
    CAST(SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS REAL) / NULLIF(COUNT(*), 0) AS success_rate
FROM runs
GROUP BY tool_name;

CREATE VIEW IF NOT EXISTS v_step_duration_ms_p50_p95 AS
WITH ordered AS (
    SELECT
        step_id,
        duration_ms,
        ROW_NUMBER() OVER (PARTITION BY step_id ORDER BY duration_ms) AS rn,
        COUNT(*) OVER (PARTITION BY step_id) AS cnt
    FROM runs
    WHERE duration_ms IS NOT NULL
),
percentiles AS (
    SELECT
        step_id,
        MAX(
            CASE
                WHEN rn = CAST(((cnt - 1) * 0.50) AS INTEGER) + 1 THEN duration_ms
            END
        ) AS duration_ms_p50,
        MAX(
            CASE
                WHEN rn = CAST(((cnt - 1) * 0.95) AS INTEGER) + 1 THEN duration_ms
            END
        ) AS duration_ms_p95
    FROM ordered
    GROUP BY step_id
)
SELECT
    step_id,
    duration_ms_p50,
    duration_ms_p95
FROM percentiles;

CREATE VIEW IF NOT EXISTS v_session_failure_reasons AS
SELECT
    session_id,
    COALESCE(failure_reason, 'unknown') AS failure_reason,
    COUNT(*) AS failure_count
FROM runs
WHERE status = 'failed'
GROUP BY session_id, COALESCE(failure_reason, 'unknown');
"""


def connect_sqlite(database: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA busy_timeout = 5000;")
    return connection


def initialize_storage(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)


def init_sqlite(database: str | Path) -> sqlite3.Connection:
    connection = connect_sqlite(database)
    initialize_storage(connection)
    return connection
