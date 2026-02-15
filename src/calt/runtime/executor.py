from __future__ import annotations

import concurrent.futures
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from calt.tools import READONLY_TOOLS, apply_patch, write_file_apply, write_file_preview


class RuntimeArtifact(BaseModel):
    name: str
    kind: str = "json"
    payload: dict[str, Any]


class StepRunResult(BaseModel):
    status: Literal["succeeded", "failed"]
    output: dict[str, Any] | None = None
    error: str | None = None
    artifacts: list[RuntimeArtifact] = Field(default_factory=list)


class StepExecutor:
    def execute(self, *, tool: str, inputs: dict[str, Any], timeout: int) -> StepRunResult:
        bounded_timeout = max(1, int(timeout))
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._invoke, tool, dict(inputs), bounded_timeout)
                output = future.result(timeout=bounded_timeout)
        except concurrent.futures.TimeoutError:
            return StepRunResult(
                status="failed",
                error=f"tool timeout after {bounded_timeout}s",
            )
        except Exception as error:  # noqa: BLE001
            return StepRunResult(status="failed", error=str(error))

        return StepRunResult(
            status="succeeded",
            output=output,
            artifacts=[
                RuntimeArtifact(
                    name=f"{tool}_{uuid4().hex[:8]}.json",
                    kind="json",
                    payload=output,
                )
            ],
        )

    def _invoke(self, tool: str, inputs: dict[str, Any], timeout: int) -> dict[str, Any]:
        if tool in READONLY_TOOLS:
            if tool == "run_shell_readonly":
                inputs.setdefault("timeout_sec", min(timeout, 30))
            return READONLY_TOOLS[tool].invoke(inputs).model_dump(mode="json")

        if tool == "write_file_preview":
            return write_file_preview(
                workspace_root=self._require_input(inputs, "workspace_root"),
                path=self._require_input(inputs, "path"),
                content=self._require_input(inputs, "content"),
            )

        if tool == "write_file_apply":
            return write_file_apply(
                workspace_root=self._require_input(inputs, "workspace_root"),
                path=self._require_input(inputs, "path"),
                content=self._require_input(inputs, "content"),
                preview=inputs.get("preview"),
            )

        if tool == "apply_patch":
            return apply_patch(
                workspace_root=self._require_input(inputs, "workspace_root"),
                patch=self._require_input(inputs, "patch"),
                mode=self._require_input(inputs, "mode"),
                preview=inputs.get("preview"),
            )

        raise ValueError(f"unknown tool: {tool}")

    @staticmethod
    def _require_input(inputs: dict[str, Any], key: str) -> Any:
        if key not in inputs:
            raise ValueError(f"missing required input: {key}")
        return inputs[key]
