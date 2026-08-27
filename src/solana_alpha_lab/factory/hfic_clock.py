"""Injectable UTC provenance clock for Hypothesis Forge records."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

Clock = Callable[[], datetime]

CANONICAL_UTC_PATTERN = r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
_PLACEHOLDER_PREFIX = "1970-01-01"


class HficClockError(ValueError):
    """Fail-closed HFIC timestamp error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def resolve_clock(clock: Clock | None) -> Clock:
    return clock if clock is not None else utc_now


def is_placeholder_timestamp(value: object) -> bool:
    if isinstance(value, datetime):
        instant = value.astimezone(UTC) if value.tzinfo is not None else value
        return instant.year == 1970 and instant.month == 1 and instant.day == 1
    if not isinstance(value, str) or not value.strip():
        return False
    return value.strip().startswith(_PLACEHOLDER_PREFIX)


def render_canonical_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise HficClockError("HFIC_TIMESTAMP_NAIVE")
    instant = value.astimezone(UTC).replace(microsecond=0)
    if is_placeholder_timestamp(instant):
        raise HficClockError("HFIC_TIMESTAMP_PLACEHOLDER")
    text = instant.strftime("%Y-%m-%dT%H:%M:%SZ")
    validate_hfic_timestamp(text)
    return text


def parse_hfic_timestamp(value: object) -> datetime:
    text = validate_hfic_timestamp(value)
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def validate_hfic_timestamp(value: object) -> str:
    if value is None:
        raise HficClockError("HFIC_TIMESTAMP_MISSING")
    if isinstance(value, datetime):
        return render_canonical_utc(value)
    if not isinstance(value, str) or not value.strip():
        raise HficClockError("HFIC_TIMESTAMP_MISSING")
    text = value.strip()
    if is_placeholder_timestamp(text):
        raise HficClockError("HFIC_TIMESTAMP_PLACEHOLDER")
    if text.endswith("+00:00"):
        raise HficClockError("HFIC_TIMESTAMP_MALFORMED")
    if "T" not in text or not text.endswith("Z"):
        raise HficClockError("HFIC_TIMESTAMP_MALFORMED")
    body = text[:-1]
    try:
        parsed = datetime.strptime(body, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise HficClockError("HFIC_TIMESTAMP_MALFORMED") from exc
    if parsed.tzinfo is not None:
        raise HficClockError("HFIC_TIMESTAMP_MALFORMED")
    if not text.startswith("20"):
        raise HficClockError("HFIC_TIMESTAMP_MALFORMED")
    return text


def capture_stage_time(clock: Clock | None = None) -> datetime:
    instant = resolve_clock(clock)()
    if instant.tzinfo is None:
        raise HficClockError("HFIC_TIMESTAMP_NAIVE")
    aware = instant.astimezone(UTC)
    if is_placeholder_timestamp(aware):
        raise HficClockError("HFIC_TIMESTAMP_PLACEHOLDER")
    return aware.replace(microsecond=0)


class FrozenClock:
    """Deterministic clock that always returns one instant."""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise HficClockError("HFIC_TIMESTAMP_NAIVE")
        self._instant = instant.astimezone(UTC)

    def __call__(self) -> datetime:
        return self._instant


class SequenceClock:
    """Deterministic clock that yields a predeclared sequence of instants."""

    def __init__(self, instants: Sequence[datetime]) -> None:
        if not instants:
            raise HficClockError("HFIC_TIMESTAMP_MISSING")
        resolved: list[datetime] = []
        for instant in instants:
            if instant.tzinfo is None:
                raise HficClockError("HFIC_TIMESTAMP_NAIVE")
            resolved.append(instant.astimezone(UTC))
        self._instants = resolved
        self._index = 0

    def __call__(self) -> datetime:
        if self._index >= len(self._instants):
            raise HficClockError("HFIC_CLOCK_EXHAUSTED")
        value = self._instants[self._index]
        self._index += 1
        return value


def envelope_time_text(value: Any) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.strftime("%Y-%m-%dT%H:%M:%S")
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
