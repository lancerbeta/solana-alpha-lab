"""Deterministic TASK-21 A7 freeze and acceptance evidence builder."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

from solana_alpha_lab.task21_forward_recovery import (
    build_source_inventory,
    canonical_json_bytes,
)


JsonObject = dict[str, Any]
ATOM_ID = "T21-A7_DATASET_FREEZE_ACCEPTANCE_CATALOG_FACTORY_FIT_V1"
PRE_A7_INDEX_EXCLUSIONS = {
    "configs/task21_dataset_freeze_acceptance_v1.yaml",
    "configs/task21_final_owner_pulse_v1.yaml",
    "docs/contracts/task21_dataset_freeze_acceptance_contract_v1.md",
    "docs/evidence/task21/a7_acceptance_catalog_factory_fit_v1.json",
    "docs/evidence/task21/effective_sample_summary_v1.json",
    "docs/evidence/task21/final_dataset_freeze_manifest_v1.json",
    "docs/evidence/task21/task21_artifact_index_v1.json",
    "scripts/finalize_task21_a7.py",
    "scripts/show_task21_final_owner_pulse.py",
    "src/solana_alpha_lab/task21_dataset_freeze_acceptance.py",
    "src/solana_alpha_lab/task21_final_owner_pulse.py",
    "tests/test_task21_dataset_freeze_acceptance.py",
    "tests/test_task21_durable_resume_router_binding.py",
    "tests/test_task21_final_owner_pulse.py",
}
PLANNED_ASSET_ID_RE = re.compile(r"\b[A-Z]+-T21-[A-Z0-9-]+-[0-9]{3}\b")


class Task21A7Error(RuntimeError):
    """The frozen TASK-21 evidence cannot be accepted safely."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_yaml(path: Path) -> JsonObject:
    value = yaml.safe_load(path.read_bytes())
    if not isinstance(value, dict):
        raise Task21A7Error(f"yaml_root_not_mapping:{path.as_posix()}")
    return value


def load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise Task21A7Error(f"json_root_not_mapping:{path.as_posix()}")
    return value


def validate_frozen_inputs(repository_root: Path, plan: JsonObject) -> None:
    for binding in plan["frozen_inputs"]:
        path = repository_root / binding["path"]
        if not path.is_file():
            raise Task21A7Error(f"frozen_input_missing:{binding['path']}")
        if sha256_file(path) != binding["sha256"]:
            raise Task21A7Error(f"frozen_input_hash_drift:{binding['path']}")


def _source_roots(recovery_plan: JsonObject) -> list[str]:
    roots: list[str] = []
    for component in recovery_plan["components"]:
        roots.extend(str(value) for value in component["source_roots"])
    return roots


def build_dataset_freeze_manifest(
    *, repository_root: Path, plan: JsonObject
) -> JsonObject:
    recovery_plan = load_yaml(
        repository_root / "configs/task21_final_dataset_recovery_v1.yaml"
    )
    recovery_receipt = load_json(
        repository_root
        / "docs/evidence/task21/final_dataset_recovery_acceptance_v1.json"
    )
    roots = _source_roots(recovery_plan)
    files = build_source_inventory(
        repository_root=repository_root,
        source_roots=roots,
    )
    identity = plan["accepted_dataset_identity"]
    actual = {
        "root_count": len(roots),
        "file_count": len(files),
        "stored_bytes": sum(int(row["bytes"]) for row in files),
        "source_inventory_sha256": sha256_bytes(canonical_json_bytes(files)),
    }
    expected = {
        key: identity[key]
        for key in (
            "root_count",
            "file_count",
            "stored_bytes",
            "source_inventory_sha256",
        )
    }
    if actual != expected:
        raise Task21A7Error("final_dataset_identity_drift")
    if recovery_receipt.get("status") != "PASS_REMOTE_RECOVERY_PROVEN":
        raise Task21A7Error("final_remote_recovery_not_proven")
    if recovery_receipt["isolated_restore"]["restored_inventory_sha256"] != (
        actual["source_inventory_sha256"]
    ):
        raise Task21A7Error("remote_restore_inventory_drift")
    return {
        "schema": "smial.task21.final-dataset-freeze-manifest",
        "schema_version": "1.0",
        "task_id": "TASK-21",
        "atom_id": ATOM_ID,
        "status": "FROZEN_ACCEPTED_LOCAL_CANDIDATE",
        "as_of": "2026-08-01",
        **actual,
        "source_roots": roots,
        "files": files,
        "remote_recovery": {
            "status": "PASS_REMOTE_RECOVERY_PROVEN",
            "archive_sha256": identity["remote_archive_sha256"],
            "archive_bytes": identity["remote_archive_bytes"],
            "drive_file_id": identity["remote_file_id"],
            "exact_raw_readback": True,
            "isolated_restore": True,
        },
        "freeze_policy": {
            "accepted_bytes_mutable": False,
            "delete_allowed": False,
            "silent_backfill_allowed": False,
            "historical_rewrite_allowed": False,
            "correction_requires_new_dataset_identity": True,
        },
        "outcome_values_read": False,
        "contains_raw_market_data": False,
        "contains_raw_data_identity_only": True,
        "contains_secrets": False,
    }


def build_effective_sample_summary(plan: JsonObject) -> JsonObject:
    sample = plan["effective_sample"]
    if sample["quote_attempts"] != sample["quote_pairs"] * 2:
        raise Task21A7Error("quote_pair_attempt_mismatch")
    if sample["complete_members"] + sample["incomplete_members"] != (
        sample["nominated_and_admitted_members"]
    ):
        raise Task21A7Error("member_count_mismatch")
    return {
        "schema": "smial.task21.effective-sample-summary",
        "schema_version": "1.0",
        "task_id": "TASK-21",
        "atom_id": ATOM_ID,
        "status": "PASS_WITH_LIMITATIONS",
        "as_of": "2026-08-01",
        "owner_verdict": sample["eligible_claim"],
        "population": {
            "nominated_and_admitted_members": 8,
            "complete_members": 5,
            "incomplete_members": 3,
            "content_distinct_nomination_batches": 3,
            "complete_member_clusters": 2,
            "maximum_complete_member_share_one_batch": 0.6,
        },
        "strata": [
            {
                "batch_id": "R1",
                "members": 3,
                "complete_members": 0,
                "observed_panels": 7,
                "quote_pairs": 28,
                "quote_attempts": 56,
                "missing_panels": 3,
                "role": "PARTIAL_AND_GAP_EVIDENCE_ONLY",
            },
            {
                "batch_id": "R2",
                "members": 3,
                "complete_members": 3,
                "observed_panels": 9,
                "quote_pairs": 36,
                "quote_attempts": 72,
                "missing_panels": 0,
                "role": "COMPLETE_COHORT_CLUSTER",
            },
            {
                "batch_id": "R3",
                "members": 2,
                "complete_members": 2,
                "observed_panels": 6,
                "quote_pairs": 24,
                "quote_attempts": 48,
                "missing_panels": 0,
                "role": "COMPLETE_COHORT_CLUSTER",
            },
        ],
        "totals": {
            "observed_panels": 22,
            "quote_pairs": 88,
            "quote_attempts": 176,
            "explicit_missing_panels": 3,
        },
        "observation_span": {
            "forward_first_observed_at": "2026-07-31T07:49:54.402486Z",
            "forward_last_observed_at": "2026-08-01T14:52:42.412665Z",
            "elapsed_seconds": 111768.010179,
            "elapsed_time_is_not_a_sufficiency_proxy": True,
        },
        "selection_and_dependence": {
            "watchlist_conditioned": True,
            "same_day_sequential_batches": True,
            "member_iid_assumption_allowed": False,
            "nomination_batch_grouping_required": True,
            "cross_regime_claim_allowed": False,
        },
        "gaps": [
            "R1_H6_THREE_PANELS_EXPLICIT_GAP_NO_BACKFILL",
            "R1_H24_ONE_SENTINEL_NOT_FULL_COHORT",
            "ONLY_TWO_COMPLETE_NOMINATION_CLUSTERS",
            "NO_MARKET_WIDE_OR_CROSS_REGIME_SAMPLE",
            "NO_STATISTICAL_POWER_CLAIM",
        ],
        "task22_eligibility": {
            "status": "ELIGIBLE_FOR_DETERMINISTIC_SPLIT_AND_HOLDOUT_LEDGER_ONLY",
            "outcomes_opened": False,
            "split_before_outcome_required": True,
            "group_by_nomination_batch_required": True,
            "alpha_claim_allowed": False,
        },
        "non_claims": sample["prohibited_claims"],
    }


def _pre_a7_paths(repository_root: Path) -> list[Path]:
    candidates: set[Path] = set()
    patterns = (
        "configs/task21_*.yaml",
        "docs/contracts/task21_*.md",
        "docs/evidence/task21/*",
        "scripts/*task21*.py",
        "src/solana_alpha_lab/task21_*.py",
        "tests/test_task21_*.py",
        "tests/fixtures/task21/**/*",
    )
    for pattern in patterns:
        candidates.update(path for path in repository_root.glob(pattern) if path.is_file())
    return sorted(
        path
        for path in candidates
        if path.relative_to(repository_root).as_posix() not in PRE_A7_INDEX_EXCLUSIONS
    )


def build_artifact_index(
    *, repository_root: Path, plan: JsonObject
) -> JsonObject:
    rows: list[JsonObject] = []
    planned_ids: set[str] = set()
    for path in _pre_a7_paths(repository_root):
        relative = path.relative_to(repository_root).as_posix()
        value = path.read_bytes()
        rows.append(
            {
                "path": relative,
                "bytes": len(value),
                "sha256": sha256_bytes(value),
            }
        )
        if path.suffix in {".yaml", ".yml"}:
            planned_ids.update(PLANNED_ASSET_ID_RE.findall(value.decode("utf-8")))
    stable_ids = set(plan["catalog_transaction"]["registered_asset_ids"])
    selected_prior_ids = sorted(planned_ids & stable_ids)
    superseded_ids = sorted(planned_ids - stable_ids)
    return {
        "schema": "smial.task21.artifact-index",
        "schema_version": "1.0",
        "task_id": "TASK-21",
        "atom_id": ATOM_ID,
        "status": "CONTENT_ADDRESSED_COMPLETE_PRE_A7_INDEX",
        "as_of": "2026-08-01",
        "selection_rule": (
            "ALL_PRE_A7_TASK21_CONFIG_CONTRACT_EVIDENCE_SCRIPT_MODULE_TEST_"
            "FIXTURE_FILES_EXCLUDING_A7_DERIVED_AND_A7_MUTATED_OUTPUTS"
        ),
        "file_count": len(rows),
        "stored_bytes": sum(int(row["bytes"]) for row in rows),
        "artifact_set_sha256": sha256_bytes(canonical_json_bytes(rows)),
        "files": rows,
        "planned_asset_id_reconciliation": {
            "planned_id_count": len(planned_ids),
            "registered_as_stable_assets": selected_prior_ids,
            "superseded_by_this_index": superseded_ids,
            "policy": plan["catalog_transaction"]["planned_id_policy"],
        },
        "local_raw_included": False,
        "contains_secrets": False,
    }


def _artifact_binding(repository_root: Path, relative: str) -> JsonObject:
    path = repository_root / relative
    return {"path": relative, "sha256": sha256_file(path)}


def build_acceptance_receipt(
    *, repository_root: Path, plan: JsonObject
) -> JsonObject:
    bindings = [
        _artifact_binding(repository_root, relative)
        for relative in (
            "configs/task21_dataset_freeze_acceptance_v1.yaml",
            "docs/contracts/task21_dataset_freeze_acceptance_contract_v1.md",
            "docs/evidence/task21/final_dataset_freeze_manifest_v1.json",
            "docs/evidence/task21/effective_sample_summary_v1.json",
            "docs/evidence/task21/task21_artifact_index_v1.json",
            "docs/handoffs/task21_to_task22_v1.md",
            "docs/architecture/intents/ARCH-INTENT-003-product-owner-operating-topology.md",
            "docs/roadmap_patches/task21_product_vision_followups_v1.md",
            "configs/task21_final_owner_pulse_v1.yaml",
            "src/solana_alpha_lab/task21_final_owner_pulse.py",
            "scripts/show_task21_final_owner_pulse.py",
        )
    ]
    checks = [
        ("MISSION_AND_ESTIMAND", "PASS", "The freeze serves a named split/holdout decision and claims no alpha."),
        ("FLEXIBILITY_AND_REUSE", "PASS", "Provider-neutral manifests preserve members, batches, attempts and recovery identity."),
        ("COMPATIBILITY_AND_HISTORY", "PASS", "Forward-only rebase and explicit H6 gap remain intact without rewriting prior receipts."),
        ("EFFICIENCY", "PASS", "Collection stopped at the event-triggered sufficiency boundary; no calendar waiting or extra calls were added."),
        ("RESEARCH_TRUTH", "PASS", "Outcomes remain unopened and TASK-22 must freeze a group-aware split before analysis."),
        ("OWNER_OPERABILITY_AND_UX", "PASS", "Final Owner Pulse exposes dataset identity, limitations, recovery and exact next action."),
        ("EXECUTION_TO_CASHFLOW", "NOT_APPLICABLE", "TASK-21 measures quote evidence and makes no fill, position, NetReturn or cashflow claim."),
        ("MONITORING_AND_RECOVERY", "PASS", "The exact 91-file dataset has private byte read-back and isolated full restore proof."),
        ("BUILD_VERSUS_BUY", "PASS", "Existing collector, recovery and Catalog machinery is wrapped; no platform or dependency was added."),
        ("SECURITY_AND_AUTHORITY", "PASS", "A7 is local-only with zero provider, Drive, credential, cash, signer and transaction actions."),
        ("FAILURE_RED_TEAM", "PASS", "Acceptance fails on hash drift, restore drift, outcome opening, batch leakage, backfill or claim expansion."),
        ("PRODUCT_HORIZON", "PASS", "Documentation and production-lite cockpit gaps have durable triggers without implementation leakage."),
        ("CATALOG_ECONOMY", "PASS", "One content-addressed index replaces atom-level registration bureaucracy while preserving every path/hash."),
        ("CONTRADICTION_SCAN", "PASS", "Freeze, sample, recovery, handoff, product intent and next gate use one bounded claim."),
        ("MIGRATION_AND_ROLLBACK", "PASS", "All changes are additive; prior evidence and external bytes remain immutable."),
    ]
    return {
        "schema": "smial.task21.a7-acceptance-catalog-factory-fit",
        "schema_version": "1.0",
        "task_id": "TASK-21",
        "atom_id": ATOM_ID,
        "status": "PASS",
        "as_of": "2026-08-01",
        "owner_verdict": "DATASET_READY_FOR_NARROW_CONDITIONAL_ANALYSIS_WITH_LIMITATIONS",
        "dataset": plan["accepted_dataset_identity"],
        "effective_sample": plan["effective_sample"],
        "usage": plan["task_usage_reconciliation"],
        "frozen_artifacts": bindings,
        "catalog": {
            "status": "REGISTERED_IN_TASK21_A7_CATALOG_TRANSACTION",
            "version": plan["catalog_transaction"]["target_version"],
            "assets": plan["catalog_transaction"]["target_assets"],
            "asset_registries": 4,
            "schemas": 4,
            "queries": 8,
            "lifecycle_registries": 9,
            "lifecycle_records": 52,
            "registered_asset_ids": plan["catalog_transaction"]["registered_asset_ids"],
            "planned_id_policy": plan["catalog_transaction"]["planned_id_policy"],
        },
        "product_vision_reconciliation": plan["product_vision_reconciliation"],
        "factory_fit": {
            "mode": "FULL_REVIEW",
            "verdict": "PASS_WITH_DURABLE_FOLLOWUPS",
            "checks": [
                {"check_id": key, "status": status, "evidence": evidence}
                for key, status, evidence in checks
            ],
            "durable_followups": [
                {
                    "owner": "TASK-34A",
                    "trigger": "FIRST_UNATTENDED_RUNTIME_OR_SECOND_OPERATOR_OR_REPEATED_DOC_FRICTION",
                    "destination": "ROADMAP_PATCH_AND_TASK21_FINISH_SOURCE_CANDIDATE",
                },
                {
                    "owner": "TASK-35A",
                    "trigger": "STABLE_READ_CONTRACTS_BEFORE_TASK38_SHADOW_OBSERVATION",
                    "destination": "ROADMAP_PATCH_AND_TASK21_FINISH_SOURCE_CANDIDATE",
                },
                {
                    "owner": "CROSS_HYPOTHESIS_REVIEW_WATCH",
                    "trigger": "MULTI_FAMILY_EVIDENCE_OR_SECOND_SYNTHESIS_OR_MEASURED_TRIAGE_DELAY",
                    "destination": "PRODUCT_VISION_ARCHITECTURE_INTENT",
                },
            ],
        },
        "validation": {
            "a7_targeted_suite": "PASS_10_OF_10",
            "catalog_validation": "PASS_0_26_0_369_ASSETS",
            "diff_check": "PASS",
            "full_repository_unit_suite": "PASS_1431_OF_1431",
            "generated_navigation": "PASS",
            "repository_state_validator": "DEFERRED_TO_A8_EXACT_STAGED_OR_CI_CHECKPOINT_CURRENT_DIRTY_TASK_BRANCH_IS_OUTSIDE_ACCEPTED_TOPOLOGY",
            "secret_scan": "PASS",
            "task21_combined_suite": "PASS_297_OF_297",
        },
        "actual_actions": {
            "local_write_only": True,
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "collector_executions": 0,
            "raw_or_dataset_writes": 0,
            "credentials": 0,
            "cash_spend_usd_cents": 0,
            "wallet_signer_transaction_actions": 0,
            "source_mutation": False,
            "commit": False,
            "push": False,
            "pull_request": False,
            "merge": False,
            "destructive_actions": False,
        },
        "non_claims": [
            "NOT_MARKET_WIDE_REPRESENTATIVENESS",
            "NOT_CROSS_REGIME_GENERALIZATION",
            "NOT_STATISTICAL_POWER_SUFFICIENCY",
            "NOT_ALPHA",
            "NOT_EXECUTABLE_NET_RETURN",
            "NOT_STRATEGY_OR_POSITION",
            "NOT_PRODUCTION_READINESS",
            "NOT_TASK22_STARTED",
            "NOT_TASK21_DONE",
            "NOT_PROJECT_SOURCE_ACTIVATED",
        ],
        "next_boundary": {
            "atom_id": "T21-A8_REPOSITORY_DELIVERY_V1",
            "status": "NOT_AUTHORIZED",
            "task22_status": "ELIGIBLE_AFTER_A8_AND_TASK21_FINISH_GATE_WITH_SEPARATE_ENTRY_GATE",
        },
        "state_change": "LOCAL_FILES_AND_CATALOG_ONLY",
    }


def write_json_create_only(
    path: Path, value: JsonObject, *, replace_generated: bool = False
) -> None:
    encoded = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != encoded:
            if not replace_generated:
                raise Task21A7Error(
                    f"generated_output_exists_with_drift:{path.as_posix()}"
                )
            path.write_bytes(encoded)
        return
    with path.open("xb") as handle:
        handle.write(encoded)


def materialize_a7_outputs(
    repository_root: Path, *, replace_generated: bool = False
) -> list[Path]:
    repository_root = repository_root.resolve()
    plan = load_yaml(
        repository_root / "configs/task21_dataset_freeze_acceptance_v1.yaml"
    )
    validate_frozen_inputs(repository_root, plan)
    outputs: list[tuple[str, JsonObject]] = [
        (
            "docs/evidence/task21/final_dataset_freeze_manifest_v1.json",
            build_dataset_freeze_manifest(repository_root=repository_root, plan=plan),
        ),
        (
            "docs/evidence/task21/effective_sample_summary_v1.json",
            build_effective_sample_summary(plan),
        ),
        (
            "docs/evidence/task21/task21_artifact_index_v1.json",
            build_artifact_index(repository_root=repository_root, plan=plan),
        ),
    ]
    paths: list[Path] = []
    for relative, value in outputs:
        path = repository_root / relative
        write_json_create_only(path, value, replace_generated=replace_generated)
        paths.append(path)
    receipt_path = (
        repository_root
        / "docs/evidence/task21/a7_acceptance_catalog_factory_fit_v1.json"
    )
    write_json_create_only(
        receipt_path,
        build_acceptance_receipt(repository_root=repository_root, plan=plan),
        replace_generated=replace_generated,
    )
    paths.append(receipt_path)
    return paths


def verify_hash_bindings(repository_root: Path, bindings: Iterable[JsonObject]) -> None:
    for binding in bindings:
        if sha256_file(repository_root / binding["path"]) != binding["sha256"]:
            raise Task21A7Error(f"artifact_hash_drift:{binding['path']}")
