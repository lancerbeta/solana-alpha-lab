"""Fail-closed TASK-21 wrapper for one bounded live quote shakedown."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeAlias

import yaml

from solana_alpha_lab.jupiter_quote_transport import (
    EXTERNAL_AUTHORITY_PHRASE as TASK10_TRANSPORT_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate as Task10TransportGate,
)
from solana_alpha_lab.pilot_supervisor import SupervisorLimits
from solana_alpha_lab.task17a_execution_capacity_panel import run_window

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

TASK_ID = "TASK-21"
ATOM_ID = "T21-A5_BOUNDED_LIVE_SHAKEDOWN_V1"
EXTERNAL_AUTHORITY_PHRASE = ATOM_ID
WINDOW_ID = "T21-A5-WINDOW-01"
LOGICAL_ROOT = "task21_live_shakedown_v1"
OUTPUT_RELATIVE_ROOT = "local/task21_collector/live_shakedown"
PROVIDER_CALLS_MAX = 8
MODELED_CREDITS_MAX = 8
DURABLE_BYTES_MAX = 5_242_880
MIN_FREE_SPACE_AFTER_WRITE = 2_147_483_648
BACKUP_AGE_MAX = timedelta(hours=24)
RESTORE_AGE_MAX = timedelta(days=7)


class Task21LiveShakedownError(RuntimeError):
    """The live shakedown cannot proceed under the frozen boundary."""


class Task21ExternalAuthorityRequired(Task21LiveShakedownError):
    """The separate provider/live-write gate is absent or invalid."""


@dataclass(frozen=True, slots=True)
class Task21LiveExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise Task21ExternalAuthorityRequired(
                "task21_external_authority_phrase_mismatch"
            )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21LiveShakedownError("config_root_invalid")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21LiveShakedownError("receipt_root_invalid")
    return value


def _utc_datetime(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise Task21LiveShakedownError(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21LiveShakedownError(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Task21LiveShakedownError(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def validate_contract(config: Mapping[str, Any], repo_root: Path) -> None:
    if config.get("task_id") != TASK_ID or config.get("atom_id") != ATOM_ID:
        raise Task21LiveShakedownError("config_identity_drift")
    if config.get("status") != "FROZEN_AWAITING_EXACT_EXTERNAL_AUTHORITY":
        raise Task21LiveShakedownError("config_status_drift")
    frozen = config.get("frozen_inputs")
    if not isinstance(frozen, list) or not frozen:
        raise Task21LiveShakedownError("frozen_inputs_missing")
    for item in frozen:
        if not isinstance(item, Mapping):
            raise Task21LiveShakedownError("frozen_input_invalid")
        relative = item.get("path")
        expected = item.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(expected, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected) is None
        ):
            raise Task21LiveShakedownError("frozen_input_identity_invalid")
        actual = _sha256_file(repo_root / relative)
        if actual != expected:
            raise Task21LiveShakedownError(
                f"frozen_input_hash_drift:{relative}:{expected}:{actual}"
            )
    probe = config.get("technical_probe")
    if not isinstance(probe, Mapping):
        raise Task21LiveShakedownError("technical_probe_missing")
    if (
        probe.get("isolation") != "TECHNICAL_PROBE_NOT_WATCHLIST_ADMISSION"
        or probe.get("real_candidate_admissions") != 0
        or probe.get("task21_watchlist_members_created") != 0
        or probe.get("forward_dataset_rows") != 0
    ):
        raise Task21LiveShakedownError("technical_probe_isolation_drift")
    run = config.get("run")
    if not isinstance(run, Mapping):
        raise Task21LiveShakedownError("run_config_missing")
    expected_caps = {
        "provider_calls_max": PROVIDER_CALLS_MAX,
        "modeled_provider_credits_max": MODELED_CREDITS_MAX,
        "concurrency": 1,
        "retries": 0,
        "request_timeout_seconds": 20,
        "wall_seconds_max": 300,
        "minimum_interval_seconds": 2.2,
        "received_response_bytes_max": 1_048_576,
        "durable_bytes_max": DURABLE_BYTES_MAX,
        "api_keys": 0,
        "accounts": 0,
        "credentials": 0,
        "cash_spend_usd_cents": 0,
        "wallet_signer_transaction_actions": 0,
        "executions_max": 1,
    }
    if any(run.get(key) != value for key, value in expected_caps.items()):
        raise Task21LiveShakedownError("run_cap_drift")
    provider = config.get("official_provider_readback")
    if not isinstance(provider, Mapping):
        raise Task21LiveShakedownError("provider_readback_missing")
    if (
        provider.get("base_url") != "https://api.jup.ag"
        or provider.get("path") != "/swap/v1/quote"
        or provider.get("keyless_allowed") is not True
        or provider.get("keyless_rate_limit_rps") != 0.5
        or provider.get("current_status")
        != "AVAILABLE_SUPERSEDED_NOT_ACTIVELY_MAINTAINED"
    ):
        raise Task21LiveShakedownError("provider_surface_drift")


def validate_recovery_freshness(
    receipt: Mapping[str, Any],
    *,
    now: datetime,
) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise Task21LiveShakedownError("now_must_be_timezone_aware")
    now = now.astimezone(UTC)
    if (
        receipt.get("task_id") != TASK_ID
        or receipt.get("verdict") != "PASS"
        or receipt.get("provider_api_rpc_wss_calls") != 0
    ):
        raise Task21LiveShakedownError("recovery_gate_not_passed")
    health = receipt.get("health")
    if not isinstance(health, Mapping) or health.get("health_state") != "HEALTHY":
        raise Task21LiveShakedownError("recovery_gate_unhealthy")
    backup_at = _utc_datetime(
        "last_successful_backup_at",
        health.get("last_successful_backup_at"),
    )
    restore_at = _utc_datetime(
        "last_successful_restore_at",
        health.get("last_successful_restore_at"),
    )
    if backup_at > now or restore_at > now:
        raise Task21LiveShakedownError("recovery_evidence_from_future")
    if now - backup_at > BACKUP_AGE_MAX:
        raise Task21LiveShakedownError("recovery_backup_stale")
    if now - restore_at > RESTORE_AGE_MAX:
        raise Task21LiveShakedownError("recovery_restore_proof_stale")


def _available_disk_bytes(repo_root: Path) -> int:
    return shutil.disk_usage(repo_root).free


def _preflight_disk(available_disk_bytes: int) -> None:
    limits = SupervisorLimits(
        predicted_child_write_bytes_max=DURABLE_BYTES_MAX,
        start_reserve_fixed_bytes=536_870_912,
        runtime_reserve_fixed_bytes=268_435_456,
    )
    limits.validate()
    if (
        isinstance(available_disk_bytes, bool)
        or not isinstance(available_disk_bytes, int)
        or available_disk_bytes
        < MIN_FREE_SPACE_AFTER_WRITE + limits.start_required_bytes
    ):
        raise Task21LiveShakedownError("disk_pressure_blocks_live_shakedown")


def run_live_shakedown(
    *,
    gate: Task21LiveExecutionGate,
    repo_root: Path,
    config_path: Path,
    recovery_receipt_path: Path,
    transport_factory: Callable[[], Any] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    available_disk_bytes: int | None = None,
) -> dict[str, JsonValue]:
    """Run exactly one guarded foreground window after the explicit gate."""

    if not isinstance(gate, Task21LiveExecutionGate):
        raise Task21ExternalAuthorityRequired(
            "task21_external_execution_gate_required"
        )
    config = _load_yaml(config_path)
    validate_contract(config, repo_root)
    started_at = now()
    validate_recovery_freshness(
        _load_json(recovery_receipt_path),
        now=started_at,
    )
    _preflight_disk(
        _available_disk_bytes(repo_root)
        if available_disk_bytes is None
        else available_disk_bytes
    )
    raw_root = repo_root / OUTPUT_RELATIVE_ROOT
    window_root = raw_root / LOGICAL_ROOT / f"window={WINDOW_ID}"
    if window_root.exists():
        raise Task21LiveShakedownError("live_shakedown_output_already_exists")
    transport = (
        transport_factory()
        if transport_factory is not None
        else BoundedQuoteTransport(
            gate=Task10TransportGate(TASK10_TRANSPORT_AUTHORITY)
        )
    )
    summary = run_window(
        raw_root=raw_root,
        window_id=WINDOW_ID,
        transport=transport,
        logical_root=LOGICAL_ROOT,
    )
    if summary.provider_calls > PROVIDER_CALLS_MAX:
        raise Task21LiveShakedownError("provider_call_cap_exceeded")
    if summary.stored_bytes > DURABLE_BYTES_MAX:
        raise Task21LiveShakedownError("durable_byte_cap_exceeded")
    safe = summary.safe_receipt()
    return {
        "schema": "smial.task21.bounded-live-shakedown-runtime-receipt",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": safe["status"],
        "technical_probe_only": True,
        "task21_watchlist_members_created": 0,
        "real_candidate_admissions": 0,
        "forward_dataset_rows": 0,
        "provider_api_rpc_wss_calls": safe["provider_calls"],
        "modeled_provider_credits": safe["provider_calls"],
        "provider_billed_credit_claim": "NOT_AVAILABLE_KEYLESS_NO_ACCOUNT",
        "cash_spend_usd_cents": 0,
        "drive_reads": 0,
        "drive_writes": 0,
        "credentials_used": 0,
        "wallet_signer_transaction_actions": 0,
        "scheduler_or_background_process": False,
        "auto_escalated_to_atom6": False,
        "runtime": safe,
    }
