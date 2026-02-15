from __future__ import annotations

from pathlib import Path

_CGROUP_DOCKER_MARKERS: tuple[str, ...] = (
    "docker",
    "containerd",
    "kubepods",
    "podman",
)


def is_running_in_docker(
    *,
    dockerenv_path: str | Path = "/.dockerenv",
    cgroup_path: str | Path = "/proc/1/cgroup",
) -> bool:
    dockerenv = Path(dockerenv_path)
    if dockerenv.exists():
        return True

    cgroup = Path(cgroup_path)
    try:
        cgroup_text = cgroup.read_text(encoding="utf-8")
    except OSError:
        return False

    lowered = cgroup_text.lower()
    return any(marker in lowered for marker in _CGROUP_DOCKER_MARKERS)
