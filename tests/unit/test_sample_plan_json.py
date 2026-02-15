from __future__ import annotations

import json
from pathlib import Path


def test_sample_plan_has_minimum_importable_structure() -> None:
    sample_plan_path = Path(__file__).resolve().parents[2] / "examples" / "sample_plan.json"
    payload = json.loads(sample_plan_path.read_text(encoding="utf-8"))

    assert isinstance(payload, dict)
    assert {"version", "title", "steps"}.issubset(payload)
    assert isinstance(payload["version"], int)
    assert payload["version"] >= 1
    assert isinstance(payload["title"], str)
    assert payload["title"] != ""
    assert isinstance(payload["steps"], list)
    assert len(payload["steps"]) == 1

    step = payload["steps"][0]
    assert isinstance(step, dict)
    assert {"id", "title", "tool", "inputs", "timeout_sec"}.issubset(step)
    assert step["id"] == "step_list_workspace"
    assert step["tool"] == "list_dir"
    assert step["inputs"] == {"path": "."}
    assert isinstance(step["timeout_sec"], int)
    assert 1 <= step["timeout_sec"] <= 120
