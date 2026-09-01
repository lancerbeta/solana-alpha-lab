"""Map derived-hash drift failures to one actionable CI/pre-commit line."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

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


def routine_harness_sync_base_ref(*, root: Path | None = None) -> str | None:
    from harness_sync import routine_harness_sync_base_ref as resolve

    return resolve(root=root)


def harness_sync_apply_command(*, base_ref: str | None = None, root: Path | None = None) -> str:
    resolved = base_ref if base_ref is not None else routine_harness_sync_base_ref(root=root)
    if resolved:
        return f"{HARNESS_SYNC} --base-ref {resolved}"
    return f"{HARNESS_SYNC}{RECOVERY_SUFFIX}"


def harness_sync_repair_suffix(*, root: Path | None = None) -> str:
    from harness_sync import harness_sync_repair_suffix as suffix

    return suffix(root=root)


def derived_hash_drift_summary(*, root: Path | None = None) -> str:
    return f"DERIVED_HASH_DRIFT: run {harness_sync_apply_command(root=root)}"


def emit_derived_hash_drift_summary(*, stream: TextIO | None = None, root: Path | None = None) -> None:
    print(derived_hash_drift_summary(root=root), file=stream or sys.stderr)
