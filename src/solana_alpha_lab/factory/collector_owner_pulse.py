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
    DISK_WARNING_EARLY_PCT,
    DISK_WARNING_PCT,
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
DAILY_PULSE_ON_CALENDAR = "*-*-* 06:15:00"


def _fmt(value: object) -> str:
    if value is None or value == UNKNOWN:
        return "UNKNOWN"
    return str(value)


def _owner_action(packet: Mapping[str, Any]) -> str:
    classes = set(packet.get("health_classes") or [])
    if "PROVIDER_AUTH_FAILED" in classes:
        return "Inspect Jupiter credential placement (JUPITER_FREE_API_KEY); do not rotate blindly."
    if "DISK_CRITICAL" in classes:
        return "Free disk or scale storage before scientific evidence is at risk; do not auto-delete RDP."
    if "BACKUP_DEGRADED" in classes:
        return "Run independent backup (`factory_remote_doctor.py --backup`) and verify FACTORY_BACKUP_SINK domain."
    if "OFFHOST_BACKUP_FAILED" in classes or "OFFHOST_BACKUP_STALE" in classes:
        return "Off-host Google Drive copy stale or failed; local backup may still be OK. Agent should run offhost copy proof path."
    if "BUDGET_BLOCKED" in classes:
        return "Inspect ObservationSchedule budget counters; do not raise caps without owner OK."
    if "RELEASE_BLOCKED" in classes:
        reasons = packet.get("release_blocked_reasons") or []
        return f"Clear release blockers before seal: {', '.join(map(str, reasons)) or 'UNKNOWN'}."
    if "DATA_STALE" in classes:
        return "Confirm observation timer is enabled and last tick advances."
    if packet.get("collector_verdict") == "DEGRADED":
        return "Review health_classes in collector operational packet; no automatic mutate."
    return "NONE"


def _backup_domain_pulse_label(domain: object) -> str:
    text = str(domain or UNKNOWN)
    if text == "ABSOLUTE_SINK_SAME_VOLUME":
        return "SAME_VOLUME"
    if text == "PARENT_INDEPENDENT_GIT_SIDE":
        return "SAME_VOLUME"
    if text in {UNKNOWN, "UNKNOWN"}:
        return "UNKNOWN"
    return text


def _offhost_pulse_label(state: object) -> str:
    mapping = {
        "CURRENT": "OK",
        "DEGRADED": "DEGRADED",
        "HARD_ATTENTION": "STALE",
        "FAILED": "FAILED",
        "MISSING": "MISSING",
        "UNCONFIGURED": "UNCONFIGURED",
    }
    return mapping.get(str(state or ""), _fmt(state))


def render_daily_owner_pulse(packet: Mapping[str, Any]) -> str:
    """Deterministic human-readable daily summary. No secrets."""

    disk = packet.get("filesystem_disk_used_pct")
    disk_note = _fmt(disk)
    if isinstance(disk, int):
        if disk >= 85:
            disk_note = f"{disk}% CRITICAL"
        elif disk >= DISK_WARNING_PCT:
            disk_note = f"{disk}% WARNING"
        elif disk >= DISK_WARNING_EARLY_PCT:
            disk_note = f"{disk}% EARLY_WARNING"
        else:
            disk_note = f"{disk}% NORMAL"

    projected = packet.get("projected_disk_80pct")
    if isinstance(projected, dict):
        projected_txt = f"{projected.get('estimated_days')}d to {projected.get('threshold_pct')}%"
    else:
        projected_txt = _fmt(projected)

    backup_age = packet.get("backup_age_seconds")
    if isinstance(backup_age, int):
        if backup_age < 3600:
            backup_age_txt = f"{backup_age // 60}m"
        else:
            backup_age_txt = f"{backup_age // 3600}h"
    else:
        backup_age_txt = _fmt(backup_age)

    offhost_age = packet.get("offhost_backup_age_seconds")
    if isinstance(offhost_age, int):
        if offhost_age < 3600:
            offhost_age_txt = f"{offhost_age // 60}m"
        else:
            offhost_age_txt = f"{offhost_age // 3600}h"
    else:
        offhost_age_txt = _fmt(offhost_age)

    local_domain = _backup_domain_pulse_label(packet.get("backup_domain"))
    offhost_remote = _fmt(packet.get("offhost_remote"))
    offhost_state = _offhost_pulse_label(packet.get("offhost_backup_state"))

    oldest = packet.get("oldest_due_age")
    if isinstance(oldest, int):
        oldest_txt = f"{oldest}s"
    else:
        oldest_txt = _fmt(oldest)

    lines = [
        "FACTORY / DAILY",
        "",
        f"Collector: {_fmt(packet.get('collector_verdict'))}",
        f"Cohort: {_fmt(packet.get('cohort_readiness_state'))}/{_fmt(packet.get('cohort_id'))}",
        "",
        f"Candidates 24h: {_fmt(packet.get('candidates_24h'))}",
        f"Sampled: {_fmt(packet.get('sampled_members_24h'))}",
        f"X eligible: {_fmt(packet.get('x_eligible_24h'))}",
        "",
        f"4h/24h closure: observations={_fmt(packet.get('observations_24h'))} "
        f"typed_missing={_fmt(packet.get('typed_missing_24h'))} "
        f"censored_late={_fmt(packet.get('censored_late_24h'))}",
        f"Coverage: {_fmt(packet.get('discovery_coverage_class'))}",
        f"Gap incidents: {_fmt((packet.get('health_classes') or []).count('DISCOVERY_GAP') if isinstance(packet.get('health_classes'), list) else UNKNOWN)}",
        "",
        "Provider:",
        f"401 {_fmt(packet.get('HTTP_401_24h'))} / "
        f"403 {_fmt(packet.get('HTTP_403_24h'))} / "
        f"429 {_fmt(packet.get('HTTP_429_24h'))} / "
        f"5xx {_fmt(packet.get('HTTP_5XX_24h'))} / "
        f"timeout {_fmt(packet.get('TIMEOUT_24h'))}",
        "",
        f"Backlog: pending={_fmt(packet.get('pending_due'))} "
        f"in_flight={_fmt(packet.get('in_flight_indeterminate'))} "
        f"budget_blocked={_fmt(packet.get('blocked_budget'))}",
        f"Oldest due: {oldest_txt}",
        "",
        "Storage:",
        f"Disk: {disk_note}",
        f"Growth 24h: disk_pp={_fmt(packet.get('disk_growth_24h_pct_points'))} "
        f"data_bytes={_fmt(packet.get('data_growth_24h_bytes'))}",
        f"SQLite: {_fmt(packet.get('observation_sqlite_bytes'))}",
        f"Observation RDP: {_fmt(packet.get('observation_rdp_bytes'))}",
        f"Projected 80% disk: {projected_txt}",
        "",
        "Backup:",
        f"local {backup_age_txt} / {local_domain}",
        f"offhost {offhost_age_txt} / {offhost_remote} / {offhost_state}",
        "",
        "Release:",
        f"state={_fmt(packet.get('release_state'))} "
        f"sealed={_fmt(packet.get('last_sealed_release_id'))} "
        f"corpus_v={_fmt(packet.get('current_live_corpus_version'))}",
        "",
        "Owner action:",
        _owner_action(packet),
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
    incident_key = f"DAILY_COLLECTOR_OWNER_PULSE:{day}"
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
    if incident_key in sent:
        return {
            "delivered": False,
            "deduped": True,
            "incident_key": incident_key,
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

    sent[incident_key] = {"at": render_utc(clock)}
    history["sent"] = sent
    store.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "delivered": True,
        "deduped": False,
        "incident_key": incident_key,
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
