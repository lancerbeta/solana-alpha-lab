"""Stage-2 off-host durability: copy-only Google Drive mirror of local backups.

Never deletes remote objects. Never reads or stores OAuth tokens. Local
factory-remote-backup remains stage 1 and canonical first-stage durability.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from solana_alpha_lab.factory.remote_ops import (
    RemoteOpsError,
    _backup_newest,
    _sha256_file,
    backup_domain_for,
    backup_plane_lock,
    load_config_v1_1,
    logical_inventory_sha256,
    package_backup,
    package_delta_backup,
    prune_superseded_local_backups,
    read_backup_manifest,
    resolve_backup_sink,
    restore_incremental_chain_isolated,
    scan_backup_inventory,
)

RECEIPT_SCHEMA = "smial.factory-offhost-backup-receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
CHECKPOINT_SCHEMA = "smial.factory-offhost-recovery-checkpoint"
CHECKPOINT_SCHEMA_VERSION = "1.0"
DEFAULT_RCLONE_BIN = "/usr/bin/rclone"
OFFHOST_REMOTE = "GOOGLE_DRIVE"
SUCCESS_TERMINALS = frozenset(
    {
        "COPIED_VERIFIED",
        "ALREADY_PRESENT_VERIFIED",
        "DAILY_DELTA_VERIFIED",
        "NO_CHANGES_VERIFIED",
        "WEEKLY_FULL_VERIFIED",
        "FULL_COVERAGE_RECONFIRMED_NO_CHANGE",
    }
)
FAILURE_TERMINALS = frozenset({"COPY_FAILED", "REMOTE_IDENTITY_CONFLICT", "SOURCE_INTEGRITY_FAILED"})
CHECKPOINT_TERMINALS = frozenset(
    {
        "DAILY_DELTA_VERIFIED",
        "NO_CHANGES_VERIFIED",
        "WEEKLY_FULL_VERIFIED",
        "FULL_COVERAGE_RECONFIRMED_NO_CHANGE",
    }
)
OWNER_BACKUP_TRAFFIC_TARGET_30D = 300_000_000_000
INTERNAL_PAYLOAD_PLANNING_BUDGET_30D = 240_000_000_000
PLANNING_FIXTURE_PAYLOAD_30D = 202_000_000_000
GB = 1_000_000_000
ALLOWED_RCLONE_SUBCOMMANDS = frozenset({"copyto", "lsjson", "size"})
FORBIDDEN_RCLONE_SUBCOMMANDS = frozenset(
    {
        "sync",
        "delete",
        "purge",
        "move",
        "cleanup",
        "dedupe",
        "deletefile",
        "rmdirs",
        "mount",
    }
)

RcloneRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class OffhostBackupError(RemoteOpsError):
    """Typed off-host backup failure."""


@dataclass(frozen=True, slots=True)
class OffhostConfig:
    remote_name: str
    destination_root: str
    rclone_config_absolute: Path
    rclone_bin: Path
    receipt_relative: str
    freshness_current_max_seconds: int
    freshness_degraded_max_seconds: int
    chain_relative: str = "local/factory_v1/offhost_backup_chain.json"
    traffic_ledger_relative: str = "local/factory_v1/offhost_traffic_ledger.json"

    @property
    def remote_prefix(self) -> str:
        return f"{self.remote_name}:"

    def remote_object(self, filename: str) -> str:
        return f"{self.remote_prefix}{self.destination_root}/{filename}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_offhost_config(loaded: Mapping[str, Any]) -> OffhostConfig | None:
    offhost = loaded.get("backup", {}).get("offhost")
    if not isinstance(offhost, dict) or offhost.get("enabled") is not True:
        return None
    return OffhostConfig(
        remote_name=str(offhost["remote_name"]),
        destination_root=str(offhost["destination_root"]),
        rclone_config_absolute=Path(str(offhost["rclone_config_absolute"])),
        rclone_bin=Path(str(offhost.get("rclone_bin") or DEFAULT_RCLONE_BIN)),
        receipt_relative=str(offhost["receipt_relative"]),
        freshness_current_max_seconds=int(offhost["freshness_current_max_seconds"]),
        freshness_degraded_max_seconds=int(offhost["freshness_degraded_max_seconds"]),
    )


def load_offhost_config(root: Path) -> OffhostConfig | None:
    try:
        loaded = load_config_v1_1(root)
    except RemoteOpsError:
        return None
    return _parse_offhost_config(loaded)


def validate_rclone_argv(argv: Sequence[str]) -> None:
    if not argv:
        raise OffhostBackupError("RCLONE_INVOCATION_EMPTY")
    subcommand: str | None = None
    skip_next = False
    for token in argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if token == "--config":
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        subcommand = token
        break
    if subcommand is None:
        raise OffhostBackupError("RCLONE_SUBCOMMAND_MISSING")
    if subcommand in FORBIDDEN_RCLONE_SUBCOMMANDS:
        raise OffhostBackupError(f"RCLONE_SUBCOMMAND_FORBIDDEN:{subcommand}")
    if subcommand not in ALLOWED_RCLONE_SUBCOMMANDS:
        raise OffhostBackupError(f"RCLONE_SUBCOMMAND_NOT_ALLOWED:{subcommand}")


def build_rclone_argv(config: OffhostConfig, subcommand: str, *args: str) -> list[str]:
    if subcommand in FORBIDDEN_RCLONE_SUBCOMMANDS:
        raise OffhostBackupError(f"RCLONE_SUBCOMMAND_FORBIDDEN:{subcommand}")
    if subcommand not in ALLOWED_RCLONE_SUBCOMMANDS:
        raise OffhostBackupError(f"RCLONE_SUBCOMMAND_NOT_ALLOWED:{subcommand}")
    argv = [
        str(config.rclone_bin),
        "--config",
        str(config.rclone_config_absolute),
        subcommand,
        *args,
    ]
    validate_rclone_argv(argv)
    return argv


def default_rclone_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    validate_rclone_argv(argv)
    return subprocess.run(
        list(argv),
        check=False,
        capture_output=True,
        text=True,
    )


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_offhost_receipt(root: Path, config: OffhostConfig) -> dict[str, Any] | None:
    path = root / config.receipt_relative
    if path.is_file() is False:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _receipt_has_secrets(payload: Mapping[str, Any]) -> bool:
    dumped = json.dumps(payload)
    forbidden = (
        "access_token",
        "refresh_token",
        "client_secret",
        "service_account",
        "BEGIN PRIVATE",
    )
    return any(token in dumped for token in forbidden)


def write_offhost_receipt(root: Path, config: OffhostConfig, payload: Mapping[str, Any]) -> Path:
    body = {
        "schema": RECEIPT_SCHEMA,
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "offhost_remote": OFFHOST_REMOTE,
        **dict(payload),
    }
    if _receipt_has_secrets(body):
        raise OffhostBackupError("RECEIPT_SECRET_LEAK")
    path = root / config.receipt_relative
    _atomic_write_json(path, body)
    return path


def verify_backup_bundle(path: Path) -> dict[str, Any]:
    if path.is_file() is False:
        raise OffhostBackupError("BACKUP_BUNDLE_MISSING")
    if path.is_symlink():
        raise OffhostBackupError("BACKUP_BUNDLE_SYMLINK")
    if not path.name.startswith("BACKUP_") or path.suffix != ".zip":
        raise OffhostBackupError("BACKUP_BUNDLE_NAME_INVALID")
    declared = path.stem.removeprefix("BACKUP_")
    if len(declared) != 64:
        raise OffhostBackupError("BACKUP_BUNDLE_HASH_INVALID")
    recomputed = _sha256_file(path)
    if declared != recomputed:
        raise OffhostBackupError("BACKUP_BUNDLE_HASH_MISMATCH")
    size = path.stat().st_size
    return {
        "filename": path.name,
        "path": path,
        "sha256": recomputed,
        "bytes": size,
    }


def _remote_metadata(
    config: OffhostConfig,
    remote_object: str,
    runner: RcloneRunner,
) -> dict[str, Any] | None:
    argv = build_rclone_argv(config, "lsjson", remote_object)
    completed = runner(argv)
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        if "directory not found" in stderr.lower() or "object not found" in stderr.lower():
            return None
        if not (completed.stdout or "").strip():
            return None
        raise OffhostBackupError("OFFHOST_REMOTE_METADATA_FAILED")
    try:
        rows = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise OffhostBackupError("OFFHOST_REMOTE_METADATA_INVALID") from exc
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        raise OffhostBackupError("OFFHOST_REMOTE_METADATA_INVALID")
    return {"bytes": int(row.get("Size") or 0), "path": str(row.get("Path") or "")}


def _remote_size(
    config: OffhostConfig,
    remote_object: str,
    runner: RcloneRunner,
) -> int | None:
    meta = _remote_metadata(config, remote_object, runner)
    if meta is None:
        return None
    return int(meta["bytes"])


def _rclone_version(config: OffhostConfig, runner: RcloneRunner) -> str | None:
    try:
        completed = subprocess.run(
            [str(config.rclone_bin), "version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    first = (completed.stdout or "").splitlines()[:1]
    return first[0].strip() if first else None


def rclone_config_metadata(config: OffhostConfig) -> dict[str, Any]:
    path = config.rclone_config_absolute
    if path.is_file() is False:
        return {"present": False}
    try:
        st = path.stat()
    except OSError:
        return {"present": False}
    mode = stat.S_IMODE(st.st_mode)
    mode_ok = mode == 0o600
    if os.name != "posix":
        # Production policy is enforced on the Linux VPS; git-side tests stay portable.
        mode_ok = True
    return {
        "present": True,
        "mode_octal": oct(mode),
        "mode_ok": mode_ok,
        "size_bytes": st.st_size,
        "non_empty": st.st_size > 0,
    }


def _age_seconds(iso_ts: str | None, clock: datetime) -> int | None:
    if not iso_ts:
        return None
    try:
        parsed = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max(0, int((clock.astimezone(UTC) - parsed.astimezone(UTC)).total_seconds()))


def classify_offhost_state(
    *,
    receipt: Mapping[str, Any] | None,
    age_seconds: int | None,
    configured: bool,
    rclone_ready: bool,
    current_max: int,
    degraded_max: int,
) -> str:
    if configured is False:
        return "UNCONFIGURED"
    if rclone_ready is False:
        # Git has offhost.enabled; missing/unready rclone must not look like
        # "optional not configured" and silently skip campaign attention.
        return "FAILED"
    if receipt is None:
        return "MISSING"
    terminal = str(receipt.get("terminal") or "")
    if terminal in FAILURE_TERMINALS:
        return "FAILED"
    if terminal not in SUCCESS_TERMINALS:
        return "MISSING"
    if age_seconds is None:
        return "DEGRADED"
    if age_seconds <= current_max:
        return "CURRENT"
    if age_seconds <= degraded_max:
        return "DEGRADED"
    return "HARD_ATTENTION"


def offhost_health_snapshot(
    root: Path,
    *,
    now: datetime | None = None,
    config: OffhostConfig | None = None,
) -> dict[str, Any]:
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    offhost = config if config is not None else load_offhost_config(root)
    if offhost is None:
        return {
            "configured": False,
            "offhost_remote": OFFHOST_REMOTE,
            "offhost_backup_state": "UNCONFIGURED",
            "durability_domain": "LOCAL_ONLY",
            "rclone_config": {"present": False},
        }
    meta = rclone_config_metadata(offhost)
    rclone_ready = bool(meta.get("present") and meta.get("mode_ok") and meta.get("non_empty"))
    receipt = read_offhost_receipt(root, offhost)
    verified_at = str(receipt.get("verified_at") or receipt.get("uploaded_at") or "") if receipt else ""
    age = _age_seconds(verified_at, clock)
    state = classify_offhost_state(
        receipt=receipt,
        age_seconds=age,
        configured=True,
        rclone_ready=rclone_ready,
        current_max=offhost.freshness_current_max_seconds,
        degraded_max=offhost.freshness_degraded_max_seconds,
    )
    durability = "OFF_HOST_INDEPENDENT" if state == "CURRENT" else "LOCAL_ONLY"
    traffic = payload_bytes_snapshot(root, offhost)
    return {
        "configured": True,
        "offhost_remote": OFFHOST_REMOTE,
        "offhost_backup_state": state,
        "offhost_last_verified_at": verified_at or None,
        "offhost_backup_age_seconds": age,
        "offhost_last_filename": receipt.get("source_backup_filename") if receipt else None,
        "offhost_last_sha256": receipt.get("source_sha256") if receipt else None,
        "offhost_last_terminal": receipt.get("terminal") if receipt else None,
        "durability_domain": durability,
        "rclone_config": meta,
        "freshness_policy": {
            "current_max_seconds": offhost.freshness_current_max_seconds,
            "degraded_max_seconds": offhost.freshness_degraded_max_seconds,
        },
        **traffic,
    }


def agent_durability_classification(
    *,
    local_backup_state: str,
    offhost_backup_state: str,
) -> dict[str, bool]:
    """Fresh-agent labels for Git + machine readback only (no chat history)."""

    offhost_state = str(offhost_backup_state or "UNCONFIGURED")
    local_state = str(local_backup_state or "UNKNOWN")
    return {
        "LOCAL_BACKUP_OK": local_state == "OK",
        "OFFHOST_BACKUP_OK": offhost_state == "CURRENT",
        "OFFHOST_BACKUP_STALE": offhost_state
        in {"DEGRADED", "HARD_ATTENTION", "MISSING", "FAILED"},
        "OFFHOST_NOT_CONFIGURED": offhost_state == "UNCONFIGURED",
    }


def offhost_recovery_readout(
    root: Path,
    *,
    deploy_git_sha: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read-only recovery packet for agents with zero conversation history."""

    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    offhost_cfg = load_offhost_config(root)
    offhost = offhost_health_snapshot(root, now=clock, config=offhost_cfg)
    receipt = (
        read_offhost_receipt(root, offhost_cfg)
        if offhost_cfg is not None
        else None
    )
    local_backup_state = "UNKNOWN"
    local_backup: dict[str, Any] | None = None
    backup_domain: str | None = None
    sink_relative = "local/factory_v1_backup_sink"
    try:
        loaded = load_config_v1_1(root)
        backup_block = loaded.get("backup") or {}
        sink_relative = str(backup_block.get("independent_sink_relative") or sink_relative)
        sink = resolve_backup_sink(root, loaded, os.environ)
        newest = _backup_newest(sink)
        backup_domain = backup_domain_for(root, loaded, sink, os.environ)
        if newest is None:
            local_backup_state = "MISSING"
        else:
            age = _age_seconds(str(newest.get("mtime")), clock)
            local_backup = dict(newest)
            local_backup_state = (
                "OK" if age is not None and age <= 24 * 3600 else "STALE"
            )
    except RemoteOpsError:
        local_backup_state = "UNKNOWN"

    architecture = {
        "stage_1_local": {
            "mechanism": "factory_remote_doctor.py --backup",
            "timer": "factory-remote-backup.timer",
            "service": "factory-remote-backup.service",
            "sink_relative": sink_relative,
            "sink_env": "FACTORY_BACKUP_SINK",
            "is_scientific_truth": False,
            "is_factory_backup_sink": False,
        },
        "stage_2_offhost": {
            "mechanism": "scripts/factory_offhost_backup_copy.py",
            "trigger": "factory-remote-backup-gdrive.timer weekly full + factory-remote-backup-gdrive-delta.timer daily checkpoint",
            "service": "factory-remote-backup-gdrive.service",
            "rclone_bin": str(offhost_cfg.rclone_bin) if offhost_cfg else "/usr/bin/rclone",
            "rclone_config_absolute": (
                str(offhost_cfg.rclone_config_absolute)
                if offhost_cfg
                else "/etc/solana-alpha-lab/rclone.conf"
            ),
            "remote_name": offhost_cfg.remote_name if offhost_cfg else "factory-gdrive",
            "destination_root": (
                offhost_cfg.destination_root if offhost_cfg else "solana-alpha-lab/factory-backups"
            ),
            "copy_semantics": "COPYTO_ONLY",
            "delete_remote": False,
            "sync_delete": False,
            "discovery": "RECOVERY_CHECKPOINT_FILENAME_TIMESTAMP_THEN_CONTENT_HASH",
            "is_scientific_truth": False,
            "is_factory_backup_sink": False,
            "google_drive_role": "PROVEN_OFFHOST_DURABILITY",
            "google_drive_role_prior": "OPTIONAL_COLD_COPY_NOT_DOD",
            "unproven_follow_up": "LIVE_FACTORY_INCREMENTAL_RESTORE_COMMISSIONING",
        },
    }
    if offhost_cfg is not None:
        architecture["stage_2_offhost"]["receipt_relative"] = offhost_cfg.receipt_relative

    classification = agent_durability_classification(
        local_backup_state=local_backup_state,
        offhost_backup_state=str(offhost.get("offhost_backup_state") or "UNCONFIGURED"),
    )
    return {
        "schema": "smial.factory-offhost-recovery-readout",
        "schema_version": "1.0",
        "observed_at": clock.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "deploy_git_sha": deploy_git_sha,
        "agent_classification": classification,
        "local_backup_state": local_backup_state,
        "local_backup": local_backup,
        "backup_domain": backup_domain,
        "offhost": offhost,
        "last_verified_offhost_receipt": receipt,
        "architecture": architecture,
        "isolated_restore": {
            "module": "solana_alpha_lab.factory.offhost_backup.restore_from_recovery_checkpoint",
            "discovery": "RECOVERY_CHECKPOINT_FILENAME_TIMESTAMP_THEN_CONTENT_HASH",
            "requires_isolated_dest_root": True,
            "never_replaces_live_sqlite_or_rdp": True,
            "note": "Newest valid RECOVERY_CHECKPOINT_<UTC>_<sha256>.json by filename timestamp, validate content hash, then restore referenced full/deltas into isolated dest. Never Drive listing order or object mtime. Never restore into live factory_v1 stores.",
        },
        "required_acceptance_terminal": "FACTORY_DAILY_DELTA_WEEKLY_FULL_OFFHOST_BACKUP_PASS",
    }


def copy_offhost_backup(
    root: Path,
    *,
    deploy_git_sha: str | None = None,
    config: OffhostConfig | None = None,
    environ: Mapping[str, str] | None = None,
    runner: RcloneRunner | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    offhost = config if config is not None else load_offhost_config(root)
    if offhost is None:
        raise OffhostBackupError("OFFHOST_NOT_CONFIGURED")
    meta = rclone_config_metadata(offhost)
    if not (meta.get("present") and meta.get("mode_ok") and meta.get("non_empty")):
        raise OffhostBackupError("RCLONE_CONFIG_NOT_READY")
    env = environ if environ is not None else os.environ
    loaded = load_config_v1_1(root)
    sink = resolve_backup_sink(root, loaded, env)
    newest = _backup_newest(sink)
    if newest is None:
        raise OffhostBackupError("LOCAL_BACKUP_MISSING")
    bundle_path = sink / str(newest["path"])
    try:
        bundle = verify_backup_bundle(bundle_path)
    except OffhostBackupError as exc:
        write_offhost_receipt(
            root,
            offhost,
            {
                "uploaded_at": _now(),
                "verified_at": _now(),
                "source_backup_filename": bundle_path.name,
                "source_sha256": None,
                "source_bytes": None,
                "remote_logical_path": offhost.remote_object(bundle_path.name),
                "remote_bytes": None,
                "terminal": "SOURCE_INTEGRITY_FAILED",
                "error": str(exc),
                "deploy_git_sha": deploy_git_sha,
            },
        )
        raise
    remote_object = offhost.remote_object(bundle["filename"])
    invoke = runner if runner is not None else default_rclone_runner
    existing = _remote_metadata(offhost, remote_object, invoke)
    timestamp = clock.isoformat(timespec="seconds").replace("+00:00", "Z")
    if existing is not None:
        remote_bytes = int(existing["bytes"])
        if remote_bytes != bundle["bytes"]:
            write_offhost_receipt(
                root,
                offhost,
                {
                    "uploaded_at": timestamp,
                    "verified_at": timestamp,
                    "source_backup_filename": bundle["filename"],
                    "source_sha256": bundle["sha256"],
                    "source_bytes": bundle["bytes"],
                    "remote_logical_path": remote_object,
                    "remote_bytes": remote_bytes,
                    "terminal": "REMOTE_IDENTITY_CONFLICT",
                    "deploy_git_sha": deploy_git_sha,
                },
            )
            raise OffhostBackupError("OFFHOST_REMOTE_IDENTITY_CONFLICT")
        receipt = {
            "uploaded_at": timestamp,
            "verified_at": timestamp,
            "source_backup_filename": bundle["filename"],
            "source_sha256": bundle["sha256"],
            "source_bytes": bundle["bytes"],
            "remote_logical_path": remote_object,
            "remote_bytes": remote_bytes,
            "terminal": "ALREADY_PRESENT_VERIFIED",
            "rclone_version": _rclone_version(offhost, invoke),
            "deploy_git_sha": deploy_git_sha,
        }
        write_offhost_receipt(root, offhost, receipt)
        return receipt
    argv = build_rclone_argv(
        offhost,
        "copyto",
        str(bundle["path"]),
        remote_object,
    )
    completed = invoke(argv)
    if completed.returncode != 0:
        write_offhost_receipt(
            root,
            offhost,
            {
                "uploaded_at": timestamp,
                "verified_at": timestamp,
                "source_backup_filename": bundle["filename"],
                "source_sha256": bundle["sha256"],
                "source_bytes": bundle["bytes"],
                "remote_logical_path": remote_object,
                "remote_bytes": None,
                "terminal": "COPY_FAILED",
                "deploy_git_sha": deploy_git_sha,
            },
        )
        raise OffhostBackupError("OFFHOST_COPY_FAILED")
    remote_bytes = _remote_size(offhost, remote_object, invoke)
    if remote_bytes != bundle["bytes"]:
        write_offhost_receipt(
            root,
            offhost,
            {
                "uploaded_at": timestamp,
                "verified_at": timestamp,
                "source_backup_filename": bundle["filename"],
                "source_sha256": bundle["sha256"],
                "source_bytes": bundle["bytes"],
                "remote_logical_path": remote_object,
                "remote_bytes": remote_bytes,
                "terminal": "COPY_FAILED",
                "deploy_git_sha": deploy_git_sha,
            },
        )
        raise OffhostBackupError("OFFHOST_COPY_SIZE_MISMATCH")
    receipt = {
        "uploaded_at": timestamp,
        "verified_at": timestamp,
        "source_backup_filename": bundle["filename"],
        "source_sha256": bundle["sha256"],
        "source_bytes": bundle["bytes"],
        "remote_logical_path": remote_object,
        "remote_bytes": remote_bytes,
        "terminal": "COPIED_VERIFIED",
        "rclone_version": _rclone_version(offhost, invoke),
        "deploy_git_sha": deploy_git_sha,
    }
    write_offhost_receipt(root, offhost, receipt)
    return receipt


def planning_fixture_payload_30d() -> int:
    weekly = (2 + 16 + 30 + 44 + 58) * GB
    daily = 26 * 2 * GB
    return weekly + daily


def classify_payload_budget(payload_bytes_30d: int) -> str:
    if payload_bytes_30d < 200 * GB:
        return "NORMAL"
    if payload_bytes_30d <= INTERNAL_PAYLOAD_PLANNING_BUDGET_30D:
        return "PRESSURE"
    return "OWNER_ATTENTION"


def conservative_full_pressure_bytes(
    *,
    current_full_payload_size: int,
    projected_non_full_delta_payload: int,
) -> int:
    return (5 * int(current_full_payload_size)) + int(projected_non_full_delta_payload)


def _chain_path(root: Path, config: OffhostConfig) -> Path:
    return root / config.chain_relative


def _traffic_path(root: Path, config: OffhostConfig) -> Path:
    return root / config.traffic_ledger_relative


def read_chain_state(root: Path, config: OffhostConfig) -> dict[str, Any]:
    path = _chain_path(root, config)
    if path.is_file() is False:
        return {"base_full": None, "ordered_deltas": [], "last_weekly_date": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"base_full": None, "ordered_deltas": [], "last_weekly_date": None}
    return payload if isinstance(payload, dict) else {"base_full": None, "ordered_deltas": []}


def write_chain_state(root: Path, config: OffhostConfig, payload: Mapping[str, Any]) -> None:
    _atomic_write_json(_chain_path(root, config), payload)


def _utc_compact(clock: datetime) -> str:
    return clock.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _record_traffic(
    root: Path,
    config: OffhostConfig,
    *,
    clock: datetime,
    attempted_payload_bytes: int,
    verified_payload_bytes: int,
    already_present_payload_bytes: int = 0,
    terminal: str,
) -> None:
    path = _traffic_path(root, config)
    ledger: dict[str, Any]
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            ledger = loaded if isinstance(loaded, dict) else {"events": []}
        except (OSError, json.JSONDecodeError):
            ledger = {"events": []}
    else:
        ledger = {"events": []}
    events = list(ledger.get("events") or [])
    events.append(
        {
            "at": clock.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "attempted_payload_bytes": int(attempted_payload_bytes),
            "verified_payload_bytes": int(verified_payload_bytes),
            "already_present_payload_bytes": 0 if already_present_payload_bytes else 0,
            "terminal": terminal,
        }
    )
    cutoff = clock.astimezone(UTC).timestamp() - 30 * 24 * 3600
    kept = []
    for event in events:
        try:
            stamp = datetime.fromisoformat(str(event.get("at") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if stamp.timestamp() >= cutoff:
            kept.append(event)
    attempted = sum(int(event.get("attempted_payload_bytes") or 0) for event in kept)
    verified = sum(int(event.get("verified_payload_bytes") or 0) for event in kept)
    body = {
        "schema": "smial.factory-offhost-traffic-ledger",
        "schema_version": "1.0",
        "events": kept,
        "offhost_backup_payload_bytes_30d": attempted,
        "verified_payload_bytes_30d": verified,
        "projected_offhost_backup_payload_bytes_30d": planning_fixture_payload_30d(),
        "budget_class": classify_payload_budget(attempted),
        "application_payload_is_billing_truth": False,
    }
    _atomic_write_json(path, body)


def payload_bytes_snapshot(root: Path, config: OffhostConfig) -> dict[str, Any]:
    path = _traffic_path(root, config)
    unknown = {
        "offhost_backup_payload_bytes_30d": None,
        "projected_offhost_backup_payload_bytes_30d": planning_fixture_payload_30d(),
        "budget_class": "UNKNOWN",
        "application_payload_is_billing_truth": False,
        "offhost_backup_payload_measured": False,
    }
    if path.is_file() is False:
        return dict(unknown)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(unknown)
    if not isinstance(payload, dict) or "offhost_backup_payload_bytes_30d" not in payload:
        return dict(unknown)
    try:
        measured = int(payload["offhost_backup_payload_bytes_30d"])
    except (TypeError, ValueError):
        return dict(unknown)
    current_full = 0
    try:
        loaded = load_config_v1_1(root)
        newest = _backup_newest(resolve_backup_sink(root, loaded, os.environ))
        if newest is not None:
            current_full = int(newest.get("bytes") or 0)
    except RemoteOpsError:
        current_full = 0
    pressure = conservative_full_pressure_bytes(
        current_full_payload_size=current_full,
        projected_non_full_delta_payload=52 * GB,
    )
    return {
        "offhost_backup_payload_bytes_30d": measured,
        "projected_offhost_backup_payload_bytes_30d": int(
            payload.get("projected_offhost_backup_payload_bytes_30d")
            or planning_fixture_payload_30d()
        ),
        "budget_class": classify_payload_budget(measured),
        "application_payload_is_billing_truth": False,
        "offhost_backup_payload_measured": True,
        "conservative_full_pressure_bytes": pressure,
        "offhost_egress_policy_pressure": pressure > INTERNAL_PAYLOAD_PLANNING_BUDGET_30D,
    }


def copy_local_object(
    *,
    local_path: Path,
    remote_object: str,
    config: OffhostConfig,
    runner: RcloneRunner,
    clock: datetime,
) -> dict[str, Any]:
    size = local_path.stat().st_size
    existing = _remote_metadata(config, remote_object, runner)
    if existing is not None:
        remote_bytes = int(existing["bytes"])
        if remote_bytes != size:
            raise OffhostBackupError("OFFHOST_REMOTE_IDENTITY_CONFLICT")
        return {
            "terminal": "ALREADY_PRESENT_VERIFIED",
            "attempted_payload_bytes": 0,
            "verified_payload_bytes": 0,
            "already_present_payload_bytes": 0,
            "remote_bytes": remote_bytes,
        }
    argv = build_rclone_argv(config, "copyto", str(local_path), remote_object)
    completed = runner(argv)
    if completed.returncode != 0:
        return {
            "terminal": "COPY_FAILED",
            "attempted_payload_bytes": size,
            "verified_payload_bytes": 0,
            "already_present_payload_bytes": 0,
            "remote_bytes": None,
        }
    remote_bytes = _remote_size(config, remote_object, runner)
    if remote_bytes != size:
        return {
            "terminal": "COPY_FAILED",
            "attempted_payload_bytes": size,
            "verified_payload_bytes": 0,
            "already_present_payload_bytes": 0,
            "remote_bytes": remote_bytes,
        }
    return {
        "terminal": "COPIED_VERIFIED",
        "attempted_payload_bytes": size,
        "verified_payload_bytes": size,
        "already_present_payload_bytes": 0,
        "remote_bytes": remote_bytes,
    }


def _checkpoint_canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(payload), indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _reuse_or_package_full(
    *,
    root: Path,
    loaded: Mapping[str, Any],
    env: Mapping[str, str],
    sink: Path,
    current_inventory: str,
    current_entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    newest = _backup_newest(sink)
    if newest is not None:
        path = sink / str(newest["path"])
        if path.is_file():
            manifest = read_backup_manifest(path)
            if str(manifest.get("inventory_sha256")) == current_inventory:
                return {
                    "bundle": newest["path"],
                    "sha256": newest["sha256"],
                    "bytes": newest["bytes"],
                    "entries": list(current_entries),
                    "inventory_sha256": current_inventory,
                    "reused": True,
                }
    packed = package_backup(
        root,
        config=loaded,
        environ=env,
        acquire_lock=False,
        prune_superseded=False,
    )
    packed["reused"] = False
    return packed


def publish_recovery_checkpoint(
    *,
    root: Path,
    config: OffhostConfig,
    runner: RcloneRunner,
    clock: datetime,
    checkpoint: Mapping[str, Any],
    sink: Path,
) -> dict[str, Any]:
    body = {
        "schema": CHECKPOINT_SCHEMA,
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        **dict(checkpoint),
        "created_at": clock.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    encoded = _checkpoint_canonical(body)
    digest = hashlib.sha256(encoded).hexdigest()
    filename = f"RECOVERY_CHECKPOINT_{_utc_compact(clock)}_{digest}.json"
    local = sink / filename
    local.write_bytes(encoded)
    remote = config.remote_object(filename)
    copied = copy_local_object(
        local_path=local,
        remote_object=remote,
        config=config,
        runner=runner,
        clock=clock,
    )
    if copied["terminal"] == "COPY_FAILED":
        raise OffhostBackupError("CHECKPOINT_COPY_FAILED")
    if _sha256_file(local) != digest:
        raise OffhostBackupError("CHECKPOINT_HASH_MISMATCH")
    return {
        "filename": filename,
        "sha256": digest,
        "local_path": local,
        "remote_logical_path": remote,
        "copy": copied,
        "payload": body,
    }


def validate_recovery_checkpoint(path: Path) -> dict[str, Any]:
    if path.is_file() is False:
        raise OffhostBackupError("CHECKPOINT_MISSING")
    name = path.name
    if not name.startswith("RECOVERY_CHECKPOINT_") or not name.endswith(".json"):
        raise OffhostBackupError("CHECKPOINT_NAME_INVALID")
    stem = name.removeprefix("RECOVERY_CHECKPOINT_").removesuffix(".json")
    if "_" not in stem:
        raise OffhostBackupError("CHECKPOINT_NAME_INVALID")
    _stamp, declared = stem.rsplit("_", 1)
    if len(declared) != 64:
        raise OffhostBackupError("CHECKPOINT_HASH_INVALID")
    recomputed = _sha256_file(path)
    if declared != recomputed:
        raise OffhostBackupError("CHECKPOINT_HASH_MISMATCH")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OffhostBackupError("CHECKPOINT_INVALID") from exc
    if not isinstance(payload, dict) or payload.get("schema") != CHECKPOINT_SCHEMA:
        raise OffhostBackupError("CHECKPOINT_INVALID")
    return payload


def newest_checkpoint_filename(names: Sequence[str]) -> str | None:
    matched: list[tuple[str, str]] = []
    for name in names:
        if not name.startswith("RECOVERY_CHECKPOINT_") or not name.endswith(".json"):
            continue
        stem = name.removeprefix("RECOVERY_CHECKPOINT_").removesuffix(".json")
        if "_" not in stem:
            continue
        stamp, digest = stem.rsplit("_", 1)
        if len(digest) != 64:
            continue
        matched.append((stamp, name))
    if not matched:
        return None
    matched.sort()
    return matched[-1][1]


def restore_from_recovery_checkpoint(
    *,
    checkpoint_path: Path,
    objects_dir: Path,
    dest_root: Path,
) -> dict[str, Any]:
    payload = validate_recovery_checkpoint(checkpoint_path)
    base_name = str((payload.get("base_full") or {}).get("filename") or "")
    if not base_name:
        raise OffhostBackupError("CHECKPOINT_BASE_MISSING")
    full_bundle = objects_dir / base_name
    deltas = [
        objects_dir / str(item["filename"])
        for item in (payload.get("ordered_deltas") or [])
        if isinstance(item, dict) and item.get("filename")
    ]
    restored = restore_incremental_chain_isolated(
        full_bundle=full_bundle,
        deltas=deltas,
        dest_root=dest_root,
        expected_inventory_sha256=str(payload.get("result_inventory_sha256") or "") or None,
    )
    restored["checkpoint_filename"] = checkpoint_path.name
    restored["discovery"] = "RECOVERY_CHECKPOINT_FILENAME_TIMESTAMP_THEN_CONTENT_HASH"
    return restored


def _accounted_copy(
    *,
    root: Path,
    config: OffhostConfig,
    runner: RcloneRunner,
    clock: datetime,
    local_path: Path,
    remote_object: str,
) -> dict[str, Any]:
    copied = copy_local_object(
        local_path=local_path,
        remote_object=remote_object,
        config=config,
        runner=runner,
        clock=clock,
    )
    _record_traffic(
        root,
        config,
        clock=clock,
        attempted_payload_bytes=int(copied["attempted_payload_bytes"]),
        verified_payload_bytes=int(copied["verified_payload_bytes"]),
        already_present_payload_bytes=0,
        terminal=str(copied["terminal"]),
    )
    return copied


def run_offhost_checkpoint(
    root: Path,
    *,
    mode: str,
    deploy_git_sha: str | None = None,
    config: OffhostConfig | None = None,
    environ: Mapping[str, str] | None = None,
    runner: RcloneRunner | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if mode not in {"daily", "weekly"}:
        raise OffhostBackupError("CHECKPOINT_MODE_INVALID")
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    offhost = config if config is not None else load_offhost_config(root)
    if offhost is None:
        raise OffhostBackupError("OFFHOST_NOT_CONFIGURED")
    meta = rclone_config_metadata(offhost)
    if not (meta.get("present") and meta.get("mode_ok") and meta.get("non_empty")):
        raise OffhostBackupError("RCLONE_CONFIG_NOT_READY")
    invoke = runner if runner is not None else default_rclone_runner
    env = environ if environ is not None else os.environ
    loaded = load_config_v1_1(root)
    sink = resolve_backup_sink(root, loaded, env)
    with backup_plane_lock(root):
        scanned = scan_backup_inventory(root, config=loaded)
        current_entries = list(scanned["entries"])
        current_inventory = str(scanned["inventory_sha256"])
        chain = read_chain_state(root, offhost)
        weekly_due = mode == "weekly" or (
            mode == "daily"
            and clock.weekday() == 6
            and str(chain.get("last_weekly_date") or "") != clock.date().isoformat()
        )
        base = chain.get("base_full") if isinstance(chain.get("base_full"), dict) else None
        ordered = list(chain.get("ordered_deltas") or [])
        checkpoint_terminal = "NO_CHANGES_VERIFIED"
        weekly_full_state = "OK"
        packed: dict[str, Any] | None = None
        source_full: dict[str, Any] | None = None

        def ensure_full() -> dict[str, Any]:
            nonlocal packed
            if packed is None:
                packed = _reuse_or_package_full(
                    root=root,
                    loaded=loaded,
                    env=env,
                    sink=sink,
                    current_inventory=current_inventory,
                    current_entries=current_entries,
                )
            return packed

        def adopt_full(full: Mapping[str, Any]) -> dict[str, Any]:
            return {
                "filename": full["bundle"],
                "sha256": full["sha256"],
                "inventory_sha256": current_inventory,
                "bytes": full["bytes"],
            }

        def persist_chain(*, last_weekly: Any) -> None:
            write_chain_state(
                root,
                offhost,
                {
                    "base_full": base,
                    "ordered_deltas": ordered,
                    "last_weekly_date": last_weekly,
                    "tip_entries": current_entries,
                    "tip_inventory_sha256": current_inventory,
                },
            )

        skip_daily = False
        if weekly_due:
            if base and str(base.get("inventory_sha256")) == current_inventory:
                checkpoint_terminal = "FULL_COVERAGE_RECONFIRMED_NO_CHANGE"
                source_full = {
                    "bundle": base["filename"],
                    "sha256": base["sha256"],
                    "bytes": base.get("bytes"),
                }
                persist_chain(last_weekly=clock.date().isoformat())
                skip_daily = True
            else:
                full = ensure_full()
                copied_payload = _accounted_copy(
                    root=root,
                    config=offhost,
                    runner=invoke,
                    clock=clock,
                    local_path=sink / str(full["bundle"]),
                    remote_object=offhost.remote_object(str(full["bundle"])),
                )
                if copied_payload["terminal"] == "COPY_FAILED":
                    weekly_full_state = "DEGRADED"
                    if mode == "weekly" or base is None:
                        raise OffhostBackupError("OFFHOST_COPY_FAILED")
                    skip_daily = False
                else:
                    checkpoint_terminal = "WEEKLY_FULL_VERIFIED"
                    base = adopt_full(full)
                    ordered = []
                    source_full = full
                    prune_superseded_local_backups(sink, sink / str(full["bundle"]))
                    persist_chain(last_weekly=clock.date().isoformat())
                    skip_daily = True

        if mode == "daily" and skip_daily is False:
            tip_entries = chain.get("tip_entries") if isinstance(chain.get("tip_entries"), list) else None
            tip_inventory = str(chain.get("tip_inventory_sha256") or "")
            if base is None:
                full = ensure_full()
                copied_payload = _accounted_copy(
                    root=root,
                    config=offhost,
                    runner=invoke,
                    clock=clock,
                    local_path=sink / str(full["bundle"]),
                    remote_object=offhost.remote_object(str(full["bundle"])),
                )
                if copied_payload["terminal"] == "COPY_FAILED":
                    raise OffhostBackupError("OFFHOST_COPY_FAILED")
                base = adopt_full(full)
                ordered = []
                source_full = full
                checkpoint_terminal = "WEEKLY_FULL_VERIFIED"
                prune_superseded_local_backups(sink, sink / str(full["bundle"]))
            elif tip_inventory == current_inventory or str(base.get("inventory_sha256")) == current_inventory:
                checkpoint_terminal = "NO_CHANGES_VERIFIED"
                source_full = {
                    "bundle": base["filename"],
                    "sha256": base["sha256"],
                    "bytes": base.get("bytes"),
                }
            else:
                parent_manifest: dict[str, Any] | None = None
                if tip_entries:
                    parent_manifest = {
                        "entries": tip_entries,
                        "inventory_sha256": tip_inventory or logical_inventory_sha256(tip_entries),
                    }
                else:
                    base_bundle = sink / str(base["filename"])
                    if base_bundle.is_file():
                        parent_manifest = read_backup_manifest(base_bundle)
                if parent_manifest is None:
                    full = ensure_full()
                    copied_payload = _accounted_copy(
                        root=root,
                        config=offhost,
                        runner=invoke,
                        clock=clock,
                        local_path=sink / str(full["bundle"]),
                        remote_object=offhost.remote_object(str(full["bundle"])),
                    )
                    if copied_payload["terminal"] == "COPY_FAILED":
                        raise OffhostBackupError("OFFHOST_COPY_FAILED")
                    base = adopt_full(full)
                    ordered = []
                    source_full = full
                    checkpoint_terminal = "WEEKLY_FULL_VERIFIED"
                    prune_superseded_local_backups(sink, sink / str(full["bundle"]))
                else:
                    delta = package_delta_backup(
                        root,
                        base_manifest=parent_manifest,
                        current_entries=current_entries,
                        sink=sink,
                        acquire_lock=False,
                    )
                    source_full = {
                        "bundle": base["filename"],
                        "sha256": base["sha256"],
                        "bytes": base.get("bytes"),
                    }
                    if int(delta.get("delta_payload_bytes") or 0) == 0:
                        checkpoint_terminal = "NO_CHANGES_VERIFIED"
                    else:
                        delta_path = Path(delta["path"])
                        copied_payload = _accounted_copy(
                            root=root,
                            config=offhost,
                            runner=invoke,
                            clock=clock,
                            local_path=delta_path,
                            remote_object=offhost.remote_object(str(delta["bundle"])),
                        )
                        if copied_payload["terminal"] == "COPY_FAILED":
                            raise OffhostBackupError("OFFHOST_COPY_FAILED")
                        ordered.append(
                            {
                                "filename": delta["bundle"],
                                "sha256": delta["sha256"],
                                "result_inventory_sha256": delta["result_inventory_sha256"],
                                "bytes": delta["bytes"],
                            }
                        )
                        checkpoint_terminal = "DAILY_DELTA_VERIFIED"
                        try:
                            delta_path.unlink()
                        except OSError:
                            pass
            persist_chain(last_weekly=chain.get("last_weekly_date"))

        if base is None:
            raise OffhostBackupError("BASE_FULL_MISSING")
        if source_full is None:
            source_full = {
                "bundle": base["filename"],
                "sha256": base["sha256"],
                "bytes": base.get("bytes"),
            }
        checkpoint_body = {
            "source_backup_sha256": source_full["sha256"],
            "result_inventory_sha256": current_inventory,
            "base_full": {
                "filename": base["filename"],
                "sha256": base["sha256"],
                "inventory_sha256": base["inventory_sha256"],
            },
            "ordered_deltas": [
                {
                    "filename": item["filename"],
                    "sha256": item["sha256"],
                    "result_inventory_sha256": item["result_inventory_sha256"],
                }
                for item in ordered
            ],
            "checkpoint_terminal": checkpoint_terminal,
            "weekly_full_state": weekly_full_state,
            "deploy_git_sha": deploy_git_sha,
        }
        published = publish_recovery_checkpoint(
            root=root,
            config=offhost,
            runner=invoke,
            clock=clock,
            checkpoint=checkpoint_body,
            sink=sink,
        )
        _record_traffic(
            root,
            offhost,
            clock=clock,
            attempted_payload_bytes=int(published["copy"]["attempted_payload_bytes"]),
            verified_payload_bytes=int(published["copy"]["verified_payload_bytes"]),
            already_present_payload_bytes=0,
            terminal=str(published["copy"]["terminal"]),
        )
        timestamp = clock.isoformat(timespec="seconds").replace("+00:00", "Z")
        receipt = {
            "uploaded_at": timestamp,
            "verified_at": timestamp,
            "source_backup_filename": source_full["bundle"],
            "source_sha256": source_full["sha256"],
            "source_bytes": source_full.get("bytes"),
            "remote_logical_path": published["remote_logical_path"],
            "remote_bytes": published["copy"].get("remote_bytes"),
            "terminal": checkpoint_terminal,
            "checkpoint_filename": published["filename"],
            "checkpoint_sha256": published["sha256"],
            "weekly_full_state": weekly_full_state,
            "rclone_version": _rclone_version(offhost, invoke),
            "deploy_git_sha": deploy_git_sha,
        }
        write_offhost_receipt(root, offhost, receipt)
        return receipt


__all__ = [
    "ALLOWED_RCLONE_SUBCOMMANDS",
    "FORBIDDEN_RCLONE_SUBCOMMANDS",
    "INTERNAL_PAYLOAD_PLANNING_BUDGET_30D",
    "OWNER_BACKUP_TRAFFIC_TARGET_30D",
    "PLANNING_FIXTURE_PAYLOAD_30D",
    "OffhostBackupError",
    "OffhostConfig",
    "agent_durability_classification",
    "build_rclone_argv",
    "classify_offhost_state",
    "classify_payload_budget",
    "conservative_full_pressure_bytes",
    "copy_offhost_backup",
    "default_rclone_runner",
    "load_offhost_config",
    "newest_checkpoint_filename",
    "offhost_health_snapshot",
    "offhost_recovery_readout",
    "payload_bytes_snapshot",
    "planning_fixture_payload_30d",
    "publish_recovery_checkpoint",
    "read_offhost_receipt",
    "rclone_config_metadata",
    "restore_incremental_chain_isolated",
    "restore_from_recovery_checkpoint",
    "run_offhost_checkpoint",
    "validate_rclone_argv",
    "validate_recovery_checkpoint",
    "verify_backup_bundle",
    "write_offhost_receipt",
]
