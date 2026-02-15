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

    async def create_session(self, goal: str | None = None) -> dict[str, Any]:
        return self._record("create_session", goal=goal)

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
        )

    async def execute_step(self, session_id: str, step_id: str) -> dict[str, Any]:
        return self._record("execute_step", session_id=session_id, step_id=step_id)

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        return self._record("stop_session", session_id=session_id)

    async def search_events(self, session_id: str, q: str | None = None) -> dict[str, Any]:
        return self._record("search_events", session_id=session_id, q=q)

    async def list_artifacts(self, session_id: str) -> dict[str, Any]:
        return self._record("list_artifacts", session_id=session_id)

    async def list_tools(self) -> dict[str, Any]:
        return self._record("list_tools")

    async def get_tool_permissions(self, tool_name: str) -> dict[str, Any]:
        return self._record("get_tool_permissions", tool_name=tool_name)


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


def _invoke(app: Any, args: list[str]) -> Any:
    return runner.invoke(
        app,
        ["--base-url", "http://daemon.local", "--token", "test-token", *args],
    )


def _parse_stdout(result: Any) -> dict[str, Any]:
    return json.loads(result.stdout)


def test_session_create_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, factory = cli_fixture
    result = _invoke(app, ["session", "create", "--goal", "demo"])
    assert result.exit_code == 0
    assert factory.calls == [("http://daemon.local", "test-token")]
    assert client.calls == [("create_session", {"goal": "demo"})]
    assert _parse_stdout(result)["method"] == "create_session"


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


def test_session_stop_command(cli_fixture: tuple[Any, MockDaemonClient, MockClientFactory]) -> None:
    app, client, _ = cli_fixture
    result = _invoke(app, ["session", "stop", "session-1"])
    assert result.exit_code == 0
    assert client.calls == [("stop_session", {"session_id": "session-1"})]
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
    assert client.calls == [("get_tool_permissions", {"tool_name": "read_file"})]
    assert _parse_stdout(result)["method"] == "get_tool_permissions"
