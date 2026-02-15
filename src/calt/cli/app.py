from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import anyio
import httpx
import typer

from calt.client import DaemonApiClient


class DaemonClientProtocol(Protocol):
    async def __aenter__(self) -> DaemonClientProtocol: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None: ...

    async def create_session(self, goal: str | None = None) -> dict[str, Any]: ...

    async def import_plan(
        self,
        session_id: str,
        *,
        version: int,
        title: str,
        steps: list[dict[str, Any]],
        session_goal: str | None = None,
    ) -> dict[str, Any]: ...

    async def approve_plan(
        self,
        session_id: str,
        version: int,
        *,
        approved_by: str,
        source: str,
    ) -> dict[str, Any]: ...

    async def approve_step(
        self,
        session_id: str,
        step_id: str,
        *,
        approved_by: str,
        source: str,
    ) -> dict[str, Any]: ...

    async def execute_step(self, session_id: str, step_id: str) -> dict[str, Any]: ...

    async def stop_session(self, session_id: str) -> dict[str, Any]: ...

    async def search_events(self, session_id: str, q: str | None = None) -> dict[str, Any]: ...

    async def list_artifacts(self, session_id: str) -> dict[str, Any]: ...

    async def list_tools(self) -> dict[str, Any]: ...

    async def get_tool_permissions(self, tool_name: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CliSettings:
    base_url: str
    token: str


ClientFactory = Callable[[str, str], DaemonClientProtocol]
ClientOperation = Callable[[DaemonClientProtocol], Awaitable[dict[str, Any]]]


def _default_client_factory(base_url: str, token: str) -> DaemonApiClient:
    return DaemonApiClient(base_url=base_url, token=token)


def _require_settings(ctx: typer.Context) -> CliSettings:
    settings = ctx.obj
    if isinstance(settings, CliSettings):
        return settings
    raise RuntimeError("CLI context is not initialized")


def _print_payload(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


def _load_plan_payload(path: Path) -> tuple[int, str, list[dict[str, Any]], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise typer.BadParameter(f"failed to read plan file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("plan file must be a valid JSON object") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter("plan file must be a JSON object")

    missing = [key for key in ("version", "title", "steps") if key not in payload]
    if missing:
        raise typer.BadParameter(f"missing keys in plan file: {', '.join(missing)}")

    steps = payload["steps"]
    if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
        raise typer.BadParameter("'steps' must be a list of objects")

    session_goal = payload.get("session_goal")
    if session_goal is not None and not isinstance(session_goal, str):
        raise typer.BadParameter("'session_goal' must be a string")

    return int(payload["version"]), str(payload["title"]), steps, session_goal


async def _execute_operation(
    settings: CliSettings,
    client_factory: ClientFactory,
    operation: ClientOperation,
) -> dict[str, Any]:
    async with client_factory(settings.base_url, settings.token) as client:
        return await operation(client)


def _run_and_print(
    settings: CliSettings,
    client_factory: ClientFactory,
    operation: ClientOperation,
) -> None:
    try:
        payload = anyio.run(_execute_operation, settings, client_factory, operation)
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        detail = exc.response.text.strip() or "request failed"
        typer.echo(f"HTTP {status_code}: {detail}", err=True)
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        typer.echo(f"HTTP error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _print_payload(payload)


def build_app(client_factory: ClientFactory | None = None) -> typer.Typer:
    resolved_client_factory = client_factory or _default_client_factory

    app = typer.Typer(no_args_is_help=True)
    session_app = typer.Typer(no_args_is_help=True)
    plan_app = typer.Typer(no_args_is_help=True)
    step_app = typer.Typer(no_args_is_help=True)
    logs_app = typer.Typer(no_args_is_help=True)
    artifacts_app = typer.Typer(no_args_is_help=True)
    tools_app = typer.Typer(no_args_is_help=True)

    @app.callback()
    def app_callback(
        ctx: typer.Context,
        base_url: str = typer.Option(
            "http://127.0.0.1:8000",
            "--base-url",
            envvar="CALT_DAEMON_BASE_URL",
            help="Daemon base URL.",
        ),
        token: str = typer.Option(
            ...,
            "--token",
            envvar="CALT_DAEMON_TOKEN",
            help="Daemon bearer token.",
        ),
    ) -> None:
        ctx.obj = CliSettings(base_url=base_url, token=token)

    @session_app.command("create")
    def session_create(
        ctx: typer.Context,
        goal: str | None = typer.Option(None, "--goal", help="Session goal."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.create_session(goal=goal),
        )

    @session_app.command("stop")
    def session_stop(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.stop_session(session_id),
        )

    @plan_app.command("import")
    def plan_import_command(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        plan_file: Path = typer.Argument(
            ...,
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Plan JSON file path.",
        ),
    ) -> None:
        version, title, steps, session_goal = _load_plan_payload(plan_file)
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.import_plan(
                session_id,
                version=version,
                title=title,
                steps=steps,
                session_goal=session_goal,
            ),
        )

    @plan_app.command("approve")
    def plan_approve(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        version: int = typer.Argument(..., help="Plan version."),
        approved_by: str = typer.Option("cli", "--approved-by", help="Approver ID."),
        source: str = typer.Option("cli", "--source", help="Approval source."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.approve_plan(
                session_id,
                version,
                approved_by=approved_by,
                source=source,
            ),
        )

    @step_app.command("approve")
    def step_approve(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        step_id: str = typer.Argument(..., help="Step ID."),
        approved_by: str = typer.Option("cli", "--approved-by", help="Approver ID."),
        source: str = typer.Option("cli", "--source", help="Approval source."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.approve_step(
                session_id,
                step_id,
                approved_by=approved_by,
                source=source,
            ),
        )

    @step_app.command("execute")
    def step_execute(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        step_id: str = typer.Argument(..., help="Step ID."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.execute_step(session_id, step_id),
        )

    @logs_app.command("search")
    def logs_search(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        query: str | None = typer.Option(None, "--query", "-q", help="Search query."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.search_events(session_id, q=query),
        )

    @artifacts_app.command("list")
    def artifacts_list(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.list_artifacts(session_id),
        )

    @tools_app.command("list")
    def tools_list(ctx: typer.Context) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.list_tools(),
        )

    @tools_app.command("permissions")
    def tools_permissions(
        ctx: typer.Context,
        tool_name: str = typer.Argument(..., help="Tool name."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.get_tool_permissions(tool_name),
        )

    app.add_typer(session_app, name="session")
    app.add_typer(plan_app, name="plan")
    app.add_typer(step_app, name="step")
    app.add_typer(logs_app, name="logs")
    app.add_typer(artifacts_app, name="artifacts")
    app.add_typer(tools_app, name="tools")
    return app


app = build_app()


def run() -> None:
    app()
