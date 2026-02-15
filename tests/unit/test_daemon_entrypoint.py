from __future__ import annotations

from pathlib import Path

from calt.daemon.entrypoint import build_daemon_settings, parse_daemon_settings


def test_parse_daemon_settings_defaults() -> None:
    settings = parse_daemon_settings([])

    assert settings.db_path == (Path.cwd() / "data/calt.sqlite3").resolve()
    assert settings.data_root is None
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.reload is False


def test_parse_daemon_settings_custom_values(tmp_path: Path) -> None:
    db_path = tmp_path / "daemon.sqlite3"
    data_root = tmp_path / "data-root"

    settings = parse_daemon_settings(
        [
            "--db-path",
            str(db_path),
            "--data-root",
            str(data_root),
            "--host",
            "0.0.0.0",
            "--port",
            "9001",
            "--reload",
        ]
    )

    assert settings.db_path == db_path.resolve()
    assert settings.data_root == data_root.resolve()
    assert settings.host == "0.0.0.0"
    assert settings.port == 9001
    assert settings.reload is True


def test_build_daemon_settings_keeps_data_root_optional() -> None:
    settings = build_daemon_settings(
        db_path="relative.sqlite3",
        data_root=None,
        host="127.0.0.1",
        port=8000,
        reload=False,
    )

    assert settings.db_path == (Path.cwd() / "relative.sqlite3").resolve()
    assert settings.data_root is None
