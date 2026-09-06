"""Daily Collector Owner Pulse — Telegram summary, not incident spam.

Dry-run: zero network, zero credential VALUE reads.
Emit: Telegram only via FACTORY_TELEGRAM_* env names; never Jupiter credentials.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from solana_alpha_lab.factory.collector_operational_packet import (
    UNKNOWN,
    append_storage_history,
    build_collector_operational_packet,
)
from solana_alpha_lab.factory.observation_schedule import render_utc
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.remote_ops import (
    RemoteOpsError,
    load_config,
    require_secret,
)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
PULSE_DEDUP_RELATIVE = "local/factory_v1/collector_owner_pulse_dedup.json"
# Ordinary documented UTC time — deterministic schedule bytes.
DAILY_PULSE_ON_CALENDAR = "*-*-* 06:15:00 UTC"


def _fmt(value: object) -> str:
    if value is None or value == UNKNOWN:
        return "UNKNOWN"
    return str(value)


def _owner_action_code(packet: Mapping[str, Any]) -> str:
    classes = set(packet.get("health_classes") or [])
    if "IMMUTABLE_ARCHIVE_HASH_MISMATCH" in classes:
        return "IMMUTABLE_ARCHIVE_HASH_MISMATCH"
    if "DISK_RUNWAY_HARD50" in classes or "DISK_CRITICAL" in classes:
        return "DISK_RUNWAY_HARD50"
    if "PROVIDER_AUTH_FAILED" in classes:
        return "SUSTAINED_PROVIDER_FAILURE"
    if "IMMUTABLE_ARCHIVE_STALE" in classes:
        return "IMMUTABLE_ARCHIVE_STALE"
    if "BACKUP_DEGRADED" in classes:
        return "MUTABLE_BACKUP_STALE"
    if "DATA_STALE" in classes:
        return "SOURCE_DATA_STALE"
    if "DISK_RUNWAY_TARGET40" in classes:
        return "DISK_RUNWAY_TARGET40"
    if packet.get("collector_verdict") == "ACTION_REQUIRED":
        return "COLLECTOR_ACTION"
    return "NONE"


def _owner_action(packet: Mapping[str, Any]) -> str:
    code = _owner_action_code(packet)
    mapping = {
        "IMMUTABLE_ARCHIVE_HASH_MISMATCH": "Fail closed: do not overwrite remote archive; inspect Drive object vs local SHA.",
        "DISK_RUNWAY_HARD50": "Free disk or scale storage before scientific evidence is at risk; do not auto-delete RDP.",
        "SUSTAINED_PROVIDER_FAILURE": "Inspect Jupiter credential placement (JUPITER_FREE_API_KEY); do not rotate blindly.",
        "IMMUTABLE_ARCHIVE_STALE": "Closed-day Drive archive is behind RPO; later timer catch-up should converge.",
        "MUTABLE_BACKUP_STALE": "Mutable backup freshness degraded; do not treat generic offhost CURRENT as archive proof.",
        "SOURCE_DATA_STALE": "Confirm observation timer is enabled and last source-poll advances.",
        "DISK_RUNWAY_TARGET40": "Projected 97d footprint exceeds TARGET40; no scientific delete from this pulse.",
        "COLLECTOR_ACTION": "Review collector operational packet; no automatic mutate.",
        "NONE": "NONE",
    }
    return mapping.get(code, code)


def _pulse_state(packet: Mapping[str, Any]) -> str:
    verdict = str(packet.get("collector_verdict") or "")
    if _owner_action_code(packet) != "NONE" or verdict == "ACTION_REQUIRED":
        return "ACTION"
    if verdict == "DEGRADED":
        return "DEGRADED"
    return "OK"


def render_daily_owner_pulse(packet: Mapping[str, Any]) -> str:
    """Phone-short daily card. No secrets. Footer is parser-stable."""

    disk = packet.get("filesystem_disk_used_pct")
    disk_note = _fmt(disk) if not isinstance(disk, int) else f"{disk}%"
    runway = str(packet.get("projected_97d_status") or "UNKNOWN")
    backup_age = packet.get("backup_age_seconds")
    if isinstance(backup_age, int):
        backup_age_txt = f"{backup_age // 3600}h" if backup_age >= 3600 else f"{backup_age // 60}m"
    else:
        backup_age_txt = _fmt(backup_age)
    state = _pulse_state(packet)
    action_code = _owner_action_code(packet)
    lifecycle = _fmt(packet.get("cohort_readiness_state"))
    lines = [
        f"FACTORY / DAILY — {state}",
        "",
        f"Collector: {_fmt(packet.get('activation_state'))} / {_fmt(packet.get('collector_verdict'))}",
        f"Lifecycle: {lifecycle}",
        "",
        "Durability:",
        f"Mutable backup {backup_age_txt} full_rdp={_fmt(packet.get('mutable_backup_includes_full_observation_rdp'))}",
        f"Immutable archive verified={_fmt(packet.get('immutable_archive_latest_verified_day'))} "
        f"backlog={_fmt(packet.get('immutable_archive_backlog_days'))}",
        "",
        f"Storage: {disk_note} projected97d={_fmt(packet.get('projected_97d_bytes'))} {runway}",
        "",
        "Owner:",
        _owner_action(packet),
        "",
        "```",
        "MESSAGE_TYPE=DAILY",
        f"STATE={state}",
        f"INCIDENT={action_code if action_code != 'NONE' else 'NONE'}",
        f"COLLECTOR_STATE={_fmt(packet.get('activation_state'))}",
        f"LIFECYCLE_STATE={lifecycle}",
        f"ARCHIVE_LAST_VERIFIED_DAY={_fmt(packet.get('immutable_archive_latest_verified_day'))}",
        f"ARCHIVE_BACKLOG_DAYS={_fmt(packet.get('immutable_archive_backlog_days'))}",
        f"MUTABLE_BACKUP_STATE={backup_age_txt}",
        f"PROJECTED_97D_BYTES={_fmt(packet.get('projected_97d_bytes'))}",
        f"OWNER_ACTION={action_code}",
        "```",
    ]
    return "\n".join(lines) + "\n"


def _utc_day(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%d")


def emit_daily_owner_pulse(
    *,
    root: Path,
    text: str,
    now: datetime | None = None,
    remote_config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    transport: Callable[[str, str, str], None] | None = None,
    dedup_store: Path | None = None,
    incident_key: str | None = None,
) -> dict[str, Any]:
    """Send one Telegram message. Reads only FACTORY_TELEGRAM_* values."""

    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    loaded = dict(remote_config) if remote_config is not None else load_config(root)
    env = environ if environ is not None else os.environ
    token_env = str(loaded["alert"]["token_env"])
    chat_env = str(loaded["alert"]["chat_id_env"])
    if token_env != "FACTORY_TELEGRAM_BOT_TOKEN" or chat_env != "FACTORY_TELEGRAM_CHAT_ID":
        raise RemoteOpsError("PULSE_TELEGRAM_ENV_BINDING_DRIFT")
    # Never touch Jupiter credential names.
    for forbidden in ("JUPITER_FREE_API_KEY", "JUPITER_API_KEY"):
        if forbidden in dict(env) and transport is None:
            # Presence in environ mapping is fine; we must not call require_secret on it.
            pass

    day = _utc_day(clock)
    key = incident_key or f"DAILY_COLLECTOR_OWNER_PULSE:{day}"
    store = dedup_store or (root / PULSE_DEDUP_RELATIVE)
    store.parent.mkdir(parents=True, exist_ok=True)
    history: dict[str, Any] = {}
    if store.is_file():
        try:
            loaded_history = json.loads(store.read_text(encoding="utf-8"))
            if isinstance(loaded_history, dict):
                history = loaded_history
        except (OSError, json.JSONDecodeError):
            history = {}
    sent = history.get("sent") if isinstance(history.get("sent"), dict) else {}
    if key in sent:
        return {
            "delivered": False,
            "deduped": True,
            "incident_key": key,
            "credentials_read": ["FACTORY_TELEGRAM_BOT_TOKEN", "FACTORY_TELEGRAM_CHAT_ID"],
            "jupiter_credentials_read": 0,
        }

    token = require_secret(token_env, env)
    chat_id = require_secret(chat_env, env)
    if transport is None:
        url = TELEGRAM_API.format(token=token)
        payload = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        request = urllib.request.Request(url, data=payload, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if int(response.status) >= 300:
                    raise RemoteOpsError("PULSE_TRANSPORT_FAILED")
        except urllib.error.URLError:
            # Do not chain URLError: Telegram token is embedded in the request URL.
            raise RemoteOpsError("PULSE_TRANSPORT_FAILED")
    else:
        transport(token, chat_id, text)

    sent[key] = {"at": render_utc(clock)}
    history["sent"] = sent
    store.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "delivered": True,
        "deduped": False,
        "incident_key": key,
        "credentials_read": ["FACTORY_TELEGRAM_BOT_TOKEN", "FACTORY_TELEGRAM_CHAT_ID"],
        "jupiter_credentials_read": 0,
        "chars": len(text),
    }


def run_daily_owner_pulse(
    *,
    root: Path,
    store: ObservationScheduleStore,
    mode: str,
    now: datetime | None = None,
    deploy_git_sha: str | None = None,
    observation_rdp: Path | None = None,
    remote_config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    transport: Callable[[str, str, str], None] | None = None,
    record_storage_history: bool = False,
) -> dict[str, Any]:
    if mode not in {"dry-run", "emit"}:
        raise ValueError("PULSE_MODE_INVALID")
    clock = now or datetime.now(UTC)
    packet = build_collector_operational_packet(
        root=root,
        store=store,
        now=clock,
        deploy_git_sha=deploy_git_sha,
        observation_rdp=observation_rdp,
        remote_config=remote_config,
        environ=environ if environ is not None else {},
    )
    text = render_daily_owner_pulse(packet)
    result: dict[str, Any] = {
        "mode": mode,
        "text": text,
        "packet": packet,
        "on_calendar_utc": DAILY_PULSE_ON_CALENDAR,
        "network_calls": 0,
        "credential_value_reads": 0,
        "jupiter_credentials_read": 0,
    }
    if mode == "dry-run":
        return result

    if record_storage_history:
        append_storage_history(
            root,
            observed_at=str(packet["observed_at"]),
            disk_used_pct=(
                packet["filesystem_disk_used_pct"]
                if isinstance(packet.get("filesystem_disk_used_pct"), int)
                else None
            ),
            sqlite_bytes=(
                packet["observation_sqlite_bytes"]
                if isinstance(packet.get("observation_sqlite_bytes"), int)
                else None
            ),
            rdp_bytes=(
                packet["observation_rdp_bytes"]
                if isinstance(packet.get("observation_rdp_bytes"), int)
                else None
            ),
        )

    delivery = emit_daily_owner_pulse(
        root=root,
        text=text,
        now=clock,
        remote_config=remote_config,
        environ=environ,
        transport=transport,
    )
    result["delivery"] = delivery
    result["network_calls"] = 0 if delivery.get("deduped") else 1
    result["credential_value_reads"] = 2 if not delivery.get("deduped") else 0
    result["jupiter_credentials_read"] = 0
    return result


__all__ = [
    "DAILY_PULSE_ON_CALENDAR",
    "PULSE_DEDUP_RELATIVE",
    "emit_daily_owner_pulse",
    "render_daily_owner_pulse",
    "run_daily_owner_pulse",
]
