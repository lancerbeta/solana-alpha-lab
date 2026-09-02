"""Unified provider pacing + bounded tick fairness for ObservationSchedule."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

TIMER_CADENCE_SECONDS = 60
DEFAULT_TICK_WALL_BUDGET_SECONDS = 55
MAX_INTRA_TICK_PACE_WAITS = 20
FREE_TIER_MIN_PACE_SECONDS = 3


class _AccountingGate(Protocol):
    budgets: Mapping[str, Any]
    pace: int

    def gate(
        self,
        *,
        extra_calls: int = 1,
        extra_credits: int = 1,
        extra_raw: int = 1,
        now: datetime | None = None,
    ) -> str | None: ...

    def note(
        self,
        *,
        raw_bytes: int = 1,
        credits: int = 1,
        completed_at: datetime | None = None,
    ) -> None: ...


class AdvancingClock:
    """Injectable clock with optional sleep for deterministic pacing tests."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("TIMESTAMP_INVALID")
        self._current = start.astimezone(UTC)

    def __call__(self) -> datetime:
        return self._current

    def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        self._current = self._current + timedelta(seconds=seconds)


class ProviderTickContext:
    """One provider pacing surface for all ObservationSchedule provider calls."""

    def __init__(
        self,
        *,
        tick_start: datetime,
        pace_seconds: int,
        injectable_clock: Callable[[], datetime] | AdvancingClock | None = None,
        tick_wall_budget_seconds: int = DEFAULT_TICK_WALL_BUDGET_SECONDS,
    ) -> None:
        if tick_start.tzinfo is None:
            raise ValueError("TIMESTAMP_INVALID")
        self.tick_start = tick_start.astimezone(UTC)
        self.pace_seconds = max(FREE_TIER_MIN_PACE_SECONDS, int(pace_seconds))
        self.tick_wall_budget_seconds = int(tick_wall_budget_seconds)
        self._injectable = injectable_clock
        self._logical_offset = timedelta(0)
        self.pace_waits = 0
        self.provider_completions = 0

    def now(self) -> datetime:
        if self._injectable is not None:
            return self._injectable().astimezone(UTC)
        return self.tick_start + self._logical_offset

    def clock(self) -> Callable[[], datetime]:
        return self.now

    def elapsed_tick_seconds(self) -> float:
        return max(0.0, (self.now() - self.tick_start).total_seconds())

    def tick_budget_exhausted(self) -> bool:
        return self.elapsed_tick_seconds() >= self.tick_wall_budget_seconds

    def _advance_pace_wait(self) -> None:
        self.pace_waits += 1
        if self._injectable is not None:
            sleeper = getattr(self._injectable, "sleep", None)
            if callable(sleeper):
                sleeper(self.pace_seconds)
                return
        self._logical_offset += timedelta(seconds=self.pace_seconds)

    def wait_for_provider_slot(
        self,
        accounts: _AccountingGate,
        *,
        extra_calls: int = 1,
        extra_credits: int = 1,
        extra_raw: int = 1,
    ) -> str | None:
        """Wait/defer safely until a provider slot opens within the tick budget."""

        while True:
            blocked = accounts.gate(
                extra_calls=extra_calls,
                extra_credits=extra_credits,
                extra_raw=extra_raw,
                now=self.now(),
            )
            if blocked != "PACE_WAIT":
                return blocked
            if self.pace_waits >= MAX_INTRA_TICK_PACE_WAITS:
                return "PACE_WAIT"
            if self.elapsed_tick_seconds() + self.pace_seconds > self.tick_wall_budget_seconds:
                return "PACE_WAIT"
            self._advance_pace_wait()

    def record_provider_completion(
        self,
        accounts: _AccountingGate,
        *,
        raw_bytes: int = 1,
        credits: int = 1,
        completed_at: datetime | None = None,
    ) -> None:
        completion = (completed_at or self.now()).astimezone(UTC)
        accounts.note(raw_bytes=raw_bytes, credits=credits, completed_at=completion)
        self.provider_completions += 1
        if self._injectable is None:
            self._logical_offset = max(
                self._logical_offset,
                completion - self.tick_start + timedelta(seconds=self.pace_seconds),
            )

    def should_defer_fresh_source_poll(
        self,
        accounts: _AccountingGate,
        *,
        matured_due_count: int,
        poll_slot_cached: bool,
    ) -> bool:
        """Defer a fresh /recent slot when due work would starve on the same frozen tick."""

        if poll_slot_cached or matured_due_count <= 0:
            return False
        return accounts.gate(extra_credits=1, now=self.now()) == "PACE_WAIT"


def max_provider_calls_per_tick(
    *,
    pace_seconds: int,
    tick_wall_budget_seconds: int = DEFAULT_TICK_WALL_BUDGET_SECONDS,
    max_claims_per_tick: int = 60,
) -> int:
    pace = max(FREE_TIER_MIN_PACE_SECONDS, int(pace_seconds))
    budget_calls = max(1, tick_wall_budget_seconds // pace)
    return min(int(max_claims_per_tick), budget_calls)


def reserved_source_poll_calls(*, poll_period_seconds: int, timer_cadence_seconds: int) -> int:
    if poll_period_seconds <= 0:
        return 0
    if timer_cadence_seconds < poll_period_seconds:
        return 1
    return max(1, timer_cadence_seconds // poll_period_seconds)


def usable_due_calls_per_tick(
    *,
    pace_seconds: int,
    poll_period_seconds: int,
    timer_cadence_seconds: int = TIMER_CADENCE_SECONDS,
    tick_wall_budget_seconds: int = DEFAULT_TICK_WALL_BUDGET_SECONDS,
    max_claims_per_tick: int = 60,
) -> int:
    total = max_provider_calls_per_tick(
        pace_seconds=pace_seconds,
        tick_wall_budget_seconds=tick_wall_budget_seconds,
        max_claims_per_tick=max_claims_per_tick,
    )
    poll_reserve = min(
        total,
        reserved_source_poll_calls(
            poll_period_seconds=poll_period_seconds,
            timer_cadence_seconds=timer_cadence_seconds,
        ),
    )
    return max(0, total - poll_reserve)


__all__ = [
    "AdvancingClock",
    "DEFAULT_TICK_WALL_BUDGET_SECONDS",
    "FREE_TIER_MIN_PACE_SECONDS",
    "MAX_INTRA_TICK_PACE_WAITS",
    "ProviderTickContext",
    "TIMER_CADENCE_SECONDS",
    "max_provider_calls_per_tick",
    "reserved_source_poll_calls",
    "usable_due_calls_per_tick",
    "wait_for_provider_slot",
]

# Back-compat alias for internal import style
wait_for_provider_slot = ProviderTickContext.wait_for_provider_slot
