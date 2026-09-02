"""Activation-scoped due-pressure projection for collector health truth."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from solana_alpha_lab.factory.observation_schedule import parse_utc
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

_ACTIVE_DUE_STATES = frozenset({"PENDING", "DUE", "CLAIMED"})


def build_due_pressure_projection(
    store: ObservationScheduleStore,
    *,
    now: datetime,
    schedule_sha256: str | None = None,
    activation_id: str | None = None,
) -> dict[str, Any]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(UTC)

    future_not_due_count = 0
    due_now_count = 0
    claimed_count = 0
    actually_overdue_count = 0
    deadline_missed_count = 0
    in_flight_count = 0
    blocked_budget_count = 0
    oldest_overdue_age_seconds = 0
    minimum_deadline_slack_seconds: int | None = None

    rows = store.due_in_states(
        (
            "PENDING",
            "DUE",
            "CLAIMED",
            "CENSORED_LATE",
            "IN_FLIGHT_CALL_INDETERMINATE",
            "BLOCKED_BUDGET",
        ),
        due_at_max=now + timedelta(days=365),
    )
    for row in rows:
        if schedule_sha256 and str(row.get("schedule_sha256")) != schedule_sha256:
            continue
        if activation_id and str(row.get("activation_id")) != activation_id:
            continue
        state = str(row.get("state") or "")
        due_at = parse_utc(str(row["due_at"]))
        deadline_at = parse_utc(str(row["deadline_at"]))
        if state == "CENSORED_LATE":
            deadline_missed_count += 1
            continue
        if state == "IN_FLIGHT_CALL_INDETERMINATE":
            in_flight_count += 1
            continue
        if state == "BLOCKED_BUDGET":
            blocked_budget_count += 1
            continue
        if due_at > now:
            future_not_due_count += 1
            continue
        if state == "CLAIMED":
            claimed_count += 1
        else:
            due_now_count += 1
        if state in _ACTIVE_DUE_STATES:
            actually_overdue_count += 1
            age = int((now - due_at).total_seconds())
            oldest_overdue_age_seconds = max(oldest_overdue_age_seconds, age)
            slack = int((deadline_at - now).total_seconds())
            if minimum_deadline_slack_seconds is None or slack < minimum_deadline_slack_seconds:
                minimum_deadline_slack_seconds = slack

    return {
        "future_not_due_count": future_not_due_count,
        "due_now_count": due_now_count,
        "claimed_count": claimed_count,
        "actually_overdue_count": actually_overdue_count,
        "deadline_missed_count": deadline_missed_count,
        "in_flight_count": in_flight_count,
        "blocked_budget_count": blocked_budget_count,
        "oldest_overdue_age_seconds": oldest_overdue_age_seconds,
        "minimum_deadline_slack_seconds": minimum_deadline_slack_seconds,
        "pending_due_count": future_not_due_count + due_now_count + claimed_count,
    }


def backlog_risk_from_due_pressure(projection: dict[str, Any]) -> bool:
    """True only for timeliness-threatening pressure, not future scheduling depth."""

    if int(projection.get("blocked_budget_count") or 0) > 0:
        return True
    if int(projection.get("in_flight_count") or 0) > 0:
        return True
    overdue = int(projection.get("actually_overdue_count") or 0)
    oldest = int(projection.get("oldest_overdue_age_seconds") or 0)
    if overdue > 0 and oldest > 120:
        return True
    slack = projection.get("minimum_deadline_slack_seconds")
    due_now = int(projection.get("due_now_count") or 0)
    if due_now > 0 and isinstance(slack, int) and slack < 60:
        return True
    return False


__all__ = [
    "backlog_risk_from_due_pressure",
    "build_due_pressure_projection",
]
