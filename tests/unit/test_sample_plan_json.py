from __future__ import annotations

import json
from pathlib import Path

from calt.tools.readonly import is_allowlisted_command

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
REQUIRED_PLAN_KEYS = {"version", "title", "session_goal", "steps"}
REQUIRED_STEP_KEYS = {"id", "title", "tool", "inputs", "timeout_sec"}
ALLOWED_TOOLS = {
    "read_file",
    "list_dir",
    "run_shell_readonly",
    "write_file_preview",
    "write_file_apply",
    "apply_patch",
}
ALLOWED_RISKS = {"low", "medium", "high"}


def _load_sample_plans() -> dict[str, dict[str, object]]:
    plans: dict[str, dict[str, object]] = {}
    for path in sorted(EXAMPLES_DIR.glob("*_plan.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        plans[path.name] = payload
    assert "sample_plan.json" in plans
    return plans


def test_all_sample_plans_have_minimum_structure() -> None:
    plans = _load_sample_plans()
    assert len(plans) >= 4

    for name, payload in plans.items():
        assert REQUIRED_PLAN_KEYS.issubset(payload), name
        assert isinstance(payload["version"], int), name
        assert payload["version"] >= 1, name
        assert isinstance(payload["title"], str), name
        assert payload["title"] != "", name
        assert isinstance(payload["session_goal"], str), name
        assert payload["session_goal"] != "", name
        assert isinstance(payload["steps"], list), name
        assert payload["steps"], name

        for step in payload["steps"]:
            assert isinstance(step, dict), name
            assert REQUIRED_STEP_KEYS.issubset(step), name
            assert isinstance(step["id"], str), name
            assert step["id"] != "", name
            assert isinstance(step["title"], str), name
            assert step["title"] != "", name
            assert isinstance(step["tool"], str), name
            assert step["tool"] in ALLOWED_TOOLS, name
            assert isinstance(step["inputs"], dict), name
            assert isinstance(step["timeout_sec"], int), name
            assert step["timeout_sec"] > 0, name
            if "risk" in step:
                assert step["risk"] in ALLOWED_RISKS, name

            if step["tool"] == "run_shell_readonly":
                command = step["inputs"].get("command")
                assert isinstance(command, str), name
                assert is_allowlisted_command(command), name


def test_sample_plan_expectations() -> None:
    payload = _load_sample_plans()["sample_plan.json"]
    steps = payload["steps"]
    assert len(steps) == 1
    assert steps[0]["id"] == "step_list_workspace"
    assert steps[0]["tool"] == "list_dir"
    assert steps[0]["inputs"] == {"path": "."}


def test_workspace_overview_plan_expectations() -> None:
    payload = _load_sample_plans()["workspace_overview_plan.json"]
    steps = payload["steps"]
    assert len(steps) == 3
    assert [step["tool"] for step in steps] == ["list_dir", "list_dir", "read_file"]


def test_search_inspect_plan_expectations() -> None:
    payload = _load_sample_plans()["search_inspect_plan.json"]
    steps = payload["steps"]
    assert len(steps) == 3
    assert [step["tool"] for step in steps] == [
        "run_shell_readonly",
        "run_shell_readonly",
        "read_file",
    ]


def test_preview_only_write_plan_expectations() -> None:
    payload = _load_sample_plans()["preview_only_write_plan.json"]
    steps = payload["steps"]
    assert len(steps) == 2
    assert {step["tool"] for step in steps} == {"write_file_preview", "apply_patch"}
    for step in steps:
        if step["tool"] == "apply_patch":
            assert step["inputs"].get("mode") == "preview"
