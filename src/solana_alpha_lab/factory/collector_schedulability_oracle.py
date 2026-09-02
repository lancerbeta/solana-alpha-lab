"""Deterministic ObservationSchedule capacity / schedulability oracle (zero-network).

``recommended_inclusion_probability`` is derived from the **applied** member cap
``min(requested_max_members_per_utc_day, max_supported_members_per_day)``, not from
``max_supported_members_per_day`` alone. A prior bug used the capacity ceiling (e.g.
456/2000 → 0.228) while the applied cap remained 114 (→ 0.057).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from solana_alpha_lab.factory.observation_primitive_registry import (
    load_observation_primitive_registry,
)

from solana_alpha_lab.factory.observation_provider_pacing import (
    DEFAULT_TICK_WALL_BUDGET_SECONDS,
    TIMER_CADENCE_SECONDS as PACING_TIMER_CADENCE_SECONDS,
    usable_due_calls_per_tick,
)

TIMER_CADENCE_SECONDS = PACING_TIMER_CADENCE_SECONDS
MATERIAL_HEADROOM_PCT = 25
FREE_TIER_MIN_PACE_SECONDS = 3
FREE_TIER_PACE_BOUND_CALLS_PER_DAY = 86400 // FREE_TIER_MIN_PACE_SECONDS
ALLOWED_X_POINTS = frozenset({300, 600, 900})
PREFERRED_X_SECONDS = 300
DEFAULT_LIFECYCLE_Y_SECONDS = (900, 1800, 3600, 7200, 14400, 43200, 86400)
SEARCH_BUNDLE = "BUNDLE-JUPITER-TOKEN-SEARCH-SNAPSHOT-001"
STOP_FREE_TIER_CAPACITY_NOT_PROVEN = "STOP_FREE_TIER_CAPACITY_NOT_PROVEN"


@dataclass(frozen=True, slots=True)
class SchedulabilityResult:
    terminal: str
    max_supported_members_per_day: int
    recommended_inclusion_probability: str
    recommended_max_members_per_utc_day: int
    predicted_provider_calls_per_day: int
    predicted_provider_calls_lifetime_21d: int
    pace_bound_calls_per_day: int
    headroom_pct: int
    source_poll_gap_risk: str
    p95_due_lateness_seconds: int
    p99_due_lateness_seconds: int
    selected_x_due_offset_seconds: int
    x_selection_basis: str
    timer_cadence_seconds: int
    max_claims_per_tick: int
    min_provider_pace_seconds: int
    stress_cases: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def recommended_inclusion_probability(
    *,
    recommended_members: int,
    candidate_launches_per_utc_day: int,
) -> str:
    """Bernoulli p for the applied member cap, not the capacity ceiling."""

    if candidate_launches_per_utc_day <= 0:
        return "0"
    if recommended_members >= candidate_launches_per_utc_day:
        return "1.0"
    value = recommended_members / candidate_launches_per_utc_day
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def classify_discovery_coverage(
    *,
    period_seconds: int,
    empirical_overlap_seconds: int | None,
    provider_contract_proven: bool = False,
    gap_confirmed: bool = False,
) -> str:
    """Outcome-blind discovery coverage class for commissioning diagnostics."""

    if gap_confirmed:
        return "GAP_CONFIRMED"
    if provider_contract_proven:
        return "PROVIDER_CONTRACT_PROVEN"
    if empirical_overlap_seconds is None:
        return "GAP_SUSPECTED"
    if empirical_overlap_seconds >= period_seconds:
        return "EMPIRICAL_OVERLAP_ONLY"
    if empirical_overlap_seconds <= 0:
        return "GAP_CONFIRMED"
    return "GAP_SUSPECTED"


def select_x_point(
    *,
    timing_evidence_seconds: Sequence[int] | None = None,
) -> tuple[int, str]:
    """Prefer X300; later X only from {300,600,900} via outcome-blind timing."""

    if not timing_evidence_seconds:
        return PREFERRED_X_SECONDS, "INSUFFICIENT_TIMING_EVIDENCE_KEEP_X300"
    observed = [int(item) for item in timing_evidence_seconds if int(item) > 0]
    if not observed:
        return PREFERRED_X_SECONDS, "INSUFFICIENT_TIMING_EVIDENCE_KEEP_X300"
    ordered = sorted(observed)
    idx = max(0, math.ceil(0.95 * len(ordered)) - 1)
    lag = ordered[idx]
    for candidate in sorted(ALLOWED_X_POINTS):
        if candidate >= lag:
            basis = (
                "PREFERRED_X300"
                if candidate == PREFERRED_X_SECONDS
                else "OUTCOME_BLIND_TIMING_P95"
            )
            return candidate, basis
    return max(ALLOWED_X_POINTS), "OUTCOME_BLIND_TIMING_P95_CLAMPED"


def _search_batch_size(root) -> int:
    registry = load_observation_primitive_registry(root)
    primitive = registry.require_primitive("PRIM-JUPITER-TOKENS-V2-SEARCH-001")
    return max(1, int(primitive["max_batch_size"]))


def _calls_for_members(
    *,
    members: int,
    point_count: int,
    batch_size: int,
    worst_case_unbatched: bool,
) -> int:
    if members <= 0:
        return 0
    if worst_case_unbatched:
        return members * point_count
    batches_per_point = math.ceil(members / batch_size)
    return batches_per_point * point_count


def _simulate_due_lateness(
    *,
    members: int,
    point_count: int,
    batch_size: int,
    pace_seconds: int,
    timer_cadence_seconds: int,
    max_claims: int,
    poll_period_seconds: int,
    worst_case_unbatched: bool,
    tick_wall_budget_seconds: int = DEFAULT_TICK_WALL_BUDGET_SECONDS,
) -> tuple[int, int, str]:
    """Synthetic burst: members become due for one lifecycle point in the same minute."""

    del point_count
    if members <= 0:
        return 0, 0, "NONE"
    if worst_case_unbatched:
        remaining_calls = members
    else:
        remaining_calls = math.ceil(members / batch_size)
    usable_per_tick = usable_due_calls_per_tick(
        pace_seconds=pace_seconds,
        poll_period_seconds=poll_period_seconds,
        timer_cadence_seconds=timer_cadence_seconds,
        tick_wall_budget_seconds=tick_wall_budget_seconds,
        max_claims_per_tick=max_claims,
    )
    if usable_per_tick <= 0:
        return 86_400, 86_400, "HIGH"
    ticks_needed = math.ceil(remaining_calls / usable_per_tick)
    lateness = max(0, (ticks_needed - 1) * timer_cadence_seconds)
    p95 = lateness
    p99 = lateness + timer_cadence_seconds if ticks_needed > 1 else lateness
    gap_risk = "LOW"
    if ticks_needed > 2:
        gap_risk = "MEDIUM"
    if ticks_needed > 5:
        gap_risk = "HIGH"
    return p95, p99, gap_risk


def evaluate_schedulability(
    *,
    root,
    schedule: Mapping[str, Any],
    max_claims_per_tick: int = 60,
    timer_cadence_seconds: int = TIMER_CADENCE_SECONDS,
    required_headroom_pct: int = MATERIAL_HEADROOM_PCT,
    candidate_launches_per_utc_day: int = 2000,
    timing_evidence_seconds: Sequence[int] | None = None,
) -> SchedulabilityResult:
    """Prove Free-tier envelope against actual scheduler knobs (no network)."""

    x_seconds, x_basis = select_x_point(timing_evidence_seconds=timing_evidence_seconds)
    point_count = 1 + len(list(schedule.get("y_points") or ()))
    members = int(schedule["sampling"]["max_members_per_utc_day"])
    pace = int(schedule["budgets"]["min_provider_pace_seconds"])
    period = int(schedule["source_poll"]["period_seconds"])
    batch_size = _search_batch_size(root)
    pace_bound = 86400 // max(FREE_TIER_MIN_PACE_SECONDS, pace)
    usable_bound = int(pace_bound * (100 - required_headroom_pct) / 100)

    discovery_per_day = (86400 + period - 1) // period
    predicted_day = discovery_per_day + _calls_for_members(
        members=members,
        point_count=point_count,
        batch_size=batch_size,
        worst_case_unbatched=True,
    )
    admission_days = 21
    predicted_life = discovery_per_day * admission_days + (
        _calls_for_members(
            members=members,
            point_count=point_count,
            batch_size=batch_size,
            worst_case_unbatched=True,
        )
        * admission_days
    )

    p95, p99, gap_risk = _simulate_due_lateness(
        members=members,
        point_count=point_count,
        batch_size=batch_size,
        pace_seconds=pace,
        timer_cadence_seconds=timer_cadence_seconds,
        max_claims=max_claims_per_tick,
        poll_period_seconds=period,
        worst_case_unbatched=True,
    )

    max_members = 0
    for trial in range(0, max(members * 4, 1) + 1):
        trial_calls = discovery_per_day + _calls_for_members(
            members=trial,
            point_count=point_count,
            batch_size=batch_size,
            worst_case_unbatched=True,
        )
        if trial_calls <= usable_bound:
            max_members = trial
        else:
            break
    if max_members <= 0:
        return SchedulabilityResult(
            terminal=STOP_FREE_TIER_CAPACITY_NOT_PROVEN,
            max_supported_members_per_day=0,
            recommended_inclusion_probability="0",
            recommended_max_members_per_utc_day=0,
            predicted_provider_calls_per_day=predicted_day,
            predicted_provider_calls_lifetime_21d=predicted_life,
            pace_bound_calls_per_day=pace_bound,
            headroom_pct=0,
            source_poll_gap_risk="HIGH",
            p95_due_lateness_seconds=p95,
            p99_due_lateness_seconds=p99,
            selected_x_due_offset_seconds=x_seconds,
            x_selection_basis=x_basis,
            timer_cadence_seconds=timer_cadence_seconds,
            max_claims_per_tick=max_claims_per_tick,
            min_provider_pace_seconds=pace,
            stress_cases=(
                "SPARSE_NORMAL",
                "BURSTY_LAUNCH_MINUTE",
                "DISTINCT_DUE_TIMESTAMPS",
                "WORST_CASE_UNBATCHED_SEARCH",
                "SOURCE_POLL_PLUS_DUE",
                "RESTART_RECOVERY",
                "PROVIDER_PACE_WAIT",
                "LONG_TICK_NEAR_TIMER",
            ),
            reason_codes=("FREE_TIER_PACE_BOUND_EXCEEDED",),
        )

    capacity_ceiling_members = max_members
    headroom = int(100 * (1 - predicted_day / max(1, pace_bound)))
    reasons: list[str] = []
    terminal = "SCHEDULABLE_WITH_HEADROOM"
    allowed_x_lateness = int(schedule["x_point"]["allowed_lateness_seconds"])
    recommended_members_cap = max_members
    if p95 > allowed_x_lateness:
        # Reduce recommended members until burst lateness fits the scientific window.
        fitted = max_members
        while fitted > 0:
            trial_p95, _, _ = _simulate_due_lateness(
                members=fitted,
                point_count=point_count,
                batch_size=batch_size,
                pace_seconds=pace,
                timer_cadence_seconds=timer_cadence_seconds,
                max_claims=max_claims_per_tick,
                poll_period_seconds=period,
                worst_case_unbatched=True,
            )
            if trial_p95 <= allowed_x_lateness:
                break
            fitted -= 1
        if fitted <= 0:
            terminal = STOP_FREE_TIER_CAPACITY_NOT_PROVEN
            reasons.append("BURST_LATENESS_EXCEEDS_ALLOWED_WINDOW")
            recommended_members_cap = 0
        else:
            recommended_members_cap = fitted
            reasons.append("MEMBERS_CAPPED_FOR_ALLOWED_LATENESS")
            # Recompute predicted load for the fitted envelope.
            predicted_day = discovery_per_day + _calls_for_members(
                members=min(members, recommended_members_cap),
                point_count=point_count,
                batch_size=batch_size,
                worst_case_unbatched=True,
            )
            predicted_life = predicted_day * admission_days
            headroom = int(100 * (1 - predicted_day / max(1, pace_bound)))
            p95, p99, gap_risk = _simulate_due_lateness(
                members=min(members, recommended_members_cap),
                point_count=point_count,
                batch_size=batch_size,
                pace_seconds=pace,
                timer_cadence_seconds=timer_cadence_seconds,
                max_claims=max_claims_per_tick,
                poll_period_seconds=period,
                worst_case_unbatched=True,
            )
    if predicted_day > usable_bound or headroom < required_headroom_pct:
        terminal = STOP_FREE_TIER_CAPACITY_NOT_PROVEN
        reasons.append("MATERIAL_HEADROOM_NOT_MET")
    if int(schedule["x_point"]["due_offset_seconds"]) != x_seconds:
        reasons.append("SCHEDULE_X_DIFFERS_FROM_ORACLE_SELECTION")

    recommended_members = min(members, recommended_members_cap)
    inclusion = recommended_inclusion_probability(
        recommended_members=recommended_members,
        candidate_launches_per_utc_day=candidate_launches_per_utc_day,
    )

    return SchedulabilityResult(
        terminal=terminal,
        max_supported_members_per_day=capacity_ceiling_members,
        recommended_inclusion_probability=inclusion,
        recommended_max_members_per_utc_day=recommended_members,
        predicted_provider_calls_per_day=predicted_day,
        predicted_provider_calls_lifetime_21d=predicted_life,
        pace_bound_calls_per_day=pace_bound,
        headroom_pct=max(0, headroom),
        source_poll_gap_risk=gap_risk,
        p95_due_lateness_seconds=p95,
        p99_due_lateness_seconds=p99,
        selected_x_due_offset_seconds=x_seconds,
        x_selection_basis=x_basis,
        timer_cadence_seconds=timer_cadence_seconds,
        max_claims_per_tick=max_claims_per_tick,
        min_provider_pace_seconds=pace,
        stress_cases=(
            "SPARSE_NORMAL",
            "BURSTY_LAUNCH_MINUTE",
            "DISTINCT_DUE_TIMESTAMPS",
            "WORST_CASE_UNBATCHED_SEARCH",
            "SOURCE_POLL_PLUS_DUE",
            "PROVIDER_PACE_WAIT",
            "LONG_TICK_NEAR_TIMER",
        ),
        reason_codes=tuple(reasons),
    )


__all__ = [
    "ALLOWED_X_POINTS",
    "DEFAULT_LIFECYCLE_Y_SECONDS",
    "FREE_TIER_MIN_PACE_SECONDS",
    "FREE_TIER_PACE_BOUND_CALLS_PER_DAY",
    "MATERIAL_HEADROOM_PCT",
    "PREFERRED_X_SECONDS",
    "SEARCH_BUNDLE",
    "STOP_FREE_TIER_CAPACITY_NOT_PROVEN",
    "SchedulabilityResult",
    "TIMER_CADENCE_SECONDS",
    "classify_discovery_coverage",
    "evaluate_schedulability",
    "recommended_inclusion_probability",
    "select_x_point",
]
