from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from calt.client import DaemonApiClient


def _decode_json_body(request: httpx.Request) -> dict[str, Any] | None:
    if not request.content:
        return None
    return json.loads(request.content.decode("utf-8"))


@pytest.mark.anyio
async def test_daemon_client_builds_expected_requests() -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(status_code=200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with DaemonApiClient(
        base_url="http://daemon.local",
        token="test-token",
        transport=transport,
    ) as client:
        await client.create_session(goal="demo", mode="dry_run", safety_profile="dev")
        await client.import_plan(
            "session-1",
            version=2,
            title="imported",
            session_goal="verify client",
            steps=[
                {
                    "id": "step_001",
                    "title": "List",
                    "tool": "list_dir",
                    "inputs": {"path": "."},
                    "timeout_sec": 30,
                }
            ],
        )
        await client.get_session("session-1")
        await client.get_plan("session-1", 2)
        await client.approve_plan("session-1", 2, approved_by="user-1", source="cli")
        await client.approve_step("session-1", "step_001", approved_by="user-1", source="cli")
        await client.execute_step("session-1", "step_001", confirm_high_risk=True)
        await client.stop_session("session-1")
        await client.search_events("session-1", q="list_dir")
        await client.list_artifacts("session-1")
        await client.list_tools()
        await client.get_tool_permissions("read_file")

    assert [(req.method, req.url.path) for req in captured_requests] == [
        ("POST", "/api/v1/sessions"),
        ("POST", "/api/v1/sessions/session-1/plans/import"),
        ("GET", "/api/v1/sessions/session-1"),
        ("GET", "/api/v1/sessions/session-1/plans/2"),
        ("POST", "/api/v1/sessions/session-1/plans/2/approve"),
        ("POST", "/api/v1/sessions/session-1/steps/step_001/approve"),
        ("POST", "/api/v1/sessions/session-1/steps/step_001/execute"),
        ("POST", "/api/v1/sessions/session-1/stop"),
        ("GET", "/api/v1/sessions/session-1/events/search"),
        ("GET", "/api/v1/sessions/session-1/artifacts"),
        ("GET", "/api/v1/tools"),
        ("GET", "/api/v1/tools/read_file/permissions"),
    ]
    assert all(req.headers["Authorization"] == "Bearer test-token" for req in captured_requests)
    assert _decode_json_body(captured_requests[0]) == {
        "goal": "demo",
        "mode": "dry_run",
        "safety_profile": "dev",
    }
    assert _decode_json_body(captured_requests[1]) == {
        "version": 2,
        "title": "imported",
        "session_goal": "verify client",
        "steps": [
            {
                "id": "step_001",
                "title": "List",
                "tool": "list_dir",
                "inputs": {"path": "."},
                "timeout_sec": 30,
            }
        ],
    }
    assert _decode_json_body(captured_requests[4]) == {"approved_by": "user-1", "source": "cli"}
    assert _decode_json_body(captured_requests[5]) == {"approved_by": "user-1", "source": "cli"}
    assert _decode_json_body(captured_requests[6]) == {"confirm_high_risk": True}
    assert captured_requests[8].url.params["q"] == "list_dir"


@pytest.mark.anyio
async def test_daemon_client_raises_http_status_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=500, json={"detail": "internal error"})

    transport = httpx.MockTransport(handler)
    async with DaemonApiClient(
        base_url="http://daemon.local",
        token="test-token",
        transport=transport,
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.list_tools()
