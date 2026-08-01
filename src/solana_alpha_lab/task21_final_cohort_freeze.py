"""Deterministic outcome-blind review of the TASK-21 final cohort."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeAlias


JsonObject: TypeAlias = dict[str, Any]

CAPTURE_ROLES = (
    "R2_SOURCE_P0_RUNTIME_ACCEPTANCE",
    "R2_P1_RUNTIME_ACCEPTANCE",
    "R2_P2_RUNTIME_ACCEPTANCE",
    "R3_SOURCE_P0_RUNTIME_ACCEPTANCE",
    "R3_P1_RUNTIME_ACCEPTANCE",
    "R3_P2_RUNTIME_ACCEPTANCE",
)


class Task21FinalCohortFreezeError(RuntimeError):
    """The frozen final-cohort contract or its evidence was violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Task21FinalCohortFreezeError(message)


def _utc(value: object, *, field: str) -> datetime:
    _require(isinstance(value, str), f"{field}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21FinalCohortFreezeError(f"{field}_invalid") from exc
    _require(parsed.tzinfo is not None, f"{field}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _panel_summary(
    receipt: Mapping[str, Any],
    *,
    panel_id: str,
    expected_members: Sequence[str],
) -> JsonObject:
    panel = receipt[panel_id.casefold()]
    windows = panel["windows"]
    member_ids = [item["member_id"] for item in windows]
    _require(member_ids == list(expected_members), f"{panel_id}_member_order_drift")
    _require(
        panel["panels_complete"] == len(expected_members),
        f"{panel_id}_panel_count_drift",
    )
    _require(panel["panels_stopped"] == 0, f"{panel_id}_stopped_panel")
    _require(
        panel["quote_pairs_complete"] == len(expected_members) * 4,
        f"{panel_id}_quote_pair_count_drift",
    )
    _require(
        panel["quote_attempts_complete"] == len(expected_members) * 8,
        f"{panel_id}_quote_attempt_count_drift",
    )
    _require(
        sum(int(value) for value in panel["terminal_counts"].values())
        == panel["quote_attempts_complete"],
        f"{panel_id}_terminal_count_drift",
    )
    _require(
        all(item["provider_calls"] == 8 for item in windows),
        f"{panel_id}_provider_call_drift",
    )
    _require(
        len({item["receipt_sha256"] for item in windows}) == len(windows),
        f"{panel_id}_receipt_identity_collision",
    )
    local = receipt["local_evidence"]
    _require(local["exact_readback"] == "PASS", f"{panel_id}_readback_failed")
    _require(local["create_only"] is True, f"{panel_id}_create_only_drift")
    return {
        "panels": panel["panels_complete"],
        "quote_pairs": panel["quote_pairs_complete"],
        "quote_attempts": panel["quote_attempts_complete"],
        "windows": windows,
    }


def _validate_authority(authority: Mapping[str, Any]) -> None:
    _require(authority["class"] == "LOCAL_WRITE_ONLY", "authority_class_drift")
    ignored = {"class", "source", "gate_phrase", "managed_files"}
    for key, value in authority.items():
        if key in ignored:
            continue
        if isinstance(value, bool):
            _require(not value, f"authority_leak:{key}")
        else:
            _require(value == 0, f"authority_leak:{key}")


def evaluate_final_cohort_freeze(
    plan: Mapping[str, Any],
    evidence_by_role: Mapping[str, Mapping[str, Any]],
) -> JsonObject:
    """Review and freeze cohort evidence without reading quote outcomes."""

    _require(plan.get("task_id") == "TASK-21", "task_id_drift")
    _require(
        plan.get("atom_id")
        == "T21-A6S_R3_COMPLETE_FINAL_COHORT_REVIEW_AND_FREEZE_V1",
        "atom_id_drift",
    )
    _require(
        plan.get("status") == "FROZEN_LOCAL_FINAL_COHORT_REVIEW_PLAN",
        "status_drift",
    )
    history = plan["protected_history"]
    _require(history["outcome_blindness_preserved"], "outcome_unsealed")
    for key in (
        "historical_artifacts_rewritten",
        "hypothesis_definition_changed",
        "primary_estimand_changed",
        "quote_route_price_cost_values_read",
    ):
        _require(not history[key], key)

    h0 = evidence_by_role["R1_H0_RUNTIME_ACCEPTANCE"]
    _require(h0["status"] == "PASS", "r1_h0_not_accepted")
    _require(
        h0["admission"]["outcome_or_route_input_used"] is False,
        "r1_outcome_selection_used",
    )
    for role in CAPTURE_ROLES:
        receipt = evidence_by_role[role]
        _require(receipt["task_id"] == "TASK-21", f"{role}_task_drift")
        _require(receipt["status"] == "PASS", f"{role}_not_accepted")

    expected_batches = {
        item["batch_id"]: item for item in plan["frozen_batches"]
    }
    bindings = (
        (
            "T21-R2",
            evidence_by_role["R2_SOURCE_P0_RUNTIME_ACCEPTANCE"],
            evidence_by_role["R2_P1_RUNTIME_ACCEPTANCE"],
            evidence_by_role["R2_P2_RUNTIME_ACCEPTANCE"],
        ),
        (
            "T21-R3",
            evidence_by_role["R3_SOURCE_P0_RUNTIME_ACCEPTANCE"],
            evidence_by_role["R3_P1_RUNTIME_ACCEPTANCE"],
            evidence_by_role["R3_P2_RUNTIME_ACCEPTANCE"],
        ),
    )
    all_members: list[str] = []
    all_mints: list[str] = []
    panel_windows: dict[str, dict[str, Mapping[str, Any]]] = {}
    totals = {"panels": 0, "quote_pairs": 0, "quote_attempts": 0}

    for batch_id, p0_receipt, p1_receipt, p2_receipt in bindings:
        expected = expected_batches[batch_id]
        members = p0_receipt["admission"]["members"]
        member_ids = [item["member_id"] for item in members]
        mints = [item["mint"] for item in members]
        _require(member_ids == expected["member_ids"], f"{batch_id}_member_drift")
        _require(mints == expected["mints"], f"{batch_id}_mint_drift")
        _require(
            p0_receipt["admission"]["persisted_before_first_jupiter_call"] is True,
            f"{batch_id}_admission_not_persisted",
        )
        _require(
            p0_receipt["admission"]["outcome_or_route_input_used"] is False,
            f"{batch_id}_outcome_selection_used",
        )
        for receipt, panel_id in (
            (p0_receipt, "P0"),
            (p1_receipt, "P1"),
            (p2_receipt, "P2"),
        ):
            if panel_id != "P0":
                population = receipt["population"]
                _require(
                    population["member_ids"] == member_ids,
                    f"{batch_id}_{panel_id}_population_drift",
                )
                _require(
                    population["changed"] is False,
                    f"{batch_id}_{panel_id}_population_changed",
                )
                _require(
                    population["outcome_or_route_selection_used"] is False,
                    f"{batch_id}_{panel_id}_outcome_selection_used",
                )
            summary = _panel_summary(
                receipt,
                panel_id=panel_id,
                expected_members=member_ids,
            )
            for key in totals:
                totals[key] += int(summary[key])
            for window in summary["windows"]:
                panel_windows.setdefault(window["member_id"], {})[panel_id] = window
        all_members.extend(member_ids)
        all_mints.extend(mints)

    _require(len(all_members) == 5, "member_count_drift")
    _require(len(set(all_members)) == 5, "member_identity_collision")
    _require(len(set(all_mints)) == 5, "mint_identity_collision")

    separation = plan["panel_rules"]["minimum_separation_seconds"]
    maximum_span = plan["panel_rules"]["member_total_span_seconds_max"]
    for member_id, windows in panel_windows.items():
        _require(set(windows) == {"P0", "P1", "P2"}, f"{member_id}_panel_set_drift")
        p0_complete = _utc(windows["P0"]["completed_at"], field="p0_completed_at")
        p1_trigger = _utc(windows["P1"]["triggered_at"], field="p1_triggered_at")
        p1_complete = _utc(windows["P1"]["completed_at"], field="p1_completed_at")
        p2_trigger = _utc(windows["P2"]["triggered_at"], field="p2_triggered_at")
        p2_complete = _utc(windows["P2"]["completed_at"], field="p2_completed_at")
        _require(
            (p1_trigger - p0_complete).total_seconds() >= separation,
            f"{member_id}_p1_too_early",
        )
        _require(
            (p2_trigger - p1_complete).total_seconds() >= separation,
            f"{member_id}_p2_too_early",
        )
        _require(
            (p2_complete - p0_complete).total_seconds() <= maximum_span,
            f"{member_id}_span_expired",
        )

    gate = plan["success_gate"]
    _require(totals["panels"] == gate["complete_panels"], "panel_count_drift")
    _require(
        totals["quote_pairs"] == gate["complete_quote_pairs"],
        "quote_pair_count_drift",
    )
    _require(
        totals["quote_attempts"] == gate["complete_quote_attempts"],
        "quote_attempt_count_drift",
    )
    largest_share = max(len(item["member_ids"]) for item in plan["frozen_batches"]) / len(all_members)
    _require(
        largest_share <= gate["maximum_member_share_one_batch"],
        "batch_share_breach",
    )

    sources = plan["source_batches"]
    _require(
        len(sources) == gate["independent_nomination_batches_total"],
        "source_batch_count_drift",
    )
    _require(
        len({item["source_observation_id"] for item in sources}) == len(sources),
        "source_id_collision",
    )
    _require(
        len({item["source_content_sha256"] for item in sources}) == len(sources),
        "source_content_collision",
    )
    source_times = [_utc(item["observed_at"], field="source_observed_at") for item in sources]
    _require(source_times == sorted(source_times), "source_time_order_drift")
    for role, expected in (
        ("R2_SOURCE_P0_RUNTIME_ACCEPTANCE", sources[1]),
        ("R3_SOURCE_P0_RUNTIME_ACCEPTANCE", sources[2]),
    ):
        observed = evidence_by_role[role]["source"]
        for key in ("source_observation_id", "source_content_sha256", "observed_at"):
            _require(observed[key] == expected[key], f"{role}_{key}_drift")

    final_budget = evidence_by_role["R3_P2_RUNTIME_ACCEPTANCE"]["budget_after_p2"]
    for key, expected in plan["whole_task_usage_at_stop"].items():
        _require(final_budget[key] == expected, f"{key}_drift")
    for used_key, cap_key in (
        ("external_requests", "external_requests_cap"),
        ("source_requests", "source_requests_cap"),
        ("quote_requests", "quote_requests_cap"),
        ("response_bytes", "response_bytes_cap"),
    ):
        _require(final_budget[used_key] <= final_budget[cap_key], f"{used_key}_cap_breach")

    extension_usage = {
        "provider_api_rpc_wss_calls": 0,
        "source_requests": 0,
        "jupiter_calls": 0,
        "received_bytes": 0,
        "local_durable_bytes": 0,
        "local_file_count": 0,
    }
    for role in CAPTURE_ROLES:
        receipt = evidence_by_role[role]
        actions = receipt["actual_actions"]
        extension_usage["provider_api_rpc_wss_calls"] += actions[
            "provider_api_rpc_wss_calls"
        ]
        extension_usage["source_requests"] += actions.get("dexscreener_calls", 0)
        extension_usage["source_requests"] += actions.get(
            "solana_public_rpc_calls", 0
        )
        extension_usage["jupiter_calls"] += actions["jupiter_calls"]
        extension_usage["received_bytes"] += actions["received_bytes"]
        extension_usage["local_durable_bytes"] += actions["local_durable_bytes"]
        extension_usage["local_file_count"] += receipt["local_evidence"]["file_count"]
        for key in (
            "cash_spend_usd_cents",
            "credentials_used",
            "scheduler_or_background_process",
            "deploy",
            "catalog_mutation",
            "source_mutation",
            "wallet_signer_transaction_actions",
            "destructive_actions",
            "merge",
        ):
            value = actions[key]
            _require(value is False if isinstance(value, bool) else value == 0, f"{role}_{key}_leak")
        _require(actions["retries"] == 0, f"{role}_retry_drift")
        _require(actions["concurrency"] == 1, f"{role}_concurrency_drift")
    _require(extension_usage == plan["extension_usage"], "extension_usage_drift")

    progress = evidence_by_role["R3_P2_RUNTIME_ACCEPTANCE"]["final_cohort_progress"]
    _require(
        progress["collection_gate"]
        == "SATISFIED_PENDING_SEPARATE_REVIEW_AND_FREEZE",
        "collection_progress_drift",
    )
    _require(progress["new_members_complete"] == 5, "progress_member_drift")

    recovery = evidence_by_role["R3_PRE_P2_RECOVERY_ACCEPTANCE"]
    _require(recovery["status"] == "PASS_REMOTE_RECOVERY_PROVEN", "recovery_not_proven")
    _require(recovery["verdict"] == "PASS", "recovery_verdict_drift")
    restored = recovery["isolated_restore"]
    _require(restored["source_unchanged"] is True, "recovery_source_changed")
    _require(restored["source_mutations"] == 0, "recovery_source_mutation")
    _require(restored["source_deletions"] == 0, "recovery_source_deletion")
    _require(restored["restore_overwrites"] == 0, "recovery_overwrite")
    _require(
        plan["recovery"]["full_dataset_restore_before_a7"] == "REQUIRED",
        "full_restore_gate_missing",
    )

    _validate_authority(plan["authority"])
    boundary = plan["next_boundary"]
    _require(
        boundary["atom_id"]
        == "T21-A7_DATASET_FREEZE_ACCEPTANCE_CATALOG_FACTORY_FIT_V1",
        "a7_boundary_drift",
    )
    _require(boundary["status"] == "NOT_AUTHORIZED", "a7_authorized")
    _require(boundary["task22_authorized"] is False, "task22_authorized")

    return {
        "status": "PASS",
        "verdict": "FINAL_COHORT_COMPLETE_AND_EVIDENCE_SET_FROZEN_PENDING_A7_RECOVERY",
        "cohort_evidence_frozen": True,
        "dataset_frozen": False,
        "a7_review_eligible": True,
        "task22_eligible": False,
        "new_members_complete": len(all_members),
        "member_ids": all_members,
        "mints": all_mints,
        "complete_panels": totals["panels"],
        "complete_quote_pairs": totals["quote_pairs"],
        "complete_quote_attempts": totals["quote_attempts"],
        "independent_nomination_batches_total": len(sources),
        "maximum_member_share_one_batch": largest_share,
        "extension_usage": extension_usage,
        "whole_task_usage_at_stop": dict(plan["whole_task_usage_at_stop"]),
        "quote_route_price_cost_values_read": False,
        "additional_collection_authorized": False,
        "full_dataset_remote_restore_required": True,
    }


def inventory_evidence_roots(
    repo_root: Path,
    roots: Sequence[Mapping[str, Any]],
) -> JsonObject:
    """Create a canonical read-only inventory of the six evidence roots."""

    repository = repo_root.resolve()
    records: list[JsonObject] = []
    summaries: list[JsonObject] = []
    seen_paths: set[str] = set()
    for item in roots:
        relative_root = str(item["root"])
        root = (repository / relative_root).resolve()
        _require(repository in root.parents, "inventory_root_escape")
        _require(root.is_dir(), f"inventory_root_missing:{relative_root}")
        root_records: list[JsonObject] = []
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            relative = path.relative_to(repository).as_posix()
            _require(relative not in seen_paths, f"inventory_duplicate_path:{relative}")
            seen_paths.add(relative)
            payload = path.read_bytes()
            record = {
                "path": relative,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            records.append(record)
            root_records.append(record)
        stored_bytes = sum(record["bytes"] for record in root_records)
        _require(
            len(root_records) == item["file_count"],
            f"inventory_file_count_drift:{relative_root}",
        )
        _require(
            stored_bytes == item["stored_bytes"],
            f"inventory_stored_bytes_drift:{relative_root}",
        )
        summaries.append(
            {
                "root": relative_root,
                "file_count": len(root_records),
                "stored_bytes": stored_bytes,
                "inventory_sha256": hashlib.sha256(
                    json.dumps(
                        root_records, sort_keys=True, separators=(",", ":")
                    ).encode("utf-8")
                ).hexdigest(),
            }
        )
    return {
        "status": "PASS",
        "root_count": len(summaries),
        "file_count": len(records),
        "stored_bytes": sum(record["bytes"] for record in records),
        "inventory_sha256": hashlib.sha256(
            json.dumps(records, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest(),
        "roots": summaries,
    }
