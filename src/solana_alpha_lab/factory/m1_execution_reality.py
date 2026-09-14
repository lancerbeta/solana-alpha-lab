"""M1 execution reality calibration: typed outcomes, denominator, friction.

M1 classifies the quote surface exposed by the existing ObservationSchedule
collector spine at fixed $10/$100 USDC notionals for canonical fresh EARLY
pump.fun candidates. This module is pure typed classification and arithmetic
over already-collected typed evidence; it performs no provider calls and no
runtime mutation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

M1_SCHEMA_VERSION = "1.0"
M1_CAPABILITY_ID = "CAP-M1-EXECUTION-REALITY-CALIBRATION-001"

# Canonical notional identities (atomic USDC, 6 decimals).
NOTIONAL_10_USD = "10"
NOTIONAL_100_USD = "100"
NOTIONAL_ATOMIC = {
    NOTIONAL_10_USD: "10000000",
    NOTIONAL_100_USD: "100000000",
}
NOTIONAL_ENTRY_PRIMITIVE = {
    NOTIONAL_10_USD: "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-USDC10-001",
    NOTIONAL_100_USD: "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-USDC100-001",
}
NOTIONAL_REVERSE_PRIMITIVE = {
    NOTIONAL_10_USD: "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-USDC10-001",
    NOTIONAL_100_USD: "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-USDC100-001",
}
NOTIONAL_ENTRY_BUNDLE = {
    NOTIONAL_10_USD: "BUNDLE-JUPITER-QUOTE-BUY-USDC10-001",
    NOTIONAL_100_USD: "BUNDLE-JUPITER-QUOTE-BUY-USDC100-001",
}
NOTIONAL_REVERSE_BUNDLE = {
    NOTIONAL_10_USD: "BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-USDC10-001",
    NOTIONAL_100_USD: "BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-USDC100-001",
}
M1_NOTIONALS = (NOTIONAL_10_USD, NOTIONAL_100_USD)

# M1 execution outcome classes (per notional).
OUTCOME_TWO_WAY = "TWO_WAY"
OUTCOME_ENTRY_ONLY = "ENTRY_ONLY"
OUTCOME_NO_ENTRY = "NO_ENTRY"
OUTCOME_UNKNOWN = "UNKNOWN"
M1_OUTCOMES = (OUTCOME_TWO_WAY, OUTCOME_ENTRY_ONLY, OUTCOME_NO_ENTRY, OUTCOME_UNKNOWN)

# Typed terminal classes on one quote leg.
LEG_OBSERVED = "QUOTE_OBSERVED"
LEG_NO_ROUTE = "NO_ROUTE"
LEG_NOTIONAL_NO_ROUTE = "NOTIONAL_NO_ROUTE"
LEG_UNKNOWN = "UNKNOWN"

# Quote missing_reason → leg classification. Registry typed classes only.
_LEG_CLASS_BY_MISSING_REASON = {
    "NO_ROUTE": LEG_NO_ROUTE,
    "NOTIONAL_NO_ROUTE": LEG_NOTIONAL_NO_ROUTE,
}


class M1ExecutionRealityError(ValueError):
    """Typed M1 classification failure."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise M1ExecutionRealityError(code)


def leg_class(
    *,
    state: str | None,
    missing_reason: str | None,
) -> str:
    """Classify one quote leg from typed scheduler terminal evidence.

    OBSERVED → QUOTE_OBSERVED; typed market route-unavailable → NO_ROUTE
    (market or notional variants are both execution-unavailable for M1);
    everything else (timeout, transport, HTTP error, schema drift,
    unrecognized provider error, dependency gaps of unknown origin) → UNKNOWN.
    """

    if state == "OBSERVED":
        return LEG_OBSERVED
    reason = str(missing_reason or "")
    mapped = _LEG_CLASS_BY_MISSING_REASON.get(reason)
    if mapped is not None:
        return mapped
    return LEG_UNKNOWN


def classify_execution_outcome(
    entry_leg: str,
    reverse_leg: str | None,
) -> str:
    """Map (entry, reverse) leg classes to one M1 outcome.

    Entry market/no-route → NO_ENTRY. Entry observed + reverse market
    no-route → ENTRY_ONLY. Both observed → TWO_WAY. Any UNKNOWN leg (or a
    reverse leg with no typed evidence at all while entry is observed but the
    dependency chain is indeterminate) → UNKNOWN.
    """

    _require(entry_leg in {LEG_OBSERVED, LEG_NO_ROUTE, LEG_NOTIONAL_NO_ROUTE, LEG_UNKNOWN}, "ENTRY_LEG_CLASS_INVALID")
    if entry_leg == LEG_UNKNOWN:
        return OUTCOME_UNKNOWN
    if entry_leg in {LEG_NO_ROUTE, LEG_NOTIONAL_NO_ROUTE}:
        return OUTCOME_NO_ENTRY
    # entry observed from here
    if reverse_leg is None:
        return OUTCOME_UNKNOWN
    _require(
        reverse_leg in {LEG_OBSERVED, LEG_NO_ROUTE, LEG_NOTIONAL_NO_ROUTE, LEG_UNKNOWN},
        "REVERSE_LEG_CLASS_INVALID",
    )
    if reverse_leg == LEG_UNKNOWN:
        return OUTCOME_UNKNOWN
    if reverse_leg in {LEG_NO_ROUTE, LEG_NOTIONAL_NO_ROUTE}:
        return OUTCOME_ENTRY_ONLY
    return OUTCOME_TWO_WAY


def notional_outcome_counts(
    outcomes: Sequence[str],
) -> dict[str, int]:
    """Count M1 outcomes and verify the denominator invariant closes."""

    counts = {outcome: 0 for outcome in M1_OUTCOMES}
    for outcome in outcomes:
        _require(outcome in counts, "OUTCOME_CLASS_INVALID")
        counts[outcome] += 1
    return counts


def verify_denominatorInvariant(  # noqa: N802 (kept explicit)
    population_n: int,
    counts: Mapping[str, int],
) -> None:
    """population_n == two_way_n + entry_only_n + no_entry_n + unknown_n."""

    total = sum(int(counts[name]) for name in M1_OUTCOMES)
    _require(
        int(population_n) == total,
        "M1_DENOMINATOR_INVARIANT_VIOLATION",
    )


def quote_implied_roundtrip_friction(
    *,
    entry_notional_atomic: str,
    entry_out_amount: str,
    reverse_out_amount: str,
) -> str:
    """Deterministic quote-implied roundtrip friction as a Decimal string.

    friction = 1 - (reverse_out / entry_notional) for USDC-notional entries.
    Both amounts are base-10 atomic strings of the same asset (USDC in /
    USDC out), so the ratio is unit-correct without decimal rescaling.
    """

    for name, value in (
        ("entry_notional_atomic", entry_notional_atomic),
        ("entry_out_amount", entry_out_amount),
        ("reverse_out_amount", reverse_out_amount),
    ):
        _require(isinstance(value, str) and value != "", f"{name}_INVALID")
    try:
        notional = Decimal(entry_notional_atomic)
        reverse = Decimal(reverse_out_amount)
        entry_out = Decimal(entry_out_amount)
    except InvalidOperation as exc:
        raise M1ExecutionRealityError("FRICTION_AMOUNT_NOT_DECIMAL") from exc
    _require(notional > 0, "ENTRY_NOTIONAL_MUST_BE_POSITIVE")
    _require(entry_out > 0, "ENTRY_OUT_MUST_BE_POSITIVE")
    _require(reverse >= 0, "REVERSE_OUT_MUST_BE_NON_NEGATIVE")
    friction = Decimal(1) - (reverse / notional)
    return str(friction)


def friction_summary(
    frictions: Sequence[str],
) -> dict[str, Any]:
    """Deterministic n / median / p25 / p75 / min / max over Decimal strings."""

    values: list[Decimal] = []
    for item in frictions:
        try:
            values.append(Decimal(item))
        except InvalidOperation as exc:
            raise M1ExecutionRealityError("FRICTION_VALUE_NOT_DECIMAL") from exc
    _require(bool(values), "FRICTION_SUMMARY_EMPTY")
    values.sort()
    n = len(values)

    def _median(sorted_values: list[Decimal]) -> Decimal:
        mid = len(sorted_values) // 2
        if len(sorted_values) % 2 == 1:
            return sorted_values[mid]
        return (sorted_values[mid - 1] + sorted_values[mid]) / Decimal(2)

    def _quantile(sorted_values: list[Decimal], q: Decimal) -> Decimal:
        # Linear interpolation on deterministic sorted order.
        pos = q * (len(sorted_values) - 1)
        low = int(pos)
        high = min(low + 1, len(sorted_values) - 1)
        frac = pos - low
        return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * frac

    return {
        "n": n,
        "median": str(_median(values)),
        "p25": str(_quantile(values, Decimal("0.25"))),
        "p75": str(_quantile(values, Decimal("0.75"))),
        "min": str(values[0]),
        "max": str(values[-1]),
    }


def normalized_entry_size_linearity(
    *,
    entry_out_10: str,
    entry_out_100: str,
) -> str:
    """entry_out_100 / (10 x entry_out_10) as a Decimal string.

    Unit-correct normalized diagnostic: both outputs are atomic token amounts
    of the same token at the same decision time slice, so the ratio of the
    $100 output to ten times the $10 output measures quote linearity in entry
    size. EXECUTION_DIAGNOSTIC only; never a signal or admission rule.
    """

    try:
        out10 = Decimal(entry_out_10)
        out100 = Decimal(entry_out_100)
    except InvalidOperation as exc:
        raise M1ExecutionRealityError("LINEARITY_AMOUNT_NOT_DECIMAL") from exc
    _require(out10 > 0, "ENTRY_OUT_10_MUST_BE_POSITIVE")
    _require(out100 >= 0, "ENTRY_OUT_100_MUST_BE_NON_NEGATIVE")
    return str(out100 / (Decimal(10) * out10))


def cross_notional_transition(
    *,
    outcome_10: str,
    outcome_100: str,
) -> str:
    """Canonical paired-transition key ``<OUT10>__<OUT100>``."""

    _require(outcome_10 in M1_OUTCOMES, "OUTCOME_10_INVALID")
    _require(outcome_100 in M1_OUTCOMES, "OUTCOME_100_INVALID")
    return f"{outcome_10}__{outcome_100}"


def cross_notional_transition_counts(
    transitions: Sequence[str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for transition in transitions:
        left, _, right = transition.partition("__")
        _require(left in M1_OUTCOMES and right in M1_OUTCOMES, "TRANSITION_INVALID")
        counts[transition] = counts.get(transition, 0) + 1
    return dict(sorted(counts.items()))


def classify_member_outcomes(
    member_evidence: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, str]:
    """Classify per-notional outcomes for one member.

    ``member_evidence`` shape: ``{notional: {"entry": {...}, "reverse": {...}}}``
    where each leg carries ``state`` and optionally ``missing_reason`` typed
    fields as persisted by the scheduler (or None when no typed evidence
    exists).
    """

    outcomes: dict[str, str] = {}
    for notional in M1_NOTIONALS:
        legs = member_evidence.get(notional)
        if not isinstance(legs, Mapping):
            outcomes[notional] = OUTCOME_UNKNOWN
            continue
        entry_leg = leg_class(
            state=_leg_state(legs.get("entry")),
            missing_reason=_leg_missing_reason(legs.get("entry")),
        )
        reverse_evidence = legs.get("reverse")
        reverse_leg = (
            None
            if reverse_evidence is None
            else leg_class(
                state=_leg_state(reverse_evidence),
                missing_reason=_leg_missing_reason(reverse_evidence),
            )
        )
        outcomes[notional] = classify_execution_outcome(entry_leg, reverse_leg)
    return outcomes


def _leg_state(leg: object) -> str | None:
    if isinstance(leg, Mapping):
        raw = leg.get("state")
        return str(raw) if raw is not None else None
    return None


def _leg_missing_reason(leg: object) -> str | None:
    if isinstance(leg, Mapping):
        raw = leg.get("missing_reason")
        return str(raw) if raw is not None else None
    return None


__all__ = [
    "M1_CAPABILITY_ID",
    "M1ExecutionRealityError",
    "M1_NOTIONALS",
    "M1_OUTCOMES",
    "M1_SCHEMA_VERSION",
    "NOTIONAL_10_USD",
    "NOTIONAL_100_USD",
    "NOTIONAL_ATOMIC",
    "NOTIONAL_ENTRY_BUNDLE",
    "NOTIONAL_ENTRY_PRIMITIVE",
    "NOTIONAL_REVERSE_BUNDLE",
    "NOTIONAL_REVERSE_PRIMITIVE",
    "OUTCOME_ENTRY_ONLY",
    "OUTCOME_NO_ENTRY",
    "OUTCOME_TWO_WAY",
    "OUTCOME_UNKNOWN",
    "classify_execution_outcome",
    "classify_member_outcomes",
    "cross_notional_transition",
    "cross_notional_transition_counts",
    "friction_summary",
    "leg_class",
    "normalized_entry_size_linearity",
    "notional_outcome_counts",
    "quote_implied_roundtrip_friction",
    "verify_denominatorInvariant",
]
