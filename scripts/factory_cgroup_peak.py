"""Save a oneshot's kernel memory peak before systemd disposes its cgroup."""

from __future__ import annotations

import json
from pathlib import Path


def read_cgroup_peak() -> dict[str, int]:
    paths = [line.split("::", 1)[1] for line in Path("/proc/self/cgroup").read_text().splitlines()
             if line.startswith("0::")]
    if len(paths) != 1:
        raise ValueError("CGROUP_V2_UNAVAILABLE")
    mount = Path("/sys/fs/cgroup").resolve()
    current = (mount / paths[0].lstrip("/")).resolve()
    current.relative_to(mount)
    peak = int((current / "memory.peak").read_text().strip())
    maximum = int((current / "memory.max").read_text().strip())
    if not 0 < peak <= maximum:
        raise ValueError("CGROUP_PEAK_UNAVAILABLE")
    return {"cgroup_memory_peak_bytes": peak, "cgroup_memory_max_bytes": maximum}


def main() -> None:
    try:
        result = read_cgroup_peak()
    except (OSError, ValueError):
        print(json.dumps({"resource_state": "UNKNOWN", "reason": "KERNEL_CGROUP_PEAK_UNAVAILABLE"}))
        raise SystemExit(2)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
