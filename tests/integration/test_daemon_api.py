from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from calt.daemon import create_app

AUTH_HEADERS = {"Authorization": "Bearer test-token"}
DEFAULT_PLAN_PAYLOAD = {
    "version": 1,
    "title": "integration plan",
    "session_goal": "verify daemon api",
    "steps": [
        {
            "id": "step_001",
            "title": "List files",
            "tool": "list_dir",
            "inputs": {"path": "."},
            "timeout_sec": 30,
        }
    ],
}


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "daemon.sqlite3"


@pytest.fixture
def app(database_path: Path):
    return create_app(database_path)


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _create_session(client: AsyncClient, *, mode: str = "normal") -> str:
    response = await client.post(
        "/api/v1/sessions",
        headers=AUTH_HEADERS,
        json={"goal": "api test", "mode": mode},
    )
    assert response.status_code == 200
    return response.json()["id"]


async def _import_plan(
    client: AsyncClient,
    session_id: str,
    payload: dict[str, object] | None = None,
) -> None:
    response = await client.post(
        f"/api/v1/sessions/{session_id}/plans/import",
        headers=AUTH_HEADERS,
        json=payload or DEFAULT_PLAN_PAYLOAD,
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_create_session_supports_mode_in_request_and_response(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/sessions",
        headers=AUTH_HEADERS,
        json={"goal": "api test", "mode": "dry_run"},
    )
    assert create.status_code == 200
    payload = create.json()
    assert payload["mode"] == "dry_run"

    get_session = await client.get(
        f"/api/v1/sessions/{payload['id']}",
        headers=AUTH_HEADERS,
    )
    assert get_session.status_code == 200
    assert get_session.json()["mode"] == "dry_run"


@pytest.mark.anyio
async def test_execute_step_rejects_before_approval(client: AsyncClient) -> None:
    session_id = await _create_session(client)
    await _import_plan(client, session_id)

    response = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_001/execute",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 409
    assert "required before execution" in response.json()["detail"]


@pytest.mark.anyio
async def test_execute_step_allows_after_plan_and_step_approval(client: AsyncClient) -> None:
    session_id = await _create_session(client)
    await _import_plan(client, session_id)

    approve_plan = await client.post(
        f"/api/v1/sessions/{session_id}/plans/1/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert approve_plan.status_code == 200

    approve_step = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_001/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert approve_step.status_code == 200

    execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_001/execute",
        headers=AUTH_HEADERS,
    )
    assert execute.status_code == 200
    execute_payload = execute.json()
    assert execute_payload["status"] == "succeeded"
    assert isinstance(execute_payload["artifacts"], list)
    assert execute_payload["error"] is None

    session = await client.get(
        f"/api/v1/sessions/{session_id}",
        headers=AUTH_HEADERS,
    )
    assert session.status_code == 200
    assert session.json()["status"] == "succeeded"


@pytest.mark.anyio
async def test_execute_step_rejects_high_risk_without_confirm_and_allows_with_confirm(
    client: AsyncClient,
) -> None:
    session_id = await _create_session(client)
    high_risk_payload = {
        "version": 1,
        "title": "high risk plan",
        "session_goal": "verify high risk confirm",
        "steps": [
            {
                "id": "step_high",
                "title": "high risk execute",
                "tool": "list_dir",
                "risk": "high",
                "inputs": {"path": "."},
                "timeout_sec": 30,
            }
        ],
    }
    await _import_plan(client, session_id, high_risk_payload)

    approve_plan = await client.post(
        f"/api/v1/sessions/{session_id}/plans/1/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert approve_plan.status_code == 200

    approve_step = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_high/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert approve_step.status_code == 200

    rejected = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_high/execute",
        headers=AUTH_HEADERS,
    )
    assert rejected.status_code == 409
    assert "confirm_high_risk=true" in rejected.json()["detail"]

    execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_high/execute",
        headers=AUTH_HEADERS,
        json={"confirm_high_risk": True},
    )
    assert execute.status_code == 200
    assert execute.json()["status"] == "succeeded"


@pytest.mark.anyio
async def test_execute_step_records_events_and_artifacts(client: AsyncClient) -> None:
    session_id = await _create_session(client)
    await _import_plan(client, session_id)

    approve_plan = await client.post(
        f"/api/v1/sessions/{session_id}/plans/1/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert approve_plan.status_code == 200

    approve_step = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_001/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert approve_step.status_code == 200

    execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_001/execute",
        headers=AUTH_HEADERS,
    )
    assert execute.status_code == 200

    events = await client.get(
        f"/api/v1/sessions/{session_id}/events/search",
        headers=AUTH_HEADERS,
        params={"q": "step_executed"},
    )
    assert events.status_code == 200
    event_items = events.json()["items"]
    assert any(item["event_type"] == "step_executed" for item in event_items)

    artifacts = await client.get(
        f"/api/v1/sessions/{session_id}/artifacts",
        headers=AUTH_HEADERS,
    )
    assert artifacts.status_code == 200
    artifact_items = artifacts.json()["items"]
    assert len(artifact_items) == 1
    assert artifact_items[0]["path"].startswith(f"data/sessions/{session_id}/artifacts/")


@pytest.mark.anyio
async def test_search_events_includes_event_type_in_like_fallback(
    client: AsyncClient,
    database_path: Path,
) -> None:
    session_id = await _create_session(client)
    await _import_plan(client, session_id)

    approve_plan = await client.post(
        f"/api/v1/sessions/{session_id}/plans/1/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert approve_plan.status_code == 200

    approve_step = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_001/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "user_1", "source": "integration"},
    )
    assert approve_step.status_code == 200

    execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/step_001/execute",
        headers=AUTH_HEADERS,
    )
    assert execute.status_code == 200

    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE events_fts")
        connection.commit()

    events = await client.get(
        f"/api/v1/sessions/{session_id}/events/search",
        headers=AUTH_HEADERS,
        params={"q": "step_executed"},
    )
    assert events.status_code == 200
    event_items = events.json()["items"]
    assert any(item["event_type"] == "step_executed" for item in event_items)


@pytest.mark.anyio
async def test_stop_session_sets_cancelled_status(client: AsyncClient) -> None:
    session_id = await _create_session(client)

    stop = await client.post(
        f"/api/v1/sessions/{session_id}/stop",
        headers=AUTH_HEADERS,
    )
    assert stop.status_code == 200
    assert stop.json()["status"] == "cancelled"

    session = await client.get(
        f"/api/v1/sessions/{session_id}",
        headers=AUTH_HEADERS,
    )
    assert session.status_code == 200
    assert session.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_tools_endpoints_return_default_registry(client: AsyncClient) -> None:
    tools = await client.get("/api/v1/tools", headers=AUTH_HEADERS)
    assert tools.status_code == 200
    tool_names = {item["tool_name"] for item in tools.json()["items"]}
    assert "read_file" in tool_names
    assert "run_shell_readonly" in tool_names

    permissions = await client.get(
        "/api/v1/tools/read_file/permissions",
        headers=AUTH_HEADERS,
    )
    assert permissions.status_code == 200
    payload = permissions.json()
    assert payload["tool_name"] == "read_file"
    assert payload["permission_profile"] == "workspace_read"


@pytest.mark.anyio
async def test_import_and_get_plan_and_event_search(client: AsyncClient) -> None:
    session_id = await _create_session(client)
    await _import_plan(client, session_id)

    plan = await client.get(
        f"/api/v1/sessions/{session_id}/plans/1",
        headers=AUTH_HEADERS,
    )
    assert plan.status_code == 200
    plan_payload = plan.json()
    assert plan_payload["version"] == 1
    assert plan_payload["steps"][0]["id"] == "step_001"
    assert plan_payload["steps"][0]["timeout_sec"] == 30

    events = await client.get(
        f"/api/v1/sessions/{session_id}/events/search",
        headers=AUTH_HEADERS,
        params={"q": "imported"},
    )
    assert events.status_code == 200
    assert isinstance(events.json()["items"], list)

    artifacts = await client.get(
        f"/api/v1/sessions/{session_id}/artifacts",
        headers=AUTH_HEADERS,
    )
    assert artifacts.status_code == 200
    assert artifacts.json()["items"] == []
