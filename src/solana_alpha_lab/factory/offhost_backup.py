"""Stage-2 off-host durability: copy-only Google Drive mirror of local backups.

Never deletes remote objects. Never reads or stores OAuth tokens. Local
factory-remote-backup remains stage 1 and canonical first-stage durability.
"""

from __future__ import annotations

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
    load_config_v1_1,
    resolve_backup_sink,
)

RECEIPT_SCHEMA = "smial.factory-offhost-backup-receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
DEFAULT_RCLONE_BIN = "/usr/bin/rclone"
OFFHOST_REMOTE = "GOOGLE_DRIVE"
SUCCESS_TERMINALS = frozenset({"COPIED_VERIFIED", "ALREADY_PRESENT_VERIFIED"})
FAILURE_TERMINALS = frozenset({"COPY_FAILED", "REMOTE_IDENTITY_CONFLICT", "SOURCE_INTEGRITY_FAILED"})
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
        return "UNCONFIGURED"
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
            "trigger": "factory-remote-backup.service OnSuccess=factory-remote-backup-gdrive.service",
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
            "is_scientific_truth": False,
            "is_factory_backup_sink": False,
            "google_drive_role": "PROVEN_OFFHOST_DURABILITY",
            "google_drive_role_prior": "OPTIONAL_COLD_COPY_NOT_DOD",
            "unproven_follow_up": "NONEMPTY_RDP_OFFHOST_RESTORE_PROOF",
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
            "module": "solana_alpha_lab.factory.remote_ops.restore_backup_isolated",
            "requires_isolated_dest_root": True,
            "never_replaces_live_sqlite_or_rdp": True,
            "note": "Download bundle to isolated temp path first; never restore into /opt/solana-alpha-lab/local/factory_v1 live stores.",
        },
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


__all__ = [
    "ALLOWED_RCLONE_SUBCOMMANDS",
    "FORBIDDEN_RCLONE_SUBCOMMANDS",
    "OffhostBackupError",
    "OffhostConfig",
    "agent_durability_classification",
    "build_rclone_argv",
    "classify_offhost_state",
    "copy_offhost_backup",
    "default_rclone_runner",
    "load_offhost_config",
    "offhost_health_snapshot",
    "offhost_recovery_readout",
    "read_offhost_receipt",
    "rclone_config_metadata",
    "validate_rclone_argv",
    "verify_backup_bundle",
    "write_offhost_receipt",
]
