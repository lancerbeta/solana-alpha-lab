"""Pure offline runtime preparation for the TASK-21 final cohort.

The module turns future nomination observations into deterministic admission
and foreground-panel plans.  It intentionally has no transport, filesystem
writer, scheduler, credential, or trading capability.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeAlias

from solana_alpha_lab.task21_forward_collector import canonical_json_bytes, sha256_file


JsonObject: TypeAlias = dict[str, Any]

TASK_ID = "TASK-21"
ATOM_ID = "T21-A6S_EVENT_TRIGGERED_FINAL_COHORT_RUNTIME_PREP_V1"
SCHEMA_VERSION = "1.0"
PANEL_ORDER = ("P0", "P1", "P2")
BASE58_ALPHABET = frozenset(
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)
FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "alpha",
        "costbps",
        "fill",
        "hypothesisverdict",
        "inamount",
        "outamount",
        "pnl",
        "price",
        "priceimpactpct",
        "profit",
        "quote",
        "rank",
        "realizedvwap",
        "return",
        "roi",
        "route",
        "routeplan",
        "score",
        "sharpe",
        "swap",
        "terminal",
        "terminalstate",
    }
)


class Task21FinalCohortError(RuntimeError):
    """The final-cohort runtime contract was violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Task21FinalCohortError(message)


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _reject_outcome_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _require(isinstance(key, str), "input_key_must_be_text")
            normalized = _normalized_key(key)
            if any(
                normalized == forbidden or normalized.startswith(forbidden)
                for forbidden in FORBIDDEN_OUTCOME_KEYS
            ):
                raise Task21FinalCohortError(
                    f"outcome_field_forbidden:{key}"
                )
            _reject_outcome_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_outcome_fields(item)


def _utc(value: object, field: str) -> datetime:
    _require(isinstance(value, str), f"{field}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21FinalCohortError(f"{field}_invalid") from exc
    _require(
        parsed.tzinfo is not None and parsed.utcoffset() is not None,
        f"{field}_must_be_timezone_aware",
    )
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    _require(
        value.tzinfo is not None and value.utcoffset() is not None,
        "datetime_must_be_timezone_aware",
    )
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sha256_text(value: object, field: str) -> str:
    _require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        f"{field}_must_be_lowercase_sha256",
    )
    return value


def _valid_mint(value: object) -> bool:
    return (
        isinstance(value, str)
        and 32 <= len(value) <= 44
        and set(value) <= BASE58_ALPHABET
    )


def _member_id(
    *, policy_version: str, batch_id: str, nomination_event_id: str, mint: str
) -> str:
    payload = {
        "batch_id": batch_id,
        "mint": mint,
        "nomination_event_id": nomination_event_id,
        "policy_version": policy_version,
    }
    suffix = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:20]
    return f"T21-WATCH-{suffix}"


def validate_runtime_config(config: Mapping[str, Any]) -> None:
    """Validate the frozen offline runtime plan without reading outcomes."""

    _require(config.get("task_id") == TASK_ID, "task_id_drift")
    _require(config.get("atom_id") == ATOM_ID, "atom_id_drift")
    _require(
        config.get("status") == "OFFLINE_RUNTIME_PREP_ONLY",
        "runtime_status_drift",
    )
    _require(config.get("transport") is None, "transport_capability_forbidden")
    _require(config.get("scheduler") is None, "scheduler_capability_forbidden")

    cohort = config["cohort"]
    batches = cohort["batches"]
    _require(
        [(item["batch_id"], item["member_cap"]) for item in batches]
        == [("T21-R2", 3), ("T21-R3", 2)],
        "batch_plan_drift",
    )
    _require(cohort["evaluated_candidates_used"] == 3, "candidate_used_drift")
    _require(cohort["evaluated_candidates_cap"] == 8, "candidate_cap_drift")
    _require(cohort["new_member_cap"] == 5, "member_cap_drift")
    _require(sum(item["member_cap"] for item in batches) == 5, "member_sum_drift")

    panels = config["panels"]
    _require(tuple(panels["order"]) == PANEL_ORDER, "panel_order_drift")
    _require(panels["minimum_separation_seconds"] == 1801, "separation_drift")
    _require(panels["member_total_span_seconds_max"] == 86400, "span_drift")
    _require(panels["provider_calls_per_panel_max"] == 8, "panel_call_cap_drift")
    _require(panels["quote_pairs_per_panel"] == 4, "quote_pair_drift")
    _require(panels["retries"] == 0, "retry_drift")
    _require(panels["concurrency"] == 1, "concurrency_drift")
    _require(not panels["narrow_expiry_window_used"], "narrow_window_reintroduced")

    budget = config["budget"]
    caps = budget["caps"]
    used = budget["used"]
    for key in ("external_requests", "source_requests", "quote_requests"):
        _require(0 <= used[key] <= caps[key], f"{key}_used_invalid")
    _require(
        used
        == {"external_requests": 60, "source_requests": 4, "quote_requests": 56},
        "starting_budget_drift",
    )
    _require(
        caps
        == {"external_requests": 192, "source_requests": 8, "quote_requests": 184},
        "budget_caps_drift",
    )
    _require(budget["headroom_not_authority"], "headroom_authority_leak")

    authority = config["authority"]
    _require(authority["class"] == "LOCAL_WRITE_ONLY", "authority_class_drift")
    for key, value in authority.items():
        if key in {"class", "source", "gate_phrase"}:
            continue
        if isinstance(value, bool):
            _require(not value, f"authority_leak:{key}")
        else:
            _require(value == 0, f"authority_leak:{key}")


def validate_protected_inputs(
    *, repo_root: Path, config: Mapping[str, Any]
) -> None:
    """Fail closed if any decision-bearing input changed before execution."""

    validate_runtime_config(config)
    root = repo_root.resolve()
    protected = config.get("protected_inputs")
    _require(isinstance(protected, list) and protected, "protected_inputs_missing")
    seen_roles: set[str] = set()
    for item in protected:
        _require(isinstance(item, Mapping), "protected_input_invalid")
        role = item.get("role")
        relative_text = item.get("path")
        _require(isinstance(role, str) and role, "protected_input_role_invalid")
        _require(role not in seen_roles, "protected_input_role_duplicate")
        _require(
            isinstance(relative_text, str) and relative_text,
            "protected_input_path_invalid",
        )
        relative = Path(relative_text)
        _require(not relative.is_absolute(), "protected_input_path_must_be_relative")
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise Task21FinalCohortError(
                "protected_input_outside_repository"
            ) from exc
        _require(candidate.is_file(), f"protected_input_missing:{role}")
        expected = _sha256_text(item.get("sha256"), "protected_input_sha256")
        _require(
            sha256_file(candidate) == expected,
            f"protected_input_hash_drift:{role}",
        )
        seen_roles.add(role)


def initial_runtime_state(config: Mapping[str, Any]) -> JsonObject:
    """Return a mutable copy of the exact accepted pre-extension state."""

    validate_runtime_config(config)
    initial = config["initial_state"]
    accepted = initial["accepted_source_observations"]
    _require(len(accepted) == 1, "initial_source_observation_count_drift")
    _sha256_text(accepted[0]["source_content_sha256"], "initial_source_hash")
    _utc(accepted[0]["observed_at"], "initial_observed_at")
    _require(len(initial["seen_mints"]) == 3, "initial_mint_count_drift")
    _require(all(_valid_mint(mint) for mint in initial["seen_mints"]), "initial_mint_invalid")
    return {
        "accepted_source_observations": deepcopy(accepted),
        "retained_source_observations": [],
        "seen_mints": list(initial["seen_mints"]),
        "evaluated_candidates_used": config["cohort"]["evaluated_candidates_used"],
        "admitted_members": [],
        "budget": {
            "used": deepcopy(config["budget"]["used"]),
            "reserved": {
                "external_requests": 0,
                "source_requests": 0,
                "quote_requests": 0,
            },
        },
    }


def _budget_total(state: Mapping[str, Any], key: str) -> int:
    return int(state["budget"]["used"][key]) + int(
        state["budget"]["reserved"][key]
    )


def _consume_source_calls(
    *, config: Mapping[str, Any], state: JsonObject, source_calls: int
) -> None:
    _require(isinstance(source_calls, int) and source_calls >= 1, "source_calls_invalid")
    caps = config["budget"]["caps"]
    _require(
        _budget_total(state, "source_requests") + source_calls
        <= caps["source_requests"],
        "source_request_cap_exceeded",
    )
    _require(
        _budget_total(state, "external_requests") + source_calls
        <= caps["external_requests"],
        "external_request_cap_exceeded_by_source",
    )
    state["budget"]["used"]["source_requests"] += source_calls
    state["budget"]["used"]["external_requests"] += source_calls


def _retain_and_stop(
    *, state: JsonObject, observation: Mapping[str, Any], reason: str
) -> JsonObject:
    state["retained_source_observations"].append(
        {
            "batch_id": observation.get("batch_id"),
            "source_observation_id": observation.get("source_observation_id"),
            "source_content_sha256": observation.get("source_content_sha256"),
            "reason": reason,
        }
    )
    return {
        "status": "STOPPED_NO_ADMISSION",
        "reason": reason,
        "candidate_states": [],
        "members": [],
        "state": state,
        "external_actions_authorized": False,
    }


def evaluate_nomination_observation(
    *,
    config: Mapping[str, Any],
    state: Mapping[str, Any],
    observation: Mapping[str, Any],
    admitted_at: str,
) -> JsonObject:
    """Evaluate one already-observed source batch and reserve future panels.

    `source_calls` records a physical call count supplied by the future caller;
    this pure function performs no call itself.
    """

    validate_runtime_config(config)
    working = deepcopy(dict(state))
    _reject_outcome_fields(observation)
    admitted_time = _utc(admitted_at, "admitted_at")

    accepted_batches = len(working["accepted_source_observations"]) - 1
    batches = config["cohort"]["batches"]
    _require(accepted_batches < len(batches), "final_cohort_already_closed")
    expected = batches[accepted_batches]
    _require(observation.get("batch_id") == expected["batch_id"], "unexpected_batch")
    source_calls = observation.get("source_calls")
    _require(
        isinstance(source_calls, int)
        and 1 <= source_calls <= expected["source_calls_max"],
        "source_call_count_outside_batch_cap",
    )
    _consume_source_calls(config=config, state=working, source_calls=source_calls)

    source_id = observation.get("source_observation_id")
    _require(isinstance(source_id, str) and source_id, "source_observation_id_invalid")
    source_hash = _sha256_text(
        observation.get("source_content_sha256"), "source_content_sha256"
    )
    observed_at = _utc(observation.get("observed_at"), "observed_at")
    accepted = working["accepted_source_observations"]
    if source_id in {item["source_observation_id"] for item in accepted}:
        return _retain_and_stop(
            state=working,
            observation=observation,
            reason="SOURCE_OBSERVATION_ID_NOT_NEW",
        )
    if source_hash in {item["source_content_sha256"] for item in accepted}:
        return _retain_and_stop(
            state=working,
            observation=observation,
            reason="SOURCE_CONTENT_NOT_NOVEL",
        )
    prior_observed_at = max(
        _utc(item["observed_at"], "prior_observed_at") for item in accepted
    )
    if observed_at <= prior_observed_at:
        return _retain_and_stop(
            state=working,
            observation=observation,
            reason="OBSERVED_AT_NOT_STRICTLY_AFTER_PRIOR_BATCH",
        )

    candidates = observation.get("candidates")
    _require(isinstance(candidates, list) and candidates, "candidates_missing")
    _require(len(candidates) <= expected["member_cap"], "batch_candidate_cap_exceeded")
    remaining_candidates = (
        config["cohort"]["evaluated_candidates_cap"]
        - working["evaluated_candidates_used"]
    )
    _require(len(candidates) <= remaining_candidates, "whole_task_candidate_cap_exceeded")

    ordered = sorted(
        candidates,
        key=lambda item: (
            _utc(item.get("first_reliable_available_at"), "first_reliable_available_at"),
            _utc(item.get("observed_at"), "candidate_observed_at"),
            item.get("nomination_event_id"),
            item.get("mint"),
        ),
    )
    _require(candidates == ordered, "candidate_sort_order_drift")

    candidate_states: list[JsonObject] = []
    admitted: list[JsonObject] = []
    local_seen = set(working["seen_mints"])
    for candidate in candidates:
        nomination_id = candidate.get("nomination_event_id")
        mint = candidate.get("mint")
        decimals = candidate.get("mint_decimals")
        inputs = candidate.get("exact_rule_input_values")
        _require(isinstance(nomination_id, str) and nomination_id, "nomination_id_invalid")
        _require(_valid_mint(mint), "candidate_mint_invalid")
        _require(
            isinstance(decimals, int)
            and not isinstance(decimals, bool)
            and 0 <= decimals <= 30,
            "mint_decimals_invalid",
        )
        _require(isinstance(inputs, Mapping), "exact_rule_inputs_missing")
        _require(
            inputs.get("prior_relevant_quote_outcome_exposure") is False,
            "prior_quote_outcome_exposure_forbidden",
        )
        _require(
            inputs.get("uses_task21_quote_route_or_price_outcome") is False,
            "quote_route_price_admission_forbidden",
        )
        eligible = candidate.get("eligible") is True
        if mint in local_seen:
            state_code = "EVALUATED_REJECTED_DUPLICATE_MINT"
        elif not eligible:
            state_code = "EVALUATED_REJECTED_POLICY_INELIGIBLE"
        else:
            member_id = _member_id(
                policy_version=config["cohort"]["policy_version"],
                batch_id=expected["batch_id"],
                nomination_event_id=nomination_id,
                mint=mint,
            )
            deadline = admitted_time + timedelta(
                seconds=config["panels"]["member_total_span_seconds_max"]
            )
            member = {
                "member_id": member_id,
                "batch_id": expected["batch_id"],
                "nomination_event_id": nomination_id,
                "mint": mint,
                "mint_decimals": decimals,
                "policy_version": config["cohort"]["policy_version"],
                "entered_at": _utc_text(admitted_time),
                "panel_deadline_at": _utc_text(deadline),
                "panel_status": {
                    "P0": "PENDING",
                    "P1": "BLOCKED_ON_P0",
                    "P2": "BLOCKED_ON_P1",
                },
            }
            admitted.append(member)
            local_seen.add(mint)
            state_code = "WATCHLIST_ACTIVE"
        candidate_states.append(
            {
                "nomination_event_id": nomination_id,
                "mint": mint,
                "state": state_code,
            }
        )

    working["evaluated_candidates_used"] += len(candidates)
    if not admitted:
        return _retain_and_stop(
            state=working,
            observation=observation,
            reason="NO_PREVIOUSLY_UNSEEN_ELIGIBLE_MINT",
        ) | {"candidate_states": candidate_states}

    quote_reservation = (
        len(admitted)
        * len(PANEL_ORDER)
        * config["panels"]["provider_calls_per_panel_max"]
    )
    caps = config["budget"]["caps"]
    _require(
        _budget_total(working, "quote_requests") + quote_reservation
        <= caps["quote_requests"],
        "remaining_quote_budget_cannot_complete_members",
    )
    _require(
        _budget_total(working, "external_requests") + quote_reservation
        <= caps["external_requests"],
        "remaining_external_budget_cannot_complete_members",
    )
    working["budget"]["reserved"]["quote_requests"] += quote_reservation
    working["budget"]["reserved"]["external_requests"] += quote_reservation
    working["accepted_source_observations"].append(
        {
            "batch_id": expected["batch_id"],
            "source_observation_id": source_id,
            "source_content_sha256": source_hash,
            "observed_at": _utc_text(observed_at),
        }
    )
    working["seen_mints"] = sorted(local_seen)
    working["admitted_members"].extend(admitted)
    next_batch = (
        batches[accepted_batches + 1]["batch_id"]
        if accepted_batches + 1 < len(batches)
        else None
    )
    return {
        "status": "ADMITTED_OFFLINE_PLAN_ONLY",
        "batch_id": expected["batch_id"],
        "candidate_states": candidate_states,
        "members": admitted,
        "state": working,
        "next_batch_id": next_batch,
        "provider_calls_performed": 0,
        "external_actions_authorized": False,
    }


def evaluate_panel_trigger(
    *,
    config: Mapping[str, Any],
    member: Mapping[str, Any],
    panel_history: Sequence[Mapping[str, Any]],
    requested_panel: str,
    now: str,
    recovery_health: str,
    response_bytes_used: int,
    stored_bytes_used: int,
    dataset_bytes_used: int,
    free_disk_bytes: int,
    remaining_reserved_provider_calls: int,
) -> JsonObject:
    """Return a foreground action decision; never execute the panel."""

    validate_runtime_config(config)
    _require(requested_panel in PANEL_ORDER, "panel_label_invalid")
    completed = [item.get("panel_id") for item in panel_history]
    expected_index = len(completed)
    _require(expected_index < len(PANEL_ORDER), "member_panels_already_complete")
    _require(completed == list(PANEL_ORDER[:expected_index]), "panel_history_order_drift")
    _require(requested_panel == PANEL_ORDER[expected_index], "panel_not_next")
    current = _utc(now, "now")
    admitted_at = _utc(member.get("entered_at"), "member_entered_at")
    deadline = admitted_at + timedelta(
        seconds=config["panels"]["member_total_span_seconds_max"]
    )
    if current > deadline:
        return {
            "status": "RETAIN_GAP_STOP_NO_BACKFILL",
            "reason": "MEMBER_TOTAL_SPAN_EXPIRED",
            "external_actions_authorized": False,
        }
    if expected_index:
        prior = _utc(panel_history[-1].get("completed_at"), "prior_completed_at")
        eligible_at = prior + timedelta(
            seconds=config["panels"]["minimum_separation_seconds"]
        )
        if current < eligible_at:
            return {
                "status": "WAIT_MINIMUM_SEPARATION",
                "eligible_at": _utc_text(eligible_at),
                "narrow_expiry_at": None,
                "external_actions_authorized": False,
            }
    else:
        eligible_at = admitted_at
        if current < eligible_at:
            return {
                "status": "WAIT_FOR_ADMISSION",
                "eligible_at": _utc_text(eligible_at),
                "external_actions_authorized": False,
            }

    if recovery_health != "HEALTHY":
        return {
            "status": "STOPPED_SAFELY",
            "reason": "RECOVERY_HEALTH_NOT_HEALTHY",
            "external_actions_authorized": False,
        }
    if remaining_reserved_provider_calls < config["panels"][
        "provider_calls_per_panel_max"
    ]:
        return {
            "status": "STOPPED_SAFELY",
            "reason": "REMAINING_BUDGET_CANNOT_COMPLETE_PANEL",
            "external_actions_authorized": False,
        }
    byte_budget = config["budget"]["bytes_and_storage"]
    measured = {
        "response": response_bytes_used,
        "stored": stored_bytes_used,
        "dataset": dataset_bytes_used,
    }
    for name, used in measured.items():
        _require(isinstance(used, int) and used >= 0, f"{name}_bytes_used_invalid")
        if used >= byte_budget[f"{name}_bytes_cap"]:
            return {
                "status": "STOPPED_SAFELY",
                "reason": f"{name.upper()}_BYTE_CAP_REACHED",
                "external_actions_authorized": False,
            }
    if free_disk_bytes < byte_budget["min_free_space_bytes_after_write"]:
        return {
            "status": "STOPPED_SAFELY",
            "reason": "FREE_DISK_FLOOR_NOT_MET",
            "external_actions_authorized": False,
        }
    return {
        "status": "READY_FOR_SEPARATE_EXTERNAL_AUTHORITY",
        "member_id": member["member_id"],
        "panel_id": requested_panel,
        "eligible_at": _utc_text(eligible_at),
        "deadline_at": _utc_text(deadline),
        "provider_api_rpc_wss_calls_max": config["panels"][
            "provider_calls_per_panel_max"
        ],
        "retries": 0,
        "external_actions_authorized": False,
    }


def prepare_offline_scenario(
    *, config: Mapping[str, Any], scenario: Mapping[str, Any]
) -> JsonObject:
    """Run the synthetic happy path and expose exact physical arithmetic."""

    _require(scenario.get("synthetic_only") is True, "fixture_must_be_synthetic")
    _require(scenario.get("contains_market_data") is False, "market_data_forbidden")
    _require(
        scenario.get("hypothesis_outcome_unsealed") is False,
        "hypothesis_outcome_unsealed",
    )
    state = initial_runtime_state(config)
    receipts: list[JsonObject] = []
    for observation in scenario["happy_path_observations"]:
        result = evaluate_nomination_observation(
            config=config,
            state=state,
            observation=observation,
            admitted_at=observation["observed_at"],
        )
        _require(result["status"] == "ADMITTED_OFFLINE_PLAN_ONLY", "happy_path_stopped")
        receipts.append({key: value for key, value in result.items() if key != "state"})
        state = result["state"]

    members = state["admitted_members"]
    projected = {
        key: _budget_total(state, key)
        for key in ("external_requests", "source_requests", "quote_requests")
    }
    complete_panels = len(members) * len(PANEL_ORDER)
    complete_quote_pairs = complete_panels * config["panels"]["quote_pairs_per_panel"]
    _require(len(members) == config["cohort"]["new_member_cap"], "happy_member_count_drift")
    _require(projected["external_requests"] == 184, "projected_external_drift")
    _require(projected["source_requests"] == 8, "projected_source_drift")
    _require(projected["quote_requests"] == 176, "projected_quote_drift")
    return {
        "schema": "smial.task21.event-triggered-final-cohort-offline-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "status": "PASS",
        "verdict": "FINAL_COHORT_RUNTIME_READY_OFFLINE_ONLY",
        "batch_receipts": receipts,
        "new_members": len(members),
        "planned_panels": complete_panels,
        "planned_quote_pairs": complete_quote_pairs,
        "projected_budget": projected,
        "external_request_headroom": config["budget"]["caps"]["external_requests"]
        - projected["external_requests"],
        "dataset_ready": False,
        "task22_eligible": False,
        "provider_calls_performed": 0,
        "raw_or_dataset_writes": 0,
        "next_boundary": {
            "atom_id": "T21-A6S_R2_EVENT_TRIGGERED_SOURCE_AND_P0_CAPTURE_V1",
            "status": "NOT_AUTHORIZED",
            "requires_separate_external_authority": True,
        },
    }
