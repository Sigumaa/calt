from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_codex_ops.sh"
EXPECTED_FILES = [
    "AGENTS.md",
    ".codex/PROJECT_PLAN.md",
    ".codex/PLAN_PROGRESS.md",
    ".codex/STARTUP_CHECKLIST.md",
    ".codex/DOCKER_TESTING.md",
    ".github/workflows/precommit.yml",
]


def _run_bootstrap(target_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), "--root", str(target_root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_bootstrap_creates_required_files_for_empty_directory(tmp_path: Path) -> None:
    result = _run_bootstrap(tmp_path)

    assert result.returncode == 0, result.stderr
    for relative_path in EXPECTED_FILES:
        assert (tmp_path / relative_path).exists(), relative_path
        assert f"CREATED: {relative_path}" in result.stdout

    agents_body = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Skills" not in agents_body


def test_bootstrap_keeps_existing_files_and_prints_skipped(tmp_path: Path) -> None:
    existing_agents = tmp_path / "AGENTS.md"
    existing_agents.write_text("# custom agents\n", encoding="utf-8")

    existing_workflow = tmp_path / ".github" / "workflows" / "precommit.yml"
    existing_workflow.parent.mkdir(parents=True, exist_ok=True)
    existing_workflow.write_text("name: keep-existing\n", encoding="utf-8")

    result = _run_bootstrap(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "SKIPPED: AGENTS.md" in result.stdout
    assert "SKIPPED: .github/workflows/precommit.yml" in result.stdout
    assert existing_agents.read_text(encoding="utf-8") == "# custom agents\n"
    assert existing_workflow.read_text(encoding="utf-8") == "name: keep-existing\n"

    for relative_path in EXPECTED_FILES:
        assert (tmp_path / relative_path).exists(), relative_path
