from __future__ import annotations

from pathlib import Path

from calt.daemon.docker_env import is_running_in_docker


def test_is_running_in_docker_true_when_dockerenv_exists(tmp_path: Path) -> None:
    dockerenv = tmp_path / ".dockerenv"
    dockerenv.touch()
    cgroup = tmp_path / "cgroup"
    cgroup.write_text("", encoding="utf-8")

    assert is_running_in_docker(dockerenv_path=dockerenv, cgroup_path=cgroup) is True


def test_is_running_in_docker_true_when_cgroup_contains_marker(tmp_path: Path) -> None:
    dockerenv = tmp_path / ".dockerenv"
    cgroup = tmp_path / "cgroup"
    cgroup.write_text("1:name=systemd:/docker/abcdef\n", encoding="utf-8")

    assert is_running_in_docker(dockerenv_path=dockerenv, cgroup_path=cgroup) is True


def test_is_running_in_docker_false_without_markers(tmp_path: Path) -> None:
    dockerenv = tmp_path / ".dockerenv"
    cgroup = tmp_path / "cgroup"
    cgroup.write_text("1:name=systemd:/user.slice\n", encoding="utf-8")

    assert is_running_in_docker(dockerenv_path=dockerenv, cgroup_path=cgroup) is False
