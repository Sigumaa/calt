from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import uvicorn

from .api import create_app


@dataclass(frozen=True)
class DaemonSettings:
    db_path: Path
    data_root: Path | None
    host: str
    port: int
    reload: bool


def _resolve_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def build_daemon_settings(
    *,
    db_path: str,
    data_root: str | None,
    host: str,
    port: int,
    reload: bool,
) -> DaemonSettings:
    return DaemonSettings(
        db_path=_resolve_path(db_path),
        data_root=_resolve_path(data_root) if data_root is not None else None,
        host=host,
        port=port,
        reload=reload,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calt-daemon",
        description="Run calt daemon API server.",
    )
    parser.add_argument(
        "--db-path",
        default="data/calt.sqlite3",
        help="SQLite database file path.",
    )
    parser.add_argument(
        "--data-root",
        default=None,
        help="Data root directory path.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable development auto-reload.",
    )
    return parser


def parse_daemon_settings(argv: Sequence[str] | None = None) -> DaemonSettings:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return build_daemon_settings(
        db_path=args.db_path,
        data_root=args.data_root,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def run(argv: Sequence[str] | None = None) -> None:
    settings = parse_daemon_settings(argv)
    app = create_app(settings.db_path, data_root=settings.data_root)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
