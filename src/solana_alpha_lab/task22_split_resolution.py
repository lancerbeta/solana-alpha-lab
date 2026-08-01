"""Consumer-specific, outcome-blind TASK-22 split resolution."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


JsonObject = dict[str, Any]
ATOM_ID = "T22-A5_CONSUMER_TIME_PROFILE_AND_SPLIT_RESOLUTION_V1"
PROFILE_PATH = "configs/task22_task23_consumer_time_profile_v1.yaml"
SCHEMA_PATH = "catalog/schemas/task22_split_resolution.schema.json"
SPLIT_PATH = "docs/evidence/task22/dataset_split_manifest_v2.json"
LEDGER_PATH = "docs/evidence/task22/holdout_access_ledger_v2.json"


class Task22ResolutionError(RuntimeError):
    """The consumer-specific split cannot be resolved safely."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")


def artifact_bytes(value: object) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_yaml(path: Path) -> JsonObject:
    value = yaml.safe_load(path.read_bytes())
    if not isinstance(value, dict):
        raise Task22ResolutionError(f"yaml_root_not_mapping:{path.as_posix()}")
    return value


def load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise Task22ResolutionError(f"json_root_not_mapping:{path.as_posix()}")
    return value


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def validate_inputs(repository_root: Path, profile: JsonObject) -> None:
    bindings = [
        profile["accepted_baseline"]["a4_receipt"],
        profile["accepted_baseline"]["parent_split"],
        profile["accepted_baseline"]["parent_ledger"],
        *profile["frozen_timing_inputs"],
    ]
    for binding in bindings:
        path = repository_root / binding["path"]
        if not path.is_file():
            raise Task22ResolutionError(f"frozen_input_missing:{binding['path']}")
        if sha256_file(path) != binding["sha256"]:
            raise Task22ResolutionError(
                f"frozen_input_hash_drift:{binding['path']}"
            )
    consumer = profile["consumer"]
    if consumer["feature_max_lookback_seconds"] != 0:
        raise Task22ResolutionError("unproven_feature_lookback")
    if consumer["optimization_or_strategy_selection_allowed"]:
        raise Task22ResolutionError("strategy_optimization_not_allowed")
    if consumer["exact_horizon_claims_allowed"]:
        raise Task22ResolutionError("nominal_horizon_claim_not_allowed")


def _receipts(
    repository_root: Path, profile: JsonObject
) -> dict[tuple[str, str], JsonObject]:
    return {
        (binding["batch_id"], binding["panel_id"]): load_json(
            repository_root / binding["path"]
        )
        for binding in profile["frozen_timing_inputs"]
    }


def _panel(receipt: JsonObject, panel_id: str) -> JsonObject:
    key = panel_id.lower()
    value = receipt.get(key)
    if not isinstance(value, dict):
        raise Task22ResolutionError(f"panel_missing:{panel_id}")
    return value


def _window_map(receipt: JsonObject, panel_id: str) -> dict[str, JsonObject]:
    return {
        row["member_id"]: row
        for row in _panel(receipt, panel_id)["windows"]
    }


def _batch_timing(
    *, receipts: dict[tuple[str, str], JsonObject], batch_id: str
) -> JsonObject:
    p0_receipt = receipts[(batch_id, "P0")]
    p1_receipt = receipts[(batch_id, "P1")]
    p2_receipt = receipts[(batch_id, "P2")]
    p0 = _window_map(p0_receipt, "P0")
    p1 = _window_map(p1_receipt, "P1")
    p2 = _window_map(p2_receipt, "P2")
    if set(p0) != set(p1) or set(p0) != set(p2):
        raise Task22ResolutionError(f"panel_membership_drift:{batch_id}")

    member_elapsed = []
    for member_id in sorted(p0):
        p0_at = _timestamp(p0[member_id]["triggered_at"])
        p1_at = _timestamp(p1[member_id]["triggered_at"])
        p2_at = _timestamp(p2[member_id]["completed_at"])
        member_elapsed.append(
            {
                "member_id": member_id,
                "p0_triggered_at": _iso(p0_at),
                "p1_triggered_at": _iso(p1_at),
                "p2_completed_at": _iso(p2_at),
                "p1_elapsed_seconds": (p1_at - p0_at).total_seconds(),
                "p2_available_elapsed_seconds": (p2_at - p0_at).total_seconds(),
            }
        )
    source_at = _timestamp(p0_receipt["source"]["observed_at"])
    label_at = max(
        _timestamp(row["p2_completed_at"]) for row in member_elapsed
    )
    return {
        "batch_id": batch_id,
        "member_ids": sorted(p0),
        "member_count": len(p0),
        "selection_observed_at": _iso(source_at),
        "label_first_reliable_available_at": _iso(label_at),
        "maximum_p2_available_elapsed_seconds": max(
            row["p2_available_elapsed_seconds"] for row in member_elapsed
        ),
        "members": member_elapsed,
    }


def _resolve(
    *, profile: JsonObject, development: JsonObject, holdout: JsonObject
) -> JsonObject:
    consumer = profile["consumer"]
    max_observed = max(
        development["maximum_p2_available_elapsed_seconds"],
        holdout["maximum_p2_available_elapsed_seconds"],
    )
    if max_observed > consumer["label_horizon_seconds"]:
        raise Task22ResolutionError("declared_label_horizon_too_short")
    label_at = _timestamp(development["label_first_reliable_available_at"])
    holdout_at = _timestamp(holdout["selection_observed_at"])
    gap = (holdout_at - label_at).total_seconds()
    embargo = consumer["embargo_seconds"]
    purged = [
        row["member_id"]
        for row in development["members"]
        if _timestamp(row["p2_completed_at"]) >= holdout_at
    ]
    if purged or gap < embargo:
        raise Task22ResolutionError("temporal_envelope_not_splittable")
    return {
        "verdict": "PASS",
        "development_label_available_at": _iso(label_at),
        "holdout_selection_at": _iso(holdout_at),
        "pre_embargo_gap_seconds": gap,
        "required_embargo_seconds": embargo,
        "embargo_boundary_at": _iso(label_at + timedelta(seconds=embargo)),
        "post_embargo_slack_seconds": gap - embargo,
        "purged_development_members": purged,
        "actual_timestamps_used": True,
        "source_start_gap_alone_used": False,
    }


def build_split_manifest(
    *, repository_root: Path, profile: JsonObject
) -> JsonObject:
    receipts = _receipts(repository_root, profile)
    development = _batch_timing(receipts=receipts, batch_id="T21-R2")
    holdout = _batch_timing(receipts=receipts, batch_id="T21-R3")
    temporal = _resolve(
        profile=profile,
        development=development,
        holdout=holdout,
    )
    parent = load_json(
        repository_root
        / profile["accepted_baseline"]["parent_split"]["path"]
    )
    consumer = profile["consumer"]
    profile_sha256 = sha256_file(repository_root / PROFILE_PATH)
    identity_payload = {
        "algorithm_id": "SMIAL-T22-CONSUMER-SPECIFIC-GROUP-TIME-SPLIT",
        "algorithm_version": "2.0",
        "dataset_inventory_sha256": parent["content_addressing"][
            "dataset_inventory_sha256"
        ],
        "parent_split_content_sha256": parent["content_addressing"][
            "split_content_sha256"
        ],
        "consumer_profile_id": profile["profile_id"],
        "consumer_profile_sha256": profile_sha256,
        "development_batch_id": "T21-R2",
        "validation": "NONE",
        "holdout_batch_id": "T21-R3",
        "temporal_resolution": temporal,
        "outcome_state": "UNOPENED",
    }
    return {
        "schema": "smial.task22.dataset-split-manifest-v2",
        "schema_version": "2.0",
        "task_id": "TASK-22",
        "atom_id": ATOM_ID,
        "as_of": "2026-08-01",
        "split_id": "T22-SPLIT-T21-FROZEN-002",
        "parent_split": {
            "split_id": parent["split_id"],
            "path": profile["accepted_baseline"]["parent_split"]["path"],
            "sha256": profile["accepted_baseline"]["parent_split"]["sha256"],
            "split_content_sha256": parent["content_addressing"][
                "split_content_sha256"
            ],
            "historical_bytes_rewritten": False,
        },
        "status": "SPLIT_READY_WITH_LIMITATIONS",
        "consumer_profile": {
            "profile_id": profile["profile_id"],
            "profile_version": profile["profile_version"],
            "path": PROFILE_PATH,
            "sha256": profile_sha256,
            "consumer_task_id": consumer["consumer_task_id"],
            "feature_max_lookback_seconds": consumer[
                "feature_max_lookback_seconds"
            ],
            "label_horizon_seconds": consumer["label_horizon_seconds"],
            "label_first_reliable_available_at_rule": consumer[
                "label_first_reliable_available_at_rule"
            ],
            "execution_or_settlement_lag_seconds_if_applicable": consumer[
                "execution_or_settlement_lag_seconds_if_applicable"
            ],
            "elapsed_time_semantics": consumer["elapsed_time_semantics"],
            "exact_horizon_claims_allowed": False,
        },
        "content_addressing": {
            "digest_algorithm": "SHA-256",
            "identity_payload": identity_payload,
            "split_content_sha256": sha256_bytes(
                canonical_json_bytes(identity_payload)
            ),
            "dataset_inventory_sha256": parent["content_addressing"][
                "dataset_inventory_sha256"
            ],
        },
        "temporal_resolution": temporal,
        "roles": {
            "development": {
                "state": "ASSIGNED",
                **development,
            },
            "validation": {
                "state": "NONE",
                "batch_id": None,
                "member_ids": [],
            },
            "holdout": {
                "state": "UNTOUCHED",
                "access": "DENY",
                **holdout,
            },
            "auxiliary_gap_evidence": parent["roles"][
                "auxiliary_gap_evidence"
            ],
        },
        "outcome_seal": {
            "state": "UNOPENED",
            "outcome_values_read": False,
            "outcome_paths_opened": [],
            "access_default": "DENY",
            "first_access_requires_append_only_consumption_event": True,
        },
        "claim_boundary": {
            "allowed": [
                "TASK23_THREE_PANEL_COHORT_DIAGNOSTICS_ELIGIBILITY",
                "SPLIT_READY_WITH_LIMITATIONS",
                "R3_HOLDOUT_UNTOUCHED",
            ],
            "forbidden": consumer["forbidden_claims"],
        },
        "acceptance": {
            "status": "PASS",
            "owner_verdict": "SPLIT_READY_WITH_LIMITATIONS",
            "additional_collection_required_for_this_consumer": False,
            "task23_started": False,
            "outcome_access_authorized": False,
            "provider_calls": 0,
            "outcome_reads": 0,
        },
        "catalog": {
            "registered_in_atom5": False,
            "status": "CATALOG_TRANSACTION_PENDING_T22_A6",
        },
    }


def build_ledger(
    *, repository_root: Path, profile: JsonObject, manifest: JsonObject
) -> JsonObject:
    parent_binding = profile["accepted_baseline"]["parent_ledger"]
    split_sha256 = sha256_bytes(artifact_bytes(manifest))
    return {
        "schema": "smial.task22.holdout-ledger-extension-v2",
        "schema_version": "2.0",
        "task_id": "TASK-22",
        "atom_id": ATOM_ID,
        "as_of": "2026-08-01",
        "ledger_id": "T22-HOLDOUT-ACCESS-LEDGER-001",
        "ledger_version": 2,
        "previous_ledger": {
            "path": parent_binding["path"],
            "sha256": parent_binding["sha256"],
        },
        "role": "COMPANION_EVIDENCE_NOT_SECOND_TRUTH_OWNER",
        "registry_binding": {
            "registry_id": "SMIAL-REGISTRY-HOLDOUT-CONSUMPTION",
            "truth_owner": "TASK-03",
            "historical_bytes_mutable": False,
            "consumption_record_appended_in_atom5": False,
        },
        "split_binding": {
            "split_id": manifest["split_id"],
            "path": SPLIT_PATH,
            "sha256": split_sha256,
            "split_content_sha256": manifest["content_addressing"][
                "split_content_sha256"
            ],
        },
        "assignment_receipt": {
            "assignment_id": "T22-HOLDOUT-ASSIGNMENT-001",
            "assigned_on": "2026-08-01",
            "prior_state": "UNASSIGNED_UNOPENED",
            "resulting_state": "UNTOUCHED",
            "holdout_batch_id": "T21-R3",
            "consumer_profile_id": profile["profile_id"],
            "consumer_profile_sha256": sha256_file(
                repository_root / PROFILE_PATH
            ),
            "temporal_resolution_sha256": sha256_bytes(
                canonical_json_bytes(manifest["temporal_resolution"])
            ),
            "outcome_values_read": False,
            "outcome_paths_opened": [],
        },
        "state": {
            "current": "UNTOUCHED",
            "access_default": "DENY",
            "outcome_values_read": False,
            "outcome_paths_opened": [],
        },
        "records": [],
        "catalog": {
            "registered_in_atom5": False,
            "status": "CATALOG_TRANSACTION_PENDING_T22_A6",
        },
    }


def build_all(repository_root: Path) -> tuple[JsonObject, JsonObject]:
    profile = load_yaml(repository_root / PROFILE_PATH)
    validate_inputs(repository_root, profile)
    manifest = build_split_manifest(
        repository_root=repository_root,
        profile=profile,
    )
    ledger = build_ledger(
        repository_root=repository_root,
        profile=profile,
        manifest=manifest,
    )
    return manifest, ledger
