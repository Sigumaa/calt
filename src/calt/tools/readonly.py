from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, Field

from .interfaces import PermissionProfile, ToolDefinition

ALLOWLIST_COMMAND_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("ls",),
    ("cat",),
    ("rg",),
    ("find",),
    ("git", "status"),
    ("git", "diff"),
    ("python", "-m", "pytest", "-q"),
)


def _ensure_workspace_root(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("workspace_root must be an existing directory")
    return root


def _resolve_workspace_path(workspace_root: Path, path: str) -> Path:
    resolved_path = (workspace_root / path).resolve()
    if not resolved_path.is_relative_to(workspace_root):
        raise ValueError("path must stay within workspace_root")
    return resolved_path


def _tokens_match_allowlist(tokens: Sequence[str]) -> bool:
    return any(
        len(tokens) >= len(prefix) and tuple(tokens[: len(prefix)]) == prefix
        for prefix in ALLOWLIST_COMMAND_PREFIXES
    )


def is_allowlisted_command(command: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens:
        return False
    return _tokens_match_allowlist(tokens)


def _parse_allowlisted_command(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError as error:
        raise ValueError("command could not be parsed") from error

    if not tokens:
        raise ValueError("command must not be empty")
    if not _tokens_match_allowlist(tokens):
        raise ValueError(f"command is not allowlisted: {command}")
    return tokens


class ReadFileInput(BaseModel):
    workspace_root: str
    path: str = Field(min_length=1)
    encoding: str = "utf-8"


class ReadFileOutput(BaseModel):
    path: str
    content: str


def read_file(params: ReadFileInput) -> ReadFileOutput:
    workspace_root = _ensure_workspace_root(params.workspace_root)
    target_path = _resolve_workspace_path(workspace_root, params.path)
    content = target_path.read_text(encoding=params.encoding)
    return ReadFileOutput(path=params.path, content=content)


class DirEntry(BaseModel):
    name: str
    is_dir: bool


class ListDirInput(BaseModel):
    workspace_root: str
    path: str = "."


class ListDirOutput(BaseModel):
    path: str
    entries: list[DirEntry]


def list_dir(params: ListDirInput) -> ListDirOutput:
    workspace_root = _ensure_workspace_root(params.workspace_root)
    target_path = _resolve_workspace_path(workspace_root, params.path)
    if not target_path.is_dir():
        raise ValueError("target path is not a directory")

    entries = [
        DirEntry(name=entry.name, is_dir=entry.is_dir())
        for entry in sorted(target_path.iterdir(), key=lambda item: item.name)
    ]
    return ListDirOutput(path=params.path, entries=entries)


class RunShellReadonlyInput(BaseModel):
    workspace_root: str
    command: str = Field(min_length=1)
    timeout_sec: int = Field(default=30, ge=1, le=30)


class RunShellReadonlyOutput(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str


def run_shell_readonly(params: RunShellReadonlyInput) -> RunShellReadonlyOutput:
    workspace_root = _ensure_workspace_root(params.workspace_root)
    tokens = _parse_allowlisted_command(params.command)
    completed = subprocess.run(
        tokens,
        cwd=workspace_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=params.timeout_sec,
    )
    return RunShellReadonlyOutput(
        command=params.command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


READ_FILE_TOOL = ToolDefinition(
    name="read_file",
    description="Read a file from session workspace.",
    permission_profile=PermissionProfile.workspace_read,
    input_model=ReadFileInput,
    output_model=ReadFileOutput,
    handler=read_file,
)

LIST_DIR_TOOL = ToolDefinition(
    name="list_dir",
    description="List files in session workspace.",
    permission_profile=PermissionProfile.workspace_read,
    input_model=ListDirInput,
    output_model=ListDirOutput,
    handler=list_dir,
)

RUN_SHELL_READONLY_TOOL = ToolDefinition(
    name="run_shell_readonly",
    description="Run allowlisted readonly shell commands.",
    permission_profile=PermissionProfile.shell_readonly,
    input_model=RunShellReadonlyInput,
    output_model=RunShellReadonlyOutput,
    handler=run_shell_readonly,
)

READONLY_TOOLS: dict[str, ToolDefinition] = {
    READ_FILE_TOOL.name: READ_FILE_TOOL,
    LIST_DIR_TOOL.name: LIST_DIR_TOOL,
    RUN_SHELL_READONLY_TOOL.name: RUN_SHELL_READONLY_TOOL,
}
