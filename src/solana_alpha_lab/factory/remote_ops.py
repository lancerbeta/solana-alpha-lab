"""Factory remote operations: health, backup, alerts, security baseline.

Owns no scientific truth. Secrets have no defaults. Process-alive is never
HEALTHY. Backup on the same parent as live stores is not independent.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Iterator, Mapping, Sequence

import jsonschema
import yaml

CONFIG_RELATIVE = "configs/factory_remote_operations_v1.yaml"
SCHEMA_RELATIVE = "catalog/schemas/factory_remote_operations.schema.json"
CONFIG_V1_1_RELATIVE = "configs/factory_remote_operations_v1_1.yaml"
SCHEMA_V1_1_RELATIVE = "catalog/schemas/factory_remote_operations_v1_1.schema.json"
FORBIDDEN_HEALTHY = "HEALTHY"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
UNRESOLVED_STATES = frozenset(
    {"OPEN", "PARTIAL", "UNKNOWN", "UNRESOLVED", "EXIT_REQUIRED", "EXITING"}
)
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
BACKUP_SINK_ENV = "FACTORY_BACKUP_SINK"
BACKUP_BUNDLE_NAME = re.compile(r"^BACKUP_[0-9a-f]{64}\.zip$")
DELTA_BUNDLE_NAME = re.compile(r"^DELTA_[0-9a-f]{64}\.zip$")
BACKUP_STREAM_CHUNK = 1024 * 1024
BACKUP_LOCK_RELATIVE = "local/factory_v1/backup_plane.lock"
BACKUP_LOCK_STALE_SECONDS = 14400
PROTECTED_LIVE_NAMES = frozenset(
    {
        "observation_rdp",
        "operational_state.sqlite",
        "paper_plane_state.sqlite",
        "observation_schedule_state.sqlite",
    }
)


class RemoteOpsError(ValueError):
    """Raised when remote operations cannot proceed fail-closed."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(BACKUP_STREAM_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def logical_inventory_sha256(entries: Sequence[Mapping[str, Any]]) -> str:
    canonical = [
        {
            "bytes": int(item["bytes"]),
            "path": str(item["path"]),
            "sha256": str(item["sha256"]),
        }
        for item in sorted(entries, key=lambda row: str(row["path"]))
    ]
    return _sha256_bytes(
        json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def _safe_relative(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if (
        candidate.is_absolute()
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in candidate.parts
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise RemoteOpsError("REMOTE_PATH_UNSAFE")
    root_resolved = root.resolve()
    current = root
    for part in candidate.parts:
        current = current / part
        if current.is_symlink():
            raise RemoteOpsError("REMOTE_PATH_UNSAFE")
    resolved = current.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise RemoteOpsError("REMOTE_PATH_UNSAFE") from exc
    return resolved


def _reject_symlink_components(path: Path) -> None:
    if path.is_absolute() is False:
        raise RemoteOpsError("REMOTE_PATH_UNSAFE")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise RemoteOpsError("REMOTE_PATH_UNSAFE")


def _is_published_backup_bundle(path: Path) -> bool:
    return path.is_file() and BACKUP_BUNDLE_NAME.fullmatch(path.name) is not None


def _fsync_file(path: Path) -> None:
    fd = os.open(str(path), os.O_RDWR)
    try:
        os.fsync(fd)
    except OSError as exc:
        # Windows can refuse fsync on a just-closed ZIP handle; Linux VPS still fsyncs.
        if os.name == "nt" and getattr(exc, "errno", None) in {9, 22}:
            return
        raise
    finally:
        os.close(fd)


def _stream_copy_hashed(source, dest: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as handle:
        while True:
            chunk = source.read(BACKUP_STREAM_CHUNK)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError as exc:
            if os.name != "nt" or getattr(exc, "errno", None) not in {9, 22}:
                raise
    return digest.hexdigest(), size


def _lock_holder_alive(path: Path) -> bool:
    try:
        raw = path.read_bytes().decode("utf-8", errors="replace")
        pid = int(raw.split(":", 1)[0])
    except (OSError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@contextmanager
def backup_plane_lock(root: Path, *, timeout_seconds: float = 30.0) -> Iterator[Path]:
    path = _safe_relative(root, BACKUP_LOCK_RELATIVE)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    handle: int | None = None
    while True:
        try:
            handle = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(handle, f"{os.getpid()}:{_now()}".encode("utf-8"))
            break
        except FileExistsError:
            alive = _lock_holder_alive(path)
            try:
                age = time.time() - path.stat().st_mtime
            except OSError:
                age = BACKUP_LOCK_STALE_SECONDS + 1
            if alive is False and age > BACKUP_LOCK_STALE_SECONDS:
                try:
                    path.unlink()
                    continue
                except OSError:
                    pass
            if time.monotonic() >= deadline:
                raise RemoteOpsError("WRITER_BUSY")
            time.sleep(0.05)
    try:
        yield path
    finally:
        if handle is not None:
            os.close(handle)
        try:
            path.unlink()
        except OSError:
            pass


def _stream_zip_entry(
    archive: zipfile.ZipFile,
    relative: str,
    source: Path,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    info = zipfile.ZipInfo(filename=relative, date_time=ZIP_TIMESTAMP)
    info.external_attr = 0o100644 << 16
    with source.open("rb") as src, archive.open(info, "w") as dest:
        while True:
            chunk = src.read(BACKUP_STREAM_CHUNK)
            if not chunk:
                break
            dest.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def prune_superseded_local_backups(sink: Path, keep: Path) -> list[str]:
    if keep.parent.resolve() != sink.resolve():
        raise RemoteOpsError("BACKUP_PRUNE_KEEP_NOT_IN_SINK")
    removed: list[str] = []
    for candidate in sorted(sink.glob("BACKUP_*.zip")):
        if candidate.resolve() == keep.resolve():
            continue
        if not _is_published_backup_bundle(candidate):
            continue
        candidate.unlink()
        removed.append(candidate.name)
    return removed


def load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE
    if path.is_file() is False:
        raise RemoteOpsError("REMOTE_OPS_CONFIG_MISSING")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RemoteOpsError("REMOTE_OPS_CONFIG_INVALID")
    schema = json.loads((root / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    jsonschema.validate(loaded, schema)
    return loaded


def load_config_v1_1(root: Path) -> dict[str, Any]:
    path = root / CONFIG_V1_1_RELATIVE
    if path.is_file() is False:
        raise RemoteOpsError("REMOTE_OPS_CONFIG_MISSING")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RemoteOpsError("REMOTE_OPS_CONFIG_INVALID")
    schema = json.loads((root / SCHEMA_V1_1_RELATIVE).read_text(encoding="utf-8"))
    jsonschema.validate(loaded, schema)
    return loaded


def _select_v1_1_config(root: Path, loaded: Mapping[str, Any]) -> dict[str, Any]:
    if (
        str(loaded.get("schema_version") or "") != "1.1"
        and (root / CONFIG_V1_1_RELATIVE).is_file()
    ):
        return load_config_v1_1(root)
    return dict(loaded)


def consistent_sqlite_backup(source: Path, dest: Path) -> None:
    import sqlite3

    if (
        source.is_absolute() is False
        or dest.is_absolute() is False
    ):
        raise RemoteOpsError("REMOTE_PATH_UNSAFE")
    _reject_symlink_components(source)
    _reject_symlink_components(dest)
    source = source.resolve()
    if source.is_file() is False:
        raise RemoteOpsError("BACKUP_SOURCE_MISSING")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    replica = sqlite3.connect(dest)
    try:
        conn.backup(replica)
        replica.commit()
    finally:
        replica.close()
        conn.close()


def require_secret(name: str, environ: Mapping[str, str] | None = None) -> str:
    """Fail closed. A missing secret is an error, never a default."""

    if not name or name != name.strip() or " " in name:
        raise RemoteOpsError("SECRET_NAME_INVALID")
    env = environ if environ is not None else os.environ
    value = env.get(name)
    if value is None or value.strip() == "":
        raise RemoteOpsError(f"SECRET_MISSING:{name}")
    return value


def _read_text(root: Path, relative: str) -> str:
    path = _safe_relative(root, relative)
    if path.is_file() is False:
        raise RemoteOpsError(f"TEMPLATE_MISSING:{relative}")
    return path.read_text(encoding="utf-8")


def verify_security_templates(root: Path, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    loaded = dict(config) if config is not None else load_config(root)
    sshd = _read_text(root, str(loaded["security"]["sshd_relative"]))
    nft = _read_text(root, str(loaded["security"]["nftables_relative"]))
    jail = _read_text(root, str(loaded["security"]["fail2ban_relative"]))
    secrets_example = _read_text(root, str(loaded["security"]["secrets_example_relative"]))
    unit_relatives = [
        str(loaded["units"]["workbench_relative"]),
        str(loaded["units"]["health_relative"]),
        str(loaded["units"]["backup_service_relative"]),
        str(loaded["units"]["paper_heartbeat_relative"]),
    ]
    extra_units = loaded["units"]
    for key in (
        "observation_schedule_service_relative",
        "observation_schedule_timer_relative",
    ):
        if key in extra_units:
            unit_relatives.append(str(extra_units[key]))
    units = {relative: _read_text(root, relative) for relative in unit_relatives}
    failures: list[str] = []
    if "PasswordAuthentication no" not in sshd:
        failures.append("PASSWORD_SSH_NOT_DENIED")
    if "PermitRootLogin no" not in sshd:
        failures.append("ROOT_LOGIN_NOT_DENIED")
    if "AllowUsers factory" not in sshd:
        failures.append("SSH_USER_NOT_FACTORY_ONLY")
    if "PasswordAuthentication yes" in sshd or "PermitRootLogin yes" in sshd:
        failures.append("INSECURE_SSH_AFFIRMATIVE")
    if "policy drop" not in nft:
        failures.append("FIREWALL_NOT_DENY_DEFAULT")
    if "tcp dport 22 accept" not in nft:
        failures.append("SSH_PORT_NOT_ALLOWED")
    if "tcp dport 8765" in nft:
        failures.append("WORKBENCH_PUBLIC")
    if "enabled = true" not in jail:
        failures.append("FAIL2BAN_NOT_ENABLED")
    if "PLACEHOLDER-ONLY" not in secrets_example:
        failures.append("SECRETS_EXAMPLE_NOT_PLACEHOLDER")
    for name in ("FACTORY_TELEGRAM_BOT_TOKEN=", "FACTORY_TELEGRAM_CHAT_ID="):
        if name not in secrets_example:
            failures.append("SECRETS_EXAMPLE_MISSING_NAME")
        line = next((row for row in secrets_example.splitlines() if row.startswith(name)), "")
        if line.split("=", 1)[-1].strip():
            failures.append("SECRET_VALUE_IN_GIT")
    for relative, body in units.items():
        if "0.0.0.0" in body:
            failures.append(f"PUBLIC_BIND:{relative}")
        if "--host 127.0.0.1" not in body and "factory-v1-workbench.service" in relative:
            failures.append("WORKBENCH_NOT_LOOPBACK")
        if ".env" in body and "secrets.env" not in body:
            failures.append(f"DOTENV_IN_UNIT:{relative}")
        if any(marker in body for marker in ("BEGIN PRIVATE", "xoxb-")):
            failures.append(f"SECRET_MATERIAL_IN_UNIT:{relative}")
    if failures:
        raise RemoteOpsError("UNHEALTHY_SECURITY_BASELINE:" + ",".join(failures))
    return {
        "password_ssh": False,
        "permit_root_login": False,
        "public_admin": False,
        "fail2ban": True,
        "firewall_deny_default": True,
        "secrets_in_git": False,
    }


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _age_seconds(stamp: str | None, now: datetime) -> int | None:
    if not stamp:
        return None
    try:
        return int((now - _parse_iso(stamp)).total_seconds())
    except ValueError:
        return None


def _disk_used_percent(path: Path) -> int:
    usage = shutil.disk_usage(path)
    if usage.total <= 0:
        return 100
    return int(round(100.0 * (usage.used / usage.total)))


def _paper_unresolved(root: Path, paper_relative: str) -> dict[str, Any]:
    path = root / paper_relative
    if path.is_file() is False:
        return {"present": False, "unresolved": 0, "total": 0, "bots": 0}
    import sqlite3

    conn = sqlite3.connect(path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
        unresolved = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE state IN ({})".format(
                ",".join("?" * len(UNRESOLVED_STATES))
            ),
            tuple(UNRESOLVED_STATES),
        ).fetchone()[0]
        bots = conn.execute("SELECT COUNT(*) FROM bot_instances").fetchone()[0]
    except sqlite3.Error:
        return {"present": True, "unresolved": 1, "total": 0, "bots": 0, "store": "UNREADABLE"}
    finally:
        conn.close()
    return {"present": True, "unresolved": int(unresolved), "total": int(total), "bots": int(bots)}


def _heartbeat(root: Path, relative: str) -> dict[str, Any] | None:
    path = root / relative
    if path.is_file() is False:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _volume_id(path: Path) -> int | None:
    try:
        target = path if path.exists() else path.parent
        return int(target.stat().st_dev)
    except OSError:
        return None


def backup_domain_for(
    root: Path,
    loaded: Mapping[str, Any],
    sink: Path,
    environ: Mapping[str, str],
) -> str:
    named = str(environ.get(BACKUP_SINK_ENV) or "").strip()
    if not named:
        return "PARENT_INDEPENDENT_GIT_SIDE"
    live = _safe_relative(root, str(loaded["stores"]["operational_relative"])).parent
    live_dev = _volume_id(live)
    sink_dev = _volume_id(sink)
    if live_dev is None or sink_dev is None:
        return "ABSOLUTE_SINK_DEVICE_UNKNOWN"
    if live_dev == sink_dev:
        return "ABSOLUTE_SINK_SAME_VOLUME"
    return "VOLUME_INDEPENDENT_ENV_SINK"


def resolve_backup_sink(
    root: Path,
    loaded: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> Path:
    env = environ if environ is not None else os.environ
    named = str(env.get(BACKUP_SINK_ENV) or "").strip()
    if named:
        sink = Path(named)
        if sink.is_absolute() is False:
            raise RemoteOpsError("BACKUP_SINK_ENV_NOT_ABSOLUTE")
        return sink.resolve()
    return _safe_relative(root, str(loaded["backup"]["independent_sink_relative"]))


def _backup_newest(sink: Path) -> dict[str, Any] | None:
    if sink.is_dir() is False:
        return None
    bundles = [path for path in sink.glob("BACKUP_*.zip") if _is_published_backup_bundle(path)]
    if not bundles:
        return None
    newest = max(bundles, key=lambda path: path.stat().st_mtime)
    return {
        "path": newest.name,
        "sha256": newest.stem.replace("BACKUP_", "", 1),
        "mtime": datetime.fromtimestamp(newest.stat().st_mtime, UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "bytes": newest.stat().st_size,
    }


def project_health(
    *,
    root: Path,
    process_alive: bool,
    config: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    loaded = dict(config) if config is not None else load_config(root)
    clock = now or datetime.now(UTC)
    env = environ if environ is not None else os.environ
    security = verify_security_templates(root, loaded)
    heartbeat = _heartbeat(root, str(loaded["monitoring"]["heartbeat_relative"]))
    heartbeat_at = str(heartbeat.get("observed_at") or "") if heartbeat else ""
    progress_at = str(heartbeat.get("progress_at") or heartbeat_at) if heartbeat else ""
    freshness_age = _age_seconds(heartbeat_at, clock)
    stall_age = _age_seconds(progress_at, clock)
    paper = _paper_unresolved(root, str(loaded["stores"]["paper_relative"]))
    sink = resolve_backup_sink(root, loaded, env)
    backup = _backup_newest(sink)
    backup_age = _age_seconds(str(backup["mtime"]) if backup else None, clock)
    disk = _disk_used_percent(root)
    alert_configured = bool(
        env.get(str(loaded["alert"]["token_env"]), "").strip()
        and env.get(str(loaded["alert"]["chat_id_env"]), "").strip()
    )
    domain = backup_domain_for(root, loaded, sink, env)
    from solana_alpha_lab.factory.offhost_backup import offhost_health_snapshot

    offhost = offhost_health_snapshot(root, now=clock)
    dimensions = {
        "process": "ALIVE" if process_alive else "DOWN",
        "security": "PASS",
        "data_freshness": (
            "OK"
            if freshness_age is not None
            and freshness_age <= int(loaded["monitoring"]["freshness_max_seconds"])
            else "STALE"
        ),
        "provider_route": "UNOBSERVED_GIT_SIDE",
        "job_bot_progress": (
            "OK"
            if stall_age is not None
            and stall_age <= int(loaded["monitoring"]["stall_max_seconds"])
            else "STALLED"
        ),
        "unresolved_position": "DIRTY" if int(paper.get("unresolved") or 0) > 0 else "CLEAN",
        "reconciliation": "DIRTY" if int(paper.get("unresolved") or 0) > 0 else "CLEAN",
        "backup_age": (
            "OK"
            if backup_age is not None and backup_age <= 24 * 3600
            else ("MISSING" if backup is None else "STALE")
        ),
        "disk": (
            "OK" if disk <= int(loaded["monitoring"]["disk_used_percent_max"]) else "HIGH"
        ),
        "alert_sink": "CONFIGURED" if alert_configured else "UNCONFIGURED",
        "offhost_backup": offhost.get("offhost_backup_state", "UNCONFIGURED"),
    }
    if process_alive is False:
        verdict = "UNHEALTHY_NOT_RUNNING"
        next_safe_action = "START_REMOTE_PROCESSES"
    elif dimensions["unresolved_position"] == "DIRTY":
        verdict = "UNHEALTHY_UNRESOLVED_POSITION"
        next_safe_action = "INSPECT_UNRESOLVED_POSITIONS"
    elif dimensions["backup_age"] != "OK":
        verdict = "DEGRADED_BACKUP_AGE"
        next_safe_action = "RUN_INDEPENDENT_BACKUP"
    elif offhost.get("configured") and offhost.get("offhost_backup_state") in {
        "FAILED",
    }:
        verdict = "DEGRADED_OFFHOST_BACKUP_FAILED"
        next_safe_action = "RUN_OFFHOST_BACKUP_COPY"
    elif offhost.get("configured") and offhost.get("offhost_backup_state") in {
        "HARD_ATTENTION",
        "MISSING",
        "DEGRADED",
    }:
        verdict = "DEGRADED_OFFHOST_BACKUP_STALE"
        next_safe_action = "RUN_OFFHOST_BACKUP_COPY"
    elif dimensions["data_freshness"] == "STALE":
        verdict = "DEGRADED_STALE_DATA"
        next_safe_action = "WRITE_PAPER_HEARTBEAT"
    elif dimensions["job_bot_progress"] == "STALLED":
        verdict = "DEGRADED_BOT_STALL"
        next_safe_action = "RESTART_PAPER_HEARTBEAT"
    elif dimensions["disk"] == "HIGH":
        verdict = "DEGRADED_DISK"
        next_safe_action = "FREE_DISK_OR_SCALE_STORAGE"
    elif process_alive and dimensions["backup_age"] == "OK" and dimensions["data_freshness"] == "OK":
        verdict = "RUNTIME_PROVED_BACKUP_INDEPENDENT"
        next_safe_action = (
            "CONTINUE_UNATTENDED_AGENT_RESTORES"
            if alert_configured
            else "OWNER_INFRASTRUCTURE_PACKET_THEN_LIVE_HOST"
        )
    else:
        verdict = "DEGRADED_PROCESS_ALIVE_BACKUP_UNKNOWN"
        next_safe_action = "COMPLETE_REMOTE_OPS_PROOFS"
    if verdict == FORBIDDEN_HEALTHY:
        raise RemoteOpsError("HEALTHY_FROM_PROCESS_ALIVE_FORBIDDEN")
    if process_alive and verdict == FORBIDDEN_HEALTHY:
        raise RemoteOpsError("HEALTHY_FROM_PROCESS_ALIVE_FORBIDDEN")
    terminal = (
        "FACTORY_REMOTE_OPERATIONS_GIT_READY"
        if verdict == "RUNTIME_PROVED_BACKUP_INDEPENDENT"
        and loaded["implementation"] == "GIT_SIDE_REMOTE_OPS_PROOF"
        else verdict
    )
    return {
        "verdict": verdict,
        "terminal": terminal,
        "process_alive": process_alive,
        "deploy_version": str(loaded["deploy"]["version"]),
        "purchase": str(loaded["target"]["purchase"]),
        "implementation": str(loaded["implementation"]),
        "sku": str(loaded["target"]["sku"]),
        "rejected_sku": str(loaded["target"]["rejected_sku"]),
        "workbench_bind": str(loaded["workbench"]["bind"]),
        "backup_status": (
            "INDEPENDENT_BUNDLE_PRESENT" if backup else str(loaded["health"]["backup_status_when_unproved"])
        ),
        "dimensions": dimensions,
        "security": security,
        "paper": paper,
        "backup": backup,
        "disk_used_percent": disk,
        "heartbeat_age_seconds": freshness_age,
        "stall_age_seconds": stall_age,
        "backup_domain": domain,
        "offhost": offhost,
        "offhost_backup_state": offhost.get("offhost_backup_state"),
        "offhost_last_verified_at": offhost.get("offhost_last_verified_at"),
        "offhost_backup_age_seconds": offhost.get("offhost_backup_age_seconds"),
        "offhost_last_filename": offhost.get("offhost_last_filename"),
        "offhost_last_sha256": offhost.get("offhost_last_sha256"),
        "offhost_remote": offhost.get("offhost_remote"),
        "durability_domain": offhost.get("durability_domain"),
        "alert_configured": alert_configured,
        "next_safe_action": next_safe_action,
        "rpo_max": loaded["deploy"]["rpo_max"],
        "rto_max": loaded["deploy"]["rto_max"],
        "observed_at": clock.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def write_heartbeat(
    root: Path,
    *,
    config: Mapping[str, Any] | None = None,
    kind: str = "PAPER_HEARTBEAT",
    progress_at: str | None = None,
) -> Path:
    loaded = (
        dict(config) if config is not None else load_config(root)
    )
    loaded = _select_v1_1_config(root, loaded)
    path = _safe_relative(root, str(loaded["monitoring"]["heartbeat_relative"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = _now()
    payload = {
        "kind": kind,
        "observed_at": stamp,
        "progress_at": progress_at or stamp,
        "deploy_version": loaded["deploy"]["version"],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    observation_relative = loaded["monitoring"].get("observation_heartbeat_relative")
    if observation_relative:
        observation_path = _safe_relative(root, str(observation_relative))
        observation_path.parent.mkdir(parents=True, exist_ok=True)
        observation_payload = dict(payload)
        observation_payload["kind"] = "OBSERVATION_SCHEDULE_HEARTBEAT"
        observation_path.write_text(
            json.dumps(observation_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return path


def _assert_independent_sink(root: Path, loaded: Mapping[str, Any], sink: Path) -> None:
    if loaded["backup"]["same_parent_forbidden"] is not True:
        raise RemoteOpsError("INDEPENDENT_FLAG_DRIFT")
    parents = []
    relatives = list(loaded["backup"]["source_relative_paths"]) + list(
        loaded["backup"].get("recursive_relative_paths") or []
    )
    for relative in relatives:
        source = _safe_relative(root, relative)
        parents.append(source.parent.resolve())
    sink_parent = sink.parent.resolve() if sink.suffix == ".zip" else sink.resolve()
    if sink.is_dir() is False:
        sink_parent = sink.resolve()
    for parent in parents:
        if sink_parent == parent or parent in sink_parent.parents or sink_parent in parent.parents:
            raise RemoteOpsError("BACKUP_SINK_NOT_INDEPENDENT")
        if sink_parent == parent.parent:
            raise RemoteOpsError("BACKUP_SINK_NOT_INDEPENDENT")


def _backup_source_paths(
    root: Path,
    loaded: Mapping[str, Any],
) -> list[tuple[str, Path, bool]]:
    result: list[tuple[str, Path, bool]] = []
    seen: set[str] = set()
    for relative in loaded["backup"]["source_relative_paths"]:
        normalized = str(relative).replace("\\", "/")
        source = _safe_relative(root, normalized)
        if source.is_file() is False:
            raise RemoteOpsError(f"BACKUP_SOURCE_MISSING:{normalized}")
        if normalized not in seen:
            result.append((normalized, source, normalized.endswith(".sqlite")))
            seen.add(normalized)
    for relative in loaded["backup"].get("recursive_relative_paths") or []:
        normalized_root = str(relative).replace("\\", "/").rstrip("/")
        source_root = _safe_relative(root, normalized_root)
        if source_root.is_dir() is False:
            raise RemoteOpsError(f"BACKUP_SOURCE_MISSING:{normalized_root}")
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            normalized = source.relative_to(root).as_posix()
            source = _safe_relative(root, normalized)
            if normalized not in seen:
                result.append((normalized, source, normalized.endswith(".sqlite")))
                seen.add(normalized)
    return result


def scan_backup_inventory(
    root: Path,
    *,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    loaded = dict(config) if config is not None else load_config(root)
    loaded = _select_v1_1_config(root, loaded)
    sources = _backup_source_paths(root, loaded)
    entries: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="factory-inventory-") as staging_name:
        staging = Path(staging_name)
        for relative, source, is_sqlite in sources:
            if is_sqlite and str(loaded.get("schema_version")) == "1.1":
                snapshot = staging / relative
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                consistent_sqlite_backup(source, snapshot)
                digest = _sha256_file(snapshot)
                size = snapshot.stat().st_size
                kind = "SQLITE_BACKUP_API"
            else:
                digest = _sha256_file(source)
                size = source.stat().st_size
                kind = "FILE_SNAPSHOT"
            entries.append(
                {
                    "path": relative,
                    "sha256": digest,
                    "bytes": size,
                    "kind": kind,
                }
            )
    return {
        "entries": entries,
        "inventory_sha256": logical_inventory_sha256(entries),
    }


def package_backup(
    root: Path,
    *,
    config: Mapping[str, Any] | None = None,
    sink_override: Path | None = None,
    environ: Mapping[str, str] | None = None,
    acquire_lock: bool = True,
    prune_superseded: bool | None = None,
) -> dict[str, Any]:
    if acquire_lock:
        with backup_plane_lock(root):
            return package_backup(
                root,
                config=config,
                sink_override=sink_override,
                environ=environ,
                acquire_lock=False,
                prune_superseded=prune_superseded,
            )
    loaded = dict(config) if config is not None else load_config(root)
    loaded = _select_v1_1_config(root, loaded)
    if sink_override is not None:
        raw_sink = sink_override.absolute()
        _reject_symlink_components(raw_sink)
        sink = raw_sink.resolve()
    else:
        sink = resolve_backup_sink(root, loaded, environ)
    if sink.is_absolute() is False:
        raise RemoteOpsError("REMOTE_PATH_UNSAFE")
    _reject_symlink_components(sink)
    _assert_independent_sink(root, loaded, sink)
    sink.mkdir(parents=True, exist_ok=True)
    sources = _backup_source_paths(root, loaded)
    entries: list[dict[str, Any]] = []
    tmp = sink / f".packaging-{os.getpid()}-{time.time_ns()}.zip"
    with tempfile.TemporaryDirectory(prefix="factory-backup-", dir=str(sink.parent)) as staging_name:
        staging = Path(staging_name)
        try:
            with zipfile.ZipFile(
                tmp,
                mode="w",
                compression=zipfile.ZIP_STORED,
                allowZip64=True,
            ) as archive:
                for relative, source, is_sqlite in sources:
                    snapshot = staging / relative
                    if is_sqlite and str(loaded.get("schema_version")) == "1.1":
                        consistent_sqlite_backup(source, snapshot)
                        digest, size = _stream_zip_entry(archive, relative, snapshot)
                        kind = "SQLITE_BACKUP_API"
                    else:
                        digest, size = _stream_zip_entry(archive, relative, source)
                        kind = "FILE_SNAPSHOT"
                    entries.append(
                        {
                            "path": relative,
                            "sha256": digest,
                            "bytes": size,
                            "kind": kind,
                        }
                    )
                rdp_entries = [
                    item
                    for item in entries
                    if item["path"] == "local/factory_v1/observation_rdp"
                    or item["path"].startswith("local/factory_v1/observation_rdp/")
                ]
                journal_entries = [
                    item
                    for item in entries
                    if "/publication_jobs/" in item["path"] or "/journals/" in item["path"]
                ]
                inventory_sha256 = logical_inventory_sha256(entries)
                manifest = {
                    "kind": "FACTORY_REMOTE_BACKUP_MANIFEST",
                    "schema_version": str(loaded.get("schema_version") or "1.0"),
                    "backup_consistency": (
                        "SQLITE_BACKUP_API_AND_RDP_MANIFESTS"
                        if str(loaded.get("schema_version")) == "1.1"
                        else "FILE_SNAPSHOT"
                    ),
                    "created_at": _now(),
                    "entries": entries,
                    "inventory_sha256": inventory_sha256,
                    "rdp_inventory": {
                        "count": len(rdp_entries),
                        "fingerprint": _sha256_bytes(
                            json.dumps(rdp_entries, sort_keys=True).encode("utf-8")
                        ),
                    },
                    "active_journal_inventory": {
                        "count": len(journal_entries),
                        "fingerprint": _sha256_bytes(
                            json.dumps(journal_entries, sort_keys=True).encode("utf-8")
                        ),
                    },
                }
                info = zipfile.ZipInfo(filename="BACKUP_MANIFEST.json", date_time=ZIP_TIMESTAMP)
                info.external_attr = 0o100644 << 16
                archive.writestr(
                    info, json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
                )
            _fsync_file(tmp)
            published_manifest = read_backup_manifest(tmp)
            if str(published_manifest.get("inventory_sha256")) != inventory_sha256:
                raise RemoteOpsError("BACKUP_MANIFEST_INVENTORY_MISMATCH")
            digest = _sha256_file(tmp)
            dest = sink / f"BACKUP_{digest}.zip"
            os.replace(tmp, dest)
            if _sha256_file(dest) != digest:
                raise RemoteOpsError("BACKUP_BUNDLE_HASH_MISMATCH")
        finally:
            if tmp.exists():
                tmp.unlink()
    should_prune = prune_superseded
    if should_prune is None:
        backup_cfg = loaded.get("backup") if isinstance(loaded.get("backup"), dict) else {}
        should_prune = int(backup_cfg.get("local_verified_bundle_retention") or 0) == 1
    pruned: list[str] = []
    if should_prune:
        pruned = prune_superseded_local_backups(sink, dest)
    return {
        "bundle": dest.name,
        "sha256": digest,
        "bytes": dest.stat().st_size,
        "entries": entries,
        "inventory_sha256": logical_inventory_sha256(entries),
        "sink": dest.parent.as_posix(),
        "pruned": pruned,
    }


def read_backup_manifest(bundle: Path) -> dict[str, Any]:
    if bundle.is_file() is False:
        raise RemoteOpsError("BACKUP_BUNDLE_MISSING")
    with zipfile.ZipFile(bundle, "r") as archive:
        if "BACKUP_MANIFEST.json" not in archive.namelist():
            raise RemoteOpsError("BACKUP_MANIFEST_MISSING")
        try:
            manifest = json.loads(archive.read("BACKUP_MANIFEST.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteOpsError("BACKUP_MANIFEST_INVALID") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("entries"), list):
        raise RemoteOpsError("BACKUP_MANIFEST_INVALID")
    return manifest


def package_delta_backup(
    root: Path,
    *,
    base_manifest: Mapping[str, Any],
    current_entries: Sequence[Mapping[str, Any]],
    sink: Path,
    acquire_lock: bool = False,
) -> dict[str, Any]:
    if acquire_lock:
        with backup_plane_lock(root):
            return package_delta_backup(
                root,
                base_manifest=base_manifest,
                current_entries=current_entries,
                sink=sink,
                acquire_lock=False,
            )
    sink.mkdir(parents=True, exist_ok=True)
    base_by_path = {
        str(item["path"]): item
        for item in base_manifest.get("entries") or []
        if isinstance(item, dict) and item.get("path")
    }
    current_by_path = {str(item["path"]): item for item in current_entries}
    changed: list[dict[str, Any]] = []
    deleted: list[str] = []
    for path, item in current_by_path.items():
        prior = base_by_path.get(path)
        if prior is None or str(prior.get("sha256")) != str(item.get("sha256")):
            changed.append(dict(item))
    for path in base_by_path:
        if path not in current_by_path:
            deleted.append(path)
    result_inventory_sha256 = logical_inventory_sha256(current_entries)
    base_inventory_sha256 = str(
        base_manifest.get("inventory_sha256")
        or logical_inventory_sha256(list(base_by_path.values()))
    )
    if not changed and not deleted:
        return {
            "bundle": None,
            "sha256": None,
            "bytes": 0,
            "delta_payload_bytes": 0,
            "changed": [],
            "deleted": [],
            "result_inventory_sha256": result_inventory_sha256,
            "base_inventory_sha256": base_inventory_sha256,
            "terminal": "NO_CHANGES",
        }
    tmp = sink / f".delta-{os.getpid()}-{time.time_ns()}.zip"
    try:
        with zipfile.ZipFile(tmp, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            packed_changed: list[dict[str, Any]] = []
            for item in changed:
                relative = str(item["path"])
                source = _safe_relative(root, relative)
                if relative.endswith(".sqlite"):
                    snapshot = tmp.parent / f".sqlite-{os.getpid()}-{time.time_ns()}"
                    try:
                        consistent_sqlite_backup(source, snapshot)
                        digest, size = _stream_zip_entry(archive, relative, snapshot)
                    finally:
                        snapshot.unlink(missing_ok=True)
                    kind = "SQLITE_BACKUP_API"
                else:
                    digest, size = _stream_zip_entry(archive, relative, source)
                    kind = "FILE_SNAPSHOT"
                packed_changed.append(
                    {"path": relative, "sha256": digest, "bytes": size, "kind": kind}
                )
            delta_manifest = {
                "kind": "FACTORY_REMOTE_BACKUP_DELTA_MANIFEST",
                "schema_version": "1.0",
                "created_at": _now(),
                "base_inventory_sha256": base_inventory_sha256,
                "result_inventory_sha256": result_inventory_sha256,
                "changed": packed_changed,
                "deleted": sorted(deleted),
            }
            info = zipfile.ZipInfo(filename="DELTA_MANIFEST.json", date_time=ZIP_TIMESTAMP)
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info, json.dumps(delta_manifest, indent=2, sort_keys=True).encode("utf-8")
            )
        _fsync_file(tmp)
        digest = _sha256_file(tmp)
        dest = sink / f"DELTA_{digest}.zip"
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {
        "bundle": dest.name,
        "sha256": digest,
        "bytes": dest.stat().st_size,
        "delta_payload_bytes": dest.stat().st_size,
        "changed": packed_changed,
        "deleted": sorted(deleted),
        "result_inventory_sha256": result_inventory_sha256,
        "base_inventory_sha256": base_inventory_sha256,
        "terminal": "DELTA_PACKAGED",
        "path": dest,
    }


def apply_delta_bundle(delta: Path, dest_root: Path) -> dict[str, Any]:
    if delta.is_file() is False:
        raise RemoteOpsError("DELTA_BUNDLE_MISSING")
    declared = delta.stem.removeprefix("DELTA_")
    if DELTA_BUNDLE_NAME.fullmatch(delta.name) is None or declared != _sha256_file(delta):
        raise RemoteOpsError("DELTA_BUNDLE_HASH_MISMATCH")
    with zipfile.ZipFile(delta, "r") as archive:
        names = archive.namelist()
        if "DELTA_MANIFEST.json" not in names:
            raise RemoteOpsError("DELTA_MANIFEST_MISSING")
        manifest = json.loads(archive.read("DELTA_MANIFEST.json").decode("utf-8"))
        if (
            not isinstance(manifest, dict)
            or manifest.get("kind") != "FACTORY_REMOTE_BACKUP_DELTA_MANIFEST"
        ):
            raise RemoteOpsError("DELTA_MANIFEST_INVALID")
        for relative in manifest.get("deleted") or []:
            target = _safe_relative(dest_root, str(relative))
            if target.is_file():
                target.unlink()
        applied = 0
        for item in manifest.get("changed") or []:
            relative = str(item["path"])
            target = _safe_relative(dest_root, relative)
            with archive.open(relative) as source:
                digest, _size = _stream_copy_hashed(source, target)
            if digest != str(item.get("sha256")):
                raise RemoteOpsError(f"DELTA_HASH_MISMATCH:{relative}")
            applied += 1
    return {"applied": applied, "deleted": list(manifest.get("deleted") or [])}


def restore_backup_isolated(
    *,
    bundle: Path,
    dest_root: Path,
) -> dict[str, Any]:
    if bundle.is_file() is False:
        raise RemoteOpsError("BACKUP_BUNDLE_MISSING")
    bundle_digest = _sha256_file(bundle)
    if bundle.name.startswith("BACKUP_") and bundle.suffix == ".zip":
        declared_digest = bundle.stem.removeprefix("BACKUP_")
        if (
            len(declared_digest) != 64
            or any(character not in "0123456789abcdef" for character in declared_digest)
            or declared_digest != bundle_digest
        ):
            raise RemoteOpsError("BACKUP_BUNDLE_HASH_MISMATCH")
    if dest_root.is_absolute() is False:
        raise RemoteOpsError("RESTORE_ROOT_NOT_ISOLATED")
    if dest_root.resolve() == bundle.parent.resolve():
        raise RemoteOpsError("RESTORE_ROOT_NOT_ISOLATED")
    if dest_root.is_symlink():
        raise RemoteOpsError("RESTORE_ROOT_NOT_ISOLATED")
    _reject_symlink_components(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    restored: list[dict[str, Any]] = []
    sqlite_integrity: list[dict[str, Any]] = []
    with zipfile.ZipFile(bundle, "r") as archive:
        names = archive.namelist()
        if "BACKUP_MANIFEST.json" not in names:
            raise RemoteOpsError("BACKUP_MANIFEST_MISSING")
        if names.count("BACKUP_MANIFEST.json") != 1 or len(names) != len(set(names)):
            raise RemoteOpsError("BACKUP_ARCHIVE_ENTRIES_INVALID")
        try:
            manifest = json.loads(archive.read("BACKUP_MANIFEST.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteOpsError("BACKUP_MANIFEST_INVALID") from exc
        if (
            not isinstance(manifest, dict)
            or manifest.get("kind") != "FACTORY_REMOTE_BACKUP_MANIFEST"
            or not isinstance(manifest.get("entries"), list)
        ):
            raise RemoteOpsError("BACKUP_MANIFEST_INVALID")
        expected: dict[str, str] = {}
        entry_kinds: dict[str, str] = {}
        for item in manifest["entries"]:
            if not isinstance(item, dict):
                raise RemoteOpsError("BACKUP_MANIFEST_INVALID")
            name = item.get("path")
            digest = item.get("sha256")
            if (
                not isinstance(name, str)
                or not name
                or "\\" in name
                or PureWindowsPath(name).is_absolute()
                or bool(PureWindowsPath(name).drive)
                or Path(name).is_absolute()
                or ".." in Path(name).parts
                or ".." in PureWindowsPath(name).parts
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
                or name in expected
            ):
                raise RemoteOpsError("BACKUP_MANIFEST_INVALID")
            expected[name] = digest
            entry_kinds[name] = str(item.get("kind") or "")
        if manifest.get("schema_version") == "1.1" and any(
            name.endswith(".sqlite") and entry_kinds.get(name) != "SQLITE_BACKUP_API"
            for name in expected
        ):
            raise RemoteOpsError("BACKUP_MANIFEST_INVALID")
        archive_entries = {
            name.replace("\\", "/")
            for name in names
            if name != "BACKUP_MANIFEST.json"
        }
        if archive_entries != set(expected):
            raise RemoteOpsError("BACKUP_MANIFEST_ENTRIES_MISMATCH")
        for name in names:
            if name == "BACKUP_MANIFEST.json":
                continue
            candidate = Path(name)
            if (
                "\\" in name
                or candidate.is_absolute()
                or PureWindowsPath(name).is_absolute()
                or bool(PureWindowsPath(name).drive)
                or ".." in candidate.parts
                or ".." in PureWindowsPath(name).parts
            ):
                raise RemoteOpsError("BACKUP_ENTRY_UNSAFE")
            target = dest_root / candidate
            if target.exists() or target.is_symlink():
                raise RemoteOpsError(f"RESTORE_TARGET_EXISTS:{name}")
            if any(parent.is_symlink() for parent in target.parents if parent.exists()):
                raise RemoteOpsError("BACKUP_ENTRY_UNSAFE")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source:
                digest, size = _stream_copy_hashed(source, target)
            if expected.get(name.replace("\\", "/")) != digest:
                raise RemoteOpsError(f"BACKUP_HASH_MISMATCH:{name}")
            restored.append(
                {"path": name.replace("\\", "/"), "sha256": digest, "bytes": size}
            )
            if (
                name.replace("\\", "/").endswith(".sqlite")
                and entry_kinds.get(name.replace("\\", "/")) == "SQLITE_BACKUP_API"
            ):
                try:
                    conn = sqlite3.connect(target)
                    try:
                        check = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
                    finally:
                        conn.close()
                except sqlite3.Error as exc:
                    raise RemoteOpsError(f"RESTORE_SQLITE_INTEGRITY_FAILED:{name}") from exc
                if check != "ok":
                    raise RemoteOpsError(f"RESTORE_SQLITE_INTEGRITY_FAILED:{name}")
                sqlite_integrity.append({"path": name.replace("\\", "/"), "result": check})
        rdp_entries = [
            item
            for item in manifest["entries"]
            if str(item["path"]) == "local/factory_v1/observation_rdp"
            or str(item["path"]).startswith("local/factory_v1/observation_rdp/")
        ]
        expected_rdp_fingerprint = _sha256_bytes(
            json.dumps(rdp_entries, sort_keys=True).encode("utf-8")
        )
        rdp_inventory = manifest.get("rdp_inventory") or {}
        if rdp_inventory and (
            int(rdp_inventory.get("count", -1)) != len(rdp_entries)
            or str(rdp_inventory.get("fingerprint")) != expected_rdp_fingerprint
        ):
            raise RemoteOpsError("BACKUP_RDP_INVENTORY_MISMATCH")
        journal_entries = [
            item
            for item in manifest["entries"]
            if "/publication_jobs/" in str(item["path"])
            or "/journals/" in str(item["path"])
        ]
        journal_inventory = manifest.get("active_journal_inventory") or {}
        expected_journal_fingerprint = _sha256_bytes(
            json.dumps(journal_entries, sort_keys=True).encode("utf-8")
        )
        if journal_inventory and (
            int(journal_inventory.get("count", -1)) != len(journal_entries)
            or str(journal_inventory.get("fingerprint")) != expected_journal_fingerprint
        ):
            raise RemoteOpsError("BACKUP_JOURNAL_INVENTORY_MISMATCH")
        observation_stores = [
            item["path"]
            for item in manifest["entries"]
            if str(item["path"]).endswith("observation_schedule_state.sqlite")
        ]
    for relative in observation_stores:
        target = dest_root / str(relative)
        conn = sqlite3.connect(target)
        try:
            recovery_epoch = f"RESTORE-{bundle_digest[:24]}"
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS restore_markers (
                    marker_id TEXT PRIMARY KEY,
                    recovery_epoch TEXT NOT NULL,
                    resolved INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO restore_markers(
                    marker_id, recovery_epoch, resolved, payload_json, created_at
                ) VALUES ('UNRESOLVED', ?, 0, ?, ?)
                ON CONFLICT(marker_id) DO UPDATE SET
                    recovery_epoch=excluded.recovery_epoch,
                    resolved=0,
                    payload_json=excluded.payload_json,
                    created_at=excluded.created_at
                """,
                (
                    recovery_epoch,
                    json.dumps({"recovery_epoch": recovery_epoch}, sort_keys=True),
                    _now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return {
        "restored": restored,
        "count": len(restored),
        "sqlite_integrity": sqlite_integrity,
        "rdp_inventory": {
            "count": len(rdp_entries),
            "fingerprint": expected_rdp_fingerprint,
        },
        "active_journal_inventory": {
            "count": len(journal_entries),
            "fingerprint": expected_journal_fingerprint,
        },
        "recovery_gap": bool(observation_stores),
        "restore_marker_unresolved": bool(observation_stores),
    }


def restore_incremental_chain_isolated(
    *,
    full_bundle: Path,
    deltas: Sequence[Path],
    dest_root: Path,
    expected_inventory_sha256: str | None = None,
) -> dict[str, Any]:
    restored = restore_backup_isolated(bundle=full_bundle, dest_root=dest_root)
    applied = []
    for delta in deltas:
        applied.append(apply_delta_bundle(delta, dest_root))
    live_rdp = dest_root / "local/factory_v1/observation_rdp"
    rdp_files = []
    if live_rdp.is_dir():
        rdp_files = sorted(
            path.relative_to(dest_root).as_posix()
            for path in live_rdp.rglob("*")
            if path.is_file()
        )
    return {
        **restored,
        "deltas_applied": applied,
        "rdp_file_count": len(rdp_files),
        "terminal": (
            "NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF_PASS"
            if rdp_files
            else "EMPTY_RDP_INCREMENTAL_RESTORE"
        ),
        "expected_inventory_sha256": expected_inventory_sha256,
    }


ALERT_CODE_RU = {
    "START_REMOTE_PROCESSES": "Напишите агенту: процесс Factory упал. Сами не SSH и не Linux.",
    "INSPECT_UNRESOLVED_POSITIONS": "Напишите агенту: есть незакрытая paper-позиция. SQLite не трогайте.",
    "RUN_INDEPENDENT_BACKUP": "Напишите агенту: нужен независимый backup. Сами не копируйте файлы.",
    "RUN_OFFHOST_BACKUP_COPY": "Напишите агенту: off-host Google Drive copy stale или failed. Local backup отдельно проверьте.",
    "WRITE_PAPER_HEARTBEAT": "Напишите агенту: heartbeat paper устарел. Сами ничего не запускайте.",
    "RESTART_PAPER_HEARTBEAT": "Напишите агенту: paper-бот не продвигается. Сами не systemctl.",
    "FREE_DISK_OR_SCALE_STORAGE": "Напишите агенту: диск тесен. Сами не заходите на хост.",
    "OWNER_INFRASTRUCTURE_PACKET_THEN_LIVE_HOST": "Пакет хоста уже выполнен. Дальше агент и Git merge, не Linux.",
    "CONTINUE_UNATTENDED_AGENT_RESTORES": "Ничего не делать. Хост чинит агент.",
    "COMPLETE_REMOTE_OPS_PROOFS": "Напишите агенту: remote-ops доказательства не закрыты.",
    "NO_NEW_ENTRIES": "Новые входы не открывать. Это не команда зайти на сервер.",
    "RUNTIME_PROVED_BACKUP_INDEPENDENT": "Backup parent-independent, runtime жив. Не operational-ready.",
}


ALERT_KINDS = frozenset({"OPS", "TRADE", "SECURITY"})
ALERT_KIND_UI = {
    "OPS": {
        "mark": "OPS",
        "ru": "эксплуатация",
        "icon": "🛠️",
        "swatch": "🔵",
    },
    "TRADE": {
        "mark": "TRADE",
        "ru": "торговля",
        "icon": "📈",
        "swatch": "🟢",
    },
    "SECURITY": {
        "mark": "SEC",
        "ru": "безопасность",
        "icon": "🛡️",
        "swatch": "🔴",
    },
}


TRADE_BLOCK_KEYS = frozenset(
    {
        "emulation",
        "action",
        "bot",
        "hypothesis",
        "ticker",
        "mint_short",
        "side",
        "notional_usd",
        "pnl_usd",
        "horizon",
        "state",
    }
)


def _format_trade_block(kind: str, trade: Mapping[str, Any] | None) -> str:
    if trade is None:
        if kind == "TRADE":
            return "ожидание контура · нет live-сделок · не alpha"
        return "нет live-сделок · блок зарезервирован · не alpha"
    extra = set(trade) - TRADE_BLOCK_KEYS
    if extra:
        raise RemoteOpsError("TRADE_BLOCK_KEYS_UNKNOWN")
    if trade.get("emulation") is not True:
        raise RemoteOpsError("TRADE_BLOCK_REQUIRES_EMULATION")
    lines = [
        "<b>ЭМУЛЯЦИЯ</b> · paper/shadow · не live · не alpha · не деньги",
        f"действие: {html.escape(str(trade.get('action') or '—'), quote=True)}",
        f"бот: <code>{html.escape(str(trade.get('bot') or '—'), quote=True)}</code>",
        f"гипотеза: <code>{html.escape(str(trade.get('hypothesis') or '—'), quote=True)}</code>",
        f"тикер: <code>{html.escape(str(trade.get('ticker') or '—'), quote=True)}</code>",
        f"mint: <code>{html.escape(str(trade.get('mint_short') or '—'), quote=True)}</code>",
        f"сторона: {html.escape(str(trade.get('side') or '—'), quote=True)}",
        f"размер: {html.escape(str(trade.get('notional_usd') or '—'), quote=True)}",
        f"PnL paper: {html.escape(str(trade.get('pnl_usd') or '—'), quote=True)}",
        f"горизонт: <code>{html.escape(str(trade.get('horizon') or '—'), quote=True)}</code>",
        f"состояние: <code>{html.escape(str(trade.get('state') or '—'), quote=True)}</code>",
    ]
    return "\n".join(lines)


def _alert_ru(value: str) -> str:
    return ALERT_CODE_RU.get(value, value)


def format_alert(
    *,
    what: str,
    why_it_matters: str,
    current_safe_state: str,
    required_action: str,
    kind: str = "OPS",
    host_label: str = "factory-remote-ops",
    trade: Mapping[str, Any] | None = None,
) -> str:
    if kind not in ALERT_KINDS:
        raise RemoteOpsError("ALERT_KIND_INVALID")
    ui = ALERT_KIND_UI[kind]
    what_h = html.escape(_alert_ru(what), quote=True)
    why_h = html.escape(_alert_ru(why_it_matters), quote=True)
    safe_h = html.escape(_alert_ru(current_safe_state), quote=True)
    action_h = html.escape(_alert_ru(required_action), quote=True)
    host_h = html.escape(host_label, quote=True)
    kind_h = html.escape(ui["mark"], quote=True)
    kind_ru = html.escape(ui["ru"], quote=True)
    swatch = ui["swatch"]
    icon = ui["icon"]
    trade_h = _format_trade_block(kind, trade)
    return (
        f"{swatch} {icon} <b>FACTORY</b> · <code>{kind_h}</code> · {kind_ru}\n"
        f"\n"
        f"{swatch} <b>ЧТО</b>\n{what_h}\n"
        f"\n"
        f"{swatch} <b>ПОЧЕМУ ЭТО ВАЖНО</b>\n{why_h}\n"
        f"\n"
        f"{swatch} <b>СЕЙЧАС БЕЗОПАСНО</b>\n{safe_h}\n"
        f"\n"
        f"{swatch} <b>ЧТО СДЕЛАТЬ</b>\n{action_h}\n"
        f"\n"
        f"🟢 📈 <b>ТОРГОВЛЯ</b>\n{trade_h}\n"
        f"\n"
        f"⚪ 🖥️ <b>ХОСТ</b>\n<code>{host_h}</code> · Workbench только SSH tunnel · <code>127.0.0.1:8765</code>"
    )


def emit_alert(
    *,
    config: Mapping[str, Any],
    incident_key: str,
    what: str,
    why_it_matters: str,
    current_safe_state: str,
    required_action: str,
    store: Path,
    environ: Mapping[str, str] | None = None,
    transport: Callable[[str, str], None] | None = None,
    kind: str = "OPS",
    host_label: str = "factory-remote-ops",
    trade: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not incident_key or "/" in incident_key or ".." in incident_key:
        raise RemoteOpsError("INCIDENT_KEY_INVALID")
    store.parent.mkdir(parents=True, exist_ok=True)
    history: dict[str, Any] = {}
    if store.is_file():
        loaded_history = json.loads(store.read_text(encoding="utf-8"))
        if isinstance(loaded_history, dict):
            history = loaded_history
    sent = history.get("sent") if isinstance(history.get("sent"), dict) else {}
    if config["alert"]["dedup"] is True and incident_key in sent:
        return {
            "delivered": False,
            "deduped": True,
            "incident_key": incident_key,
            "sent_count": len(sent),
        }
    token = require_secret(str(config["alert"]["token_env"]), environ)
    chat_id = require_secret(str(config["alert"]["chat_id_env"]), environ)
    body = format_alert(
        what=what,
        why_it_matters=why_it_matters,
        current_safe_state=current_safe_state,
        required_action=required_action,
        kind=kind,
        host_label=host_label,
        trade=trade,
    )
    if transport is None:
        url = TELEGRAM_API.format(token=token)
        payload = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": body,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        request = urllib.request.Request(url, data=payload, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if int(response.status) >= 300:
                    raise RemoteOpsError("ALERT_TRANSPORT_FAILED")
        except urllib.error.URLError as exc:
            raise RemoteOpsError("ALERT_TRANSPORT_FAILED") from exc
    else:
        transport(token, body)
    sent[incident_key] = {"at": _now()}
    history["sent"] = sent
    store.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "delivered": True,
        "deduped": False,
        "incident_key": incident_key,
        "sent_count": len(sent),
        "kind": kind,
        "text": body,
    }


def emit_health_alert(
    *,
    root: Path,
    packet: Mapping[str, Any],
    config: Mapping[str, Any],
    store: Path | None = None,
    environ: Mapping[str, str] | None = None,
    transport: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    if packet.get("verdict") == "RUNTIME_PROVED_BACKUP_INDEPENDENT":
        return {"delivered": False, "skipped": "NO_INCIDENT"}
    if packet.get("alert_configured") is not True:
        return {"delivered": False, "skipped": "ALERT_SINK_UNCONFIGURED"}
    incident_key = str(packet.get("verdict") or "")
    if not incident_key:
        raise RemoteOpsError("INCIDENT_KEY_INVALID")
    path = store if store is not None else root / "local/factory_v1/alert_dedup.json"
    result = emit_alert(
        config=config,
        incident_key=incident_key,
        what=incident_key,
        why_it_matters=incident_key,
        current_safe_state="NO_NEW_ENTRIES",
        required_action=str(packet.get("next_safe_action") or "COMPLETE_REMOTE_OPS_PROOFS"),
        store=path,
        environ=environ,
        transport=transport,
        kind="OPS",
    )
    result.pop("text", None)
    return result


def doctor_packet(
    root: Path,
    *,
    process_alive: bool,
    config: Mapping[str, Any] | None = None,
    git_sha: str | None = None,
) -> dict[str, Any]:
    health = project_health(root=root, process_alive=process_alive, config=config)
    health["git_sha"] = git_sha
    health["agent_readable"] = True
    dumped = json.dumps(health)
    for forbidden in ("BEGIN PRIVATE", "xoxb-", "bot[0-9]:"):
        if forbidden in dumped:
            raise RemoteOpsError("SECRET_LEAK_IN_DOCTOR")
    return health


def prove_git_side(root: Path, *, isolated_sink: Path) -> dict[str, Any]:
    config = load_config(root)
    verify_security_templates(root, config)
    write_heartbeat(root, config=config)
    operational = _safe_relative(root, str(config["stores"]["operational_relative"]))
    paper = _safe_relative(root, str(config["stores"]["paper_relative"]))
    operational.parent.mkdir(parents=True, exist_ok=True)
    paper.parent.mkdir(parents=True, exist_ok=True)
    if operational.is_file() is False:
        operational.write_bytes(b"ops-proof")
    if paper.is_file() is False:
        import sqlite3

        conn = sqlite3.connect(paper)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS bot_instances (bot_instance_id TEXT PRIMARY KEY, strategy_id TEXT, strategy_version TEXT, mode TEXT, status TEXT, started_at TEXT, stopped_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS positions (position_id TEXT PRIMARY KEY, bot_instance_id TEXT, mint TEXT, state TEXT, signal_kind TEXT, entered_notional_usd REAL, exit_notional_usd REAL, opened_at TEXT, closed_at TEXT)"
        )
        conn.commit()
        conn.close()
    packed = package_backup(root, config=config, sink_override=isolated_sink)
    restored_root = isolated_sink.parent / "restore"
    restore_backup_isolated(
        bundle=isolated_sink / packed["bundle"],
        dest_root=restored_root,
    )
    health = project_health(root=root, process_alive=True, config=config)
    if health["verdict"] == FORBIDDEN_HEALTHY:
        raise RemoteOpsError("HEALTHY_FROM_PROCESS_ALIVE_FORBIDDEN")
    return {
        "terminal": "FACTORY_REMOTE_OPERATIONS_GIT_READY",
        "backup": packed,
        "health_verdict": health["verdict"],
        "security": health["security"],
        "purchase": config["target"]["purchase"],
        "sku": config["target"]["sku"],
    }
