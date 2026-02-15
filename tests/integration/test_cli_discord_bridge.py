from __future__ import annotations

import json
from pathlib import Path

import anyio
from httpx import ASGITransport
from typer.testing import CliRunner

from calt.cli import build_app
from calt.client import DaemonApiClient
from calt.daemon import create_app
from calt.discord_bot import DiscordBotService

AUTH_TOKEN = "test-token"
BASE_URL = "http://testserver"
runner = CliRunner()


def _invoke_cli(app: object, args: list[str]):
    return runner.invoke(
        app,
        ["--base-url", BASE_URL, "--token", AUTH_TOKEN, *args, "--json"],
    )


def _parse_success(result) -> dict[str, object]:
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_cli_and_discord_can_operate_same_session(tmp_path: Path) -> None:
    database_path = tmp_path / "daemon.sqlite3"
    data_root = tmp_path / "data"
    app = create_app(database_path, data_root=data_root)
    transport = ASGITransport(app=app)

    def client_factory(base_url: str, token: str) -> DaemonApiClient:
        return DaemonApiClient(base_url=base_url, token=token, transport=transport)

    cli_app = build_app(client_factory=client_factory)
    session_payload = _parse_success(
        _invoke_cli(cli_app, ["session", "create", "--goal", "cli-discord bridge"]),
    )
    session_id = str(session_payload["id"])

    plan_file = tmp_path / "plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "version": 1,
                "title": "cli-discord bridge plan",
                "session_goal": "verify shared session",
                "steps": [
                    {
                        "id": "step_001",
                        "title": "List workspace",
                        "tool": "list_dir",
                        "inputs": {"path": "."},
                        "timeout_sec": 30,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    _parse_success(_invoke_cli(cli_app, ["plan", "import", session_id, str(plan_file)]))
    _parse_success(
        _invoke_cli(
            cli_app,
            [
                "plan",
                "approve",
                session_id,
                "1",
                "--approved-by",
                "cli-user",
                "--source",
                "cli",
            ],
        )
    )

    discord_client = DaemonApiClient(base_url=BASE_URL, token=AUTH_TOKEN, transport=transport)
    service = DiscordBotService(client=discord_client, allowed_user_ids={42})
    try:
        step_approval = anyio.run(
            lambda: service.step_approve(user_id=42, session_id=session_id, step_id="step_001"),
        )
        assert step_approval["session_id"] == session_id
        assert step_approval["step_id"] == "step_001"

        execution = _parse_success(
            _invoke_cli(cli_app, ["step", "execute", session_id, "step_001"]),
        )
        assert execution["status"] == "succeeded"

        logs_payload = anyio.run(
            lambda: service.logs_search(user_id=42, session_id=session_id, q="step"),
        )
    finally:
        anyio.run(discord_client.aclose)

    items = logs_payload["items"]
    step_approved_events = [
        item for item in items if item["event_type"] == "step_approved"
    ]
    assert step_approved_events
    assert step_approved_events[0]["source"] == "discord"
    assert step_approved_events[0]["user_id"] == "42"
    assert any(item["event_type"] == "step_executed" for item in items)
