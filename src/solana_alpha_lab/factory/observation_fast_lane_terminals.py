"""Shared observation-specific Fast Lane terminal contract.

Forge (HFIC) and the generic no-Git runner must consume this module. Do not
re-encode the four observation terminals as independent string checks.
"""

from __future__ import annotations

from dataclasses import dataclass


PANEL_REUSE_READY = "PANEL_REUSE_READY"
ATTACHED_TO_ACTIVE_SCHEDULE = "ATTACHED_TO_ACTIVE_SCHEDULE"
SCHEDULE_ACTIVATION_REQUIRED = "SCHEDULE_ACTIVATION_REQUIRED"
NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED = "NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED"

OBSERVATION_FAST_LANE_TERMINALS = frozenset(
    {
        PANEL_REUSE_READY,
        ATTACHED_TO_ACTIVE_SCHEDULE,
        SCHEDULE_ACTIVATION_REQUIRED,
        NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED,
    }
)

OBSERVATION_CHANGE_LANE_TERMINALS = frozenset(
    {
        "CHANGE_LANE_PRIMITIVE_GAP",
        "CHANGE_LANE_ESTIMATOR_GAP",
        "CHANGE_LANE_SAFETY_CONTRACT_GAP",
    }
)

OBSERVATION_DENY_TERMINALS = frozenset(
    {
        "DENY_OUTCOME_LEAKAGE",
        "DENY_RETROACTIVE_MUTATION",
        "DENY_UNSAFE_RUNTIME_CODE",
        "BLOCKED_BUDGET",
        "BLOCKED_AUTHORITY",
    }
)


@dataclass(frozen=True, slots=True)
class ObservationFastLaneRouting:
    """One observation compiler terminal mapped for HFIC and no-Git execution."""

    classifier_terminal: str
    hfic_terminal: str
    execution_status: str
    scientific_terminal: str
    persist_completed_run: bool
    preserve_next_action: bool


_ROUTING: dict[str, ObservationFastLaneRouting] = {
    PANEL_REUSE_READY: ObservationFastLaneRouting(
        classifier_terminal=PANEL_REUSE_READY,
        hfic_terminal="PASS_FAST_LANE_READY",
        execution_status="COMPLETE",
        scientific_terminal="INCONCLUSIVE",
        persist_completed_run=True,
        preserve_next_action=True,
    ),
    ATTACHED_TO_ACTIVE_SCHEDULE: ObservationFastLaneRouting(
        classifier_terminal=ATTACHED_TO_ACTIVE_SCHEDULE,
        hfic_terminal="PASS_FAST_LANE_READY",
        execution_status="BLOCKED_DATA",
        scientific_terminal="INVALID",
        persist_completed_run=False,
        preserve_next_action=True,
    ),
    SCHEDULE_ACTIVATION_REQUIRED: ObservationFastLaneRouting(
        classifier_terminal=SCHEDULE_ACTIVATION_REQUIRED,
        hfic_terminal="OWNER_DECISION_REQUIRED",
        execution_status="BLOCKED_AUTHORITY",
        scientific_terminal="INVALID",
        persist_completed_run=False,
        preserve_next_action=True,
    ),
    NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED: ObservationFastLaneRouting(
        classifier_terminal=NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED,
        hfic_terminal="OWNER_DECISION_REQUIRED",
        execution_status="BLOCKED_AUTHORITY",
        scientific_terminal="INVALID",
        persist_completed_run=False,
        preserve_next_action=True,
    ),
}


def observation_fast_lane_routing(terminal: str) -> ObservationFastLaneRouting | None:
    """Return the shared routing row, or None when the terminal is not observation-specific."""

    return _ROUTING.get(terminal)


def hfic_terminal_for_classifier(terminal: str) -> str | None:
    """Map a classifier terminal that originated in ObservationSchedule compile."""

    routing = observation_fast_lane_routing(terminal)
    if routing is not None:
        return routing.hfic_terminal
    if terminal in OBSERVATION_CHANGE_LANE_TERMINALS:
        return "PASS_CHANGE_LANE_REQUIRED"
    if terminal in OBSERVATION_DENY_TERMINALS:
        return "KILL_UNBOUND_EVIDENCE"
    return None


__all__ = [
    "ATTACHED_TO_ACTIVE_SCHEDULE",
    "NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED",
    "OBSERVATION_CHANGE_LANE_TERMINALS",
    "OBSERVATION_DENY_TERMINALS",
    "OBSERVATION_FAST_LANE_TERMINALS",
    "ObservationFastLaneRouting",
    "PANEL_REUSE_READY",
    "SCHEDULE_ACTIVATION_REQUIRED",
    "hfic_terminal_for_classifier",
    "observation_fast_lane_routing",
]
