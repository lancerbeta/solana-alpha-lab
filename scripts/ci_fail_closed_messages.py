"""Map derived-hash drift failures to one actionable CI/pre-commit line."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import TextIO

import yaml

ROOT = Path(__file__).resolve().parents[1]
TASK_CONTRACT_DIR = "docs/tasks"
TASK_CONTRACT_FRONTMATTER = re.compile(r"^---\n(?P<frontmatter>.*?)\n---", re.DOTALL)

DERIVED_HASH_DRIFT_MARKERS = (
    "canonical_catalog_hash_mismatch:",
    "sha256_mismatch:",
    "catalog_current_checkpoint_drift:",
    "navigation_projection_stale",
    "STALE_OUTPUTS:",
)

UV_RUN = "uv run --locked --managed-python python -B"
HARNESS_SYNC = f"{UV_RUN} scripts/harness_sync.py --apply"
RECOVERY_SUFFIX = "  # RECOVERY_FULL_ORACLE"


def is_derived_hash_drift(text: str) -> bool:
    return any(marker in text for marker in DERIVED_HASH_DRIFT_MARKERS)


def _expected_base_from_contract(relative: str, *, root: Path) -> str | None:
    if not relative.startswith(f"{TASK_CONTRACT_DIR}/") or not relative.endswith(".md"):
        return None
    path = root / relative
    if not path.is_file():
        return None
    match = TASK_CONTRACT_FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if match is None:
        return None
    metadata = yaml.safe_load(match.group("frontmatter"))
    if not isinstance(metadata, dict):
        return None
    binding = metadata.get("git_binding")
    if not isinstance(binding, dict):
        return None
    expected_base = binding.get("expected_base")
    if isinstance(expected_base, str) and re.fullmatch(r"[0-9a-f]{40}", expected_base):
        return expected_base
    return None


def _git_name_only_z(args: list[str], *, root: Path) -> list[str]:
    completed = subprocess.run(
        args,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        return []
    relatives: list[str] = []
    for item in completed.stdout.split(b"\0"):
        if not item:
            continue
        relative = item.decode("utf-8", errors="strict").replace("\\", "/")
        if relative.startswith(f"{TASK_CONTRACT_DIR}/") and relative.endswith(".md"):
            relatives.append(relative)
    return relatives


def _task_contract_relatives_for_repair(*, root: Path) -> set[str]:
    relatives = set(_git_name_only_z(
        ["git", "diff", "--cached", "--name-only", "--no-renames", "-z"],
        root=root,
    ))
    relatives.update(_git_name_only_z(
        ["git", "diff", "--name-only", "--no-renames", "-z", "HEAD"],
        root=root,
    ))
    merge_base = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if merge_base.returncode == 0:
        base = merge_base.stdout.decode("ascii", errors="strict").strip()
        if re.fullmatch(r"[0-9a-f]{40}", base):
            relatives.update(_git_name_only_z(
                [
                    "git",
                    "diff",
                    "--name-only",
                    "--no-renames",
                    "-z",
                    base,
                    "HEAD",
                    "--",
                    f"{TASK_CONTRACT_DIR}/",
                ],
                root=root,
            ))
    return relatives


def routine_harness_sync_base_ref(*, root: Path | None = None) -> str | None:
    """Single task expected_base when branch/staging context is unambiguous."""

    target = root or ROOT
    if not (target / ".git").is_dir():
        return None
    bases = {
        base
        for relative in _task_contract_relatives_for_repair(root=target)
        if (base := _expected_base_from_contract(relative, root=target)) is not None
    }
    if len(bases) == 1:
        return next(iter(bases))
    return None


def harness_sync_apply_command(*, base_ref: str | None = None, root: Path | None = None) -> str:
    resolved = base_ref if base_ref is not None else routine_harness_sync_base_ref(root=root)
    if resolved:
        return f"{HARNESS_SYNC} --base-ref {resolved}"
    return f"{HARNESS_SYNC}{RECOVERY_SUFFIX}"


def harness_sync_repair_suffix(*, root: Path | None = None) -> str:
    resolved = routine_harness_sync_base_ref(root=root)
    if resolved:
        return f"; run harness_sync.py --apply --base-ref {resolved}"
    return f"; run harness_sync.py --apply{RECOVERY_SUFFIX}"


def derived_hash_drift_summary(*, root: Path | None = None) -> str:
    return f"DERIVED_HASH_DRIFT: run {harness_sync_apply_command(root=root)}"


def emit_derived_hash_drift_summary(*, stream: TextIO | None = None, root: Path | None = None) -> None:
    print(derived_hash_drift_summary(root=root), file=stream or sys.stderr)
