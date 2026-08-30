"""Map derived-hash drift failures to one actionable CI/pre-commit line."""

from __future__ import annotations

import sys
from typing import TextIO

DERIVED_HASH_DRIFT_MARKERS = (
    "canonical_catalog_hash_mismatch:",
    "sha256_mismatch:",
    "catalog_current_checkpoint_drift:",
    "navigation_projection_stale",
    "STALE_OUTPUTS:",
)

HARNESS_SYNC_APPLY = (
    "uv run --locked --managed-python python -B scripts/harness_sync.py --apply"
)


def is_derived_hash_drift(text: str) -> bool:
    return any(marker in text for marker in DERIVED_HASH_DRIFT_MARKERS)


def derived_hash_drift_summary() -> str:
    return f"DERIVED_HASH_DRIFT: run {HARNESS_SYNC_APPLY}"


def emit_derived_hash_drift_summary(*, stream: TextIO | None = None) -> None:
    print(derived_hash_drift_summary(), file=stream or sys.stderr)
