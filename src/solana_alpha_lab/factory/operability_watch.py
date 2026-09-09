"""Local operability watch: one incident, one recovery, pending Telegram retry."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from solana_alpha_lab.factory.collector_operational_packet import (
    build_collector_operational_packet,
)
from solana_alpha_lab.factory.collector_owner_pulse import emit_daily_owner_pulse
from solana_alpha_lab.factory.observation_schedule import render_utc
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.remote_ops import RemoteOpsError

STATE_RELATIVE = "local/factory_v1/operability_incident_state.json"
SNAPSHOT_RELATIVE = "local/factory_v1/operability_collector_snapshot.json"
WATCH_ON_CALENDAR = "*-*-* *:0/15:00 UTC"
WATCH_CADENCE_SECONDS = 15 * 60
COLLECTOR_SNAPSHOT_SCHEMA = "smial.collector-derived-operability-snapshot"
COLLECTOR_SNAPSHOT_SCHEMA_VERSION = "1.0"
COLLECTOR_SNAPSHOT_FRESHNESS_GRACE_SECONDS = 180
COLLECTOR_SNAPSHOT_FRESH_MAX_AGE_SECONDS = (
    WATCH_CADENCE_SECONDS + COLLECTOR_SNAPSHOT_FRESHNESS_GRACE_SECONDS
)
COLLECTOR_SNAPSHOT_PACKET_FIELDS = (
    "activation_state",
    "backup_age_seconds",
    "collector_verdict",
    "filesystem_disk_used_pct",
    "health_classes",
    "immutable_archive_last_terminal",
    "immutable_archive_latest_verified_day",
    "offhost_backup_state",
    "projected_97d_status",
    "provider_observations",
    "restore_marker_unresolved",
)
WATCH_REQUIRED_TIMERS = (
    "factory-observation-schedule.timer",
    "factory-remote-backup.timer",
    "factory-collector-owner-pulse.timer",
    "factory-hot90-closed-day-archive.timer",
    "factory-operability-watch.timer",
)
WATCH_WORKBENCH_UNIT = "factory-v1-workbench.service"
SYSTEMD_READBACK_UNAVAILABLE = "SYSTEMD_READBACK_UNAVAILABLE"
_UNIT_OK = frozenset({None, "", "active", SYSTEMD_READBACK_UNAVAILABLE})

INCIDENT_GRACE_SECONDS = {
    "COLLECTOR_STALLED": 1800,
    "SOURCE_DATA_STALE": 1800,
    "PUBLICATION_STUCK": 1800,
    "PUBLICATION_FAILED": 0,
    "SQLITE_INTEGRITY_FAILED": 0,
    "MUTABLE_BACKUP_STALE": 86400,
    "MUTABLE_BACKUP_FAILED": 0,
    "IMMUTABLE_ARCHIVE_STALE": 86400,
    "IMMUTABLE_ARCHIVE_UPLOAD_FAILED": 86400,
    "IMMUTABLE_ARCHIVE_HASH_MISMATCH": 0,
    "DISK_RUNWAY_TARGET40": 86400,
    "DISK_RUNWAY_HARD50": 0,
    "SUSTAINED_PROVIDER_FAILURE": 1800,
    "MATERIAL_COVERAGE_DEGRADATION": 1800,
    "REQUIRED_TIMER_FAILED": 900,
    "WORKBENCH_SERVICE_DOWN": 0,
    "ALERTING_UNAVAILABLE": 0,
}


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def build_collector_snapshot(
    packet: Mapping[str, Any],
    *,
    observed_at: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for key in COLLECTOR_SNAPSHOT_PACKET_FIELDS:
        if key in packet:
            body[key] = packet[key]
    return {
        "schema": COLLECTOR_SNAPSHOT_SCHEMA,
        "schema_version": COLLECTOR_SNAPSHOT_SCHEMA_VERSION,
        "observed_at": observed_at,
        "packet": body,
    }


def _parse_snapshot_observed_at(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def validate_collector_snapshot(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("schema") != COLLECTOR_SNAPSHOT_SCHEMA:
        return None
    version = str(raw.get("schema_version") or "")
    if not version.startswith("1."):
        return None
    observed_at = str(raw.get("observed_at") or "").strip()
    if _parse_snapshot_observed_at(observed_at) is None:
        return None
    packet = raw.get("packet")
    if not isinstance(packet, dict):
        return None
    if "health_classes" in packet and not isinstance(packet.get("health_classes"), list):
        return None
    allowlisted = {
        key: packet[key] for key in COLLECTOR_SNAPSHOT_PACKET_FIELDS if key in packet
    }
    return {
        "schema": COLLECTOR_SNAPSHOT_SCHEMA,
        "schema_version": COLLECTOR_SNAPSHOT_SCHEMA_VERSION,
        "observed_at": observed_at,
        "packet": allowlisted,
    }


def evaluate_collector_snapshot_freshness(
    observed_at: str,
    *,
    now: datetime,
) -> tuple[str, int | None]:
    parsed = _parse_snapshot_observed_at(observed_at)
    if parsed is None:
        return "INVALID", None
    clock = now if now.tzinfo else now.replace(tzinfo=UTC)
    clock = clock.astimezone(UTC)
    age = (clock - parsed).total_seconds()
    if age < -COLLECTOR_SNAPSHOT_FRESHNESS_GRACE_SECONDS:
        return "INVALID", int(age)
    if age < 0:
        age = 0.0
    age_seconds = int(age)
    if age <= COLLECTOR_SNAPSHOT_FRESH_MAX_AGE_SECONDS:
        return "FRESH", age_seconds
    return "STALE", age_seconds


def load_collector_snapshot_file(path: Path) -> tuple[str, dict[str, Any] | None]:
    if path.is_file() is False:
        return "MISSING", None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return "INVALID", None
    if not isinstance(payload, dict):
        return "INVALID", None
    if payload.get("schema") == COLLECTOR_SNAPSHOT_SCHEMA:
        raw = payload
    elif "collector_snapshot" in payload:
        raw = payload.get("collector_snapshot")
    else:
        return "INVALID", None
    parsed = validate_collector_snapshot(raw)
    if parsed is None:
        return "INVALID", None
    return "PRESENT", parsed


def classify_incidents(
    packet: Mapping[str, Any],
    *,
    unit_status: Mapping[str, str] | None = None,
) -> dict[str, str]:
    classes = set(packet.get("health_classes") or [])
    found: dict[str, str] = {}
    if "DATA_STALE" in classes:
        found["SOURCE_DATA_STALE"] = "Collector source-poll older than 3 periods."
    if "RDP_PUBLICATION_STALE" in classes:
        found["PUBLICATION_STUCK"] = "Publication progress is stale beyond the freshness bound."
    if "BACKUP_DEGRADED" in classes:
        found["MUTABLE_BACKUP_STALE"] = "Mutable backup freshness degraded."
    if packet.get("restore_marker_unresolved") is True:
        found["MUTABLE_BACKUP_FAILED"] = "Restore marker unresolved."
    if "IMMUTABLE_ARCHIVE_STALE" in classes:
        found["IMMUTABLE_ARCHIVE_STALE"] = "Closed-day archive backlog older than RPO."
    if str(packet.get("immutable_archive_last_terminal") or "") == "DRIVE_WRITE_FAILED":
        found["IMMUTABLE_ARCHIVE_UPLOAD_FAILED"] = "Archive Drive write failed."
    if "IMMUTABLE_ARCHIVE_HASH_MISMATCH" in classes:
        found["IMMUTABLE_ARCHIVE_HASH_MISMATCH"] = "Remote archive SHA != local archive SHA."
    if "DISK_RUNWAY_TARGET40" in classes:
        found["DISK_RUNWAY_TARGET40"] = "Projected 97d storage exceeds TARGET40."
    if "DISK_RUNWAY_HARD50" in classes or "DISK_CRITICAL" in classes:
        found["DISK_RUNWAY_HARD50"] = "Projected 97d storage or live disk exceeds HARD50."
    if "PROVIDER_FAILED" in classes or "PROVIDER_AUTH_FAILED" in classes:
        found["SUSTAINED_PROVIDER_FAILURE"] = "Provider errors are material."
    if "DISCOVERY_GAP" in classes:
        found["MATERIAL_COVERAGE_DEGRADATION"] = "Discovery gap confirmed."
    units = unit_status or {}
    for unit in WATCH_REQUIRED_TIMERS:
        status = units.get(unit)
        if status not in _UNIT_OK:
            found["REQUIRED_TIMER_FAILED"] = f"{unit} is not active."
            break
    workbench = units.get(WATCH_WORKBENCH_UNIT)
    if workbench not in _UNIT_OK:
        found["WORKBENCH_SERVICE_DOWN"] = f"{WATCH_WORKBENCH_UNIT} is not active."
    if "MUTABLE_BACKUP_FULL_RDP_UNEXPECTED" in classes:
        found["MUTABLE_BACKUP_FAILED"] = "Mutable backup profile includes full Observation RDP."
    return found


def _load_state(path: Path) -> dict[str, Any]:
    if path.is_file() is False:
        return {"active": {}, "pending": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"active": {}, "pending": []}
    if not isinstance(payload, dict):
        return {"active": {}, "pending": []}
    payload.setdefault("active", {})
    payload.setdefault("pending", [])
    return payload


def render_incident_message(
    *,
    kind: str,
    code: str,
    detail: str,
    packet: Mapping[str, Any],
    first_seen_at: str,
    recovered_at: str | None = None,
) -> str:
    state = "ACTION" if kind == "INCIDENT" else "OK"
    backup_age = packet.get("backup_age_seconds")
    if isinstance(backup_age, int):
        backup_state = f"{backup_age // 3600}h" if backup_age >= 3600 else f"{backup_age // 60}m"
    else:
        backup_state = "UNKNOWN"
    verified_day = packet.get("immutable_archive_latest_verified_day")
    if verified_day is None or verified_day == "":
        verified_day = "UNKNOWN"
    lines = [
        f"FACTORY / {kind} — {state}",
        "",
        f"{code}: {detail}",
        f"Collector: {packet.get('collector_verdict')}",
        f"Archive: verified={verified_day} "
        f"backlog={packet.get('immutable_archive_backlog_days')}",
        "",
        "```",
        f"MESSAGE_TYPE={kind}",
        f"STATE={state}",
        f"INCIDENT={code}",
        f"COLLECTOR_STATE={packet.get('activation_state')}",
        f"LIFECYCLE_STATE={packet.get('cohort_readiness_state')}",
        f"ARCHIVE_LAST_VERIFIED_DAY={verified_day}",
        f"ARCHIVE_BACKLOG_DAYS={packet.get('immutable_archive_backlog_days')}",
        f"MUTABLE_BACKUP_STATE={backup_state}",
        f"PROJECTED_97D_BYTES={packet.get('projected_97d_bytes')}",
        f"OWNER_ACTION={code if kind == 'INCIDENT' else 'NONE'}",
        f"DEDUP_KEY={code}",
        f"FIRST_SEEN_AT={first_seen_at}",
    ]
    if recovered_at:
        lines.append(f"RECOVERED_AT={recovered_at}")
    lines.extend(["```", ""])
    return "\n".join(str(item) for item in lines)


def evaluate_operability(
    *,
    root: Path,
    store: ObservationScheduleStore,
    now: datetime | None = None,
    deploy_git_sha: str | None = None,
    observation_rdp: Path | None = None,
    remote_config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    unit_status: Mapping[str, str] | None = None,
    emit: bool = False,
    persist: bool | None = None,
    transport: Callable[[str, str, str], None] | None = None,
) -> dict[str, Any]:
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    write_state = True if persist is None else persist
    packet = build_collector_operational_packet(
        root=root,
        store=store,
        now=clock,
        deploy_git_sha=deploy_git_sha,
        observation_rdp=observation_rdp,
        remote_config=remote_config,
        environ=environ if environ is not None else os.environ,
    )
    present = classify_incidents(packet, unit_status=unit_status)
    state_path = root / STATE_RELATIVE
    state = _load_state(state_path)
    active: dict[str, Any] = dict(state.get("active") or {})
    pending: list[dict[str, Any]] = list(state.get("pending") or [])
    messages: list[dict[str, Any]] = []

    for code, detail in present.items():
        record = dict(active.get(code) or {})
        first = str(record.get("first_seen_at") or render_utc(clock))
        record["first_seen_at"] = first
        record["last_seen_at"] = render_utc(clock)
        record["detail"] = detail
        elapsed = (
            clock - datetime.fromisoformat(first.replace("Z", "+00:00"))
        ).total_seconds()
        grace = INCIDENT_GRACE_SECONDS.get(code, 1800)
        if elapsed >= grace and record.get("notified") is not True:
            text = render_incident_message(
                kind="INCIDENT",
                code=code,
                detail=detail,
                packet=packet,
                first_seen_at=first,
            )
            pending.append({"kind": "INCIDENT", "code": code, "text": text, "first_seen_at": first})
            record["notified"] = True
            messages.append({"kind": "INCIDENT", "code": code})
        active[code] = record

    for code in list(active):
        if code in present:
            continue
        record = active.pop(code)
        if record.get("notified") is True:
            recovered_at = render_utc(clock)
            text = render_incident_message(
                kind="RECOVERED",
                code=code,
                detail=str(record.get("detail") or ""),
                packet=packet,
                first_seen_at=str(record.get("first_seen_at")),
                recovered_at=recovered_at,
            )
            pending.append(
                {
                    "kind": "RECOVERED",
                    "code": code,
                    "text": text,
                    "first_seen_at": record.get("first_seen_at"),
                    "recovered_at": recovered_at,
                }
            )
            messages.append({"kind": "RECOVERED", "code": code})

    still_pending: list[dict[str, Any]] = []
    if emit:
        for item in pending:
            try:
                delivery = emit_daily_owner_pulse(
                    root=root,
                    text=str(item["text"]),
                    now=clock,
                    remote_config=remote_config,
                    environ=environ,
                    transport=transport,
                    incident_key=f"{item['kind']}:{item['code']}:{item.get('first_seen_at')}",
                )
            except RemoteOpsError:
                still_pending.append(item)
                continue
            if delivery.get("delivered") or delivery.get("deduped"):
                continue
            still_pending.append(item)
    else:
        still_pending = pending

    next_state = {
        "active": active,
        "pending": still_pending,
        "collector_snapshot": build_collector_snapshot(
            packet,
            observed_at=str(packet.get("observed_at") or render_utc(clock)),
        ),
    }
    if write_state:
        _atomic_write_json(state_path, next_state)
        _atomic_write_json(root / SNAPSHOT_RELATIVE, next_state["collector_snapshot"])
    return {
        "present": sorted(present),
        "messages": messages,
        "pending_count": len(still_pending),
        "preview_messages": [str(item.get("text") or "") for item in still_pending],
        "packet_verdict": packet.get("collector_verdict"),
        "on_calendar_utc": WATCH_ON_CALENDAR,
    }
