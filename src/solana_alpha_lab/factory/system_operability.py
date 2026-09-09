"""SystemOperabilityProjectionV2. Derived current-health composition. Persists nowhere."""

from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from solana_alpha_lab.factory.external_heartbeat import HEARTBEAT_ENV, UNCONFIGURED
from solana_alpha_lab.factory.observation_schedule import render_utc
from solana_alpha_lab.factory.observation_schedule_runtime import DEPLOY_SHA_NAME
from solana_alpha_lab.factory.operability_watch import (
    SNAPSHOT_RELATIVE as COLLECTOR_SNAPSHOT_RELATIVE,
    STATE_RELATIVE as INCIDENT_STATE_RELATIVE,
    WATCH_REQUIRED_TIMERS,
    WATCH_WORKBENCH_UNIT,
    classify_incidents,
    evaluate_collector_snapshot_freshness,
    load_collector_snapshot_file,
)

SCHEMA = "smial.system-operability-projection"
SCHEMA_VERSION = "2.0"
OBS_SQLITE_RELATIVE = "local/factory_v1/observation_schedule_state.sqlite"
OBS_RUNTIME_RELATIVE = "configs/observation_schedule_runtime_v1.yaml"
CAPABILITY_RUNTIME_RELATIVE = "configs/factory_v1_production_lite_runtime_v1.yaml"
UNATTENDED_RUNBOOK = "docs/operator/FACTORY_UNATTENDED_OPERABILITY.md"
REMOTE_HOST_RUNBOOK = "docs/operator/FACTORY_REMOTE_HOST.md"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
SYSTEMD_UNAVAILABLE = "SYSTEMD_READBACK_UNAVAILABLE"
HTTP_SERVING = "SERVING_NOW"
UnitReader = Callable[[str], str]

NON_CLAIMS = (
    "NO ALPHA",
    "NO LIVE",
    "NO REAL MONEY",
    "NO OWNER FCF",
    "NO DEPLOY",
    "NO PROVIDER CALL",
    "NO DRIVE WRITE",
    "NO TELEGRAM SEND",
    "NO WALLET",
    "NO SYSTEM HEALTH FROM GIT",
    "NO MONITORING PLATFORM",
    "NO CANONICAL DONE",
    "NO SYNCHRONOUS_COLLECTOR_RECOMPUTE_ON_GET",
)

RECOVERY_ROUTE = {
    "SOURCE_DATA_STALE": UNATTENDED_RUNBOOK,
    "PUBLICATION_STUCK": UNATTENDED_RUNBOOK,
    "PUBLICATION_FAILED": UNATTENDED_RUNBOOK,
    "REQUIRED_TIMER_FAILED": UNATTENDED_RUNBOOK,
    "WORKBENCH_SERVICE_DOWN": UNATTENDED_RUNBOOK,
    "MUTABLE_BACKUP_STALE": UNATTENDED_RUNBOOK,
    "MUTABLE_BACKUP_FAILED": UNATTENDED_RUNBOOK,
    "OFFHOST_BACKUP_STALE": UNATTENDED_RUNBOOK,
    "OFFHOST_BACKUP_FAILED": UNATTENDED_RUNBOOK,
    "IMMUTABLE_ARCHIVE_STALE": UNATTENDED_RUNBOOK,
    "IMMUTABLE_ARCHIVE_UPLOAD_FAILED": UNATTENDED_RUNBOOK,
    "IMMUTABLE_ARCHIVE_HASH_MISMATCH": UNATTENDED_RUNBOOK,
    "DISK_RUNWAY_TARGET40": UNATTENDED_RUNBOOK,
    "DISK_RUNWAY_HARD50": UNATTENDED_RUNBOOK,
    "SUSTAINED_PROVIDER_FAILURE": UNATTENDED_RUNBOOK,
    "MATERIAL_COVERAGE_DEGRADATION": UNATTENDED_RUNBOOK,
    "ALERTING_UNAVAILABLE": UNATTENDED_RUNBOOK,
    "DEPLOY_IDENTITY_MISMATCH": REMOTE_HOST_RUNBOOK,
    "COLLECTOR_SNAPSHOT_MISSING": UNATTENDED_RUNBOOK,
    "COLLECTOR_SNAPSHOT_STALE": UNATTENDED_RUNBOOK,
    "COLLECTOR_SNAPSHOT_INVALID": UNATTENDED_RUNBOOK,
}

AUTHORITY_CODES = frozenset(
    {
        "REQUIRED_TIMER_FAILED",
        "WORKBENCH_SERVICE_DOWN",
        "DEPLOY_IDENTITY_MISMATCH",
    }
)

COVERAGE_GROUPS = (
    "HTTP_SELF",
    "SYSTEMD",
    "COLLECTOR",
    "DATA_FRESHNESS",
    "PROVIDER_OBSERVATIONS",
    "STORAGE",
    "MUTABLE_BACKUP",
    "OFFHOST_BACKUP",
    "IMMUTABLE_ARCHIVE",
    "DEPLOY_IDENTITY",
    "ALERTING",
    "OUT_OF_BAND_HOST_REACHABILITY",
)


def _utc_now(clock: datetime | None = None) -> datetime:
    value = clock or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _coverage(status: str, *, detail: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"status": status}
    if detail:
        row["detail"] = detail
    return row


def observation_sqlite_path(root: Path) -> Path:
    runtime_path = root / OBS_RUNTIME_RELATIVE
    if runtime_path.is_file():
        try:
            loaded = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            loaded = None
        if isinstance(loaded, dict):
            rel = loaded.get("ops_store_relative")
            if isinstance(rel, str) and rel.strip():
                return (root / rel).resolve()
    return (root / OBS_SQLITE_RELATIVE).resolve()


def read_deploy_marker(root: Path) -> str | None:
    marker = root / DEPLOY_SHA_NAME
    try:
        if marker.is_symlink() or marker.is_file() is False:
            return None
        if marker.resolve().parent != root.resolve():
            return None
        text = marker.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if _SHA40.fullmatch(text) is None:
        return None
    return text


def read_git_head(root: Path) -> str | None:
    git_dir = root / ".git"
    if git_dir.exists() is False:
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        value = completed.stdout.decode("ascii").strip()
    except UnicodeDecodeError:
        return None
    if _SHA40.fullmatch(value) is None:
        return None
    return value


def read_capability_deploy_version(root: Path) -> str | None:
    path = root / CAPABILITY_RUNTIME_RELATIVE
    if path.is_file() is False:
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(loaded, dict):
        return None
    value = loaded.get("deploy_version")
    return str(value) if value else None


def default_unit_reader(unit: str) -> str:
    try:
        completed = subprocess.run(
            ["systemctl", "is-active", unit],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except FileNotFoundError:
        return SYSTEMD_UNAVAILABLE
    except (OSError, subprocess.TimeoutExpired):
        return SYSTEMD_UNAVAILABLE
    status = (completed.stdout or "").strip()
    if status:
        return status
    return SYSTEMD_UNAVAILABLE


def read_required_units(
    *,
    unit_status: Mapping[str, str] | None = None,
    unit_reader: UnitReader | None = None,
) -> dict[str, str]:
    required = (*WATCH_REQUIRED_TIMERS, WATCH_WORKBENCH_UNIT)
    if unit_status is not None:
        units = {str(name): str(value) for name, value in unit_status.items()}
        for name in required:
            units.setdefault(name, SYSTEMD_UNAVAILABLE)
        return units
    reader = unit_reader or default_unit_reader
    return {name: reader(name) for name in required}


def _systemd_coverage(units: Mapping[str, str]) -> dict[str, Any]:
    values = list(units.values())
    if values and all(item == SYSTEMD_UNAVAILABLE for item in values):
        return _coverage("UNAVAILABLE", detail=SYSTEMD_UNAVAILABLE)
    if any(item == SYSTEMD_UNAVAILABLE for item in values):
        return _coverage("PARTIAL", detail=SYSTEMD_UNAVAILABLE)
    return _coverage("AVAILABLE")


def _telegram_class(environ: Mapping[str, str]) -> dict[str, Any]:
    token_set = bool(_text(environ.get("FACTORY_TELEGRAM_BOT_TOKEN")))
    chat_set = bool(_text(environ.get("FACTORY_TELEGRAM_CHAT_ID")))
    if token_set and chat_set:
        return {
            "status": "CONFIGURED",
            "delivery": "NOT_PROVED",
        }
    if token_set or chat_set:
        return {
            "status": "PARTIAL",
            "delivery": "NOT_PROVED",
        }
    return {
        "status": "NOT_CONFIGURED",
        "delivery": "NOT_PROVED",
    }


def _heartbeat_class(environ: Mapping[str, str]) -> dict[str, Any]:
    url = _text(environ.get(HEARTBEAT_ENV))
    if url == "":
        return _coverage("NOT_CONFIGURED", detail=UNCONFIGURED)
    return _coverage("CONFIGURED", detail="URL_PRESENT_NOT_PROBED")


def _attention_card(
    code: str,
    *,
    evidence: str,
    current_safe_state: str,
    next_safe_action: str,
    observed_at: str,
) -> dict[str, Any]:
    authority = code in AUTHORITY_CODES
    return {
        "attention_code": code,
        "native_identity": code,
        "WHAT": code,
        "WHY_NOW": evidence,
        "IMPACT": "P1",
        "EVIDENCE": evidence,
        "CURRENT_SAFE_STATE": current_safe_state,
        "NEXT_SAFE_ACTION": next_safe_action,
        "RECOVERY_ROUTE": RECOVERY_ROUTE.get(code, UNATTENDED_RUNBOOK),
        "AUTHORITY_REQUIRED": authority,
        "observed_at": observed_at,
        "source_domain": "SYSTEM",
        "source_owner": "SYSTEM_OPERABILITY_SURFACE_V2",
        "drilldown_target": "/system",
    }


def _next_action_for(code: str) -> str:
    if code == "REQUIRED_TIMER_FAILED":
        return "FOLLOW_UNATTENDED_TIMER_RECOVERY"
    if code == "WORKBENCH_SERVICE_DOWN":
        return "FOLLOW_UNATTENDED_WORKBENCH_RECOVERY"
    if code == "DEPLOY_IDENTITY_MISMATCH":
        return "FOLLOW_DEPLOY_BOUNDARY"
    if code.startswith("DISK_RUNWAY_"):
        return "FOLLOW_STORAGE_RUNWAY_RECOVERY"
    if "BACKUP" in code or "ARCHIVE" in code:
        return "FOLLOW_DURABILITY_RUNBOOK"
    if code in {"SOURCE_DATA_STALE", "PUBLICATION_STUCK", "PUBLICATION_FAILED"}:
        return "INSPECT_COLLECTOR_FRESHNESS"
    if code == "COLLECTOR_SNAPSHOT_MISSING":
        return "WAIT_ONE_WATCH_CYCLE"
    if code in {"COLLECTOR_SNAPSHOT_STALE", "COLLECTOR_SNAPSHOT_INVALID"}:
        return "INSPECT_COLLECTOR_FRESHNESS"
    return "INSPECT_SYSTEM"


_UNOBSERVED = frozenset(
    {
        "",
        "UNKNOWN",
        "UNCONFIGURED",
        "NOT_CONFIGURED",
        "NOT_PRESENT",
        "NOT_APPLICABLE",
        "EXPLICIT_UNKNOWN",
        "N/A",
        "NONE",
        "NULL",
    }
)


def _observed(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return True
    text = _text(value)
    if not text:
        return False
    return text.upper() not in _UNOBSERVED


def _evidence_status(
    *,
    action: bool = False,
    degraded: bool = False,
    not_configured: bool = False,
    present: bool = False,
) -> str:
    if action:
        return "ACTION_REQUIRED"
    if not_configured:
        return "NOT_CONFIGURED"
    if degraded:
        return "DEGRADED"
    if present:
        return "AVAILABLE"
    return "UNKNOWN"


def _map_packet_coverage(packet: Mapping[str, Any] | None, *, source_status: str) -> dict[str, Any]:
    if packet is None:
        missing = "NOT_PRESENT" if source_status == "NOT_PRESENT" else source_status
        return {
            "COLLECTOR": _coverage(missing),
            "DATA_FRESHNESS": _coverage(missing),
            "PROVIDER_OBSERVATIONS": _coverage(missing),
            "STORAGE": _coverage(missing),
            "MUTABLE_BACKUP": _coverage(missing),
            "OFFHOST_BACKUP": _coverage(missing),
            "IMMUTABLE_ARCHIVE": _coverage(missing),
        }
    classes = {str(item) for item in (packet.get("health_classes") or [])}
    offhost_state = _text(packet.get("offhost_backup_state")).upper()
    freshness = _evidence_status(
        degraded="DATA_STALE" in classes,
        present=_observed(packet.get("collector_verdict")),
    )
    provider = _evidence_status(
        degraded=bool(
            classes
            & {
                "PROVIDER_FAILED",
                "PROVIDER_AUTH_FAILED",
                "PROVIDER_RATE_LIMITED",
            }
        ),
        present=_observed(packet.get("provider_observations")),
    )
    storage = _evidence_status(
        action=bool(classes & {"DISK_RUNWAY_HARD50", "DISK_CRITICAL"}),
        degraded=bool(classes & {"DISK_RUNWAY_TARGET40", "DISK_WARNING"}),
        present=_observed(packet.get("filesystem_disk_used_pct"))
        and _observed(packet.get("projected_97d_status")),
    )
    mutable = _evidence_status(
        degraded=bool(classes & {"BACKUP_DEGRADED", "MUTABLE_BACKUP_FULL_RDP_UNEXPECTED"}),
        present=_observed(packet.get("backup_age_seconds")),
    )
    offhost = _evidence_status(
        degraded=bool(classes & {"OFFHOST_BACKUP_STALE", "OFFHOST_BACKUP_FAILED"})
        or offhost_state in {"STALE", "FAILED"},
        not_configured=offhost_state in {"UNCONFIGURED", "NOT_CONFIGURED", "LOCAL_ONLY"},
        present=offhost_state in {"CURRENT", "OK", "AVAILABLE"},
    )
    archive = _evidence_status(
        action="IMMUTABLE_ARCHIVE_HASH_MISMATCH" in classes,
        degraded="IMMUTABLE_ARCHIVE_STALE" in classes,
        present=_observed(packet.get("immutable_archive_latest_verified_day")),
    )
    mapped = {
        "COLLECTOR": _coverage("AVAILABLE"),
        "DATA_FRESHNESS": _coverage(freshness),
        "PROVIDER_OBSERVATIONS": _coverage(provider),
        "STORAGE": _coverage(storage),
        "MUTABLE_BACKUP": _coverage(mutable),
        "OFFHOST_BACKUP": _coverage(offhost),
        "IMMUTABLE_ARCHIVE": _coverage(archive),
    }
    if source_status == "STALE":
        for row in mapped.values():
            if row.get("status") == "AVAILABLE":
                row["status"] = "STALE"
    return mapped


def _rollup_state(
    *,
    attention: list[Mapping[str, Any]],
    coverage: Mapping[str, Mapping[str, Any]],
    collector_verdict: str | None,
) -> str:
    codes = {str(item.get("attention_code") or "") for item in attention}
    action_codes = {
        "DISK_RUNWAY_HARD50",
        "IMMUTABLE_ARCHIVE_HASH_MISMATCH",
        "WORKBENCH_SERVICE_DOWN",
        "REQUIRED_TIMER_FAILED",
        "SQLITE_INTEGRITY_FAILED",
        "ALERTING_UNAVAILABLE",
        "MUTABLE_BACKUP_FAILED",
        "OFFHOST_BACKUP_FAILED",
        "IMMUTABLE_ARCHIVE_UPLOAD_FAILED",
    }
    if codes & action_codes or collector_verdict == "ACTION_REQUIRED":
        return "ACTION_REQUIRED"
    material = (
        "SYSTEMD",
        "COLLECTOR",
        "DATA_FRESHNESS",
        "STORAGE",
        "MUTABLE_BACKUP",
        "OFFHOST_BACKUP",
        "IMMUTABLE_ARCHIVE",
        "DEPLOY_IDENTITY",
    )
    statuses = [str(coverage.get(name, {}).get("status") or "") for name in material]
    if any(status == "ACTION_REQUIRED" for status in statuses):
        return "ACTION_REQUIRED"
    if (
        (codes - {"COLLECTOR_SNAPSHOT_MISSING", "COLLECTOR_SNAPSHOT_STALE", "COLLECTOR_SNAPSHOT_INVALID"})
        or collector_verdict == "DEGRADED"
        or any(status == "DEGRADED" for status in statuses)
    ):
        return "DEGRADED"
    blocked = {
        "UNAVAILABLE",
        "NOT_PRESENT",
        "INVALID",
        "PARTIAL",
        "UNKNOWN",
        "NOT_CONFIGURED",
        "STALE",
        "MISSING",
    }
    if any(status in blocked for status in statuses):
        return "UNKNOWN"
    return "OK_OBSERVED"


def _snapshot_meta(
    *,
    freshness: str,
    observed_at: str | None = None,
    age_seconds: int | None = None,
) -> dict[str, Any]:
    return {
        "freshness": freshness,
        "observed_at": observed_at,
        "age_seconds": age_seconds,
    }


def _open_collector(
    root: Path,
    *,
    now: datetime,
    injected: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any] | None, str, dict[str, Any]]:
    if injected is not None:
        return injected, "PRESENT", _snapshot_meta(freshness="INJECTED")
    shape, snapshot = load_collector_snapshot_file(root / COLLECTOR_SNAPSHOT_RELATIVE)
    if shape == "MISSING":
        return None, "NOT_PRESENT", _snapshot_meta(freshness="MISSING")
    if shape == "INVALID" or snapshot is None:
        return None, "INVALID", _snapshot_meta(freshness="INVALID")
    source_observed = str(snapshot.get("observed_at") or "")
    freshness, age = evaluate_collector_snapshot_freshness(observed_at=source_observed, now=now)
    meta = _snapshot_meta(
        freshness=freshness,
        observed_at=source_observed,
        age_seconds=age,
    )
    if freshness == "INVALID":
        return None, "INVALID", meta
    packet = snapshot.get("packet")
    if not isinstance(packet, dict):
        return None, "INVALID", _snapshot_meta(freshness="INVALID", observed_at=source_observed)
    if freshness == "STALE":
        return packet, "STALE", meta
    return packet, "PRESENT", meta


def compose_system_operability(
    *,
    root: Path,
    now: datetime | None = None,
    http_self: str = "NOT_APPLICABLE",
    unit_status: Mapping[str, str] | None = None,
    unit_reader: UnitReader | None = None,
    collector_packet: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    clock = _utc_now(now)
    observed_at = render_utc(clock)
    env = {str(key): str(value) for key, value in (environ if environ is not None else os.environ).items()}
    units = read_required_units(unit_status=unit_status, unit_reader=unit_reader)
    packet, collector_status, snapshot_meta = _open_collector(
        root, now=clock, injected=collector_packet
    )
    systemd_units = dict(units)
    if _systemd_coverage(units)["status"] == "UNAVAILABLE":
        classified_units = {
            name: SYSTEMD_UNAVAILABLE for name in (*WATCH_REQUIRED_TIMERS, WATCH_WORKBENCH_UNIT)
        }
    else:
        classified_units = systemd_units
    incidents = classify_incidents(packet or {}, unit_status=classified_units)
    classes = {str(item) for item in ((packet or {}).get("health_classes") or [])}
    if "OFFHOST_BACKUP_STALE" in classes:
        incidents.setdefault(
            "OFFHOST_BACKUP_STALE", "Off-host backup freshness degraded."
        )
    if "OFFHOST_BACKUP_FAILED" in classes:
        incidents.setdefault("OFFHOST_BACKUP_FAILED", "Off-host backup failed.")
    attention = [
        _attention_card(
            code,
            evidence=detail,
            current_safe_state="DEGRADED",
            next_safe_action=_next_action_for(code),
            observed_at=observed_at,
        )
        for code, detail in incidents.items()
    ]
    deployed = read_deploy_marker(root)
    git_head = read_git_head(root)
    if deployed and git_head:
        deploy_relation = "MATCH" if deployed == git_head else "MISMATCH"
    elif deployed or git_head:
        deploy_relation = "PARTIAL"
    else:
        deploy_relation = "UNKNOWN"
    if deploy_relation == "MISMATCH":
        attention.append(
            _attention_card(
                "DEPLOY_IDENTITY_MISMATCH",
                evidence=f"deployed={deployed} git_head={git_head}",
                current_safe_state="DEGRADED",
                next_safe_action=_next_action_for("DEPLOY_IDENTITY_MISMATCH"),
                observed_at=observed_at,
            )
        )
    freshness = str(snapshot_meta.get("freshness") or "")
    snapshot_attention = {
        "MISSING": (
            "COLLECTOR_SNAPSHOT_MISSING",
            "Dedicated collector snapshot is absent; wait one operability-watch cycle.",
            "UNKNOWN",
        ),
        "STALE": (
            "COLLECTOR_SNAPSHOT_STALE",
            "Dedicated collector snapshot exceeded 1080s freshness; no GET rebuild.",
            "UNKNOWN",
        ),
        "INVALID": (
            "COLLECTOR_SNAPSHOT_INVALID",
            "Dedicated collector snapshot failed schema or source observed_at.",
            "UNKNOWN",
        ),
    }
    if freshness in snapshot_attention:
        code, evidence, safe = snapshot_attention[freshness]
        attention.append(
            _attention_card(
                code,
                evidence=evidence,
                current_safe_state=safe,
                next_safe_action=_next_action_for(code),
                observed_at=observed_at,
            )
        )
    telegram = _telegram_class(env)
    heartbeat = _heartbeat_class(env)
    coverage = {
        "HTTP_SELF": _coverage(
            "SERVING" if http_self == HTTP_SERVING else http_self
        ),
        "SYSTEMD": _systemd_coverage(units),
        **_map_packet_coverage(packet, source_status=collector_status),
        "DEPLOY_IDENTITY": _coverage(
            "AVAILABLE" if deploy_relation in {"MATCH", "MISMATCH"} else deploy_relation
        ),
        "ALERTING": _coverage(str(telegram["status"])),
        "OUT_OF_BAND_HOST_REACHABILITY": heartbeat,
        "CHANGE_HISTORY": _coverage("STATE_ONLY"),
    }
    collector_verdict = None if packet is None else _text(packet.get("collector_verdict"))
    state = _rollup_state(
        attention=attention,
        coverage=coverage,
        collector_verdict=collector_verdict or None,
    )
    workbench_unit = units.get(WATCH_WORKBENCH_UNIT, SYSTEMD_UNAVAILABLE)
    processes = {
        "http_self": http_self,
        "managed_workbench_unit": workbench_unit,
        "required_timers": {
            name: units.get(name, SYSTEMD_UNAVAILABLE) for name in WATCH_REQUIRED_TIMERS
        },
    }
    next_item = attention[0] if attention else None
    if next_item:
        next_safe = str(next_item.get("NEXT_SAFE_ACTION") or "INSPECT_COVERAGE_GAPS")
    elif state == "OK_OBSERVED":
        next_safe = ""
    else:
        next_safe = "INSPECT_COVERAGE_GAPS"
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed_at,
        "state": state,
        "coverage": coverage,
        "identity": {
            "deployed_sha": deployed,
            "git_head": git_head,
            "deploy_relation": deploy_relation,
            "capability_deploy_version": read_capability_deploy_version(root),
            "capability_health_owner": "SYSTEM_OPERABILITY_SURFACE_V2",
        },
        "processes": processes,
        "collection": {
            "source_status": collector_status,
            "collector_verdict": collector_verdict or collector_status,
            "health_classes": list(packet.get("health_classes") or []) if packet else [],
            "activation_state": packet.get("activation_state") if packet else None,
            "snapshot": snapshot_meta,
        },
        "collector_snapshot": snapshot_meta,
        "storage": {
            "filesystem_disk_used_pct": None if packet is None else packet.get("filesystem_disk_used_pct"),
            "projected_97d_status": None if packet is None else packet.get("projected_97d_status"),
        },
        "durability": {
            "mutable_backup": None if packet is None else packet.get("backup_age_seconds"),
            "offhost_backup_state": None if packet is None else packet.get("offhost_backup_state"),
            "immutable_archive_latest_verified_day": (
                None if packet is None else packet.get("immutable_archive_latest_verified_day")
            ),
        },
        "alerting": telegram,
        "out_of_band_host_reachability": heartbeat,
        "attention": attention,
        "next_safe_action": next_safe,
        "authority_required": bool(next_item and next_item.get("AUTHORITY_REQUIRED")),
        "non_claims": list(NON_CLAIMS),
        "incident_state_relative": INCIDENT_STATE_RELATIVE,
        "collector_snapshot_relative": COLLECTOR_SNAPSHOT_RELATIVE,
    }
