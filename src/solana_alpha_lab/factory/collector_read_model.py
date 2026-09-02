"""Collector health / read model derived from ObservationSchedule store + status."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from solana_alpha_lab.factory.collector_schedulability_oracle import (
    classify_discovery_coverage,
)
from solana_alpha_lab.factory.due_pressure import (
    backlog_risk_from_due_pressure,
    build_due_pressure_projection,
)
from solana_alpha_lab.factory.observation_primitives import (
    HTTP_CLASS_401,
    HTTP_CLASS_403,
    HTTP_CLASS_429,
    HTTP_CLASS_5XX,
    HTTP_CLASS_OK,
    HTTP_CLASS_TIMEOUT,
    HTTP_CLASS_TRANSPORT,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

DISCOVERY = "PRIM-JUPITER-TOKENS-V2-RECENT-001"
SEARCH = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"


def _safe_parse(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return parse_utc(raw)
    except Exception:
        return None


def _http_bucket(http_class: object) -> str | None:
    text = str(http_class or "")
    if text == HTTP_CLASS_401:
        return "HTTP_401_24h"
    if text == HTTP_CLASS_403:
        return "HTTP_403_24h"
    if text == HTTP_CLASS_429:
        return "HTTP_429_24h"
    if text == HTTP_CLASS_5XX:
        return "HTTP_5XX_24h"
    if text == HTTP_CLASS_TIMEOUT:
        return "TIMEOUT_24h"
    if text == HTTP_CLASS_TRANSPORT:
        return "TRANSPORT_ERROR_24h"
    return None


def build_collector_read_model(
    store: ObservationScheduleStore,
    *,
    now: datetime,
    schedule_sha256: str | None = None,
    activation_id: str | None = None,
    deploy_git_sha: str | None = None,
    period_seconds: int = 60,
    empirical_overlap_seconds: int | None = None,
) -> dict[str, Any]:
    """Compose operational collector fields from existing store surfaces."""

    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(UTC)
    window_start = now - timedelta(hours=24)
    activations = store.list_activations()
    selected = None
    if schedule_sha256 and activation_id:
        selected = store.get_activation(schedule_sha256, activation_id)
    elif activations:
        live = [row for row in activations if row.get("state") == "ACTIVE"]
        selected = live[0] if live else activations[0]
    digest = str((selected or {}).get("schedule_sha256") or schedule_sha256 or "")
    act_id = str((selected or {}).get("activation_id") or activation_id or "")
    activation_state = str((selected or {}).get("state") or "NONE")

    due_counts = store.due_counts()
    due_pressure = build_due_pressure_projection(
        store,
        now=now,
        schedule_sha256=digest or None,
        activation_id=act_id or None,
    )
    pending_due = int(due_pressure["pending_due_count"])
    in_flight = int(due_pressure["in_flight_count"])
    blocked_budget = int(due_pressure["blocked_budget_count"])

    oldest_due_age = int(due_pressure["oldest_overdue_age_seconds"])

    http_counts = {
        "HTTP_401_24h": 0,
        "HTTP_403_24h": 0,
        "HTTP_429_24h": 0,
        "HTTP_5XX_24h": 0,
        "TIMEOUT_24h": 0,
        "TRANSPORT_ERROR_24h": 0,
    }
    observations_24h = 0
    typed_missing_24h = 0
    censored_late_24h = 0
    last_source_poll_attempt_at = None
    last_source_poll_success_at = None
    last_search_success_at = None

    for call in store.list_calls():
        payload = call.get("payload") or {}
        if isinstance(payload, str):
            continue
        updated = _safe_parse(call.get("updated_at") or call.get("created_at"))
        if updated is None or updated < window_start:
            continue
        primitive = str(call.get("primitive_id") or "")
        http_class = payload.get("http_class")
        bucket = _http_bucket(http_class)
        if bucket:
            http_counts[bucket] += 1
        status = str(payload.get("status") or "")
        if status == "OBSERVED":
            observations_24h += 1
        if status == "MISSING_TYPED" or payload.get("missing_reason"):
            if str(payload.get("missing_reason") or "") not in {
                "",
                "None",
                "ENTITY_ABSENT_FROM_RESPONSE",
            }:
                typed_missing_24h += 1
            elif status == "MISSING_TYPED":
                typed_missing_24h += 1
        if primitive == DISCOVERY:
            last_source_poll_attempt_at = render_utc(updated)
            if http_class == HTTP_CLASS_OK or status == "OBSERVED":
                last_source_poll_success_at = render_utc(updated)
        if primitive == SEARCH and (
            http_class == HTTP_CLASS_OK or status == "OBSERVED"
        ):
            last_search_success_at = render_utc(updated)

    last_tick_at = None
    selected_payload = dict((selected or {}).get("payload") or {})
    tick_raw = selected_payload.get("last_tick_at")
    if isinstance(tick_raw, str) and tick_raw:
        last_tick_at = tick_raw

    for row in store.due_in_states(
        ("CENSORED_LATE",), due_at_max=now + timedelta(days=365)
    ):
        if digest and str(row.get("schedule_sha256")) != digest:
            continue
        if act_id and str(row.get("activation_id")) != act_id:
            continue
        updated = _safe_parse(row.get("updated_at"))
        if updated is not None and updated >= window_start:
            censored_late_24h += 1

    source_poll_age = None
    if last_source_poll_attempt_at:
        attempt = parse_utc(last_source_poll_attempt_at)
        source_poll_age = int((now - attempt).total_seconds())

    coverage = classify_discovery_coverage(
        period_seconds=period_seconds,
        empirical_overlap_seconds=empirical_overlap_seconds,
    )

    health_flags: list[str] = []
    if store.restore_marker_unresolved():
        health_flags.append("BACKUP_DEGRADED")
    if activation_state == "ACTIVE":
        health_flags.append("PROCESS_OK")
    if any(http_counts[key] for key in http_counts):
        health_flags.append("PROVIDER_FAILED")
    if coverage == "GAP_CONFIRMED":
        health_flags.append("DISCOVERY_GAP")
    elif coverage == "GAP_SUSPECTED":
        health_flags.append("DISCOVERY_COVERAGE_UNKNOWN")
    if backlog_risk_from_due_pressure(due_pressure):
        health_flags.append("BACKLOG_RISK")
    if source_poll_age is not None and source_poll_age > period_seconds * 3:
        health_flags.append("DATA_STALE")

    candidates_24h = 0
    members_24h = 0
    if digest and act_id:
        for cand in store.list_candidates(schedule_sha256=digest, activation_id=act_id):
            created = _safe_parse(cand.get("created_at") or cand.get("updated_at"))
            if created is None or created < window_start:
                continue
            candidates_24h += 1
            if str(cand.get("state") or "") in {
                "SELECTED",
                "MEMBER",
                "ADMITTED",
                "SAMPLED",
            }:
                members_24h += 1

    return {
        "deploy_git_sha": deploy_git_sha,
        "schedule_sha256": digest or None,
        "activation_id": act_id or None,
        "activation_state": activation_state,
        "last_tick_at": last_tick_at,
        "last_source_poll_attempt_at": last_source_poll_attempt_at,
        "last_source_poll_success_at": last_source_poll_success_at,
        "source_poll_age": source_poll_age,
        "discovery_coverage_class": coverage,
        "last_search_success_at": last_search_success_at,
        "pending_due_count": pending_due,
        "oldest_due_age_seconds": oldest_due_age,
        "due_pressure": due_pressure,
        "in_flight_indeterminate_count": in_flight,
        "blocked_budget_count": blocked_budget,
        "candidate_count_24h": candidates_24h,
        "sampled_member_count_24h": members_24h,
        "observations_24h": observations_24h,
        "typed_missing_24h": typed_missing_24h,
        "censored_late_24h": censored_late_24h,
        **http_counts,
        "observation_rdp_last_publish_at": None,
        "disk_used_pct": None,
        "disk_growth_24h": None,
        "last_backup_at": None,
        "last_backup_sha256": None,
        "backup_domain": None,
        "release_state": None,
        "last_sealed_release_id": None,
        "health_flags": health_flags,
        "restore_marker_unresolved": store.restore_marker_unresolved(),
        "due_counts": due_counts,
    }


__all__ = ["build_collector_read_model"]
