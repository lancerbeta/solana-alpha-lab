"""Forward-only correction for the TASK-21 observation horizon gate."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


UTC = timezone.utc
POLICY_ID = "OBSERVATION-HORIZON-POLICY-T21-001"
POLICY_VERSION = "1.0"
ATOM_ID = "T21-A6S_T1_HORIZON_GATE_CORRECTION_V1"
NEXT_ATOM = "T21-A6S_BOUNDED_ADMISSION_AND_MULTI_HORIZON_CAPTURE_V1"
EXPECTED_OFFSETS = (0, 3600, 21600, 86400, 259200, 604800)


class ObservationHorizonError(ValueError):
    """Raised when the forward-only horizon correction drifts."""


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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ObservationHorizonError("invalid_utc_timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ObservationHorizonError("invalid_utc_timestamp") from exc
    return parsed.astimezone(UTC)


def format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ObservationHorizonError("naive_timestamp")
    return (
        value.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def validate_policy(
    policy: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    if policy.get("policy_id") != POLICY_ID:
        raise ObservationHorizonError("policy_id_drift")
    if policy.get("policy_version") != POLICY_VERSION:
        raise ObservationHorizonError("policy_version_drift")
    if policy.get("atom_id") != ATOM_ID:
        raise ObservationHorizonError("atom_id_drift")
    correction = policy.get("correction", {})
    if correction.get("no_backdating") is not True:
        raise ObservationHorizonError("backdating_not_forbidden")
    if correction.get("historical_receipts_rewritten") is not False:
        raise ObservationHorizonError("historical_rewrite_not_forbidden")
    if correction.get("original_p7d_retained_as_observation_horizon") is not True:
        raise ObservationHorizonError("p7d_horizon_not_retained")

    protected = policy.get("protected_inputs", {})
    source = protected.get("source_receipt", {})
    source_path = repository_root / source.get("path", "")
    if not source_path.is_file():
        raise ObservationHorizonError("source_receipt_missing")
    if sha256_file(source_path) != source.get("sha256"):
        raise ObservationHorizonError("source_receipt_hash_drift")
    if protected.get("nomination_count") != 3:
        raise ObservationHorizonError("nomination_count_drift")
    if protected.get("admission_count") != 0:
        raise ObservationHorizonError("admission_already_occurred")
    if protected.get("panel_count") != 0:
        raise ObservationHorizonError("panel_already_observed")
    if protected.get("quote_outcomes_observed_before_correction") is not False:
        raise ObservationHorizonError("outcome_blindness_broken")

    windows = policy.get("capture_clock", {}).get("offsets")
    if not isinstance(windows, list):
        raise ObservationHorizonError("horizon_offsets_missing")
    offsets = tuple(item.get("offset_seconds") for item in windows)
    if offsets != EXPECTED_OFFSETS:
        raise ObservationHorizonError("horizon_offsets_drift")
    if len({item.get("window_id") for item in windows}) != len(windows):
        raise ObservationHorizonError("duplicate_window_id")
    if policy["capture_clock"].get("global_magic_horizon_allowed") is not False:
        raise ObservationHorizonError("global_magic_horizon_not_forbidden")

    boundary = policy.get("next_boundary", {})
    if boundary.get("atom_id") != NEXT_ATOM:
        raise ObservationHorizonError("next_atom_drift")
    if boundary.get("calendar_wait_required") is not False:
        raise ObservationHorizonError("calendar_wait_still_active")
    for key in (
        "real_candidate_admissions_authorized",
        "provider_api_rpc_wss_calls_authorized",
        "jupiter_quote_calls_authorized",
        "raw_or_dataset_writes_authorized",
        "scheduler_or_background_process_authorized",
        "a7_authorized",
    ):
        if boundary.get(key) is not False:
            raise ObservationHorizonError(f"authority_leak:{key}")


def build_correction_plan(
    policy: Mapping[str, Any],
    *,
    repository_root: Path,
    as_of: datetime,
) -> dict[str, Any]:
    validate_policy(policy, repository_root=repository_root)
    effective_at = parse_utc(policy["effective_at"])
    observed_at = as_of.astimezone(UTC)
    if observed_at < effective_at:
        raise ObservationHorizonError("correction_not_yet_effective")
    correction = policy["correction"]
    protected = policy["protected_inputs"]
    return {
        "schema": "smial.task21.observation-horizon-correction-plan",
        "schema_version": "1.0",
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "atom_id": ATOM_ID,
        "as_of": format_utc(observed_at),
        "verdict": "P7D_EXCLUSIVE_WAIT_SUPERSEDED_FORWARD_ONLY",
        "original_gate": {
            "gate_id": correction["original_gate_id"],
            "anchor_at": correction["original_anchor_at"],
            "earliest_at": correction["original_earliest_at"],
            "retained_as_horizon": True,
        },
        "protected_truth": {
            "source_receipt_sha256": protected["source_receipt"]["sha256"],
            "replay_partition_sha256": protected["replay_partition"]["sha256"],
            "nominations": protected["nomination_count"],
            "admissions": protected["admission_count"],
            "panels": protected["panel_count"],
            "backdating": False,
            "historical_rewrite": False,
            "outcomes_observed_before_correction": False,
        },
        "capture_clock": {
            "anchor": "FIRST_AUTHORIZED_CAPTURE",
            "wait_before_first_capture": "NONE",
            "offset_seconds": list(EXPECTED_OFFSETS),
            "missed_window_policy": "RETAIN_EXPLICIT_GAP_NO_BACKFILL",
        },
        "next_boundary": {
            "state": "READY_FOR_SEPARATE_ADMISSION_AND_CAPTURE_AUTHORITY",
            "atom_id": NEXT_ATOM,
            "external_authority_granted": False,
        },
    }


def materialize_capture_schedule(
    policy: Mapping[str, Any],
    *,
    repository_root: Path,
    first_authorized_capture_at: datetime,
) -> list[dict[str, Any]]:
    validate_policy(policy, repository_root=repository_root)
    effective_at = parse_utc(policy["effective_at"])
    capture_at = first_authorized_capture_at.astimezone(UTC)
    if capture_at < effective_at:
        raise ObservationHorizonError("capture_before_correction")
    windows = policy["capture_clock"]["offsets"]
    return [
        {
            "window_id": window["window_id"],
            "scheduled_at": format_utc(
                capture_at + timedelta(seconds=window["offset_seconds"])
            ),
            "offset_seconds": window["offset_seconds"],
            "purpose": window["purpose"],
        }
        for window in windows
    ]
