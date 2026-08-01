"""Local owner-facing read model for TASK-21 evidence and time gates."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
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
H1_GATE_PREFIX = "TASK21-H1-"
H1_NEXT_ATOM = "T21-A6S_H1_FOREGROUND_CAPTURE_V1"
H6_GATE_PREFIX = "TASK21-H6-"
H6_NEXT_ATOM = "T21-A6S_H6_FOREGROUND_CAPTURE_V1"
H24_GATE_PREFIX = "TASK21-H24-"
H24_NEXT_ATOM = "T21-A6S_H24_FOREGROUND_CAPTURE_V1"
H72_NEXT_ATOM = "T21-A6S_H72_FOREGROUND_CAPTURE_V1"
H168_NEXT_ATOM = "T21-A6S_H168_FOREGROUND_CAPTURE_V1"
MOSCOW = timezone(timedelta(hours=3))
FROZEN_SENTINEL_OFFSETS_SECONDS = {
    "H24": 86_400,
    "H72": 259_200,
    "H168": 604_800,
}
FUTURE_HORIZON_ATOMS = {
    "H24": H24_NEXT_ATOM,
    "H72": H72_NEXT_ATOM,
    "H168": H168_NEXT_ATOM,
}
H0_RECEIPT_RELATIVE_PATH = (
    "docs/evidence/task21/h0_admission_capture_runtime_acceptance_v1.json"
)
H1_RECEIPT_RELATIVE_PATH = (
    "docs/evidence/task21/h1_foreground_capture_runtime_acceptance_v1.json"
)
H6_RECEIPT_RELATIVE_PATH = (
    "docs/evidence/task21/h6_foreground_capture_runtime_acceptance_v1.json"
)
H24_RECEIPT_RELATIVE_PATH = (
    "docs/evidence/task21/h24_foreground_capture_runtime_acceptance_v1.json"
)
PRE_H24_RECOVERY_RELATIVE_PATH = (
    "docs/evidence/task21/pre_h24_recovery_refresh_acceptance_v1.json"
)
EXPECTED_NOMINATION_STATUS = "OFFLINE_AND_T1_TOKEN2022_REPLAY_PASS"
CORRECTION_RECEIPT_RELATIVE_PATH = (
    "docs/evidence/task21/observation_horizon_policy_acceptance_v1.json"
)
HORIZON_POLICY_RELATIVE_PATH = (
    "configs/task21_observation_horizon_policy_v1.yaml"
)
SENTINEL_REBASE_RELATIVE_PATH = (
    "configs/task21_post_h6_gap_sentinel_value_rebase_v1.yaml"
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
    "RESOLVED_WITH_EVIDENCE",
    "RESOLVED_WITH_GAP_EVIDENCE",
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


def _format_exact(value: datetime, *, zone: timezone = UTC) -> str:
    if value.tzinfo is None:
        raise Task21OwnerPulseError("naive_schedule_timestamp")
    return value.astimezone(zone).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def build_observation_schedule(
    *,
    horizon_policy: JsonObject,
    sentinel_rebase: JsonObject,
    h0_receipt: JsonObject,
    active_gate: JsonObject,
    evaluated_gate: JsonObject,
    as_of: datetime,
) -> JsonObject:
    """Show one minimum-age H24 gate and dormant future candidates."""

    capture_clock = horizon_policy.get("capture_clock")
    if not isinstance(capture_clock, dict):
        raise Task21OwnerPulseError("horizon_schedule_clock_missing")
    raw_offsets = capture_clock.get("offsets")
    if not isinstance(raw_offsets, list):
        raise Task21OwnerPulseError("horizon_schedule_offsets_missing")
    offsets = {
        item.get("window_id"): item.get("offset_seconds")
        for item in raw_offsets
        if isinstance(item, dict)
    }
    if any(
        offsets.get(horizon_id) != expected
        for horizon_id, expected in FROZEN_SENTINEL_OFFSETS_SECONDS.items()
    ):
        raise Task21OwnerPulseError("horizon_schedule_offset_drift")
    if capture_clock.get("anchor") != "FIRST_AUTHORIZED_CAPTURE":
        raise Task21OwnerPulseError("horizon_schedule_policy_drift")
    h24_rebase = sentinel_rebase.get("h24_rebase", {})
    future_rebase = sentinel_rebase.get("future_horizons", {})
    if (
        sentinel_rebase.get("atom_id")
        != "T21-A6S_POST_H6_GAP_SENTINEL_VALUE_REBASE_V1"
        or sentinel_rebase.get("status")
        != "FROZEN_FORWARD_ONLY_LOCAL_REPAIR"
        or h24_rebase.get("horizon_semantics") != "MINIMUM_AGE_24H_PLUS"
        or h24_rebase.get("latest_at") is not None
        or h24_rebase.get("narrow_expiry_window_used") is not False
        or future_rebase.get("mandatory") != []
        or future_rebase.get("active_time_gates_created") != 0
    ):
        raise Task21OwnerPulseError("sentinel_value_rebase_drift")

    windows = h0_receipt.get("h0", {}).get("windows")
    if not isinstance(windows, list) or len(windows) != 3:
        raise Task21OwnerPulseError("horizon_schedule_h0_population_drift")
    trigger_times = [
        parse_utc(item.get("triggered_at"))
        for item in windows
        if isinstance(item, dict)
    ]
    if len(trigger_times) != 3:
        raise Task21OwnerPulseError("horizon_schedule_h0_trigger_drift")
    anchor = max(trigger_times)

    h24_earliest = anchor + timedelta(
        seconds=FROZEN_SENTINEL_OFFSETS_SECONDS["H24"]
    )
    if (
        not str(active_gate.get("gate_id", "")).startswith(H24_GATE_PREFIX)
        or active_gate.get("required_next_atom") != H24_NEXT_ATOM
        or parse_utc(active_gate.get("earliest_at")) != h24_earliest
        or active_gate.get("latest_at") is not None
        or active_gate.get("time_semantics")
        != "MINIMUM_AGE_NO_EXPIRY_RECORD_ACTUAL_ELAPSED_SECONDS"
        or evaluated_gate.get("gate_id") != active_gate.get("gate_id")
    ):
        raise Task21OwnerPulseError("horizon_schedule_active_gate_drift")

    normalized_as_of = as_of.astimezone(UTC)
    h24_resolved = (
        evaluated_gate.get("source_status") == "RESOLVED_WITH_EVIDENCE"
    )
    schedule: list[JsonObject] = []
    for horizon_id, offset_seconds in FROZEN_SENTINEL_OFFSETS_SECONDS.items():
        earliest = anchor + timedelta(seconds=offset_seconds)
        is_active = horizon_id == "H24"
        schedule.append(
            {
                "horizon_id": horizon_id,
                "state": (
                    evaluated_gate["state"]
                    if is_active
                    else "DEFERRED_TRIGGER_ONLY"
                ),
                "source": (
                    "ACTIVE_TIME_GATE"
                    if is_active
                    else "POST_H6_REBASE_CANDIDATE_HORIZON"
                ),
                "earliest_at": _format_exact(earliest),
                "latest_at": None,
                "earliest_at_msk": _format_exact(earliest, zone=MOSCOW),
                "latest_at_msk": None,
                "remaining_seconds": max(
                    0, int((earliest - normalized_as_of).total_seconds())
                ),
                "required_next_atom": FUTURE_HORIZON_ATOMS[horizon_id],
                "activation_trigger": (
                    "ALREADY_RESOLVED_WITH_EVIDENCE"
                    if is_active and h24_resolved
                    else "EXACT_ACTIVE_GATE_PLUS_SEPARATE_USER_AUTHORITY"
                    if is_active
                    else "NAMED_NEED_PLUS_FRESH_BUDGET_PLUS_EXACT_AUTHORITY"
                ),
                "external_authority_granted": False,
                "automatic_execution": False,
            }
        )
    return {
        "status": (
            "H24_CAPTURED_H72_H168_TRIGGER_ONLY"
            if h24_resolved
            else "H24_MINIMUM_AGE_ACTIVE_H72_H168_TRIGGER_ONLY"
        ),
        "basis": "LATEST_H0_TRIGGER_PLUS_POST_H6_VALUE_REBASE",
        "h0_anchor_at": _format_exact(anchor),
        "timing_default": "NOT_BEFORE_PLUS_ACTUAL_ELAPSED_TIME",
        "narrow_expiry_window_used": False,
        "scheduler_or_background_process": False,
        "windows": schedule,
    }


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
    gate_id = gate.get("gate_id")
    if gate_id == EXPECTED_GATE_ID:
        expected_next_atom = EXPECTED_NEXT_ATOM
    elif isinstance(gate_id, str) and gate_id.startswith(H1_GATE_PREFIX):
        expected_next_atom = H1_NEXT_ATOM
    elif isinstance(gate_id, str) and gate_id.startswith(H6_GATE_PREFIX):
        expected_next_atom = H6_NEXT_ATOM
    elif isinstance(gate_id, str) and gate_id.startswith(H24_GATE_PREFIX):
        expected_next_atom = H24_NEXT_ATOM
    else:
        raise Task21OwnerPulseError("unexpected_gate_id")
    if gate.get("task_id") != EXPECTED_TASK_ID:
        raise Task21OwnerPulseError("unexpected_gate_task")
    if gate.get("required_next_atom") != expected_next_atom:
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
        latest_raw = gate.get("latest_at")
        latest_at = (
            None
            if latest_raw is None
            else parse_utc(latest_raw)
        )
        if latest_at is not None and normalized_as_of > latest_at:
            state = "MISSED_WINDOW_GAP_CLOSE_REQUIRED"
            parallel_work_allowed = False
            owner_action_required = True
        elif normalized_as_of >= earliest_at:
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
        historical_boundary = (
            boundary.get("required_next_atom") == CORRECTED_NEXT_ATOM
            and boundary.get("calendar_wait_required") is False
        )
        h0_resolved_boundary = (
            boundary.get("status") == "RESOLVED_BY_EXACT_H0_RUNTIME_RECEIPT"
            and boundary.get("required_next_atom") == H1_NEXT_ATOM
            and boundary.get("calendar_wait_required") is True
        )
        if (
            resolution.get("disposition")
            != "P7D_EXCLUSIVE_WAIT_SUPERSEDED_FORWARD_ONLY"
            or not (historical_boundary or h0_resolved_boundary)
        ):
            raise Task21OwnerPulseError("invalid_gate_correction")
        state = (
            "H0_RESOLVED_H1_GATE_OWNS_NEXT"
            if h0_resolved_boundary
            else "READY_FOR_ADMISSION_AND_CAPTURE_AUTHORITY"
        )
        parallel_work_allowed = True
        owner_action_required = not h0_resolved_boundary
    elif status in TERMINAL_GATE_STATES:
        state = status
        parallel_work_allowed = True
        owner_action_required = False
    else:
        raise Task21OwnerPulseError("invalid_gate_status")

    return {
        "gate_id": gate_id,
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
    historical_gate_source = matching[0]
    active_gates = [
        item
        for item in gates
        if isinstance(item, dict) and item.get("status") == "ACTIVE_WAITING"
    ]
    if len(active_gates) > 1:
        raise Task21OwnerPulseError("multiple_unresolved_active_time_gates")
    h24_gate_sources = [
        item
        for item in gates
        if isinstance(item, dict)
        and isinstance(item.get("gate_id"), str)
        and item["gate_id"].startswith(H24_GATE_PREFIX)
    ]
    if len(h24_gate_sources) > 1:
        raise Task21OwnerPulseError("duplicate_h24_gate")
    gate_source = (
        active_gates[0]
        if active_gates
        else h24_gate_sources[0]
        if h24_gate_sources
        else historical_gate_source
    )
    gate = evaluate_time_gate(gate_source, as_of=observed_at)

    source_receipt_binding = historical_gate_source.get("source_receipt", {})
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
    if replay.get("t1_close_at") != historical_gate_source.get("earliest_at"):
        raise Task21OwnerPulseError("t1_close_mismatch")

    correction_receipt: JsonObject | None = None
    horizon_policy: JsonObject | None = None
    sentinel_rebase: JsonObject | None = None
    if historical_gate_source.get("status") == "SUPERSEDED_WITH_EVIDENCE":
        resolution = historical_gate_source.get("resolution", {})
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
        sentinel_rebase = _load_yaml(root / SENTINEL_REBASE_RELATIVE_PATH)
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
    h0_receipt: JsonObject | None = None
    h1_receipt: JsonObject | None = None
    h6_receipt: JsonObject | None = None
    h24_receipt: JsonObject | None = None
    h0_panels = 0
    h0_stored_bytes = 0
    h0_response_bytes = 0
    h0_provider_calls = 0
    h1_gate_sources = [
        item
        for item in gates
        if isinstance(item, dict)
        and isinstance(item.get("gate_id"), str)
        and item["gate_id"].startswith(H1_GATE_PREFIX)
    ]
    if len(h1_gate_sources) > 1:
        raise Task21OwnerPulseError("duplicate_h1_gate")
    if h1_gate_sources:
        h0_binding = h1_gate_sources[0].get("h0_result_receipt", {})
        if h0_binding.get("path") != H0_RECEIPT_RELATIVE_PATH:
            raise Task21OwnerPulseError("h0_receipt_pointer_invalid")
        h0_path = root / H0_RECEIPT_RELATIVE_PATH
        if _sha256(h0_path) != h0_binding.get("sha256"):
            raise Task21OwnerPulseError("h0_receipt_hash_drift")
        h0_receipt = _load_json(h0_path)
        if (
            h0_receipt.get("status") != "PASS"
            or h0_receipt.get("verdict")
            != "THREE_REAL_T1_MEMBERS_ADMITTED_AND_H0_CAPTURED"
        ):
            raise Task21OwnerPulseError("h0_receipt_not_pass")
        h0_actions = h0_receipt.get("actual_actions", {})
        admissions = _validate_non_negative(
            "h0_real_candidate_admissions",
            h0_actions.get("real_candidate_admissions"),
        )
        h0_panels = _validate_non_negative(
            "h0_panels_complete",
            h0_receipt.get("h0", {}).get("panels_complete"),
        )
        h0_stored_bytes = _validate_non_negative(
            "h0_local_stored_bytes",
            h0_actions.get("local_stored_bytes"),
        )
        h0_response_bytes = _validate_non_negative(
            "h0_received_bytes",
            h0_receipt.get("h0", {}).get("received_bytes"),
        )
        h0_provider_calls = _validate_non_negative(
            "h0_provider_calls",
            h0_actions.get("provider_api_rpc_wss_calls"),
        )
        external_requests += h0_provider_calls
        cash_spend += _validate_non_negative(
            "h0_cash_spend_usd_cents",
            h0_actions.get("cash_spend_usd_cents"),
        )
    h6_gate_sources = [
        item
        for item in gates
        if isinstance(item, dict)
        and isinstance(item.get("gate_id"), str)
        and item["gate_id"].startswith(H6_GATE_PREFIX)
    ]
    if len(h6_gate_sources) > 1:
        raise Task21OwnerPulseError("duplicate_h6_gate")
    if h6_gate_sources:
        h1_binding = h6_gate_sources[0].get("h1_result_receipt", {})
        if h1_binding.get("path") != H1_RECEIPT_RELATIVE_PATH:
            raise Task21OwnerPulseError("h1_receipt_pointer_invalid")
        h1_path = root / H1_RECEIPT_RELATIVE_PATH
        if _sha256(h1_path) != h1_binding.get("sha256"):
            raise Task21OwnerPulseError("h1_receipt_hash_drift")
        h1_receipt = _load_json(h1_path)
        if (
            h1_receipt.get("status") != "PASS"
            or h1_receipt.get("verdict")
            != "EXACT_H0_POPULATION_CAPTURED_AT_H1"
        ):
            raise Task21OwnerPulseError("h1_receipt_not_pass")
        h1_actions = h1_receipt.get("actual_actions", {})
        h1_panels = _validate_non_negative(
            "h1_panels_complete",
            h1_receipt.get("h1", {}).get("panels_complete"),
        )
        h1_stored_bytes = _validate_non_negative(
            "h1_local_stored_bytes",
            h1_actions.get("local_stored_bytes"),
        )
        h1_response_bytes = _validate_non_negative(
            "h1_received_bytes",
            h1_receipt.get("h1", {}).get("received_bytes"),
        )
        h1_provider_calls = _validate_non_negative(
            "h1_provider_calls",
            h1_actions.get("provider_api_rpc_wss_calls"),
        )
        h0_panels += h1_panels
        h0_stored_bytes += h1_stored_bytes
        h0_response_bytes += h1_response_bytes
        h0_provider_calls += h1_provider_calls
        external_requests += h1_provider_calls
        cash_spend += _validate_non_negative(
            "h1_cash_spend_usd_cents",
            h1_actions.get("cash_spend_usd_cents"),
        )
    if isinstance(gate_source.get("gate_id"), str) and gate_source[
        "gate_id"
    ].startswith(H24_GATE_PREFIX):
        h6_binding = gate_source.get("h6_result_receipt", {})
        if h6_binding.get("path") != H6_RECEIPT_RELATIVE_PATH:
            raise Task21OwnerPulseError("h6_receipt_pointer_invalid")
        h6_path = root / H6_RECEIPT_RELATIVE_PATH
        if _sha256(h6_path) != h6_binding.get("sha256"):
            raise Task21OwnerPulseError("h6_receipt_hash_drift")
        h6_receipt = _load_json(h6_path)
        if (
            h6_receipt.get("status") != "PASS"
            or h6_receipt.get("verdict")
            != "H6_EXPLICIT_GAP_RECORDED_NO_BACKFILL"
            or h6_receipt.get("h6", {}).get("status") != "GAP"
        ):
            raise Task21OwnerPulseError("h6_receipt_not_gap_pass")
        h6_actions = h6_receipt.get("actual_actions", {})
        h0_stored_bytes += _validate_non_negative(
            "h6_local_stored_bytes",
            h6_actions.get("local_stored_bytes"),
        )
        external_requests += _validate_non_negative(
            "h6_provider_calls",
            h6_actions.get("provider_api_rpc_wss_calls"),
        )
        cash_spend += _validate_non_negative(
            "h6_cash_spend_usd_cents",
            h6_actions.get("cash_spend_usd_cents"),
        )

    if (
        isinstance(gate_source.get("gate_id"), str)
        and gate_source["gate_id"].startswith(H24_GATE_PREFIX)
        and gate_source.get("status") == "RESOLVED_WITH_EVIDENCE"
    ):
        h24_binding = gate_source.get("resolution", {}).get(
            "result_receipt", {}
        )
        if h24_binding.get("path") != H24_RECEIPT_RELATIVE_PATH:
            raise Task21OwnerPulseError("h24_receipt_pointer_invalid")
        h24_path = root / H24_RECEIPT_RELATIVE_PATH
        if _sha256(h24_path) != h24_binding.get("sha256"):
            raise Task21OwnerPulseError("h24_receipt_hash_drift")
        h24_receipt = _load_json(h24_path)
        if (
            h24_receipt.get("status") != "PASS"
            or h24_receipt.get("verdict")
            != "ONE_FROZEN_SENTINEL_CAPTURED_AT_H24_PLUS"
            or h24_receipt.get("h24", {}).get("panels_complete") != 1
            or h24_receipt.get("h24", {}).get("actual_elapsed_seconds", 0)
            < FROZEN_SENTINEL_OFFSETS_SECONDS["H24"]
        ):
            raise Task21OwnerPulseError("h24_receipt_not_pass")
        h24_actions = h24_receipt.get("actual_actions", {})
        h24_panels = _validate_non_negative(
            "h24_panels_complete",
            h24_receipt.get("h24", {}).get("panels_complete"),
        )
        h24_stored_bytes = _validate_non_negative(
            "h24_local_stored_bytes",
            h24_actions.get("local_stored_bytes"),
        )
        h24_response_bytes = _validate_non_negative(
            "h24_received_bytes",
            h24_receipt.get("h24", {}).get("received_bytes"),
        )
        h24_provider_calls = _validate_non_negative(
            "h24_provider_calls",
            h24_actions.get("provider_api_rpc_wss_calls"),
        )
        h0_panels += h24_panels
        h0_stored_bytes += h24_stored_bytes
        h0_response_bytes += h24_response_bytes
        h0_provider_calls += h24_provider_calls
        external_requests += h24_provider_calls
        cash_spend += _validate_non_negative(
            "h24_cash_spend_usd_cents",
            h24_actions.get("cash_spend_usd_cents"),
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

    recovery_path = root / PRE_H24_RECOVERY_RELATIVE_PATH
    recovery = _load_json(recovery_path)
    if recovery.get("verdict") != "PASS":
        raise Task21OwnerPulseError("runtime_recovery_receipt_not_pass")
    current_recovery_pointer = gate_source.get("recovery_prerequisite", {}).get(
        "result_receipt", {}
    )
    if (
        current_recovery_pointer.get("path") != PRE_H24_RECOVERY_RELATIVE_PATH
        or current_recovery_pointer.get("sha256") != _sha256(recovery_path)
    ):
        raise Task21OwnerPulseError("current_recovery_receipt_pointer_drift")
    remote_backup = recovery.get("google_drive", {})
    raw_readback = remote_backup.get("raw_readback", {})
    exact_backup_readback = bool(raw_readback.get("complete_byte_identity"))
    latest_backup_at = parse_utc(
        recovery["health"]["last_successful_backup_at"]
    )
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

    partition_binding = historical_gate_source.get(
        "frozen_replay_partition", {}
    )
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
    if horizon_policy is None or sentinel_rebase is None or h0_receipt is None:
        raise Task21OwnerPulseError("observation_schedule_inputs_unavailable")
    observation_schedule = build_observation_schedule(
        horizon_policy=horizon_policy,
        sentinel_rebase=sentinel_rebase,
        h0_receipt=h0_receipt,
        active_gate=gate_source,
        evaluated_gate=gate,
        as_of=observed_at,
    )

    attention: list[JsonObject] = []
    if gate["state"] == "DUE_PREEMPT_PARALLEL_WORK":
        attention.append(
            {
                "severity": "CRITICAL",
                "code": (
                    "TASK21_H24_CAPTURE_DUE"
                    if gate["gate_id"].startswith(H24_GATE_PREFIX)
                    else (
                        "TASK21_H6_CAPTURE_DUE"
                        if gate["gate_id"].startswith(H6_GATE_PREFIX)
                        else (
                        "TASK21_H1_CAPTURE_DUE"
                        if gate["gate_id"].startswith(H1_GATE_PREFIX)
                        else "TASK21_T1_CLOSE_DUE"
                        )
                    )
                ),
                "action": gate["required_next_atom"],
            }
        )
    if gate["state"] == "MISSED_WINDOW_GAP_CLOSE_REQUIRED":
        attention.append(
            {
                "severity": "CRITICAL",
                "code": (
                    "TASK21_H24_WINDOW_MISSED"
                    if gate["gate_id"].startswith(H24_GATE_PREFIX)
                    else (
                        "TASK21_H6_WINDOW_MISSED"
                        if gate["gate_id"].startswith(H6_GATE_PREFIX)
                        else "TASK21_H1_WINDOW_MISSED"
                    )
                ),
                "action": gate["required_next_atom"],
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
                "code": (
                    "TASK21_H24_FORWARD_WAIT_ACTIVE"
                    if gate["gate_id"].startswith(H24_GATE_PREFIX)
                    else (
                        "TASK21_H6_FORWARD_WAIT_ACTIVE"
                        if gate["gate_id"].startswith(H6_GATE_PREFIX)
                        else (
                        "TASK21_H1_FORWARD_WAIT_ACTIVE"
                        if gate["gate_id"].startswith(H1_GATE_PREFIX)
                        else "TASK21_T1_FORWARD_WAIT_ACTIVE"
                        )
                    )
                ),
                "action": "NON_INTERFERING_PARALLEL_WORK_ONLY",
            }
        )

    pulse: JsonObject = {
        "schema": "smial.task21.owner-pulse",
        "schema_version": "1.7",
        "read_model_id": "OWNER-PULSE-T21-001",
        "task_id": EXPECTED_TASK_ID,
        "atom_id": "T21-P4_MULTI_HORIZON_OWNER_SCHEDULE_V1",
        "as_of": format_utc(observed_at),
        "truth_ownership": "DERIVED_READ_MODEL_ONLY",
        "attention": attention,
        "active_time_gates": [gate],
        "observation_schedule": observation_schedule,
        "task21_forward_state": {
            "state": (
                "H24_CAPTURED_FUTURE_SENTINELS_TRIGGER_ONLY"
                if h24_receipt is not None
                else {
                    "WAITING_PARALLEL_WORK_ALLOWED": (
                        "H24_WAITING" if h6_receipt is not None else
                        ("H6_WAITING" if h1_receipt is not None else "H1_WAITING")
                    ),
                    "DUE_PREEMPT_PARALLEL_WORK": (
                        "H24_CAPTURE_DUE" if h6_receipt is not None else
                        ("H6_CAPTURE_DUE" if h1_receipt is not None else "H1_CAPTURE_DUE")
                    ),
                    "MISSED_WINDOW_GAP_CLOSE_REQUIRED": (
                        "H24_MISSED_GAP_CLOSE_REQUIRED" if h6_receipt is not None else
                        ("H6_MISSED_GAP_CLOSE_REQUIRED" if h1_receipt is not None else "H1_MISSED_GAP_CLOSE_REQUIRED")
                    ),
                }.get(gate["state"], gate["state"])
                if h0_receipt is not None
                else (
                    "T1_NOMINATIONS_READY_FOR_ADMISSION_AND_CAPTURE_AUTHORITY"
                    if correction_receipt is not None
                    else replay["verdict"]
                )
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
                False
                if h24_receipt is not None
                else gate["state"] == "WAITING_PARALLEL_WORK_ALLOWED"
                if h0_receipt is not None
                else (
                    None
                    if horizon_policy is None
                    else horizon_policy["next_boundary"][
                        "calendar_wait_required"
                    ]
                )
            ),
            "real_nominations": nomination_count,
            "real_admissions": admissions,
            "panels_captured": h0_panels,
            "local_replay_partition_present": partition_present,
            "local_replay_partition_identity_ok": partition_identity_ok,
            "local_dataset_bytes": (
                (partition_binding["bytes"] if partition_identity_ok else 0)
                + h0_stored_bytes
            ),
            "coverage_by_required_field": (
                "H0_H1_6_PLUS_H24_SENTINEL_1_CAPTURED_H6_EXPLICIT_GAP_DETAILS_SEALED"
                if h24_receipt is not None
                else "H0_H1_6_OF_9_CAPTURED_H6_EXPLICIT_GAP_DETAILS_SEALED"
                if h6_receipt is not None
                else "H0_H1_6_OF_6_CAPTURED_DETAILS_SEALED"
                if h1_receipt is not None
                else (
                    "H0_3_OF_3_CAPTURED_DETAILS_SEALED"
                    if h0_receipt is not None
                    else "NOT_AVAILABLE_BEFORE_PANEL_CAPTURE"
                )
            ),
            "missingness_by_required_field": (
                "H6_THREE_PANELS_MISSING_EXPLICIT_GAP_NO_BACKFILL_H24_SENTINEL_COMPLETE"
                if h24_receipt is not None
                else "H6_THREE_PANELS_MISSING_EXPLICIT_GAP_NO_BACKFILL"
                if h6_receipt is not None
                else "H0_H1_NO_MISSING_PANELS"
                if h1_receipt is not None
                else (
                    "H0_NO_MISSING_PANELS"
                    if h0_receipt is not None
                    else "NOT_AVAILABLE_BEFORE_PANEL_CAPTURE"
                )
            ),
            "freshness_by_required_field": (
                gate["state"]
                if h0_receipt is not None
                else "NOT_AVAILABLE_BEFORE_PANEL_CAPTURE"
            ),
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
            "last_closed_partition_at": (
                None
                if h0_receipt is None
                else (
                    h24_receipt.get("completed_at")
                    if h24_receipt is not None
                    else h6_receipt.get("completed_at")
                    if h6_receipt is not None
                    else h1_receipt.get("completed_at")
                    if h1_receipt is not None
                    else h0_receipt.get("completed_at")
                )
            ),
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
            "provider_credits_used": h0_provider_calls,
            "provider_credits_cap": caps.get("max_provider_credits"),
            "provider_credit_claim": (
                "MODELED_ONLY_NO_BILLED_CREDIT_CLAIM"
                if h0_receipt is not None
                else "NO_BILLED_CREDITS_EVIDENCED"
            ),
            "response_bytes_used": (
                h0_response_bytes if h0_receipt is not None else None
            ),
            "response_bytes_cap": caps.get("max_response_bytes"),
            "response_bytes_state": (
                "H0_H1_H24_RECEIPTS_RECONCILED_H6_GAP_RETAINED"
                if h24_receipt is not None
                else "H0_H1_RECEIPTS_RECONCILED_H6_GAP_RETAINED"
                if h6_receipt is not None
                else "H0_H1_RECEIPTS_RECONCILED"
                if h1_receipt is not None
                else (
                    "H0_RECEIPT_RECONCILED"
                    if h0_receipt is not None
                    else "NOT_RECONCILED_BY_CURRENT_RECEIPT"
                )
            ),
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
                    _source_entry(root, SENTINEL_REBASE_RELATIVE_PATH),
                ]
                if correction_receipt is not None
                else []
            ),
            *(
                [_source_entry(root, H0_RECEIPT_RELATIVE_PATH)]
                if h0_receipt is not None
                else []
            ),
            *(
                [_source_entry(root, H1_RECEIPT_RELATIVE_PATH)]
                if h1_receipt is not None
                else []
            ),
            *(
                [_source_entry(root, H6_RECEIPT_RELATIVE_PATH)]
                if h6_receipt is not None
                else []
            ),
            *(
                [_source_entry(root, H24_RECEIPT_RELATIVE_PATH)]
                if h24_receipt is not None
                else []
            ),
            _source_entry(root, PRE_H24_RECOVERY_RELATIVE_PATH),
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
    schedule = pulse["observation_schedule"]
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
                f"TASK-21 forward: {task['state']}; gate={gate['state']}; "
                f"earliest={gate['earliest_at']}; "
                f"remaining_seconds={gate['remaining_seconds']}"
            ),
            "Расписание наблюдений (MSK):",
            *[
                (
                    f"- {item['horizon_id']}: {item['state']}; "
                    f"not_before={item['earliest_at_msk']}; "
                    "expires=NO; "
                    f"action={item['required_next_atom']}"
                )
                for item in schedule["windows"]
            ],
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
