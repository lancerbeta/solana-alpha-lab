"""Collector health / read model derived from ObservationSchedule store + status."""

from __future__ import annotations

import json
from collections.abc import Mapping as MappingLike
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
from solana_alpha_lab.factory.observation_schedule import (
    cohort_family_key,
    parse_utc,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

DISCOVERY = "PRIM-JUPITER-TOKENS-V2-RECENT-001"
SEARCH = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"

_KIND_AUTH = "auth"
_KIND_RATE = "rate"
_KIND_FAILED = "failed"
_KIND_OK = "ok"
_KIND_OTHER = "other"


def _payload_missing_reason(row: MappingLike) -> object:
    payload = row.get("payload")
    if isinstance(payload, dict):
        return payload.get("missing_reason")
    return None


def _activation_freshness_key(row: MappingLike) -> tuple[str, str, str]:
    """Canonical freshness order for current-activation selection."""

    return (
        str(row.get("updated_at") or ""),
        str(row.get("created_at") or ""),
        str(row.get("activation_id") or ""),
    )


def activation_rows_with_family_keys(
    store: ObservationScheduleStore,
    activations: list[MappingLike] | tuple[MappingLike, ...],
) -> list[dict[str, Any]]:
    """Attach canonical family identity before current-state selection."""

    enriched: list[dict[str, Any]] = []
    for raw in activations:
        row = dict(raw)
        schedule_sha256 = str(row.get("schedule_sha256") or "")
        registered = (
            store.get_registered_schedule(schedule_sha256)
            if schedule_sha256
            else None
        )
        if registered is not None:
            try:
                row["cohort_family_key"] = cohort_family_key(
                    registered["document"]
                )
            except (KeyError, TypeError, ValueError):
                pass
        enriched.append(row)
    return enriched


def activation_selection_status(
    activations: list[MappingLike] | tuple[MappingLike, ...],
    *,
    family_key: str | None = None,
) -> str:
    """Classify whether current-activation selection has a safe scope.

    An explicit non-empty family key is a caller-provided scope.  Without one,
    every row must carry the same canonical family identity.  Missing family
    identity is ambiguity, not evidence that the activation set is empty.
    """

    if family_key:
        return "SCOPED"
    if not activations:
        return "EMPTY"
    family_keys = {
        str(row.get("cohort_family_key") or "")
        for row in activations
        if str(row.get("cohort_family_key") or "")
    }
    has_unscoped_rows = any(
        not str(row.get("cohort_family_key") or "") for row in activations
    )
    if has_unscoped_rows or len(family_keys) != 1:
        return "AMBIGUOUS"
    return "SCOPED"


def select_current_activation(
    activations: list[MappingLike] | tuple[MappingLike, ...],
    *,
    now: datetime | None = None,
    family_key: str | None = None,
    explicit_scope: bool = False,
) -> dict[str, Any] | None:
    """Deterministic current campaign activation for status/doctor/operability.

    Precedence:
    1. current ACTIVE (freshest if several)
    2. otherwise current DRAINING (freshest if several)
    3. otherwise latest relevant activation by canonical freshness order

    Historical ABORTED_SAFETY remains selectable only when no ACTIVE/DRAINING
    peer exists; it is never preferred over a live draining campaign.
    Missing family identity or multiple canonical family keys without an
    explicit scope are ambiguous and fail closed instead of allowing one
    family to mask another.  A caller that already supplied one exact
    schedule+activation selector may set ``explicit_scope``.
    """

    clock = None
    if now is not None:
        clock = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
        clock = clock.astimezone(UTC)
    rows: list[dict[str, Any]] = []
    for raw in activations:
        row = dict(raw)
        if clock is not None:
            payload = row.get("payload")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (TypeError, ValueError):
                    payload = None
            if isinstance(payload, dict):
                effective_raw = payload.get("transition_effective_at")
                if effective_raw:
                    try:
                        effective_at = parse_utc(str(effective_raw))
                    except (TypeError, ValueError):
                        effective_at = None
                    if effective_at is not None and effective_at > clock:
                        prior_state = str(payload.get("prior_state") or "")
                        if prior_state in {"ACTIVE", "DRAINING"}:
                            row["state"] = prior_state
                            row["future_transition_pending"] = True
                        else:
                            continue
        rows.append(row)
    if family_key is not None:
        rows = [
            row
            for row in rows
            if str(row.get("cohort_family_key") or "") == family_key
        ]
    elif (
        (not explicit_scope or len(rows) != 1)
        and activation_selection_status(rows) == "AMBIGUOUS"
    ):
        return None
    if not rows:
        return None
    active = [row for row in rows if str(row.get("state") or "") == "ACTIVE"]
    if active:
        return max(active, key=_activation_freshness_key)
    draining = [row for row in rows if str(row.get("state") or "") == "DRAINING"]
    if draining:
        return max(draining, key=_activation_freshness_key)
    return max(rows, key=_activation_freshness_key)


def classify_doctor_current_activation(
    activations: list[MappingLike] | tuple[MappingLike, ...],
    *,
    recovery_proofs: MappingLike | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Map current activation selection to doctor terminal precedence.

    Historical ABORTED_SAFETY never overrides a current ACTIVE/DRAINING campaign.
    """

    selection_status = activation_selection_status(activations)
    if selection_status == "AMBIGUOUS":
        return {
            "terminal": "DOCTOR_ACTIVATION_SCOPE_AMBIGUOUS",
            "live_activation": False,
            "current_activation_id": None,
            "current_schedule_sha256": None,
            "current_activation_state": "UNKNOWN",
            "activation_selection_status": selection_status,
            "stops_admitting_at": None,
            "late_recovery_at": None,
            "late_recovery_proof": "UNKNOWN",
            "late_recovery_event_id": None,
            "next_action": "RECONCILE_ACTIVATION_FAMILY_SCOPE",
        }

    current = select_current_activation(activations, now=now)
    current_state = str((current or {}).get("state") or "")
    current_id = (current or {}).get("activation_id")
    current_digest = (current or {}).get("schedule_sha256")
    live = current_state == "ACTIVE"
    stops_admitting_at = (current or {}).get("stops_admitting_at")
    late_recovery_at = None
    recovery_proof = None
    if current_state == "DRAINING":
        recovery_proof = "UNKNOWN"
        recovery_key = (
            str(current_digest or ""),
            str(current_id or ""),
        )
        proof = (
            recovery_proofs.get(recovery_key)
            if isinstance(recovery_proofs, MappingLike) and current_id is not None
            else None
        )
        if isinstance(proof, MappingLike):
            late_recovery_at = proof.get("late_recovery_at")
            recovery_proof = proof.get("late_recovery_proof") or "UNKNOWN"
    lifecycle_fields = {
        "stops_admitting_at": stops_admitting_at,
        "late_recovery_at": late_recovery_at,
        "late_recovery_proof": recovery_proof,
        "late_recovery_event_id": (
            proof.get("late_recovery_event_id")
            if current_state == "DRAINING" and isinstance(proof, MappingLike)
            else (
                (current or {}).get("last_transition_event_id")
                if current_state == "DRAINING"
                else None
            )
        ),
    }
    if current_state == "ABORTED_SAFETY":
        return {
            **lifecycle_fields,
            "activation_selection_status": selection_status,
            "terminal": "DOCTOR_ABORTED_SAFETY",
            "live_activation": False,
            "current_activation_id": current_id,
            "current_schedule_sha256": current_digest,
            "current_activation_state": current_state,
            "next_action": "MUST_NOT_RESUME",
        }
    if current_state == "PAUSED_OPERATOR":
        return {
            **lifecycle_fields,
            "activation_selection_status": selection_status,
            "terminal": "DOCTOR_PAUSED",
            "live_activation": False,
            "current_activation_id": current_id,
            "current_schedule_sha256": current_digest,
            "current_activation_state": current_state,
            "next_action": "RESUME",
        }
    if current_state == "DRAINING" and recovery_proof == "UNKNOWN":
        return {
            **lifecycle_fields,
            "activation_selection_status": selection_status,
            "terminal": "DOCTOR_RECOVERY_PROOF_UNAVAILABLE",
            "live_activation": False,
            "current_activation_id": current_id,
            "current_schedule_sha256": current_digest,
            "current_activation_state": current_state,
            "next_action": "REPAIR_DRAINING_RECOVERY_PROOF",
        }
    if current_state in {"ACTIVE", "DRAINING"}:
        return {
            **lifecycle_fields,
            "activation_selection_status": selection_status,
            "terminal": "DOCTOR_CURRENT_OK",
            "live_activation": live,
            "current_activation_id": current_id,
            "current_schedule_sha256": current_digest,
            "current_activation_state": current_state,
            "next_action": (
                "TICK_ONCE"
                if (
                    current_state == "ACTIVE"
                    or late_recovery_at is not None
                    or recovery_proof == "NOT_REQUIRED"
                )
                else "REPAIR_DRAINING_RECOVERY_PROOF"
            ),
        }
    return {
        **lifecycle_fields,
        "activation_selection_status": selection_status,
        "terminal": "DOCTOR_NO_LIVE_ACTIVATION",
        "live_activation": False,
        "current_activation_id": current_id,
        "current_schedule_sha256": current_digest,
        "current_activation_state": current_state or None,
        "next_action": "REGISTER_AUTHORIZE_ACTIVATE",
    }


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


def _attempt_kind(http_class: object) -> str:
    text = str(http_class or "")
    if text in {HTTP_CLASS_401, HTTP_CLASS_403}:
        return _KIND_AUTH
    if text == HTTP_CLASS_429:
        return _KIND_RATE
    if text in {HTTP_CLASS_5XX, HTTP_CLASS_TIMEOUT, HTTP_CLASS_TRANSPORT}:
        return _KIND_FAILED
    if text == HTTP_CLASS_OK:
        return _KIND_OK
    return _KIND_OTHER


def derive_current_provider_state(
    calls: list[dict[str, Any]],
    *,
    now: datetime,
) -> dict[str, bool]:
    """Latest-by-time per primitive; 24h counters stay separate diagnostics.

    Proven recovery is a later same-primitive HTTP_OK on a non-STARTED
    ledger row. A later STARTED or unclassified call cannot clear an unresolved
    failure. Future timestamps cannot manufacture recovery. A later success on
    a different primitive cannot clear another primitive. Malformed
    timestamps never count as success. Future-dated rows cannot replace a
    valid-time classification: future HTTP_OK is ignored, and future failures
    remain unresolved without becoming the latest attempt.
    """

    latest_failure_at: dict[str, datetime] = {}
    latest_failure_kinds: dict[str, set[str]] = {}
    latest_success_at: dict[str, datetime] = {}
    malformed_kinds: dict[str, set[str]] = {}

    for call in calls:
        payload = call.get("payload") or {}
        if isinstance(payload, str):
            continue
        primitive = str(call.get("primitive_id") or "")
        if str(call.get("state") or "") == "STARTED":
            continue
        kind = _attempt_kind(payload.get("http_class"))
        updated = _safe_parse(call.get("updated_at") or call.get("created_at"))
        if updated is None:
            if kind in {_KIND_AUTH, _KIND_RATE, _KIND_FAILED}:
                malformed_kinds.setdefault(primitive, set()).add(kind)
            continue
        if updated > now:
            if kind in {_KIND_AUTH, _KIND_RATE, _KIND_FAILED}:
                malformed_kinds.setdefault(primitive, set()).add(kind)
            continue
        if kind == _KIND_OK:
            success_at = latest_success_at.get(primitive)
            if success_at is None or updated > success_at:
                latest_success_at[primitive] = updated
            continue
        if kind not in {_KIND_AUTH, _KIND_RATE, _KIND_FAILED}:
            continue
        previous_at = latest_failure_at.get(primitive)
        if previous_at is None or updated > previous_at:
            latest_failure_at[primitive] = updated
            latest_failure_kinds[primitive] = {kind}
        elif updated == previous_at:
            latest_failure_kinds.setdefault(primitive, set()).add(kind)

    auth = False
    rate = False
    failed = False
    primitives = set(latest_failure_kinds) | set(malformed_kinds)
    for primitive in primitives:
        unresolved: set[str] = set(malformed_kinds.get(primitive) or ())
        failure_at = latest_failure_at.get(primitive)
        success_at = latest_success_at.get(primitive)
        if failure_at is not None and (success_at is None or success_at <= failure_at):
            unresolved.update(latest_failure_kinds.get(primitive) or ())
        if _KIND_AUTH in unresolved:
            auth = True
        if _KIND_RATE in unresolved:
            rate = True
        if _KIND_FAILED in unresolved:
            failed = True
    return {
        "provider_current_auth_failed": auth,
        "provider_current_rate_limited": rate,
        "provider_current_failed": failed,
    }


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
    activations = activation_rows_with_family_keys(store, store.list_activations())
    selection_status = activation_selection_status(activations)
    selected = None
    if schedule_sha256 and activation_id:
        requested = store.get_activation(schedule_sha256, activation_id)
        if requested is not None:
            selected = select_current_activation(
                activation_rows_with_family_keys(store, [requested]),
                now=now,
                explicit_scope=True,
            )
            selection_status = "SCOPED"
    elif activations:
        selected = select_current_activation(activations, now=now)
    digest = str((selected or {}).get("schedule_sha256") or schedule_sha256 or "")
    act_id = str((selected or {}).get("activation_id") or activation_id or "")
    activation_state = (
        "UNKNOWN"
        if selection_status == "AMBIGUOUS"
        else str((selected or {}).get("state") or "NONE")
    )

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
    current_state_calls: list[dict[str, Any]] = []

    for call in store.list_calls():
        payload = call.get("payload") or {}
        if isinstance(payload, str):
            continue
        updated = _safe_parse(call.get("updated_at") or call.get("created_at"))
        if updated is None:
            current_state_calls.append(call)
            continue
        if updated < window_start:
            continue
        current_state_calls.append(call)
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
    current_provider = derive_current_provider_state(current_state_calls, now=now)

    health_flags: list[str] = []
    if store.restore_marker_unresolved():
        health_flags.append("BACKUP_DEGRADED")
    if activation_state == "ACTIVE":
        health_flags.append("PROCESS_OK")
    if current_provider["provider_current_auth_failed"]:
        health_flags.append("PROVIDER_AUTH_FAILED")
    if current_provider["provider_current_rate_limited"]:
        health_flags.append("PROVIDER_RATE_LIMITED")
    if current_provider["provider_current_failed"]:
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
        "activation_selection_status": selection_status,
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
        **current_provider,
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


__all__ = [
    "activation_selection_status",
    "build_collector_read_model",
    "build_m1_progress_projection",
    "classify_doctor_current_activation",
    "derive_current_provider_state",
    "select_current_activation",
]


def build_m1_progress_projection(
    store: ObservationScheduleStore,
    *,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Minimal provisional M1 campaign progress projection (§23).

    Operational provisional counters only; the final scientific M1 result
    comes from the frozen immutable-lineage calibration report, never from
    this moving read-model projection.
    """

    from solana_alpha_lab.factory.m1_execution_reality import (
        NOTIONAL_ENTRY_PRIMITIVE,
        NOTIONAL_REVERSE_PRIMITIVE,
        M1_NOTIONALS,
    )

    m1_primitives = {
        NOTIONAL_ENTRY_PRIMITIVE[n] for n in M1_NOTIONALS
    } | {NOTIONAL_REVERSE_PRIMITIVE[n] for n in M1_NOTIONALS}
    del m1_primitives  # documentation only; counting goes through scoped rows
    sampled = 0
    complete_dual_notional = 0
    outcome_counts: dict[str, dict[str, int]] = {
        n: {"TWO_WAY": 0, "ENTRY_ONLY": 0, "NO_ENTRY": 0, "UNKNOWN": 0}
        for n in M1_NOTIONALS
    }
    m1_calls = 0
    last_progress_at = None
    blocker: str | None = None

    from solana_alpha_lab.factory.m1_execution_reality import (
        classify_execution_outcome,
        leg_class,
    )

    terminal_states = (
        "PENDING",
        "DUE",
        "CLAIMED",
        "STARTED",
        "OBSERVED",
        "MISSING_TYPED",
        "DISAPPEARED",
        "CENSORED",
        "CENSORED_LATE",
        "IN_FLIGHT_CALL_INDETERMINATE",
        "DEPENDENCY_MISSING",
        "BLOCKED_BUDGET",
    )
    # States that imply a provider call was actually issued for the leg.
    # PENDING/DUE/CLAIMED/STARTED are scheduled but unexecuted;
    # DEPENDENCY_MISSING/BLOCKED_BUDGET/CENSORED never opened a socket.
    _call_issued_states = frozenset(
        {
            "OBSERVED",
            "MISSING_TYPED",
            "DISAPPEARED",
            "CENSORED_LATE",
            "IN_FLIGHT_CALL_INDETERMINATE",
        }
    )

    def _scoped_leg_rows(entity_id: str, primitive_id: str) -> list[dict[str, Any]]:
        return store.list_due_in_states_scoped(
            terminal_states,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            entity_id=entity_id,
            primitive_ids=(primitive_id,),
        )

    for cand in store.list_candidates(
        schedule_sha256=schedule_sha256, activation_id=activation_id
    ):
        if str(cand.get("state") or "") not in {"X_ELIGIBLE", "SAMPLED_MEMBER", "MEMBER"}:
            continue
        entity_id = str(cand.get("entity_id") or "")
        if not entity_id:
            continue
        sampled += 1
        member_outcomes: dict[str, str] = {}
        for notional in M1_NOTIONALS:
            entry_rows = _scoped_leg_rows(entity_id, NOTIONAL_ENTRY_PRIMITIVE[notional])
            reverse_rows = _scoped_leg_rows(
                entity_id, NOTIONAL_REVERSE_PRIMITIVE[notional]
            )
            m1_calls += sum(
                1
                for row in entry_rows + reverse_rows
                if str(row.get("state") or "") in _call_issued_states
            )
            entry_row = entry_rows[-1] if entry_rows else None
            reverse_row = reverse_rows[-1] if reverse_rows else None
            for row in (entry_row, reverse_row):
                if row is None:
                    continue
                updated = _safe_parse(row.get("updated_at") or row.get("created_at"))
                if updated is not None and (
                    last_progress_at is None or updated > last_progress_at
                ):
                    last_progress_at = updated
            entry_leg = (
                leg_class(
                    state=str(entry_row.get("state") or ""),
                    missing_reason=_payload_missing_reason(entry_row),
                )
                if entry_row is not None
                else "UNKNOWN"
            )
            reverse_leg = (
                leg_class(
                    state=str(reverse_row.get("state") or ""),
                    missing_reason=_payload_missing_reason(reverse_row),
                )
                if reverse_row is not None
                else None
            )
            member_outcomes[notional] = classify_execution_outcome(entry_leg, reverse_leg)
            outcome_counts[notional][member_outcomes[notional]] += 1
        if all(member_outcomes[n] != "UNKNOWN" for n in M1_NOTIONALS):
            complete_dual_notional += 1

    # Exact blocker: only material operational blockers surfaced by the
    # existing read-model semantics.
    activations = store.get_activation(schedule_sha256, activation_id)
    state = str((activations or {}).get("state") or "NONE") if activations else "NONE"
    if state != "ACTIVE":
        blocker = f"ACTIVATION_{state}"
    elif store.restore_marker_unresolved():
        blocker = "BACKUP_DEGRADED"

    return {
        "projection": "M1_PROGRESS_PROVISIONAL",
        "m1_active": state == "ACTIVE",
        "schedule_sha256": schedule_sha256,
        "activation_id": activation_id,
        "sampled_member_count": sampled,
        "complete_dual_notional_member_count": complete_dual_notional,
        "provisional_outcome_counts": {
            f"notional_{n}_usd": outcome_counts[n] for n in M1_NOTIONALS
        },
        "m1_provider_calls_used": m1_calls,
        "last_m1_progress_at": render_utc(last_progress_at) if last_progress_at else None,
        "blocker": blocker,
        "final_result_source": "FROZEN_M1_CALIBRATION_REPORT_ONLY",
    }
