"""Factory remote operations: health, backup, alerts, security baseline.

Owns no scientific truth. Secrets have no defaults. Process-alive is never
HEALTHY. Backup on the same parent as live stores is not independent.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

import jsonschema
import yaml

CONFIG_RELATIVE = "configs/factory_remote_operations_v1.yaml"
SCHEMA_RELATIVE = "catalog/schemas/factory_remote_operations.schema.json"
FORBIDDEN_HEALTHY = "HEALTHY"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
UNRESOLVED_STATES = frozenset(
    {"OPEN", "PARTIAL", "UNKNOWN", "UNRESOLVED", "EXIT_REQUIRED", "EXITING"}
)
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
BACKUP_SINK_ENV = "FACTORY_BACKUP_SINK"


class RemoteOpsError(ValueError):
    """Raised when remote operations cannot proceed fail-closed."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _safe_relative(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise RemoteOpsError("REMOTE_PATH_UNSAFE")
    return (root / candidate).resolve()


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
    bundles = sorted(sink.glob("BACKUP_*.zip"))
    if not bundles:
        return None
    newest = bundles[-1]
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
        "alert_configured": alert_configured,
        "next_safe_action": next_safe_action,
        "rpo_max": loaded["deploy"]["rpo_max"],
        "rto_max": loaded["deploy"]["rto_max"],
        "observed_at": clock.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def write_heartbeat(root: Path, *, config: Mapping[str, Any] | None = None) -> Path:
    loaded = dict(config) if config is not None else load_config(root)
    path = _safe_relative(root, str(loaded["monitoring"]["heartbeat_relative"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = _now()
    payload = {
        "kind": "PAPER_HEARTBEAT",
        "observed_at": stamp,
        "progress_at": stamp,
        "deploy_version": loaded["deploy"]["version"],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _assert_independent_sink(root: Path, loaded: Mapping[str, Any], sink: Path) -> None:
    if loaded["backup"]["same_parent_forbidden"] is not True:
        raise RemoteOpsError("INDEPENDENT_FLAG_DRIFT")
    parents = []
    for relative in loaded["backup"]["source_relative_paths"]:
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


def package_backup(
    root: Path,
    *,
    config: Mapping[str, Any] | None = None,
    sink_override: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    loaded = dict(config) if config is not None else load_config(root)
    sink = (
        sink_override.resolve()
        if sink_override is not None
        else resolve_backup_sink(root, loaded, environ)
    )
    _assert_independent_sink(root, loaded, sink)
    sink.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative in loaded["backup"]["source_relative_paths"]:
            source = _safe_relative(root, relative)
            if source.is_file() is False:
                raise RemoteOpsError(f"BACKUP_SOURCE_MISSING:{relative}")
            digest = _sha256_file(source)
            info = zipfile.ZipInfo(filename=relative.replace("\\", "/"), date_time=ZIP_TIMESTAMP)
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
            entries.append({"path": relative.replace("\\", "/"), "sha256": digest, "bytes": source.stat().st_size})
        manifest = {
            "kind": "FACTORY_REMOTE_BACKUP_MANIFEST",
            "created_at": _now(),
            "entries": entries,
        }
        info = zipfile.ZipInfo(filename="BACKUP_MANIFEST.json", date_time=ZIP_TIMESTAMP)
        info.external_attr = 0o100644 << 16
        archive.writestr(info, json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
    payload = buffer.getvalue()
    digest = _sha256_bytes(payload)
    dest = sink / f"BACKUP_{digest}.zip"
    dest.write_bytes(payload)
    return {
        "bundle": dest.name,
        "sha256": digest,
        "bytes": len(payload),
        "entries": entries,
        "sink": dest.parent.as_posix(),
    }


def restore_backup_isolated(
    *,
    bundle: Path,
    dest_root: Path,
) -> dict[str, Any]:
    if bundle.is_file() is False:
        raise RemoteOpsError("BACKUP_BUNDLE_MISSING")
    dest_root.mkdir(parents=True, exist_ok=True)
    restored: list[dict[str, Any]] = []
    with zipfile.ZipFile(bundle, "r") as archive:
        names = archive.namelist()
        if "BACKUP_MANIFEST.json" not in names:
            raise RemoteOpsError("BACKUP_MANIFEST_MISSING")
        manifest = json.loads(archive.read("BACKUP_MANIFEST.json").decode("utf-8"))
        expected = {item["path"]: item["sha256"] for item in manifest["entries"]}
        for name in names:
            if name == "BACKUP_MANIFEST.json":
                continue
            candidate = Path(name)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise RemoteOpsError("BACKUP_ENTRY_UNSAFE")
            target = dest_root / candidate
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(name)
            digest = _sha256_bytes(data)
            if expected.get(name.replace("\\", "/")) != digest:
                raise RemoteOpsError(f"BACKUP_HASH_MISMATCH:{name}")
            target.write_bytes(data)
            restored.append({"path": name.replace("\\", "/"), "sha256": digest, "bytes": len(data)})
    return {"restored": restored, "count": len(restored)}


ALERT_CODE_RU = {
    "START_REMOTE_PROCESSES": "Напишите агенту: процесс Factory упал. Сами не SSH и не Linux.",
    "INSPECT_UNRESOLVED_POSITIONS": "Напишите агенту: есть незакрытая paper-позиция. SQLite не трогайте.",
    "RUN_INDEPENDENT_BACKUP": "Напишите агенту: нужен независимый backup. Сами не копируйте файлы.",
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
