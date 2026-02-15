from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from calt.cli import build_app

runner = CliRunner()


class MockDaemonClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.session_response: dict[str, Any] = {
            "id": "session-1",
            "status": "awaiting_plan_approval",
            "needs_replan": False,
            "plan_version": 1,
        }
        self.plan_response: dict[str, Any] = {
            "session_id": "session-1",
            "version": 1,
            "title": "mock plan",
            "steps": [],
        }

    async def __aenter__(self) -> MockDaemonClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        return None

    def _record(self, method: str, **payload: Any) -> dict[str, Any]:
        self.calls.append((method, payload))
        return {"ok": True, "method": method, **payload}

    async def create_session(
        self,
        goal: str | None = None,
        *,
        mode: str = "normal",
        safety_profile: str = "strict",
    ) -> dict[str, Any]:
        record_payload: dict[str, Any] = {"goal": goal}
        if mode != "normal":
            record_payload["mode"] = mode
        if safety_profile != "strict":
            record_payload["safety_profile"] = safety_profile
        payload = self._record("create_session", **record_payload)
        payload.update(
            {
                "id": "session-1",
                "mode": mode,
                "safety_profile": safety_profile,
                "status": "awaiting_plan_approval",
                "plan_version": None,
                "created_at": "2026-02-15T00:00:00Z",
            }
        )
        return payload

    async def import_plan(
        self,
        session_id: str,
        *,
        version: int,
        title: str,
        steps: list[dict[str, Any]],
        session_goal: str | None = None,
    ) -> dict[str, Any]:
        return self._record(
            "import_plan",
            session_id=session_id,
            version=version,
            title=title,
            steps=steps,
            session_goal=session_goal,
        )

    async def approve_plan(
        self,
        session_id: str,
        version: int,
        *,
        approved_by: str = "system",
        source: str = "api",
    ) -> dict[str, Any]:
        return self._record(
            "approve_plan",
            session_id=session_id,
            version=version,
            approved_by=approved_by,
            source=source,
            approved=True,
        )

    async def approve_step(
        self,
        session_id: str,
        step_id: str,
        *,
        approved_by: str = "system",
        source: str = "api",
    ) -> dict[str, Any]:
        return self._record(
            "approve_step",
            session_id=session_id,
            step_id=step_id,
            approved_by=approved_by,
            source=source,
            approved=True,
        )

    async def execute_step(
        self,
        session_id: str,
        step_id: str,
        *,
        confirm_high_risk: bool = False,
    ) -> dict[str, Any]:
        record_payload: dict[str, Any] = {"session_id": session_id, "step_id": step_id}
        if confirm_high_risk:
            record_payload["confirm_high_risk"] = True
        payload = self._record("execute_step", **record_payload)
        payload.update(
            {
                "status": "succeeded",
                "run_id": 101,
                "error": None,
                "artifacts": [],
                "output": {"ok": True},
            }
        )
        return payload

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        return self._record("stop_session", session_id=session_id, status="cancelled")

    async def get_session(self, session_id: str) -> dict[str, Any]:
        self.calls.append(("get_session", {"session_id": session_id}))
        payload = dict(self.session_response)
        payload["id"] = str(payload.get("id") or session_id)
        return payload

    async def get_plan(self, session_id: str, version: int) -> dict[str, Any]:
        self.calls.append(("get_plan", {"session_id": session_id, "version": version}))
        payload = dict(self.plan_response)
        payload["session_id"] = str(payload.get("session_id") or session_id)
        payload["version"] = int(payload.get("version") or version)
        raw_steps = payload.get("steps")
        if isinstance(raw_steps, list):
            payload["steps"] = [dict(step) for step in raw_steps if isinstance(step, dict)]
        return payload

    async def search_events(self, session_id: str, q: str | None = None) -> dict[str, Any]:
        payload = self._record("search_events", session_id=session_id, q=q)
        payload["items"] = [
            {
                "id": 1,
                "event_type": "step_executed",
                "summary": "step step_001 executed",
                "source": "daemon",
                "created_at": "2026-02-15T00:00:00Z",
            }
        ]
        return payload

    async def list_artifacts(self, session_id: str) -> dict[str, Any]:
        return self._record("list_artifacts", session_id=session_id)

    async def list_tools(self) -> dict[str, Any]:
        payload = self._record("list_tools")
        payload["items"] = [
            {
                "tool_name": "list_dir",
                "permission_profile": "readonly",
                "enabled": True,
            }
        ]
        return payload

    async def get_tool_permissions(self, tool_name: str) -> dict[str, Any]:
        return self._record(
            "get_tool_permissions",
            tool_name=tool_name,
            permission_profile="readonly",
            enabled=True,
            description="list directory entries",
        )


class MockClientFactory:
    def __init__(self, client: MockDaemonClient) -> None:
        self.client = client
        self.calls: list[tuple[str, str]] = []

    def __call__(self, base_url: str, token: str) -> MockDaemonClient:
        self.calls.append((base_url, token))
        return self.client


@pytest.fixture
def cli_fixture() -> tuple[Any, MockDaemonClient, MockClientFactory]:
    client = MockDaemonClient()
    factory = MockClientFactory(client)
    app = build_app(client_factory=factory)
    return app, client, factory


def _invoke(app: Any, args: list[str], *, json_output: bool = True) -> Any:
    command = [*args]
    if json_output:
        command.append("--json")
    return runner.invoke(
        app,
        ["--base-url", "http://daemon.local", "--token", "test-token", *command],
    )


def _parse_stdout(result: Any) -> dict[str, Any]:
    return json.loads(result.stdout)


def test_session_create_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, factory = cli_fixture
    result = _invoke(app, ["session", "create", "--goal", "demo"])
    assert result.exit_code == 0
    assert factory.calls == [("http://daemon.local", "test-token")]
    assert client.calls[0] == ("create_session", {"goal": "demo"})
    assert _parse_stdout(result)["method"] == "create_session"


def test_session_create_command_with_dry_run_mode(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["session", "create", "--goal", "demo", "--mode", "dry_run"])
    assert result.exit_code == 0
    assert client.calls == [("create_session", {"goal": "demo", "mode": "dry_run"})]
    payload = _parse_stdout(result)
    assert payload["method"] == "create_session"
    assert payload["mode"] == "dry_run"


def test_session_create_command_with_dev_safety_profile(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["session", "create", "--goal", "demo", "--safety-profile", "dev"])
    assert result.exit_code == 0
    assert client.calls == [("create_session", {"goal": "demo", "safety_profile": "dev"})]
    payload = _parse_stdout(result)
    assert payload["method"] == "create_session"
    assert payload["safety_profile"] == "dev"


def test_plan_import_command(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, client, _ = cli_fixture
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "version": 3,
                "title": "cli plan",
                "session_goal": "validate cli",
                "steps": [{"id": "step_001", "title": "List", "tool": "list_dir", "inputs": {}}],
            }
        ),
        encoding="utf-8",
    )
    result = _invoke(app, ["plan", "import", "session-1", str(plan_file)])
    assert result.exit_code == 0
    assert client.calls == [
        (
            "import_plan",
            {
                "session_id": "session-1",
                "version": 3,
                "title": "cli plan",
                "steps": [{"id": "step_001", "title": "List", "tool": "list_dir", "inputs": {}}],
                "session_goal": "validate cli",
            },
        )
    ]
    assert _parse_stdout(result)["method"] == "import_plan"


def test_plan_import_rejects_invalid_json(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, client, _ = cli_fixture
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{not-json", encoding="utf-8")
    result = _invoke(app, ["plan", "import", "session-1", str(invalid_file)])
    assert result.exit_code == 2
    assert client.calls == []


def test_plan_approve_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, _ = cli_fixture
    result = _invoke(
        app,
        ["plan", "approve", "session-1", "2", "--approved-by", "alice", "--source", "terminal"],
    )
    assert result.exit_code == 0
    assert client.calls == [
        (
            "approve_plan",
            {
                "session_id": "session-1",
                "version": 2,
                "approved_by": "alice",
                "source": "terminal",
                "approved": True,
            },
        )
    ]
    assert _parse_stdout(result)["method"] == "approve_plan"


def test_step_approve_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, _ = cli_fixture
    result = _invoke(
        app,
        ["step", "approve", "session-1", "step_001", "--approved-by", "alice", "--source", "terminal"],
    )
    assert result.exit_code == 0
    assert client.calls == [
        (
            "approve_step",
            {
                "session_id": "session-1",
                "step_id": "step_001",
                "approved_by": "alice",
                "source": "terminal",
                "approved": True,
            },
        )
    ]
    assert _parse_stdout(result)["method"] == "approve_step"


def test_step_execute_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["step", "execute", "session-1", "step_001"])
    assert result.exit_code == 0
    assert client.calls == [("execute_step", {"session_id": "session-1", "step_id": "step_001"})]
    assert _parse_stdout(result)["method"] == "execute_step"


def test_step_execute_command_with_confirm_high_risk(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, _ = cli_fixture
    result = _invoke(
        app,
        ["step", "execute", "session-1", "step_001", "--confirm-high-risk"],
    )
    assert result.exit_code == 0
    assert client.calls == [
        (
            "execute_step",
            {
                "session_id": "session-1",
                "step_id": "step_001",
                "confirm_high_risk": True,
            },
        )
    ]
    assert _parse_stdout(result)["method"] == "execute_step"


def test_session_stop_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["session", "stop", "session-1"])
    assert result.exit_code == 0
    assert client.calls == [("stop_session", {"session_id": "session-1", "status": "cancelled"})]
    assert _parse_stdout(result)["method"] == "stop_session"


def test_logs_search_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["logs", "search", "session-1", "--query", "list_dir"])
    assert result.exit_code == 0
    assert client.calls == [("search_events", {"session_id": "session-1", "q": "list_dir"})]
    assert _parse_stdout(result)["method"] == "search_events"


def test_artifacts_list_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["artifacts", "list", "session-1"])
    assert result.exit_code == 0
    assert client.calls == [("list_artifacts", {"session_id": "session-1"})]
    assert _parse_stdout(result)["method"] == "list_artifacts"


def test_tools_list_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["tools", "list"])
    assert result.exit_code == 0
    assert client.calls == [("list_tools", {})]
    assert _parse_stdout(result)["method"] == "list_tools"


def test_tools_permissions_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["tools", "permissions", "read_file"])
    assert result.exit_code == 0
    assert client.calls[0][0] == "get_tool_permissions"
    assert client.calls[0][1]["tool_name"] == "read_file"
    assert _parse_stdout(result)["method"] == "get_tool_permissions"


def test_explain_command_recommends_plan_approve_for_awaiting_plan_approval(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, _ = cli_fixture
    client.session_response = {
        "id": "session-1",
        "status": "awaiting_plan_approval",
        "needs_replan": False,
        "plan_version": 2,
    }
    client.plan_response = {
        "session_id": "session-1",
        "version": 2,
        "title": "v2",
        "steps": [{"id": "step_001", "status": "pending"}],
    }

    result = _invoke(app, ["explain", "session-1"])
    assert result.exit_code == 0
    assert [method for method, _ in client.calls] == ["get_session", "get_plan"]
    payload = _parse_stdout(result)
    assert payload["session_id"] == "session-1"
    assert payload["status"] == "awaiting_plan_approval"
    assert payload["needs_replan"] is False
    assert payload["plan_version"] == 2
    assert payload["plan_title"] == "v2"
    assert payload["pending_step_id"] == "step_001"
    assert payload["pending_step_status"] == "pending"
    assert (
        payload["next_command"]
        == "calt plan approve session-1 2 --approved-by cli --source cli"
    )


def test_explain_command_recommends_step_approve_for_unapproved_step(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, _ = cli_fixture
    client.session_response = {
        "id": "session-1",
        "status": "awaiting_step_approval",
        "needs_replan": False,
        "plan_version": 3,
    }
    client.plan_response = {
        "session_id": "session-1",
        "version": 3,
        "title": "v3",
        "steps": [
            {"id": "step_pending", "status": "pending"},
            {"id": "step_done", "status": "succeeded"},
        ],
    }

    result = _invoke(app, ["explain", "session-1"])
    assert result.exit_code == 0
    payload = _parse_stdout(result)
    assert payload["plan_version"] == 3
    assert payload["plan_title"] == "v3"
    assert payload["pending_step_id"] == "step_pending"
    assert payload["pending_step_status"] == "pending"
    assert (
        payload["next_command"]
        == "calt step approve session-1 step_pending --approved-by cli --source cli"
    )
    assert payload["reason"] == "step step_pending is not approved"


def test_explain_command_recommends_step_execute_for_approved_unexecuted_step(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, _ = cli_fixture
    client.session_response = {
        "id": "session-1",
        "status": "awaiting_step_approval",
        "needs_replan": False,
        "plan_version": 4,
    }
    client.plan_response = {
        "session_id": "session-1",
        "version": 4,
        "title": "v4",
        "steps": [
            {"id": "step_done", "status": "succeeded"},
            {"id": "step_ready", "status": "awaiting_step_approval"},
        ],
    }

    result = _invoke(app, ["explain", "session-1"])
    assert result.exit_code == 0
    payload = _parse_stdout(result)
    assert payload["plan_version"] == 4
    assert payload["plan_title"] == "v4"
    assert payload["pending_step_id"] == "step_ready"
    assert payload["pending_step_status"] == "awaiting_step_approval"
    assert payload["next_command"] == "calt step execute session-1 step_ready"
    assert payload["reason"] == "step step_ready is approved but not executed"


def test_explain_command_recommends_plan_import_for_needs_replan(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, _ = cli_fixture
    client.session_response = {
        "id": "session-1",
        "status": "failed",
        "needs_replan": True,
        "plan_version": 5,
    }
    client.plan_response = {
        "session_id": "session-1",
        "version": 5,
        "title": "v5",
        "steps": [{"id": "step_pending", "status": "pending"}],
    }

    result = _invoke(app, ["explain", "session-1"])
    assert result.exit_code == 0
    payload = _parse_stdout(result)
    assert payload["plan_version"] == 5
    assert payload["plan_title"] == "v5"
    assert payload["pending_step_id"] == "step_pending"
    assert payload["pending_step_status"] == "pending"
    assert payload["next_command"] == "calt plan import session-1 <new_plan_file>"
    assert payload["reason"] == "session is in replan-required state"


def test_guide_command_shows_short_flow(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, _, _ = cli_fixture
    result = _invoke(app, ["guide"], json_output=False)
    assert result.exit_code == 0
    assert "最短操作フロー" in result.stdout
    assert "calt quickstart <plan_file> --goal <goal>" in result.stdout


def test_quickstart_calls_client_in_order(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, client, _ = cli_fixture
    plan_file = tmp_path / "quickstart_plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "version": 1,
                "title": "quickstart plan",
                "steps": [
                    {"id": "step_001", "title": "first", "tool": "list_dir", "inputs": {}},
                    {"id": "step_002", "title": "second", "tool": "list_dir", "inputs": {}},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _invoke(app, ["quickstart", str(plan_file), "--goal", "ship"])
    assert result.exit_code == 0
    assert client.calls == [
        ("create_session", {"goal": "ship"}),
        (
            "import_plan",
            {
                "session_id": "session-1",
                "version": 1,
                "title": "quickstart plan",
                "steps": [
                    {"id": "step_001", "title": "first", "tool": "list_dir", "inputs": {}},
                    {"id": "step_002", "title": "second", "tool": "list_dir", "inputs": {}},
                ],
                "session_goal": "ship",
            },
        ),
        (
            "approve_plan",
            {
                "session_id": "session-1",
                "version": 1,
                "approved_by": "cli",
                "source": "cli",
                "approved": True,
            },
        ),
        (
            "approve_step",
            {
                "session_id": "session-1",
                "step_id": "step_001",
                "approved_by": "cli",
                "source": "cli",
                "approved": True,
            },
        ),
        ("execute_step", {"session_id": "session-1", "step_id": "step_001"}),
        (
            "approve_step",
            {
                "session_id": "session-1",
                "step_id": "step_002",
                "approved_by": "cli",
                "source": "cli",
                "approved": True,
            },
        ),
        ("execute_step", {"session_id": "session-1", "step_id": "step_002"}),
    ]
    payload = _parse_stdout(result)
    assert payload["session_id"] == "session-1"
    assert [item["step_id"] for item in payload["step_results"]] == ["step_001", "step_002"]


def test_quickstart_uses_plan_session_goal_when_goal_is_omitted(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, client, _ = cli_fixture
    plan_file = tmp_path / "quickstart_plan_goal.json"
    plan_file.write_text(
        json.dumps(
            {
                "version": 2,
                "title": "quickstart plan with goal",
                "session_goal": "from-plan",
                "steps": [{"id": "step_001", "title": "first", "tool": "list_dir", "inputs": {}}],
            }
        ),
        encoding="utf-8",
    )

    result = _invoke(app, ["quickstart", str(plan_file)])
    assert result.exit_code == 0
    assert client.calls[0] == ("create_session", {"goal": "from-plan"})
    assert client.calls[1][0] == "import_plan"
    assert client.calls[1][1]["session_goal"] == "from-plan"


def test_doctor_command_runs_diagnostics(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert [method for method, _ in client.calls] == [
        "list_tools",
        "get_tool_permissions",
        "create_session",
        "import_plan",
        "approve_plan",
        "approve_step",
        "execute_step",
        "search_events",
        "list_artifacts",
        "stop_session",
    ]
    payload = _parse_stdout(result)
    checks = {item["name"]: item["status"] for item in payload["checks"]}
    assert payload["ok"] is True
    assert checks["base_url"] == "pass"
    assert checks["token"] == "pass"
    assert checks["session_create"] == "pass"
    assert checks["step_execute"] == "pass"


def test_session_create_fails_when_token_is_empty_with_actionable_message(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, factory = cli_fixture
    result = runner.invoke(
        app,
        [
            "--base-url",
            "http://daemon.local",
            "--token",
            "",
            "session",
            "create",
            "--goal",
            "demo",
            "--json",
        ],
    )
    assert result.exit_code == 1
    output = result.stdout + getattr(result, "stderr", "")
    assert "missing or empty" in output
    assert "CALT_DAEMON_TOKEN" in output
    assert factory.calls == []
    assert client.calls == []


def test_doctor_command_fails_when_token_is_empty(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
) -> None:
    app, client, _ = cli_fixture
    result = runner.invoke(app, ["--base-url", "http://daemon.local", "--token", "", "doctor", "--json"])
    assert result.exit_code == 1
    payload = _parse_stdout(result)
    checks = {item["name"]: item for item in payload["checks"]}
    assert payload["ok"] is False
    assert checks["token"]["status"] == "fail"
    assert "CALT_DAEMON_TOKEN" in checks["token"]["detail"]
    for name in (
        "daemon_connectivity",
        "tools_permissions",
        "session_create",
        "plan_import",
        "plan_approve",
        "step_approve",
        "step_execute",
        "logs_search",
        "artifacts_list",
        "session_stop",
    ):
        assert checks[name]["status"] == "skip"
        assert "CALT_DAEMON_TOKEN" in checks[name]["detail"]
    assert "Illegal header value" not in result.stdout
    assert client.calls == []


def test_flow_run_calls_client_in_order(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, client, _ = cli_fixture
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "version": 1,
                "title": "flow plan",
                "steps": [
                    {"id": "step_001", "title": "first", "tool": "list_dir", "inputs": {}},
                    {"id": "step_002", "title": "second", "tool": "list_dir", "inputs": {}},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _invoke(app, ["flow", "run", "--goal", "ship", str(plan_file)])
    assert result.exit_code == 0
    assert client.calls == [
        ("create_session", {"goal": "ship"}),
        (
            "import_plan",
            {
                "session_id": "session-1",
                "version": 1,
                "title": "flow plan",
                "steps": [
                    {"id": "step_001", "title": "first", "tool": "list_dir", "inputs": {}},
                    {"id": "step_002", "title": "second", "tool": "list_dir", "inputs": {}},
                ],
                "session_goal": "ship",
            },
        ),
        (
            "approve_plan",
            {
                "session_id": "session-1",
                "version": 1,
                "approved_by": "cli",
                "source": "cli",
                "approved": True,
            },
        ),
        (
            "approve_step",
            {
                "session_id": "session-1",
                "step_id": "step_001",
                "approved_by": "cli",
                "source": "cli",
                "approved": True,
            },
        ),
        ("execute_step", {"session_id": "session-1", "step_id": "step_001"}),
        (
            "approve_step",
            {
                "session_id": "session-1",
                "step_id": "step_002",
                "approved_by": "cli",
                "source": "cli",
                "approved": True,
            },
        ),
        ("execute_step", {"session_id": "session-1", "step_id": "step_002"}),
    ]
    payload = _parse_stdout(result)
    assert payload["session_id"] == "session-1"
    assert [item["step_id"] for item in payload["step_results"]] == ["step_001", "step_002"]


def test_wizard_run_calls_client_in_order_with_explicit_plan_and_goal(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, client, _ = cli_fixture
    plan_file = tmp_path / "wizard_plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "version": 3,
                "title": "wizard plan",
                "steps": [{"id": "step_001", "title": "first", "tool": "list_dir", "inputs": {}}],
            }
        ),
        encoding="utf-8",
    )

    result = _invoke(app, ["wizard", "run", str(plan_file), "--goal", "ship"])
    assert result.exit_code == 0
    assert client.calls == [
        ("create_session", {"goal": "ship"}),
        (
            "import_plan",
            {
                "session_id": "session-1",
                "version": 3,
                "title": "wizard plan",
                "steps": [{"id": "step_001", "title": "first", "tool": "list_dir", "inputs": {}}],
                "session_goal": "ship",
            },
        ),
        (
            "approve_plan",
            {
                "session_id": "session-1",
                "version": 3,
                "approved_by": "cli",
                "source": "cli",
                "approved": True,
            },
        ),
        (
            "approve_step",
            {
                "session_id": "session-1",
                "step_id": "step_001",
                "approved_by": "cli",
                "source": "cli",
                "approved": True,
            },
        ),
        ("execute_step", {"session_id": "session-1", "step_id": "step_001"}),
    ]
    payload = _parse_stdout(result)
    assert payload["session_id"] == "session-1"
    assert payload["plan_title"] == "wizard plan"
    assert payload["goal"] == "ship"
    assert [item["step_id"] for item in payload["step_results"]] == ["step_001"]


def test_wizard_run_rich_output_includes_plan_title_and_goal(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, _, _ = cli_fixture
    plan_file = tmp_path / "wizard_rich_plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "version": 5,
                "title": "wizard rich plan",
                "steps": [{"id": "step_001", "title": "first", "tool": "list_dir", "inputs": {}}],
            }
        ),
        encoding="utf-8",
    )

    result = _invoke(app, ["wizard", "run", str(plan_file), "--goal", "ship"], json_output=False)
    assert result.exit_code == 0
    assert "Wizard Run Summary" in result.stdout
    assert "Plan Title" in result.stdout
    assert "wizard rich plan" in result.stdout
    assert "Goal" in result.stdout
    assert "ship" in result.stdout


def test_wizard_run_prompts_for_plan_and_goal_when_omitted(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, client, _ = cli_fixture
    plan_file = tmp_path / "wizard_prompt_plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "version": 4,
                "title": "wizard prompt plan",
                "session_goal": "from-plan",
                "steps": [{"id": "step_001", "title": "first", "tool": "list_dir", "inputs": {}}],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["--base-url", "http://daemon.local", "--token", "test-token", "wizard", "run", "--json"],
        input=f"{plan_file}\n\n",
    )
    assert result.exit_code == 0
    assert client.calls[0] == ("create_session", {"goal": "from-plan"})
    assert client.calls[1][0] == "import_plan"
    assert client.calls[1][1]["session_goal"] == "from-plan"


def test_wizard_run_fails_on_invalid_prompt_plan_path(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, client, _ = cli_fixture
    missing_plan_file = tmp_path / "missing_plan.json"

    result = runner.invoke(
        app,
        ["--base-url", "http://daemon.local", "--token", "test-token", "wizard", "run", "--json"],
        input=f"{missing_plan_file}\n",
    )
    assert result.exit_code == 2
    assert client.calls == []


def test_rich_output_contains_major_strings(
    cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory],
    tmp_path: Path,
) -> None:
    app, _, _ = cli_fixture
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "version": 2,
                "title": "rich plan",
                "steps": [{"id": "step_001", "title": "List", "tool": "list_dir", "inputs": {}}],
            }
        ),
        encoding="utf-8",
    )

    session_result = _invoke(app, ["session", "create", "--goal", "rich"], json_output=False)
    plan_result = _invoke(app, ["plan", "import", "session-1", str(plan_file)], json_output=False)
    step_result = _invoke(app, ["step", "execute", "session-1", "step_001"], json_output=False)
    logs_result = _invoke(app, ["logs", "search", "session-1", "--query", "step"], json_output=False)

    assert session_result.exit_code == 0
    assert plan_result.exit_code == 0
    assert step_result.exit_code == 0
    assert logs_result.exit_code == 0
    assert "Session Created" in session_result.stdout
    assert "Plan Imported" in plan_result.stdout
    assert "Step Executed" in step_result.stdout
    assert "Logs Search" in logs_result.stdout
