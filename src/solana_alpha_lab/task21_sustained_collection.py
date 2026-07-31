"""Deterministic local control plane for TASK-21 sustained collection.

This module validates synthetic lifecycle and monitoring evidence only. It has
no network, provider, Drive, scheduler, wallet or transaction capability.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

TASK_ID = "TASK-21"
ATOM_ID = "T21-A6_SUSTAINED_FORWARD_COLLECTION_AND_MONITORING_V1"
OUTPUT_FILENAMES = ("manifest.json", "state_receipt.json")
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
        "tokenranking",
    }
)


class SustainedCollectionError(RuntimeError):
    """A frozen TASK-21 sustained-control invariant was violated."""


@dataclass(frozen=True, slots=True)
class OfflineAcceptance:
    """Canonical bytes produced without external I/O."""

    manifest_bytes: bytes
    receipt_bytes: bytes

    @property
    def file_bytes(self) -> dict[str, bytes]:
        return {
            "manifest.json": self.manifest_bytes,
            "state_receipt.json": self.receipt_bytes,
        }

    @property
    def receipt(self) -> dict[str, Any]:
        return json.loads(self.receipt_bytes)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SustainedCollectionError("value_must_be_canonical_json") from exc


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SustainedCollectionError("yaml_document_must_be_mapping")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SustainedCollectionError("json_document_must_be_mapping")
    return value


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _reject_outcome_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SustainedCollectionError("scenario_key_must_be_text")
            normalized = _normalized_key(key)
            if any(
                normalized == forbidden or normalized.startswith(forbidden)
                for forbidden in FORBIDDEN_OUTCOME_KEYS
            ):
                raise SustainedCollectionError("outcome_field_forbidden_while_active")
            _reject_outcome_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_outcome_fields(item)


def _aware_utc(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise SustainedCollectionError(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SustainedCollectionError(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SustainedCollectionError(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SustainedCollectionError(f"{name}_must_be_nonnegative_integer")
    return value


def _validate_sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise SustainedCollectionError(f"{name}_invalid")
    return value


def validate_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if (
        config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
        or config.get("status")
        != "PREPARED_LOCAL_CONTROL_PLANE_NO_FORWARD_COLLECTION"
    ):
        raise SustainedCollectionError("config_identity_or_status_drift")
    gate = config.get("entry_gate")
    if not isinstance(gate, Mapping) or gate.get("verdict") != "START_WITH_PATCH":
        raise SustainedCollectionError("entry_patch_missing")
    patch = gate.get("patch")
    if (
        not isinstance(patch, Mapping)
        or patch.get("real_launch_blocked") is not True
        or patch.get("technical_probe_automatic_carry_forward") is not False
    ):
        raise SustainedCollectionError("real_launch_must_remain_blocked")
    population = config.get("population")
    if (
        not isinstance(population, Mapping)
        or population.get("real_current_member_count") != 0
        or population.get("technical_probe_automatic_carry_forward") is not False
    ):
        raise SustainedCollectionError("population_boundary_drift")
    authority = config.get("authority")
    if not isinstance(authority, Mapping):
        raise SustainedCollectionError("authority_missing")
    zero_fields = (
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
        "provider_credits",
        "cash_spend_usd_cents",
        "dependency_changes",
    )
    if any(authority.get(field) != 0 for field in zero_fields):
        raise SustainedCollectionError("local_authority_external_value_nonzero")
    if authority.get("scheduler_or_background_process") is not False:
        raise SustainedCollectionError("scheduler_not_authorized")
    frozen = config.get("frozen_inputs")
    if not isinstance(frozen, list) or not frozen:
        raise SustainedCollectionError("frozen_inputs_missing")
    for item in frozen:
        if not isinstance(item, Mapping):
            raise SustainedCollectionError("frozen_input_invalid")
        relative = item.get("path")
        if not isinstance(relative, str):
            raise SustainedCollectionError("frozen_input_path_invalid")
        expected = _validate_sha256("frozen_input_sha256", item.get("sha256"))
        actual = sha256_file(repo_root / relative)
        if actual != expected:
            raise SustainedCollectionError(
                f"frozen_input_hash_drift:{relative}:{expected}:{actual}"
            )


def _deduplicate_events(
    events: object,
    *,
    identity_field: str,
) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(events, list):
        raise SustainedCollectionError(f"{identity_field}_events_must_be_list")
    accepted: dict[str, tuple[bytes, dict[str, Any]]] = {}
    duplicates = 0
    for raw in events:
        if not isinstance(raw, dict):
            raise SustainedCollectionError(f"{identity_field}_event_must_be_mapping")
        identity = raw.get(identity_field)
        if not isinstance(identity, str) or not identity:
            raise SustainedCollectionError(f"{identity_field}_invalid")
        encoded = canonical_json_bytes(raw)
        existing = accepted.get(identity)
        if existing is None:
            accepted[identity] = (encoded, raw)
        elif existing[0] == encoded:
            duplicates += 1
        else:
            raise SustainedCollectionError(f"conflicting_duplicate:{identity_field}")
    return [item[1] for item in accepted.values()], duplicates


def _validate_nomination_events(events: object) -> tuple[list[dict[str, Any]], int]:
    nominations, duplicates = _deduplicate_events(
        events, identity_field="nomination_event_id"
    )
    required = {
        "nomination_event_id",
        "source_asset_id",
        "source_version",
        "source_content_sha256",
        "observed_at",
        "first_reliable_available_at",
        "hypothesis_version_id",
        "watchlist_policy_version",
        "exact_rule_input_values",
        "reason_codes",
        "evidence_checkpoint",
    }
    if not 1 <= len(nominations) <= 8:
        raise SustainedCollectionError("nomination_count_outside_bounds")
    for event in nominations:
        if set(event) != required:
            raise SustainedCollectionError("nomination_fields_drift")
        _validate_sha256("source_content_sha256", event["source_content_sha256"])
        observed = _aware_utc("nomination_observed_at", event["observed_at"])
        reliable = _aware_utc(
            "nomination_first_reliable_available_at",
            event["first_reliable_available_at"],
        )
        if reliable < observed:
            raise SustainedCollectionError(
                "nomination_availability_before_observation"
            )
    return nominations, duplicates


def _validate_membership_events(
    events: object,
    *,
    nomination_ids: set[str],
) -> tuple[list[dict[str, Any]], int]:
    memberships, duplicates = _deduplicate_events(
        events, identity_field="membership_event_id"
    )
    required = {
        "membership_event_id",
        "member_id",
        "mint",
        "mint_decimals",
        "nomination_event_id",
        "hypothesis_version_id",
        "policy_version",
        "state",
        "entered_at",
        "first_reliable_available_at",
        "reason_codes",
        "evidence_checkpoint",
    }
    member_ids: set[str] = set()
    for event in memberships:
        if set(event) != required:
            raise SustainedCollectionError("membership_fields_drift")
        member_id = event["member_id"]
        if not isinstance(member_id, str) or not member_id or member_id in member_ids:
            raise SustainedCollectionError("member_id_invalid_or_duplicate")
        member_ids.add(member_id)
        if event["nomination_event_id"] not in nomination_ids:
            raise SustainedCollectionError("membership_nomination_missing")
        if event["state"] != "WATCHLIST_ACTIVE":
            raise SustainedCollectionError("offline_member_must_be_active")
        if (
            not isinstance(event["mint"], str)
            or not event["mint"]
            or isinstance(event["mint_decimals"], bool)
            or not isinstance(event["mint_decimals"], int)
            or not 0 <= event["mint_decimals"] <= 30
        ):
            raise SustainedCollectionError("member_mint_invalid")
        entered = _aware_utc("member_entered_at", event["entered_at"])
        reliable = _aware_utc(
            "member_first_reliable_available_at",
            event["first_reliable_available_at"],
        )
        if reliable < entered:
            raise SustainedCollectionError("member_availability_before_entry")
    if not 1 <= len(memberships) <= 8:
        raise SustainedCollectionError("active_member_count_outside_bounds")
    return memberships, duplicates


def _panel_metrics(
    panels: object,
    *,
    member_ids: set[str],
) -> tuple[dict[str, int], dict[str, int]]:
    deduplicated, duplicate_count = _deduplicate_events(
        panels, identity_field="window_id"
    )
    required = {
        "window_id",
        "member_id",
        "status",
        "quote_pairs",
        "provider_calls",
        "provider_credits",
        "response_bytes",
        "stored_bytes",
    }
    totals = Counter[str]()
    complete_by_member = Counter[str]()
    for panel in deduplicated:
        if set(panel) != required or panel["member_id"] not in member_ids:
            raise SustainedCollectionError("panel_identity_or_fields_invalid")
        if panel["status"] not in {"COMPLETE", "MISSED"}:
            raise SustainedCollectionError("panel_status_invalid")
        for field in (
            "quote_pairs",
            "provider_calls",
            "provider_credits",
            "response_bytes",
            "stored_bytes",
        ):
            totals[field] += _nonnegative_int(field, panel[field])
        if panel["quote_pairs"] > 4 or panel["provider_calls"] > 8:
            raise SustainedCollectionError("per_panel_cap_exceeded")
        if panel["status"] == "COMPLETE":
            if panel["quote_pairs"] != 4:
                raise SustainedCollectionError("complete_panel_pair_count_invalid")
            totals["complete_panels"] += 1
            complete_by_member[panel["member_id"]] += 1
        else:
            if panel["quote_pairs"] != 0 or panel["provider_calls"] != 0:
                raise SustainedCollectionError("missed_panel_must_not_claim_calls")
            totals["missed_panels"] += 1
    totals["exact_duplicate_panels"] = duplicate_count
    totals["complete_members"] = sum(
        count == 3 for count in complete_by_member.values()
    )
    return dict(totals), dict(complete_by_member)


def _validate_caps(
    config: Mapping[str, Any],
    scenario: Mapping[str, Any],
    metrics: Mapping[str, int],
) -> None:
    caps = config["physical_caps"]
    health = scenario.get("health")
    if not isinstance(health, Mapping):
        raise SustainedCollectionError("health_missing")
    comparisons = {
        "provider_calls": "max_provider_requests",
        "provider_credits": "max_provider_credits",
        "response_bytes": "max_response_bytes",
        "stored_bytes": "max_stored_bytes",
    }
    for observed, cap in comparisons.items():
        if metrics.get(observed, 0) > caps[cap]:
            raise SustainedCollectionError(f"physical_cap_exceeded:{observed}")
    if _nonnegative_int("dataset_bytes", health.get("dataset_bytes")) > caps[
        "max_dataset_bytes"
    ]:
        raise SustainedCollectionError("physical_cap_exceeded:dataset_bytes")
    if _nonnegative_int("free_disk_bytes", health.get("free_disk_bytes")) < caps[
        "min_free_space_bytes_after_write"
    ]:
        raise SustainedCollectionError("physical_cap_exceeded:free_disk_bytes")
    if _nonnegative_int(
        "cash_spend_usd_cents", health.get("cash_spend_usd_cents")
    ) != 0:
        raise SustainedCollectionError("cash_spend_forbidden")


def _lifecycle(elapsed_days: int, sufficient: bool) -> tuple[str, str]:
    if elapsed_days < 30:
        return "ACTIVE", "CONTINUE_UNCHANGED_TO_DAY30"
    if elapsed_days < 45:
        if sufficient:
            return (
                "DAY30_REVIEW",
                "DATASET_READY_FOR_A7_FREEZE_REQUIRES_SEPARATE_AUTHORITY",
            )
        return "DAY30_REVIEW", "CONTINUE_UNCHANGED_TO_DAY45"
    if sufficient:
        return "DAY45_STOPPED", "STOPPED_READY_FOR_A7_REQUIRES_SEPARATE_AUTHORITY"
    return "DAY45_STOPPED", "STOPPED_SAFELY_NEW_PLAN_OR_REDESIGN_REQUIRED"


def build_offline_acceptance(
    *,
    repo_root: Path,
    config_path: Path,
    scenario_path: Path,
    scenario_override: Mapping[str, Any] | None = None,
) -> OfflineAcceptance:
    """Evaluate one synthetic sustained-control scenario without external I/O."""

    config = load_yaml(config_path)
    validate_config(config, repo_root)
    scenario = (
        deepcopy(scenario_override)
        if scenario_override is not None
        else load_json(scenario_path)
    )
    if (
        scenario.get("task_id") != TASK_ID
        or scenario.get("atom_id") != ATOM_ID
        or scenario.get("synthetic_only") is not True
        or scenario.get("contains_market_data") is not False
        or scenario.get("technical_probe_automatic_carry_forward") is not False
    ):
        raise SustainedCollectionError("scenario_identity_or_scope_invalid")
    _reject_outcome_fields(scenario)
    elapsed_days = _nonnegative_int(
        "simulated_elapsed_days", scenario.get("simulated_elapsed_days")
    )
    nominations, nomination_duplicates = _validate_nomination_events(
        scenario.get("nomination_events")
    )
    memberships, membership_duplicates = _validate_membership_events(
        scenario.get("membership_events"),
        nomination_ids={item["nomination_event_id"] for item in nominations},
    )
    metrics, complete_by_member = _panel_metrics(
        scenario.get("panel_receipts"),
        member_ids={item["member_id"] for item in memberships},
    )
    _validate_caps(config, scenario, metrics)

    gaps = scenario.get("gap_events")
    incidents = scenario.get("incident_events")
    if not isinstance(gaps, list) or not isinstance(incidents, list):
        raise SustainedCollectionError("gap_and_incident_events_must_be_lists")
    health = scenario["health"]
    backup_age = _nonnegative_int("backup_age_hours", health.get("backup_age_hours"))
    restore_age = _nonnegative_int(
        "restore_proof_age_hours", health.get("restore_proof_age_hours")
    )
    recovery_healthy = (
        health.get("health_state") == "HEALTHY"
        and backup_age <= config["recovery"]["backup_maximum_age_hours"]
        and restore_age <= config["recovery"]["restore_proof_maximum_age_hours"]
    )
    admission_times = [
        _aware_utc("member_entered_at", item["entered_at"]) for item in memberships
    ]
    distinct_dates = len({item.date().isoformat() for item in admission_times})
    distinct_weeks = len(
        {(item.isocalendar().year, item.isocalendar().week) for item in admission_times}
    )
    sufficient = (
        metrics.get("complete_members", 0)
        >= config["information_sufficiency"]["minimum_complete_members"]
        and metrics.get("complete_panels", 0)
        >= config["information_sufficiency"]["minimum_complete_panels"]
        and metrics.get("quote_pairs", 0)
        >= config["information_sufficiency"]["minimum_complete_quote_pairs"]
        and distinct_dates
        >= config["information_sufficiency"]["minimum_distinct_admission_dates_utc"]
        and distinct_weeks
        >= config["information_sufficiency"]["minimum_distinct_admission_weeks_utc"]
        and recovery_healthy
    )
    lifecycle, decision = _lifecycle(elapsed_days, sufficient)
    config_sha256 = sha256_file(config_path)
    scenario_sha256 = sha256_file(scenario_path)
    receipt = {
        "schema": "smial.task21.sustained-collection-offline-state-receipt",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": "PASS",
        "synthetic_only": True,
        "local_control_plane_only": True,
        "config_sha256": config_sha256,
        "scenario_sha256": scenario_sha256,
        "simulated_elapsed_days": elapsed_days,
        "lifecycle": lifecycle,
        "decision": decision,
        "information_sufficient": sufficient,
        "coverage": {
            "evaluated_nominations": len(nominations),
            "active_members": len(memberships),
            "complete_members": metrics.get("complete_members", 0),
            "complete_panels": metrics.get("complete_panels", 0),
            "missed_panels": metrics.get("missed_panels", 0),
            "complete_quote_pairs": metrics.get("quote_pairs", 0),
            "distinct_admission_dates_utc": distinct_dates,
            "distinct_admission_weeks_utc": distinct_weeks,
            "complete_panels_by_member": dict(sorted(complete_by_member.items())),
        },
        "consumption": {
            "modeled_provider_calls": metrics.get("provider_calls", 0),
            "modeled_provider_credits": metrics.get("provider_credits", 0),
            "modeled_response_bytes": metrics.get("response_bytes", 0),
            "modeled_stored_bytes": metrics.get("stored_bytes", 0),
            "dataset_bytes": health["dataset_bytes"],
            "cash_spend_usd_cents": 0,
        },
        "recovery": {
            "health_state": health.get("health_state"),
            "backup_age_hours": backup_age,
            "restore_proof_age_hours": restore_age,
            "healthy_for_new_windows": recovery_healthy,
        },
        "append_only_evidence": {
            "gap_events_retained": len(gaps),
            "incident_events_retained": len(incidents),
            "exact_duplicate_nominations_deduplicated": nomination_duplicates,
            "exact_duplicate_memberships_deduplicated": membership_duplicates,
            "exact_duplicate_panels_deduplicated": metrics.get(
                "exact_duplicate_panels", 0
            ),
        },
        "real_launch": {
            "authorized": False,
            "real_task21_watchlist_members": 0,
            "technical_probe_automatic_carry_forward": False,
            "blockers": [
                "REAL_VERSIONED_NOMINATION_AND_MEMBERSHIP_SET",
                "CURRENT_RECOVERY_HEALTHY",
                "SUSTAINED_PROVIDER_ENDPOINT_AND_SCHEMA_FROZEN",
                "EXACT_EXTERNAL_COLLECTION_AUTHORITY",
            ],
        },
        "actual_actions": {
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "credential_use": 0,
            "real_candidate_admissions": 0,
            "live_collector_executions": 0,
            "forward_raw_or_dataset_writes": 0,
            "backup_executions": 0,
            "restore_executions": 0,
            "cash_spend_usd_cents": 0,
            "wallet_signer_transaction_actions": 0,
            "scheduler_or_background_process": False,
        },
        "non_claims": [
            "NO_SUSTAINED_FORWARD_COLLECTION_STARTED",
            "NO_REAL_TASK21_WATCHLIST_MEMBER_CREATED",
            "NO_FORWARD_DATASET_CREATED",
            "NO_HYPOTHESIS_RESULT_UNSEALED",
            "NO_A7_FREEZE_OR_CATALOG_TRANSACTION",
        ],
    }
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    manifest = {
        "schema": "smial.task21.sustained-collection-offline-manifest",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "config_sha256": config_sha256,
        "scenario_sha256": scenario_sha256,
        "state_receipt": {
            "logical_path": "state_receipt.json",
            "bytes": len(receipt_bytes),
            "sha256": sha256_bytes(receipt_bytes),
        },
        "synthetic_only": True,
    }
    return OfflineAcceptance(
        manifest_bytes=canonical_json_bytes(manifest) + b"\n",
        receipt_bytes=receipt_bytes,
    )


def materialize_create_once(run: OfflineAcceptance, output_root: Path) -> str:
    """Create ignored local evidence once or deduplicate exact restart bytes."""

    if output_root.exists():
        actual = {
            path.name: path.read_bytes()
            for path in output_root.iterdir()
            if path.is_file()
        }
        if set(actual) != set(OUTPUT_FILENAMES) or any(
            actual[name] != payload for name, payload in run.file_bytes.items()
        ):
            raise SustainedCollectionError("conflicting_or_incomplete_restart")
        return "EXACT_DUPLICATE_RESTART_DEDUPLICATED"
    output_root.mkdir(parents=True, exist_ok=False)
    for name in OUTPUT_FILENAMES:
        path = output_root / name
        with path.open("xb") as handle:
            handle.write(run.file_bytes[name])
        if sha256_file(path) != sha256_bytes(run.file_bytes[name]):
            raise SustainedCollectionError("materialized_readback_hash_mismatch")
    return "CREATED_AND_READBACK_VERIFIED"
