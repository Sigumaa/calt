from __future__ import annotations

from pathlib import Path

from calt.runtime import StepExecutor


def test_step_executor_runs_readonly_tool_and_generates_artifact(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hello", encoding="utf-8")

    result = StepExecutor().execute(
        tool="list_dir",
        inputs={"workspace_root": str(tmp_path), "path": "."},
        timeout=30,
    )

    assert result.status == "succeeded"
    assert result.error is None
    assert result.output is not None
    assert result.output["path"] == "."
    assert len(result.artifacts) == 1
    assert result.artifacts[0].kind == "json"


def test_step_executor_returns_failed_for_unknown_tool(tmp_path: Path) -> None:
    result = StepExecutor().execute(
        tool="unknown_tool",
        inputs={"workspace_root": str(tmp_path)},
        timeout=30,
    )

    assert result.status == "failed"
    assert "unknown tool" in (result.error or "")
    assert result.output is None
    assert result.artifacts == []
