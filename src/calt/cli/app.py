from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import anyio
import httpx
import typer

from calt.cli.display import compose_sections, render_kv_panel, render_table
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
PayloadRenderer = Callable[[dict[str, Any]], str]


def _default_client_factory(base_url: str, token: str) -> DaemonApiClient:
    return DaemonApiClient(base_url=base_url, token=token)


def _require_settings(ctx: typer.Context) -> CliSettings:
    settings = ctx.obj
    if isinstance(settings, CliSettings):
        return settings
    raise RuntimeError("CLI context is not initialized")


def _print_payload(
    payload: dict[str, Any],
    *,
    as_json: bool,
    renderer: PayloadRenderer | None = None,
) -> None:
    if as_json:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if renderer is None:
        typer.echo(_render_generic_payload(payload))
        return

    typer.echo(renderer(payload))


def _truncate(value: str, *, limit: int = 60) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _render_generic_payload(payload: dict[str, Any]) -> str:
    return render_kv_panel("Result", [(key, value) for key, value in payload.items()])


def _render_session_create_payload(payload: dict[str, Any]) -> str:
    return render_kv_panel(
        "Session Created",
        [
            ("Session ID", payload.get("id")),
            ("Goal", payload.get("goal")),
            ("Status", payload.get("status")),
            ("Plan Version", payload.get("plan_version")),
            ("Created At", payload.get("created_at")),
        ],
    )


def _render_session_stop_payload(payload: dict[str, Any]) -> str:
    return render_kv_panel(
        "Session Stopped",
        [
            ("Session ID", payload.get("session_id")),
            ("Status", payload.get("status")),
        ],
    )


def _render_plan_import_payload(payload: dict[str, Any]) -> str:
    steps = payload.get("steps")
    step_rows: list[list[Any]] = []
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_rows.append(
                [
                    step.get("id"),
                    step.get("title"),
                    step.get("tool"),
                    step.get("status"),
                ]
            )

    summary_panel = render_kv_panel(
        "Plan Imported",
        [
            ("Session ID", payload.get("session_id")),
            ("Version", payload.get("version")),
            ("Title", payload.get("title")),
            ("Step Count", len(step_rows)),
        ],
    )
    if not step_rows:
        return summary_panel
    return compose_sections(
        [
            summary_panel,
            render_table("Steps", ["ID", "Title", "Tool", "Status"], step_rows),
        ]
    )


def _render_plan_approve_payload(payload: dict[str, Any]) -> str:
    return render_kv_panel(
        "Plan Approved",
        [
            ("Session ID", payload.get("session_id")),
            ("Version", payload.get("version")),
            ("Approved", payload.get("approved")),
        ],
    )


def _render_step_approve_payload(payload: dict[str, Any]) -> str:
    return render_kv_panel(
        "Step Approved",
        [
            ("Session ID", payload.get("session_id")),
            ("Step ID", payload.get("step_id")),
            ("Approved", payload.get("approved")),
        ],
    )


def _render_step_execute_payload(payload: dict[str, Any]) -> str:
    sections: list[str] = [
        render_kv_panel(
            "Step Executed",
            [
                ("Session ID", payload.get("session_id")),
                ("Step ID", payload.get("step_id")),
                ("Status", payload.get("status")),
                ("Run ID", payload.get("run_id")),
                ("Error", payload.get("error")),
            ],
        )
    ]
    artifacts = payload.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        sections.append(
            render_table(
                "Artifacts",
                ["#", "Path"],
                [[index, artifact] for index, artifact in enumerate(artifacts, start=1)],
            )
        )
    return compose_sections(sections)


def _render_logs_search_payload(payload: dict[str, Any]) -> str:
    items = payload.get("items")
    rows: list[list[Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    item.get("id"),
                    item.get("event_type"),
                    _truncate(str(item.get("summary", "-"))),
                    item.get("source"),
                    item.get("created_at"),
                ]
            )

    summary = render_kv_panel("Logs Search", [("Result Count", len(rows))])
    if not rows:
        return summary
    return compose_sections(
        [
            summary,
            render_table(
                "Events",
                ["ID", "Type", "Summary", "Source", "Created At"],
                rows,
            ),
        ]
    )


def _render_artifacts_list_payload(payload: dict[str, Any]) -> str:
    items = payload.get("items")
    rows: list[list[Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    item.get("id"),
                    item.get("step_id"),
                    item.get("kind"),
                    item.get("path"),
                ]
            )
    summary = render_kv_panel("Artifacts", [("Result Count", len(rows))])
    if not rows:
        return summary
    return compose_sections(
        [
            summary,
            render_table("Artifact List", ["ID", "Step", "Kind", "Path"], rows),
        ]
    )


def _render_tools_list_payload(payload: dict[str, Any]) -> str:
    items = payload.get("items")
    rows: list[list[Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    item.get("tool_name"),
                    item.get("permission_profile"),
                    item.get("enabled"),
                ]
            )
    summary = render_kv_panel("Tools", [("Result Count", len(rows))])
    if not rows:
        return summary
    return compose_sections(
        [
            summary,
            render_table("Tool List", ["Tool", "Permission", "Enabled"], rows),
        ]
    )


def _render_tool_permissions_payload(payload: dict[str, Any]) -> str:
    return render_kv_panel(
        "Tool Permissions",
        [
            ("Tool", payload.get("tool_name")),
            ("Permission", payload.get("permission_profile")),
            ("Enabled", payload.get("enabled")),
            ("Description", payload.get("description")),
        ],
    )


def _render_flow_run_payload(payload: dict[str, Any]) -> str:
    step_results = payload.get("step_results")
    rows: list[list[Any]] = []
    succeeded = 0
    if isinstance(step_results, list):
        for result in step_results:
            if not isinstance(result, dict):
                continue
            status = result.get("status")
            if status == "succeeded":
                succeeded += 1
            rows.append(
                [
                    result.get("step_id"),
                    result.get("approved"),
                    status,
                    result.get("run_id"),
                    _truncate(str(result.get("error", "-"))),
                ]
            )

    summary = render_kv_panel(
        "Flow Run Summary",
        [
            ("Session ID", payload.get("session_id")),
            ("Plan Version", payload.get("plan_version")),
            ("Total Steps", payload.get("total_steps")),
            ("Succeeded", succeeded),
            ("Failed", len(rows) - succeeded),
        ],
    )
    if not rows:
        return summary
    return compose_sections(
        [
            summary,
            render_table(
                "Step Results",
                ["Step ID", "Approved", "Status", "Run ID", "Error"],
                rows,
            ),
        ]
    )


def _render_guide_text() -> str:
    return compose_sections(
        [
            render_kv_panel(
                "最短操作フロー",
                [
                    ("目的", "goalとplan fileだけで実行する"),
                    ("推奨コマンド", "calt flow run"),
                ],
            ),
            render_table(
                "手順",
                ["Step", "Command"],
                [
                    ["1", "calt guide"],
                    ["2", "calt flow run --goal <goal> <plan_file>"],
                    ["3", "calt logs search <session_id> --query step_executed"],
                    ["4", "必要時: calt logs search <session_id> --json"],
                ],
            ),
        ]
    )


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


async def _run_flow_operation(
    client: DaemonClientProtocol,
    *,
    goal: str,
    version: int,
    title: str,
    steps: list[dict[str, Any]],
    plan_session_goal: str | None,
    approved_by: str,
    source: str,
) -> dict[str, Any]:
    session_payload = await client.create_session(goal=goal)
    session_id = str(session_payload.get("id", ""))
    if not session_id:
        raise RuntimeError("session create response does not include id")

    import_payload = await client.import_plan(
        session_id,
        version=version,
        title=title,
        steps=steps,
        session_goal=plan_session_goal or goal,
    )
    await client.approve_plan(
        session_id,
        version,
        approved_by=approved_by,
        source=source,
    )

    step_results: list[dict[str, Any]] = []
    imported_steps = import_payload.get("steps")
    ordered_steps: list[dict[str, Any]]
    if isinstance(imported_steps, list):
        ordered_steps = [step for step in imported_steps if isinstance(step, dict)]
    else:
        ordered_steps = steps

    for step in ordered_steps:
        step_id_raw = step.get("id")
        if step_id_raw is None:
            continue
        step_id = str(step_id_raw)
        approve_payload = await client.approve_step(
            session_id,
            step_id,
            approved_by=approved_by,
            source=source,
        )
        execute_payload = await client.execute_step(session_id, step_id)
        status = str(execute_payload.get("status") or "succeeded")
        step_results.append(
            {
                "step_id": step_id,
                "approved": approve_payload.get("approved"),
                "status": status,
                "run_id": execute_payload.get("run_id"),
                "error": execute_payload.get("error"),
            }
        )
        if status != "succeeded":
            break

    return {
        "session_id": session_id,
        "plan_version": version,
        "plan_title": title,
        "total_steps": len(ordered_steps),
        "step_results": step_results,
    }


def _run_and_print(
    settings: CliSettings,
    client_factory: ClientFactory,
    operation: ClientOperation,
    *,
    as_json: bool = False,
    renderer: PayloadRenderer | None = None,
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
    _print_payload(payload, as_json=as_json, renderer=renderer)


def build_app(client_factory: ClientFactory | None = None) -> typer.Typer:
    resolved_client_factory = client_factory or _default_client_factory

    app = typer.Typer(no_args_is_help=True)
    session_app = typer.Typer(no_args_is_help=True)
    plan_app = typer.Typer(no_args_is_help=True)
    step_app = typer.Typer(no_args_is_help=True)
    logs_app = typer.Typer(no_args_is_help=True)
    artifacts_app = typer.Typer(no_args_is_help=True)
    tools_app = typer.Typer(no_args_is_help=True)
    flow_app = typer.Typer(no_args_is_help=True)

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
            "",
            "--token",
            envvar="CALT_DAEMON_TOKEN",
            help="Daemon bearer token.",
        ),
    ) -> None:
        ctx.obj = CliSettings(base_url=base_url, token=token)

    @app.command("guide")
    def guide_command() -> None:
        typer.echo(_render_guide_text())

    @session_app.command("create")
    def session_create(
        ctx: typer.Context,
        goal: str | None = typer.Option(None, "--goal", help="Session goal."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.create_session(goal=goal),
            as_json=json_output,
            renderer=_render_session_create_payload,
        )

    @session_app.command("stop")
    def session_stop(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.stop_session(session_id),
            as_json=json_output,
            renderer=_render_session_stop_payload,
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
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
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
            as_json=json_output,
            renderer=_render_plan_import_payload,
        )

    @plan_app.command("approve")
    def plan_approve(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        version: int = typer.Argument(..., help="Plan version."),
        approved_by: str = typer.Option("cli", "--approved-by", help="Approver ID."),
        source: str = typer.Option("cli", "--source", help="Approval source."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
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
            as_json=json_output,
            renderer=_render_plan_approve_payload,
        )

    @step_app.command("approve")
    def step_approve(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        step_id: str = typer.Argument(..., help="Step ID."),
        approved_by: str = typer.Option("cli", "--approved-by", help="Approver ID."),
        source: str = typer.Option("cli", "--source", help="Approval source."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
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
            as_json=json_output,
            renderer=_render_step_approve_payload,
        )

    @step_app.command("execute")
    def step_execute(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        step_id: str = typer.Argument(..., help="Step ID."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.execute_step(session_id, step_id),
            as_json=json_output,
            renderer=_render_step_execute_payload,
        )

    @logs_app.command("search")
    def logs_search(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        query: str | None = typer.Option(None, "--query", "-q", help="Search query."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.search_events(session_id, q=query),
            as_json=json_output,
            renderer=_render_logs_search_payload,
        )

    @artifacts_app.command("list")
    def artifacts_list(
        ctx: typer.Context,
        session_id: str = typer.Argument(..., help="Session ID."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.list_artifacts(session_id),
            as_json=json_output,
            renderer=_render_artifacts_list_payload,
        )

    @tools_app.command("list")
    def tools_list(
        ctx: typer.Context,
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.list_tools(),
            as_json=json_output,
            renderer=_render_tools_list_payload,
        )

    @tools_app.command("permissions")
    def tools_permissions(
        ctx: typer.Context,
        tool_name: str = typer.Argument(..., help="Tool name."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.get_tool_permissions(tool_name),
            as_json=json_output,
            renderer=_render_tool_permissions_payload,
        )

    @flow_app.command("run")
    def flow_run(
        ctx: typer.Context,
        plan_file: Path = typer.Argument(
            ...,
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Plan JSON file path.",
        ),
        goal: str = typer.Option(..., "--goal", help="Session goal."),
        approved_by: str = typer.Option("cli", "--approved-by", help="Approver ID."),
        source: str = typer.Option("cli", "--source", help="Approval source."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        version, title, steps, plan_session_goal = _load_plan_payload(plan_file)
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: _run_flow_operation(
                client,
                goal=goal,
                version=version,
                title=title,
                steps=steps,
                plan_session_goal=plan_session_goal,
                approved_by=approved_by,
                source=source,
            ),
            as_json=json_output,
            renderer=_render_flow_run_payload,
        )

    app.add_typer(session_app, name="session")
    app.add_typer(plan_app, name="plan")
    app.add_typer(step_app, name="step")
    app.add_typer(logs_app, name="logs")
    app.add_typer(artifacts_app, name="artifacts")
    app.add_typer(tools_app, name="tools")
    app.add_typer(flow_app, name="flow")
    return app


app = build_app()


def run() -> None:
    app()
