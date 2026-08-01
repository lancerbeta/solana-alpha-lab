"""Deterministic TASK-21 information-sufficiency rebase checks."""

from __future__ import annotations

from typing import Any


JsonObject = dict[str, Any]


class Task21InformationSufficiencyError(RuntimeError):
    """The rebase contract is internally inconsistent or expands authority."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Task21InformationSufficiencyError(message)


def _all_zero_or_false(values: JsonObject, ignored: set[str]) -> bool:
    for key, value in values.items():
        if key in ignored:
            continue
        if isinstance(value, bool):
            if value:
                return False
        elif value != 0:
            return False
    return True


def evaluate_information_sufficiency_rebase(plan: JsonObject) -> JsonObject:
    """Validate the bounded rebase and return its decision-bearing arithmetic.

    The function consumes only operational coverage and budget metadata. It does
    not read quote outcomes, cost curves, token ranks, or hypothesis verdicts.
    """

    _require(plan.get("task_id") == "TASK-21", "task_id_drift")
    _require(
        plan.get("atom_id") == "T21-A6S_INFORMATION_SUFFICIENCY_REBASE_V1",
        "atom_id_drift",
    )
    _require(
        plan.get("status") == "FROZEN_LOCAL_REBASE_NO_EXTERNAL_ACTION",
        "status_drift",
    )

    history = plan["protected_history"]
    _require(not history["historical_artifacts_rewritten"], "history_rewrite")
    _require(not history["sealed_outcomes_read"], "outcome_unsealed")
    _require(
        history["hypothesis_definition_changed"] is False,
        "hypothesis_definition_changed",
    )
    _require(
        history["primary_estimand_changed"] is False,
        "primary_estimand_changed",
    )

    current = plan["current_evidence"]
    base_panels = sum(int(value) for value in current["base_panels_by_horizon"].values())
    _require(base_panels == int(current["base_panels_exact"]), "base_panel_count_drift")
    _require(current["base_panels_by_horizon"] == {"H0": 3, "H1": 3, "H6": 0}, "base_horizon_drift")
    _require(current["h6_gap_retained"], "h6_gap_erased")
    _require(current["supplemental_panels_exact"] == 1, "supplemental_panel_drift")
    _require(
        not current["supplemental_panels_count_toward_complete_member"],
        "supplemental_sufficiency_inflation",
    )
    _require(current["complete_base_members_exact"] == 0, "complete_member_drift")

    budget = plan["budget"]
    caps = budget["whole_task_caps"]
    used = budget["used_before_rebase"]
    remaining = budget["remaining_before_rebase"]
    proposed = budget["proposed_final_extension_max"]
    projected = budget["projected_whole_task_max"]

    for key in ("external_requests", "source_requests", "quote_requests"):
        _require(
            int(remaining[key]) == int(caps[key]) - int(used[key]),
            f"remaining_{key}_drift",
        )
        _require(
            int(projected[key]) == int(used[key]) + int(proposed[key]),
            f"projected_{key}_drift",
        )
        _require(int(projected[key]) <= int(caps[key]), f"{key}_cap_breach")

    byte_budget = budget["bytes_and_storage"]
    for prefix in ("response", "stored", "dataset"):
        cap = int(byte_budget[f"{prefix}_bytes_cap"])
        used_bytes = int(byte_budget[f"{prefix}_bytes_used"])
        remaining_bytes = int(byte_budget[f"{prefix}_bytes_remaining"])
        _require(remaining_bytes == cap - used_bytes, f"{prefix}_byte_arithmetic_drift")
        _require(remaining_bytes > 0, f"{prefix}_byte_cap_exhausted")
    _require(
        int(byte_budget["free_disk_bytes_observed"])
        >= int(byte_budget["min_free_space_bytes_after_write"]),
        "free_disk_floor_not_met",
    )
    _require(
        byte_budget["future_write_behavior"] == "FAIL_CLOSED_AT_EXACT_RUNTIME_CAP",
        "future_byte_cap_not_fail_closed",
    )

    cohort = plan["final_extension"]
    new_member_cap = sum(int(batch["member_cap"]) for batch in cohort["batches"])
    _require(new_member_cap == int(cohort["new_member_cap"]), "batch_member_cap_drift")
    _require(
        int(cohort["evaluated_candidates_used"]) + new_member_cap
        == int(cohort["evaluated_candidates_whole_task_cap"]),
        "candidate_cap_arithmetic_drift",
    )
    _require(len(cohort["batches"]) == 2, "source_batch_count_drift")
    _require(
        all(int(batch["source_calls_max"]) == 2 for batch in cohort["batches"]),
        "source_batch_call_cap_drift",
    )
    _require(
        sum(int(batch["source_calls_max"]) for batch in cohort["batches"])
        == int(proposed["source_requests"]),
        "source_call_arithmetic_drift",
    )

    panel = cohort["panel_schedule"]
    expected_quote_requests = (
        new_member_cap
        * int(panel["panels_per_member"])
        * int(panel["provider_calls_per_panel_max"])
    )
    _require(expected_quote_requests == int(proposed["quote_requests"]), "quote_call_arithmetic_drift")
    _require(int(panel["minimum_separation_seconds"]) == 1801, "panel_separation_drift")
    _require(int(panel["member_total_span_seconds_max"]) == 86400, "panel_span_drift")
    _require(int(panel["retries"]) == 0, "retry_drift")
    _require(not panel["narrow_expiry_window_used"], "narrow_window_reintroduced")
    _require(not cohort["minimum_calendar_wait_required"], "calendar_wait_reintroduced")
    _require(not cohort["scheduler_or_background_process"], "scheduler_authority_leak")

    sufficiency = plan["information_sufficiency"]
    _require(sufficiency["minimum_complete_members"] == 5, "member_minimum_drift")
    _require(sufficiency["minimum_complete_panels"] == 15, "panel_minimum_drift")
    _require(sufficiency["minimum_complete_quote_pairs"] == 60, "quote_pair_minimum_drift")
    _require(sufficiency["minimum_independent_nomination_batches"] == 3, "batch_minimum_drift")
    _require(sufficiency["minimum_calendar_days"] is None, "calendar_day_gate_reintroduced")
    _require(sufficiency["minimum_calendar_weeks"] is None, "calendar_week_gate_reintroduced")
    _require(
        sufficiency["market_state_handling"]
        == "REPORT_OBSERVED_STATES_WITHOUT_FORCING_OR_GENERALIZING",
        "market_state_claim_drift",
    )
    _require(
        sufficiency["success_disposition"]
        == "DATASET_READY_FOR_NARROW_CONDITIONAL_ANALYSIS",
        "success_disposition_drift",
    )

    stop = plan["stop_rules"]
    _require(stop["automatic_extension_allowed"] is False, "automatic_extension_leak")
    _require(stop["calendar_elapsed_alone_is_evidence"] is False, "calendar_evidence_drift")
    _require(stop["cap_exhaustion_disposition"] == "STOPPED_SAFELY_OR_REDESIGN_DATA", "cap_stop_drift")

    authority = plan["authority"]
    _require(authority["class"] == "LOCAL_WRITE_ONLY", "authority_class_drift")
    _require(
        _all_zero_or_false(authority, {"class", "source", "gate_phrase", "managed_files"}),
        "authority_leak",
    )
    boundary = plan["next_boundary"]
    _require(boundary["status"] == "NOT_AUTHORIZED", "next_boundary_authorized")
    _require(not boundary["external_actions_authorized"], "external_authority_leak")
    _require(not boundary["task22_authorized"], "task22_authority_leak")

    return {
        "status": "PASS",
        "verdict": "BOUNDED_EVENT_TRIGGERED_EXTENSION_JUSTIFIED",
        "dataset_ready": False,
        "task22_eligible": False,
        "current_complete_base_members": int(current["complete_base_members_exact"]),
        "new_member_cap": new_member_cap,
        "new_base_panels_max": new_member_cap * int(panel["panels_per_member"]),
        "new_quote_requests_max": expected_quote_requests,
        "new_source_requests_max": int(proposed["source_requests"]),
        "projected_external_requests_max": int(projected["external_requests"]),
        "external_request_headroom": int(caps["external_requests"]) - int(projected["external_requests"]),
        "response_bytes_remaining": int(byte_budget["response_bytes_remaining"]),
        "stored_bytes_remaining": int(byte_budget["stored_bytes_remaining"]),
        "dataset_bytes_remaining": int(byte_budget["dataset_bytes_remaining"]),
        "calendar_wait_required": False,
        "sealed_outcomes_read": False,
    }
