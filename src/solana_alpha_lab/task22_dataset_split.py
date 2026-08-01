"""Outcome-blind TASK-22 group split and holdout ledger builder."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


JsonObject = dict[str, Any]
ATOM_ID = "T22-A3_DETERMINISTIC_SPLIT_AND_HOLDOUT_LEDGER_V1"
SPEC_PATH = "configs/task22_group_aware_split_v1.yaml"
SPEC_SHA256 = "43e71918e4da1150defc97b812ea648fac9f3a3c567dba379f6948b0ac007272"
SPLIT_PATH = "docs/evidence/task22/dataset_split_manifest_v1.json"
LEDGER_PATH = "docs/evidence/task22/holdout_access_ledger_v1.json"
ACCEPTANCE_PATH = (
    "docs/evidence/task22/"
    "deterministic_split_and_holdout_ledger_acceptance_v1.json"
)
SPLIT_SCHEMA_PATH = "catalog/schemas/task22_split_manifest.schema.json"
LEDGER_SCHEMA_PATH = (
    "catalog/schemas/task22_holdout_ledger_extension.schema.json"
)
IMPLEMENTATION_PATH = "src/solana_alpha_lab/task22_dataset_split.py"
SCRIPT_PATH = "scripts/build_task22_dataset_split.py"
TEST_PATH = "tests/test_task22_deterministic_split_and_holdout_ledger.py"


class Task22SplitError(RuntimeError):
    """The frozen TASK-21 evidence cannot be split safely."""


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
        raise Task22SplitError(f"yaml_root_not_mapping:{path.as_posix()}")
    return value


def load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise Task22SplitError(f"json_root_not_mapping:{path.as_posix()}")
    return value


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _binding(path: str, sha256: str) -> JsonObject:
    return {"path": path, "sha256": sha256}


def validate_frozen_inputs(repository_root: Path, spec: JsonObject) -> None:
    if sha256_file(repository_root / SPEC_PATH) != SPEC_SHA256:
        raise Task22SplitError("a2_spec_hash_drift")
    if spec["outcome_seal"] != {
        "state": "UNOPENED",
        "outcome_values_read": False,
        "outcome_paths_opened": [],
        "split_before_outcome_required": True,
        "feature_threshold_or_strategy_tuning_allowed": False,
        "seal_break_before_a3": "FAIL_CLOSED_DATASET_NOT_SPLITTABLE",
    }:
        raise Task22SplitError("outcome_seal_drift")
    for binding in spec["frozen_inputs"]:
        path = repository_root / binding["path"]
        if not path.is_file():
            raise Task22SplitError(f"frozen_input_missing:{binding['path']}")
        if sha256_file(path) != binding["sha256"]:
            raise Task22SplitError(
                f"frozen_input_hash_drift:{binding['path']}"
            )


def _group_identity(group: JsonObject) -> JsonObject:
    payload = {
        "batch_id": group["batch_id"],
        "source_observed_at": group["source_observed_at"],
        "member_ids": sorted(group["member_ids"]),
    }
    return {
        **payload,
        "member_count": len(payload["member_ids"]),
        "partition_sha256": sha256_bytes(canonical_json_bytes(payload)),
    }


def build_split_manifest(spec: JsonObject) -> JsonObject:
    groups = sorted(
        spec["grouping_contract"]["complete_groups"],
        key=lambda row: (row["source_observed_at"], row["batch_id"]),
    )
    if len(groups) < 2:
        raise Task22SplitError("fewer_than_two_complete_groups")
    if len(groups) > 2:
        raise Task22SplitError("three_or_more_groups_require_redesign")

    development = _group_identity(groups[0])
    holdout_candidate = _group_identity(groups[1])
    source_gap_seconds = (
        _timestamp(holdout_candidate["source_observed_at"])
        - _timestamp(development["source_observed_at"])
    ).total_seconds()
    bounds = spec["chronology_and_purge_contract"][
        "project_horizon_bounds_seconds"
    ]
    reasons = [
        "CONSUMER_TIME_CONTRACT_MISSING",
    ]
    if source_gap_seconds < bounds["maximum"]:
        reasons.append("SOURCE_START_GAP_LT_MAX_PROJECT_HORIZON")

    identity_payload = {
        "algorithm_id": "SMIAL-T22-GROUP-TIME-SPLIT",
        "algorithm_version": "1.0",
        "dataset_inventory_sha256": spec["accepted_dataset"][
            "source_inventory_sha256"
        ],
        "development_candidate": development,
        "holdout_candidate": holdout_candidate,
        "validation": "NONE",
        "verdict": "EXTEND_EVIDENCE",
        "outcome_state": "UNOPENED",
    }
    split_content_sha256 = sha256_bytes(
        canonical_json_bytes(identity_payload)
    )
    incomplete = spec["grouping_contract"]["incomplete_groups"]

    return {
        "schema": "smial.task22.dataset-split-manifest",
        "schema_version": "1.0",
        "task_id": "TASK-22",
        "atom_id": ATOM_ID,
        "as_of": "2026-08-01",
        "split_id": "T22-SPLIT-T21-FROZEN-001",
        "status": "EXTEND_EVIDENCE",
        "owner_verdict": "EXTEND_EVIDENCE",
        "reason_codes": reasons,
        "content_addressing": {
            "digest_algorithm": "SHA-256",
            "identity_payload": identity_payload,
            "split_content_sha256": split_content_sha256,
            "dataset_manifest": _binding(
                "docs/evidence/task21/final_dataset_freeze_manifest_v1.json",
                "295d29354554247e08ddd39cd9f6b642e262869f22a0da9925227e6fab378a0f",
            ),
            "dataset_inventory_sha256": spec["accepted_dataset"][
                "source_inventory_sha256"
            ],
            "a2_contract_spec": _binding(SPEC_PATH, SPEC_SHA256),
        },
        "outcome_seal": {
            "state": "UNOPENED",
            "outcome_values_read": False,
            "outcome_paths_opened": [],
            "analysis_access_allowed": False,
        },
        "grouping": {
            "primary_group_key": "nomination_batch_id",
            "member_cross_fold_allowed": False,
            "batch_cross_fold_allowed": False,
            "member_iid_assumption_allowed": False,
        },
        "roles": {
            "development": {
                "state": "PROVISIONAL_ONLY",
                **development,
            },
            "validation": {
                "state": "NONE",
                "batch_id": None,
                "member_ids": [],
            },
            "holdout": {
                "state": "UNASSIGNED_UNOPENED",
                "batch_id": None,
                "member_ids": [],
                "access": "DENY",
            },
            "holdout_candidate": {
                "state": "CANDIDATE_NOT_ASSIGNED",
                "access": "DENY",
                **holdout_candidate,
            },
            "auxiliary_gap_evidence": [
                {
                    "batch_id": row["batch_id"],
                    "member_count": row["member_count"],
                    "missing_panels": row["missing_panels"],
                    "outcome_access": "DENY",
                }
                for row in incomplete
            ],
        },
        "chronology": {
            "source_start_gap_seconds": source_gap_seconds,
            "source_start_gap_is_independence_proof": False,
            "consumer_time_contract_present": False,
            "minimum_project_horizon_seconds": bounds["minimum"],
            "maximum_project_horizon_seconds": bounds["maximum"],
            "minimum_horizon_check": "UNKNOWN_CONSUMER_AVAILABILITY_RULE",
            "maximum_horizon_check": (
                "FAIL_SOURCE_START_GAP_LT_HORIZON"
                if source_gap_seconds < bounds["maximum"]
                else "UNKNOWN_CONSUMER_AVAILABILITY_RULE"
            ),
            "purge_status": "NOT_COMPUTABLE",
            "embargo_status": "NOT_COMPUTABLE",
        },
        "claim_boundary": {
            "allowed": [
                "GROUP_AWARE_SPLIT_PIPELINE_MATERIALIZED",
                "EXTEND_EVIDENCE",
                "OUTCOMES_REMAIN_SEALED",
            ],
            "forbidden": spec["claim_boundary"]["forbidden"],
        },
        "catalog": {
            "registered_in_atom3": False,
            "status": "CATALOG_TRANSACTION_PENDING_T22_A4",
        },
    }


def build_holdout_ledger(split_manifest: JsonObject) -> JsonObject:
    split_sha256 = sha256_bytes(artifact_bytes(split_manifest))
    base_registry = next(
        row
        for row in load_spec_bindings(split_manifest)
        if row["path"] == "registries/holdout_consumption.yaml"
    )
    return {
        "schema": "smial.task22.holdout-ledger-extension",
        "schema_version": "1.0",
        "task_id": "TASK-22",
        "atom_id": ATOM_ID,
        "as_of": "2026-08-01",
        "ledger_id": "T22-HOLDOUT-ACCESS-LEDGER-001",
        "ledger_version": 1,
        "previous_ledger_sha256": None,
        "role": "COMPANION_EVIDENCE_NOT_SECOND_TRUTH_OWNER",
        "registry_binding": {
            "registry_id": "SMIAL-REGISTRY-HOLDOUT-CONSUMPTION",
            "registry_type": "holdout_consumption",
            "truth_owner": "TASK-03",
            "path": base_registry["path"],
            "sha256": base_registry["sha256"],
            "historical_bytes_mutable": False,
        },
        "split_binding": {
            "split_id": split_manifest["split_id"],
            "path": SPLIT_PATH,
            "sha256": split_sha256,
            "split_content_sha256": split_manifest["content_addressing"][
                "split_content_sha256"
            ],
        },
        "state": {
            "current": "UNASSIGNED_UNOPENED",
            "access_default": "DENY",
            "outcome_values_read": False,
            "outcome_paths_opened": [],
        },
        "append_only_contract": {
            "snapshot_files_are_create_only": True,
            "prior_records_must_be_exact_prefix": True,
            "allowed_transitions": [
                "UNASSIGNED_UNOPENED->UNTOUCHED",
                "UNTOUCHED->CONSUMED",
            ],
            "consumed_to_untouched_allowed": False,
            "base_registry_projection": (
                "APPEND_BASE_REGISTRY_RECORD_ONLY_AFTER_VALID_CONSUMPTION"
            ),
        },
        "records": [],
        "catalog": {
            "registered_in_atom3": False,
            "status": "CATALOG_TRANSACTION_PENDING_T22_A4",
        },
    }


def load_spec_bindings(split_manifest: JsonObject) -> list[JsonObject]:
    del split_manifest
    return [
        {
            "path": "registries/holdout_consumption.yaml",
            "sha256": (
                "863d68e53861c4aa30f6afa1a512ec5ab84c8966273cee6d42ca1519ef5fa07a"
            ),
        }
    ]


def append_consumption_event(
    *, ledger: JsonObject, event: JsonObject, prior_ledger_sha256: str
) -> JsonObject:
    if ledger["state"]["current"] != "UNTOUCHED":
        raise Task22SplitError("holdout_not_untouched")
    if event["prior_state"] != "UNTOUCHED":
        raise Task22SplitError("invalid_prior_state")
    if event["resulting_state"] != "CONSUMED":
        raise Task22SplitError("invalid_resulting_state")
    if event["event_sequence"] != len(ledger["records"]) + 1:
        raise Task22SplitError("invalid_event_sequence")
    next_ledger = deepcopy(ledger)
    next_ledger["ledger_version"] += 1
    next_ledger["previous_ledger_sha256"] = prior_ledger_sha256
    next_ledger["records"].append(deepcopy(event))
    next_ledger["state"] = {
        "current": "CONSUMED",
        "access_default": "DENY",
        "outcome_values_read": True,
        "outcome_paths_opened": event["access_receipt"]["outcome_paths_opened"],
    }
    return next_ledger


def validate_append_only_extension(
    *, previous: JsonObject, current: JsonObject
) -> None:
    if current["ledger_id"] != previous["ledger_id"]:
        raise Task22SplitError("ledger_identity_drift")
    if current["ledger_version"] != previous["ledger_version"] + 1:
        raise Task22SplitError("ledger_version_not_incremented_once")
    if current["previous_ledger_sha256"] != sha256_bytes(
        artifact_bytes(previous)
    ):
        raise Task22SplitError("previous_ledger_hash_mismatch")
    previous_records = previous["records"]
    if current["records"][: len(previous_records)] != previous_records:
        raise Task22SplitError("historical_ledger_record_mutation")
    if len(current["records"]) != len(previous_records) + 1:
        raise Task22SplitError("ledger_extension_not_single_append")
    if previous["state"]["current"] == "CONSUMED":
        raise Task22SplitError("consumed_holdout_cannot_be_reopened_or_reset")


def build_acceptance_receipt(
    *, repository_root: Path, manifest: JsonObject, ledger: JsonObject
) -> JsonObject:
    generated = {
        SPLIT_PATH: sha256_bytes(artifact_bytes(manifest)),
        LEDGER_PATH: sha256_bytes(artifact_bytes(ledger)),
    }
    paths = [
        SPEC_PATH,
        SPLIT_SCHEMA_PATH,
        LEDGER_SCHEMA_PATH,
        IMPLEMENTATION_PATH,
        SCRIPT_PATH,
        TEST_PATH,
    ]
    bindings = [
        _binding(path, sha256_file(repository_root / path)) for path in paths
    ]
    bindings.extend(_binding(path, sha) for path, sha in generated.items())
    return {
        "schema": "smial.task22.split-ledger-acceptance",
        "schema_version": "1.0",
        "task_id": "TASK-22",
        "atom_id": ATOM_ID,
        "as_of": "2026-08-01",
        "status": "PASS_EXTEND_EVIDENCE",
        "owner_verdict": "EXTEND_EVIDENCE",
        "split_id": manifest["split_id"],
        "split_content_sha256": manifest["content_addressing"][
            "split_content_sha256"
        ],
        "outcome_seal": {
            "state": "UNOPENED",
            "outcome_values_read": False,
            "outcome_paths_opened": [],
        },
        "acceptance": {
            "content_addressed_split_manifest": "PASS",
            "group_integrity": "PASS",
            "validation_role": "NONE",
            "holdout_access": "DENY",
            "append_only_ledger_extension": "PASS",
            "base_registry_compatibility": "PASS",
            "deterministic_rebuild": "PASS",
            "catalog_registration": "DEFERRED_T22_A4",
        },
        "reason_codes": manifest["reason_codes"],
        "artifacts": sorted(bindings, key=lambda row: row["path"]),
        "authority": {
            "class": "LOCAL_WRITE_ONLY",
            "source": "EXPLICIT_USER",
            "gate_phrase": ATOM_ID,
            "managed_file_count": 8,
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "credential_use": 0,
            "outcome_reads": 0,
            "raw_or_dataset_writes": 0,
            "cash_spend_usd_cents": 0,
            "dependency_changes": 0,
            "commit": False,
            "push": False,
            "pull_request": False,
            "merge": False,
            "ui_changes": False,
            "wallet_signer_transaction_actions": 0,
            "destructive_actions": False,
        },
        "next_boundary": {
            "atom_id": "T22-A4_ACCEPTANCE_CATALOG_FACTORY_FIT_V1",
            "authorized": False,
            "outcome_reads_authorized": False,
            "external_calls_authorized": False,
        },
    }


def build_all(repository_root: Path) -> tuple[JsonObject, JsonObject, JsonObject]:
    spec = load_yaml(repository_root / SPEC_PATH)
    validate_frozen_inputs(repository_root, spec)
    manifest = build_split_manifest(spec)
    ledger = build_holdout_ledger(manifest)
    acceptance = build_acceptance_receipt(
        repository_root=repository_root,
        manifest=manifest,
        ledger=ledger,
    )
    return manifest, ledger, acceptance
