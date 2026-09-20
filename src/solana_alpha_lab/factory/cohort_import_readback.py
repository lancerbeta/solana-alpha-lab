"""Operational cohort import readback for the owner publish/import loop.

Not a Forge input receipt. Durable payload never carries absolute machine paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.data_root import instance_fingerprint
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    CORPUS_DATASET_ID,
    load_live_corpus_lineage,
)

PASS_ALREADY_PRESENT_EXACT = "PASS_ALREADY_PRESENT_EXACT"
STOP_IDENTITY_CONFLICT = "STOP_IDENTITY_CONFLICT"
_IDENTITY_CONFLICT_CODES = frozenset(
    {
        "COHORT_ALREADY_IMPORTED",
        "CANONICAL_TARGET_CONFLICT",
        "IDENTITY_CONFLICT",
        "IMPORT_CONFLICT",
    }
)


def owner_import_terminal(code_or_status: str) -> str:
    if code_or_status == "IDEMPOTENT_REIMPORT":
        return PASS_ALREADY_PRESENT_EXACT
    if code_or_status in _IDENTITY_CONFLICT_CODES:
        return STOP_IDENTITY_CONFLICT
    return code_or_status


def build_cohort_import_readback(
    data_root: Path,
    *,
    lineage: Mapping[str, Any] | None = None,
    fingerprint: str | None = None,
) -> dict[str, Any]:
    loaded = dict(lineage) if lineage is not None else load_live_corpus_lineage(data_root)
    raw_cohorts = loaded.get("cohorts")
    groups: dict[str, list[dict[str, Any]]] = {}
    if isinstance(raw_cohorts, list):
        for item in raw_cohorts:
            if not isinstance(item, Mapping):
                continue
            cohort_id = str(item.get("cohort_id") or "")
            if not cohort_id:
                continue
            groups.setdefault(cohort_id, []).append(dict(item))

    visible: list[dict[str, Any]] = []
    duplicate_count = 0
    for cohort_id, group in sorted(groups.items()):
        lineage_count = len(group)
        if lineage_count > 1:
            duplicate_count += lineage_count - 1
        latest = group[-1]
        source = latest.get("source_sha256")
        if not isinstance(source, str) or not source:
            source = None
        visible.append(
            {
                "cohort_id": cohort_id,
                "release_id": latest.get("release_id"),
                "source_sha256": source,
                "schedule_sha256": latest.get("schedule_sha256"),
                "lineage_count": lineage_count,
                "status": "PRESENT_ONCE" if lineage_count == 1 else "DUPLICATE",
            }
        )

    integrity = "PASS" if duplicate_count == 0 else "DUPLICATE_LINEAGE"
    if not visible:
        next_action = "IMPORT_VERIFIED_RELEASE"
    elif integrity == "PASS":
        next_action = "STOP_BEFORE_HYPOTHESIS_FORGE"
    else:
        next_action = STOP_IDENTITY_CONFLICT
    return {
        "schema": "smial.cohort-import-readback",
        "schema_version": "1.0",
        "data_root_instance_fingerprint_sha256": fingerprint
        or instance_fingerprint(Path(data_root)),
        "corpus_dataset_id": loaded.get("corpus_dataset_id") or CORPUS_DATASET_ID,
        "corpus_version": loaded.get("current_corpus_version"),
        "current_dataset_manifest_id": loaded.get("current_dataset_manifest_id"),
        "visible_cohorts": visible,
        "lineage_integrity": integrity,
        "duplicate_cohort_count": duplicate_count,
        "next_owner_action": next_action,
    }
