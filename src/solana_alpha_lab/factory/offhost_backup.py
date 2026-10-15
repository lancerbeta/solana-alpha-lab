"""Stage-2 off-host durability: ordinary runs copy immutable backup objects.

Remote prune uses a separate default-off exact-plan adapter. Never reads or
stores OAuth tokens. Local factory-remote-backup remains stage 1 durability.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sqlite3
import subprocess
import time
import shutil
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from solana_alpha_lab.factory.remote_ops import (
    RemoteOpsError,
    _backup_newest,
    _effective_backup_lists,
    _filesystem_inventory,
    _sha256_file,
    backup_domain_for,
    backup_payload_snapshot,
    backup_plane_lock,
    load_config_v1_1,
    logical_inventory_sha256,
    package_backup,
    package_delta_backup,
    read_backup_manifest,
    resolve_backup_sink,
    restore_incremental_chain_isolated,
    scan_backup_inventory,
)

RECEIPT_SCHEMA = "smial.factory-offhost-backup-receipt"
RECEIPT_SCHEMA_VERSION = "1.1"
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
ALLOWED_RCLONE_SUBCOMMANDS = frozenset({"copyto", "lsjson", "size", "hashsum"})
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
    pending_relative: str = "local/factory_v1/offhost_backup_pending.json"
    freshness_policy_revision: int = 1

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
    revision = int(offhost.get("freshness_policy_revision", 1))
    current_max = int(offhost["freshness_current_max_seconds"])
    degraded_max = int(offhost["freshness_degraded_max_seconds"])
    if (revision, current_max, degraded_max) not in {(1, 86400, 172800), (2, 108000, 172800)}:
        raise OffhostBackupError("OFFHOST_FRESHNESS_POLICY_REVISION_CONFLICT")
    if str(loaded.get("deploy", {}).get("rpo_max") or "") != ("24h" if revision == 1 else "30h"):
        raise OffhostBackupError("OFFHOST_FRESHNESS_RPO_CONFLICT")
    return OffhostConfig(
        remote_name=str(offhost["remote_name"]),
        destination_root=str(offhost["destination_root"]),
        rclone_config_absolute=Path(str(offhost["rclone_config_absolute"])),
        rclone_bin=Path(str(offhost.get("rclone_bin") or DEFAULT_RCLONE_BIN)),
        receipt_relative=str(offhost["receipt_relative"]),
        freshness_current_max_seconds=int(offhost["freshness_current_max_seconds"]),
        freshness_degraded_max_seconds=int(offhost["freshness_degraded_max_seconds"]),
        chain_relative=str(offhost.get("chain_relative") or "local/factory_v1/offhost_backup_chain.json"),
        traffic_ledger_relative=str(offhost.get("traffic_ledger_relative") or "local/factory_v1/offhost_traffic_ledger.json"),
        pending_relative=str(offhost.get("pending_relative") or "local/factory_v1/offhost_backup_pending.json"),
        freshness_policy_revision=revision,
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
        timeout=3 * 3600,
    )


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    if os.name == "posix":
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _attempt_path(root: Path, config: OffhostConfig) -> Path:
    return root / (config.receipt_relative + ".attempt.json")


def read_offhost_attempt(root: Path, config: OffhostConfig) -> dict[str, Any] | None:
    try:
        payload = json.loads(_attempt_path(root, config).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


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
        "schema_version": RECEIPT_SCHEMA_VERSION if payload.get("clock_semantics") == "SNAPSHOT_DATA_AGE_V2" else "1.0",
        "offhost_remote": OFFHOST_REMOTE,
        **dict(payload),
    }
    if _receipt_has_secrets(body):
        raise OffhostBackupError("RECEIPT_SECRET_LEAK")
    path = root / config.receipt_relative
    _atomic_write_json(_attempt_path(root, config), body)
    previous = read_offhost_receipt(root, config)
    # Keep the legacy reader on the last proven recovery point. A first failure
    # still uses the old receipt location so old installations see FAILED.
    if body.get("terminal") in SUCCESS_TERMINALS or not previous or previous.get("terminal") not in SUCCESS_TERMINALS:
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
    seconds = (clock.astimezone(UTC) - parsed.astimezone(UTC)).total_seconds()
    return int(seconds) if seconds >= 0 else None


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
    attempt = read_offhost_attempt(root, offhost)
    verified_at = str(receipt.get("verified_at") or receipt.get("uploaded_at") or "") if receipt else ""
    v2_clock = bool(receipt and receipt.get("clock_semantics") == "SNAPSHOT_DATA_AGE_V2")
    data_as_of = str(receipt.get("snapshot_data_as_of") or ("" if v2_clock else verified_at)) if receipt else ""
    age = _age_seconds(data_as_of, clock)
    if v2_clock:
        try:
            if datetime.fromisoformat(data_as_of.replace("Z", "+00:00")).tzinfo is None:
                age = None
        except ValueError:
            age = None
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
        "offhost_snapshot_data_as_of": data_as_of or None,
        "offhost_current_max_age_seconds": offhost.freshness_current_max_seconds,
        "offhost_freshness_policy_revision": offhost.freshness_policy_revision,
        "offhost_clock_semantics": "SNAPSHOT_DATA_AGE_V2" if v2_clock else "LEGACY_START_CLOCK_LOWER_BOUND",
        "offhost_last_attempt": attempt,
        "offhost_last_attempt_terminal": attempt.get("terminal") if attempt else None,
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
    root: Path, *, deploy_git_sha: str | None = None,
    config: OffhostConfig | None = None, environ: Mapping[str, str] | None = None,
    runner: RcloneRunner | None = None, now: datetime | None = None,
    acquire_lock: bool = True,
) -> dict[str, Any]:
    if acquire_lock:
        try:
            with backup_plane_lock(root, timeout_seconds=0):
                return copy_offhost_backup(root, deploy_git_sha=deploy_git_sha, config=config,
                    environ=environ, runner=runner, now=now, acquire_lock=False)
        except RemoteOpsError as exc:
            if str(exc) == "WRITER_BUSY":
                return {"terminal": "DEFERRED", "reason": "WRITER_BUSY"}
            raise
    actual_clock = lambda: now if now is not None else datetime.now(UTC)
    clock = actual_clock()
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
    path = sink / str(newest["path"])
    try:
        bundle = verify_backup_bundle(path)
    except OffhostBackupError as exc:
        write_offhost_receipt(root, offhost, {
            "terminal": "SOURCE_INTEGRITY_FAILED", "failed_at": _stamp(actual_clock()),
            "failure_code": str(exc).split(":", 1)[0], "deploy_git_sha": deploy_git_sha,
        })
        raise
    remote = offhost.remote_object(bundle["filename"])
    invoke = runner if runner is not None else default_rclone_runner
    try:
        copied = _accounted_copy(root=root, config=offhost, runner=invoke,
            clock=clock, local_path=path, remote_object=remote, wall_clock=actual_clock)
    except OffhostBackupError as exc:
        write_offhost_receipt(root, offhost, {
            "terminal": "REMOTE_IDENTITY_CONFLICT", "failed_at": _stamp(actual_clock()),
            "failure_code": str(exc).split(":", 1)[0], "deploy_git_sha": deploy_git_sha,
        })
        raise
    receipt = {
        **copied, "run_started_at": _stamp(clock),
        "source_backup_filename": bundle["filename"], "source_sha256": bundle["sha256"],
        "source_bytes": bundle["bytes"], "remote_logical_path": remote,
        "deploy_git_sha": deploy_git_sha,
    }
    if copied["terminal"] == "COPY_FAILED":
        receipt["failed_at"] = _stamp(actual_clock())
        write_offhost_receipt(root, offhost, receipt)
        raise OffhostBackupError("OFFHOST_COPY_FAILED")
    manifest = read_backup_manifest(path)
    data_as_of = manifest.get("snapshot_data_as_of")
    if data_as_of:
        receipt.update(clock_semantics="SNAPSHOT_DATA_AGE_V2", snapshot_data_as_of=data_as_of)
    else:
        # A legacy archive's historical timestamp is a lower-bound compatibility
        # clock, never rejuvenated by copying an unchanged bundle again.
        receipt.update(clock_semantics="LEGACY_START_CLOCK_LOWER_BOUND",
                       snapshot_data_as_of=str(manifest.get("created_at") or newest.get("mtime") or ""))
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
    if not path.exists() and not path.is_symlink():
        return {"base_full": None, "ordered_deltas": [], "last_weekly_date": None}
    if not path.is_file() or path.is_symlink():
        raise OffhostBackupError("OFFHOST_CHAIN_STATE_CORRUPT")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OffhostBackupError("OFFHOST_CHAIN_STATE_CORRUPT") from exc
    # Both legacy and current publishers persist a proven non-null base and
    # its complete tip. Only an absent file is an uninitialized installation.
    required = {"base_full", "ordered_deltas", "last_weekly_date", "tip_entries", "tip_inventory_sha256"}
    if (not isinstance(payload, dict) or not required.issubset(payload)
            or not isinstance(payload["ordered_deltas"], list)
            or not isinstance(payload["tip_entries"], list)):
        raise OffhostBackupError("OFFHOST_CHAIN_STATE_CORRUPT")
    base = payload.get("base_full")
    if not isinstance(base, dict) or not base.get("filename") or not base.get("sha256"):
        raise OffhostBackupError("OFFHOST_CHAIN_STATE_CORRUPT")
    if any(not isinstance(item, dict) or not item.get("filename") or not item.get("sha256") for item in payload["ordered_deltas"]):
        raise OffhostBackupError("OFFHOST_CHAIN_STATE_CORRUPT")
    try:
        references = ([base] if base else []) + payload["ordered_deltas"]
        for index, item in enumerate(references):
            name = _filename(item["filename"])
            prefix = "BACKUP_" if index == 0 else "DELTA_"
            if name != prefix + item["sha256"] + ".zip" or not _published_object_name(name):
                raise ValueError("reference")
        if logical_inventory_sha256(payload["tip_entries"]) != payload["tip_inventory_sha256"]:
            raise ValueError("tip")
    except (KeyError, TypeError, ValueError, OffhostBackupError) as exc:
        raise OffhostBackupError("OFFHOST_CHAIN_STATE_CORRUPT") from exc
    return payload


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
        except (OSError, json.JSONDecodeError) as exc:
            raise OffhostBackupError("OFFHOST_TRAFFIC_LEDGER_CORRUPT") from exc
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


def _rclone_failure_fields(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Machine fields only. Raw stderr can contain credential echoes."""

    stderr = completed.stderr or ""
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")
    lowered = stderr.lower()
    if "directory not found" in lowered or "object not found" in lowered:
        failure_class = "REMOTE_OBJECT_ABSENT"
    elif "quota" in lowered or "rate limit" in lowered or "ratelimit" in lowered:
        failure_class = "QUOTA"
    else:
        failure_class = "UNCLASSIFIED"
    return {
        "rclone_returncode": int(completed.returncode),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        "rclone_failure_class": failure_class,
    }


def copy_local_object(
    *,
    local_path: Path,
    remote_object: str,
    config: OffhostConfig,
    runner: RcloneRunner,
    clock: datetime,
    wall_clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    actual_clock = wall_clock or (lambda: clock)
    size = local_path.stat().st_size
    local_md5 = _md5_file(local_path)
    existing = _remote_metadata(config, remote_object, runner)
    if existing is not None:
        remote_bytes = int(existing["bytes"])
        if remote_bytes != size or _remote_md5(config, remote_object, runner) != local_md5:
            raise OffhostBackupError("OFFHOST_REMOTE_IDENTITY_CONFLICT")
        return {
            "terminal": "ALREADY_PRESENT_VERIFIED",
            "attempted_payload_bytes": 0,
            "verified_payload_bytes": 0,
            "already_present_payload_bytes": 0,
            "remote_bytes": remote_bytes,
            "uploaded_at": None,
            "verified_at": _stamp(actual_clock()),
            "verification": "REMOTE_MD5_AND_SIZE_LOCAL_SHA256",
        }
    argv = build_rclone_argv(config, "copyto", str(local_path), remote_object)
    try:
        completed = runner(argv)
    except (subprocess.TimeoutExpired, TimeoutError):
        completed = subprocess.CompletedProcess(argv, 124, stdout="", stderr="transport timeout")
    uploaded_at = _stamp(actual_clock())
    # A transport failure may have happened after the remote commit. Reconcile
    # this exact immutable object before retrying it, never recapture the source.
    remote_bytes = _remote_size(config, remote_object, runner)
    if remote_bytes is not None:
        if remote_bytes != size or _remote_md5(config, remote_object, runner) != local_md5:
            raise OffhostBackupError("OFFHOST_REMOTE_IDENTITY_CONFLICT")
    if completed.returncode != 0 and remote_bytes is None:
        return {
            "terminal": "COPY_FAILED",
            "attempted_payload_bytes": size,
            "verified_payload_bytes": 0,
            "already_present_payload_bytes": 0,
            "remote_bytes": None,
            **_rclone_failure_fields(completed),
        }
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
        "verification": "REMOTE_MD5_AND_SIZE_LOCAL_SHA256",
        "uploaded_at": uploaded_at,
        "verified_at": _stamp(actual_clock()),
    }


def _md5_file(path: Path) -> str:
    # MD5 is the existing Drive checksum capability; SHA256 still binds local
    # identities. This checks transport bytes, never authenticity of a provider.
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remote_md5(config: OffhostConfig, remote_object: str, runner: RcloneRunner) -> str:
    completed = runner(build_rclone_argv(config, "hashsum", "MD5", remote_object))
    if completed.returncode != 0:
        raise OffhostBackupError("OFFHOST_REMOTE_CHECKSUM_UNAVAILABLE")
    rows = (completed.stdout or "").splitlines()
    if len(rows) != 1:
        raise OffhostBackupError("OFFHOST_REMOTE_CHECKSUM_INVALID")
    digest = rows[0].split()[0].lower() if rows[0].split() else ""
    if len(digest) != 32 or any(char not in "0123456789abcdef" for char in digest):
        raise OffhostBackupError("OFFHOST_REMOTE_CHECKSUM_INVALID")
    return digest


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
    snapshot: Any = None,
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
        snapshot=snapshot,
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
    temporary = sink / ("." + filename + ".pending")
    try:
        with temporary.open("wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if _sha256_file(temporary) != digest:
            raise OffhostBackupError("CHECKPOINT_HASH_MISMATCH")
        os.replace(temporary, local)
    finally:
        if temporary.is_file():
            temporary.unlink()
    validate_recovery_checkpoint(local)
    remote = config.remote_object(filename)
    copied = _accounted_copy(
        root=root,
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
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise OffhostBackupError("CHECKPOINT_VERSION_UNSUPPORTED")
    try:
        datetime.strptime(_stamp, "%Y%m%dT%H%M%SZ")
        references = [payload["base_full"], *payload["ordered_deltas"]]
        if not isinstance(payload["ordered_deltas"], list):
            raise ValueError("deltas")
        names: set[str] = set()
        for index, reference in enumerate(references):
            filename = _filename(reference["filename"])
            prefix = "BACKUP_" if index == 0 else "DELTA_"
            expected = prefix + reference["sha256"] + ".zip"
            if filename != expected or filename in names:
                raise ValueError("reference")
            if len(reference["sha256"]) != 64 or any(char not in "0123456789abcdef" for char in reference["sha256"]):
                raise ValueError("hash")
            names.add(filename)
        inventory = payload["result_inventory_sha256"]
        if len(inventory) != 64 or any(char not in "0123456789abcdef" for char in inventory):
            raise ValueError("inventory")
    except (KeyError, TypeError, ValueError) as exc:
        raise OffhostBackupError("CHECKPOINT_REFERENCES_INVALID") from exc
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
    wall_clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    def accounted_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        # Persist attempted bytes before invoking the transport; timeout or a
        # process death must not erase the transfer attempt from the ledger.
        if len(argv) > 3 and argv[3] == "copyto":
            _record_traffic(root, config, clock=clock,
                attempted_payload_bytes=local_path.stat().st_size,
                verified_payload_bytes=0, terminal="COPY_STARTED")
        return runner(argv)

    copied = copy_local_object(
        local_path=local_path,
        remote_object=remote_object,
        config=config,
        runner=accounted_runner,
        clock=clock,
        wall_clock=wall_clock,
    )
    _record_traffic(
        root,
        config,
        clock=clock,
        attempted_payload_bytes=0,
        verified_payload_bytes=int(copied["verified_payload_bytes"]),
        already_present_payload_bytes=0,
        terminal=str(copied["terminal"]),
    )
    return copied


def _filename(value: Any) -> str:
    name = str(value)
    if not name or Path(name).name != name or "/" in name or "\\" in name or name in {".", ".."}:
        raise OffhostBackupError("OFFHOST_OBJECT_NAME_INVALID")
    return name


def _published_object_name(name: str) -> bool:
    if name.startswith(("BACKUP_", "DELTA_")) and name.endswith(".zip"):
        digest = name.split("_", 1)[1][:-4]
    elif name.startswith("RECOVERY_CHECKPOINT_") and name.endswith(".json"):
        try:
            stamp, digest = name[len("RECOVERY_CHECKPOINT_"):-5].rsplit("_", 1)
            datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")
        except ValueError:
            return False
    else:
        return False
    return len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)


def _referenced_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "filename":
                names.add(_filename(child))
            else:
                names.update(_referenced_names(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            names.update(_referenced_names(child))
    return names


def plan_backup_prune(
    objects: Sequence[str], retained_checkpoints: Sequence[Mapping[str, Any]], *,
    scientific_pins: Sequence[str] = (),
    pending_operations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Pure reachability plan; it grants no local or remote delete authority."""
    available = {_filename(name) for name in objects}
    reachable = _referenced_names(list(retained_checkpoints)) | _referenced_names(list(pending_operations))
    reachable.update(_filename(name) for name in scientific_pins)
    eligible = {name for name in available if _published_object_name(name)}
    body = {
        "schema": "smial.factory-backup-prune-plan", "schema_version": "1.0",
        "reachable": sorted(reachable),
        "removable": sorted(eligible - reachable) if not reachable - available else [],
        "missing_references": sorted(reachable - available), "remote_delete_enabled": False,
        "requires_exact_operate_authority": True,
    }
    body["plan_sha256"] = hashlib.sha256(_checkpoint_canonical(body)).hexdigest()
    return body


def _pending_path(root: Path, config: OffhostConfig) -> Path:
    return root / config.pending_relative


def plan_checkpoint_prune(
    root: Path, *, objects: Sequence[str], config: OffhostConfig,
    retained_checkpoint_filenames: Sequence[str] = (), scientific_pins: Sequence[str] = (),
    environ: Mapping[str, str] | None = None,
    restore_proof_artifacts: Sequence[Path] = (),
) -> dict[str, Any]:
    """Bind a bounded object inventory to current local recovery references."""
    if len(objects) > 10000:
        raise OffhostBackupError("PRUNE_OBJECT_BUDGET_EXCEEDED")
    chain = read_chain_state(root, config)
    pending = _read_pending(root, config)
    last_good = (chain.get("last_checkpoint") or {}).get("filename")
    if not last_good:
        receipt = read_offhost_receipt(root, config) or {}
        last_good = receipt.get("checkpoint_filename")
    if not last_good:
        raise OffhostBackupError("PRUNE_LAST_GOOD_CHECKPOINT_REQUIRED")
    selected = {_filename(last_good), *(_filename(name) for name in retained_checkpoint_filenames)}
    for point in chain.get("retained_checkpoints") or []:
        selected.add(_filename(point["filename"]))
    if len(selected) > 32:
        raise OffhostBackupError("PRUNE_RESTORE_POINT_BUDGET_EXCEEDED")
    sink = resolve_backup_sink(root, load_config_v1_1(root), environ if environ is not None else os.environ)
    retained = []
    for name in sorted(selected):
        retained.append({"filename": name, "checkpoint": validate_recovery_checkpoint(sink / name)})
    native_pins = _retention_cold_archive_pins(root, objects)
    pins = sorted({_filename(name) for name in [*scientific_pins, *(chain.get("scientific_pins") or []),
                                               *native_pins["matching"]]})
    source = {"chain": chain, "pending": pending, "retained": retained,
              "scientific_pins": pins, "native_pins": native_pins}
    body = plan_backup_prune(objects, [chain, *retained], scientific_pins=pins,
        pending_operations=[pending] if pending else [])
    body.pop("plan_sha256")
    if native_pins["missing_count"]:
        body["missing_references"].append("NATIVE_COLD_PINS_MISSING_COUNT:" + str(native_pins["missing_count"]))
        body["removable"] = []
    body.update(objects=sorted(set(objects)), retained_checkpoint_filenames=sorted(selected),
        scientific_pins=pins, reference_sha256=hashlib.sha256(_checkpoint_canonical(source)).hexdigest())
    artifacts = _load_prune_proof_artifacts(restore_proof_artifacts)
    body["restore_proof_artifact_sha256"] = {
        name: artifact["sha256"] for name, artifact in sorted(artifacts.items()) if name in selected
    }
    body["plan_sha256"] = hashlib.sha256(_checkpoint_canonical(body)).hexdigest()
    return body


def _load_prune_proof_artifacts(paths: Sequence[Path]) -> dict[str, dict[str, Any]]:
    """Read durable verifier outputs; caller-supplied assertions grant nothing."""
    if len(paths) > 32:
        raise OffhostBackupError("PRUNE_RESTORE_PROOF_ARTIFACT_BUDGET")
    result: dict[str, dict[str, Any]] = {}
    for path in paths:
        path = Path(path)
        try:
            if (path.name != ".remote-restore-proof.json" or path.is_symlink()
                    or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024):
                raise ValueError("artifact")
            proof = json.loads(path.read_text(encoding="utf-8"))
            intent = json.loads((path.parent / ".remote-restore-intent.json").read_text(encoding="utf-8"))
            if not isinstance(proof, dict) or not isinstance(intent, dict):
                raise ValueError("shape")
            for entries in (proof.get("verified_objects"), proof.get("operational_inventory"), intent.get("objects")):
                if not isinstance(entries, list) or not entries or any(not isinstance(item, dict) for item in entries):
                    raise ValueError("entries")
            if not isinstance(proof.get("restore"), dict):
                raise ValueError("restore")
            name = _filename(proof["checkpoint_filename"])
            if (name in result or proof.get("schema") != "smial.factory-remote-restore-proof"
                    or proof.get("schema_version") != "1.0"
                    or proof.get("terminal") != "REMOTE_CHECKPOINT_RESTORE_VERIFIED"
                    or intent.get("schema") != "smial.factory-remote-restore-intent"
                    or intent.get("checkpoint_filename") != name
                    or intent.get("checkpoint_sha256") != proof.get("checkpoint_sha256")):
                raise ValueError("identity")
            result[name] = {"payload": proof, "intent": intent, "path": path,
                            "sha256": _sha256_file(path)}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise OffhostBackupError("PRUNE_RESTORE_PROOF_ARTIFACT_INVALID") from exc
    return result


def _verify_prune_proof_oracle(artifact: Mapping[str, Any], checkpoint_path: Path, *,
        verified_tree_consumer: Callable[[Path, Path], None] | None = None) -> dict[str, Any]:
    """Reconstruct actual cached archive bytes; never trust an integrity label."""
    proof = artifact["payload"]
    cache = Path(artifact["path"]).parent
    objects = cache / "objects"
    expected_checkpoint = validate_recovery_checkpoint(checkpoint_path)
    identities = proof.get("verified_objects") or []
    if not identities or len({item["filename"] for item in identities}) != len(identities):
        raise OffhostBackupError("PRUNE_RESTORE_PROOF_OBJECTS_CONFLICT")
    expected_names = {item["filename"] for item in artifact["intent"]["objects"]}
    if {item["filename"] for item in identities} != expected_names:
        raise OffhostBackupError("PRUNE_RESTORE_PROOF_OBJECTS_CONFLICT")
    actual_names = {path.name for path in objects.iterdir()}
    if actual_names != expected_names or any(path.is_symlink() or not path.is_file() for path in objects.iterdir()):
        raise OffhostBackupError("PRUNE_RESTORE_PROOF_OBJECTS_CONFLICT")
    for item in identities:
        source = objects / _filename(item["filename"])
        if _sha256_file(source) != item["sha256"] or source.stat().st_size != int(item["bytes"]) or _md5_file(source) != item["md5"]:
            raise OffhostBackupError("PRUNE_RESTORE_PROOF_OBJECTS_CONFLICT")
    cached_checkpoint = objects / checkpoint_path.name
    if _sha256_file(cached_checkpoint) != _sha256_file(checkpoint_path):
        raise OffhostBackupError("PRUNE_RESTORE_PROOF_CHECKPOINT_CONFLICT")
    restored_root = cache / "restored"
    if cache.is_symlink() or objects.is_symlink() or restored_root.is_symlink():
        raise OffhostBackupError("PRUNE_RESTORE_PROOF_CACHE_UNSAFE")
    actual = _filesystem_inventory(restored_root)
    if sorted(actual, key=lambda item: item["path"]) != sorted(proof.get("operational_inventory") or [], key=lambda item: item["path"]):
        raise OffhostBackupError("PRUNE_RESTORE_PROOF_OPERATIONAL_CONFLICT")
    scratch = cache / ".prune-verify"
    scratch_intent = cache / ".prune-verify.intent.json"
    ownership = {"proof_artifact_sha256": artifact["sha256"], "checkpoint_sha256": _sha256_file(checkpoint_path)}
    if scratch.exists():
        try:
            owned = json.loads(scratch_intent.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OffhostBackupError("PRUNE_RESTORE_SCRATCH_OWNERSHIP_CONFLICT") from exc
        if (owned != ownership or scratch.is_symlink() or not scratch.resolve().is_relative_to(cache.resolve())
                or any(path.is_symlink() for path in scratch.rglob("*"))):
            raise OffhostBackupError("PRUNE_RESTORE_SCRATCH_OWNERSHIP_CONFLICT")
        shutil.rmtree(scratch)
    _atomic_write_json(scratch_intent, ownership)
    try:
        raw_budget = sum(int(item["bytes"]) for item in read_backup_manifest(
            objects / expected_checkpoint["base_full"]["filename"])["entries"])
        for item in expected_checkpoint["ordered_deltas"]:
            with zipfile.ZipFile(objects / item["filename"]) as archive:
                raw_budget += sum(int(entry["bytes"]) for entry in json.loads(
                    archive.read("DELTA_MANIFEST.json"))["changed"])
        raw_budget += sum(int(item["bytes"]) for descriptor in artifact["intent"].get("supplemental_archives") or []
                          for item in descriptor["raw_entries"])
        if shutil.disk_usage(cache).free < raw_budget:
            raise OffhostBackupError("PRUNE_RESTORE_DISK_BUDGET_EXHAUSTED")
        oracle = restore_from_recovery_checkpoint(checkpoint_path=cached_checkpoint,
            objects_dir=objects, dest_root=scratch)
        supplemental = _hydrate_retirement_raw_archives(artifact["intent"].get("supplemental_archives") or [],
            objects_dir=objects, restored_root=scratch)
        expected_members = {item["path"] for item in [*oracle["restored"], *supplemental]}
        if (oracle["raw_inventory_sha256"] != expected_checkpoint["result_inventory_sha256"]
                or {item["path"] for item in actual} != expected_members
                or not oracle.get("sqlite_integrity")
                or any(item.get("result") != "ok" for item in oracle["sqlite_integrity"])
                or proof.get("restore", {}).get("sqlite_integrity") != oracle["sqlite_integrity"]
                or sorted(proof.get("restore", {}).get("restored") or [], key=lambda item: item["path"])
                    != sorted(oracle["restored"], key=lambda item: item["path"])
                or proof.get("supplemental_raw_inventory", []) != supplemental):
            raise OffhostBackupError("PRUNE_RESTORE_PROOF_ORACLE_FAILED")
        if verified_tree_consumer is not None:
            verified_tree_consumer(restored_root, scratch)
        return oracle
    finally:
        if scratch.exists() and not scratch.is_symlink() and scratch.resolve().is_relative_to(cache.resolve()):
            shutil.rmtree(scratch)
        scratch_intent.unlink(missing_ok=True)


def _retention_cold_archive_pins(root: Path, candidates: Sequence[str]) -> dict[str, Any]:
    """Bounded exact membership against the native indexed/WAL-aware pin owner."""
    from solana_alpha_lab.factory.observation_schedule_runtime import load_runtime_config

    if not (root / "configs/observation_schedule_runtime_v1.yaml").is_file():
        raise OffhostBackupError("PRUNE_RETENTION_PIN_OWNER_CONFIG_MISSING")
    try:
        runtime = load_runtime_config(root, "configs/observation_schedule_runtime_v1.yaml")
        path = (root / str(runtime["ops_store_relative"])).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise OffhostBackupError("PRUNE_RETENTION_PIN_OWNER_MISSING")
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('retention_archive_pins','retention_control')")}
            matching: set[str] = set()
            if "retention_archive_pins" in tables:
                total = int(connection.execute("SELECT COUNT(*) FROM retention_archive_pins").fetchone()[0])
                for offset in range(0, len(candidates), 256):
                    chunk = list(candidates[offset:offset + 256])
                    placeholders = ",".join("?" for _ in chunk)
                    matching.update(_filename(row[0]) for row in connection.execute(
                        "SELECT object_name FROM retention_archive_pins WHERE object_name IN (" + placeholders + ")", chunk))
            elif "retention_control" in tables:
                # Transitional old installations: SQLite filters the old array;
                # Python never loads the complete lifetime pin list.
                row = connection.execute("SELECT json_valid(payload_json),json_type(payload_json) FROM retention_control WHERE control_key='cold_archive_pins'").fetchone()
                if row is None:
                    total = 0
                elif row[0] != 1 or row[1] != "array":
                    raise ValueError("pins")
                else:
                    total = int(connection.execute("SELECT json_array_length(payload_json) FROM retention_control WHERE control_key='cold_archive_pins'").fetchone()[0])
                    for offset in range(0, len(candidates), 256):
                        chunk = list(candidates[offset:offset + 256])
                        placeholders = ",".join("?" for _ in chunk)
                        matching.update(_filename(row[0]) for row in connection.execute(
                            "SELECT value FROM json_each((SELECT payload_json FROM retention_control WHERE control_key='cold_archive_pins')) WHERE value IN (" + placeholders + ")", chunk))
            else:
                total = 0
            return {"matching": sorted(matching), "total_count": total, "missing_count": total - len(matching)}
        finally:
            connection.close()
    except OffhostBackupError:
        raise
    except Exception as exc:
        raise OffhostBackupError("PRUNE_RETENTION_PIN_STATE_CORRUPT") from exc

def verify_remote_checkpoint_restore(
    *, checkpoint_path: Path, isolated_root: Path,
    config: OffhostConfig, runner: RcloneRunner | None = None,
    max_objects: int = 128, max_bytes: int = 20 * GB,
    max_wall_seconds: float = 3 * 3600,
    monotonic_clock: Callable[[], float] = time.monotonic,
    supplemental_archives: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Independent content readback with one immutable, resumable owned cache."""
    checkpoint = validate_recovery_checkpoint(checkpoint_path)
    identities = [{"filename": checkpoint_path.name, "sha256": _sha256_file(checkpoint_path)},
                  checkpoint["base_full"], *checkpoint["ordered_deltas"], *supplemental_archives]
    for archive in supplemental_archives:
        if (_filename(archive["filename"]) != "ARCHIVE_" + str(archive["sha256"]) + ".zip"
                or archive.get("remote_object") != config.remote_object(archive["filename"])):
            raise OffhostBackupError("REMOTE_RESTORE_SUPPLEMENT_IDENTITY_CONFLICT")
    if len({item["filename"] for item in identities}) != len(identities):
        raise OffhostBackupError("REMOTE_RESTORE_DUPLICATE_OBJECT_IDENTITY")
    if not 0 < len(identities) <= max_objects <= 128 or max_bytes <= 0 or max_wall_seconds <= 0:
        raise OffhostBackupError("REMOTE_RESTORE_BUDGET_INVALID")
    identity = {"schema": "smial.factory-remote-restore-intent", "schema_version": "1.0",
                "checkpoint_filename": checkpoint_path.name, "checkpoint_sha256": _sha256_file(checkpoint_path),
                "objects": [{"filename": item["filename"], "sha256": item["sha256"]} for item in identities]}
    identity["supplemental_archives"] = list(supplemental_archives)
    intent_path = isolated_root / ".remote-restore-intent.json"
    if isolated_root.exists():
        try:
            existing = json.loads(intent_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OffhostBackupError("REMOTE_RESTORE_DEST_NOT_OWNED") from exc
        if existing != identity:
            raise OffhostBackupError("REMOTE_RESTORE_DEST_IDENTITY_CONFLICT")
    else:
        isolated_root.mkdir(parents=True)
        _atomic_write_json(intent_path, identity)
    objects_dir = isolated_root / "objects"
    objects_dir.mkdir(exist_ok=True)
    allowed_names = {str(item["filename"]) for item in identities}
    allowed_names.update("." + name + ".pending" for name in list(allowed_names))
    if objects_dir.is_symlink() or any(path.is_symlink() or path.name not in allowed_names for path in objects_dir.iterdir()):
        raise OffhostBackupError("REMOTE_RESTORE_CACHE_MEMBERSHIP_CONFLICT")
    started = monotonic_clock()
    def invoke(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        remaining = max_wall_seconds - (monotonic_clock() - started)
        if remaining <= 0:
            raise OffhostBackupError("REMOTE_RESTORE_WALL_BUDGET_EXHAUSTED")
        if runner is not None:
            return runner(argv)
        validate_rclone_argv(argv)
        return subprocess.run(list(argv), check=False, capture_output=True, text=True, timeout=remaining)
    # Check the complete transfer closure before admitting any download. Cached
    # objects are part of the same operation budget, never a new generation.
    total = 0
    for item in identities:
        size = _remote_size(config, config.remote_object(_filename(item["filename"])), invoke)
        if size is None:
            raise OffhostBackupError("REMOTE_RESTORE_OBJECT_MISSING")
        total += size
    if total > max_bytes:
        raise OffhostBackupError("REMOTE_RESTORE_BYTE_BUDGET_EXHAUSTED")
    cached_bytes = sum(path.stat().st_size for path in objects_dir.iterdir() if path.is_file() and not path.is_symlink())
    if shutil.disk_usage(isolated_root).free < max(0, total - cached_bytes):
        raise OffhostBackupError("REMOTE_RESTORE_DISK_BUDGET_EXHAUSTED")
    verified = []
    for item in identities:
        name = _filename(item["filename"])
        local = objects_dir / name
        if not local.is_file() or local.is_symlink() or _sha256_file(local) != item["sha256"]:
            staging = objects_dir / ("." + name + ".pending")
            result = invoke(build_rclone_argv(config, "copyto", config.remote_object(name), str(staging)))
            if result.returncode != 0 or not staging.is_file() or _sha256_file(staging) != item["sha256"]:
                if staging.is_file() and not staging.is_symlink():
                    staging.unlink()
                raise OffhostBackupError("REMOTE_RESTORE_CONTENT_READBACK_FAILED")
            os.replace(staging, local)
        verified.append({"filename": name, "sha256": item["sha256"],
                         "md5": _md5_file(local), "bytes": local.stat().st_size})
    proof_path = isolated_root / ".remote-restore-proof.json"
    if proof_path.is_file():
        try:
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OffhostBackupError("REMOTE_RESTORE_PROOF_CACHE_CONFLICT") from exc
        if proof.get("checkpoint_sha256") != identity["checkpoint_sha256"] or proof.get("verified_objects") != verified:
            raise OffhostBackupError("REMOTE_RESTORE_PROOF_CACHE_CONFLICT")
        for item in proof.get("operational_inventory") or []:
            path = isolated_root / "restored" / str(item["path"])
            if (not path.resolve().is_relative_to((isolated_root / "restored").resolve())
                    or path.is_symlink() or not path.is_file() or path.stat().st_size != item["bytes"]
                    or _sha256_file(path) != item["sha256"]):
                raise OffhostBackupError("REMOTE_RESTORE_PROOF_CACHE_CONFLICT")
        if not proof.get("operational_inventory"):
            raise OffhostBackupError("REMOTE_RESTORE_PROOF_CACHE_CONFLICT")
        return proof
    restored_root = isolated_root / "restored"
    if restored_root.exists():
        # Only this intent's partially reconstructed tree may be removed.
        # Reject symlinks and validate the absolute target before recursive work.
        if (restored_root.is_symlink() or not restored_root.resolve().is_relative_to(isolated_root.resolve())
                or any(path.is_symlink() for path in restored_root.rglob("*"))):
            raise OffhostBackupError("REMOTE_RESTORE_PARTIAL_ROOT_UNSAFE")
        shutil.rmtree(restored_root)
    estimate = sum(int(item["bytes"]) for item in read_backup_manifest(objects_dir / checkpoint["base_full"]["filename"])["entries"])
    for item in checkpoint["ordered_deltas"]:
        with zipfile.ZipFile(objects_dir / item["filename"]) as archive:
            delta = json.loads(archive.read("DELTA_MANIFEST.json"))
            estimate += sum(int(entry["bytes"]) for entry in delta["changed"])
    estimate += sum(int(entry["bytes"]) for archive in supplemental_archives for entry in archive["raw_entries"])
    if shutil.disk_usage(isolated_root).free < estimate:
        raise OffhostBackupError("REMOTE_RESTORE_DISK_BUDGET_EXHAUSTED")
    if monotonic_clock() - started >= max_wall_seconds:
        raise OffhostBackupError("REMOTE_RESTORE_WALL_BUDGET_EXHAUSTED")
    restored = restore_from_recovery_checkpoint(checkpoint_path=objects_dir / checkpoint_path.name,
        objects_dir=objects_dir, dest_root=restored_root)
    if restored.get("raw_inventory_sha256") != checkpoint["result_inventory_sha256"]:
        raise OffhostBackupError("REMOTE_RESTORE_INVENTORY_NOT_PROVEN")
    supplemental_inventory = _hydrate_retirement_raw_archives(
        supplemental_archives, objects_dir=objects_dir, restored_root=restored_root)
    if monotonic_clock() - started >= max_wall_seconds:
        raise OffhostBackupError("REMOTE_RESTORE_WALL_BUDGET_EXHAUSTED")
    proof = {"terminal": "REMOTE_CHECKPOINT_RESTORE_VERIFIED", "checkpoint_filename": checkpoint_path.name,
             "schema": "smial.factory-remote-restore-proof", "schema_version": "1.0",
             "checkpoint_sha256": identity["checkpoint_sha256"],
             "result_inventory_sha256": checkpoint["result_inventory_sha256"],
             "verified_objects": verified, "restore": restored,
             "supplemental_raw_inventory": supplemental_inventory,
             "restored_data_root_relative": "restored", "objects_relative": "objects",
             "operational_inventory": [{"path": path.relative_to(restored_root).as_posix(),
                                        "bytes": path.stat().st_size, "sha256": _sha256_file(path)}
                                       for path in sorted(restored_root.rglob("*")) if path.is_file()],
             "downloaded_closure_bytes": total,
             "restored_logical_bytes": sum(int(item["bytes"]) for item in [*restored["restored"], *supplemental_inventory]),
             "staging_final_bytes": sum(path.stat().st_size for path in isolated_root.rglob("*") if path.is_file())}
    if monotonic_clock() - started >= max_wall_seconds:
        raise OffhostBackupError("REMOTE_RESTORE_WALL_BUDGET_EXHAUSTED")
    _atomic_write_json(proof_path, proof)
    return proof


def _hydrate_retirement_raw_archives(
    descriptors: Sequence[Mapping[str, Any]], *, objects_dir: Path, restored_root: Path,
) -> list[dict[str, Any]]:
    """WRAP the existing closed-day manifest; stream only required source bodies."""
    from solana_alpha_lab.factory.hot90_archive import ARCHIVE_KIND, confined_relative_file
    from solana_alpha_lab.factory.observation_schedule import canonical_sha256

    result: dict[str, dict[str, Any]] = {}
    for descriptor in descriptors:
        with zipfile.ZipFile(objects_dir / descriptor["filename"]) as archive:
            manifest = json.loads(archive.read("ARCHIVE_MANIFEST.json"))
            entries = manifest.get("entries") or []
            if (manifest.get("kind") != ARCHIVE_KIND
                    or manifest.get("inventory_sha256") != descriptor["inventory_sha256"]
                    or canonical_sha256(entries) != descriptor["inventory_sha256"]):
                raise OffhostBackupError("RETIREMENT_RAW_ARCHIVE_INVENTORY_CONFLICT")
            by_path = {item["path"]: item for item in entries}
            if len(by_path) != len(entries) or len(set(archive.namelist())) != len(archive.namelist()):
                raise OffhostBackupError("RETIREMENT_RAW_ARCHIVE_DUPLICATE_PATH")
            for item in descriptor["raw_entries"]:
                relative = str(item["path"])
                declared = by_path.get(relative)
                if not declared or declared["sha256"] != item["sha256"] or int(declared["bytes"]) != int(item["bytes"]):
                    raise OffhostBackupError("RETIREMENT_RAW_ARCHIVE_ENTRY_CONFLICT")
                full_relative = "local/factory_v1/observation_rdp/" + relative
                target = confined_relative_file(restored_root, full_relative,
                    error=OffhostBackupError, code="RETIREMENT_RAW_ARCHIVE_PATH_UNSAFE")
                info = archive.getinfo(relative)
                if info.file_size != int(item["bytes"]) or stat.S_ISLNK(info.external_attr >> 16):
                    raise OffhostBackupError("RETIREMENT_RAW_ARCHIVE_ENTRY_UNSAFE")
                target.parent.mkdir(parents=True, exist_ok=True)
                staging = target.with_name("." + target.name + ".i2-raw-pending")
                digest, size = hashlib.sha256(), 0
                try:
                    with archive.open(info) as source, staging.open("wb") as destination:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            destination.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                    if digest.hexdigest() != item["sha256"] or size != int(item["bytes"]):
                        raise OffhostBackupError("RETIREMENT_RAW_ARCHIVE_HASH_CONFLICT")
                    if target.exists() and (_sha256_file(target) != item["sha256"] or target.stat().st_size != size):
                        raise OffhostBackupError("RETIREMENT_RAW_CHECKPOINT_SOURCE_CONFLICT")
                    os.replace(staging, target)
                finally:
                    if staging.is_file():
                        staging.unlink()
                result[full_relative] = {"path": full_relative, "sha256": item["sha256"], "bytes": size}
    return [result[name] for name in sorted(result)]

def apply_remote_backup_prune(
    root: Path, *, plan: Mapping[str, Any], config: OffhostConfig,
    runner: RcloneRunner | None = None, approved_plan_sha256: str | None = None,
    remote_delete_authorized: bool = False,
    restore_proofs: Sequence[Mapping[str, Any]] = (),
    restore_proof_artifacts: Sequence[Path] = (),
    max_delete_objects: int = 8, max_wall_seconds: float = 30.0,
    monotonic_clock: Callable[[], float] = time.monotonic,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Separate exact-plan adapter; ordinary rclone remains copy-only.

    No wildcard, sync, purge or credential/config mutation is expressible here.
    Every retained point needs an independent content-readback/restore proof;
    current remote checksums must still match that proven closure.
    """
    if not remote_delete_authorized:
        return {"status": "DISABLED", "reason": "REMOTE_DELETE_DEFAULT_OFF"}
    body = {key: value for key, value in plan.items() if key != "plan_sha256"}
    digest = hashlib.sha256(_checkpoint_canonical(body)).hexdigest()
    if digest != plan.get("plan_sha256") or digest != approved_plan_sha256:
        raise OffhostBackupError("PRUNE_EXACT_PLAN_APPROVAL_REQUIRED")
    if not 0 < max_delete_objects <= 64 or not 0 < max_wall_seconds <= 300:
        raise OffhostBackupError("PRUNE_BUDGET_INVALID")
    started = monotonic_clock()
    def invoke(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if monotonic_clock() - started >= max_wall_seconds:
            raise OffhostBackupError("PRUNE_WALL_BUDGET_EXHAUSTED")
        if runner is not None:
            return runner(argv)
        if len(argv) != 5 or argv[3] != "deletefile" or not argv[4].startswith(config.remote_object("")):
            validate_rclone_argv(argv)
        return subprocess.run(list(argv), check=False, capture_output=True, text=True,
            timeout=max(0.001, max_wall_seconds - (monotonic_clock() - started)))

    deleted: list[str] = []
    completed_names: list[str] = []
    try:
        with backup_plane_lock(root, timeout_seconds=0):
            fresh = plan_checkpoint_prune(root, objects=plan["objects"], config=config,
                retained_checkpoint_filenames=plan["retained_checkpoint_filenames"],
                scientific_pins=plan["scientific_pins"], environ=environ,
                restore_proof_artifacts=restore_proof_artifacts)
            if fresh["reference_sha256"] != plan["reference_sha256"] or fresh["missing_references"]:
                raise OffhostBackupError("PRUNE_REFERENCE_CONFLICT")
            bindings = plan.get("restore_proof_artifact_sha256") or {}
            if not bindings or set(bindings) != set(fresh["retained_checkpoint_filenames"]):
                raise OffhostBackupError("PRUNE_RETAINED_RESTORE_PROOF_ARTIFACT_REQUIRED")
            if fresh["restore_proof_artifact_sha256"] != bindings or fresh["plan_sha256"] != digest:
                raise OffhostBackupError("PRUNE_RESTORE_PROOF_ARTIFACT_CONFLICT")
            artifacts = _load_prune_proof_artifacts(restore_proof_artifacts)
            proofs = {name: artifact["payload"] for name, artifact in artifacts.items()}
            if restore_proofs and {proof.get("checkpoint_filename"): proof for proof in restore_proofs} != proofs:
                raise OffhostBackupError("PRUNE_RESTORE_PROOF_ARTIFACT_CONFLICT")
            for name in fresh["retained_checkpoint_filenames"]:
                proof = proofs.get(name) or {}
                if proof.get("terminal") != "REMOTE_CHECKPOINT_RESTORE_VERIFIED":
                    raise OffhostBackupError("PRUNE_RETAINED_RESTORE_PROOF_REQUIRED")
                identities = proof.get("verified_objects") or []
                proven_names = {item["filename"] for item in identities}
                loaded = load_config_v1_1(root)
                sink = resolve_backup_sink(root, loaded, environ if environ is not None else os.environ)
                checkpoint = validate_recovery_checkpoint(sink / name)
                _verify_prune_proof_oracle(artifacts[name], sink / name)
                required = {name, *_referenced_names(checkpoint)}
                extra_names = proven_names - required
                if (not required.issubset(proven_names)
                        or any(not extra.startswith("ARCHIVE_") or not extra.endswith(".zip") for extra in extra_names)
                        or proof.get("checkpoint_sha256") != _sha256_file(sink / name)
                        or proof.get("result_inventory_sha256") != checkpoint["result_inventory_sha256"]):
                    raise OffhostBackupError("PRUNE_RETAINED_RESTORE_PROOF_CONFLICT")
                if (proof.get("restore", {}).get("raw_inventory_sha256") != checkpoint["result_inventory_sha256"]
                        or not proof.get("restore", {}).get("sqlite_integrity")):
                    raise OffhostBackupError("PRUNE_RETAINED_RESTORE_PROOF_CONFLICT")
                expected = {name: _sha256_file(sink / name),
                            **{item["filename"]: item["sha256"] for item in [checkpoint["base_full"], *checkpoint["ordered_deltas"]]}}
                expected.update({extra: extra.removeprefix("ARCHIVE_").removesuffix(".zip") for extra in extra_names})
                for item in identities:
                    if item.get("sha256") != expected[item["filename"]]:
                        raise OffhostBackupError("PRUNE_RETAINED_RESTORE_PROOF_CONFLICT")
                    remote = config.remote_object(_filename(item["filename"]))
                    if _remote_size(config, remote, invoke) != int(item["bytes"]) or _remote_md5(config, remote, invoke) != item["md5"]:
                        raise OffhostBackupError("PRUNE_RETAINED_REMOTE_IDENTITY_CONFLICT")
            for candidate in fresh["removable"]:
                if len(deleted) >= max_delete_objects or monotonic_clock() - started >= max_wall_seconds:
                    break
                name = _filename(candidate)
                remote = config.remote_object(name)
                if _remote_metadata(config, remote, invoke) is None:
                    completed_names.append(name)
                    continue  # repeat of this exact partially applied plan
                # Dedicated approval-gated adapter, deliberately outside the
                # global copy-only command constructor and runner validator.
                argv = [str(config.rclone_bin), "--config", str(config.rclone_config_absolute), "deletefile", remote]
                completed = invoke(argv)
                if completed.returncode != 0 or _remote_metadata(config, remote, invoke) is not None:
                    raise OffhostBackupError("PRUNE_REMOTE_DELETE_UNCONFIRMED")
                deleted.append(name)
                completed_names.append(name)
            return {"status": "COMPLETE" if len(completed_names) == len(fresh["removable"]) else "PROGRESS",
                    "plan_sha256": digest, "deleted": deleted}
    except RemoteOpsError as exc:
        if str(exc) == "PRUNE_WALL_BUDGET_EXHAUSTED":
            return {"status": "YIELD", "reason": "WALL_BUDGET", "deleted": deleted}
        if str(exc) == "WRITER_BUSY":
            return {"status": "YIELD", "reason": "WRITER_BUSY", "deleted": []}
        raise
    except (subprocess.TimeoutExpired, TimeoutError):
        return {"status": "YIELD", "reason": "REMOTE_OUTCOME_UNKNOWN", "deleted": deleted}


def refresh_checkpoint_archive(
    root: Path, checkpoint_receipt: Mapping[str, Any], *, now: datetime,
    runner: RcloneRunner | None = None,
) -> dict[str, Any]:
    """Existing caller's optional, policy-bound independent cold refresh."""
    from solana_alpha_lab.factory.observation_schedule_retention import (
        checkpoint_archive_refresh_intent, checkpoint_archive_refresh_required,
        register_checkpoint_retirement_archive, retirement_raw_archive_dependencies,
    )
    from solana_alpha_lab.factory.observation_schedule_runtime import load_runtime_config
    from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

    decision = checkpoint_archive_refresh_required(root, now=now)
    if decision.get("required") is not True:
        return {"status": "DISABLED", "reason": decision["reason"]}
    budget = decision["budget"]
    cold_relative = str(budget["cold_root_relative"])
    cold_root = (root / cold_relative).resolve()
    loaded = load_config_v1_1(root)
    if not cold_root.is_relative_to(root.resolve()) or cold_root == root.resolve():
        raise OffhostBackupError("ARCHIVE_REFRESH_COLD_ROOT_UNSAFE")
    backup = loaded["backup"]
    sources = [*backup["source_relative_paths"], *backup["recursive_relative_paths"],
               *backup.get("mutable_only_source_relative_paths", []),
               *backup.get("mutable_only_recursive_relative_paths", [])]
    for relative in sources:
        source = (root / relative).resolve()
        if cold_root == source or cold_root.is_relative_to(source):
            raise OffhostBackupError("ARCHIVE_REFRESH_COLD_ROOT_IN_ROUTINE_SOURCE")
    offhost = load_offhost_config(root)
    if offhost is None:
        raise OffhostBackupError("OFFHOST_NOT_CONFIGURED")
    sink = resolve_backup_sink(root, loaded, os.environ)
    pending = decision.get("pending")
    if pending:
        checkpoint_identity = pending
    else:
        name = _filename(checkpoint_receipt["checkpoint_filename"])
        path = sink / name
        checkpoint_identity = {"checkpoint_filename": name, "checkpoint_sha256": _sha256_file(path),
                               "checkpoint": validate_recovery_checkpoint(path)}
    runtime = load_runtime_config(root, "configs/observation_schedule_runtime_v1.yaml")
    store = ObservationScheduleStore(root / runtime["ops_store_relative"])
    try:
        if not pending:
            _, recursive = _effective_backup_lists(root, loaded)
            dependencies = ({"archives": []} if "local/factory_v1/observation_rdp" in recursive
                            else retirement_raw_archive_dependencies(store, source_root=root, now=now))
            checkpoint_identity["supplemental_archives"] = dependencies["archives"]
        intent = checkpoint_archive_refresh_intent(store, checkpoint=checkpoint_identity,
            cold_relative=cold_relative, now=now, source_root=root)
        cache = cold_root / str(intent["checkpoint_sha256"])
        # The small local checkpoint is reconstructed from the exact native
        # intent if a later local full prune removed its original sink copy.
        checkpoint_path = sink / _filename(intent["checkpoint_filename"])
        if not checkpoint_path.is_file():
            encoded = _checkpoint_canonical(intent["checkpoint"])
            if hashlib.sha256(encoded).hexdigest() != intent["checkpoint_sha256"]:
                raise OffhostBackupError("ARCHIVE_REFRESH_PENDING_IDENTITY_CONFLICT")
            checkpoint_path.write_bytes(encoded)
        with backup_plane_lock(root, timeout_seconds=0):
            proof = verify_remote_checkpoint_restore(checkpoint_path=checkpoint_path,
                isolated_root=cache, config=offhost, runner=runner,
                max_objects=int(budget["max_objects"]), max_bytes=int(budget["max_bytes"]),
                max_wall_seconds=float(budget["max_wall_seconds"]),
                supplemental_archives=intent.get("supplemental_archives") or [])
        registered = register_checkpoint_retirement_archive(store, proof=proof,
            isolated_root=cache, source_root=root, now=now)
        return {"status": "REGISTERED", "checkpoint_sha256": intent["checkpoint_sha256"],
                "downloaded_closure_bytes": proof["downloaded_closure_bytes"],
                "staging_final_bytes": proof["staging_final_bytes"],
                "registration_status": registered["status"]}
    finally:
        store.close()


def release_checkpoint_archive_cache(root: Path, *, now: datetime) -> dict[str, Any]:
    """Release only a native source-owned, superseded cache; remote pins stay."""
    from solana_alpha_lab.factory.observation_schedule_retention import (
        acknowledge_checkpoint_archive_cache_release, checkpoint_archive_cache_releasable,
    )
    from solana_alpha_lab.factory.observation_schedule_runtime import load_runtime_config
    from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

    runtime = load_runtime_config(root, "configs/observation_schedule_runtime_v1.yaml")
    path = root / runtime["ops_store_relative"]
    if not path.is_file():
        return {"status": "NONE"}
    with backup_plane_lock(root, timeout_seconds=0):
        store = ObservationScheduleStore(path)
        try:
            decision = checkpoint_archive_cache_releasable(store)
            if decision["status"] != "RELEASABLE":
                return {"status": decision["status"], "reason": decision.get("reason")}
            token = decision["token"]
            raw_target = Path(token["cache_root"])
            target = raw_target.resolve()
            if (target.name != token["checkpoint_sha256"] or not target.is_relative_to(root.resolve())
                    or target == root.resolve() or raw_target.is_symlink()):
                raise OffhostBackupError("CHECKPOINT_CACHE_RELEASE_TARGET_UNSAFE")
            removed_bytes = 0
            if target.exists():
                owned = json.loads((target / ".remote-restore-intent.json").read_text(encoding="utf-8"))
                if owned.get("checkpoint_sha256") != token["checkpoint_sha256"]:
                    raise OffhostBackupError("CHECKPOINT_CACHE_RELEASE_IDENTITY_CONFLICT")
                for candidate in target.rglob("*"):
                    if candidate.is_symlink() or not candidate.resolve().is_relative_to(target):
                        raise OffhostBackupError("CHECKPOINT_CACHE_RELEASE_TARGET_UNSAFE")
                    if candidate.is_file():
                        removed_bytes += candidate.stat().st_size
                # Exact absolute target was checked above; this cache is owned
                # by the matched immutable intent and a native release token.
                shutil.rmtree(target)
            acknowledge_checkpoint_archive_cache_release(store,
                checkpoint_sha256=token["checkpoint_sha256"], now=now)
            return {"status": "RELEASED", "checkpoint_sha256": token["checkpoint_sha256"],
                    "released_local_bytes": removed_bytes}
        finally:
            store.close()


def run_checkpoint_maintenance(
    root: Path, checkpoint_receipt: Mapping[str, Any], *,
    now: datetime, runner: RcloneRunner | None = None,
) -> dict[str, Any]:
    """Run only after the verified backup released its lock; default-off."""
    from solana_alpha_lab.factory.observation_schedule_retention import maintenance_after_checkpoint

    result = maintenance_after_checkpoint(root, now=now)
    if (result.get("status") not in {"COMPLETE", "PROGRESS"}
            and not (result.get("status") == "YIELD" and result.get("reason") == "ARCHIVE_REFRESH_REQUIRED")):
        return result
    released = release_checkpoint_archive_cache(root, now=now)
    if released.get("status") == "WAIT":
        return {**result, "cache_release": released}
    try:
        refresh = refresh_checkpoint_archive(root, checkpoint_receipt, now=now, runner=runner)
        if refresh.get("status") == "REGISTERED":
            result = maintenance_after_checkpoint(root, now=now)
            released = release_checkpoint_archive_cache(root, now=now)
        return {**result, "archive_refresh": refresh, "cache_release": released}
    except Exception:
        from solana_alpha_lab.factory.observation_schedule_retention import record_maintenance_outcome
        from solana_alpha_lab.factory.observation_schedule_runtime import load_runtime_config
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        runtime = load_runtime_config(root, "configs/observation_schedule_runtime_v1.yaml")
        store = ObservationScheduleStore(root / runtime["ops_store_relative"])
        try:
            record_maintenance_outcome(store, state="FAILED", reason="ARCHIVE_REFRESH_FAILED", now=now)
        finally:
            store.close()
        return {"status": "FAILED", "reason": "ARCHIVE_REFRESH_FAILED", "backup_unchanged": True}


def _read_pending(root: Path, config: OffhostConfig) -> dict[str, Any] | None:
    path = _pending_path(root, config)
    if not path.exists():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        operation = body["operation"]
        digest = hashlib.sha256(_checkpoint_canonical(operation)).hexdigest()
        if body.get("schema") != "smial.factory-offhost-pending-operation" or digest != body["operation_sha256"]:
            raise ValueError("identity")
        if not isinstance(operation, dict) or not isinstance(operation["objects"], list):
            raise ValueError("shape")
        _referenced_names(operation)
        return operation
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise OffhostBackupError("OFFHOST_PENDING_OPERATION_CORRUPT") from exc


def _write_pending(root: Path, config: OffhostConfig, operation: Mapping[str, Any]) -> None:
    _atomic_write_json(_pending_path(root, config), {
        "schema": "smial.factory-offhost-pending-operation", "schema_version": "1.0",
        "operation_sha256": hashlib.sha256(_checkpoint_canonical(operation)).hexdigest(),
        "operation": dict(operation),
    })


def _stamp(clock: datetime) -> str:
    return clock.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _prepare_checkpoint_operation(
    *, root: Path, offhost: OffhostConfig, loaded: Mapping[str, Any],
    env: Mapping[str, str], sink: Path, mode: str, clock: datetime,
    deploy_git_sha: str | None, wall_clock: Callable[[], datetime],
) -> dict[str, Any]:
    chain = read_chain_state(root, offhost)
    started_at = _stamp(clock)
    with backup_payload_snapshot(root, loaded) as snapshot:
        scanned = scan_backup_inventory(root, config=loaded, snapshot=snapshot)
        entries = list(scanned["entries"])
        inventory = str(scanned["inventory_sha256"])
        # The clock before the first capture is a conservative lower bound for
        # the multi-store snapshot, including when all bytes are unchanged.
        captured_at = started_at
        base = chain.get("base_full")
        ordered = list(chain.get("ordered_deltas") or [])
        last_weekly = chain.get("last_weekly_date")
        weekly_due = mode == "weekly" or (clock.weekday() == 6 and last_weekly != clock.date().isoformat())
        objects: list[dict[str, Any]] = []
        terminal = "NO_CHANGES_VERIFIED"
        tip_inventory = str(chain.get("tip_inventory_sha256") or "")
        if base is None or (weekly_due and str(base.get("inventory_sha256")) != inventory):
            packed = _reuse_or_package_full(root=root, loaded=loaded, env=env, sink=sink,
                current_inventory=inventory, current_entries=entries, snapshot=snapshot)
            bundle = verify_backup_bundle(sink / str(packed["bundle"]))
            base = {"filename": bundle["filename"], "sha256": bundle["sha256"],
                    "bytes": bundle["bytes"], "inventory_sha256": inventory}
            ordered = []
            objects.append({key: base[key] for key in ("filename", "sha256", "bytes")})
            terminal = "WEEKLY_FULL_VERIFIED"
        elif weekly_due and str(base.get("inventory_sha256")) == inventory:
            # A -> B -> A: the already-verified full is again the result state.
            # Deltas leading to B must not remain reachable from this new point.
            ordered = []
            terminal = "FULL_COVERAGE_RECONFIRMED_NO_CHANGE"
        elif tip_inventory != inventory:
            tip_entries = chain.get("tip_entries")
            if not isinstance(tip_entries, list):
                raise OffhostBackupError("OFFHOST_CHAIN_TIP_INVENTORY_MISSING")
            parent = {"entries": tip_entries, "inventory_sha256": tip_inventory or logical_inventory_sha256(tip_entries)}
            delta = package_delta_backup(root, base_manifest=parent, current_entries=entries,
                sink=sink, acquire_lock=False, snapshot=snapshot)
            # A deletion-only delta changes state and must also be published.
            if delta.get("result_inventory_sha256") != parent["inventory_sha256"]:
                delta_path = Path(delta["path"])
                if _sha256_file(delta_path) != delta["sha256"]:
                    raise OffhostBackupError("OFFHOST_LOCAL_OBJECT_HASH_MISMATCH")
                item = {"filename": delta["bundle"], "sha256": delta["sha256"],
                        "result_inventory_sha256": inventory, "bytes": delta["bytes"]}
                ordered.append(item)
                objects.append({key: item[key] for key in ("filename", "sha256", "bytes")})
                terminal = "DAILY_DELTA_VERIFIED"
        if weekly_due:
            last_weekly = clock.date().isoformat()
        candidate = {"base_full": base, "ordered_deltas": ordered, "last_weekly_date": last_weekly,
                     "tip_entries": entries, "tip_inventory_sha256": inventory}
        checkpoint_body = {
            "schema": CHECKPOINT_SCHEMA, "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "created_at": started_at, "snapshot_data_as_of": captured_at,
            "run_started_at": started_at, "clock_semantics": "SNAPSHOT_DATA_AGE_V2",
            "source_backup_sha256": base["sha256"], "result_inventory_sha256": inventory,
            "base_full": base, "ordered_deltas": ordered, "checkpoint_terminal": terminal,
            "weekly_full_state": "OK", "deploy_git_sha": deploy_git_sha,
        }
        encoded = _checkpoint_canonical(checkpoint_body)
        digest = hashlib.sha256(encoded).hexdigest()
        name = f"RECOVERY_CHECKPOINT_{_utc_compact(clock)}_{digest}.json"
        checkpoint_path = sink / name
        if checkpoint_path.exists() and _sha256_file(checkpoint_path) != digest:
            raise OffhostBackupError("OFFHOST_LOCAL_OBJECT_IDENTITY_CONFLICT")
        staging = sink / ("." + name + ".pending")
        with staging.open("wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if _sha256_file(staging) != digest:
            raise OffhostBackupError("CHECKPOINT_HASH_MISMATCH")
        os.replace(staging, checkpoint_path)
        validate_recovery_checkpoint(checkpoint_path)
        checkpoint = {"filename": name, "sha256": digest, "bytes": len(encoded)}
        candidate["last_checkpoint"] = checkpoint
        for key in ("scientific_pins", "retained_checkpoints"):
            if key in chain:
                candidate[key] = chain[key]
        operation = {"mode": mode, "run_started_at": started_at,
                     "snapshot_data_as_of": captured_at,
                     "packed_local_verified_at": _stamp(wall_clock()),
                     "objects": objects, "checkpoint": checkpoint,
                     "candidate_chain": candidate, "terminal": terminal,
                     "deploy_git_sha": deploy_git_sha}
        _write_pending(root, offhost, operation)
    return operation


def _finish_checkpoint_operation(
    *, root: Path, offhost: OffhostConfig, sink: Path,
    operation: Mapping[str, Any], runner: RcloneRunner,
    wall_clock: Callable[[], datetime], monotonic_clock: Callable[[], float],
    attempt_started_monotonic: float, attempt_started_at: str,
) -> dict[str, Any]:
    objects = list(operation["objects"]) + [operation["checkpoint"]]
    uploaded_at: str | None = None
    for index, item in enumerate(objects):
        name = _filename(item["filename"])
        path = sink / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size != int(item["bytes"]) or _sha256_file(path) != item["sha256"]:
            raise OffhostBackupError("OFFHOST_PENDING_ARTIFACT_INTEGRITY_FAILED")
        copied = _accounted_copy(root=root, config=offhost, runner=runner, clock=wall_clock(),
            local_path=path, remote_object=offhost.remote_object(name), wall_clock=wall_clock)
        if copied["terminal"] == "COPY_FAILED":
            raise OffhostBackupError("CHECKPOINT_COPY_FAILED" if index == len(objects) - 1 else "OFFHOST_COPY_FAILED")
        uploaded_at = copied.get("uploaded_at") or uploaded_at
        _atomic_write_json(_attempt_path(root, offhost), {
            "terminal": "IN_PROGRESS", "run_started_at": operation["run_started_at"],
            "attempt_started_at": attempt_started_at,
            "snapshot_data_as_of": operation["snapshot_data_as_of"],
            "checkpoint_filename": operation["checkpoint"]["filename"],
            "progress": "CHECKPOINT_REMOTE_VERIFIED" if index == len(objects) - 1 else "PAYLOAD_REMOTE_VERIFIED",
            "observed_at": _stamp(wall_clock()),
        })
    verified_at = _stamp(wall_clock())
    candidate = dict(operation["candidate_chain"])
    base = candidate["base_full"]
    checkpoint = operation["checkpoint"]
    receipt = {
        "clock_semantics": "SNAPSHOT_DATA_AGE_V2",
        "snapshot_data_as_of": operation["snapshot_data_as_of"],
        "run_started_at": operation["run_started_at"],
        "attempt_started_at": attempt_started_at,
        "packed_local_verified_at": operation["packed_local_verified_at"],
        "uploaded_at": uploaded_at, "verified_at": verified_at,
        "attempt_duration_seconds": max(0.0, monotonic_clock() - attempt_started_monotonic),
        "source_backup_filename": base["filename"], "source_sha256": base["sha256"],
        "source_bytes": base.get("bytes"), "terminal": operation["terminal"],
        "remote_logical_path": offhost.remote_object(checkpoint["filename"]),
        "remote_bytes": checkpoint["bytes"], "checkpoint_filename": checkpoint["filename"],
        "checkpoint_sha256": checkpoint["sha256"], "weekly_full_state": "OK",
        "verification": "REMOTE_MD5_AND_SIZE_LOCAL_SHA256",
        "verification_scope": "NEW_PAYLOADS_AND_CHECKPOINT_PRIOR_CHAIN_BOUND",
        "upload_completion_status": "OBSERVED" if uploaded_at else "UNKNOWN_ALREADY_PRESENT_RECONCILED",
        "deploy_git_sha": operation.get("deploy_git_sha"),
    }
    # Every remote object is proven before either local last-good changes.
    # Pending survives an interruption between pointer and receipt writes.
    candidate["last_good_receipt"] = receipt
    write_chain_state(root, offhost, candidate)
    write_offhost_receipt(root, offhost, receipt)
    _pending_path(root, offhost).unlink()
    return receipt


def run_offhost_checkpoint(
    root: Path, *, mode: str, deploy_git_sha: str | None = None,
    config: OffhostConfig | None = None, environ: Mapping[str, str] | None = None,
    runner: RcloneRunner | None = None, now: datetime | None = None,
    wall_clock: Callable[[], datetime] | None = None,
    monotonic_clock: Callable[[], float] = time.monotonic,
    lock_timeout_seconds: float = 0.0,
) -> dict[str, Any]:
    if mode not in {"daily", "weekly"}:
        raise OffhostBackupError("CHECKPOINT_MODE_INVALID")
    actual_clock = wall_clock or (lambda: now if now is not None else datetime.now(UTC))
    attempt_started_monotonic = monotonic_clock()
    clock = actual_clock()
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
    operation: Mapping[str, Any] | None = None
    try:
        with backup_plane_lock(root, timeout_seconds=lock_timeout_seconds):
            read_chain_state(root, offhost)
            operation = _read_pending(root, offhost)
            if operation is None:
                operation = _prepare_checkpoint_operation(root=root, offhost=offhost,
                    loaded=loaded, env=env, sink=sink, mode=mode, clock=clock,
                    deploy_git_sha=deploy_git_sha, wall_clock=actual_clock)
            _atomic_write_json(_attempt_path(root, offhost), {
                "terminal": "IN_PROGRESS", "run_started_at": operation["run_started_at"],
                "attempt_started_at": _stamp(clock), "progress": "PACKED_LOCAL_VERIFIED",
                "snapshot_data_as_of": operation["snapshot_data_as_of"],
                "checkpoint_filename": operation["checkpoint"]["filename"],
            })
            return _finish_checkpoint_operation(root=root, offhost=offhost, sink=sink,
                operation=operation, runner=invoke, wall_clock=actual_clock,
                monotonic_clock=monotonic_clock, attempt_started_monotonic=attempt_started_monotonic,
                attempt_started_at=_stamp(clock))
    except RemoteOpsError as exc:
        if str(exc) == "WRITER_BUSY":
            return {"terminal": "DEFERRED", "reason": "WRITER_BUSY"}
        write_offhost_receipt(root, offhost, {
            "terminal": "COPY_FAILED", "failed_at": _stamp(actual_clock()),
            "failure_code": str(exc).split(":", 1)[0], "deploy_git_sha": deploy_git_sha,
            "snapshot_data_as_of": operation.get("snapshot_data_as_of") if operation else None,
            "checkpoint_filename": operation["checkpoint"]["filename"] if operation else None,
        })
        raise
    except (subprocess.TimeoutExpired, TimeoutError, OSError) as exc:
        write_offhost_receipt(root, offhost, {
            "terminal": "COPY_FAILED", "failed_at": _stamp(actual_clock()),
            "failure_code": "OFFHOST_TRANSPORT_OUTCOME_UNKNOWN", "deploy_git_sha": deploy_git_sha,
            "snapshot_data_as_of": operation.get("snapshot_data_as_of") if operation else None,
            "checkpoint_filename": operation["checkpoint"]["filename"] if operation else None,
        })
        raise OffhostBackupError("OFFHOST_TRANSPORT_OUTCOME_UNKNOWN") from exc

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
    "plan_backup_prune",
    "plan_checkpoint_prune",
    "apply_remote_backup_prune",
    "publish_recovery_checkpoint",
    "read_offhost_receipt",
    "read_offhost_attempt",
    "rclone_config_metadata",
    "restore_incremental_chain_isolated",
    "restore_from_recovery_checkpoint",
    "run_offhost_checkpoint",
    "refresh_checkpoint_archive",
    "release_checkpoint_archive_cache",
    "run_checkpoint_maintenance",
    "validate_rclone_argv",
    "validate_recovery_checkpoint",
    "verify_backup_bundle",
    "verify_remote_checkpoint_restore",
    "write_offhost_receipt",
]
