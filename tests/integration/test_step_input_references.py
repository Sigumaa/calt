from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from calt.daemon import create_app

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
    safety_profile: str = "dev",
) -> str:
    response = await client.post(
        "/api/v1/sessions",
        headers=AUTH_HEADERS,
        json={"goal": "step references", "mode": mode, "safety_profile": safety_profile},
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
async def test_step_output_reference_is_resolved_for_apply_and_field_path(
    client: AsyncClient,
    data_root: Path,
) -> None:
    session_id = await _create_session(client)
    target_path = "notes/c2_reference_from_steps.txt"
    target_content = "c2 reference demo\n"
    plan_payload = {
        "version": 1,
        "title": "step output references",
        "session_goal": "resolve step output references",
        "steps": [
            {
                "id": "step_preview",
                "title": "preview write",
                "tool": "write_file_preview",
                "inputs": {"path": target_path, "content": target_content},
                "timeout_sec": 30,
            },
            {
                "id": "step_apply",
                "title": "apply write",
                "tool": "write_file_apply",
                "inputs": {
                    "path": target_path,
                    "content": target_content,
                    "preview": "${steps.step_preview.output}",
                    "meta": {
                        "trace": [
                            {
                                "preview_path": "${steps.step_preview.output.path}",
                            }
                        ]
                    },
                },
                "timeout_sec": 30,
            },
            {
                "id": "step_read_back",
                "title": "read applied file",
                "tool": "read_file",
                "inputs": {"path": "${steps.step_apply.output.path}"},
                "timeout_sec": 30,
            },
        ],
    }
    await _import_plan(client, session_id, plan_payload)
    await _approve_plan(client, session_id)
    await _approve_step(client, session_id, "step_preview")
    await _approve_step(client, session_id, "step_apply")
    await _approve_step(client, session_id, "step_read_back")

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
    assert apply_payload["output"]["applied"] is True

    read_back_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_read_back/execute",
        headers=AUTH_HEADERS,
    )
    assert read_back_execute.status_code == 200
    read_back_payload = read_back_execute.json()
    assert read_back_payload["status"] == "succeeded"
    assert read_back_payload["output"]["content"] == target_content

    workspace_root = data_root / "sessions" / session_id / "workspace"
    assert (workspace_root / target_path).read_text(encoding="utf-8") == target_content


@pytest.mark.anyio
async def test_step_output_reference_returns_409_when_not_yet_available(
    client: AsyncClient,
) -> None:
    session_id = await _create_session(client)
    plan_payload = {
        "version": 1,
        "title": "step output reference failure",
        "session_goal": "reject unresolved reference",
        "steps": [
            {
                "id": "step_preview",
                "title": "preview write",
                "tool": "write_file_preview",
                "inputs": {"path": "notes/fail.txt", "content": "demo\n"},
                "timeout_sec": 30,
            },
            {
                "id": "step_apply",
                "title": "apply before preview execution",
                "tool": "write_file_apply",
                "inputs": {
                    "path": "notes/fail.txt",
                    "content": "demo\n",
                    "preview": "${steps.step_preview.output}",
                },
                "timeout_sec": 30,
            },
        ],
    }
    await _import_plan(client, session_id, plan_payload)
    await _approve_plan(client, session_id)
    await _approve_step(client, session_id, "step_preview")
    await _approve_step(client, session_id, "step_apply")

    execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_apply/execute",
        headers=AUTH_HEADERS,
    )
    assert execute.status_code == 409
    detail = execute.json()["detail"]
    assert "step input reference could not be resolved" in detail
    assert "${steps.step_preview.output}" in detail
