"""ObservationSchedule tick physical-dependency composition seam.

One production assembly path. Deterministic parity supplies a complete
process-local TickPhysicalOverrides object; production uses overrides=None.
No CLI/config/env switch for fake transport or synthetic clock.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.observation_provider_pacing import (
    AdvancingClock,
    ClockSleepRequiredError,
    WallClock,
    require_sleep_capable_clock,
)
from solana_alpha_lab.factory.observation_schedule_runtime import build_opener


class CompositionParityError(ValueError):
    """Fail-closed composition / physical-override defect."""


@dataclass(frozen=True)
class TickPhysicalOverrides:
    """Complete test-owned physical boundaries. Process-local only."""

    now: datetime
    opener: object
    pacing_clock: object


@dataclass(frozen=True)
class TickPhysicalBinding:
    opener: object | None
    credential_loader: Callable[[], str] | None
    pacing_clock: object | None


def validate_tick_physical_overrides(
    overrides: TickPhysicalOverrides,
) -> TickPhysicalOverrides:
    if not isinstance(overrides, TickPhysicalOverrides):
        raise CompositionParityError("PHYSICAL_OVERRIDES_INCOMPLETE")
    if overrides.opener is None or overrides.pacing_clock is None:
        raise CompositionParityError("PHYSICAL_OVERRIDES_INCOMPLETE")
    if overrides.now.tzinfo is None:
        raise CompositionParityError("PHYSICAL_NOW_NOT_UTC")
    now_utc = overrides.now.astimezone(UTC)
    try:
        clock = require_sleep_capable_clock(overrides.pacing_clock)  # type: ignore[arg-type]
    except ClockSleepRequiredError as exc:
        raise CompositionParityError("CLOCK_SLEEP_REQUIRED") from exc
    if clock is None:
        raise CompositionParityError("PHYSICAL_OVERRIDES_INCOMPLETE")
    if isinstance(clock, AdvancingClock) and clock.now() != now_utc:
        raise CompositionParityError("PHYSICAL_CLOCK_NOW_MISMATCH")
    return overrides


def materialize_tick_physical_dependencies(
    *,
    root: Path,
    config: Mapping[str, Any],
    load_credential: Callable[[], str],
    physical_overrides: TickPhysicalOverrides | None = None,
) -> TickPhysicalBinding:
    """Assemble opener/credential/clock after live authority has passed.

    Production (overrides=None) preserves current fake-fixture vs WallClock
    semantics. Parity (complete overrides) never reads credentials or builds
    the production network opener.
    """

    if physical_overrides is not None:
        validate_tick_physical_overrides(physical_overrides)
        return TickPhysicalBinding(
            opener=physical_overrides.opener,
            credential_loader=None,
            pacing_clock=physical_overrides.pacing_clock,
        )
    if config.get("fake_provider_fixture"):
        return TickPhysicalBinding(
            opener=build_opener(root, config),
            credential_loader=load_credential,
            pacing_clock=None,
        )
    return TickPhysicalBinding(
        opener=build_opener(root, config, credential=load_credential()),
        credential_loader=None,
        pacing_clock=WallClock(),
    )


__all__ = [
    "CompositionParityError",
    "TickPhysicalBinding",
    "TickPhysicalOverrides",
    "materialize_tick_physical_dependencies",
    "validate_tick_physical_overrides",
]
