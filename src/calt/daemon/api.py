from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from calt.core import Run, Session, WorkflowStatus, transition_run
from calt.storage import connect_sqlite, initialize_storage

DEFAULT_TOOLS: tuple[tuple[str, str, str], ...] = (
    ("read_file", "workspace_read", "Read a file from session workspace."),
    ("list_dir", "workspace_read", "List files in session workspace."),
    ("run_shell_readonly", "shell_readonly", "Run allowlisted readonly shell commands."),
    ("write_file_preview", "workspace_write_preview", "Preview file write."),
    ("write_file_apply", "workspace_write_apply", "Apply file write."),
    ("apply_patch", "workspace_patch", "Apply patch in preview/apply mode."),
)


class CreateSessionRequest(BaseModel):
    goal: str | None = None


class PlanStepInput(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    tool: str = Field(min_length=1)


class PlanImportRequest(BaseModel):
    version: int = Field(default=1, ge=1)
    title: str = Field(default="Imported plan", min_length=1)
    session_goal: str | None = None
    steps: list[PlanStepInput] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    approved_by: str = "system"
    source: str = "api"


def _require_bearer_token(
    authorization: str | None = Header(default=None),
) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authorization header with bearer token is required",
        )
    token = authorization.split(" ", maxsplit=1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authorization header with bearer token is required",
        )
    return token


def _ensure_default_tools(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT INTO tool_registry (tool_name, permission_profile, description, enabled)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(tool_name) DO NOTHING
        """,
        DEFAULT_TOOLS,
    )


def _fetch_session_or_404(
    connection: sqlite3.Connection,
    session_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT id, goal, status, created_at, updated_at
        FROM sessions
        WHERE id = ?
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found",
        )
    return row


def _fetch_plan_or_404(
    connection: sqlite3.Connection,
    session_id: str,
    version: int,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT id, session_id, version, title
        FROM plans
        WHERE session_id = ? AND version = ?
        """,
        (session_id, version),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="plan not found",
        )
    return row


def _fetch_step_or_404(
    connection: sqlite3.Connection,
    session_id: str,
    step_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT
            s.id,
            s.step_key,
            s.title,
            s.tool_name,
            s.status,
            p.id AS plan_id,
            p.version AS plan_version
        FROM steps AS s
        INNER JOIN plans AS p ON p.id = s.plan_id
        WHERE p.session_id = ? AND s.step_key = ?
        """,
        (session_id, step_id),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="step not found",
        )
    return row


def _insert_event(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    event_type: str,
    summary: str,
    payload_text: str = "",
    run_id: int | None = None,
    source: str = "daemon",
    user_id: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO events (session_id, run_id, event_type, summary, payload_text, source, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, run_id, event_type, summary, payload_text, source, user_id),
    )


def _serialize_step_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["step_key"],
        "title": row["title"],
        "tool": row["tool_name"],
        "status": row["status"],
    }


def create_app(database: str | Path) -> FastAPI:
    database_path = str(database)
    bootstrap_connection = connect_sqlite(database_path)
    try:
        initialize_storage(bootstrap_connection)
        _ensure_default_tools(bootstrap_connection)
        bootstrap_connection.commit()
    finally:
        bootstrap_connection.close()

    app = FastAPI(title="calt-daemon")

    @app.post("/api/v1/sessions")
    def create_session(
        payload: CreateSessionRequest,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        session = Session(goal=payload.goal)
        connection = connect_sqlite(database_path)
        try:
            connection.execute(
                """
                INSERT INTO sessions (id, goal, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.goal or "",
                    session.status.value,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
            _insert_event(
                connection,
                session_id=session.id,
                event_type="session_created",
                summary="session created",
            )
            connection.commit()
        finally:
            connection.close()

        return {
            "id": session.id,
            "goal": session.goal,
            "status": session.status.value,
            "plan_version": session.plan_version,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }

    @app.get("/api/v1/sessions/{session_id}")
    def get_session(
        session_id: str,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            row = _fetch_session_or_404(connection, session_id)
            version_row = connection.execute(
                """
                SELECT MAX(version) AS current_plan_version
                FROM plans
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        finally:
            connection.close()

        return {
            "id": row["id"],
            "goal": row["goal"] or None,
            "status": row["status"],
            "plan_version": version_row["current_plan_version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @app.post("/api/v1/sessions/{session_id}/plans/import")
    def import_plan(
        session_id: str,
        payload: PlanImportRequest,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            _fetch_session_or_404(connection, session_id)
            connection.execute(
                """
                INSERT INTO plans (session_id, version, title, raw_yaml)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, version) DO UPDATE SET
                    title = excluded.title,
                    raw_yaml = excluded.raw_yaml
                """,
                (
                    session_id,
                    payload.version,
                    payload.title,
                    json.dumps(payload.model_dump(), ensure_ascii=True),
                ),
            )
            plan_row = _fetch_plan_or_404(connection, session_id, payload.version)
            connection.execute(
                "DELETE FROM steps WHERE plan_id = ?",
                (plan_row["id"],),
            )

            for step in payload.steps:
                connection.execute(
                    """
                    INSERT INTO steps (plan_id, step_key, title, tool_name, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        plan_row["id"],
                        step.id,
                        step.title,
                        step.tool,
                        WorkflowStatus.pending.value,
                    ),
                )

            if payload.session_goal is None:
                connection.execute(
                    """
                    UPDATE sessions
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (WorkflowStatus.awaiting_plan_approval.value, session_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE sessions
                    SET goal = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        payload.session_goal,
                        WorkflowStatus.awaiting_plan_approval.value,
                        session_id,
                    ),
                )

            _insert_event(
                connection,
                session_id=session_id,
                event_type="plan_imported",
                summary=f"plan v{payload.version} imported",
                payload_text=payload.title,
            )
            connection.commit()
        finally:
            connection.close()

        return {
            "session_id": session_id,
            "version": payload.version,
            "title": payload.title,
            "steps": [
                {
                    "id": step.id,
                    "title": step.title,
                    "tool": step.tool,
                    "status": WorkflowStatus.pending.value,
                }
                for step in payload.steps
            ],
        }

    @app.get("/api/v1/sessions/{session_id}/plans/{version}")
    def get_plan(
        session_id: str,
        version: int,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            _fetch_session_or_404(connection, session_id)
            plan_row = _fetch_plan_or_404(connection, session_id, version)
            step_rows = connection.execute(
                """
                SELECT step_key, title, tool_name, status
                FROM steps
                WHERE plan_id = ?
                ORDER BY id
                """,
                (plan_row["id"],),
            ).fetchall()
        finally:
            connection.close()

        return {
            "session_id": session_id,
            "version": plan_row["version"],
            "title": plan_row["title"],
            "steps": [_serialize_step_row(row) for row in step_rows],
        }

    @app.post("/api/v1/sessions/{session_id}/plans/{version}/approve")
    def approve_plan(
        session_id: str,
        version: int,
        payload: ApprovalRequest,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            _fetch_session_or_404(connection, session_id)
            plan_row = _fetch_plan_or_404(connection, session_id, version)
            connection.execute(
                """
                INSERT INTO approvals (session_id, plan_id, approval_type, approved, source, user_id)
                VALUES (?, ?, 'plan', 1, ?, ?)
                """,
                (session_id, plan_row["id"], payload.source, payload.approved_by),
            )
            connection.execute(
                """
                UPDATE sessions
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (WorkflowStatus.awaiting_step_approval.value, session_id),
            )
            _insert_event(
                connection,
                session_id=session_id,
                event_type="plan_approved",
                summary=f"plan v{version} approved",
                source=payload.source,
                user_id=payload.approved_by,
            )
            connection.commit()
        finally:
            connection.close()

        return {
            "session_id": session_id,
            "version": version,
            "approved": True,
        }

    @app.post("/api/v1/sessions/{session_id}/steps/{step_id}/approve")
    def approve_step(
        session_id: str,
        step_id: str,
        payload: ApprovalRequest,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            _fetch_session_or_404(connection, session_id)
            step_row = _fetch_step_or_404(connection, session_id, step_id)
            connection.execute(
                """
                INSERT INTO approvals (
                    session_id,
                    plan_id,
                    step_id,
                    approval_type,
                    approved,
                    source,
                    user_id
                )
                VALUES (?, ?, ?, 'step', 1, ?, ?)
                """,
                (
                    session_id,
                    step_row["plan_id"],
                    step_row["id"],
                    payload.source,
                    payload.approved_by,
                ),
            )
            connection.execute(
                """
                UPDATE steps
                SET status = ?
                WHERE id = ?
                """,
                (WorkflowStatus.awaiting_step_approval.value, step_row["id"]),
            )
            _insert_event(
                connection,
                session_id=session_id,
                event_type="step_approved",
                summary=f"step {step_id} approved",
                source=payload.source,
                user_id=payload.approved_by,
            )
            connection.commit()
        finally:
            connection.close()

        return {
            "session_id": session_id,
            "step_id": step_id,
            "approved": True,
        }

    @app.post("/api/v1/sessions/{session_id}/steps/{step_id}/execute")
    def execute_step(
        session_id: str,
        step_id: str,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            _fetch_session_or_404(connection, session_id)
            step_row = _fetch_step_or_404(connection, session_id, step_id)

            plan_approved = connection.execute(
                """
                SELECT 1
                FROM approvals
                WHERE session_id = ?
                  AND plan_id = ?
                  AND approval_type = 'plan'
                  AND approved = 1
                LIMIT 1
                """,
                (session_id, step_row["plan_id"]),
            ).fetchone()
            step_approved = connection.execute(
                """
                SELECT 1
                FROM approvals
                WHERE session_id = ?
                  AND step_id = ?
                  AND approval_type = 'step'
                  AND approved = 1
                LIMIT 1
                """,
                (session_id, step_row["id"]),
            ).fetchone()

            if plan_approved is None or step_approved is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="plan and step approvals are required before execution",
                )

            run = Run(
                session_id=session_id,
                plan_version=step_row["plan_version"],
                step_id=step_id,
            )
            transition_run(run, WorkflowStatus.awaiting_plan_approval)
            transition_run(run, WorkflowStatus.awaiting_step_approval)
            transition_run(run, WorkflowStatus.running)
            transition_run(run, WorkflowStatus.succeeded)

            run_cursor = connection.execute(
                """
                INSERT INTO runs (
                    session_id,
                    plan_id,
                    step_id,
                    tool_name,
                    status,
                    duration_ms,
                    failure_reason,
                    started_at,
                    finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    step_row["plan_id"],
                    step_row["id"],
                    step_row["tool_name"],
                    run.status.value,
                    0,
                    run.failure_reason,
                    run.started_at.isoformat() if run.started_at else None,
                    run.finished_at.isoformat() if run.finished_at else None,
                ),
            )
            run_id = run_cursor.lastrowid

            connection.execute(
                """
                UPDATE steps
                SET status = ?
                WHERE id = ?
                """,
                (WorkflowStatus.succeeded.value, step_row["id"]),
            )

            remaining_steps_row = connection.execute(
                """
                SELECT COUNT(*) AS remaining_count
                FROM steps
                WHERE plan_id = ?
                  AND status != ?
                """,
                (step_row["plan_id"], WorkflowStatus.succeeded.value),
            ).fetchone()
            all_steps_succeeded = remaining_steps_row["remaining_count"] == 0
            session_status = (
                WorkflowStatus.succeeded
                if all_steps_succeeded
                else WorkflowStatus.awaiting_step_approval
            )
            connection.execute(
                """
                UPDATE sessions
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (session_status.value, session_id),
            )

            _insert_event(
                connection,
                session_id=session_id,
                run_id=run_id,
                event_type="step_executed",
                summary=f"step {step_id} executed",
                payload_text=step_row["tool_name"],
            )
            connection.commit()
        finally:
            connection.close()

        return {
            "session_id": session_id,
            "step_id": step_id,
            "status": WorkflowStatus.succeeded.value,
            "run_id": run_id,
        }

    @app.post("/api/v1/sessions/{session_id}/stop")
    def stop_session(
        session_id: str,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            _fetch_session_or_404(connection, session_id)
            connection.execute(
                """
                UPDATE sessions
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (WorkflowStatus.cancelled.value, session_id),
            )
            _insert_event(
                connection,
                session_id=session_id,
                event_type="session_stopped",
                summary="session stopped",
            )
            connection.commit()
        finally:
            connection.close()

        return {
            "session_id": session_id,
            "status": WorkflowStatus.cancelled.value,
        }

    @app.get("/api/v1/sessions/{session_id}/events/search")
    def search_events(
        session_id: str,
        q: str | None = None,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            _fetch_session_or_404(connection, session_id)
            if q:
                try:
                    rows = connection.execute(
                        """
                        SELECT
                            e.id,
                            e.event_type,
                            e.summary,
                            e.payload_text,
                            e.source,
                            e.user_id,
                            e.created_at
                        FROM events AS e
                        INNER JOIN events_fts ON events_fts.rowid = e.id
                        WHERE e.session_id = ?
                          AND events_fts MATCH ?
                        ORDER BY e.id DESC
                        """,
                        (session_id, q),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            else:
                rows = connection.execute(
                    """
                    SELECT id, event_type, summary, payload_text, source, user_id, created_at
                    FROM events
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT 100
                    """,
                    (session_id,),
                ).fetchall()
        finally:
            connection.close()

        return {
            "items": [
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "summary": row["summary"],
                    "payload_text": row["payload_text"],
                    "source": row["source"],
                    "user_id": row["user_id"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        }

    @app.get("/api/v1/sessions/{session_id}/artifacts")
    def list_artifacts(
        session_id: str,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            _fetch_session_or_404(connection, session_id)
            rows = connection.execute(
                """
                SELECT id, run_id, step_id, kind, path, sha256, created_at
                FROM artifacts
                WHERE session_id = ?
                ORDER BY id DESC
                """,
                (session_id,),
            ).fetchall()
        finally:
            connection.close()

        return {
            "items": [
                {
                    "id": row["id"],
                    "run_id": row["run_id"],
                    "step_id": row["step_id"],
                    "kind": row["kind"],
                    "path": row["path"],
                    "sha256": row["sha256"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        }

    @app.get("/api/v1/tools")
    def list_tools(_: str = Depends(_require_bearer_token)) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            _ensure_default_tools(connection)
            rows = connection.execute(
                """
                SELECT tool_name, permission_profile, description, enabled
                FROM tool_registry
                ORDER BY tool_name
                """
            ).fetchall()
            connection.commit()
        finally:
            connection.close()

        return {
            "items": [
                {
                    "tool_name": row["tool_name"],
                    "permission_profile": row["permission_profile"],
                    "description": row["description"],
                    "enabled": bool(row["enabled"]),
                }
                for row in rows
            ]
        }

    @app.get("/api/v1/tools/{tool_name}/permissions")
    def get_tool_permissions(
        tool_name: str,
        _: str = Depends(_require_bearer_token),
    ) -> dict[str, Any]:
        connection = connect_sqlite(database_path)
        try:
            row = connection.execute(
                """
                SELECT tool_name, permission_profile, description, enabled
                FROM tool_registry
                WHERE tool_name = ?
                """,
                (tool_name,),
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return {
                "tool_name": tool_name,
                "permission_profile": "unknown",
                "description": "",
                "enabled": False,
            }
        return {
            "tool_name": row["tool_name"],
            "permission_profile": row["permission_profile"],
            "description": row["description"],
            "enabled": bool(row["enabled"]),
        }

    return app
