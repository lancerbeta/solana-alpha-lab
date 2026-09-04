"""Waiter-side wall-clock deadline for ObservationSchedule provider calls.

Socket/urllib inactivity timeouts alone are not a sufficient end-to-end bound:
a stalled logical provider operation must still terminate before the scheduler
lease TTL so the tick cannot self-fence via LEASE_FENCED.

This wrapper is a waiter timeout, not a GIL-preempting hard kill. A worker
that holds the GIL (UTF-8 decode / ``json.loads`` of a huge body) can starve
``Event.wait`` and complete after the nominal wall — the V1 ``time.sleep``
stall did not represent that class. Bounded response + bounded parse in
``observation_provider_bounded_response`` is the GIL-starvation control.
The thread wrapper remains for I/O stalls that release the GIL.

ADOPT: stdlib threading + join slices (no new package). Heartbeat renews the
held lease while waiting; on wall expiry the waiter raises TimeoutError and
does not join the worker (daemon), so the owning tick can complete typed
TIMEOUT missingness and release the lease.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from solana_alpha_lab.factory.observation_schedule_store import LEASE_SECONDS

T = TypeVar("T")

# Must stay strictly below LEASE_SECONDS so a hung call cannot outlive the lease
# even if heartbeat slices are slightly delayed.
DEFAULT_PROVIDER_CALL_WALL_SECONDS = 60
PROVIDER_CALL_WALL_DEADLINE = "PROVIDER_CALL_WALL_DEADLINE"
_HEARTBEAT_SLICE_SECONDS = 5.0


class ProviderWallDeadlineError(TimeoutError):
    """Hard end-to-end provider-call wall deadline exceeded."""

    def __init__(self) -> None:
        super().__init__(PROVIDER_CALL_WALL_DEADLINE)


def resolve_provider_call_wall_seconds(config: dict[str, Any] | None = None) -> int:
    raw = None if config is None else config.get("provider_call_wall_seconds")
    if raw is None:
        value = DEFAULT_PROVIDER_CALL_WALL_SECONDS
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("PROVIDER_CALL_WALL_SECONDS_INVALID") from exc
    if value <= 0 or value >= LEASE_SECONDS:
        raise ValueError("PROVIDER_CALL_WALL_SECONDS_MUST_BE_BELOW_LEASE")
    return value


def run_with_provider_wall_deadline(
    fn: Callable[[], T],
    *,
    wall_seconds: float,
    heartbeat: Callable[[], None] | None = None,
    heartbeat_every_seconds: float = _HEARTBEAT_SLICE_SECONDS,
    sleeper: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
) -> T:
    """Run fn under a waiter-side wall-clock deadline.

    Heartbeat (if provided) runs on wait slices so a legitimate bounded wait
    renews the scheduler lease. On deadline, raises ProviderWallDeadlineError
    without blocking on the worker thread. Does not preempt GIL-bound work;
    pair with bounded body/parse so that class cannot reach LEASE_SECONDS.
    """

    if wall_seconds <= 0:
        raise ValueError("PROVIDER_CALL_WALL_SECONDS_INVALID")
    if wall_seconds >= LEASE_SECONDS:
        raise ValueError("PROVIDER_CALL_WALL_SECONDS_MUST_BE_BELOW_LEASE")
    clock = time.monotonic if monotonic is None else monotonic
    sleep = time.sleep if sleeper is None else sleeper
    slice_s = min(float(heartbeat_every_seconds), float(wall_seconds))
    if slice_s <= 0:
        slice_s = float(wall_seconds)

    box: dict[str, Any] = {}
    done = threading.Event()

    def _worker() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 — surface to waiter
            box["error"] = exc
        finally:
            done.set()

    worker = threading.Thread(
        target=_worker,
        name="observation-provider-wall",
        daemon=True,
    )
    worker.start()
    deadline = clock() + float(wall_seconds)
    try:
        while True:
            remaining = deadline - clock()
            if remaining <= 0:
                raise ProviderWallDeadlineError()
            wait_for = min(slice_s, remaining)
            if done.wait(timeout=wait_for):
                break
            if heartbeat is not None:
                heartbeat()
        if "error" in box:
            raise box["error"]
        return box["value"]  # type: ignore[no-any-return]
    finally:
        # Do not join: a wedged socket must not block tick completion.
        # Daemon thread dies with the process; oneshot ticks are short-lived.
        sleep(0)


class WallDeadlineOpener:
    """Wrap any opener.open(url) with the hard provider-call wall deadline."""

    def __init__(
        self,
        inner: object,
        *,
        wall_seconds: float,
        heartbeat: Callable[[], None] | None = None,
        sleeper: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        if not hasattr(inner, "open"):
            raise ValueError("PROVIDER_OPENER_MISSING_OPEN")
        self._inner = inner
        self._wall_seconds = float(wall_seconds)
        self._heartbeat = heartbeat
        self._sleeper = sleeper
        self._monotonic = monotonic

    @property
    def inner(self) -> object:
        return self._inner

    @property
    def wall_seconds(self) -> float:
        return self._wall_seconds

    def open(self, url: str) -> dict[str, Any]:
        return run_with_provider_wall_deadline(
            lambda: self._inner.open(url),  # type: ignore[union-attr]
            wall_seconds=self._wall_seconds,
            heartbeat=self._heartbeat,
            sleeper=self._sleeper,
            monotonic=self._monotonic,
        )


def wrap_opener_with_wall_deadline(
    opener: object | None,
    *,
    wall_seconds: float,
    heartbeat: Callable[[], None] | None = None,
) -> object | None:
    if opener is None:
        return None
    if isinstance(opener, WallDeadlineOpener):
        return opener
    return WallDeadlineOpener(
        opener,
        wall_seconds=wall_seconds,
        heartbeat=heartbeat,
    )


__all__ = [
    "DEFAULT_PROVIDER_CALL_WALL_SECONDS",
    "PROVIDER_CALL_WALL_DEADLINE",
    "ProviderWallDeadlineError",
    "WallDeadlineOpener",
    "resolve_provider_call_wall_seconds",
    "run_with_provider_wall_deadline",
    "wrap_opener_with_wall_deadline",
]
