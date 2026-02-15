from pathlib import Path

import pytest

from calt.tools import (
    LIST_DIR_TOOL,
    READ_FILE_TOOL,
    RUN_SHELL_READONLY_TOOL,
    ListDirInput,
    PermissionProfile,
    ReadFileInput,
    RunShellReadonlyInput,
    is_allowlisted_command,
    list_dir,
    read_file,
    run_shell_readonly,
)


@pytest.mark.parametrize(
    "command",
    [
        "ls",
        "cat README.md",
        "rg TODO src",
        "find . -maxdepth 1",
        "git status --short",
        "git diff --stat",
        "python -m pytest -q tests/unit",
    ],
)
def test_is_allowlisted_command_accepts_configured_commands(command: str) -> None:
    assert is_allowlisted_command(command) is True


@pytest.mark.parametrize(
    "command",
    [
        "",
        "echo hello",
        "git log --oneline",
        "python -m pytest tests/unit",
    ],
)
def test_is_allowlisted_command_rejects_other_commands(command: str) -> None:
    assert is_allowlisted_command(command) is False


def test_read_file_reads_content_from_workspace(tmp_path: Path) -> None:
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello", encoding="utf-8")

    result = read_file(ReadFileInput(workspace_root=str(tmp_path), path="note.txt"))

    assert result.path == "note.txt"
    assert result.content == "hello"


def test_read_file_rejects_path_outside_workspace(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="workspace_root"):
        read_file(ReadFileInput(workspace_root=str(tmp_path), path="../secret.txt"))


def test_list_dir_returns_sorted_entries(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a").mkdir()

    result = list_dir(ListDirInput(workspace_root=str(tmp_path)))

    assert [entry.name for entry in result.entries] == ["a", "b.txt"]
    assert [entry.is_dir for entry in result.entries] == [True, False]


def test_run_shell_readonly_runs_allowlisted_command(tmp_path: Path) -> None:
    (tmp_path / "sample.txt").write_text("sample", encoding="utf-8")

    result = run_shell_readonly(
        RunShellReadonlyInput(workspace_root=str(tmp_path), command="ls")
    )

    assert result.exit_code == 0
    assert "sample.txt" in result.stdout


def test_run_shell_readonly_rejects_non_allowlisted_command(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allowlisted"):
        run_shell_readonly(
            RunShellReadonlyInput(workspace_root=str(tmp_path), command="echo test")
        )


def test_tool_definitions_expose_permission_profiles_and_models(tmp_path: Path) -> None:
    (tmp_path / "memo.txt").write_text("memo", encoding="utf-8")

    result = READ_FILE_TOOL.invoke({"workspace_root": str(tmp_path), "path": "memo.txt"})

    assert result.content == "memo"
    assert READ_FILE_TOOL.permission_profile == PermissionProfile.workspace_read
    assert LIST_DIR_TOOL.permission_profile == PermissionProfile.workspace_read
    assert RUN_SHELL_READONLY_TOOL.permission_profile == PermissionProfile.shell_readonly
