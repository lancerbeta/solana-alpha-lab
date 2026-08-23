"""Exact-SHA live release for the non-git Factory deploy root.

Deploy model on factory-remote-ops:
  /opt/solana-alpha-lab          — runtime tree (no .git)
  .factory_deploy_sha            — exact 40-hex pin
  local/                         — preserved operational state

Release uses git archive of an exact SHA into a staging directory, then rsync
into the deploy root while preserving local/ and secrets outside the tree.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
import sys

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.live_ops_hardening import LiveOpsHardeningError, _now

DEPLOY_SHA_NAME = ".factory_deploy_sha"
UNITS = [
    "factory-v1-workbench.service",
    "factory-remote-health.service",
    "factory-paper-heartbeat.timer",
    "factory-remote-backup.timer",
]
PRESERVE_NAMES = frozenset({"local", ".venv", DEPLOY_SHA_NAME})


def _run(cmd: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise LiveOpsHardeningError(
            f"CMD_FAILED:{' '.join(cmd)}:{completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout.strip()


def read_deploy_sha(root: Path) -> str | None:
    path = root / DEPLOY_SHA_NAME
    if path.is_file() is False:
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def write_deploy_sha(root: Path, sha: str) -> None:
    if len(sha) != 40:
        raise LiveOpsHardeningError("EXACT_SHA_REQUIRED")
    (root / DEPLOY_SHA_NAME).write_text(sha + "\n", encoding="utf-8")


def systemctl(*args: str) -> str:
    return _run(["sudo", "systemctl", *args])


def stop_units() -> None:
    for unit in UNITS:
        systemctl("stop", unit)


def start_units() -> None:
    for unit in UNITS:
        systemctl("start", unit)


def uv_sync(root: Path) -> None:
    _run(["sudo", "/usr/bin/uv", "sync", "--locked"], cwd=root)


def doctor(root: Path) -> dict[str, Any]:
    raw = _run(
        [
            "sudo",
            "/usr/bin/uv",
            "run",
            "--locked",
            "--managed-python",
            "python",
            "-B",
            "scripts/factory_remote_doctor.py",
        ],
        cwd=root,
    )
    return json.loads(raw)


def archive_sha_to_staging(*, repo: Path, sha: str, staging: Path) -> None:
    import io
    import tarfile

    if len(sha) != 40:
        raise LiveOpsHardeningError("EXACT_SHA_REQUIRED")
    staging.mkdir(parents=True, exist_ok=True)
    _run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=repo)
    completed = subprocess.run(
        ["git", "archive", "--format=tar", sha],
        cwd=str(repo),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise LiveOpsHardeningError(
            f"GIT_ARCHIVE_FAILED:{completed.stderr.decode('utf-8', errors='replace')}"
        )
    with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:") as tar:
        tar.extractall(path=staging, filter="data")


def sync_staging_into_deploy(*, staging: Path, deploy_root: Path) -> list[str]:
    if staging.is_dir() is False:
        raise LiveOpsHardeningError("STAGING_MISSING")
    deploy_root.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    # Remove tracked paths that should refresh, preserving local/ and .venv.
    for child in list(deploy_root.iterdir()):
        if child.name in PRESERVE_NAMES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        changed.append(f"removed:{child.name}")
    for child in staging.iterdir():
        dest = deploy_root / child.name
        if child.is_dir():
            shutil.copytree(child, dest, dirs_exist_ok=False)
        else:
            shutil.copy2(child, dest)
        changed.append(f"copied:{child.name}")
    return changed


def deploy_exact_sha(
    *,
    repo: Path,
    deploy_root: Path,
    sha: str,
    sync_env: bool = True,
    restart: bool = True,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="factory-release-") as tmp:
        staging = Path(tmp) / sha
        archive_sha_to_staging(repo=repo, sha=sha, staging=staging)
        if restart:
            stop_units()
        changed = sync_staging_into_deploy(staging=staging, deploy_root=deploy_root)
        write_deploy_sha(deploy_root, sha)
        if sync_env:
            uv_sync(deploy_root)
        if restart:
            start_units()
        packet = doctor(deploy_root) if restart else {}
    return {
        "sha": sha,
        "deploy_root": str(deploy_root),
        "changed": changed,
        "doctor_verdict": packet.get("verdict"),
        "at": _now(),
    }


def release_sequence(
    *,
    repo: Path,
    deploy_root: Path,
    target_sha: str,
    previous_sha: str,
    sync_env: bool = True,
) -> dict[str, Any]:
    if target_sha == previous_sha:
        raise LiveOpsHardeningError("TARGET_EQUALS_PREVIOUS")
    start = read_deploy_sha(deploy_root)
    steps: list[dict[str, Any]] = [{"step": "START", "sha": start, "at": _now()}]

    target = deploy_exact_sha(
        repo=repo, deploy_root=deploy_root, sha=target_sha, sync_env=sync_env, restart=True
    )
    steps.append({"step": "DEPLOY_TARGET", **target})

    rolled = deploy_exact_sha(
        repo=repo, deploy_root=deploy_root, sha=previous_sha, sync_env=sync_env, restart=True
    )
    steps.append({"step": "ROLLBACK_PREVIOUS", **rolled})

    forward = deploy_exact_sha(
        repo=repo, deploy_root=deploy_root, sha=target_sha, sync_env=sync_env, restart=True
    )
    steps.append({"step": "FORWARD_RESTORE", **forward})

    final = read_deploy_sha(deploy_root)
    if final != target_sha:
        raise LiveOpsHardeningError("FINAL_NOT_TARGET")
    return {
        "live_deploy_rollback": True,
        "live_forward_restore": True,
        "left_on_rollback_sha": False,
        "start_sha": start,
        "target_sha": target_sha,
        "previous_sha": previous_sha,
        "final_sha": final,
        "steps": steps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="Git repository with object SHAs")
    parser.add_argument("--deploy-root", type=Path, default=Path("/opt/solana-alpha-lab"))
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--previous-sha", required=True)
    parser.add_argument("--skip-uv-sync", action="store_true")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = release_sequence(
        repo=args.repo.resolve(),
        deploy_root=args.deploy_root.resolve(),
        target_sha=args.target_sha,
        previous_sha=args.previous_sha,
        sync_env=not args.skip_uv_sync,
    )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LiveOpsHardeningError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(2) from exc
