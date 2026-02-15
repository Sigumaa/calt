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


async def _create_session(client: AsyncClient, *, goal: str) -> str:
    response = await client.post(
        "/api/v1/sessions",
        headers=AUTH_HEADERS,
        json={"goal": goal},
    )
    assert response.status_code == 200
    return response.json()["id"]


async def _import_plan(
    client: AsyncClient,
    *,
    session_id: str,
    version: int,
    title: str,
    session_goal: str,
    steps: list[dict[str, object]],
) -> None:
    response = await client.post(
        f"/api/v1/sessions/{session_id}/plans/import",
        headers=AUTH_HEADERS,
        json={
            "version": version,
            "title": title,
            "session_goal": session_goal,
            "steps": steps,
        },
    )
    assert response.status_code == 200


async def _approve_plan(client: AsyncClient, *, session_id: str, version: int) -> None:
    response = await client.post(
        f"/api/v1/sessions/{session_id}/plans/{version}/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "e2e-user", "source": "e2e"},
    )
    assert response.status_code == 200


async def _approve_step(client: AsyncClient, *, session_id: str, step_id: str) -> None:
    response = await client.post(
        f"/api/v1/sessions/{session_id}/steps/{step_id}/approve",
        headers=AUTH_HEADERS,
        json={"approved_by": "e2e-user", "source": "e2e"},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_e2e_success_flow_executes_all_steps_and_records_outputs(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    session_id = await _create_session(client, goal="e2e success")
    steps = [
        {
            "id": "step_list",
            "title": "List workspace",
            "tool": "list_dir",
            "inputs": {"path": "."},
            "timeout_sec": 30,
        },
        {
            "id": "step_shell",
            "title": "Run readonly shell",
            "tool": "run_shell_readonly",
            "inputs": {"command": "ls"},
            "timeout_sec": 30,
        },
    ]
    await _import_plan(
        client,
        session_id=session_id,
        version=1,
        title="e2e success flow",
        session_goal="validate successful end-to-end flow",
        steps=steps,
    )
    await _approve_plan(client, session_id=session_id, version=1)

    for step_id in ("step_list", "step_shell"):
        await _approve_step(client, session_id=session_id, step_id=step_id)
        execute = await client.post(
            f"/api/v1/sessions/{session_id}/steps/{step_id}/execute",
            headers=AUTH_HEADERS,
        )
        assert execute.status_code == 200
        execute_payload = execute.json()
        assert execute_payload["status"] == "succeeded"
        assert execute_payload["error"] is None

    session = await client.get(
        f"/api/v1/sessions/{session_id}",
        headers=AUTH_HEADERS,
    )
    assert session.status_code == 200
    session_payload = session.json()
    assert session_payload["status"] == "succeeded"
    assert session_payload["needs_replan"] is False

    events = await client.get(
        f"/api/v1/sessions/{session_id}/events/search",
        headers=AUTH_HEADERS,
    )
    assert events.status_code == 200
    event_items = events.json()["items"]
    assert any(item["event_type"] == "plan_approved" for item in event_items)
    assert len([item for item in event_items if item["event_type"] == "step_executed"]) == 2

    artifacts = await client.get(
        f"/api/v1/sessions/{session_id}/artifacts",
        headers=AUTH_HEADERS,
    )
    assert artifacts.status_code == 200
    artifact_items = artifacts.json()["items"]
    assert len(artifact_items) == 2
    for artifact in artifact_items:
        assert artifact["path"].startswith(f"data/sessions/{session_id}/artifacts/")
        assert (tmp_path / artifact["path"]).exists()


@pytest.mark.anyio
async def test_e2e_failure_requires_replan_then_recovers_with_new_version(
    client: AsyncClient,
) -> None:
    session_id = await _create_session(client, goal="e2e failure recovery")
    plan_v1_steps = [
        {
            "id": "v1_step_ok",
            "title": "First succeeds",
            "tool": "list_dir",
            "inputs": {"path": "."},
            "timeout_sec": 30,
        },
        {
            "id": "v1_step_fail",
            "title": "Second fails",
            "tool": "run_shell_readonly",
            "inputs": {"command": "echo blocked"},
            "timeout_sec": 30,
        },
        {
            "id": "v1_step_after_fail",
            "title": "Must not continue",
            "tool": "list_dir",
            "inputs": {"path": "."},
            "timeout_sec": 30,
        },
    ]
    await _import_plan(
        client,
        session_id=session_id,
        version=1,
        title="e2e failure flow",
        session_goal="validate failure and recovery flow",
        steps=plan_v1_steps,
    )
    await _approve_plan(client, session_id=session_id, version=1)

    for step_id in ("v1_step_ok", "v1_step_fail", "v1_step_after_fail"):
        await _approve_step(client, session_id=session_id, step_id=step_id)

    first_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/v1_step_ok/execute",
        headers=AUTH_HEADERS,
    )
    assert first_execute.status_code == 200
    assert first_execute.json()["status"] == "succeeded"

    failed_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/v1_step_fail/execute",
        headers=AUTH_HEADERS,
    )
    assert failed_execute.status_code == 200
    failed_payload = failed_execute.json()
    assert failed_payload["status"] == "failed"
    assert "not allowlisted" in (failed_payload["error"] or "")

    failed_session = await client.get(
        f"/api/v1/sessions/{session_id}",
        headers=AUTH_HEADERS,
    )
    assert failed_session.status_code == 200
    failed_session_payload = failed_session.json()
    assert failed_session_payload["status"] == "failed"
    assert failed_session_payload["needs_replan"] is True

    blocked_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/v1_step_after_fail/execute",
        headers=AUTH_HEADERS,
    )
    assert blocked_execute.status_code == 409
    assert "needs replan" in blocked_execute.json()["detail"]

    plan_v2_steps = [
        {
            "id": "v2_step_resume",
            "title": "Resume with new plan",
            "tool": "list_dir",
            "inputs": {"path": "."},
            "timeout_sec": 30,
        }
    ]
    await _import_plan(
        client,
        session_id=session_id,
        version=2,
        title="e2e recovery flow",
        session_goal="recover with new plan version",
        steps=plan_v2_steps,
    )
    await _approve_plan(client, session_id=session_id, version=2)
    await _approve_step(client, session_id=session_id, step_id="v2_step_resume")

    recovery_execute = await client.post(
        f"/api/v1/sessions/{session_id}/steps/v2_step_resume/execute",
        headers=AUTH_HEADERS,
    )
    assert recovery_execute.status_code == 200
    recovery_payload = recovery_execute.json()
    assert recovery_payload["status"] == "succeeded"
    assert recovery_payload["error"] is None

    recovered_session = await client.get(
        f"/api/v1/sessions/{session_id}",
        headers=AUTH_HEADERS,
    )
    assert recovered_session.status_code == 200
    recovered_session_payload = recovered_session.json()
    assert recovered_session_payload["status"] == "succeeded"
    assert recovered_session_payload["plan_version"] == 2
    assert recovered_session_payload["needs_replan"] is False

    events = await client.get(
        f"/api/v1/sessions/{session_id}/events/search",
        headers=AUTH_HEADERS,
        params={"q": "step"},
    )
    assert events.status_code == 200
    event_items = events.json()["items"]
    assert any(item["event_type"] == "step_failed" for item in event_items)
    assert any(item["summary"] == "step v2_step_resume executed" for item in event_items)
