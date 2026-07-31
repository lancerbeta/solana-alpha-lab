"""Reusable foreground-only quote capture core for TASK-21 H72 and H168."""

from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from solana_alpha_lab.jupiter_quote_logger import (
    DEFAULT_SLIPPAGE_BPS,
    PROVIDER,
    PROVIDER_VERSION,
    QuoteProjection,
    build_buy_panel_requests,
    decide_dependent_sell,
    project_quote_observation,
)
from solana_alpha_lab.jupiter_quote_transport import (
    EXTERNAL_AUTHORITY_PHRASE as TRANSPORT_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate as TransportGate,
    HttpCapture,
)
from solana_alpha_lab.task21_live_shakedown import (
    Task21LiveShakedownError,
    validate_recovery_freshness,
)
from solana_alpha_lab.task21_multi_horizon_capture import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)


TASK_ID = "TASK-21"
CORE_ATOM_ID = "T21-P5_FUTURE_SENTINEL_CAPTURE_CORE_V1"
SCHEMA_VERSION = "1.0"
CALLS_PER_PANEL_MAX = 8
CALLS_TOTAL_MAX = 24
RECEIVED_BYTES_MAX = 3_145_728
DURABLE_BYTES_MAX = 16_777_216
WALL_SECONDS_MAX = 300
MINIMUM_INTERVAL_SECONDS = 2.2
MIN_FREE_SPACE_AFTER_WRITE = 2_147_483_648
WINDOW_GRACE_SECONDS = 600
MEMBERS_EXACT = 3
NOTIONALS_USD = [10, 25, 50, 100]


class Task21FutureSentinelError(RuntimeError):
    """A future sentinel cannot safely proceed."""


class Task21FutureSentinelAuthorityRequired(Task21FutureSentinelError):
    """The exact horizon-specific provider authority is absent."""


@dataclass(frozen=True, slots=True)
class SentinelProfile:
    horizon_id: str
    predecessor_horizon_id: str
    predecessor_runtime_atom_id: str
    runtime_atom_id: str
    gate_id_prefix: str
    offset_seconds_from_latest_h0: int
    output_relative_root: str
    next_horizon_id: str | None
    next_runtime_atom_id: str | None
    next_offset_seconds_from_latest_h0: int | None


EXPECTED_PROFILES: dict[str, dict[str, Any]] = {
    "H72": {
        "predecessor_horizon_id": "H24",
        "predecessor_runtime_atom_id": "T21-A6S_H24_FOREGROUND_CAPTURE_V1",
        "runtime_atom_id": "T21-A6S_H72_FOREGROUND_CAPTURE_V1",
        "gate_id_prefix": "TASK21-H72-",
        "offset_seconds_from_latest_h0": 259_200,
        "output_relative_root": "local/task21_forward/h72_capture",
        "next_horizon_id": "H168",
        "next_runtime_atom_id": "T21-A6S_H168_FOREGROUND_CAPTURE_V1",
        "next_offset_seconds_from_latest_h0": 604_800,
    },
    "H168": {
        "predecessor_horizon_id": "H72",
        "predecessor_runtime_atom_id": "T21-A6S_H72_FOREGROUND_CAPTURE_V1",
        "runtime_atom_id": "T21-A6S_H168_FOREGROUND_CAPTURE_V1",
        "gate_id_prefix": "TASK21-H168-",
        "offset_seconds_from_latest_h0": 604_800,
        "output_relative_root": "local/task21_forward/h168_capture",
        "next_horizon_id": None,
        "next_runtime_atom_id": None,
        "next_offset_seconds_from_latest_h0": None,
    },
}


@dataclass(frozen=True, slots=True)
class FutureSentinelExecutionGate:
    horizon_id: str
    authority_phrase: str

    def __post_init__(self) -> None:
        expected = EXPECTED_PROFILES.get(self.horizon_id, {}).get(
            "runtime_atom_id"
        )
        if self.authority_phrase != expected:
            raise Task21FutureSentinelAuthorityRequired(
                "future_sentinel_external_authority_phrase_mismatch"
            )


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21FutureSentinelError("yaml_root_invalid")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21FutureSentinelError("json_root_invalid")
    return value


def _utc(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise Task21FutureSentinelError(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21FutureSentinelError(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Task21FutureSentinelError(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise Task21FutureSentinelError(
            "future_sentinel_create_only_collision"
        ) from exc


def _inventory(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _relative_path(root: Path, value: object) -> Path:
    if not isinstance(value, str) or "\\" in value:
        raise Task21FutureSentinelError("repository_relative_path_invalid")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise Task21FutureSentinelError("repository_relative_path_invalid")
    resolved_root = root.resolve()
    resolved = (resolved_root / Path(*pure.parts)).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise Task21FutureSentinelError("repository_relative_path_escape")
    return resolved


def load_profiles(core_config_path: Path) -> dict[str, SentinelProfile]:
    config = _load_yaml(core_config_path)
    if (
        config.get("schema") != "smial.task21_future_sentinel_capture_core"
        or config.get("schema_version") != SCHEMA_VERSION
        or config.get("task_id") != TASK_ID
        or config.get("atom_id") != CORE_ATOM_ID
        or config.get("status") != "OFFLINE_VALIDATED_NOT_RUNTIME_BOUND"
    ):
        raise Task21FutureSentinelError("core_config_identity_drift")
    profiles = config.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != 2:
        raise Task21FutureSentinelError("core_profile_count_drift")
    parsed: dict[str, SentinelProfile] = {}
    for item in profiles:
        if not isinstance(item, dict):
            raise Task21FutureSentinelError("core_profile_invalid")
        horizon_id = item.get("horizon_id")
        expected = EXPECTED_PROFILES.get(str(horizon_id))
        if expected is None or any(item.get(key) != value for key, value in expected.items()):
            raise Task21FutureSentinelError("core_profile_contract_drift")
        if horizon_id in parsed:
            raise Task21FutureSentinelError("core_profile_duplicate")
        parsed[str(horizon_id)] = SentinelProfile(
            horizon_id=str(horizon_id),
            **expected,
        )
    if set(parsed) != set(EXPECTED_PROFILES):
        raise Task21FutureSentinelError("core_profile_identity_drift")

    runtime = config.get("runtime_contract", {})
    expected_runtime = {
        "population_members_exact": MEMBERS_EXACT,
        "panels_max": MEMBERS_EXACT,
        "provider_calls_per_panel_max": CALLS_PER_PANEL_MAX,
        "provider_calls_total_max": CALLS_TOTAL_MAX,
        "modeled_provider_credits_max": CALLS_TOTAL_MAX,
        "wall_seconds_max": WALL_SECONDS_MAX,
        "received_response_bytes_max": RECEIVED_BYTES_MAX,
        "durable_local_bytes_max": DURABLE_BYTES_MAX,
        "minimum_interval_seconds": MINIMUM_INTERVAL_SECONDS,
        "minimum_free_space_after_write": MIN_FREE_SPACE_AFTER_WRITE,
        "window_grace_seconds": WINDOW_GRACE_SECONDS,
        "notionals_usd": NOTIONALS_USD,
        "write_behavior": "CREATE_ONLY_CONTENT_ADDRESSED_RUN",
        "missed_window_policy": "RETAIN_EXPLICIT_GAP_NO_BACKFILL",
        "scheduler_or_background_process": False,
    }
    if not isinstance(runtime, dict) or runtime != expected_runtime:
        raise Task21FutureSentinelError("core_runtime_contract_drift")
    authority = config.get("authority", {})
    if (
        authority.get("class") != "LOCAL_WRITE_ONLY"
        or any(
            authority.get(key) != 0
            for key in (
                "network_calls",
                "provider_api_rpc_wss_calls",
                "drive_reads",
                "drive_writes",
                "raw_or_dataset_writes",
                "credentials",
                "cash_spend_usd_cents",
                "wallet_signer_transaction_actions",
                "dependency_changes",
            )
        )
        or authority.get("scheduler_or_background_process") is not False
        or authority.get("deployment") is not False
        or authority.get("destructive_actions") is not False
    ):
        raise Task21FutureSentinelError("core_authority_boundary_drift")
    return parsed


def _protected_path(
    config: Mapping[str, Any], repo_root: Path, role: str
) -> Path:
    protected = config.get("protected_inputs")
    if not isinstance(protected, list):
        raise Task21FutureSentinelError("protected_inputs_missing")
    matching = [item for item in protected if item.get("role") == role]
    if len(matching) != 1:
        raise Task21FutureSentinelError(f"protected_role_invalid:{role}")
    return _relative_path(repo_root, matching[0].get("path"))


def _h0_anchor(h0_acceptance: Mapping[str, Any]) -> datetime:
    windows = h0_acceptance.get("h0", {}).get("windows")
    if (
        h0_acceptance.get("task_id") != TASK_ID
        or h0_acceptance.get("status") != "PASS"
        or not isinstance(windows, list)
        or len(windows) != MEMBERS_EXACT
        or not all(isinstance(item, Mapping) for item in windows)
    ):
        raise Task21FutureSentinelError("h0_window_population_drift")
    return max(
        _utc("h0_triggered_at", item.get("triggered_at"))
        for item in windows
        if isinstance(item, Mapping)
    )


def _validate_profile(profile: SentinelProfile) -> None:
    expected = EXPECTED_PROFILES.get(profile.horizon_id)
    if expected is None or any(
        getattr(profile, key) != value for key, value in expected.items()
    ):
        raise Task21FutureSentinelError("future_sentinel_profile_drift")


def validate_runtime_config(
    config: Mapping[str, Any], repo_root: Path, profile: SentinelProfile
) -> None:
    _validate_profile(profile)
    if (
        config.get("schema") != "smial.task21_future_sentinel_runtime"
        or config.get("schema_version") != SCHEMA_VERSION
        or config.get("task_id") != TASK_ID
        or config.get("atom_id") != profile.runtime_atom_id
        or config.get("horizon_id") != profile.horizon_id
        or config.get("predecessor_horizon_id")
        != profile.predecessor_horizon_id
        or config.get("status") != "FROZEN_FORWARD_ONLY"
    ):
        raise Task21FutureSentinelError("runtime_config_identity_drift")
    protected = config.get("protected_inputs")
    if not isinstance(protected, list):
        raise Task21FutureSentinelError("protected_inputs_missing")
    expected_roles = {
        "H0_TRACKED_ACCEPTANCE",
        "H0_ADMISSION_EVENTS",
        "PREDECESSOR_TRACKED_ACCEPTANCE",
    }
    if {item.get("role") for item in protected} != expected_roles:
        raise Task21FutureSentinelError("protected_input_roles_drift")
    for item in protected:
        expected_hash = item.get("sha256")
        if not isinstance(expected_hash, str) or re.fullmatch(
            r"[0-9a-f]{64}", expected_hash
        ) is None:
            raise Task21FutureSentinelError("protected_input_hash_invalid")
        path = _relative_path(repo_root, item.get("path"))
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise Task21FutureSentinelError(
                f"protected_input_hash_drift:{item.get('role')}"
            )

    h0_acceptance = _load_json(
        _protected_path(config, repo_root, "H0_TRACKED_ACCEPTANCE")
    )
    predecessor = _load_json(
        _protected_path(config, repo_root, "PREDECESSOR_TRACKED_ACCEPTANCE")
    )
    if (
        predecessor.get("task_id") != TASK_ID
        or predecessor.get("status") != "PASS"
        or predecessor.get("atom_id") != profile.predecessor_runtime_atom_id
    ):
        raise Task21FutureSentinelError(
            "future_sentinel_predecessor_acceptance_drift"
        )
    anchor = _h0_anchor(h0_acceptance)
    expected_earliest = anchor + timedelta(
        seconds=profile.offset_seconds_from_latest_h0
    )
    expected_latest = expected_earliest + timedelta(
        seconds=WINDOW_GRACE_SECONDS
    )
    time_gate = config.get("time_gate", {})
    dynamic = config.get("dynamic_control", {})
    marker_path = _relative_path(repo_root, dynamic.get("path"))
    if (
        dynamic.get("role") != "ACTIVE_TIME_GATES"
        or not str(dynamic.get("gate_id", "")).startswith(
            profile.gate_id_prefix
        )
        or dynamic.get("allowed_statuses") != ["ACTIVE_WAITING"]
        or time_gate.get("gate_id") != dynamic.get("gate_id")
        or _utc("earliest_at", time_gate.get("earliest_at"))
        != expected_earliest
        or _utc("latest_at", time_gate.get("latest_at")) != expected_latest
        or time_gate.get("after_latest")
        != "WRITE_EXPLICIT_GAP_NO_PROVIDER_NO_BACKFILL"
    ):
        raise Task21FutureSentinelError("future_sentinel_time_gate_drift")
    marker = _load_json(marker_path)
    matching = [
        item
        for item in marker.get("gates", [])
        if item.get("gate_id") == dynamic.get("gate_id")
    ]
    if (
        len(matching) != 1
        or matching[0].get("task_id") != TASK_ID
        or matching[0].get("status") != "ACTIVE_WAITING"
        or matching[0].get("required_next_atom") != profile.runtime_atom_id
        or any(
            value != 0
            for value in matching[0].get(
                "authority_granted_by_marker", {}
            ).values()
        )
        or not {
            "local_writes",
            "provider_api_rpc_wss_calls",
            "drive_actions",
            "cash_spend_usd_cents",
            "wallet_signer_transaction_actions",
        }.issubset(
            matching[0].get("authority_granted_by_marker", {}).keys()
        )
    ):
        raise Task21FutureSentinelError("future_sentinel_active_gate_drift")

    population = config.get("population", {})
    member_ids = population.get("member_ids")
    if (
        not isinstance(member_ids, list)
        or len(member_ids) != MEMBERS_EXACT
        or len(set(member_ids)) != MEMBERS_EXACT
        or any(not isinstance(item, str) or not item for item in member_ids)
    ):
        raise Task21FutureSentinelError("future_sentinel_population_drift")
    sentinel = config.get("sentinel", {})
    expected_sentinel = {
        "panels_max": MEMBERS_EXACT,
        "provider_calls_per_panel_max": CALLS_PER_PANEL_MAX,
        "provider_calls_total_max": CALLS_TOTAL_MAX,
        "modeled_provider_credits_max": CALLS_TOTAL_MAX,
        "wall_seconds_max": WALL_SECONDS_MAX,
        "received_response_bytes_max": RECEIVED_BYTES_MAX,
        "durable_local_bytes_max": DURABLE_BYTES_MAX,
        "minimum_interval_seconds": MINIMUM_INTERVAL_SECONDS,
        "notionals_usd": NOTIONALS_USD,
        "local_output_root": profile.output_relative_root,
        "write_behavior": "CREATE_ONLY_CONTENT_ADDRESSED_RUN",
    }
    if not isinstance(sentinel, dict) or sentinel != expected_sentinel:
        raise Task21FutureSentinelError("future_sentinel_cap_drift")
    recovery = config.get("recovery", {})
    if (
        recovery.get("required_health") != "HEALTHY"
        or recovery.get("backup_age_hours_max_at_start") != 24
        or recovery.get("restore_age_hours_max_at_start") != 168
        or recovery.get("drive_actions") != 0
    ):
        raise Task21FutureSentinelError("future_sentinel_recovery_drift")
    authority = config.get("authority", {})
    if (
        authority.get("exact_phrase") != profile.runtime_atom_id
        or authority.get("provider_api_rpc_wss_calls_max")
        != CALLS_TOTAL_MAX
        or authority.get("drive_reads") != 0
        or authority.get("drive_writes") != 0
        or authority.get("credentials") != 0
        or authority.get("cash_spend_usd_cents") != 0
        or authority.get("wallet_signer_transaction_actions") != 0
        or authority.get("scheduler_or_background_process") is not False
        or authority.get("deployment") is not False
    ):
        raise Task21FutureSentinelError(
            "future_sentinel_authority_boundary_drift"
        )


def _load_members(
    config: Mapping[str, Any], repo_root: Path
) -> list[dict[str, Any]]:
    path = _protected_path(config, repo_root, "H0_ADMISSION_EVENTS")
    members: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Task21FutureSentinelError("h0_admission_event_invalid")
        members.append(value)
    expected = config["population"]["member_ids"]
    if [item.get("member_id") for item in members] != expected:
        raise Task21FutureSentinelError("future_sentinel_population_order_drift")
    if any(
        not isinstance(item.get("mint"), str)
        or not isinstance(item.get("mint_decimals"), int)
        or item.get("exited_at") is not None
        or not isinstance(item.get("hypothesis_version_id"), str)
        or not isinstance(item.get("nomination_event_id"), str)
        for item in members
    ):
        raise Task21FutureSentinelError("future_sentinel_member_contract_drift")
    return members


def _projection_envelope(
    projection: QuoteProjection,
    *,
    profile: SentinelProfile,
    member: Mapping[str, Any],
    window_id: str,
    ordinal: int,
) -> dict[str, Any]:
    quote = projection.quote_attempt
    raw = projection.raw_event
    return {
        "schema": "smial.task21.forward-quote-panel-raw",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": profile.runtime_atom_id,
        "horizon_id": profile.horizon_id,
        "hypothesis_version_id": member["hypothesis_version_id"],
        "member_id": member["member_id"],
        "nomination_event_id": member["nomination_event_id"],
        "window_id": window_id,
        "call_ordinal": ordinal,
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "request_hash": quote.request_hash,
        "idempotency_key": quote.idempotency_key,
        "raw_content_sha256": raw.content_sha256,
        "requested_at": _utc_text(quote.requested_at),
        "response_at": (
            None if quote.response_at is None else _utc_text(quote.response_at)
        ),
        "terminal_class": getattr(quote.status, "value", str(quote.status)),
        "stop_reason": projection.stop_reason,
        "raw_event": raw.model_dump(mode="json"),
        "quote_attempt": quote.model_dump(mode="json"),
    }


def _capture_member(
    *,
    profile: SentinelProfile,
    run_root: Path,
    config_hash: str,
    member: Mapping[str, Any],
    transport: Any,
    now: Callable[[], datetime],
    clock: Callable[[], float],
) -> dict[str, Any]:
    triggered_at = _utc_text(now())
    started = clock()
    projections: list[QuoteProjection] = []
    terminal_counts: Counter[str] = Counter()
    buy_attempts = 0
    sell_attempts = 0
    sell_not_attempted = 0
    stop_reason: str | None = None
    for index, buy_request in enumerate(
        build_buy_panel_requests(
            selected_output_mint=member["mint"],
            output_decimals=member["mint_decimals"],
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
        )
    ):
        if clock() - started >= WALL_SECONDS_MAX:
            stop_reason = "WALL_TIME_CAP_EXHAUSTED"
            break
        buy_capture: HttpCapture = transport.execute(buy_request)
        buy_attempts += 1
        buy_projection = project_quote_observation(
            buy_request, buy_capture.observation
        )
        projections.append(buy_projection)
        terminal = getattr(
            buy_projection.quote_attempt.status,
            "value",
            str(buy_projection.quote_attempt.status),
        )
        terminal_counts[terminal] += 1
        stop_reason = buy_capture.transport_stop_reason or buy_projection.stop_reason
        if stop_reason is not None:
            break
        sell = decide_dependent_sell(buy_projection, attempt_ordinal=5 + index)
        if sell.request is None:
            sell_not_attempted += 1
            continue
        sell_capture: HttpCapture = transport.execute(sell.request)
        sell_attempts += 1
        sell_projection = project_quote_observation(
            sell.request, sell_capture.observation
        )
        projections.append(sell_projection)
        terminal = getattr(
            sell_projection.quote_attempt.status,
            "value",
            str(sell_projection.quote_attempt.status),
        )
        terminal_counts[terminal] += 1
        stop_reason = sell_capture.transport_stop_reason or sell_projection.stop_reason
        if stop_reason is not None:
            break
    if transport.attempts > CALLS_PER_PANEL_MAX:
        raise Task21FutureSentinelError(
            "future_sentinel_panel_call_cap_exceeded"
        )
    if not projections:
        raise Task21FutureSentinelError("future_sentinel_panel_has_no_evidence")

    member_id = member["member_id"]
    window_id = f"{member_id}-{profile.horizon_id}"
    window_root = (
        run_root / f"member={member_id}" / f"horizon={profile.horizon_id}"
    )
    envelopes = [
        _projection_envelope(
            projection,
            profile=profile,
            member=member,
            window_id=window_id,
            ordinal=index,
        )
        for index, projection in enumerate(projections, start=1)
    ]
    raw_bytes = b"".join(
        canonical_json_bytes(item) + b"\n" for item in envelopes
    )
    raw_path = window_root / "raw_events.jsonl"
    _write_new(raw_path, raw_bytes)
    manifest = {
        "schema": "smial.task21.forward-quote-panel-manifest",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": profile.runtime_atom_id,
        "horizon_id": profile.horizon_id,
        "config_sha256": config_hash,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "triggered_at": triggered_at,
        "files": [
            {
                "logical_path": "raw_events.jsonl",
                "bytes": len(raw_bytes),
                "sha256": sha256_bytes(raw_bytes),
            }
        ],
    }
    manifest_bytes = canonical_json_bytes(manifest) + b"\n"
    manifest_path = window_root / "manifest.json"
    _write_new(manifest_path, manifest_bytes)
    receipt = {
        "schema": "smial.task21.forward-quote-panel-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": profile.runtime_atom_id,
        "horizon_id": profile.horizon_id,
        "window_id": window_id,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "status": "COMPLETE" if stop_reason is None else "STOPPED",
        "stop_reason": stop_reason,
        "triggered_at": triggered_at,
        "provider_calls": transport.attempts,
        "modeled_provider_credits": transport.attempts,
        "received_bytes": transport.received_bytes,
        "buy_attempts": buy_attempts,
        "sell_attempts": sell_attempts,
        "sell_not_attempted": sell_not_attempted,
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "raw_events_sha256": sha256_file(raw_path),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "cash_spend_usd_cents": 0,
        "credentials_used": 0,
        "wallet_signer_transaction_actions": 0,
    }
    receipt_path = window_root / "receipt.json"
    _write_new(receipt_path, canonical_json_bytes(receipt) + b"\n")
    return {
        **receipt,
        "stored_bytes": sum(
            path.stat().st_size
            for path in window_root.rglob("*")
            if path.is_file()
        ),
        "receipt_sha256": sha256_file(receipt_path),
    }


def _next_boundary(
    profile: SentinelProfile, h0_anchor: datetime
) -> dict[str, Any]:
    if profile.next_horizon_id is None:
        return {
            "status": "FOLLOWUP_SELECTION_REQUIRED_NOT_AUTHORIZED",
            "task21_acceptance_or_a7_eligible": False,
            "provider_api_rpc_wss_calls_authorized": False,
            "reason": "FINAL_SENTINEL_ALONE_DOES_NOT_COMPLETE_SUSTAINED_COLLECTION",
        }
    if (
        profile.next_runtime_atom_id is None
        or profile.next_offset_seconds_from_latest_h0 is None
    ):
        raise Task21FutureSentinelError("future_sentinel_next_boundary_drift")
    earliest = h0_anchor + timedelta(
        seconds=profile.next_offset_seconds_from_latest_h0
    )
    return {
        "atom_id": profile.next_runtime_atom_id,
        "horizon_id": profile.next_horizon_id,
        "status": "ACTIVE_WAITING_NOT_AUTHORIZED",
        "earliest_at": _utc_text(earliest),
        "latest_at": _utc_text(
            earliest + timedelta(seconds=WINDOW_GRACE_SECONDS)
        ),
        "provider_api_rpc_wss_calls_authorized": False,
        "missed_window_policy": "RETAIN_EXPLICIT_GAP_NO_BACKFILL",
    }


def _gap_receipt(
    *,
    profile: SentinelProfile,
    repo_root: Path,
    output_root: Path,
    output_override: bool,
    observed_at: datetime,
    earliest: datetime,
    latest: datetime,
    h0_anchor: datetime,
    recovery: Mapping[str, Any],
    provider_authority_present: bool,
) -> dict[str, Any]:
    claim = {
        "atom_id": profile.runtime_atom_id,
        "observed_at": _utc_text(observed_at),
    }
    run_id = (
        f"{profile.horizon_id.lower()}-gap-"
        + sha256_bytes(canonical_json_bytes(claim))[:16]
    )
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21FutureSentinelError(
            "future_sentinel_gap_output_already_exists"
        )
    backup_at = _utc(
        "last_successful_backup_at",
        recovery.get("health", {}).get("last_successful_backup_at"),
    )
    backup_age_at_earliest = (earliest - backup_at).total_seconds() / 3600
    receipt = {
        "schema": "smial.task21.future-sentinel-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": profile.runtime_atom_id,
        "horizon_id": profile.horizon_id,
        "run_id": run_id,
        "status": "GAP",
        "reason": f"{profile.horizon_id}_WINDOW_MISSED_NO_BACKFILL",
        "observed_blockers": {
            "recovery_backup_fresh_at_window_open": (
                backup_age_at_earliest <= 24
            ),
            "recovery_backup_age_hours_at_window_open": round(
                backup_age_at_earliest, 6
            ),
            "separate_provider_authority_present": provider_authority_present,
        },
        "observed_at": _utc_text(observed_at),
        "earliest_at": _utc_text(earliest),
        "latest_at": _utc_text(latest),
        "actual_actions": {
            "provider_api_rpc_wss_calls": 0,
            "modeled_provider_credits": 0,
            "local_live_windows": 0,
            "cash_spend_usd_cents": 0,
            "credentials_used": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "scheduler_or_background_process": False,
            "wallet_signer_transaction_actions": 0,
        },
        "backfill": False,
        "rescheduled": False,
        "next_boundary": _next_boundary(profile, h0_anchor),
    }
    path = run_root / "gap_receipt.json"
    _write_new(path, canonical_json_bytes(receipt) + b"\n")
    receipt["local_evidence"] = {
        "root": (
            f"TEST_OUTPUT_ROOT/run={run_id}"
            if output_override
            else run_root.relative_to(repo_root).as_posix()
        ),
        "files": _inventory(run_root),
        "tracked_in_git": False,
    }
    return receipt


def run_future_sentinel_capture(
    *,
    profile: SentinelProfile,
    gate: FutureSentinelExecutionGate | None,
    repo_root: Path,
    config_path: Path,
    recovery_receipt_path: Path,
    transport_factory: Callable[[Mapping[str, Any]], Any] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    available_disk_bytes: int | None = None,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root.resolve()
    if not config_path.resolve().is_relative_to(resolved_root):
        raise Task21FutureSentinelError("runtime_config_path_escape")
    if not recovery_receipt_path.resolve().is_relative_to(resolved_root):
        raise Task21FutureSentinelError("recovery_receipt_path_escape")
    config = _load_yaml(config_path)
    validate_runtime_config(config, repo_root, profile)
    observed_at = now()
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise Task21FutureSentinelError("runtime_now_must_be_timezone_aware")
    observed_at = observed_at.astimezone(UTC)
    earliest = _utc("earliest_at", config["time_gate"]["earliest_at"])
    latest = _utc("latest_at", config["time_gate"]["latest_at"])
    if observed_at < earliest:
        raise Task21FutureSentinelError("future_sentinel_window_not_open")
    output_root = (
        output_root_override.resolve()
        if output_root_override is not None
        else _relative_path(repo_root, profile.output_relative_root)
    )
    h0_acceptance = _load_json(
        _protected_path(config, repo_root, "H0_TRACKED_ACCEPTANCE")
    )
    anchor = _h0_anchor(h0_acceptance)
    recovery = _load_json(recovery_receipt_path)
    gate_valid = (
        isinstance(gate, FutureSentinelExecutionGate)
        and gate.horizon_id == profile.horizon_id
        and gate.authority_phrase == profile.runtime_atom_id
    )
    if observed_at > latest:
        return _gap_receipt(
            profile=profile,
            repo_root=repo_root,
            output_root=output_root,
            output_override=output_root_override is not None,
            observed_at=observed_at,
            earliest=earliest,
            latest=latest,
            h0_anchor=anchor,
            recovery=recovery,
            provider_authority_present=gate_valid,
        )
    if not gate_valid:
        raise Task21FutureSentinelAuthorityRequired(
            "future_sentinel_external_execution_gate_required"
        )
    if output_root_override is not None and transport_factory is None:
        raise Task21FutureSentinelError(
            "output_override_requires_injected_transport"
        )
    try:
        validate_recovery_freshness(recovery, now=observed_at)
    except Task21LiveShakedownError as exc:
        raise Task21FutureSentinelError(str(exc)) from exc
    free_bytes = (
        available_disk_bytes
        if available_disk_bytes is not None
        else shutil.disk_usage(repo_root).free
    )
    if free_bytes - DURABLE_BYTES_MAX < MIN_FREE_SPACE_AFTER_WRITE:
        raise Task21FutureSentinelError("future_sentinel_disk_pressure")
    members = _load_members(config, repo_root)
    config_hash = sha256_file(config_path)
    claim = {
        "atom_id": profile.runtime_atom_id,
        "config_sha256": config_hash,
        "started_at": _utc_text(observed_at),
    }
    run_id = (
        profile.horizon_id.lower()
        + "-"
        + observed_at.strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + sha256_bytes(canonical_json_bytes(claim))[:12]
    )
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21FutureSentinelError(
            "future_sentinel_run_output_already_exists"
        )

    summaries: list[dict[str, Any]] = []
    started = clock()
    for index, member in enumerate(members):
        if index:
            sleeper(MINIMUM_INTERVAL_SECONDS)
        if clock() - started >= WALL_SECONDS_MAX:
            break
        transport = (
            transport_factory(member)
            if transport_factory is not None
            else BoundedQuoteTransport(gate=TransportGate(TRANSPORT_AUTHORITY))
        )
        summary = _capture_member(
            profile=profile,
            run_root=run_root,
            config_hash=config_hash,
            member=member,
            transport=transport,
            now=now,
            clock=clock,
        )
        summaries.append(summary)
        if summary["status"] != "COMPLETE":
            break
    calls = sum(int(item["provider_calls"]) for item in summaries)
    received = sum(int(item["received_bytes"]) for item in summaries)
    if calls > CALLS_TOTAL_MAX:
        raise Task21FutureSentinelError(
            "future_sentinel_total_call_cap_exceeded"
        )
    if received > RECEIVED_BYTES_MAX:
        raise Task21FutureSentinelError(
            "future_sentinel_total_received_byte_cap_exceeded"
        )
    complete = len(summaries) == MEMBERS_EXACT and all(
        item["status"] == "COMPLETE" for item in summaries
    )
    receipt = {
        "schema": "smial.task21.future-sentinel-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": profile.runtime_atom_id,
        "horizon_id": profile.horizon_id,
        "run_id": run_id,
        "status": "PASS" if complete else "STOPPED",
        "started_at": _utc_text(observed_at),
        "population": {
            "member_ids": list(config["population"]["member_ids"]),
            "changed": False,
            "outcome_or_route_selection_used": False,
        },
        "sentinel": {
            "panels_complete": sum(
                item["status"] == "COMPLETE" for item in summaries
            ),
            "panels_stopped": sum(
                item["status"] != "COMPLETE" for item in summaries
            ),
            "windows": summaries,
        },
        "actual_actions": {
            "provider_api_rpc_wss_calls": calls,
            "modeled_provider_credits": calls,
            "received_bytes": received,
            "local_live_windows": len(summaries),
            "cash_spend_usd_cents": 0,
            "credentials_used": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "scheduler_or_background_process": False,
            "wallet_signer_transaction_actions": 0,
        },
        "next_boundary": _next_boundary(profile, anchor),
        "non_claims": [
            "NO_TRADE_OR_SWAP_EXECUTED",
            "NO_FILL_POSITION_PNL_OR_ALPHA_CLAIM",
            "NO_HYPOTHESIS_OUTCOME_UNSEALED",
            f"NO_DRIVE_ACTION_IN_{profile.horizon_id}",
            "NO_A7_CATALOG_TRANSACTION",
        ],
    }
    local_receipt_path = run_root / "runtime_receipt.json"
    _write_new(local_receipt_path, canonical_json_bytes(receipt) + b"\n")
    stored = sum(
        path.stat().st_size for path in run_root.rglob("*") if path.is_file()
    )
    if stored > DURABLE_BYTES_MAX:
        raise Task21FutureSentinelError(
            "future_sentinel_total_durable_byte_cap_exceeded"
        )
    receipt["local_evidence"] = {
        "root": (
            f"TEST_OUTPUT_ROOT/run={run_id}"
            if output_root_override is not None
            else run_root.relative_to(repo_root).as_posix()
        ),
        "stored_bytes": stored,
        "runtime_receipt_sha256": sha256_file(local_receipt_path),
        "files": _inventory(run_root),
        "tracked_in_git": False,
    }
    return receipt
