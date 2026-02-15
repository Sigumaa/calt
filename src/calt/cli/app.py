from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

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

    async def create_session(
        self,
        goal: str | None = None,
        *,
        mode: Literal["normal", "dry_run"] = "normal",
    ) -> dict[str, Any]: ...

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

    async def execute_step(
        self,
        session_id: str,
        step_id: str,
        *,
        confirm_high_risk: bool = False,
    ) -> dict[str, Any]: ...

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
            ("Mode", payload.get("mode")),
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


def _collect_step_result_rows(step_results: Any) -> tuple[list[list[Any]], int]:
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
    return rows, succeeded


def _render_step_summary_payload(payload: dict[str, Any], *, summary_title: str) -> str:
    step_results = payload.get("step_results")
    rows, succeeded = _collect_step_result_rows(step_results)

    summary = render_kv_panel(
        summary_title,
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


def _render_flow_run_payload(payload: dict[str, Any]) -> str:
    return _render_step_summary_payload(payload, summary_title="Flow Run Summary")


def _render_quickstart_payload(payload: dict[str, Any]) -> str:
    return _render_step_summary_payload(payload, summary_title="Quickstart Summary")


def _render_doctor_payload(payload: dict[str, Any]) -> str:
    counts_raw = payload.get("counts")
    counts = counts_raw if isinstance(counts_raw, dict) else {}
    checks_raw = payload.get("checks")
    rows: list[list[Any]] = []
    if isinstance(checks_raw, list):
        for check in checks_raw:
            if not isinstance(check, dict):
                continue
            rows.append(
                [
                    check.get("name"),
                    str(check.get("status", "unknown")).upper(),
                    _truncate(str(check.get("detail", "-")), limit=100),
                ]
            )

    summary = render_kv_panel(
        "Doctor Summary",
        [
            ("Overall", "PASS" if payload.get("ok") else "FAIL"),
            ("PASS", counts.get("pass", 0)),
            ("FAIL", counts.get("fail", 0)),
            ("WARN", counts.get("warn", 0)),
            ("SKIP", counts.get("skip", 0)),
        ],
    )
    if not rows:
        return summary
    return compose_sections(
        [
            summary,
            render_table("Checks", ["Name", "Status", "Detail"], rows),
        ]
    )


def _render_guide_text() -> str:
    return compose_sections(
        [
            render_kv_panel(
                "最短操作フロー",
                [
                    ("目的", "疎通確認とplan実行を最短で終える"),
                    ("推奨コマンド", "calt doctor / calt quickstart"),
                ],
            ),
            render_table(
                "手順",
                ["Step", "Command"],
                [
                    ["1", "calt guide"],
                    ["2", "calt doctor"],
                    ["3", "calt quickstart <plan_file> --goal <goal>"],
                    ["4", "必要時: calt logs search <session_id> --query step_executed"],
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


def _doctor_check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _doctor_error_detail(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        detail = exc.response.text.strip() or "request failed"
        return f"HTTP {status_code}: {_truncate(detail, limit=100)}"
    if isinstance(exc, httpx.HTTPError):
        return _truncate(str(exc), limit=100)
    return _truncate(f"{type(exc).__name__}: {exc}", limit=100)


def _doctor_finalize_payload(checks: list[dict[str, str]]) -> dict[str, Any]:
    counts = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    for check in checks:
        status = check.get("status")
        if status not in counts:
            status = "fail"
        counts[status] += 1
    return {
        "ok": counts["fail"] == 0,
        "counts": counts,
        "checks": checks,
    }


def _validate_base_url(base_url: str) -> tuple[bool, str]:
    try:
        parsed = httpx.URL(base_url)
    except Exception as exc:  # noqa: BLE001
        return False, f"invalid URL: {exc}"
    if parsed.scheme not in ("http", "https"):
        return False, f"unsupported scheme: {parsed.scheme or '(missing)'}"
    if not parsed.host:
        return False, "host is missing"
    return True, f"{parsed.scheme}://{parsed.host}"


async def _doctor_probe(
    checks: list[dict[str, str]],
    *,
    name: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
    success_detail: str | Callable[[dict[str, Any]], str],
) -> dict[str, Any] | None:
    try:
        payload = await operation()
    except Exception as exc:  # noqa: BLE001
        checks.append(_doctor_check(name, "fail", _doctor_error_detail(exc)))
        return None
    detail = success_detail(payload) if callable(success_detail) else success_detail
    checks.append(_doctor_check(name, "pass", detail))
    return payload


async def _run_doctor_operation(
    settings: CliSettings,
    client_factory: ClientFactory,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    base_url_ok, base_url_detail = _validate_base_url(settings.base_url)
    checks.append(_doctor_check("base_url", "pass" if base_url_ok else "fail", base_url_detail))

    token_ok = bool(settings.token.strip())
    checks.append(_doctor_check("token", "pass" if token_ok else "fail", "configured" if token_ok else "empty"))

    if not base_url_ok:
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
            checks.append(_doctor_check(name, "skip", "base_url is invalid"))
        return _doctor_finalize_payload(checks)

    try:
        async with client_factory(settings.base_url, settings.token) as client:
            tools_payload = await _doctor_probe(
                checks,
                name="daemon_connectivity",
                operation=client.list_tools,
                success_detail=lambda payload: (
                    f"tools endpoint reachable (items={len(payload.get('items', []))})"
                    if isinstance(payload.get("items"), list)
                    else "tools endpoint reachable"
                ),
            )

            tool_name: str | None = None
            if isinstance(tools_payload, dict):
                items = tools_payload.get("items")
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get("tool_name"):
                            tool_name = str(item["tool_name"])
                            break

            if tool_name is None:
                checks.append(_doctor_check("tools_permissions", "warn", "tool list is empty"))
            else:
                await _doctor_probe(
                    checks,
                    name="tools_permissions",
                    operation=lambda: client.get_tool_permissions(tool_name),
                    success_detail=f"{tool_name} permissions endpoint reachable",
                )

            session_payload = await _doctor_probe(
                checks,
                name="session_create",
                operation=lambda: client.create_session(goal="doctor"),
                success_detail=lambda payload: f"session_id={payload.get('id', '-')}",
            )

            session_id = ""
            if isinstance(session_payload, dict):
                session_id = str(session_payload.get("id") or "")

            if not session_id:
                for name in (
                    "plan_import",
                    "plan_approve",
                    "step_approve",
                    "step_execute",
                    "logs_search",
                    "artifacts_list",
                    "session_stop",
                ):
                    checks.append(_doctor_check(name, "skip", "session_create failed"))
                return _doctor_finalize_payload(checks)

            doctor_version = 1
            doctor_step_id = "step_doctor_ping"
            doctor_steps = [
                {
                    "id": doctor_step_id,
                    "title": "doctor ping",
                    "tool": "list_dir",
                    "inputs": {"path": "."},
                }
            ]

            import_payload = await _doctor_probe(
                checks,
                name="plan_import",
                operation=lambda: client.import_plan(
                    session_id,
                    version=doctor_version,
                    title="doctor connectivity plan",
                    steps=doctor_steps,
                    session_goal="doctor",
                ),
                success_detail="plan import endpoint reachable",
            )

            if import_payload is None:
                for name in ("plan_approve", "step_approve", "step_execute"):
                    checks.append(_doctor_check(name, "skip", "plan_import failed"))
            else:
                await _doctor_probe(
                    checks,
                    name="plan_approve",
                    operation=lambda: client.approve_plan(
                        session_id,
                        doctor_version,
                        approved_by="doctor",
                        source="doctor",
                    ),
                    success_detail="plan approve endpoint reachable",
                )
                await _doctor_probe(
                    checks,
                    name="step_approve",
                    operation=lambda: client.approve_step(
                        session_id,
                        doctor_step_id,
                        approved_by="doctor",
                        source="doctor",
                    ),
                    success_detail="step approve endpoint reachable",
                )
                await _doctor_probe(
                    checks,
                    name="step_execute",
                    operation=lambda: client.execute_step(session_id, doctor_step_id),
                    success_detail=lambda payload: (
                        f"step execute endpoint reachable (status={payload.get('status', '-')})"
                    ),
                )

            await _doctor_probe(
                checks,
                name="logs_search",
                operation=lambda: client.search_events(session_id, q="step"),
                success_detail=lambda payload: (
                    f"logs endpoint reachable (items={len(payload.get('items', []))})"
                    if isinstance(payload.get("items"), list)
                    else "logs endpoint reachable"
                ),
            )
            await _doctor_probe(
                checks,
                name="artifacts_list",
                operation=lambda: client.list_artifacts(session_id),
                success_detail=lambda payload: (
                    f"artifacts endpoint reachable (items={len(payload.get('items', []))})"
                    if isinstance(payload.get("items"), list)
                    else "artifacts endpoint reachable"
                ),
            )
            await _doctor_probe(
                checks,
                name="session_stop",
                operation=lambda: client.stop_session(session_id),
                success_detail=lambda payload: f"stop endpoint reachable (status={payload.get('status', '-')})",
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(_doctor_check("daemon_connectivity", "fail", _doctor_error_detail(exc)))

    return _doctor_finalize_payload(checks)


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

    @app.command("quickstart")
    def quickstart_command(
        ctx: typer.Context,
        plan_file: Path = typer.Argument(
            ...,
            exists=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Plan JSON file path.",
        ),
        goal: str | None = typer.Option(
            None,
            "--goal",
            help="Session goal. Defaults to plan session_goal or 'quickstart'.",
        ),
        approved_by: str = typer.Option("cli", "--approved-by", help="Approver ID."),
        source: str = typer.Option("cli", "--source", help="Approval source."),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        version, title, steps, plan_session_goal = _load_plan_payload(plan_file)
        resolved_goal = goal or plan_session_goal or "quickstart"
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: _run_flow_operation(
                client,
                goal=resolved_goal,
                version=version,
                title=title,
                steps=steps,
                plan_session_goal=plan_session_goal,
                approved_by=approved_by,
                source=source,
            ),
            as_json=json_output,
            renderer=_render_quickstart_payload,
        )

    @app.command("doctor")
    def doctor_command(
        ctx: typer.Context,
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        payload = anyio.run(_run_doctor_operation, settings, resolved_client_factory)
        _print_payload(payload, as_json=json_output, renderer=_render_doctor_payload)
        if not bool(payload.get("ok")):
            raise typer.Exit(code=1)

    @session_app.command("create")
    def session_create(
        ctx: typer.Context,
        goal: str | None = typer.Option(None, "--goal", help="Session goal."),
        mode: Literal["normal", "dry_run"] = typer.Option(
            "normal",
            "--mode",
            help="Session mode.",
        ),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.create_session(goal=goal, mode=mode),
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
        confirm_high_risk: bool = typer.Option(
            False,
            "--confirm-high-risk",
            help="Confirm execution for high-risk step.",
        ),
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON payload."),
    ) -> None:
        settings = _require_settings(ctx)
        _run_and_print(
            settings,
            resolved_client_factory,
            lambda client: client.execute_step(
                session_id,
                step_id,
                confirm_high_risk=confirm_high_risk,
            ),
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
