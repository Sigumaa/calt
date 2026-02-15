from __future__ import annotations

import difflib
import hashlib
import re
from pathlib import Path
from typing import Any, Literal, Mapping

_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,\d+)? \+(?P<new_start>\d+)(?:,\d+)? @@"
)


class ToolInputError(ValueError):
    """Raised when tool input is invalid."""


class WorkspaceBoundaryError(ToolInputError):
    """Raised when a path points outside the workspace."""


class PreviewMismatchError(ToolInputError):
    """Raised when provided preview data does not match current file state."""


class PatchFormatError(ToolInputError):
    """Raised when patch text is malformed or unsupported."""


class PatchApplyError(ToolInputError):
    """Raised when patch hunk cannot be applied to current content."""


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _resolve_workspace_path(
    workspace_root: str | Path,
    relative_path: str,
) -> tuple[Path, Path, str]:
    root = Path(workspace_root).resolve()
    target = (root / relative_path).resolve()
    try:
        canonical = target.relative_to(root).as_posix()
    except ValueError as exc:
        raise WorkspaceBoundaryError(
            f"path '{relative_path}' is outside workspace '{root}'"
        ) from exc
    return root, target, canonical


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _build_diff(before: str, after: str, relative_path: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm="",
        )
    )


def _build_preview_payload(path: str, before: str, after: str) -> dict[str, Any]:
    return {
        "path": path,
        "changed": before != after,
        "diff": _build_diff(before, after, path),
        "old_sha256": _sha256(before),
        "new_sha256": _sha256(after),
    }


def _validate_preview(
    *,
    provided: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> None:
    comparable_keys = ("path", "diff", "new_sha256")
    for key in comparable_keys:
        if provided.get(key) != actual.get(key):
            raise PreviewMismatchError(
                "provided preview does not match current file state"
            )


def _compute_write_preview(
    workspace_root: str | Path,
    path: str,
    content: str,
) -> tuple[Path, dict[str, Any]]:
    _, target, canonical = _resolve_workspace_path(workspace_root, path)
    before = _read_text_if_exists(target)
    payload = _build_preview_payload(canonical, before, content)
    return target, payload


def write_file_preview(
    workspace_root: str | Path,
    path: str,
    content: str,
) -> dict[str, Any]:
    _, payload = _compute_write_preview(workspace_root, path, content)
    return payload


def write_file_apply(
    workspace_root: str | Path,
    path: str,
    content: str,
    *,
    preview: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    target, actual_preview = _compute_write_preview(workspace_root, path, content)
    if preview is not None:
        _validate_preview(provided=preview, actual=actual_preview)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {**actual_preview, "applied": True}


def _normalize_patch_path(raw_label: str) -> str:
    token = raw_label.strip().split("\t", maxsplit=1)[0].split(" ", maxsplit=1)[0]
    if token.startswith("a/") or token.startswith("b/"):
        token = token[2:]
    return token


def _parse_single_file_patch(patch: str) -> tuple[str, list[tuple[int, list[str]]]]:
    lines = patch.splitlines()
    if not lines:
        raise PatchFormatError("patch is empty")

    header_index = -1
    for idx, line in enumerate(lines):
        if line.startswith("--- "):
            header_index = idx
            break
    if header_index < 0 or header_index + 1 >= len(lines):
        raise PatchFormatError("patch must include ---/+++ headers")

    next_line = lines[header_index + 1]
    if not next_line.startswith("+++ "):
        raise PatchFormatError("patch must include ---/+++ headers")

    old_path = _normalize_patch_path(lines[header_index][4:])
    new_path = _normalize_patch_path(next_line[4:])
    if new_path == "/dev/null":
        raise PatchFormatError("file deletion is not supported")

    target_path = new_path if new_path != "/dev/null" else old_path
    if target_path in {"", "/dev/null"}:
        raise PatchFormatError("patch target path is invalid")

    hunks: list[tuple[int, list[str]]] = []
    index = header_index + 2
    while index < len(lines):
        line = lines[index]
        if line.startswith("diff --git ") or line.startswith("index "):
            index += 1
            continue
        if line.startswith("--- "):
            raise PatchFormatError("multiple file patches are not supported")
        if not line.startswith("@@ "):
            index += 1
            continue

        match = _HUNK_HEADER_RE.match(line)
        if match is None:
            raise PatchFormatError(f"invalid hunk header: {line}")
        old_start = int(match.group("old_start"))
        index += 1

        hunk_lines: list[str] = []
        while index < len(lines):
            candidate = lines[index]
            if candidate.startswith("@@ ") or candidate.startswith("--- "):
                break
            hunk_lines.append(candidate)
            index += 1
        hunks.append((old_start, hunk_lines))

    if not hunks:
        raise PatchFormatError("patch must include at least one hunk")
    return target_path, hunks


def _apply_hunks(before: str, hunks: list[tuple[int, list[str]]]) -> str:
    old_lines = before.splitlines()
    result: list[str] = []
    cursor = 0

    for old_start, hunk_lines in hunks:
        start_index = max(old_start - 1, 0)
        if start_index < cursor or start_index > len(old_lines):
            raise PatchApplyError("invalid hunk start position")

        result.extend(old_lines[cursor:start_index])
        cursor = start_index

        for raw_line in hunk_lines:
            if raw_line.startswith("\\ No newline at end of file"):
                continue
            if not raw_line:
                raise PatchApplyError("invalid hunk line")

            op = raw_line[0]
            text = raw_line[1:]
            if op == " ":
                if cursor >= len(old_lines) or old_lines[cursor] != text:
                    raise PatchApplyError("context line does not match current content")
                result.append(text)
                cursor += 1
            elif op == "-":
                if cursor >= len(old_lines) or old_lines[cursor] != text:
                    raise PatchApplyError("deletion line does not match current content")
                cursor += 1
            elif op == "+":
                result.append(text)
            else:
                raise PatchApplyError(f"unsupported hunk operation: {op}")

    result.extend(old_lines[cursor:])
    after = "\n".join(result)
    if before.endswith("\n") and after and not after.endswith("\n"):
        after += "\n"
    return after


def _compute_patch_preview(
    workspace_root: str | Path,
    patch: str,
) -> tuple[Path, str, dict[str, Any]]:
    patch_path, hunks = _parse_single_file_patch(patch)
    _, target, canonical = _resolve_workspace_path(workspace_root, patch_path)
    before = _read_text_if_exists(target)
    after = _apply_hunks(before, hunks)
    payload = _build_preview_payload(canonical, before, after)
    return target, after, payload


def apply_patch(
    workspace_root: str | Path,
    patch: str,
    mode: Literal["preview", "apply"],
    *,
    preview: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if mode not in {"preview", "apply"}:
        raise ToolInputError("mode must be 'preview' or 'apply'")

    target, after, actual_preview = _compute_patch_preview(workspace_root, patch)
    if mode == "preview":
        return actual_preview

    if preview is not None:
        _validate_preview(provided=preview, actual=actual_preview)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(after, encoding="utf-8")
    return {**actual_preview, "applied": True}
