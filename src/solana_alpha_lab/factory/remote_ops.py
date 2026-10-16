"""Factory remote operations: health, backup, alerts, security baseline.

Owns no scientific truth. Secrets have no defaults. Process-alive is never
HEALTHY. Backup on the same parent as live stores is not independent.
"""

from __future__ import annotations

import hashlib
import ctypes
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
from contextlib import ExitStack, closing, contextmanager, nullcontext
from contextvars import ContextVar
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
BACKUP_SNAPSHOT_STAGING_RELATIVE = "local/factory_v1/backup_snapshot_staging"
BACKUP_SNAPSHOT_OWNER_NAME = ".capture-owner.json"
_HELD_BACKUP_LOCKS: ContextVar[frozenset[str]] = ContextVar("factory_backup_locks")
BACKUP_CAPTURE_FENCE_SECONDS = 30.0
BACKUP_SOURCE_SCAN_MAX_PATHS = 65536
BACKUP_PARTITION_SCAN_MAX_FILES = 16384
BACKUP_PARTITION_SCAN_MAX_BYTES = 32 * 1024 * 1024
_CAPTURE_CLOSURE_BUDGET: ContextVar[dict[str, Any] | None] = ContextVar(
    "backup_capture_closure_budget")
_CAPTURE_TRACE: ContextVar[dict[str, Any] | None] = ContextVar("backup_capture_trace")
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


@contextmanager
def _capture_phase(name: str, *, size: int = 0, count: int = 0,
                   source: str | None = None) -> Iterator[dict[str, Any]]:
    trace = _CAPTURE_TRACE.get(None)
    phase: dict[str, Any] = {"elapsed_seconds": 0.0, "bytes": size, "count": count}
    if source is not None:
        phase["source"] = source
    started = time.monotonic()
    try:
        yield phase
    except BaseException:
        if trace is not None and trace.get("failure_phase") is None:
            trace["failure_phase"] = name
        raise
    finally:
        if trace is not None:
            phase["elapsed_seconds"] = round(time.monotonic() - started, 6)
            if len(trace["phases"]) < 256:
                trace["phases"].append({"phase": name, **phase})
            else:
                trace["additional_phase_count"] = trace.get("additional_phase_count", 0) + 1


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            _capture_closure_step()
            chunk = handle.read(BACKUP_STREAM_CHUNK)
            _capture_closure_step()
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
        return True  # unknown ownership is never stale-lock authority
    if pid <= 0:
        return True
    return _pid_alive(pid)


def _pid_alive(pid: int) -> bool:
    """False means known-dead; inaccessible or uncertain processes stay owned."""
    if os.name == "nt":
        # os.kill(pid, 0) is not a POSIX liveness probe on Windows.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # invalid PID is known-dead
        try:
            status = ctypes.c_ulong()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(status)):
                return True
            return status.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


@contextmanager
def backup_plane_lock(root: Path, *, timeout_seconds: float = 30.0) -> Iterator[Path]:
    path = _safe_relative(root, BACKUP_LOCK_RELATIVE)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    handle: int | None = None
    owned_bytes: bytes | None = None
    while True:
        try:
            handle = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            owned_bytes = f"{os.getpid()}:{_now()}:{time.time_ns()}".encode("utf-8")
            os.write(handle, owned_bytes)
            break
        except FileExistsError:
            try:
                prior_stat, prior_bytes = path.stat(), path.read_bytes()
                alive = _lock_holder_alive(path)
            except OSError:
                continue
            if alive is False:
                try:
                    current = path.stat()
                    if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) == (prior_stat.st_dev, prior_stat.st_ino, prior_stat.st_size, prior_stat.st_mtime_ns) and path.read_bytes() == prior_bytes:
                        path.unlink()
                        continue
                except OSError:
                    pass
            if time.monotonic() >= deadline:
                raise RemoteOpsError("WRITER_BUSY")
            time.sleep(0.05)
    lock_scope = _HELD_BACKUP_LOCKS.set(_HELD_BACKUP_LOCKS.get(frozenset()) | {str(path.resolve())})
    try:
        yield path
    finally:
        _HELD_BACKUP_LOCKS.reset(lock_scope)
        if handle is not None:
            os.close(handle)
        try:
            if path.read_bytes() == owned_bytes:
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
    # ZipInfo does not inherit the enclosing ZipFile's compression settings.
    info.compress_type = zipfile.ZIP_DEFLATED
    info.compress_level = 1
    with source.open("rb") as src, archive.open(info, "w", force_zip64=True) as dest:
        while True:
            chunk = src.read(BACKUP_STREAM_CHUNK)
            if not chunk:
                break
            dest.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def prune_superseded_local_backups(sink: Path, keep: Path, *, protected_bundles: Sequence[str] = ()) -> list[str]:
    if keep.parent.resolve() != sink.resolve():
        raise RemoteOpsError("BACKUP_PRUNE_KEEP_NOT_IN_SINK")
    removed: list[str] = []
    for candidate in sorted(sink.glob("BACKUP_*.zip")):
        if candidate.resolve() == keep.resolve() or candidate.name in protected_bundles:
            continue
        if not _is_published_backup_bundle(candidate):
            continue
        candidate.unlink()
        removed.append(candidate.name)
    return removed


def _local_recovery_references(root: Path) -> set[str]:
    references: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)
        elif isinstance(value, str) and (BACKUP_BUNDLE_NAME.fullmatch(value) or DELTA_BUNDLE_NAME.fullmatch(value)):
            references.add(value)

    for relative in ("local/factory_v1/offhost_backup_chain.json", "local/factory_v1/offhost_backup_pending.json"):
        path = _safe_relative(root, relative)
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise RemoteOpsError("BACKUP_PRUNE_REFERENCE_STATE_INVALID") from exc
            if not isinstance(payload, dict):
                raise RemoteOpsError("BACKUP_PRUNE_REFERENCE_STATE_INVALID")
            visit(payload)
    return references


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


def consistent_sqlite_backup(source: Path, dest: Path, *, deadline_monotonic: float | None = None,
                             snapshot_connection: sqlite3.Connection | None = None,
                             budget_error: str = "BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED") -> None:
    import sqlite3

    if (
        source.is_absolute() is False
        or dest.is_absolute() is False
    ):
        raise RemoteOpsError("REMOTE_PATH_UNSAFE")
    _reject_symlink_components(source)
    _reject_symlink_components(dest)
    source = source.resolve()
    _check_backup_reclaim(source)
    if source.is_file() is False:
        raise RemoteOpsError("BACKUP_SOURCE_MISSING")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    conn = snapshot_connection or sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    replica = sqlite3.connect(dest)
    try:
        def progress(_status: int, _remaining: int, _total: int) -> None:
            if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
                raise RemoteOpsError(budget_error)
        conn.backup(replica, pages=256, progress=progress)
        replica.commit()
        _check_backup_reclaim(source)
    finally:
        replica.close()
        if snapshot_connection is None:
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


def _effective_backup_lists(root: Path, loaded: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    from solana_alpha_lab.factory.hot90_activation import load_hot90_activation
    from solana_alpha_lab.factory.hot90_mutable_backup import mutable_backup_sources

    selected = mutable_backup_sources(
        loaded["backup"],
        activation_stage=str(load_hot90_activation(root)["activation_stage"]),
    )
    return list(selected["source_relative_paths"]), list(selected["recursive_relative_paths"])


def _assert_independent_sink(root: Path, loaded: Mapping[str, Any], sink: Path) -> None:
    if loaded["backup"]["same_parent_forbidden"] is not True:
        raise RemoteOpsError("INDEPENDENT_FLAG_DRIFT")
    parents = []
    sources, recursive = _effective_backup_lists(root, loaded)
    relatives = list(sources) + list(recursive)
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
    *,
    deadline_monotonic: float | None = None,
    defer_completed_validation: bool = False,
) -> list[tuple[str, Path, bool]]:
    result: list[tuple[str, Path, bool]] = []
    seen: set[str] = set()
    scanned_paths = 0

    def scan_step() -> None:
        nonlocal scanned_paths
        if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
            raise RemoteOpsError("BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED")
        scanned_paths += 1
        if scanned_paths > BACKUP_SOURCE_SCAN_MAX_PATHS:
            raise RemoteOpsError("BACKUP_SOURCE_SCAN_BUDGET_EXCEEDED")

    scan_step()
    sources, recursive = _effective_backup_lists(root, loaded)
    for relative in sources:
        scan_step()
        normalized = str(relative).replace("\\", "/")
        source = _safe_relative(root, normalized)
        if not _admit_backup_reclaim_source(source):
            continue
        if source.is_file() is False:
            raise RemoteOpsError(f"BACKUP_SOURCE_MISSING:{normalized}")
        if normalized not in seen:
            result.append((normalized, source, normalized.endswith(".sqlite")))
            seen.add(normalized)
    for relative in recursive:
        scan_step()
        normalized_root = str(relative).replace("\\", "/").rstrip("/")
        source_root = _safe_relative(root, normalized_root)
        if source_root.is_dir() is False:
            raise RemoteOpsError(f"BACKUP_SOURCE_MISSING:{normalized_root}")
        for source in source_root.rglob("*"):
            scan_step()
            if not source.is_file():
                continue
            normalized = source.relative_to(root).as_posix()
            if ("/research/write_lookup_v1/" in normalized
                    or "/projections/research_memory.duckdb" in normalized
                    or normalized.endswith("/locks/research-writer.lock")):
                continue  # native rebuildable lookup/projection/lease is not canonical data
            # Freeze every member now, but postpone repeated parent-resolution
            # of write-once receipts until after the writer fence. No bytes are
            # read from these paths before the same frozen relative is validated.
            if not (defer_completed_validation and _immutable_publication_receipt(normalized)):
                source = _safe_relative(root, normalized)
            if not _admit_backup_reclaim_source(source):
                continue
            if normalized not in seen:
                result.append((normalized, source, normalized.endswith(".sqlite")))
                seen.add(normalized)
    if str(loaded.get("schema_version")) == "1.1":
        api_mains = {relative.casefold() for relative, _source, is_sqlite in result if is_sqlite}
        result = [item for item in result
                  if (_sqlite_sidecar_main(item[0]) or "").casefold() not in api_mains]
    return result


def _check_backup_reclaim(source: Path) -> dict[str, Any] | None:
    from solana_alpha_lab.factory.observation_schedule_store import (
        ObservationScheduleStoreError, assert_reclaim_write_allowed)

    try:
        return assert_reclaim_write_allowed(source)
    except ObservationScheduleStoreError as exc:
        raise RemoteOpsError("BACKUP_RECLAIM_RECOVERY_REQUIRED") from exc


def _admit_backup_reclaim_source(source: Path) -> bool:
    artifact = re.fullmatch(r"\.(.+\.sqlite)\.i2-reclaim(?:\.intent\.json(?:\.tmp)?"
                            r"|-(?:new|rollback)\.sqlite(?:-(?:wal|shm|journal))?)", source.name)
    if artifact:
        main = source.with_name(artifact.group(1))
        terminal = _check_backup_reclaim(main)
        if terminal is None or source.name != f".{main.name}.i2-reclaim.intent.json":
            raise RemoteOpsError("BACKUP_RECLAIM_RECOVERY_REQUIRED")
        # This validated terminal receipt binds a local inode. It is technical
        # recovery state for that host, not portable operational/scientific data.
        return False
    if source.name.casefold().endswith(".sqlite"):
        _check_backup_reclaim(source)
    return True


def _sqlite_sidecar_main(relative: str) -> str | None:
    for suffix in ("-wal", "-shm", "-journal"):
        if relative.casefold().endswith(".sqlite" + suffix):
            return relative[:-len(suffix)]
    return None


def _reject_restored_sqlite_sidecars(root: Path, entries: Sequence[Mapping[str, Any]]) -> None:
    for item in entries:
        relative = str(item["path"])
        if relative.casefold().endswith(".sqlite"):
            for suffix in ("-wal", "-shm", "-journal"):
                candidate = _safe_relative(root, relative + suffix)
                if candidate.exists():
                    raise RemoteOpsError("BACKUP_SQLITE_SIDECAR_CONFLICT")


def _is_publication_job_path(relative: str) -> bool:
    normalized = str(relative).replace("\\", "/")
    return "/datasets/publication_jobs/" in f"/{normalized}"


def _immutable_publication_receipt(relative: str) -> bool:
    path = PurePosixPath(relative)
    return (path.suffix == ".json" and not path.name.startswith(".")
            and any(f"/datasets/publication_jobs/{kind}/" in f"/{relative}"
                    for kind in ("completed", "legacy_full")))


def _publication_job_roots(root: Path, loaded: Mapping[str, Any]) -> list[str]:
    _sources, recursive = _effective_backup_lists(root, loaded)
    roots: list[str] = []
    for relative in recursive:
        normalized = str(relative).replace("\\", "/").rstrip("/")
        if normalized.endswith("datasets/publication_jobs"):
            roots.append(normalized)
            continue
        nested = f"{normalized}/datasets/publication_jobs"
        candidate = _safe_relative(root, nested)
        if candidate.is_dir():
            roots.append(nested)
    return roots


class BackupPayloadSnapshot:
    """One checkpoint's frozen membership and captured bytes, including SQLite."""

    def __init__(self, captured: Mapping[str, Mapping[str, Any]], *, captured_at: str | None = None) -> None:
        self.captured_at = captured_at or _now()
        self._captured = {
            str(path).replace("\\", "/"): dict(item) for path, item in captured.items()
        }

    def owns(self, relative: str) -> bool:
        return self.has(relative)

    def has(self, relative: str) -> bool:
        return str(relative).replace("\\", "/") in self._captured

    def entry(self, relative: str) -> dict[str, Any]:
        key = str(relative).replace("\\", "/")
        try:
            return dict(self._captured[key])
        except KeyError as exc:
            raise RemoteOpsError("SNAPSHOT_BYTES_MISSING") from exc

    def staged_path(self, relative: str) -> Path:
        staged = self.entry(relative).get("staged")
        if not isinstance(staged, Path):
            raise RemoteOpsError("SNAPSHOT_BYTES_MISSING")
        return staged

    def items(self) -> list[tuple[str, dict[str, Any]]]:
        return [(path, dict(item)) for path, item in sorted(self._captured.items())]


def _capture_closure_step(kind: str | None = None, *, size: int = 0, count: int = 1) -> None:
    """Charge work to its current capture deadline and finite closure caps.

    One native filesystem/Parquet call cannot be interrupted here. Check before
    and after it, and refuse oversized materialization before native parsing.
    """
    budget = _CAPTURE_CLOSURE_BUDGET.get(None)
    if budget is None:
        return
    if time.monotonic() > budget["deadline"]:
        raise RemoteOpsError(budget.get("error_code", "BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED"))
    if kind is not None:
        counts = budget["counts"]
        counts[kind] = counts.get(kind, 0) + count
        maximum = BACKUP_PARTITION_SCAN_MAX_FILES if kind in {"manifest_path", "manifest", "partition"} else BACKUP_SOURCE_SCAN_MAX_PATHS
        budget["bytes"] += size
        if counts[kind] > maximum or budget["bytes"] > BACKUP_PARTITION_SCAN_MAX_BYTES:
            code = ("BACKUP_PUBLICATION_PARTITION_SCAN_BUDGET_EXCEEDED"
                if kind in {"manifest_path", "manifest", "partition", "partition_bytes"}
                else "BACKUP_RECOVERY_DEPENDENCY_BUDGET_EXCEEDED")
            raise RemoteOpsError(code)


def _capture_paths(paths: Iterator[Path], *, ordered: bool = False, kind: str = "path") -> Iterator[Path]:
    """Bound enumeration before materializing a sorted path collection."""
    iterator = iter(paths)
    collected = []
    while True:
        _capture_closure_step()
        try:
            path = next(iterator)
        except StopIteration:
            break
        _capture_closure_step(kind)
        if ordered:
            collected.append(path)
        else:
            yield path
    if ordered:
        for path in sorted(collected):
            _capture_closure_step()
            yield path


def _capture_partition_paths(directory: Path) -> Iterator[Path]:
    paths = directory.iterdir() if directory.is_dir() else iter(())
    # Charge unmatched entries too: a filtered glob can traverse a large
    # directory inside one next() before the caller gets a chance to refuse.
    for path in _capture_paths(paths, ordered=True, kind="manifest_path"):
        if path.match("partition-*.json"):
            yield path


def _capture_research_store(data_root: Path, *, create_if_missing: bool = True) -> Any:
    """Bound the existing native reader; keep all scientific parsing/verifying native."""
    from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
    if _CAPTURE_CLOSURE_BUDGET.get(None) is None:
        return ResearchStore(data_root, create_if_missing=create_if_missing)

    class CaptureResearchStore(ResearchStore):
        def _manifest_files(self):
            _capture_closure_step()
            directory = self.root / "research/manifests/partitions"
            if not directory.exists():
                return ()
            if directory.is_symlink() or not directory.is_dir():
                raise ResearchStoreError("MANIFEST_DIRECTORY_UNSAFE")
            return tuple(_capture_partition_paths(directory))

        def _read_manifest(self, path):
            _capture_closure_step()
            _capture_closure_step("manifest", size=path.stat().st_size if path.is_file() else 0)
            manifest = super()._read_manifest(path)
            _capture_closure_step()
            return manifest

        def _verify_partition(self, manifest):
            _capture_closure_step("record", count=int(manifest.row_count))
            path = _safe_relative(self.root, manifest.logical_location)
            _capture_closure_step("partition", size=path.stat().st_size if path.is_file() else 0)
            if path.is_file():
                # Actual Parquet metadata can disagree with the manifest or
                # encode highly compressed columns. Bound it before native
                # _verify_partition materializes the table, then let that
                # unchanged verifier establish all scientific/hash semantics.
                import pyarrow as pa
                import pyarrow.parquet as pq
                try:
                    metadata = pq.ParquetFile(path).metadata
                except (OSError, ValueError, pa.ArrowException) as exc:
                    raise ResearchStoreError("COMMITTED_PARQUET_UNREADABLE") from exc
                _capture_closure_step("actual_record", count=int(metadata.num_rows))
                _capture_closure_step("material", count=int(metadata.num_row_groups)*int(metadata.num_columns))
                for group in range(metadata.num_row_groups):
                    for column in range(metadata.num_columns):
                        _capture_closure_step()
                        size = int(metadata.row_group(group).column(column).total_uncompressed_size)
                        if size < 0:
                            raise RemoteOpsError("BACKUP_RECOVERY_DEPENDENCY_BUDGET_EXCEEDED")
                        _capture_closure_step("partition_bytes", size=size)
            records = super()._verify_partition(manifest)
            _capture_closure_step()
            return records

        def iter_committed_records(self):
            for record in super().iter_committed_records():
                _capture_closure_step("material")
                yield record

        def find_record(self, record_id):
            _capture_closure_step("lookup")
            record = super().find_record(record_id)
            _capture_closure_step()
            return record

    _capture_closure_step()
    return CaptureResearchStore(data_root, create_if_missing=create_if_missing)


@contextmanager
def _capture_sql_deadline(conn: sqlite3.Connection) -> Iterator[None]:
    budget = _CAPTURE_CLOSURE_BUDGET.get(None)
    if budget is not None:
        conn.set_progress_handler(lambda: int(time.monotonic() > budget["deadline"]), 1000)
    try:
        yield
    except sqlite3.OperationalError as exc:
        if budget is not None and time.monotonic() > budget["deadline"]:
            raise RemoteOpsError(budget.get("error_code", "BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED")) from exc
        raise
    finally:
        if budget is not None:
            conn.set_progress_handler(None, 0)


def _capture_mutable_file(live: Path, dest: Path) -> tuple[str, int] | None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    try:
        with live.open("rb") as src, dest.open("wb") as out:
            while True:
                _capture_closure_step()
                chunk = src.read(BACKUP_STREAM_CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            out.flush()
            os.fsync(out.fileno())
    except FileNotFoundError:
        dest.unlink(missing_ok=True)
        return None
    return digest.hexdigest(), size


@contextmanager
def _capture_writer_fences(sources: Sequence[tuple[str, Path, bool]]) -> Iterator[None]:
    """Reserve existing SQLite writers without changing business or lease state.

    The backup-plane lock is always outermost. A current scheduler lease defers
    capture; BEGIN IMMEDIATE protects membership, read-view pinning and mutable
    job/dependency bytes. WAL page copying, captured SHA and control verification
    run after release. Rollback-journal DB copying remains fenced. Every failure
    releases all acquired writer reservations.
    """
    connections: list[sqlite3.Connection] = []
    started = time.monotonic()
    acquired_at = None
    first_acquired_at = None
    try:
        for _relative, source, is_sqlite in sorted(sources):
            _capture_closure_step()
            if not is_sqlite:
                continue
            _check_backup_reclaim(source)
            conn = sqlite3.connect(source.as_uri() + "?mode=rw", uri=True, timeout=0)
            connections.append(conn)
            conn.execute("BEGIN IMMEDIATE")
            if first_acquired_at is None:
                first_acquired_at = time.monotonic()
            _check_backup_reclaim(source)
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='scheduler_leases'").fetchone()
            if exists and conn.execute("SELECT 1 FROM scheduler_leases WHERE expires_at > ? LIMIT 1", (_now(),)).fetchone():
                raise RemoteOpsError("WRITER_BUSY")
        _capture_closure_step()
        acquired_at = time.monotonic()
        trace = _CAPTURE_TRACE.get(None)
        if trace is not None:
            trace["writer_fence_wait_seconds"] = round(acquired_at - started, 6)
        yield
        _capture_closure_step()
        if time.monotonic() - started > BACKUP_CAPTURE_FENCE_SECONDS:
            raise RemoteOpsError("BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED")
    except sqlite3.OperationalError as exc:
        raise RemoteOpsError("WRITER_BUSY") from exc
    finally:
        for conn in reversed(connections):
            conn.rollback()
            conn.close()
        trace = _CAPTURE_TRACE.get(None)
        if trace is not None:
            # Include release, and partial acquisition on a failed later DB.
            trace["writer_fence_hold_seconds"] = round(time.monotonic() - first_acquired_at, 6) if first_acquired_at is not None else 0.0


def _capture_source(captured: dict[str, dict[str, Any]], staging: Path, relative: str, source: Path, is_sqlite: bool, *, deadline: float | None = None,
                    hash_sqlite: bool = True) -> None:
    _capture_closure_step()
    if relative == BACKUP_SNAPSHOT_OWNER_NAME:
        raise RemoteOpsError("BACKUP_SNAPSHOT_OWNER_PATH_RESERVED")
    if relative in captured:
        return
    staged = staging / relative
    staged.parent.mkdir(parents=True, exist_ok=True)
    if is_sqlite:
        with _capture_phase("sqlite_copy_fenced", size=source.stat().st_size, count=1, source=relative):
            consistent_sqlite_backup(source, staged, deadline_monotonic=deadline)
        size = staged.stat().st_size
        digest = None
        if hash_sqlite:
            with _capture_phase("captured_sqlite_sha256", size=size, count=1, source=relative):
                digest = _sha256_file(staged)
    else:
        copied = _capture_mutable_file(source, staged)
        if copied is None:
            raise RemoteOpsError("BACKUP_SOURCE_CHANGED_DURING_CAPTURE")
        digest, size = copied
    captured[relative] = {"sha256": digest, "bytes": size, "staged": staged,
                          "kind": "SQLITE_BACKUP_API" if is_sqlite else "FILE_SNAPSHOT"}
    if deadline is not None and time.monotonic() > deadline:
        raise RemoteOpsError("BACKUP_CAPTURE_FENCE_BUDGET_EXCEEDED")


def _recovery_data_root_relative(ops_relative: str) -> str:
    parent = PurePosixPath(ops_relative).parent
    return parent.as_posix() if parent.name == "observation_rdp" else (parent / "observation_rdp").as_posix()


def _capture_recovery_raw_refs(root: Path, data_root: Path, staging: Path,
                               captured: dict[str, dict[str, Any]], value: Any) -> None:
    pending = [value]
    while pending:
        _capture_closure_step()
        current = pending.pop()
        if isinstance(current, dict):
            for key, nested in current.items():
                _capture_closure_step()
                if key in {"raw_body_rel", "witness_raw_body_rel"} and nested:
                    _capture_closure_step("raw_ref")
                    if not isinstance(nested, str):
                        raise RemoteOpsError("BACKUP_RECOVERY_DEPENDENCY_INVALID")
                    source = _safe_relative(data_root, nested)
                    if not source.is_file():
                        raise RemoteOpsError("BACKUP_RECOVERY_DEPENDENCY_MISSING")
                    relative = source.relative_to(root).as_posix()
                    _capture_source(captured, staging, relative, source, False)
                    # Native bodies/witness extracts are content-addressed.
                    # Check the frozen bytes, never re-read the live source.
                    if re.fullmatch(r"[0-9a-f]{64}", source.stem) and captured[relative]["sha256"] != source.stem:
                        raise RemoteOpsError("BACKUP_RECOVERY_DEPENDENCY_HASH_MISMATCH")
                else:
                    pending.append(nested)
        elif isinstance(current, list):
            for nested in current:
                _capture_closure_step()
                pending.append(nested)


def _capture_publication_partitions(root: Path, data_root: Path, staging: Path,
                                    captured: dict[str, dict[str, Any]], manifest_relative: str) -> None:
    """Freeze the native dataset root's matching partition descriptors and files.

    DatasetManifest stores a fingerprint, not embedded partition descriptors.
    MANIFEST/MARKER continuation does not recreate the descriptors. Resolve
    this one dataset from its receipt, or the metadata fallback for native
    publishers which do not emit that receipt. Never scan under a writer fence.
    """
    from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
    from solana_alpha_lab.storage.manifests import verify_dataset_manifest, verify_partition_manifest

    item = captured[(data_root / manifest_relative).relative_to(root).as_posix()]
    _capture_closure_step()
    if int(item["bytes"]) > 2 * 1024 * 1024:
        raise RemoteOpsError("BACKUP_PUBLICATION_PARTITION_SCAN_BUDGET_EXCEEDED")
    try:
        dataset = DatasetManifest.model_validate_json(item["staged"].read_bytes())
        partitions_dir = _safe_relative(data_root, "datasets/manifests/partitions")
        receipt = _safe_relative(data_root, manifest_relative.removesuffix(".json") + ".validation.json")
        if receipt.exists():
            if receipt.stat().st_size > 2 * 1024 * 1024:
                raise RemoteOpsError("BACKUP_PUBLICATION_PARTITION_INVALID")
            encoded = receipt.read_bytes()
            validation = json.loads(encoded)
            ids = validation.get("partition_manifest_ids") if isinstance(validation, dict) else None
            if (_sha256_bytes(encoded) != dataset.validation_receipt_sha256
                    or not isinstance(ids, list) or not ids
                    or len(ids) > BACKUP_PARTITION_SCAN_MAX_FILES
                    or any(not isinstance(i, str) or not re.fullmatch(r"partition-[0-9a-f]{64}", i) for i in ids)
                    or len(ids) != len(set(ids))):
                raise RemoteOpsError("BACKUP_PUBLICATION_PARTITION_INVALID")
            paths = [_safe_relative(data_root, f"datasets/manifests/partitions/{i}.json") for i in ids]
            _capture_source(captured, staging, receipt.relative_to(root).as_posix(), receipt, False)
            if captured[receipt.relative_to(root).as_posix()]["sha256"] != dataset.validation_receipt_sha256:
                raise RemoteOpsError("BACKUP_PUBLICATION_PARTITION_INVALID")
        else:
            paths = _capture_metadata_matches(partitions_dir, "dataset_manifest_id", {dataset.dataset_manifest_id})
        matched: list[tuple[Path, Any]] = []
        for source in paths:
            _capture_closure_step("manifest", size=source.stat().st_size)
            encoded = source.read_bytes()
            partition = PartitionManifest.model_validate_json(encoded)
            verify_partition_manifest(partition)
            if (source.stem != partition.partition_manifest_id
                    or partition.dataset_manifest_id != dataset.dataset_manifest_id):
                raise RemoteOpsError("BACKUP_PUBLICATION_PARTITION_INVALID")
            matched.append((source, partition))
        if not matched:
            raise RemoteOpsError("BACKUP_PUBLICATION_PARTITION_MISSING")
        verify_dataset_manifest(dataset, partitions=[partition for _source, partition in matched])
        for source, partition in matched:
            _capture_closure_step()
            _capture_source(captured, staging, source.relative_to(root).as_posix(), source, False)
            frozen = PartitionManifest.model_validate_json(captured[source.relative_to(root).as_posix()]["staged"].read_bytes())
            verify_partition_manifest(frozen)
            if frozen != partition:
                raise RemoteOpsError("BACKUP_PUBLICATION_PARTITION_INVALID")
            artifact = _safe_relative(data_root, partition.logical_location)
            _capture_source(captured, staging, artifact.relative_to(root).as_posix(), artifact, False)
            if captured[artifact.relative_to(root).as_posix()]["sha256"] != partition.file_sha256:
                raise RemoteOpsError("BACKUP_RECOVERY_DEPENDENCY_HASH_MISMATCH")
        marker_relative = manifest_relative.removesuffix(".json") + ".published"
        marker = captured.get((data_root / marker_relative).relative_to(root).as_posix())
        if marker:
            body = json.loads(marker["staged"].read_bytes())
            if (not isinstance(body, dict) or body.get("dataset_manifest_id") != dataset.dataset_manifest_id
                    or body.get("dataset_fingerprint") != dataset.dataset_fingerprint):
                raise RemoteOpsError("BACKUP_PUBLICATION_PARTITION_INVALID")
    except RemoteOpsError:
        raise
    except (OSError, ValueError) as exc:
        raise RemoteOpsError("BACKUP_PUBLICATION_PARTITION_INVALID") from exc


def _capture_metadata_matches(directory: Path, key: str, wanted: set[str],
                              include_state: bool = False) -> list[Path]:
    """Streaming, time-bounded fallback, outside writer fences, not an index.

    Only selected headers spend the closure material/bytes budget. Historical
    metadata costs are recorded separately; no fixed history-count cliff or
    list of every path. The enclosing capture's existing total wall deadline
    bounds every iteration/read. Namespace membership is checked by the caller.
    """
    matched: list[Path] = []
    with _capture_phase("recovery_metadata_fallback") as phase:
        if not wanted or not directory.exists():
            return matched
        _capture_check_fallback_namespace(directory)
        with os.scandir(directory) as entries:
            for entry in entries:
                _capture_closure_step()
                phase["count"] += 1
                if not entry.name.startswith("partition-") or not entry.name.endswith(".json"):
                    continue
                source = _safe_relative(directory, entry.name)
                if not entry.is_file(follow_symlinks=False) or entry.stat(follow_symlinks=False).st_size > 2 * 1024 * 1024:
                    raise RemoteOpsError("BACKUP_RECOVERY_METADATA_INVALID")
                with source.open("rb") as stream:
                    encoded = stream.read(2 * 1024 * 1024 + 1)
                if len(encoded) > 2 * 1024 * 1024:
                    raise RemoteOpsError("BACKUP_RECOVERY_METADATA_INVALID")
                phase["bytes"] += len(encoded)
                _capture_closure_step()
                try:
                    metadata = json.loads(encoded)
                except ValueError as exc:
                    raise RemoteOpsError("BACKUP_RECOVERY_METADATA_INVALID") from exc
                if not isinstance(metadata, dict):
                    raise RemoteOpsError("BACKUP_RECOVERY_METADATA_INVALID")
                value = metadata.get(key)
                if isinstance(value, str) and (value in wanted or (
                        include_state and value.startswith("RESEARCH-TXN-OBS-TRANS-"))):
                    _capture_closure_step("manifest_path")
                    matched.append(source)
        _capture_check_fallback_namespace(directory)
    return matched


def _capture_check_fallback_namespace(directory: Path) -> None:
    # Exact immutable pointers are safe across unrelated later publications.
    # A fallback has no frozen membership list and must retain its fenced stamp.
    budget = _CAPTURE_CLOSURE_BUDGET.get(None)
    if budget is None or "namespace_stamps" not in budget:
        return
    key = str(directory)
    budget["fallback_namespaces"].add(key)
    try:
        s = directory.stat() if directory.exists() else None
        actual = None if s is None else (s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns)
    except OSError as exc:
        raise RemoteOpsError("BACKUP_RECOVERY_NAMESPACE_CHANGED") from exc
    if key not in budget["namespace_stamps"] or actual != budget["namespace_stamps"][key]:
        raise RemoteOpsError("BACKUP_RECOVERY_NAMESPACE_CHANGED")


def _capture_required_transactions(conn: sqlite3.Connection) -> tuple[set[str], dict[str, dict[str, int]]]:
    """Actual captured ACTIVE/DRAINING rows own control identities, never A/B IDs."""
    with _capture_sql_deadline(conn):
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='schedule_activations'").fetchone():
            return set(), {}
        transactions: set[str] = set()
        activations: dict[str, dict[str, int]] = {}
        for schedule, event, receipt, activation, sequence in conn.execute("SELECT schedule_sha256,last_transition_event_id,authority_receipt_sha256,activation_id,transition_sequence FROM schedule_activations WHERE state IN ('ACTIVE','DRAINING')"):
            _capture_closure_step("material")
            if not event or not receipt:
                raise RemoteOpsError("BACKUP_RECOVERY_TRANSITION_EVENT_MISSING")
            transactions.update((f"RESEARCH-TXN-OBS-SCHED-{schedule[:12].upper()}",
                                 f"RESEARCH-TXN-{event.upper()}",
                                 f"RESEARCH-TXN-OBS-AUTHZ-{receipt[:12].upper()}"))
            activations.setdefault(schedule, {})[activation] = int(sequence)
        return transactions, activations


def _capture_research_transactions(root: Path, data_root: Path, staging: Path,
                                   captured: dict[str, dict[str, Any]],
                                   required: set[str], optional: set[str],
                                   activations: Mapping[str, Mapping[str, int]]) -> None:
    from solana_alpha_lab.factory.research_store import ResearchStoreError
    from solana_alpha_lab.factory.research_write_lookup import WriteLookupError
    try:
        if not required and not optional:
            return
        research = _capture_research_store(data_root, create_if_missing=False)
        lookup = research._write_lookup()  # strict read-only: no commissioning or pending repair
        wanted = required | optional
        if lookup is not None:
            manifests = []
            for transaction in sorted(wanted):
                _capture_closure_step("lookup")
                pointer = lookup.get("transactions", transaction)
                if pointer is not None:
                    if pointer["transaction_id"] != transaction:
                        raise RemoteOpsError("BACKUP_RECOVERY_RESEARCH_IDENTITY_CONFLICT")
                    manifests.append(research._lookup_manifest(pointer))
            known = {m.partition_manifest_id for m in manifests}
            for schedule in activations:
                for pointer in lookup.state_pointers(schedule):
                    _capture_closure_step("lookup")
                    if pointer["manifest_id"] not in known:
                        manifests.append(research._lookup_manifest(pointer))
                        known.add(pointer["manifest_id"])
            mode = "recovery_research_exact_lookup"
        else:
            paths = _capture_metadata_matches(data_root / "research/manifests/partitions", "partition_id", wanted, bool(activations))
            manifests = [research._read_manifest(path) for path in paths]
            mode = "recovery_research_selected"
        found: set[str] = set()
        frozen = _capture_research_store(staging / data_root.relative_to(root), create_if_missing=True)
        with _capture_phase(mode) as phase:
            for manifest in manifests:
                if manifest.partition_id not in wanted:
                    # OPS overwrites its previous transition pointer. Existing
                    # source-owned state pointers (or fallback control headers)
                    # retain precisely this activation's committed prefix.
                    records = research._verify_partition(manifest)
                    if not any(str(r.record_kind) == "OBSERVATION_SCHEDULE_STATE"
                            and str(r.entity_id) in activations
                            and str(r.run_id) in activations[str(r.entity_id)]
                            and int(json.loads(r.payload_json).get("transition_sequence", -1)) <= activations[str(r.entity_id)][str(r.run_id)]
                            for r in records):
                        continue
                if manifest.partition_id in found:
                    raise RemoteOpsError("BACKUP_RECOVERY_RESEARCH_IDENTITY_CONFLICT")
                found.add(manifest.partition_id)
                for relative in (f"research/manifests/partitions/{manifest.partition_manifest_id}.json", manifest.logical_location):
                    source = _safe_relative(data_root, relative)
                    _capture_source(captured, staging, source.relative_to(root).as_posix(), source, False)
                    phase["bytes"] += source.stat().st_size
                staged_manifest = frozen._read_manifest(staging / data_root.relative_to(root) /
                    f"research/manifests/partitions/{manifest.partition_manifest_id}.json")
                if staged_manifest != manifest:
                    raise RemoteOpsError("BACKUP_RECOVERY_RESEARCH_IDENTITY_CONFLICT")
                frozen._verify_partition(staged_manifest)
                phase["count"] += 1
        if required - found:
            raise RemoteOpsError("BACKUP_RECOVERY_REQUIRED_RESEARCH_EVENT_MISSING")
    except RemoteOpsError:
        raise
    except (ResearchStoreError, WriteLookupError) as exc:
        raise RemoteOpsError("BACKUP_RECOVERY_" + exc.code) from exc
    except OSError as exc:
        raise RemoteOpsError("BACKUP_RECOVERY_RESEARCH_SOURCE_UNREADABLE") from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise RemoteOpsError("BACKUP_RECOVERY_RESEARCH_SOURCE_INVALID") from exc


def _capture_mutable_recovery_pointers(root: Path, staging: Path,
                                      captured: dict[str, dict[str, Any]]) -> None:
    """Freeze only mutable member mirrors with their captured open job/OPS view."""
    for relative, item in list(captured.items()):
        if not _is_publication_job_path(relative) or _immutable_publication_receipt(relative):
            continue
        _capture_closure_step("material")
        if int(item["bytes"]) > 2 * 1024 * 1024:
            raise RemoteOpsError("BACKUP_OPEN_JOB_DEPENDENCY_INVALID")
        try:
            job = json.loads(item["staged"].read_bytes())
        except (ValueError, UnicodeDecodeError) as exc:
            raise RemoteOpsError("BACKUP_OPEN_JOB_DEPENDENCY_INVALID") from exc
        if not isinstance(job, dict):
            raise RemoteOpsError("BACKUP_OPEN_JOB_DEPENDENCY_INVALID")
        if not job.get("member_rel"):
            continue
        data_root = _safe_relative(root, relative.split("/datasets/publication_jobs/", 1)[0])
        member = _safe_relative(data_root, str(job["member_rel"]))
        sidecar = member.with_name("members.layout.json")
        if sidecar.is_file():
            _capture_source(captured, staging, sidecar.relative_to(root).as_posix(), sidecar, False)
            layout = json.loads(captured[sidecar.relative_to(root).as_posix()]["staged"].read_bytes())
            if not isinstance(layout, dict):
                raise RemoteOpsError("BACKUP_OPEN_JOB_DEPENDENCY_INVALID")
            if layout.get("unit_rel"):
                unit = _safe_relative(data_root, str(layout["unit_rel"]))
                _capture_source(captured, staging, unit.relative_to(root).as_posix(), unit, False)


def _capture_namespace_stamps(root: Path, captured: Mapping[str, Any]) -> dict[str, tuple[int, ...] | None]:
    roots = {p.split("/datasets/publication_jobs/", 1)[0] for p in captured if _is_publication_job_path(p)}
    roots.update(_recovery_data_root_relative(p) for p in captured if PurePosixPath(p).name == "observation_schedule_state.sqlite")
    stamps = {}
    for data in sorted(roots):
        for namespace in ("research", "datasets"):
            _capture_closure_step()
            relative = f"{data}/{namespace}/manifests/partitions"
            directory = _safe_relative(root, relative)
            if not directory.exists():
                stamps[relative] = None
            else:
                try:
                    s = directory.stat()
                except OSError as exc:
                    raise RemoteOpsError("BACKUP_RECOVERY_NAMESPACE_CHANGED") from exc
                stamps[relative] = (s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns)
    return stamps


def _capture_recovery_dependencies(root: Path, staging: Path, captured: dict[str, dict[str, Any]],
                                   *, sqlite_readers: Mapping[str, sqlite3.Connection] | None = None) -> None:
    """Narrow control-event and open-publication closure, never a full RDP copy.

    OPS owns grants, children, debts and transition IDs. ResearchStore owns the
    immutable authority/state events that prove them. Its optional lookup and
    DuckDB projection are rebuildable and deliberately excluded. Open jobs own
    their named artifacts; completed historical scientific payload stays with
    the independent immutable archive owner.
    """
    roots = {path.split("/datasets/publication_jobs/", 1)[0]
             for path in captured if "/datasets/publication_jobs/" in path}
    ops_by_data_root = {_recovery_data_root_relative(path): path for path in captured
                        if PurePosixPath(path).name == "observation_schedule_state.sqlite"}
    roots.update(ops_by_data_root)
    for data_relative in sorted(roots):
        _capture_closure_step("material")
        data_root = _safe_relative(root, data_relative)
        open_contents = {PurePosixPath(path).stem for path in captured
                         if path.startswith(data_relative + "/datasets/publication_jobs/")
                         and "/completed/" not in path and "/legacy_full/" not in path
                         and re.fullmatch(r"[0-9a-f]{64}", PurePosixPath(path).stem)}
        publication_transactions = {f"RESEARCH-TXN-{kind}-{content[:12].upper()}"
                                    for content in open_contents for kind in ("OBS", "MEM")}
        required: set[str] = set()
        activations: dict[str, dict[str, int]] = {}
        ops_item = captured.get(ops_by_data_root.get(data_relative, ""))
        if ops_item and ops_item.get("kind") == "SQLITE_BACKUP_API":
            reader = (sqlite_readers or {}).get(ops_by_data_root[data_relative])
            owned = nullcontext(reader) if reader is not None else closing(sqlite3.connect(ops_item["staged"].as_uri() + "?mode=ro&immutable=1", uri=True))
            with owned as conn:
                required, activations = _capture_required_transactions(conn)
        jobs = [(path, item) for path, item in captured.items()
                if path.startswith(data_relative + "/datasets/publication_jobs/")
                and "/completed/" not in path and "/legacy_full/" not in path
                and path.endswith(".json")]
        for path, item in jobs:
            _capture_closure_step("material")
            job = json.loads(item["staged"].read_bytes())
            content = PurePosixPath(path).stem[:12].upper()
            if job.get("stage") in {"RDP_OBSERVATION_BATCH", "RDP_MEMBER_BATCH", "MANIFEST", "MARKER", "COMPLETE"}:
                required.add(f"RESEARCH-TXN-OBS-{content}")
            if job.get("stage") in {"RDP_MEMBER_BATCH", "MANIFEST", "MARKER", "COMPLETE"}:
                required.add(f"RESEARCH-TXN-MEM-{content}")
        _capture_research_transactions(root, data_root, staging, captured, required, publication_transactions, activations)
        for _relative, item in jobs:
            _capture_closure_step("material")
            if int(item["bytes"]) > 2 * 1024 * 1024:
                raise RemoteOpsError("BACKUP_OPEN_JOB_DEPENDENCY_BUDGET_EXCEEDED")
            try:
                job = json.loads(item["staged"].read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise RemoteOpsError("BACKUP_OPEN_JOB_DEPENDENCY_INVALID") from exc
            if not isinstance(job, dict):
                raise RemoteOpsError("BACKUP_OPEN_JOB_DEPENDENCY_INVALID")
            _capture_recovery_raw_refs(root, data_root, staging, captured, job)
            stage = str(job.get("stage") or "")
            dependencies = [str(job[key]) for key in ("parquet_rel", "member_rel") if job.get(key)]
            manifest_id = job.get("dataset_manifest_id")
            if manifest_id:
                if stage in {"MANIFEST", "MARKER", "COMPLETE"}:
                    dependencies.append(f"datasets/manifests/{manifest_id}.json")
                if stage in {"MARKER", "COMPLETE"}:
                    dependencies.append(f"datasets/manifests/{manifest_id}.published")
            for dependency in dependencies:
                _capture_closure_step("material")
                source = _safe_relative(data_root, dependency)
                if not source.is_file():
                    if stage in {"ARTIFACTS", "RDP_OBSERVATION_BATCH", "RDP_MEMBER_BATCH", "MANIFEST", "MARKER", "COMPLETE"}:
                        raise RemoteOpsError("BACKUP_RECOVERY_DEPENDENCY_MISSING")
                    continue  # an intent can replay from its staged job bytes
                _capture_source(captured, staging, source.relative_to(root).as_posix(), source, False)
                sidecar = source.with_name("members.layout.json")
                if dependency == str(job.get("member_rel")) and sidecar.relative_to(root).as_posix() in captured:
                    layout = json.loads(captured[sidecar.relative_to(root).as_posix()]["staged"].read_text(encoding="utf-8"))
                    unit_rel = layout.get("unit_rel")
                    if unit_rel:
                        unit = _safe_relative(data_root, str(unit_rel))
                        _capture_source(captured, staging, unit.relative_to(root).as_posix(), unit, False)
                        unit_payload = json.loads(captured[unit.relative_to(root).as_posix()]["staged"].read_text(encoding="utf-8"))
                        for publication in unit_payload.get("publications", []):
                            _capture_closure_step("material")
                            artifact = _safe_relative(data_root, str(publication["rel"]))
                            _capture_source(captured, staging, artifact.relative_to(root).as_posix(), artifact, False)
                            if str(captured[artifact.relative_to(root).as_posix()]["sha256"]) != str(publication.get("sha256")):
                                raise RemoteOpsError("BACKUP_RECOVERY_DEPENDENCY_HASH_MISMATCH")
            if manifest_id and stage in {"MANIFEST", "MARKER", "COMPLETE"}:
                _capture_publication_partitions(root, data_root, staging, captured,
                                                 f"datasets/manifests/{manifest_id}.json")
        ops_item = captured.get(ops_by_data_root.get(data_relative, ""))
        if ops_item and ops_item.get("kind") == "SQLITE_BACKUP_API":
            # Native terminal states need no scheduling recovery. A terminal raw
            # pointer still needs bytes unless another owner proves preservation;
            # conservatively retain it, including JSON-escaped keys. This SQL
            # prefilter may overselect, never silently discard a raw dependency.
            from solana_alpha_lab.factory.observation_schedule_store import _TERMINAL_DUE_STATES
            terminal_states = ",".join("'" + state + "'" for state in sorted(_TERMINAL_DUE_STATES))
            due_predicate = (f"state NOT IN ({terminal_states}) OR "
                             "instr(payload_json,'raw_body_rel')>0 OR instr(payload_json,char(92))>0")
            reader = (sqlite_readers or {}).get(ops_by_data_root[data_relative])
            owned = (nullcontext(reader) if reader is not None else closing(sqlite3.connect(
                ops_item["staged"].as_uri() + "?mode=ro&immutable=1", uri=True)))
            with owned as conn, _capture_sql_deadline(conn):
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                for table, column, predicate in (
                    ("episode_outbox", "row_json", "1=1"),
                    ("publication_jobs", "payload_json", "stage != 'COMPLETE'"),
                    ("due_observations", "payload_json", due_predicate),
                    ("call_ledger", "payload_json", "state IN ('STARTED','UNKNOWN')"),
                ):
                    _capture_closure_step()
                    if table not in tables:
                        continue
                    cursor = conn.execute(f"SELECT rowid,length(CAST({column} AS BLOB)) FROM {table} WHERE {predicate}")
                    for rowid, size in cursor:
                        _capture_closure_step()
                        if int(size) > 2 * 1024 * 1024:
                            raise RemoteOpsError("BACKUP_RECOVERY_DEPENDENCY_BUDGET_EXCEEDED")
                        encoded = conn.execute(f"SELECT {column} FROM {table} WHERE rowid=?", (rowid,)).fetchone()[0]
                        try:
                            document = json.loads(encoded)
                        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
                            raise RemoteOpsError("BACKUP_RECOVERY_DEPENDENCY_INVALID") from exc

                        _capture_recovery_raw_refs(root, data_root, staging, captured, document)


def _verify_recovery_control_one(root: Path, ops_relative: str) -> dict[str, int]:
    """Require captured OPS transitions and authority to have their native events.

    A SQL commit preceding its ResearchEvent is a real incomplete lifecycle
    boundary. Backup defers until its existing lifecycle owner repairs it; it
    cannot silently canonize ACTIVE or manufacture the missing event.
    """
    _capture_closure_step()
    path = _safe_relative(root, ops_relative)
    if not path.is_file():
        return {"transitions": 0, "authorities": 0}
    with path.open("rb") as handle:
        if handle.read(16) != b"SQLite format 3\x00":
            return {"transitions": 0, "authorities": 0}
    # This is an isolated SQLite backup with no WAL, never the live source.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn, _capture_sql_deadline(conn):
        conn.row_factory = sqlite3.Row
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "schedule_activations" not in tables:
            return {"transitions": 0, "authorities": 0}
        with closing(conn.execute("SELECT * FROM schedule_activations WHERE state IN ('ACTIVE','DRAINING')")) as rows:
            transitions, authorities = 0, set()
            research = None
            for row in rows:
                _capture_closure_step("material")
                if research is None:
                    research = _capture_research_store(_safe_relative(root, _recovery_data_root_relative(ops_relative)), create_if_missing=False)
                item = dict(row)
                schedule_event = research.find_record(f"OBS-SCHED-{str(item['schedule_sha256'])[:16].upper()}")
                if schedule_event is None:
                    raise RemoteOpsError("BACKUP_RECOVERY_SCHEDULE_EVENT_MISSING")
                if (str(schedule_event.record_kind) != "OBSERVATION_SCHEDULE"
                        or str(schedule_event.entity_id) != str(item["schedule_sha256"])):
                    raise RemoteOpsError("BACKUP_RECOVERY_SCHEDULE_EVENT_CONFLICT")
                event_id = str(item.get("last_transition_event_id") or "")
                record = research.find_record(event_id) if event_id else None
                if record is None:
                    raise RemoteOpsError("BACKUP_RECOVERY_TRANSITION_EVENT_MISSING")
                payload = json.loads(record.payload_json)
                projected = json.loads(item["payload_json"])
                if (str(record.record_kind) != "OBSERVATION_SCHEDULE_STATE"
                        or str(record.entity_id) != str(item["schedule_sha256"])
                        or str(record.run_id) != str(item["activation_id"])
                        or payload.get("state_event_id") != event_id
                        or payload.get("state") != projected.get("new_state")
                        or payload.get("transition_sequence") != item.get("transition_sequence")
                        or payload.get("authority_receipt_sha256") != item.get("authority_receipt_sha256")):
                    raise RemoteOpsError("BACKUP_RECOVERY_TRANSITION_EVENT_CONFLICT")
                if (projected.get("new_state") == "DRAINING" and projected.get("prior_state") == "ACTIVE"
                        and record.effective_at > record.created_at):
                    from solana_alpha_lab.factory.observation_schedule_lifecycle import _prior_active_transition_research_event_proven
                    if not _prior_active_transition_research_event_proven(research.root, {**item, "payload": projected}, now=record.created_at):
                        raise RemoteOpsError("BACKUP_RECOVERY_PRIOR_ACTIVE_EVENT_MISSING")
                transitions += 1
                receipt_sha = str(item.get("authority_receipt_sha256") or "")
                _capture_closure_step()
                authority = conn.execute("SELECT payload_json FROM authority_receipts WHERE receipt_sha256=?", (receipt_sha,)).fetchone() if "authority_receipts" in tables else None
                event = research.find_record(f"OBS-AUTHZ-{receipt_sha[:16].upper()}") if receipt_sha else None
                if authority is None or event is None:
                    raise RemoteOpsError("BACKUP_RECOVERY_AUTHORITY_EVENT_MISSING")
                if str(event.record_kind) != "OBSERVATION_SCHEDULE_AUTHORITY" or json.loads(event.payload_json) != json.loads(authority[0]):
                    raise RemoteOpsError("BACKUP_RECOVERY_AUTHORITY_EVENT_CONFLICT")
                authorities.add(receipt_sha)
            return {"transitions": transitions, "authorities": len(authorities)}


def _verify_recovery_control(root: Path) -> dict[str, int]:
    result = {"transitions": 0, "authorities": 0}
    for path in _capture_paths(root.rglob("*"), ordered=True):
        if not path.match("observation_schedule_state.sqlite"):
            continue
        _capture_closure_step()
        counts = _verify_recovery_control_one(root, path.relative_to(root).as_posix())
        for key in result:
            result[key] += counts[key]
    return result


def _reclaim_dead_snapshot_staging(root: Path, parent: Path) -> None:
    """Admission runs under backup-plane lock; reclaim only this owner's dead captures."""
    parent_resolved = parent.resolve()
    repository_identity = _sha256_bytes(str(root.resolve()).encode("utf-8"))
    for count, candidate in enumerate(parent.glob("capture-*"), 1):
        if count > 1024:
            raise RemoteOpsError("BACKUP_SNAPSHOT_STAGING_RECOVERY_REQUIRED")
        _reject_symlink_components(candidate.absolute())
        resolved = candidate.resolve()
        if not candidate.is_dir() or resolved.parent != parent_resolved:
            raise RemoteOpsError("BACKUP_SNAPSHOT_STAGING_RECOVERY_REQUIRED")
        marker = candidate / BACKUP_SNAPSHOT_OWNER_NAME
        try:
            if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 4096:
                raise RemoteOpsError("BACKUP_SNAPSHOT_STAGING_RECOVERY_REQUIRED")
            identity = candidate.stat()
            encoded = marker.read_bytes()
            owner = json.loads(encoded)
            if (not isinstance(owner, dict) or owner.get("schema") != "smial.backup-capture-owner-v1"
                    or owner.get("capture_name") != candidate.name
                    or owner.get("repository_sha256") != repository_identity
                    or type(owner.get("pid")) is not int or owner["pid"] <= 0):
                raise RemoteOpsError("BACKUP_SNAPSHOT_STAGING_RECOVERY_REQUIRED")
            if _pid_alive(owner["pid"]):
                raise RemoteOpsError("WRITER_BUSY")
            current = candidate.stat()
            if ((current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino)
                    or marker.read_bytes() != encoded or candidate.resolve().parent != parent_resolved):
                raise RemoteOpsError("BACKUP_SNAPSHOT_STAGING_RECOVERY_REQUIRED")
            # The resolved absolute deletion target is one owned child of the
            # exact staging root. Unknown bytes and live owners never reach it.
            shutil.rmtree(resolved)
        except RemoteOpsError:
            raise
        except (OSError, ValueError) as exc:
            raise RemoteOpsError("BACKUP_SNAPSHOT_STAGING_RECOVERY_REQUIRED") from exc


@contextmanager
def _owned_snapshot_staging(root: Path, parent: Path) -> Iterator[Path]:
    directory: tempfile.TemporaryDirectory[str] | None = None
    try:
        with ExitStack() as admission:
            lock = _safe_relative(root, BACKUP_LOCK_RELATIVE)
            if str(lock.resolve()) not in _HELD_BACKUP_LOCKS.get(frozenset()):
                admission.enter_context(backup_plane_lock(root, timeout_seconds=0.0))
            _reclaim_dead_snapshot_staging(root, parent)
            directory = tempfile.TemporaryDirectory(prefix="capture-", dir=parent)
            staging = Path(directory.name)
            owner = {"schema": "smial.backup-capture-owner-v1", "pid": os.getpid(),
                     "repository_sha256": _sha256_bytes(str(root.resolve()).encode("utf-8")),
                     "capture_name": staging.name, "created_at": _now()}
            marker = staging / BACKUP_SNAPSHOT_OWNER_NAME
            marker.write_text(json.dumps(owner, sort_keys=True), encoding="utf-8")
            _fsync_file(marker)
        yield staging
    finally:
        if directory is not None:
            with _capture_phase("cleanup", count=1):
                directory.cleanup()


@contextmanager
def backup_payload_snapshot(
    root: Path,
    loaded: Mapping[str, Any],
    *,
    staging_parent: Path | None = None,
) -> Iterator[BackupPayloadSnapshot]:
    """Capture one immutable mapping; no downstream consumer reopens live paths."""
    started = time.monotonic()
    trace: dict[str, Any] = {"phases": [], "failure_phase": None}
    token = _CAPTURE_TRACE.set(trace)
    try:
        with _backup_payload_snapshot(root, loaded, staging_parent=staging_parent) as snapshot:
            trace["capture_elapsed_seconds"] = round(time.monotonic() - started, 6)
            snapshot.capture_trace = trace
            yield snapshot
    except (RemoteOpsError, sqlite3.Error) as exc:
        error = RemoteOpsError("BACKUP_CAPTURE_SQLITE_ERROR") if isinstance(exc, sqlite3.Error) else exc
        trace["failure_phase"] = trace["failure_phase"] or (
            "post_capture_consumer" if "capture_elapsed_seconds" in trace else
            "writer_fence_admission" if str(exc) == "WRITER_BUSY" else "capture_guard")
        error.capture_trace = trace
        if error is exc:
            raise
        raise error from exc
    finally:
        trace["lifecycle_wall_seconds"] = round(time.monotonic() - started, 6)
        _CAPTURE_TRACE.reset(token)


@contextmanager
def _backup_payload_snapshot(root: Path, loaded: Mapping[str, Any], *,
                             staging_parent: Path | None = None) -> Iterator[BackupPayloadSnapshot]:
    loaded = _select_v1_1_config(root, loaded)
    captured_at = _now()
    captured: dict[str, dict[str, Any]] = {}
    parent = staging_parent or _safe_relative(root, BACKUP_SNAPSHOT_STAGING_RELATIVE)
    _reject_symlink_components(parent.absolute())
    parent.mkdir(parents=True, exist_ok=True)
    sqlite_api = str(loaded.get("schema_version")) == "1.1"
    capture_deadline = time.monotonic() + float(loaded.get("monitoring", {}).get("stall_max_seconds", 1800))
    # This provisional census admits only the SQLite writer-fence set. It is
    # never the checkpoint's file membership: a publication can commit before
    # those fences are acquired.
    with _capture_phase("enumeration_provisional") as phase:
        provisional_sqlite = [(relative, path, True)
                              for relative, path, is_sqlite in _backup_source_paths(root, loaded)
                              if is_sqlite and sqlite_api]
        phase["count"] = len(provisional_sqlite)
    with _owned_snapshot_staging(root, parent) as staging, ExitStack() as readers:
        deadline = time.monotonic() + BACKUP_CAPTURE_FENCE_SECONDS
        token = _CAPTURE_CLOSURE_BUDGET.set({"deadline":deadline,"counts":{},"bytes":0})
        try:
            with _capture_writer_fences(provisional_sqlite):
                # Freeze authoritative membership only after every admitted writer
                # is fenced, with traversal charged to the same capture deadline.
                with _capture_phase("enumeration_fenced") as phase:
                    sources = [(relative, path, is_sqlite and sqlite_api)
                               for relative, path, is_sqlite in _backup_source_paths(
                                   root, loaded, deadline_monotonic=deadline,
                                   defer_completed_validation=True)]
                    phase["count"] = len(sources)
                fenced_sqlite = {relative for relative, _path, _sqlite in provisional_sqlite}
                if any(is_sqlite and relative not in fenced_sqlite for relative, _path, is_sqlite in sources):
                    raise RemoteOpsError("BACKUP_UNFENCED_SQLITE_DISCOVERED")
                sqlite_readers: dict[str, sqlite3.Connection] = {}
                for relative, source, is_sqlite in sources:
                    if is_sqlite:
                        conn = readers.enter_context(closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)))
                        # A read transaction pins the WAL snapshot while every
                        # admitted writer is still fenced. BEGIN alone is lazy.
                        # Rollback-journal readers would block writer COMMIT.
                        if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                            conn.close()
                            _capture_source(captured, staging, relative, source, True, deadline=deadline,
                                            hash_sqlite=False)
                            continue
                        conn.execute("BEGIN")
                        conn.execute("SELECT rootpage FROM sqlite_schema LIMIT 1").fetchall()
                        sqlite_readers[relative] = conn
                        captured[relative] = {"kind":"SQLITE_BACKUP_API", "staged":staging/relative}
                    # The native completed owner is write-once; legacy_full
                    # preserves exact bytes. Their fixed membership is copied
                    # after release. Open/flat jobs can change and stay fenced.
                    elif _is_publication_job_path(relative) and not _immutable_publication_receipt(relative):
                        _capture_source(captured, staging, relative, source, False, deadline=deadline)
                # Only mutable mirrors and namespace identity are frozen here.
                # Canonical immutable closure resolves after WAL copy/release.
                with _capture_phase("recovery_mutable_pointers"):
                    _capture_mutable_recovery_pointers(root, staging, captured)
                    namespace_stamps = _capture_namespace_stamps(root, captured)
        finally:
            _CAPTURE_CLOSURE_BUDGET.reset(token)
        # The existing stall threshold bounds capture wall separately from the
        # unchanged 30s writer fence. No live config, lease or cadence changes.
        copy_deadline = capture_deadline
        token = _CAPTURE_CLOSURE_BUDGET.set({"deadline":copy_deadline,"counts":{},"bytes":0,
            "error_code":"BACKUP_CAPTURE_TOTAL_BUDGET_EXCEEDED",
            "namespace_stamps": {str(root / p): s for p, s in namespace_stamps.items()},
            "fallback_namespaces": set()})
        try:
            for relative, source, is_sqlite in sources:
                if relative in sqlite_readers:
                    staged = staging/relative
                    with _capture_phase("sqlite_copy_online", size=source.stat().st_size, count=1, source=relative):
                        consistent_sqlite_backup(source, staged, snapshot_connection=sqlite_readers[relative],
                            deadline_monotonic=copy_deadline, budget_error="BACKUP_CAPTURE_TOTAL_BUDGET_EXCEEDED")
                    # End WAL retention before SHA or other file copies.
                    sqlite_readers[relative].rollback()
                    sqlite_readers[relative].close()
                if is_sqlite:
                    staged = captured[relative]["staged"]
                    with _capture_phase("captured_sqlite_sha256", size=staged.stat().st_size, count=1, source=relative):
                        captured[relative].update(sha256=_sha256_file(staged), bytes=staged.stat().st_size)
            with _capture_phase("recovery_dependencies") as phase:
                _capture_recovery_dependencies(root, staging, captured)
                for directory in tuple(_CAPTURE_CLOSURE_BUDGET.get()["fallback_namespaces"]):
                    _capture_check_fallback_namespace(Path(directory))
                phase["count"] = len(captured)
                phase["bytes"] = sum(item.get("bytes", 0) for item in captured.values())
            with _capture_phase("control_verification"):
                _verify_recovery_control(staging)
            with _capture_phase("remaining_files") as phase:
                for relative, source, is_sqlite in sources:
                    if _immutable_publication_receipt(relative):
                        source = _safe_relative(root, relative)
                        if not _admit_backup_reclaim_source(source) or not source.is_file():
                            raise RemoteOpsError("BACKUP_SOURCE_CHANGED_DURING_CAPTURE")
                    _capture_source(captured, staging, relative, source, is_sqlite)
                phase["count"] = len(captured)
                phase["bytes"] = sum(item["bytes"] for item in captured.values())
        finally:
            _CAPTURE_CLOSURE_BUDGET.reset(token)
        yield BackupPayloadSnapshot(captured, captured_at=captured_at)


def scan_backup_inventory(
    root: Path,
    *,
    config: Mapping[str, Any] | None = None,
    snapshot: BackupPayloadSnapshot | None = None,
) -> dict[str, Any]:
    loaded = dict(config) if config is not None else load_config(root)
    loaded = _select_v1_1_config(root, loaded)
    if snapshot is None:
        with backup_payload_snapshot(root, loaded) as owned:
            return scan_backup_inventory(root, config=loaded, snapshot=owned)
    entries = [{"path": relative, **{key: captured[key] for key in ("sha256", "bytes", "kind")}}
               for relative, captured in snapshot.items()]
    return {
        "entries": entries,
        "inventory_sha256": logical_inventory_sha256(entries),
        "snapshot_data_as_of": snapshot.captured_at,
    }


def package_backup(
    root: Path,
    *,
    config: Mapping[str, Any] | None = None,
    sink_override: Path | None = None,
    environ: Mapping[str, str] | None = None,
    acquire_lock: bool = True,
    prune_superseded: bool | None = None,
    snapshot: BackupPayloadSnapshot | None = None,
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
                snapshot=snapshot,
            )
    loaded = dict(config) if config is not None else load_config(root)
    loaded = _select_v1_1_config(root, loaded)
    if snapshot is None:
        with backup_payload_snapshot(root, loaded) as owned:
            return package_backup(
                root,
                config=loaded,
                sink_override=sink_override,
                environ=environ,
                acquire_lock=False,
                prune_superseded=prune_superseded,
                snapshot=owned,
            )
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
    entries: list[dict[str, Any]] = []
    tmp = sink / f".packaging-{os.getpid()}-{time.time_ns()}.zip"
    with ExitStack():
        try:
            with zipfile.ZipFile(
                tmp,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=1,
                allowZip64=True,
            ) as archive:
                for relative, captured in snapshot.items():
                    digest, size = _stream_zip_entry(
                        archive, relative, snapshot.staged_path(relative)
                    )
                    if digest != str(captured["sha256"]) or size != int(captured["bytes"]):
                        raise RemoteOpsError("SNAPSHOT_BYTES_MISMATCH")
                    entries.append(
                        {
                            "path": relative,
                            "sha256": digest,
                            "bytes": size,
                            "kind": str(captured["kind"]),
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
                    "snapshot_data_as_of": snapshot.captured_at,
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
                info.compress_type = zipfile.ZIP_DEFLATED
                info.compress_level = 1
                archive.writestr(
                    info, json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
                )
            _fsync_file(tmp)
            published_manifest = read_backup_manifest(tmp)
            if str(published_manifest.get("inventory_sha256")) != inventory_sha256:
                raise RemoteOpsError("BACKUP_MANIFEST_INVENTORY_MISMATCH")
            _verify_archive_payload(tmp, "BACKUP_MANIFEST.json", entries)
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
        pruned = prune_superseded_local_backups(sink, dest, protected_bundles=sorted(_local_recovery_references(root)))
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
    snapshot: BackupPayloadSnapshot | None = None,
) -> dict[str, Any]:
    if acquire_lock:
        with backup_plane_lock(root):
            return package_delta_backup(
                root,
                base_manifest=base_manifest,
                current_entries=current_entries,
                sink=sink,
                acquire_lock=False,
                snapshot=snapshot,
            )
    if snapshot is None:
        if any(_is_publication_job_path(str(item.get("path", ""))) for item in current_entries):
            raise RemoteOpsError("MUTABLE_SNAPSHOT_REQUIRED")
        config = {"schema_version": "1.1", "backup": {
            "source_relative_paths": [str(item["path"]) for item in current_entries],
            "recursive_relative_paths": [],
        }}
        with backup_payload_snapshot(root, config) as owned:
            return package_delta_backup(root, base_manifest=base_manifest,
                                        current_entries=current_entries, sink=sink,
                                        snapshot=owned)
    sink.mkdir(parents=True, exist_ok=True)
    base_by_path = _validated_entries(base_manifest.get("entries"), "BACKUP_MANIFEST_INVALID")
    current_by_path = _validated_entries(list(current_entries), "BACKUP_MANIFEST_INVALID")
    captured_inventory = scan_backup_inventory(root, config={"schema_version": "1.1"}, snapshot=snapshot)
    if logical_inventory_sha256(current_entries) != captured_inventory["inventory_sha256"]:
        raise RemoteOpsError("SNAPSHOT_BYTES_MISMATCH")
    changed: list[dict[str, Any]] = []
    deleted: list[str] = []
    for path, item in current_by_path.items():
        prior = base_by_path.get(path)
        if prior is None or (prior["sha256"], prior["bytes"]) != (item["sha256"], item["bytes"]):
            changed.append(dict(item))
    for path in base_by_path:
        if path not in current_by_path:
            deleted.append(path)
    result_inventory_sha256 = logical_inventory_sha256(current_entries)
    base_inventory_sha256 = str(
        base_manifest.get("inventory_sha256")
        or logical_inventory_sha256(list(base_by_path.values()))
    )
    if base_inventory_sha256 != logical_inventory_sha256(list(base_by_path.values())):
        raise RemoteOpsError("DELTA_BASE_INVENTORY_MISMATCH")
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
        with zipfile.ZipFile(tmp, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
            packed_changed: list[dict[str, Any]] = []
            for item in changed:
                relative = str(item["path"])
                source = snapshot.staged_path(relative)
                digest, size = _stream_zip_entry(archive, relative, source)
                kind = str(snapshot.entry(relative)["kind"])
                if digest != item["sha256"] or size != item["bytes"]:
                    raise RemoteOpsError("SNAPSHOT_BYTES_MISMATCH")
                packed_changed.append(
                    {"path": relative, "sha256": digest, "bytes": size, "kind": kind}
                )
            delta_manifest = {
                "kind": "FACTORY_REMOTE_BACKUP_DELTA_MANIFEST",
                "schema_version": "1.0",
                "created_at": _now(),
                "snapshot_data_as_of": snapshot.captured_at,
                "base_inventory_sha256": base_inventory_sha256,
                "result_inventory_sha256": result_inventory_sha256,
                "changed": packed_changed,
                "deleted": sorted(deleted),
            }
            info = zipfile.ZipInfo(filename="DELTA_MANIFEST.json", date_time=ZIP_TIMESTAMP)
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.compress_level = 1
            archive.writestr(
                info, json.dumps(delta_manifest, indent=2, sort_keys=True).encode("utf-8")
            )
        _fsync_file(tmp)
        _verify_archive_payload(tmp, "DELTA_MANIFEST.json", packed_changed)
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


def _archive_path(relative: Any) -> str:
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or "\x00" in relative or ":" in relative
            or PurePosixPath(relative).is_absolute()
            or PureWindowsPath(relative).drive
            or any(part in {"", ".", ".."} or part.rstrip(" .") != part
                   or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
                   for part in relative.split("/"))):
        raise RemoteOpsError("BACKUP_ENTRY_UNSAFE")
    return relative


def _validated_entries(entries: Any, error: str) -> dict[str, dict[str, Any]]:
    if not isinstance(entries, list):
        raise RemoteOpsError(error)
    result: dict[str, dict[str, Any]] = {}
    folded: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise RemoteOpsError(error)
        path = _archive_path(item.get("path"))
        if _sqlite_sidecar_main(path) is not None:
            raise RemoteOpsError("BACKUP_SQLITE_SIDECAR_CONFLICT")
        digest, size = item.get("sha256"), item.get("bytes")
        if (path.casefold() in folded or path in {"BACKUP_MANIFEST.json", "DELTA_MANIFEST.json"}
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or type(size) is not int or size < 0):
            raise RemoteOpsError(error)
        result[path] = dict(item)
        folded.add(path.casefold())
    if any(parent.as_posix().casefold() in folded for path in result for parent in PurePosixPath(path).parents if parent != PurePosixPath(".")):
        raise RemoteOpsError(error)
    return result


def _archive_manifest(archive: zipfile.ZipFile, manifest_name: str) -> dict[str, Any]:
    names = archive.namelist()
    if manifest_name not in names:
        raise RemoteOpsError("BACKUP_MANIFEST_MISSING" if manifest_name.startswith("BACKUP") else "DELTA_MANIFEST_MISSING")
    if len(names) != len(set(names)):
        raise RemoteOpsError("BACKUP_ARCHIVE_ENTRIES_INVALID")
    for info in archive.infolist():
        _archive_path(info.filename)
        mode = (info.external_attr >> 16) & 0o170000
        if info.is_dir() or mode not in {0, 0o100000}:
            raise RemoteOpsError("BACKUP_ENTRY_UNSAFE")
    try:
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RemoteOpsError("BACKUP_MANIFEST_INVALID") from exc
    kind = "FACTORY_REMOTE_BACKUP_MANIFEST" if manifest_name.startswith("BACKUP") else "FACTORY_REMOTE_BACKUP_DELTA_MANIFEST"
    if not isinstance(manifest, dict) or manifest.get("kind") != kind:
        raise RemoteOpsError("BACKUP_MANIFEST_INVALID")
    entries = _validated_entries(manifest.get("entries" if manifest_name.startswith("BACKUP") else "changed"), "BACKUP_MANIFEST_INVALID")
    if set(names) != set(entries) | {manifest_name}:
        raise RemoteOpsError("BACKUP_MANIFEST_ENTRIES_MISMATCH")
    if manifest.get("schema_version") == "1.1" and any(
            path.endswith(".sqlite") and item.get("kind") != "SQLITE_BACKUP_API"
            for path, item in entries.items()):
        raise RemoteOpsError("BACKUP_MANIFEST_INVALID")
    for path, item in entries.items():
        if archive.getinfo(path).file_size != item["bytes"]:
            raise RemoteOpsError("BACKUP_ENTRY_SIZE_MISMATCH")
    return manifest


def _verify_archive_payload(bundle: Path, manifest_name: str, entries: Sequence[Mapping[str, Any]]) -> None:
    expected = _validated_entries(list(entries), "BACKUP_MANIFEST_INVALID")
    try:
        with zipfile.ZipFile(bundle) as archive:
            manifest = _archive_manifest(archive, manifest_name)
            declared = manifest["entries" if manifest_name.startswith("BACKUP") else "changed"]
            if logical_inventory_sha256(declared) != logical_inventory_sha256(list(expected.values())):
                raise RemoteOpsError("BACKUP_MANIFEST_INVENTORY_MISMATCH")
            for path, item in expected.items():
                digest, size = hashlib.sha256(), 0
                with archive.open(path) as source:
                    while chunk := source.read(BACKUP_STREAM_CHUNK):
                        digest.update(chunk)
                        size += len(chunk)
                if digest.hexdigest() != item["sha256"] or size != item["bytes"]:
                    raise RemoteOpsError("BACKUP_HASH_MISMATCH")
    except (zipfile.BadZipFile, OSError) as exc:
        raise RemoteOpsError("BACKUP_ARCHIVE_CORRUPT") from exc


def _filesystem_inventory(root: Path) -> list[dict[str, Any]]:
    """Independent oracle: enumerate and reopen extracted filesystem bytes."""
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RemoteOpsError("BACKUP_ENTRY_UNSAFE")
        if path.is_file():
            relative = _archive_path(path.relative_to(root).as_posix())
            entries.append({"path": relative, "bytes": path.stat().st_size,
                            "sha256": _sha256_file(path)})
    return entries


def _raw_inventory(root: Path, baseline: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    actual = _filesystem_inventory(root)
    by_path = {item["path"]: item for item in actual}
    for path, item in baseline.items():
        if by_path.get(path) != item:
            raise RemoteOpsError("RESTORE_UNRELATED_FILE_CHANGED")
    return [item for item in actual if item["path"] not in baseline]


def _check_inventory(root: Path, expected: str, baseline: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    actual = _raw_inventory(root, baseline)
    if logical_inventory_sha256(actual) != expected:
        raise RemoteOpsError("RESTORE_INVENTORY_MISMATCH")
    return actual


def _sqlite_restore_integrity(root: Path, entries: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    checked = []
    for item in entries:
        relative = str(item["path"])
        if not relative.endswith(".sqlite"):
            continue
        source = _safe_relative(root, relative)
        with source.open("rb") as handle:
            sqlite_header = handle.read(16) == b"SQLite format 3\x00"
        if not sqlite_header and item.get("kind") != "SQLITE_BACKUP_API":
            continue  # v1.0 opaque FILE_SNAPSHOT compatibility
        try:
            with closing(sqlite3.connect(source.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
                rows = conn.execute("PRAGMA integrity_check").fetchall()
                if rows != [("ok",)]:
                    raise RemoteOpsError("RESTORE_SQLITE_INTEGRITY_FAILED")
        except sqlite3.Error as exc:
            raise RemoteOpsError("RESTORE_SQLITE_INTEGRITY_FAILED") from exc
        checked.append({"path": relative, "result": "ok"})
    return checked


def _decorate_restore(root: Path, entries: Sequence[Mapping[str, Any]], recovery_identity: str) -> bool:
    _reject_restored_sqlite_sidecars(root, entries)
    stores = [str(item["path"]) for item in entries
              if str(item["path"]).endswith("observation_schedule_state.sqlite")]
    for relative in stores:
        with closing(sqlite3.connect(_safe_relative(root, relative))) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS restore_markers (
                marker_id TEXT PRIMARY KEY, recovery_epoch TEXT NOT NULL,
                resolved INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)""")
            epoch = f"RESTORE-{recovery_identity[:24]}"
            conn.execute("""INSERT INTO restore_markers VALUES ('UNRESOLVED', ?, 0, ?, ?)
                ON CONFLICT(marker_id) DO UPDATE SET recovery_epoch=excluded.recovery_epoch,
                resolved=0,payload_json=excluded.payload_json,created_at=excluded.created_at""",
                (epoch, json.dumps({"recovery_epoch": epoch}, sort_keys=True), _now()))
            conn.commit()
    return bool(stores)


def apply_delta_bundle(delta: Path, dest_root: Path, *,
                       _baseline: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    if not delta.is_file():
        raise RemoteOpsError("DELTA_BUNDLE_MISSING")
    if not DELTA_BUNDLE_NAME.fullmatch(delta.name) or delta.stem.removeprefix("DELTA_") != _sha256_file(delta):
        raise RemoteOpsError("DELTA_BUNDLE_HASH_MISMATCH")
    baseline = _baseline or {}
    try:
        with zipfile.ZipFile(delta) as archive:
            manifest = _archive_manifest(archive, "DELTA_MANIFEST.json")
            changed = _validated_entries(manifest["changed"], "DELTA_MANIFEST_INVALID")
            deleted = manifest.get("deleted")
            if not isinstance(deleted, list) or not all(isinstance(path, str) for path in deleted):
                raise RemoteOpsError("DELTA_MANIFEST_INVALID")
            for path in deleted:
                _archive_path(path)
            if len(deleted) != len(set(deleted)) or set(deleted) & set(changed) or set(deleted) & set(baseline):
                raise RemoteOpsError("DELTA_MANIFEST_INVALID")
            before = _check_inventory(dest_root, str(manifest.get("base_inventory_sha256")), baseline)
            before_by_path = {item["path"]: item for item in before}
            if not set(deleted) <= set(before_by_path) or set(changed) & set(baseline):
                raise RemoteOpsError("DELTA_MANIFEST_INVALID")
            # Verify the whole archive before mutating the disposable reconstruction.
            _verify_archive_payload(delta, "DELTA_MANIFEST.json", list(changed.values()))
            for path in deleted:
                _safe_relative(dest_root, path).unlink()
            for path, item in changed.items():
                target = _safe_relative(dest_root, path)
                if target.exists() and not target.is_file():
                    raise RemoteOpsError("BACKUP_ENTRY_UNSAFE")
                with archive.open(path) as source:
                    _stream_copy_hashed(source, target)
            actual = _check_inventory(dest_root, str(manifest.get("result_inventory_sha256")), baseline)
    except zipfile.BadZipFile as exc:
        raise RemoteOpsError("BACKUP_ARCHIVE_CORRUPT") from exc
    return {"applied": len(changed), "deleted": deleted,
            "inventory_sha256": logical_inventory_sha256(actual)}


def restore_backup_isolated(*, bundle: Path, dest_root: Path,
                            _raw_only: bool = False) -> dict[str, Any]:
    if not bundle.is_file():
        raise RemoteOpsError("BACKUP_BUNDLE_MISSING")
    digest = _sha256_file(bundle)
    if bundle.name.startswith("BACKUP_") and (
            not BACKUP_BUNDLE_NAME.fullmatch(bundle.name)
            or bundle.stem.removeprefix("BACKUP_") != digest):
        raise RemoteOpsError("BACKUP_BUNDLE_HASH_MISMATCH")
    if (not dest_root.is_absolute() or dest_root.resolve() == bundle.parent.resolve()
            or dest_root.is_symlink()):
        raise RemoteOpsError("RESTORE_ROOT_NOT_ISOLATED")
    _reject_symlink_components(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    baseline = {item["path"]: item for item in _filesystem_inventory(dest_root)}
    try:
        with zipfile.ZipFile(bundle) as archive:
            manifest = _archive_manifest(archive, "BACKUP_MANIFEST.json")
            entries = _validated_entries(manifest["entries"], "BACKUP_MANIFEST_INVALID")
            inventory = logical_inventory_sha256(list(entries.values()))
            if str(manifest.get("inventory_sha256") or inventory) != inventory:
                raise RemoteOpsError("BACKUP_MANIFEST_INVENTORY_MISMATCH")
            if set(entries) & set(baseline):
                raise RemoteOpsError("RESTORE_TARGET_EXISTS")
            _reject_restored_sqlite_sidecars(dest_root, list(entries.values()))
            _verify_archive_payload(bundle, "BACKUP_MANIFEST.json", list(entries.values()))
            for path in entries:
                target = _safe_relative(dest_root, path)
                with archive.open(path) as source:
                    _stream_copy_hashed(source, target)
    except zipfile.BadZipFile as exc:
        raise RemoteOpsError("BACKUP_ARCHIVE_CORRUPT") from exc
    actual = _check_inventory(dest_root, inventory, baseline)
    integrity = _sqlite_restore_integrity(dest_root, list(entries.values()))
    # A legacy mutable-only full can acquire its required ResearchEvents from
    # later deltas. Its raw bytes remain verified here; semantic closure belongs
    # to the final reconstruction. Standalone full restore still requires it.
    control = None if _raw_only else _verify_recovery_control(dest_root)
    rdp = [item for item in entries.values() if str(item["path"]).startswith("local/factory_v1/observation_rdp/")]
    journals = [item for item in entries.values() if "/publication_jobs/" in str(item["path"]) or "/journals/" in str(item["path"])]
    for key, items in (("rdp_inventory", rdp), ("active_journal_inventory", journals)):
        summary = manifest.get(key)
        if summary and (summary.get("count") != len(items) or summary.get("fingerprint") != _sha256_bytes(json.dumps(items, sort_keys=True).encode("utf-8"))):
            raise RemoteOpsError("BACKUP_RDP_INVENTORY_MISMATCH" if key == "rdp_inventory" else "BACKUP_JOURNAL_INVENTORY_MISMATCH")
    marked = False if _raw_only else _decorate_restore(dest_root, actual, digest)
    return {"restored": actual, "count": len(actual), "sqlite_integrity": integrity,
            "raw_inventory_sha256": inventory, "inventory_sha256": inventory,
            "rdp_inventory": {"count": len(rdp), "fingerprint": _sha256_bytes(json.dumps(rdp, sort_keys=True).encode("utf-8"))},
            "active_journal_inventory": {"count": len(journals), "fingerprint": _sha256_bytes(json.dumps(journals, sort_keys=True).encode("utf-8"))},
            "recovery_control": control, "recovery_gap": marked, "restore_marker_unresolved": marked}


def restore_incremental_chain_isolated(*, full_bundle: Path, deltas: Sequence[Path],
                                      dest_root: Path, expected_inventory_sha256: str | None = None) -> dict[str, Any]:
    baseline = {item["path"]: item for item in _filesystem_inventory(dest_root)} if dest_root.exists() else {}
    restored = restore_backup_isolated(bundle=full_bundle, dest_root=dest_root, _raw_only=True)
    applied = [apply_delta_bundle(delta, dest_root, _baseline=baseline) for delta in deltas]
    inventory = applied[-1]["inventory_sha256"] if applied else restored["raw_inventory_sha256"]
    actual = _check_inventory(dest_root, expected_inventory_sha256 or inventory, baseline)
    integrity = _sqlite_restore_integrity(dest_root, actual)
    control = _verify_recovery_control(dest_root)
    # The raw oracle has finished. Only now may the recovery decoration change DB bytes.
    marked = _decorate_restore(dest_root, actual, inventory)
    rdp_count = sum(str(item["path"]).startswith("local/factory_v1/observation_rdp/") for item in actual)
    return {**restored, "restored": actual, "count": len(actual), "sqlite_integrity": integrity,
            "deltas_applied": applied, "rdp_file_count": rdp_count,
            "raw_inventory_sha256": inventory, "inventory_sha256": inventory,
            "recovery_control": control, "recovery_gap": marked, "restore_marker_unresolved": marked,
            "terminal": "NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF_PASS" if rdp_count else "EMPTY_RDP_INCREMENTAL_RESTORE",
            "expected_inventory_sha256": expected_inventory_sha256}


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
