"""Local owner-facing read model for TASK-21 evidence and time gates."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.task21_runtime_recovery import evaluate_recovery_health


JsonObject = dict[str, Any]
UTC = timezone.utc
EXPECTED_TASK_ID = "TASK-21"
EXPECTED_GATE_ID = "TASK21-T1-CLOSE-2026-08-06"
EXPECTED_NEXT_ATOM = (
    "T21-A6S_T1_CLOSE_EVALUATION_AND_BOUNDED_PANEL_CAPTURE_V1"
)
CORRECTED_NEXT_ATOM = (
    "T21-A6S_BOUNDED_ADMISSION_AND_MULTI_HORIZON_CAPTURE_V1"
)
EXPECTED_NOMINATION_STATUS = "OFFLINE_AND_T1_TOKEN2022_REPLAY_PASS"
CORRECTION_RECEIPT_RELATIVE_PATH = (
    "docs/evidence/task21/observation_horizon_policy_acceptance_v1.json"
)
HORIZON_POLICY_RELATIVE_PATH = (
    "configs/task21_observation_horizon_policy_v1.yaml"
)
PRODUCTION_MEMORY_RELATIVE_PATH = (
    "docs/evidence/task17/first_bounded_hypothesis_cycle_v1.json"
)
PRODUCTION_MEMORY_ASSET_ID = "DATA-T17-HYPOTHESIS-RESEARCH-MEMORY-001"
EXPECTED_PRODUCTION_MEMORY_SHA256 = (
    "8c9da2232ab0feec86da130985eaa4e5168539adaa036d0c48f44b00567c06b6"
)
EXPECTED_PRODUCTION_MEMORY_ID = "SMIAL-HYPOTHESIS-RESEARCH-MEMORY"
EXPECTED_PRODUCTION_MEMORY_OWNER = "TASK-17"
DECISION_STATE = {
    "REJECT": "REJECTED",
    "REVISE": "REVISION_REQUIRED",
    "PROMOTE": "PROMOTED",
    "PAUSE": "PAUSED",
    "MARK_DORMANT": "DORMANT",
    "RETIRE": "RETIRED",
    "REACTIVATE": "REACTIVATED",
}
TERMINAL_GATE_STATES = {
    "RESOLVED",
    "CANCELLED_WITH_EVIDENCE",
    "SUPERSEDED_WITH_EVIDENCE",
}


class Task21OwnerPulseError(ValueError):
    """Raised when the owner pulse cannot preserve its truth boundaries."""


def _load_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Task21OwnerPulseError(f"invalid_json:{path.name}") from exc
    if not isinstance(value, dict):
        raise Task21OwnerPulseError(f"json_root_not_object:{path.name}")
    return value


def _load_yaml(path: Path) -> JsonObject:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise Task21OwnerPulseError(f"invalid_yaml:{path.name}") from exc
    if not isinstance(value, dict):
        raise Task21OwnerPulseError(f"yaml_root_not_object:{path.name}")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise Task21OwnerPulseError(f"unreadable_source:{path.name}") from exc


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise Task21OwnerPulseError("invalid_utc_timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise Task21OwnerPulseError("invalid_utc_timestamp") from exc
    if parsed.tzinfo is None:
        raise Task21OwnerPulseError("invalid_utc_timestamp")
    return parsed.astimezone(UTC)


def format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise Task21OwnerPulseError("naive_as_of")
    return (
        value.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def evaluate_time_gate(gate: JsonObject, *, as_of: datetime) -> JsonObject:
    if gate.get("gate_id") != EXPECTED_GATE_ID:
        raise Task21OwnerPulseError("unexpected_gate_id")
    if gate.get("task_id") != EXPECTED_TASK_ID:
        raise Task21OwnerPulseError("unexpected_gate_task")
    if gate.get("required_next_atom") != EXPECTED_NEXT_ATOM:
        raise Task21OwnerPulseError("unexpected_required_next_atom")
    if any(
        value != 0
        for value in gate.get("authority_granted_by_marker", {}).values()
    ):
        raise Task21OwnerPulseError("external_authority_inferred_from_marker")

    earliest_at = parse_utc(gate["earliest_at"])
    normalized_as_of = as_of.astimezone(UTC)
    remaining_seconds = max(
        0,
        int((earliest_at - normalized_as_of).total_seconds()),
    )
    status = gate.get("status")

    if status == "ACTIVE_WAITING":
        if normalized_as_of >= earliest_at:
            state = "DUE_PREEMPT_PARALLEL_WORK"
            parallel_work_allowed = False
            owner_action_required = True
        else:
            state = "WAITING_PARALLEL_WORK_ALLOWED"
            parallel_work_allowed = True
            owner_action_required = False
    elif status == "SUPERSEDED_WITH_EVIDENCE":
        resolution = gate.get("resolution", {})
        boundary = gate.get("effective_next_boundary", {})
        if (
            resolution.get("disposition")
            != "P7D_EXCLUSIVE_WAIT_SUPERSEDED_FORWARD_ONLY"
            or boundary.get("required_next_atom") != CORRECTED_NEXT_ATOM
            or boundary.get("calendar_wait_required") is not False
        ):
            raise Task21OwnerPulseError("invalid_gate_correction")
        state = "READY_FOR_ADMISSION_AND_CAPTURE_AUTHORITY"
        parallel_work_allowed = True
        owner_action_required = True
    elif status in TERMINAL_GATE_STATES:
        state = status
        parallel_work_allowed = True
        owner_action_required = False
    else:
        raise Task21OwnerPulseError("invalid_gate_status")

    return {
        "gate_id": gate["gate_id"],
        "source_status": status,
        "state": state,
        "earliest_at": format_utc(earliest_at),
        "remaining_seconds": remaining_seconds,
        "parallel_work_allowed": parallel_work_allowed,
        "owner_action_required": owner_action_required,
        "required_next_atom": (
            CORRECTED_NEXT_ATOM
            if status == "SUPERSEDED_WITH_EVIDENCE"
            else gate["required_next_atom"]
        ),
        "original_required_next_atom": gate["required_next_atom"],
        "preemption_rule": gate["preemption_rule"],
        "external_authority_granted": False,
    }


def _registry_count(root: Path, relative_path: str) -> int:
    registry = _load_yaml(root / relative_path)
    records = registry.get("records")
    if not isinstance(records, list):
        raise Task21OwnerPulseError(f"registry_records_not_list:{relative_path}")
    return len(records)


def _validate_non_negative(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Task21OwnerPulseError(f"negative_or_impossible_counter:{name}")
    return value


def _source_entry(root: Path, relative_path: str) -> JsonObject:
    path = root / relative_path
    return {
        "path": relative_path,
        "sha256": _sha256(path),
    }


def _production_memory_binding(
    root: Path,
    runtime_hypothesis: JsonObject,
) -> JsonObject:
    memory_path = root / PRODUCTION_MEMORY_RELATIVE_PATH
    memory_sha256 = _sha256(memory_path)
    if memory_sha256 != EXPECTED_PRODUCTION_MEMORY_SHA256:
        raise Task21OwnerPulseError("production_hypothesis_memory_hash_drift")

    memory = _load_json(memory_path)
    if (
        memory.get("memory_id") != EXPECTED_PRODUCTION_MEMORY_ID
        or memory.get("truth_owner") != EXPECTED_PRODUCTION_MEMORY_OWNER
        or memory.get("append_only") is not True
    ):
        raise Task21OwnerPulseError("production_hypothesis_memory_identity_drift")
    memory_as_of = memory.get("as_of")
    parse_utc(memory_as_of)

    runtime_version_id = runtime_hypothesis.get("hypothesis_version_id")
    versions = memory.get("hypothesis_versions")
    if not isinstance(versions, list):
        raise Task21OwnerPulseError("production_hypothesis_versions_not_list")
    matches = [
        record
        for record in versions
        if isinstance(record, dict)
        and record.get("hypothesis_version_id") == runtime_version_id
    ]
    if len(matches) != 1:
        raise Task21OwnerPulseError("runtime_hypothesis_not_in_production_memory")
    version = matches[0]
    if version.get("definition_sha256") != runtime_hypothesis.get(
        "definition_sha256"
    ):
        raise Task21OwnerPulseError("runtime_hypothesis_definition_mismatch")

    decisions = memory.get("decision_events")
    if not isinstance(decisions, list):
        raise Task21OwnerPulseError("production_decision_events_not_list")
    matching_decisions = [
        decision
        for decision in decisions
        if isinstance(decision, dict)
        and decision.get("hypothesis_version_id") == runtime_version_id
    ]
    if not matching_decisions:
        raise Task21OwnerPulseError("production_hypothesis_state_missing")
    try:
        latest_decision = max(
            matching_decisions,
            key=lambda decision: (
                parse_utc(decision["effective_at"]),
                decision["decision_event_id"],
            ),
        )
    except (KeyError, TypeError) as exc:
        raise Task21OwnerPulseError(
            "production_hypothesis_state_invalid"
        ) from exc
    current_state = DECISION_STATE.get(latest_decision.get("decision_kind"))
    if current_state is None:
        raise Task21OwnerPulseError("production_hypothesis_state_invalid")
    if current_state != runtime_hypothesis.get("current_state"):
        raise Task21OwnerPulseError("runtime_hypothesis_state_mismatch")

    return {
        "asset_id": PRODUCTION_MEMORY_ASSET_ID,
        "memory_id": memory["memory_id"],
        "truth_owner": memory["truth_owner"],
        "as_of": memory_as_of,
        "content_sha256": memory_sha256,
        "append_only": True,
        "hypothesis_version_id": runtime_version_id,
        "family_id": version.get("family_id"),
        "research_cycle_id": version.get("research_cycle_id"),
        "origin_id": version.get("origin_id"),
        "definition_sha256": version.get("definition_sha256"),
        "current_state_as_of_memory": current_state,
        "state_source_decision_event_id": latest_decision.get(
            "decision_event_id"
        ),
        "runtime_binding_consistent": True,
    }


def build_owner_pulse(
    *,
    repository_root: Path,
    as_of: datetime | None = None,
    free_disk_bytes: int | None = None,
) -> JsonObject:
    root = repository_root.resolve()
    observed_at = (as_of or datetime.now(UTC)).astimezone(UTC)
    if observed_at.tzinfo is None:
        raise Task21OwnerPulseError("naive_as_of")

    marker_path = root / "control" / "active_time_gates.json"
    marker = _load_json(marker_path)
    gates = marker.get("gates")
    if not isinstance(gates, list):
        raise Task21OwnerPulseError("active_time_gates_not_list")
    matching = [
        gate
        for gate in gates
        if isinstance(gate, dict) and gate.get("gate_id") == EXPECTED_GATE_ID
    ]
    if len(matching) != 1:
        raise Task21OwnerPulseError("missing_or_duplicate_active_time_gate")
    gate_source = matching[0]
    gate = evaluate_time_gate(gate_source, as_of=observed_at)

    source_receipt_binding = gate_source.get("source_receipt", {})
    receipt_relative = source_receipt_binding.get("path")
    if not isinstance(receipt_relative, str):
        raise Task21OwnerPulseError("missing_source_receipt_path")
    nomination_path = root / receipt_relative
    if _sha256(nomination_path) != source_receipt_binding.get("sha256"):
        raise Task21OwnerPulseError("source_receipt_hash_drift")
    nomination = _load_json(nomination_path)
    if nomination.get("status") != EXPECTED_NOMINATION_STATUS:
        raise Task21OwnerPulseError("nomination_receipt_not_pass")
    replay = nomination.get("live_replay_receipt")
    if not isinstance(replay, dict) or replay.get("status") != "PASS":
        raise Task21OwnerPulseError("nomination_receipt_not_pass")
    if replay.get("t1_close_at") != gate_source.get("earliest_at"):
        raise Task21OwnerPulseError("t1_close_mismatch")

    correction_receipt: JsonObject | None = None
    horizon_policy: JsonObject | None = None
    if gate_source.get("status") == "SUPERSEDED_WITH_EVIDENCE":
        resolution = gate_source.get("resolution", {})
        receipt_binding = resolution.get("result_receipt", {})
        policy_binding = resolution.get("replacement_policy", {})
        if (
            receipt_binding.get("path") != CORRECTION_RECEIPT_RELATIVE_PATH
            or policy_binding.get("path") != HORIZON_POLICY_RELATIVE_PATH
        ):
            raise Task21OwnerPulseError("invalid_gate_correction_pointer")
        correction_path = root / CORRECTION_RECEIPT_RELATIVE_PATH
        policy_path = root / HORIZON_POLICY_RELATIVE_PATH
        if _sha256(correction_path) != receipt_binding.get("sha256"):
            raise Task21OwnerPulseError("gate_correction_receipt_hash_drift")
        if _sha256(policy_path) != policy_binding.get("sha256"):
            raise Task21OwnerPulseError("horizon_policy_hash_drift")
        correction_receipt = _load_json(correction_path)
        horizon_policy = _load_yaml(policy_path)
        if (
            correction_receipt.get("verdict")
            != "P7D_EXCLUSIVE_WAIT_SUPERSEDED_FORWARD_ONLY"
            or horizon_policy.get("policy_id")
            != "OBSERVATION-HORIZON-POLICY-T21-001"
        ):
            raise Task21OwnerPulseError("invalid_gate_correction_evidence")

    derived = replay.get("derived_partition", {})
    nomination_count = _validate_non_negative(
        "nomination_events",
        derived.get("nomination_events"),
    )
    actual_actions = nomination.get("current_atom_actual_actions", {})
    admissions = _validate_non_negative(
        "real_candidate_admissions",
        actual_actions.get("real_candidate_admissions"),
    )
    external_requests = _validate_non_negative(
        "task21_external_requests_cumulative",
        nomination["retained_source_history"].get(
            "task21_external_requests_cumulative"
        ),
    )
    cash_spend = _validate_non_negative(
        "cash_spend_usd_cents",
        actual_actions.get("cash_spend_usd_cents"),
    )

    run_plan_path = root / "configs" / "task21_forward_collection_run_plan_v1.yaml"
    run_plan = _load_yaml(run_plan_path)
    hypothesis = run_plan.get("hypothesis_scope", {})
    caps = run_plan.get("physical_caps", {})
    max_requests = _validate_non_negative(
        "max_provider_requests",
        caps.get("max_provider_requests"),
    )
    if external_requests > max_requests:
        raise Task21OwnerPulseError("external_request_cap_exceeded")

    recovery_path = (
        root
        / "docs"
        / "evidence"
        / "task21"
        / "runtime_recovery_gate_receipt_v1.json"
    )
    recovery = _load_json(recovery_path)
    if recovery.get("verdict") != "PASS":
        raise Task21OwnerPulseError("runtime_recovery_receipt_not_pass")
    remote_backup = replay.get("google_drive", {})
    raw_readback = remote_backup.get("raw_readback", {})
    exact_backup_readback = bool(raw_readback.get("complete_byte_identity"))
    latest_backup_at = parse_utc(remote_backup["created_time"])
    latest_restore_at = parse_utc(
        recovery["health"]["last_successful_restore_at"]
    )
    recovery_health = evaluate_recovery_health(
        observed_at=observed_at,
        last_successful_backup_at=latest_backup_at,
        last_successful_restore_at=latest_restore_at,
        exact_readback_ok=exact_backup_readback,
        restore_ok=bool(recovery["isolated_restore"]["completed_at"]),
    )

    partition_binding = gate_source.get("frozen_replay_partition", {})
    partition_relative = partition_binding.get("path")
    if not isinstance(partition_relative, str):
        raise Task21OwnerPulseError("missing_partition_path")
    partition_path = root / partition_relative
    partition_present = partition_path.is_file()
    partition_identity_ok = False
    if partition_present:
        partition_identity_ok = (
            partition_path.stat().st_size == partition_binding.get("bytes")
            and _sha256(partition_path) == partition_binding.get("sha256")
        )

    if free_disk_bytes is None:
        free_disk_bytes = shutil.disk_usage(root).free
    free_disk = _validate_non_negative("free_disk_bytes", free_disk_bytes)

    registry_counts = {
        "hypotheses": _registry_count(root, "registries/hypotheses.yaml"),
        "research_cycles": _registry_count(
            root, "registries/research_cycles.yaml"
        ),
        "strategies": _registry_count(root, "registries/strategies.yaml"),
        "bot_instances": _registry_count(root, "registries/bot_instances.yaml"),
    }
    production_memory = _production_memory_binding(root, hypothesis)

    attention: list[JsonObject] = []
    if gate["state"] == "DUE_PREEMPT_PARALLEL_WORK":
        attention.append(
            {
                "severity": "CRITICAL",
                "code": "TASK21_T1_CLOSE_DUE",
                "action": EXPECTED_NEXT_ATOM,
            }
        )
    if gate["state"] == "READY_FOR_ADMISSION_AND_CAPTURE_AUTHORITY":
        attention.append(
            {
                "severity": "HIGH",
                "code": "TASK21_CAPTURE_AUTHORITY_REQUIRED",
                "action": CORRECTED_NEXT_ATOM,
            }
        )
    if not partition_present or not partition_identity_ok:
        attention.append(
            {
                "severity": "HIGH",
                "code": "LOCAL_REPLAY_PARTITION_MISSING_OR_DRIFTED",
                "action": "RESTORE_FROM_EXACT_CONTENT_ADDRESSED_BACKUP",
            }
        )
    if recovery_health["health_state"] != "HEALTHY":
        attention.append(
            {
                "severity": "HIGH",
                "code": recovery_health["health_state"],
                "action": "REFRESH_RECOVERY_PROOF_BEFORE_FREEZE_OR_NEW_CAPTURE",
            }
        )
    if gate["state"] == "WAITING_PARALLEL_WORK_ALLOWED":
        attention.append(
            {
                "severity": "INFO",
                "code": "TASK21_T1_FORWARD_WAIT_ACTIVE",
                "action": "NON_INTERFERING_PARALLEL_WORK_ONLY",
            }
        )

    pulse: JsonObject = {
        "schema": "smial.task21.owner-pulse",
        "schema_version": "1.2",
        "read_model_id": "OWNER-PULSE-T21-001",
        "task_id": EXPECTED_TASK_ID,
        "atom_id": "T21-P2R_OWNER_PULSE_PRODUCTION_MEMORY_BINDING_V1",
        "as_of": format_utc(observed_at),
        "truth_ownership": "DERIVED_READ_MODEL_ONLY",
        "attention": attention,
        "active_time_gates": [gate],
        "task21_forward_state": {
            "state": (
                "T1_NOMINATIONS_READY_FOR_ADMISSION_AND_CAPTURE_AUTHORITY"
                if correction_receipt is not None
                else replay["verdict"]
            ),
            "t1_anchor_at": replay["anchor_at"],
            "t1_close_at": replay["t1_close_at"],
            "exclusive_p7d_wait_active": correction_receipt is None,
            "observation_horizon_policy_id": (
                horizon_policy.get("policy_id")
                if horizon_policy is not None
                else None
            ),
            "next_capture_wait_required": (
                None
                if horizon_policy is None
                else horizon_policy["next_boundary"]["calendar_wait_required"]
            ),
            "real_nominations": nomination_count,
            "real_admissions": admissions,
            "panels_captured": 0,
            "local_replay_partition_present": partition_present,
            "local_replay_partition_identity_ok": partition_identity_ok,
            "local_dataset_bytes": (
                partition_binding["bytes"] if partition_identity_ok else 0
            ),
            "coverage_by_required_field": "NOT_AVAILABLE_BEFORE_PANEL_CAPTURE",
            "missingness_by_required_field": "NOT_AVAILABLE_BEFORE_PANEL_CAPTURE",
            "freshness_by_required_field": "NOT_AVAILABLE_BEFORE_PANEL_CAPTURE",
        },
        "hypothesis_factory_state": {
            "runtime_binding": {
                "hypothesis_version_id": hypothesis.get(
                    "hypothesis_version_id"
                ),
                "state": hypothesis.get("current_state"),
                "primary_estimand": hypothesis.get("primary_estimand"),
                "outcome_tuning_allowed": False,
            },
            "production_hypothesis_memory": production_memory,
            "legacy_lifecycle_registries": {
                "role": "TASK03_SKELETONS_PRESERVED_NO_SYNTHETIC_BACKFILL",
                "intentionally_empty": all(
                    count == 0 for count in registry_counts.values()
                ),
                "counts": registry_counts,
            },
            "truth_note": (
                "TASK21_RUNTIME_BINDING_MATCHES_TASK17_PRODUCTION_MEMORY;"
                "LEGACY_REGISTRIES_ARE_NOT_THE_PRODUCTION_MEMORY"
            ),
        },
        "recovery_and_storage": {
            **recovery_health,
            "last_closed_partition_at": None,
            "last_successful_backup_at": format_utc(latest_backup_at),
            "last_successful_backup_sha256": raw_readback.get("sha256"),
            "backup_readback_status": (
                "EXACT_MATCH" if exact_backup_readback else "FAILED"
            ),
            "last_successful_restore_at": format_utc(latest_restore_at),
            "free_disk_bytes": free_disk,
            "evidence_conflict_state": "NONE",
        },
        "cost_and_authority": {
            "provider_or_source_requests_used": external_requests,
            "provider_or_source_requests_cap": max_requests,
            "provider_credits_used": 0,
            "provider_credits_cap": caps.get("max_provider_credits"),
            "provider_credit_claim": "NO_BILLED_CREDITS_EVIDENCED",
            "response_bytes_used": None,
            "response_bytes_cap": caps.get("max_response_bytes"),
            "response_bytes_state": "NOT_RECONCILED_BY_CURRENT_RECEIPT",
            "cash_spend_usd_cents": cash_spend,
            "credentials_used": 0,
            "wallet_signer_transaction_actions": 0,
            "external_authority_granted_by_pulse": False,
        },
        "unavailable_product_truth": {
            "open_positions": "NOT_IMPLEMENTED",
            "realized_pnl": "NOT_IMPLEMENTED",
            "hypothetical_pnl": "NOT_ESTABLISHED",
            "alpha": "NOT_ESTABLISHED",
        },
        "evidence_sources": [
            _source_entry(root, "control/active_time_gates.json"),
            _source_entry(root, receipt_relative),
            *(
                [
                    _source_entry(root, CORRECTION_RECEIPT_RELATIVE_PATH),
                    _source_entry(root, HORIZON_POLICY_RELATIVE_PATH),
                ]
                if correction_receipt is not None
                else []
            ),
            _source_entry(
                root,
                "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json",
            ),
            _source_entry(
                root,
                "configs/task21_forward_collection_run_plan_v1.yaml",
            ),
            _source_entry(root, PRODUCTION_MEMORY_RELATIVE_PATH),
            _source_entry(root, "registries/hypotheses.yaml"),
            _source_entry(root, "registries/research_cycles.yaml"),
            _source_entry(root, "registries/strategies.yaml"),
            _source_entry(root, "registries/bot_instances.yaml"),
        ],
        "side_effects": {
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "raw_or_dataset_writes": 0,
            "scheduler_or_background_process": False,
            "credentials_used": 0,
            "cash_spend_usd_cents": 0,
            "wallet_signer_transaction_actions": 0,
        },
    }
    return pulse


def render_owner_pulse_text(pulse: JsonObject) -> str:
    gate = pulse["active_time_gates"][0]
    task = pulse["task21_forward_state"]
    recovery = pulse["recovery_and_storage"]
    costs = pulse["cost_and_authority"]
    factory = pulse["hypothesis_factory_state"]
    memory = factory["production_hypothesis_memory"]
    registry = factory["legacy_lifecycle_registries"]["counts"]
    lines = [
        "TASK-21 OWNER PULSE",
        f"Срез: {pulse['as_of']}",
        "",
        "Сейчас требует внимания:",
    ]
    for item in pulse["attention"]:
        lines.append(
            f"- [{item['severity']}] {item['code']} -> {item['action']}"
        )
    lines.extend(
        [
            "",
            (
                f"T1: {gate['state']}; original_p7d={gate['earliest_at']}; "
                f"remaining_seconds={gate['remaining_seconds']}"
            ),
            (
                f"Кандидаты: nominations={task['real_nominations']}, "
                f"admissions={task['real_admissions']}, "
                f"panels={task['panels_captured']}"
            ),
            (
                f"Recovery: {recovery['health_state']}; "
                f"backup_age_hours={recovery['backup_age_hours']}; "
                f"restore_age_hours={recovery['restore_proof_age_hours']}"
            ),
            (
                "Бюджет: "
                f"requests={costs['provider_or_source_requests_used']}/"
                f"{costs['provider_or_source_requests_cap']}, "
                f"cash_usd_cents={costs['cash_spend_usd_cents']}"
            ),
            (
                "Production memory: "
                f"{memory['hypothesis_version_id']}; "
                f"state={memory['current_state_as_of_memory']}; "
                f"as_of={memory['as_of']}"
            ),
            (
                "Legacy registries (намеренно пусты): "
                f"hypotheses={registry['hypotheses']}, "
                f"cycles={registry['research_cycles']}, "
                f"strategies={registry['strategies']}, "
                f"bots={registry['bot_instances']}"
            ),
            "Позиции/PnL/alpha: NOT_IMPLEMENTED / NOT_ESTABLISHED",
            "Read model не даёт authority на внешние или торговые действия.",
        ]
    )
    return "\n".join(lines) + "\n"
