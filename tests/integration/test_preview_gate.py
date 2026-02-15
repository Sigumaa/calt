from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from calt.daemon import create_app
from calt.tools import apply_patch, write_file_preview

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "daemon.sqlite3"


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def app(database_path: Path, data_root: Path):
    return create_app(database_path, data_root=data_root)


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _create_session(
    client: AsyncClient,
    *,
    mode: str = "normal",
    safety_profile: str = "strict",
) -> str:
    response = await client.post(
        "/api/v1/sessions",
        headers=AUTH_HEADERS,
        json={"goal": "preview gate", "mode": mode, "safety_profile": safety_profile},
    )
    assert response.status_code == 200
    return response.json()["id"]


async def _import_plan(client: AsyncClient, session_id: str, payload: dict[str, object]) -> None:
    response = await client.post(
        f"/api/v1/sessions/{session_id}/plans/import",
        headers=AUTH_HEADERS,
        json=payload,
    )
    assert response.status_code == 200


async def _approve_plan(client: AsyncClient, session_id: str, version: int = 1) -> None:
    response = await client.post(
        f"/api/v1/sessions/{session_id}/plans/{version}/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert response.status_code == 200


async def _approve_step(client: AsyncClient, session_id: str, step_id: str) -> None:
    response = await client.post(
        f"/api/v1/sessions/{session_id}/steps/{step_id}/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_write_apply_without_preview_is_rejected_and_recorded(
    client: AsyncClient,
    database_path: Path,
) -> None:
    session_id = await _create_session(client)
    plan_payload = {
        "version": 1,
        "title": "preview gate reject",
        "session_goal": "reject apply without preview",
        "steps": [
            {
                "id": "step_apply",
                "title": "apply without preview",
                "tool": "write_file_apply",
                "inputs": {"path": "memo.txt", "content": "after\n"},
                "timeout_sec": 30,
            }
        ],
    }
    await _import_plan(client, session_id, plan_payload)
    await _approve_plan(client, session_id)
    await _approve_step(client, session_id, "step_apply")

    execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_apply/execute",
        headers=AUTH_HEADERS,
    )
    assert execute.status_code == 200
    execute_payload = execute.json()
    assert execute_payload["status"] == "failed"
    assert "preview gate rejected" in (execute_payload["error"] or "")

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        run_row = connection.execute(
            """
            SELECT status, failure_reason
            FROM runs
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        assert run_row is not None
        assert run_row["status"] == "failed"
        assert "preview gate rejected" in (run_row["failure_reason"] or "")

        event_row = connection.execute(
            """
            SELECT event_type, payload_text
            FROM events
            WHERE session_id = ? AND run_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id, execute_payload["run_id"]),
        ).fetchone()
        assert event_row is not None
        assert event_row["event_type"] == "step_failed"
        assert "preview gate rejected" in (event_row["payload_text"] or "")
    finally:
        connection.close()


@pytest.mark.anyio
async def test_dev_profile_skips_preview_gate_for_write_apply_without_preview(
    client: AsyncClient,
) -> None:
    session_id = await _create_session(client, safety_profile="dev")
    plan_payload = {
        "version": 1,
        "title": "dev profile no preview gate",
        "session_goal": "skip preview gate in dev profile",
        "steps": [
            {
                "id": "step_apply",
                "title": "apply without preview",
                "tool": "write_file_apply",
                "inputs": {"path": "memo.txt", "content": "after\n"},
                "timeout_sec": 30,
            }
        ],
    }
    await _import_plan(client, session_id, plan_payload)
    await _approve_plan(client, session_id)
    await _approve_step(client, session_id, "step_apply")

    execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_apply/execute",
        headers=AUTH_HEADERS,
    )
    assert execute.status_code == 200
    payload = execute.json()
    assert payload["status"] == "failed"
    assert "preview gate rejected" not in (payload["error"] or "")
    assert "preview is required for write_file_apply" in (payload["error"] or "")


@pytest.mark.anyio
async def test_write_apply_succeeds_after_preview_record(
    client: AsyncClient,
    database_path: Path,
    data_root: Path,
) -> None:
    session_id = await _create_session(client)
    workspace_root = data_root / "sessions" / session_id / "workspace"
    expected_preview = write_file_preview(workspace_root, "memo.txt", "after\n")

    plan_payload = {
        "version": 1,
        "title": "preview gate allow",
        "session_goal": "allow apply with preview",
        "steps": [
            {
                "id": "step_preview",
                "title": "preview write",
                "tool": "write_file_preview",
                "inputs": {"path": "memo.txt", "content": "after\n"},
                "timeout_sec": 30,
            },
            {
                "id": "step_apply",
                "title": "apply write",
                "tool": "write_file_apply",
                "inputs": {
                    "path": "memo.txt",
                    "content": "after\n",
                    "preview": expected_preview,
                },
                "timeout_sec": 30,
            },
        ],
    }
    await _import_plan(client, session_id, plan_payload)
    await _approve_plan(client, session_id)
    await _approve_step(client, session_id, "step_preview")
    await _approve_step(client, session_id, "step_apply")

    preview_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_preview/execute",
        headers=AUTH_HEADERS,
    )
    assert preview_execute.status_code == 200
    assert preview_execute.json()["status"] == "succeeded"

    apply_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_apply/execute",
        headers=AUTH_HEADERS,
    )
    assert apply_execute.status_code == 200
    apply_payload = apply_execute.json()
    assert apply_payload["status"] == "succeeded"
    assert apply_payload["error"] is None
    assert apply_payload["output"]["applied"] is True
    assert (workspace_root / "memo.txt").read_text(encoding="utf-8") == "after\n"

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        run_rows = connection.execute(
            """
            SELECT status
            FROM runs
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()
        assert [row["status"] for row in run_rows] == ["succeeded", "succeeded"]
    finally:
        connection.close()


@pytest.mark.anyio
async def test_dry_run_allows_preview_and_rejects_write_apply(
    client: AsyncClient,
    data_root: Path,
) -> None:
    session_id = await _create_session(client, mode="dry_run")
    workspace_root = data_root / "sessions" / session_id / "workspace"
    expected_preview = write_file_preview(workspace_root, "memo.txt", "after\n")
    plan_payload = {
        "version": 1,
        "title": "dry run write apply guard",
        "session_goal": "dry run blocks write apply",
        "steps": [
            {
                "id": "step_preview",
                "title": "preview write",
                "tool": "write_file_preview",
                "inputs": {"path": "memo.txt", "content": "after\n"},
                "timeout_sec": 30,
            },
            {
                "id": "step_apply",
                "title": "apply write",
                "tool": "write_file_apply",
                "inputs": {
                    "path": "memo.txt",
                    "content": "after\n",
                    "preview": expected_preview,
                },
                "timeout_sec": 30,
            },
        ],
    }
    await _import_plan(client, session_id, plan_payload)
    await _approve_plan(client, session_id)
    await _approve_step(client, session_id, "step_preview")
    await _approve_step(client, session_id, "step_apply")

    preview_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_preview/execute",
        headers=AUTH_HEADERS,
    )
    assert preview_execute.status_code == 200
    assert preview_execute.json()["status"] == "succeeded"

    apply_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_apply/execute",
        headers=AUTH_HEADERS,
    )
    assert apply_execute.status_code == 409
    assert "dry_run" in apply_execute.json()["detail"]


@pytest.mark.anyio
async def test_dry_run_allows_patch_preview_and_rejects_patch_apply(
    client: AsyncClient,
    data_root: Path,
) -> None:
    session_id = await _create_session(client, mode="dry_run")
    workspace_root = data_root / "sessions" / session_id / "workspace"
    target = workspace_root / "patch_target.txt"
    target.write_text("before\n", encoding="utf-8")
    patch = """--- a/patch_target.txt
+++ b/patch_target.txt
@@ -1 +1 @@
-before
+after
"""
    expected_preview = apply_patch(workspace_root, patch, mode="preview")
    plan_payload = {
        "version": 1,
        "title": "dry run patch apply guard",
        "session_goal": "dry run blocks patch apply",
        "steps": [
            {
                "id": "step_patch_preview",
                "title": "preview patch",
                "tool": "apply_patch",
                "inputs": {"patch": patch, "mode": "preview"},
                "timeout_sec": 30,
            },
            {
                "id": "step_patch_apply",
                "title": "apply patch",
                "tool": "apply_patch",
                "inputs": {"patch": patch, "mode": "apply", "preview": expected_preview},
                "timeout_sec": 30,
            },
        ],
    }
    await _import_plan(client, session_id, plan_payload)
    await _approve_plan(client, session_id)
    await _approve_step(client, session_id, "step_patch_preview")
    await _approve_step(client, session_id, "step_patch_apply")

    preview_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_patch_preview/execute",
        headers=AUTH_HEADERS,
    )
    assert preview_execute.status_code == 200
    assert preview_execute.json()["status"] == "succeeded"

    apply_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_patch_apply/execute",
        headers=AUTH_HEADERS,
    )
    assert apply_execute.status_code == 409
    assert "dry_run" in apply_execute.json()["detail"]
