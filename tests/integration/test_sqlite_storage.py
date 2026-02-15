from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from calt.storage import connect_sqlite, initialize_storage

REQUIRED_TABLES = {
    "sessions",
    "plans",
    "steps",
    "runs",
    "events",
    "artifacts",
    "approvals",
    "tool_registry",
    "events_fts",
}

REQUIRED_VIEWS = {
    "v_run_success_rate_by_tool",
    "v_step_duration_ms_p50_p95",
    "v_session_failure_reasons",
}


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = connect_sqlite(":memory:")
    initialize_storage(connection)
    yield connection
    connection.close()


def _exists(conn: sqlite3.Connection, *, name: str, object_type: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
        (object_type, name),
    ).fetchone()
    return row is not None


def _insert_session(conn: sqlite3.Connection, session_id: str = "sess_1") -> None:
    conn.execute(
        "INSERT INTO sessions (id, goal, status) VALUES (?, ?, ?)",
        (session_id, "integration test", "pending"),
    )


def test_initialize_storage_creates_required_tables(conn: sqlite3.Connection) -> None:
    initialize_storage(conn)
    for table_name in REQUIRED_TABLES:
        assert _exists(conn, name=table_name, object_type="table")


def test_initialize_storage_creates_required_views(conn: sqlite3.Connection) -> None:
    for view_name in REQUIRED_VIEWS:
        assert _exists(conn, name=view_name, object_type="view")


def test_events_fts_search_hits_inserted_event(conn: sqlite3.Connection) -> None:
    _insert_session(conn)
    conn.execute(
        """
        INSERT INTO events (session_id, event_type, summary, payload_text)
        VALUES (?, ?, ?, ?)
        """,
        ("sess_1", "tool_result", "step execute success", "preview apply completed"),
    )

    rows = conn.execute(
        "SELECT rowid FROM events_fts WHERE events_fts MATCH ?",
        ("completed",),
    ).fetchall()

    assert len(rows) == 1
    assert rows[0]["rowid"] == 1


def test_events_table_is_append_only(conn: sqlite3.Connection) -> None:
    _insert_session(conn)
    conn.execute(
        """
        INSERT INTO events (session_id, event_type, summary, payload_text)
        VALUES (?, ?, ?, ?)
        """,
        ("sess_1", "plan_approved", "approved", "payload"),
    )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE events SET summary = ? WHERE id = 1", ("updated",))

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM events WHERE id = 1")


def test_connect_sqlite_creates_parent_directory_when_missing(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "storage" / "daemon.sqlite3"
    assert not database_path.parent.exists()

    connection = connect_sqlite(database_path)
    try:
        assert database_path.parent.exists()
        assert database_path.exists()
    finally:
        connection.close()


def test_initialize_storage_adds_mode_column_for_legacy_sessions_table() -> None:
    connection = connect_sqlite(":memory:")
    try:
        connection.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        initialize_storage(connection)
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
        }
        assert "mode" in columns
    finally:
        connection.close()
