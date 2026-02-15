from __future__ import annotations

from pathlib import Path

import pytest

from calt.tools import (
    PreviewMismatchError,
    WorkspaceBoundaryError,
    apply_patch,
    write_file_apply,
    write_file_preview,
)


def _create_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def test_write_file_preview_is_non_destructive(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    target = workspace / "memo.txt"
    target.write_text("before\n", encoding="utf-8")

    preview = write_file_preview(workspace, "memo.txt", "after\n")

    assert preview["changed"] is True
    assert "-before" in preview["diff"]
    assert "+after" in preview["diff"]
    assert target.read_text(encoding="utf-8") == "before\n"


def test_write_file_apply_writes_content_after_preview(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    target = workspace / "memo.txt"
    target.write_text("before\n", encoding="utf-8")
    preview = write_file_preview(workspace, "memo.txt", "after\n")

    result = write_file_apply(workspace, "memo.txt", "after\n", preview=preview)

    assert result["applied"] is True
    assert target.read_text(encoding="utf-8") == "after\n"


def test_write_file_apply_rejects_outside_workspace(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)

    with pytest.raises(WorkspaceBoundaryError):
        write_file_preview(workspace, "../outside.txt", "x")
    with pytest.raises(WorkspaceBoundaryError):
        write_file_apply(workspace, "../outside.txt", "x")


def test_apply_patch_preview_is_non_destructive(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    target = workspace / "patch_target.txt"
    target.write_text("before\n", encoding="utf-8")
    patch = """--- a/patch_target.txt
+++ b/patch_target.txt
@@ -1 +1 @@
-before
+after
"""

    preview = apply_patch(workspace, patch, mode="preview")

    assert preview["changed"] is True
    assert "-before" in preview["diff"]
    assert "+after" in preview["diff"]
    assert target.read_text(encoding="utf-8") == "before\n"


def test_apply_patch_apply_writes_after_preview(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    target = workspace / "patch_target.txt"
    target.write_text("before\n", encoding="utf-8")
    patch = """--- a/patch_target.txt
+++ b/patch_target.txt
@@ -1 +1 @@
-before
+after
"""
    preview = apply_patch(workspace, patch, mode="preview")

    result = apply_patch(workspace, patch, mode="apply", preview=preview)

    assert result["applied"] is True
    assert target.read_text(encoding="utf-8") == "after\n"


def test_apply_patch_rejects_outside_workspace(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    patch = """--- /dev/null
+++ b/../outside.txt
@@ -0,0 +1 @@
+x
"""

    with pytest.raises(WorkspaceBoundaryError):
        apply_patch(workspace, patch, mode="preview")


def test_write_file_apply_rejects_mismatched_preview(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    preview = write_file_preview(workspace, "memo.txt", "after\n")
    wrong_preview = {**preview, "new_sha256": "invalid"}

    with pytest.raises(PreviewMismatchError):
        write_file_apply(workspace, "memo.txt", "after\n", preview=wrong_preview)
