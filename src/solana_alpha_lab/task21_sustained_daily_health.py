"""Offline owner read model for TASK-21 sustained-collection daily health.

The module is deliberately projection-only. It reads local synthetic receipts
and has no network, provider, Drive, scheduler, collection or trading ability.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

TASK_ID = "TASK-21"
ATOM_ID = "T21-P6_SUSTAINED_COLLECTION_DAILY_HEALTH_READ_MODEL_V1"
SOURCE_ATOM_ID = "T21-A6_SUSTAINED_FORWARD_COLLECTION_AND_MONITORING_V1"
ZERO_ACTION_FIELDS = (
    "network_calls",
    "provider_api_rpc_wss_calls",
    "drive_reads",
    "drive_writes",
    "credential_use",
    "real_candidate_admissions",
    "live_collector_executions",
    "forward_raw_or_dataset_writes",
    "backup_executions",
    "restore_executions",
    "cash_spend_usd_cents",
    "wallet_signer_transaction_actions",
)
FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "alpha",
        "costbps",
        "hypothesisverdict",
        "pnl",
        "profit",
        "rank",
        "return",
        "roi",
        "score",
        "sharpe",
        "signal",
        "position",
        "tokenranking",
    }
)


class SustainedDailyHealthError(ValueError):
    """An input or projection invariant failed closed."""


def canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as exc:
        raise SustainedDailyHealthError("value_must_be_canonical_json") from exc


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SustainedDailyHealthError("json_document_must_be_mapping")
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SustainedDailyHealthError("yaml_document_must_be_mapping")
    return value


def parse_utc(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise SustainedDailyHealthError(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SustainedDailyHealthError(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SustainedDailyHealthError(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SustainedDailyHealthError(f"{name}_must_be_nonnegative_integer")
    return value


def _validate_sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise SustainedDailyHealthError(f"{name}_invalid")
    return value


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _reject_outcome_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SustainedDailyHealthError("input_key_must_be_text")
            normalized = _normalized_key(key)
            if normalized in FORBIDDEN_OUTCOME_KEYS:
                raise SustainedDailyHealthError("outcome_field_forbidden")
            _reject_outcome_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_outcome_fields(item)


def _validate_unique_ids(name: str, value: object) -> list[str]:
    if not isinstance(value, list):
        raise SustainedDailyHealthError(f"{name}_must_be_list")
    if any(not isinstance(item, str) or not item for item in value):
        raise SustainedDailyHealthError(f"{name}_contains_invalid_id")
    if len(value) != len(set(value)):
        raise SustainedDailyHealthError(f"{name}_contains_duplicate_id")
    return list(value)


def _validate_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if (
        config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
        or config.get("status") != "OFFLINE_SYNTHETIC_ACCEPTANCE_ONLY"
    ):
        raise SustainedDailyHealthError("config_identity_or_status_drift")
    boundary = config.get("truth_boundary")
    if (
        not isinstance(boundary, Mapping)
        or boundary.get("role") != "DERIVED_READ_MODEL_ONLY"
        or boundary.get("input_mode") != "OFFLINE_SYNTHETIC"
        or boundary.get("live_monitoring_claim_allowed") is not False
    ):
        raise SustainedDailyHealthError("truth_boundary_drift")
    authority = config.get("authority")
    if not isinstance(authority, Mapping):
        raise SustainedDailyHealthError("authority_missing")
    numeric_zero = (
        "network_calls",
        "provider_api_rpc_wss_calls",
        "drive_reads",
        "drive_writes",
        "credential_use",
        "live_collection_actions",
        "forward_raw_or_dataset_writes",
        "cash_spend_usd_cents",
        "dependency_changes",
        "wallet_signer_transaction_actions",
    )
    if any(authority.get(field) != 0 for field in numeric_zero):
        raise SustainedDailyHealthError("authority_external_value_nonzero")
    if authority.get("scheduler_or_background_process") is not False:
        raise SustainedDailyHealthError("scheduler_not_authorized")
    frozen_inputs = config.get("frozen_inputs")
    if not isinstance(frozen_inputs, list) or len(frozen_inputs) != 2:
        raise SustainedDailyHealthError("frozen_inputs_drift")
    for item in frozen_inputs:
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            raise SustainedDailyHealthError("frozen_input_invalid")
        expected = _validate_sha256("frozen_input_sha256", item.get("sha256"))
        actual = sha256_file(repo_root / item["path"])
        if actual != expected:
            raise SustainedDailyHealthError(
                f"frozen_input_hash_drift:{item['path']}:{expected}:{actual}"
            )


def _validate_daily_input(
    daily: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
    source_acceptance_path: Path,
) -> tuple[datetime, datetime, list[str], list[str]]:
    required = {
        "schema",
        "schema_version",
        "task_id",
        "synthetic_only",
        "contains_market_data",
        "contains_secrets",
        "as_of_utc",
        "collection_day",
        "last_collection_event_at_utc",
        "expected_terminal_panels_to_date",
        "retained_gap_event_ids",
        "retained_incident_event_ids",
        "source_receipt",
    }
    if set(daily) != required:
        raise SustainedDailyHealthError("daily_input_fields_drift")
    input_contract = config["input_contract"]
    if (
        daily.get("schema") != input_contract["required_daily_schema"]
        or str(daily.get("schema_version"))
        != str(input_contract["required_daily_schema_version"])
        or daily.get("task_id") != TASK_ID
        or daily.get("synthetic_only") is not True
        or daily.get("contains_market_data") is not False
        or daily.get("contains_secrets") is not False
    ):
        raise SustainedDailyHealthError("daily_input_identity_or_scope_drift")
    pointer = daily.get("source_receipt")
    if not isinstance(pointer, Mapping) or set(pointer) != {
        "path",
        "sha256",
        "json_pointer",
    }:
        raise SustainedDailyHealthError("source_receipt_pointer_invalid")
    if (
        pointer.get("path")
        != "docs/evidence/task21/sustained_collection_offline_acceptance_v1.json"
        or pointer.get("json_pointer") != "/offline_state_receipt"
        or pointer.get("sha256") != sha256_file(source_acceptance_path)
    ):
        raise SustainedDailyHealthError("source_receipt_pointer_drift")
    observed_at = parse_utc("as_of_utc", daily.get("as_of_utc"))
    last_event_at = parse_utc(
        "last_collection_event_at_utc",
        daily.get("last_collection_event_at_utc"),
    )
    if last_event_at > observed_at:
        raise SustainedDailyHealthError("collection_event_from_future")
    _nonnegative_int("collection_day", daily.get("collection_day"))
    expected = _nonnegative_int(
        "expected_terminal_panels_to_date",
        daily.get("expected_terminal_panels_to_date"),
    )
    if expected > config["coverage"]["maximum_total_panels"]:
        raise SustainedDailyHealthError("expected_panels_exceed_frozen_maximum")
    gaps = _validate_unique_ids(
        "retained_gap_event_ids", daily.get("retained_gap_event_ids")
    )
    incidents = _validate_unique_ids(
        "retained_incident_event_ids", daily.get("retained_incident_event_ids")
    )
    return observed_at, last_event_at, gaps, incidents


def _validate_source_receipt(
    receipt: Mapping[str, Any], *, config: Mapping[str, Any]
) -> None:
    input_contract = config["input_contract"]
    if (
        receipt.get("schema") != input_contract["required_source_schema"]
        or str(receipt.get("schema_version"))
        != str(input_contract["required_source_schema_version"])
        or receipt.get("task_id") != TASK_ID
        or receipt.get("atom_id") != SOURCE_ATOM_ID
        or receipt.get("status") != "PASS"
        or receipt.get("synthetic_only") is not True
        or receipt.get("local_control_plane_only") is not True
    ):
        raise SustainedDailyHealthError("source_receipt_identity_or_scope_drift")
    actions = receipt.get("actual_actions")
    if not isinstance(actions, Mapping):
        raise SustainedDailyHealthError("source_actual_actions_missing")
    if any(actions.get(field) != 0 for field in ZERO_ACTION_FIELDS):
        raise SustainedDailyHealthError("synthetic_source_has_external_action")
    if actions.get("scheduler_or_background_process") is not False:
        raise SustainedDailyHealthError("synthetic_source_has_scheduler")
    _reject_outcome_fields(receipt)


def _budget_metric(used: int, cap: int, warning_bps: int) -> dict[str, Any]:
    if cap < 0:
        raise SustainedDailyHealthError("budget_cap_must_be_nonnegative")
    if cap == 0:
        return {
            "used": used,
            "cap": cap,
            "remaining": 0,
            "utilization_basis_points": 0 if used == 0 else None,
            "state": "ZERO_CAP_RESPECTED" if used == 0 else "BREACH",
        }
    utilization = used * 10_000 // cap
    if used > cap:
        state = "BREACH"
    elif used == cap:
        state = "EXHAUSTED"
    elif utilization >= warning_bps:
        state = "WARNING"
    else:
        state = "OK"
    return {
        "used": used,
        "cap": cap,
        "remaining": max(cap - used, 0),
        "utilization_basis_points": utilization,
        "state": state,
    }


def _action(
    config: Mapping[str, Any], code: str, reasons: list[str]
) -> dict[str, Any]:
    action = config["owner_actions"].get(code)
    if not isinstance(action, Mapping):
        raise SustainedDailyHealthError(f"owner_action_missing:{code}")
    return {
        "operating_state": action["operating_state"],
        "exact_action_code": code,
        "exact_action_ru": action["text_ru"],
        "reason_codes": reasons,
        "grants_runtime_authority": False,
    }


def build_daily_health(
    *,
    repo_root: Path,
    config_path: Path,
    daily_input_path: Path,
    daily_override: Mapping[str, Any] | None = None,
    state_receipt_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one deterministic offline daily-health projection."""

    config = load_yaml(config_path)
    _validate_config(config, repo_root)
    daily = (
        deepcopy(daily_override)
        if daily_override is not None
        else load_json(daily_input_path)
    )
    source_path = repo_root / daily["source_receipt"]["path"]
    observed_at, last_event_at, gap_ids, incident_ids = _validate_daily_input(
        daily,
        config=config,
        source_acceptance_path=source_path,
    )
    source_acceptance = load_json(source_path)
    source_receipt = (
        deepcopy(state_receipt_override)
        if state_receipt_override is not None
        else source_acceptance.get("offline_state_receipt")
    )
    if not isinstance(source_receipt, dict):
        raise SustainedDailyHealthError("source_state_receipt_missing")
    _validate_source_receipt(source_receipt, config=config)

    collection_day = _nonnegative_int("collection_day", daily["collection_day"])
    if collection_day != source_receipt.get("simulated_elapsed_days"):
        raise SustainedDailyHealthError("collection_day_source_mismatch")
    coverage = source_receipt.get("coverage")
    evidence = source_receipt.get("append_only_evidence")
    consumption = source_receipt.get("consumption")
    recovery = source_receipt.get("recovery")
    if not all(
        isinstance(item, Mapping)
        for item in (coverage, evidence, consumption, recovery)
    ):
        raise SustainedDailyHealthError("source_operational_sections_missing")
    complete = _nonnegative_int("complete_panels", coverage.get("complete_panels"))
    missed = _nonnegative_int("missed_panels", coverage.get("missed_panels"))
    expected = _nonnegative_int(
        "expected_terminal_panels_to_date",
        daily["expected_terminal_panels_to_date"],
    )
    if complete + missed > expected:
        raise SustainedDailyHealthError("terminal_panels_exceed_expected_to_date")
    unaccounted = expected - complete - missed
    if len(gap_ids) != missed or evidence.get("gap_events_retained") != missed:
        raise SustainedDailyHealthError("missed_panel_gap_evidence_mismatch")
    if evidence.get("incident_events_retained") != len(incident_ids):
        raise SustainedDailyHealthError("incident_evidence_mismatch")

    age_seconds = int((observed_at - last_event_at).total_seconds())
    lifecycle = source_receipt.get("lifecycle")
    if lifecycle == "DAY45_STOPPED":
        freshness_state = "NOT_APPLICABLE_COLLECTION_STOPPED"
    elif age_seconds > config["freshness"]["stale_after_hours"] * 3600:
        freshness_state = "STALE"
    elif age_seconds > config["freshness"]["warning_after_hours"] * 3600:
        freshness_state = "WARNING"
    else:
        freshness_state = "FRESH"

    sustained_config = load_yaml(
        repo_root / config["budget"]["source_caps_path"]
    )
    caps = sustained_config["physical_caps"]
    warning_bps = config["budget"]["warning_utilization_basis_points"]
    budget = {
        "provider_requests": _budget_metric(
            _nonnegative_int(
                "modeled_provider_calls", consumption.get("modeled_provider_calls")
            ),
            caps["max_provider_requests"],
            warning_bps,
        ),
        "provider_credits": _budget_metric(
            _nonnegative_int(
                "modeled_provider_credits",
                consumption.get("modeled_provider_credits"),
            ),
            caps["max_provider_credits"],
            warning_bps,
        ),
        "response_bytes": _budget_metric(
            _nonnegative_int(
                "modeled_response_bytes", consumption.get("modeled_response_bytes")
            ),
            caps["max_response_bytes"],
            warning_bps,
        ),
        "stored_bytes": _budget_metric(
            _nonnegative_int(
                "modeled_stored_bytes", consumption.get("modeled_stored_bytes")
            ),
            caps["max_stored_bytes"],
            warning_bps,
        ),
        "dataset_bytes": _budget_metric(
            _nonnegative_int("dataset_bytes", consumption.get("dataset_bytes")),
            caps["max_dataset_bytes"],
            warning_bps,
        ),
        "cash_spend_usd_cents": _budget_metric(
            _nonnegative_int(
                "cash_spend_usd_cents", consumption.get("cash_spend_usd_cents")
            ),
            caps["cash_spend_usd_cents"],
            warning_bps,
        ),
    }
    budget_breach = any(
        item["state"] in {"BREACH", "EXHAUSTED"} for item in budget.values()
    )
    budget_warning = any(item["state"] == "WARNING" for item in budget.values())

    backup_age = _nonnegative_int(
        "backup_age_hours", recovery.get("backup_age_hours")
    )
    restore_age = _nonnegative_int(
        "restore_proof_age_hours", recovery.get("restore_proof_age_hours")
    )
    recovery_healthy = (
        recovery.get("health_state") == "HEALTHY"
        and backup_age <= sustained_config["recovery"]["backup_maximum_age_hours"]
        and restore_age
        <= sustained_config["recovery"]["restore_proof_maximum_age_hours"]
    )
    if recovery.get("healthy_for_new_windows") is not recovery_healthy:
        raise SustainedDailyHealthError("recovery_health_boolean_mismatch")

    if budget_breach or not recovery_healthy:
        reasons = []
        if budget_breach:
            reasons.append("CAP_BREACH_OR_EXHAUSTION")
        if not recovery_healthy:
            reasons.append("RECOVERY_UNHEALTHY")
        owner_decision = _action(config, "SAFE_STOP_RECOVERY_OR_CAP", reasons)
    elif incident_ids:
        owner_decision = _action(
            config, "RESOLVE_OPEN_INCIDENT", ["OPEN_INCIDENT_RETAINED"]
        )
    elif freshness_state == "STALE":
        owner_decision = _action(
            config, "INVESTIGATE_STALE_COLLECTION", ["COLLECTION_EVENT_STALE"]
        )
    elif unaccounted:
        owner_decision = _action(
            config,
            "RECONCILE_UNACCOUNTED_PANEL",
            ["DUE_PANEL_WITHOUT_TERMINAL_OR_GAP"],
        )
    elif lifecycle == "DAY45_STOPPED":
        owner_decision = _action(
            config, "KEEP_STOPPED_REQUEST_DECISION", ["DAY45_HARD_STOP"]
        )
    elif gap_ids:
        owner_decision = _action(
            config, "REVIEW_GAPS_CONTINUE_NO_BACKFILL", ["RETAINED_GAP_PRESENT"]
        )
    elif (
        lifecycle == "DAY30_REVIEW"
        and source_receipt.get("information_sufficient") is True
    ):
        owner_decision = _action(
            config, "REQUEST_A7_FREEZE_REVIEW", ["A7_REVIEW_ELIGIBLE_NOT_AUTHORIZED"]
        )
    elif budget_warning or freshness_state == "WARNING":
        reasons = []
        if budget_warning:
            reasons.append("BUDGET_WARNING")
        if freshness_state == "WARNING":
            reasons.append("FRESHNESS_WARNING")
        owner_decision = _action(config, "WATCH_HEALTH_CONTINUE", reasons)
    else:
        owner_decision = _action(config, "CONTINUE_AND_RECHECK", ["ALL_CHECKS_OK"])

    source_receipt_bytes = canonical_json_bytes(source_receipt)
    return {
        "schema": config["output_contract"]["schema"],
        "schema_version": config["output_contract"]["schema_version"],
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": "PASS",
        "mode": "OFFLINE_SYNTHETIC",
        "truth_role": "DERIVED_READ_MODEL_ONLY",
        "as_of_utc": observed_at.isoformat().replace("+00:00", "Z"),
        "source": {
            "acceptance_path": daily["source_receipt"]["path"],
            "acceptance_sha256": daily["source_receipt"]["sha256"],
            "state_receipt_sha256": sha256_bytes(source_receipt_bytes),
        },
        "collection": {
            "day": collection_day,
            "lifecycle": lifecycle,
            "information_sufficient": source_receipt.get("information_sufficient"),
            "source_decision": source_receipt.get("decision"),
        },
        "coverage": {
            "expected_terminal_panels_to_date": expected,
            "complete_panels": complete,
            "missed_panels": missed,
            "unaccounted_due_panels": unaccounted,
            "missing_total": missed + unaccounted,
            "coverage_basis_points": 10_000 if expected == 0 else complete * 10_000 // expected,
            "retained_gap_event_ids": gap_ids,
        },
        "freshness": {
            "last_collection_event_at_utc": last_event_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "age_seconds": age_seconds,
            "warning_after_hours": config["freshness"]["warning_after_hours"],
            "stale_after_hours": config["freshness"]["stale_after_hours"],
            "state": freshness_state,
        },
        "quota_and_storage": budget,
        "recovery": {
            "health_state": recovery.get("health_state"),
            "backup_age_hours": backup_age,
            "backup_maximum_age_hours": sustained_config["recovery"][
                "backup_maximum_age_hours"
            ],
            "restore_proof_age_hours": restore_age,
            "restore_proof_maximum_age_hours": sustained_config["recovery"][
                "restore_proof_maximum_age_hours"
            ],
            "healthy_for_new_windows": recovery_healthy,
        },
        "incidents": {
            "retained_count": len(incident_ids),
            "retained_incident_event_ids": incident_ids,
        },
        "owner_decision": owner_decision,
        "actual_actions": {
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "live_collection_actions": 0,
            "forward_raw_or_dataset_writes": 0,
            "cash_spend_usd_cents": 0,
            "scheduler_or_background_process": False,
            "wallet_signer_transaction_actions": 0,
        },
        "non_claims": [
            "NOT_LIVE_MONITORING",
            "NO_DATASET_FREEZE",
            "NO_A7_AUTHORITY",
            "NO_HYPOTHESIS_RESULT",
            "NO_PNL_ALPHA_SIGNAL_OR_POSITION_CLAIM",
        ],
    }


def render_daily_health_text(view: Mapping[str, Any]) -> str:
    """Render a compact Russian owner view from the accepted projection."""

    coverage = view["coverage"]
    freshness = view["freshness"]
    recovery = view["recovery"]
    budget = view["quota_and_storage"]
    decision = view["owner_decision"]
    lines = [
        "TASK-21 | OFFLINE SYNTHETIC — НЕ LIVE-МОНИТОРИНГ",
        (
            f"Статус: {decision['operating_state']} | день "
            f"{view['collection']['day']} | {view['collection']['lifecycle']}"
        ),
        (
            "Coverage: "
            f"{coverage['complete_panels']}/{coverage['expected_terminal_panels_to_date']} "
            f"complete; gaps={coverage['missed_panels']}; "
            f"unaccounted={coverage['unaccounted_due_panels']}"
        ),
        (
            f"Свежесть: {freshness['state']}; "
            f"age_seconds={freshness['age_seconds']}"
        ),
        (
            "Quota: "
            f"requests={budget['provider_requests']['used']}/"
            f"{budget['provider_requests']['cap']}; "
            f"credits={budget['provider_credits']['used']}/"
            f"{budget['provider_credits']['cap']}; "
            f"dataset_bytes={budget['dataset_bytes']['used']}/"
            f"{budget['dataset_bytes']['cap']}; "
            f"cash_cents={budget['cash_spend_usd_cents']['used']}"
        ),
        (
            f"Recovery: {recovery['health_state']}; "
            f"backup={recovery['backup_age_hours']}h/"
            f"{recovery['backup_maximum_age_hours']}h; "
            f"restore={recovery['restore_proof_age_hours']}h/"
            f"{recovery['restore_proof_maximum_age_hours']}h"
        ),
        f"Incidents: {view['incidents']['retained_count']}",
        f"Действие владельца: {decision['exact_action_ru']}",
        f"Action code: {decision['exact_action_code']}",
    ]
    return "\n".join(lines) + "\n"
