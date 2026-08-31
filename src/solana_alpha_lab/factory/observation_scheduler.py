"""Crash-safe one-shot ObservationSchedule tick. systemd is the only time trigger."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from solana_alpha_lab.factory.observation_panel_publisher import (
    PublicationFault,
    publish_observation_batch,
    repair_open_publication_jobs,
)
from solana_alpha_lab.factory.observation_primitive_registry import (
    ObservationPrimitiveRegistry,
    PrimitiveRegistryError,
    load_observation_primitive_registry,
)
from solana_alpha_lab.factory.observation_primitives import (
    BUY_AMOUNT,
    RECENT_URL,
    SOL_MINT,
    execute_primitive,
    call_occurrence_id,
    parse_anchor,
    parse_first_seen,
    quote_url,
    request_sha256,
    search_url,
)
from solana_alpha_lab.factory.quote_surface_projection import (
    OBSERVED as SURFACE_OBSERVED,
    QuoteSurfaceProjectionError,
    hash_raw_response,
    project_quote_surface,
)
from solana_alpha_lab.factory.tokens_v2_typed_projection import (
    STATE_OBSERVED,
    TOKENS_V2_FIELD_KINDS,
    project_tokens_v2_field,
    project_tokens_v2_scalar,
    sanitize_tokens_v2_source_row,
)
from solana_alpha_lab.factory.observation_schedule import (
    parse_utc,
    render_utc,
    schedule_sha256,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    ObservationLifecycleError,
    _require_live_authority,
    complete_draining_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

OWNER = "tick-once"
SEARCH = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
DISCOVERY = "PRIM-JUPITER-TOKENS-V2-RECENT-001"
DEPENDENT_SELL = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
QUOTE_BUY = "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001"
BUY_1M = "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-1M-001"
REVERSE_1M = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-1M-001"
REVERSE_FOR_BUY = {QUOTE_BUY: DEPENDENT_SELL, BUY_1M: REVERSE_1M}
BUNDLE_TO_PRIMITIVE = {
    "BUNDLE-JUPITER-TOKEN-SEARCH-SNAPSHOT-001": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
    "BUNDLE-JUPITER-QUOTE-BUY-001": QUOTE_BUY,
    "BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001": DEPENDENT_SELL,
    "BUNDLE-JUPITER-QUOTE-BUY-1M-001": BUY_1M,
    "BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-1M-001": REVERSE_1M,
}
SCHEMA_REQUIRED_KEYS = {
    "PRIM-JUPITER-TOKENS-V2-RECENT-001": ("id",),
    "PRIM-JUPITER-TOKENS-V2-SEARCH-001": ("id",),
    QUOTE_BUY: ("outAmount",),
    DEPENDENT_SELL: ("outAmount",),
    BUY_1M: ("outAmount",),
    REVERSE_1M: ("outAmount",),
}
QUOTE_AMOUNT = {
    QUOTE_BUY: BUY_AMOUNT,
    BUY_1M: "1000000",
}
BUY_PRIMITIVES = frozenset(QUOTE_AMOUNT)
SELL_PRIMITIVES = frozenset(REVERSE_FOR_BUY.values())
SURFACE_FIELD_KEYS = {
    "FIELD-QUOTE-IN-AMOUNT-001": "in_amount",
    "FIELD-QUOTE-PRICE-IMPACT-PCT-001": "price_impact_pct",
    "FIELD-QUOTE-FEE-BPS-001": "fee_bps",
    "FIELD-QUOTE-PLATFORM-FEE-001": "platform_fee",
    "FIELD-QUOTE-ROUTER-001": "router",
    "FIELD-QUOTE-MODE-001": "mode",
    "FIELD-QUOTE-ROUTE-HOP-COUNT-001": "route_hop_count",
    "FIELD-QUOTE-ROUTE-FEE-AMOUNTS-PRESENT-001": "route_fee_amounts_present",
    "FIELD-QUOTE-RESPONSE-SHA256-001": "response_sha256",
}


class ObservationSchedulerError(ValueError):
    """Typed scheduler failure."""


def _sample_included(*, seed: str, entity_id: str, schedule_digest: str, probability: str) -> bool:
    digest = hashlib.sha256(f"{seed}|{entity_id}|{schedule_digest}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return bucket <= float(probability)


def poll_slot_id(
    *,
    primitive_id: str,
    query_profile_id: str,
    period_seconds: int,
    now: datetime,
    schedule_sha256: str | None = None,
    activation_id: str | None = None,
) -> str:
    epoch = int(now.astimezone(UTC).timestamp())
    slot = epoch - (epoch % int(period_seconds))
    return hashlib.sha256(
        (
            f"{primitive_id}|{query_profile_id}|{period_seconds}|{slot}|"
            f"{schedule_sha256 or ''}|{activation_id or ''}"
        ).encode("utf-8")
    ).hexdigest()


def _due_times(anchor: datetime, offset: int, lateness: int) -> tuple[str, str]:
    due = anchor + timedelta(seconds=offset)
    deadline = due + timedelta(seconds=lateness)
    return render_utc(due), render_utc(deadline)


def _first_non_none(*values: object) -> object | None:
    for value in values:
        if value is not None:
            return value
    return None


def _row_field(row: Mapping[str, Any], field_id: str) -> object:
    if field_id in TOKENS_V2_FIELD_KINDS:
        return project_tokens_v2_scalar(row, field_id)
    mapping = {
        "FIELD-QUOTE-BUY-OUT-AMOUNT-001": (
            _first_non_none(row.get("outAmount"), row.get("buy_out_amount"))
        ),
        "FIELD-QUOTE-SELL-OUT-AMOUNT-001": (
            _first_non_none(row.get("outAmount"), row.get("sell_out_amount"))
        ),
    }
    return mapping.get(field_id)


def _predicate_holds(predicate: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    value = _row_field(row, str(predicate["field_id"]))
    if value is None:
        return False
    operator = str(predicate["operator"])
    if "value_text" in predicate and predicate["value_text"] is not None:
        if operator not in {"EQ", "NEQ"}:
            return False
        left = str(value)
        right = str(predicate["value_text"])
        return left == right if operator == "EQ" else left != right
    if "value_decimal" in predicate and predicate["value_decimal"] is not None:
        try:
            left = Decimal(str(value))
            right = Decimal(str(predicate["value_decimal"]))
        except (InvalidOperation, KeyError, TypeError):
            return False
        mapping = {
            "EQ": left == right,
            "NEQ": left != right,
            "GT": left > right,
            "GTE": left >= right,
            "LT": left < right,
            "LTE": left <= right,
        }
        return bool(mapping.get(operator, False))
    return False


def _population_eligible(schedule: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    """Evaluate only source predicates during discovery admission."""
    population = schedule["population"]
    return _predicates_hold(population["source_predicates"], row)


def _x_population_eligible(schedule: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    """Evaluate X predicates only after X-point evidence is available."""
    return _predicates_hold(schedule["population"]["x_eligibility_predicates"], row)


def _predicates_hold(
    predicates: Sequence[Mapping[str, Any]],
    row: Mapping[str, Any],
) -> bool:
    for predicate in predicates:
        if not _predicate_holds(predicate, row):
            return False
    return True


class _Accounting:
    def __init__(
        self,
        store: ObservationScheduleStore,
        schedule: Mapping[str, Any],
        activation_id: str,
        now: datetime,
        credit_costs: Mapping[str, int] | None = None,
    ) -> None:
        self.store = store
        self.now = now
        self.activation_id = activation_id
        self.digest = str(schedule["schedule_sha256"])
        self.utc_day = now.strftime("%Y-%m-%d")
        self.day = store.load_accounting(
            schedule_sha256=self.digest, activation_id=activation_id, utc_day=self.utc_day
        )
        self.life = store.load_lifetime(schedule_sha256=self.digest, activation_id=activation_id)
        self.tick_calls = 0
        self.budgets = schedule["budgets"]
        self.pace = int(self.budgets["min_provider_pace_seconds"])
        self.credit_costs = dict(credit_costs or {})
        if self.day.get("last_provider_call_at") is None:
            self.day["last_provider_call_at"] = store.latest_provider_call_at(
                schedule_sha256=self.digest,
                activation_id=activation_id,
            )

    def _refresh_day(self, reference: datetime) -> None:
        utc_day = reference.astimezone(UTC).strftime("%Y-%m-%d")
        if utc_day == self.utc_day:
            return
        self.utc_day = utc_day
        self.day = self.store.load_accounting(
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            utc_day=utc_day,
        )
        if self.day.get("last_provider_call_at") is None:
            self.day["last_provider_call_at"] = self.store.latest_provider_call_at(
                schedule_sha256=self.digest,
                activation_id=self.activation_id,
            )

    def gate(
        self,
        *,
        extra_calls: int = 1,
        extra_credits: int = 1,
        extra_raw: int = 1,
        now: datetime | None = None,
    ) -> str | None:
        reference_now = (now or self.now).astimezone(UTC)
        self._refresh_day(reference_now)
        self.now = reference_now
        if str(self.budgets.get("cash_usd_max")) != "0":
            return "CHANGE_LANE_SAFETY_CONTRACT_GAP"
        if self.budgets.get("retry") is not False or self.budgets.get("fallback") is not False:
            return "CHANGE_LANE_SAFETY_CONTRACT_GAP"
        if self.tick_calls + extra_calls > int(self.budgets["provider_calls_per_tick_max"]):
            return "BLOCKED_BUDGET"
        if int(self.day["provider_calls"]) + extra_calls > int(
            self.budgets["provider_calls_per_utc_day_max"]
        ):
            return "BLOCKED_BUDGET"
        if int(self.life["provider_calls"]) + extra_calls > int(
            self.budgets["provider_calls_lifetime_max"]
        ):
            return "BLOCKED_BUDGET"
        if int(self.day["modeled_credits"]) + extra_credits > int(
            self.budgets["modeled_provider_credits_per_utc_day_max"]
        ):
            return "BLOCKED_BUDGET"
        if int(self.day["raw_bytes"]) + extra_raw > int(self.budgets["raw_bytes_per_utc_day_max"]):
            return "BLOCKED_BUDGET"
        if int(self.life["canonical_bytes"]) + extra_raw > int(
            self.budgets["canonical_bytes_lifetime_max"]
        ):
            return "BLOCKED_BUDGET"
        last = self.day.get("last_provider_call_at")
        if last:
            try:
                elapsed = (reference_now - parse_utc(str(last))).total_seconds()
            except Exception:
                elapsed = self.pace
            if elapsed < self.pace:
                return "PACE_WAIT"
        return None

    def note(
        self,
        *,
        raw_bytes: int = 1,
        credits: int = 1,
        completed_at: datetime | None = None,
    ) -> None:
        completed = (completed_at or self.now).astimezone(UTC)
        self._refresh_day(completed)
        self.now = completed
        self.tick_calls += 1
        self.day["provider_calls"] = int(self.day["provider_calls"]) + 1
        self.day["modeled_credits"] = int(self.day["modeled_credits"]) + credits
        self.day["raw_bytes"] = int(self.day["raw_bytes"]) + raw_bytes
        self.day["last_provider_call_at"] = render_utc(completed)
        self.life["provider_calls"] = int(self.life["provider_calls"]) + 1
        self.life["canonical_bytes"] = int(self.life["canonical_bytes"]) + raw_bytes
        self.store.save_accounting(
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            utc_day=self.utc_day,
            values=self.day,
            clock=completed,
        )
        self.store.save_lifetime(
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            provider_calls=int(self.life["provider_calls"]),
            canonical_bytes=int(self.life["canonical_bytes"]),
            clock=completed,
        )


def _primitive_credit_cost(accounts: _Accounting, primitive_id: str) -> int:
    return max(1, int(accounts.credit_costs.get(primitive_id, 1)))


def _result_completion(result: Mapping[str, Any], fallback: datetime) -> datetime:
    raw = result.get("first_reliable_available_at") or result.get("response_received_at")
    if isinstance(raw, str):
        try:
            return parse_utc(raw)
        except Exception:
            pass
    return fallback.astimezone(UTC)


def _entity_terminal(
    result: Mapping[str, Any],
    entity_id: str,
    *,
    previously_observed: bool,
) -> tuple[str, str | None]:
    """Classify one entity from a provider result.

    DISAPPEARED is reserved for entity absence inside a successful OBSERVED
    snapshot. Top-level provider misses (timeout, HTTP error, NO_ROUTE, …)
    are always MISSING_TYPED even after a prior OBSERVED.
    """
    entities = result.get("entities")
    result_status = str(result.get("status") or "")
    if result_status == "OBSERVED" and isinstance(entities, Mapping):
        if entity_id in entities:
            row = entities[entity_id]
            status = str(row.get("status") or "MISSING_TYPED")
            reason = row.get("missing_reason")
            if status != "OBSERVED" and previously_observed:
                return "DISAPPEARED", str(reason or "ENTITY_ABSENT_FROM_RESPONSE")
            if status != "OBSERVED":
                return "MISSING_TYPED", str(reason or "ENTITY_ABSENT_FROM_RESPONSE")
            return "OBSERVED", None
        if previously_observed:
            return "DISAPPEARED", str(
                result.get("missing_reason") or "ENTITY_ABSENT_FROM_RESPONSE"
            )
        return "MISSING_TYPED", str(
            result.get("missing_reason") or "ENTITY_ABSENT_FROM_RESPONSE"
        )
    return "MISSING_TYPED", str(
        result.get("missing_reason") or result_status or "PROVIDER_FAILURE"
    )


def _apply_x_phase(
    *,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    claim: Mapping[str, Any],
    result: Mapping[str, Any],
    terminal_state: str,
    missing_reason: str | None,
    now: datetime,
) -> tuple[str, str | None, list[dict[str, Any]]]:
    """Run X eligibility only against the observed X response row."""
    if str(claim["point_id"]) != str(schedule["x_point"]["point_id"]):
        return terminal_state, missing_reason, []
    x_primitive_ids = {
        BUNDLE_TO_PRIMITIVE[str(bundle_id)]
        for bundle_id in schedule["x_point"]["bundle_ids"]
        if BUNDLE_TO_PRIMITIVE[str(bundle_id)] not in SELL_PRIMITIVES
    }
    if str(claim["primitive_id"]) not in x_primitive_ids:
        return terminal_state, missing_reason, []
    if not store.candidate_exists(
        schedule_sha256=str(claim["schedule_sha256"]),
        activation_id=activation_id,
        entity_id=str(claim["entity_id"]),
    ):
        return terminal_state, missing_reason, []
    entities = result.get("entities") or {}
    entity = entities.get(str(claim["entity_id"])) if isinstance(entities, Mapping) else None
    x_row = entity.get("row") if isinstance(entity, Mapping) else None
    reanchored_censored = (
        _apply_authoritative_anchor(
            store=store,
            schedule=schedule,
            activation_id=activation_id,
            claim=claim,
            x_row=x_row,
            now=now,
        )
        if terminal_state == "OBSERVED"
        else []
    )
    late_current = next(
        (
            item
            for item in reanchored_censored
            if item["point_id"] == claim["point_id"]
            and item["primitive_id"] == claim["primitive_id"]
        ),
        None,
    )
    if late_current is not None:
        reason = "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE"
        store.set_candidate_state(
            {
                "schedule_sha256": claim["schedule_sha256"],
                "activation_id": activation_id,
                "entity_id": claim["entity_id"],
                "state": "X_POPULATION_INELIGIBLE",
                "payload": {
                    "x_eligibility_state": "X_POPULATION_INELIGIBLE",
                    "missing_reason": reason,
                },
            },
            clock=now,
        )
        censored = store.censor_remaining_points(
            schedule_sha256=str(claim["schedule_sha256"]),
            activation_id=activation_id,
            entity_id=str(claim["entity_id"]),
            reason=reason,
            exclude_point_id=str(claim["point_id"]),
            exclude_primitive_id=str(claim["primitive_id"]),
            clock=now,
        )
        current_key = (str(claim["point_id"]), str(claim["primitive_id"]))
        other_censored = [
            item
            for item in reanchored_censored + censored
            if (str(item["point_id"]), str(item["primitive_id"])) != current_key
        ]
        return (
            str(late_current.get("state") or "CENSORED_LATE"),
            reason,
            other_censored,
        )
    candidates = store.list_candidates(
        schedule_sha256=str(claim["schedule_sha256"]),
        activation_id=activation_id,
    )
    candidate = next(
        (item for item in candidates if str(item["entity_id"]) == str(claim["entity_id"])),
        None,
    )
    candidate_payload = dict(candidate.get("payload") or {}) if candidate else {}
    x_evidence = dict(candidate_payload.get("x_evidence") or {})
    x_predicate_evidence = dict(
        candidate_payload.get("x_predicate_evidence") or {}
    )
    source_row = candidate_payload.get("source_row")
    if isinstance(source_row, Mapping):
        x_evidence.update(dict(source_row))
    if isinstance(x_row, Mapping):
        x_evidence.update(dict(x_row))
        x_predicate_evidence.update(dict(x_row))
    x_terminal_states = {
        "OBSERVED",
        "MISSING_TYPED",
        "DISAPPEARED",
        "CENSORED",
        "CENSORED_LATE",
        "IN_FLIGHT_CALL_INDETERMINATE",
        "DEPENDENCY_MISSING",
        "BLOCKED_BUDGET",
    }
    observed_x_primitives = {
        str(item["primitive_id"])
        for item in store.due_in_states(
            (
                "OBSERVED",
                "MISSING_TYPED",
                "DISAPPEARED",
                "CENSORED",
                "CENSORED_LATE",
                "IN_FLIGHT_CALL_INDETERMINATE",
                "DEPENDENCY_MISSING",
                "BLOCKED_BUDGET",
            )
        )
        if str(item["schedule_sha256"]) == str(claim["schedule_sha256"])
        and str(item["activation_id"]) == activation_id
        and str(item["entity_id"]) == str(claim["entity_id"])
        and str(item["point_id"]) == str(claim["point_id"])
        and str(item["primitive_id"]) in x_primitive_ids
    }
    if terminal_state in x_terminal_states:
        observed_x_primitives.add(str(claim["primitive_id"]))
    if observed_x_primitives != x_primitive_ids:
        store.set_candidate_state(
            {
                "schedule_sha256": claim["schedule_sha256"],
                "activation_id": activation_id,
                "entity_id": claim["entity_id"],
                "state": "SAMPLED_MEMBER",
                "payload": {
                    "x_evidence": x_evidence,
                    "x_predicate_evidence": x_predicate_evidence,
                    "x_observed_at": result.get("first_reliable_available_at"),
                },
            },
            clock=now,
        )
        return terminal_state, missing_reason, reanchored_censored
    x_rows = [
        item
        for item in store.due_in_states(tuple(x_terminal_states))
        if str(item["schedule_sha256"]) == str(claim["schedule_sha256"])
        and str(item["activation_id"]) == activation_id
        and str(item["entity_id"]) == str(claim["entity_id"])
        and str(item["point_id"]) == str(claim["point_id"])
        and str(item["primitive_id"]) in x_primitive_ids
    ]
    if terminal_state != "OBSERVED" or any(
        str(item["state"]) != "OBSERVED" for item in x_rows
    ):
        reason = "X_EVIDENCE_NOT_OBSERVED"
        store.set_candidate_state(
            {
                "schedule_sha256": claim["schedule_sha256"],
                "activation_id": activation_id,
                "entity_id": claim["entity_id"],
                "state": "X_POPULATION_INELIGIBLE",
                "payload": {
                    "x_eligibility_state": "X_POPULATION_INELIGIBLE",
                    "missing_reason": reason,
                    "x_observed_at": result.get("first_reliable_available_at"),
                    "x_evidence": x_evidence,
                    "x_predicate_evidence": x_predicate_evidence,
                },
            },
            clock=now,
        )
        censored = store.censor_remaining_points(
            schedule_sha256=str(claim["schedule_sha256"]),
            activation_id=activation_id,
            entity_id=str(claim["entity_id"]),
            reason=reason,
            exclude_point_id=str(claim["point_id"]),
            exclude_primitive_id=str(claim["primitive_id"]),
            clock=now,
        )
        return terminal_state, reason, reanchored_censored + censored
    if not _x_population_eligible(schedule, x_predicate_evidence):
        reason = "X_POPULATION_PREDICATE_FAIL_CLOSED"
        store.set_candidate_state(
            {
                "schedule_sha256": claim["schedule_sha256"],
                "activation_id": activation_id,
                "entity_id": claim["entity_id"],
                "state": "X_POPULATION_INELIGIBLE",
                "payload": {
                    "x_eligibility_state": "X_POPULATION_INELIGIBLE",
                    "missing_reason": reason,
                    "x_observed_at": result.get("first_reliable_available_at"),
                    "x_evidence": x_evidence,
                    "x_predicate_evidence": x_predicate_evidence,
                },
            },
            clock=now,
        )
        censored = store.censor_remaining_points(
            schedule_sha256=str(claim["schedule_sha256"]),
            activation_id=activation_id,
            entity_id=str(claim["entity_id"]),
            reason="X_POPULATION_INELIGIBLE",
            exclude_point_id=str(claim["point_id"]),
            exclude_primitive_id=str(claim["primitive_id"]),
            clock=now,
        )
        return terminal_state, reason, reanchored_censored + censored
    store.set_candidate_state(
        {
            "schedule_sha256": claim["schedule_sha256"],
            "activation_id": activation_id,
            "entity_id": claim["entity_id"],
            "state": "X_ELIGIBLE",
            "payload": {
                "x_eligibility_state": "X_ELIGIBLE",
                "x_observed_at": result.get("first_reliable_available_at"),
                "x_evidence": x_evidence,
                "x_predicate_evidence": x_predicate_evidence,
            },
        },
        clock=now,
    )
    return terminal_state, missing_reason, reanchored_censored


def _apply_authoritative_anchor(
    *,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    claim: Mapping[str, Any],
    x_row: object,
    now: datetime,
) -> list[dict[str, Any]]:
    payload = claim.get("payload") or {}
    if not payload.get("provisional_due"):
        return []
    if not isinstance(x_row, Mapping):
        return []
    anchor = parse_anchor(x_row)
    if anchor is None:
        return []
    points = [schedule["x_point"], *list(schedule["y_points"])]
    due_times = {
        str(point["point_id"]): _due_times(
            anchor,
            int(point["due_offset_seconds"]),
            int(point["allowed_lateness_seconds"]),
        )
        for point in points
    }
    censored = store.reanchor_candidate(
        schedule_sha256=str(claim["schedule_sha256"]),
        activation_id=activation_id,
        entity_id=str(claim["entity_id"]),
        authoritative_anchor=render_utc(anchor),
        due_times=due_times,
        exclude_point_id=str(claim["point_id"]),
        exclude_primitive_id=str(claim["primitive_id"]),
        clock=now,
    )
    provisional_terminal = bool(payload.get("provisional_due"))
    if provisional_terminal:
        current_due, current_deadline = due_times[str(claim["point_id"])]
        observed_at = now
        try:
            valid_window = (
                parse_utc(current_due) <= observed_at <= parse_utc(current_deadline)
            )
        except Exception:
            valid_window = False
        if not valid_window:
            late_item = store.mark_point_censored_late(
                claim,
                reason="AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                clock=now,
            )
            if isinstance(claim, dict):
                invalid_payload = dict(payload)
                invalid_payload.update(
                    {
                        "missing_reason": "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                        "terminal_reason": "AUTHORITATIVE_ANCHOR_RESOLVED_TOO_LATE",
                        "scientific_valid": False,
                    }
                )
                claim["payload"] = invalid_payload
            censored.append(late_item)
            return censored
    if isinstance(claim, dict):
        claim["due_at"], claim["deadline_at"] = due_times[str(claim["point_id"])]
        next_payload = dict(payload)
        next_payload.update(
            {
                "authoritative_anchor": render_utc(anchor),
                "provisional_schedule_anchor": None,
                "provisional_due": False,
            }
        )
        claim["payload"] = next_payload
    return censored


def _apply_missingness_policy(
    *,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    claim: Mapping[str, Any],
    terminal_state: str,
    now: datetime,
) -> list[dict[str, Any]]:
    if terminal_state not in {"MISSING_TYPED", "DISAPPEARED"}:
        return []
    missingness = schedule.get("missingness") or {}
    disappearance = schedule.get("disappearance") or {}
    if terminal_state == "DISAPPEARED":
        should_censor = (
            str(disappearance.get("default"))
            == "CENSOR_REMAINING_POINTS"
        )
    else:
        should_censor = (
            missingness.get("continue_later_points_after_missing") is False
        )
    if not should_censor:
        return []
    return store.censor_remaining_points(
        schedule_sha256=str(claim["schedule_sha256"]),
        activation_id=str(claim["activation_id"]),
        entity_id=str(claim["entity_id"]),
        reason=f"{terminal_state}_CENSOR_REMAINING_POINTS",
        exclude_point_id=str(claim["point_id"]),
        clock=now,
    )


def _mints_from_search_url(url: str) -> set[str]:
    query = parse_qs(urlsplit(url).query).get("query", [""])[0]
    return {item for item in query.split(",") if item}


def _search_call_identity(
    *,
    schedule_sha256: str,
    activation_id: str,
    claims: Sequence[Mapping[str, Any]],
) -> tuple[str, str, str]:
    claim_identity = sorted(
        {
            f'{item["entity_id"]}:{item["point_id"]}:{item["due_at"]}'
            for item in claims
        }
    )
    live_ids = sorted({str(item["entity_id"]) for item in claims})
    url = search_url(list(live_ids))
    digest = request_sha256(method="GET", url=url, body=None, primitive_version="1.0")
    occurrence = call_occurrence_id(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        primitive_id=SEARCH,
        point_id="BATCH",
        due_at="|".join(
            sorted({str(item["due_at"]) for item in claims})
        ),
        claim_identity_set=claim_identity,
        request_digest=digest,
    )
    return url, digest, occurrence


def _discover(
    *,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    now: datetime,
    opener: object,
    credential_loader: Callable[[], str] | None,
    redact_with: str | None,
    accounts: _Accounting,
    execution_clock: Callable[[], datetime],
) -> tuple[list[Mapping[str, Any]], str | None, int, str | None, bool, dict[str, Any]]:
    slot = poll_slot_id(
        primitive_id=str(schedule["source_poll"]["primitive_id"]),
        query_profile_id=str(schedule["source_poll"]["query_profile_id"]),
        period_seconds=int(schedule["source_poll"]["period_seconds"]),
        now=now,
        schedule_sha256=str(schedule["schedule_sha256"]),
        activation_id=activation_id,
    )
    cached = store.load_poll_slot(slot)
    if cached is not None:
        payload = cached["payload"]
        rows = list(payload.get("rows") or [])
        return (
            rows,
            None,
            0,
            redact_with,
            True,
            {
                "request_sha256": cached.get("request_sha256"),
                "call_occurrence_id": payload.get("call_occurrence_id"),
                "request_started_at": payload.get("request_started_at"),
                "response_received_at": payload.get("response_received_at"),
                "first_reliable_available_at": payload.get(
                    "first_reliable_available_at"
                ),
            },
        )
    digest = str(schedule["schedule_sha256"])
    request_digest = request_sha256(
        method="GET", url=RECENT_URL, body=None, primitive_version="1.0"
    )
    occurrence = call_occurrence_id(
        schedule_sha256=digest,
        activation_id=activation_id,
        primitive_id=DISCOVERY,
        point_id="DISCOVERY",
        due_at=slot,
        claim_identity_set=(),
        request_digest=request_digest,
    )
    prior = store.call_state(occurrence)
    if prior == "STARTED":
        return (
            [],
            "IN_FLIGHT_CALL_INDETERMINATE",
            0,
            redact_with,
            False,
            {"request_sha256": request_digest, "call_occurrence_id": occurrence},
        )
    if prior == "COMPLETED":
        ledger = store.call_payload(occurrence) or {}
        cached_rows = ledger.get("rows")
        if isinstance(cached_rows, list):
            return (
                list(cached_rows),
                None,
                0,
                redact_with,
                True,
                {
                    "request_sha256": request_digest,
                    "call_occurrence_id": occurrence,
                    "request_started_at": ledger.get("request_started_at"),
                    "response_received_at": ledger.get("response_received_at"),
                    "first_reliable_available_at": ledger.get(
                        "first_reliable_available_at"
                    ),
                },
            )
    blocked = accounts.gate(
        extra_credits=_primitive_credit_cost(accounts, DISCOVERY),
        now=execution_clock(),
    )
    if blocked:
        return (
            [],
            blocked,
            0,
            redact_with,
            False,
            {"request_sha256": request_digest, "call_occurrence_id": occurrence},
        )
    holder = redact_with
    credential_reads = 0
    if holder is None and credential_loader is not None:
        holder = credential_loader()
        credential_reads = 1
    attempt_id = f"ATT-{uuid4().hex[:12].upper()}"
    start_state = store.start_call(
        request_sha256=request_digest,
        call_occurrence_id=occurrence,
        attempt_id=attempt_id,
        primitive_id=DISCOVERY,
        payload={"url": RECENT_URL, "poll_slot_id": slot},
        clock=now,
    )
    if start_state != "STARTED":
        return (
            [],
            start_state,
            credential_reads,
            holder,
            False,
            {"request_sha256": request_digest, "call_occurrence_id": occurrence},
        )
    result = execute_primitive(
        primitive_id=DISCOVERY,
        primitive_version="1.0",
        method="GET",
        url=RECENT_URL,
        opener=opener,
        clock=execution_clock,
        redact_with=holder,
        schema_required_keys=SCHEMA_REQUIRED_KEYS.get(DISCOVERY),
    )
    completion = _result_completion(result, now)
    accounts.note(
        raw_bytes=len(json.dumps(result.get("body"), default=str)),
        credits=_primitive_credit_cost(accounts, DISCOVERY),
        completed_at=completion,
    )
    store.complete_call(
        request_sha256=request_digest,
        call_occurrence_id=occurrence,
        attempt_id=attempt_id,
        payload={
            "status": result.get("status"),
            "missing_reason": result.get("missing_reason"),
            "response_sha256": result.get("response_sha256"),
            "rows": result.get("body") if isinstance(result.get("body"), list) else [],
            "call_occurrence_id": occurrence,
            "request_started_at": result.get("request_started_at"),
            "response_received_at": result.get("response_received_at"),
            "first_reliable_available_at": result.get("first_reliable_available_at"),
        },
        clock=completion,
    )
    body = result.get("body")
    rows = body if isinstance(body, list) else []
    store.save_poll_slot(
        poll_slot_id=slot,
        request_sha256=request_digest,
        payload={
            "rows": rows,
            "response_sha256": result.get("response_sha256"),
            "call_occurrence_id": occurrence,
            "request_started_at": result.get("request_started_at"),
            "response_received_at": result.get("response_received_at"),
            "first_reliable_available_at": result.get(
                "first_reliable_available_at"
            ),
        },
        clock=completion,
    )
    return (
        list(rows),
        None,
        credential_reads,
        holder,
        False,
        {
            "request_sha256": request_digest,
            "call_occurrence_id": occurrence,
            "request_started_at": result.get("request_started_at"),
            "response_received_at": result.get("response_received_at"),
            "first_reliable_available_at": result.get(
                "first_reliable_available_at"
            ),
        },
    )


def tick_once(
    *,
    root,
    data_root,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    now: datetime,
    opener: object | None = None,
    credential_loader: Callable[[], str] | None = None,
    producer_git_sha: str,
    max_claims: int = 60,
    discovery_rows: Sequence[Mapping[str, Any]] | None = None,
    last_tick_at: datetime | None = None,
    redact_with: str | None = None,
    fault_after: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ObservationSchedulerError("TIMESTAMP_INVALID")
    now = now.astimezone(UTC)
    if last_tick_at is not None and now < last_tick_at.astimezone(UTC):
        raise ObservationSchedulerError("CLOCK_WENT_BACKWARDS")
    if store.restore_marker_unresolved():
        raise ObservationSchedulerError("RESTORE_MARKER_UNRESOLVED")
    digest = str(schedule.get("schedule_sha256") or schedule_sha256(schedule))
    if schedule_sha256(schedule) != digest:
        raise ObservationSchedulerError("INVALID_IDENTITY")
    activation = store.get_activation(digest, activation_id)
    if activation is None:
        raise ObservationSchedulerError("ACTIVATION_MISSING")
    state = str(activation["state"])
    if now < parse_utc(str(activation["starts_at"])):
        return {
            "terminal": "NOT_YET_ACTIVE",
            "provider_calls": 0,
            "credential_reads": 0,
        }
    if state in {
        "PAUSED_OPERATOR",
        "ABORTED_SAFETY",
        "BLOCKED_AUTHORITY",
        "BLOCKED_BUDGET",
        "COMPLETE",
    }:
        return {"terminal": state, "provider_calls": 0, "credential_reads": 0}
    try:
        _require_live_authority(
            store,
            root=root,
            document=schedule,
            schedule_sha256=digest,
            now=now,
            receipt_sha256=str(activation.get("authority_receipt_sha256") or ""),
        )
    except ObservationLifecycleError as exc:
        raise ObservationSchedulerError(str(exc)) from exc
    lease_token = store.acquire_lease(f"{OWNER}-{uuid4().hex[:12]}", clock=now)
    if not lease_token:
        raise ObservationSchedulerError("WRITER_BUSY")
    credential_reads = 0
    provider_calls = 0
    published_rows: list[dict[str, Any]] = []
    stop_reason: str | None = None
    source_poll_reused = False
    discovery_context: dict[str, Any] = {}
    def execution_clock() -> datetime:
        current = datetime.now(UTC)
        # A caller may supply a logical/frozen scheduler time for offline
        # fixtures.  Never manufacture an availability time before that
        # tick, while still using the wall clock for an unconfigured runtime.
        return max(current, now)

    if clock is not None:
        execution_clock = clock
    try:
        try:
            registry = load_observation_primitive_registry(root)
            registry.verify_implementation_hashes()
        except PrimitiveRegistryError as exc:
            raise ObservationSchedulerError(str(exc)) from exc
        repair_open_publication_jobs(
            data_root=data_root,
            root=root,
            schedule=schedule,
            activation_id=activation_id,
            now=now,
            producer_git_sha=producer_git_sha,
            fault_after=fault_after,
        )
        credit_costs = {
            primitive_id: int(
                (primitive.get("modeled_credit_cost") or {}).get("credits_per_request", 1)
            )
            for primitive_id, primitive in registry.primitives.items()
        }
        accounts = _Accounting(
            store,
            schedule,
            activation_id,
            now,
            credit_costs=credit_costs,
        )
        due_work_waiting = any(
            str(item["schedule_sha256"]) == digest
            and str(item["activation_id"]) == activation_id
            for item in store.due_in_states(
                ("PENDING", "DUE", "CLAIMED"),
                due_at_max=now,
            )
        )
        successor_before_cutover = any(
            str(item["successor_schedule_sha256"]) == digest
            and str(item["successor_activation_id"]) == activation_id
            and now < parse_utc(str(item["cutover_at"]))
            for item in store.list_rollovers()
        )
        predecessor_before_cutover = any(
            str(item["predecessor_schedule_sha256"]) == digest
            and str(item["predecessor_activation_id"]) == activation_id
            and now < parse_utc(str(item["cutover_at"]))
            for item in store.list_rollovers()
        )
        from solana_alpha_lab.factory.observation_schedule_lifecycle import (
            drain_expired_admission,
            materialize_pending_observation_snapshots,
        )

        drained = drain_expired_admission(
            data_root=data_root,
            store=store,
            schedule_sha256=digest,
            activation_id=activation_id,
            now=now,
            producer_git_sha=producer_git_sha,
        )
        if drained is not None and drained.get("state") == "DRAINING":
            state = "DRAINING"
        stops_admitting_at = parse_utc(str(activation["stops_admitting_at"]))
        admission_open = now < stops_admitting_at
        can_admit_before_cutover = admission_open and (
            state == "ACTIVE"
            or (state == "DRAINING" and predecessor_before_cutover)
        )
        poll_enabled = bool(schedule.get("source_poll", {}).get("enabled", True))
        if (
            discovery_rows is None
            and poll_enabled
            and opener is not None
            and can_admit_before_cutover
            and not due_work_waiting
            and not successor_before_cutover
        ):
            (
                discovery_rows,
                stop_reason,
                credential_reads,
                holder_disc,
                source_poll_reused,
                discovery_context,
            ) = _discover(
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=now,
                    opener=opener,
                    credential_loader=credential_loader,
                    redact_with=redact_with,
                    accounts=accounts,
                    execution_clock=execution_clock,
            )
            if holder_disc is not None:
                redact_with = holder_disc
            if stop_reason in {"BLOCKED_BUDGET", "CHANGE_LANE_SAFETY_CONTRACT_GAP"}:
                store.upsert_activation(
                    {
                        "schedule_sha256": digest,
                        "activation_id": activation_id,
                        "schedule_key": activation["schedule_key"],
                        "state": stop_reason,
                        "authority_receipt_sha256": activation.get("authority_receipt_sha256"),
                        "starts_at": activation["starts_at"],
                        "stops_admitting_at": activation["stops_admitting_at"],
                        "payload": {"reason": stop_reason},
                    },
                    clock=now,
                )
                return {
                    "terminal": stop_reason,
                    "provider_calls": accounts.tick_calls,
                    "credential_reads": credential_reads,
                    "source_poll_reused": source_poll_reused,
                }
        if discovery_rows is not None and can_admit_before_cutover:
            _admit_candidates(
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                rows=discovery_rows,
                now=now,
                accounts=accounts,
                discovery_context=discovery_context,
            )
        recovered = [
            item
            for item in store.due_in_states(("CLAIMED",), due_at_max=now)
            if str(item["schedule_sha256"]) == digest
            and str(item["activation_id"]) == activation_id
        ]
        claims = recovered + store.claim_due(
            limit=max_claims,
            now=now,
            owner=OWNER,
            schedule_sha256=digest,
            activation_id=activation_id,
        )
        holder = redact_with
        batch_size = int(registry.require_primitive(SEARCH).get("max_batch_size") or 1)
        search_claims = [item for item in claims if str(item["primitive_id"]) == SEARCH]
        search_by_due: dict[str, list[Mapping[str, Any]]] = {}
        for item in search_claims:
            search_by_due.setdefault(str(item["due_at"]), []).append(item)
        for due_at in sorted(search_by_due):
          for index in range(0, len(search_by_due[due_at]), max(1, batch_size)):
            chunk = search_by_due[due_at][index : index + max(1, batch_size)]
            live = []
            for claim in chunk:
                if now > parse_utc(claim["deadline_at"]):
                    store.insert_due(
                        _due_copy(
                            claim,
                            state="CENSORED_LATE",
                            payload={"missing_reason": "CENSORED_LATE"},
                        ),
                        clock=now,
                    )
                    published_rows.append(
                        _observation_row(
                            claim,
                            "CENSORED_LATE",
                            now,
                            claim.get("request_sha256"),
                            missing_reason="CENSORED_LATE",
                        )
                    )
                else:
                    live.append(claim)
            if not live:
                continue
            url, request_digest, occurrence = _search_call_identity(
                schedule_sha256=digest,
                activation_id=activation_id,
                claims=live,
            )
            prior = store.call_state(occurrence)
            if prior == "STARTED":
                for claim in live:
                    store.insert_due(
                        _due_copy(
                            claim,
                            state="IN_FLIGHT_CALL_INDETERMINATE",
                            request_sha256=request_digest,
                            call_occurrence_id=occurrence,
                            payload={"missing_reason": "IN_FLIGHT_CALL_INDETERMINATE"},
                        ),
                        clock=now,
                    )
                    published_rows.append(
                        _observation_row(
                            claim,
                            "IN_FLIGHT_CALL_INDETERMINATE",
                            now,
                            request_digest,
                            call_occurrence_id=occurrence,
                        )
                    )
                continue
            if prior == "COMPLETED":
                ledger_payload = (
                    store.call_payload(occurrence)
                    or {}
                )
                recovered_result = {
                    "status": ledger_payload.get("status"),
                    "missing_reason": ledger_payload.get("missing_reason"),
                    "entities": ledger_payload.get("entities") or {},
                    "response_sha256": ledger_payload.get("response_sha256"),
                    "first_reliable_available_at": ledger_payload.get(
                        "first_reliable_available_at"
                    ),
                }
                for claim in live:
                    previously = store.has_prior_observation(
                        schedule_sha256=digest,
                        activation_id=activation_id,
                        entity_id=str(claim["entity_id"]),
                    )
                    terminal_state, missing_reason = _entity_terminal(
                        recovered_result,
                        str(claim["entity_id"]),
                        previously_observed=previously,
                    )
                    terminal_state, x_reason, censored_points = _apply_x_phase(
                        store=store,
                        schedule=schedule,
                        activation_id=activation_id,
                        claim=claim,
                        result=recovered_result,
                        terminal_state=terminal_state,
                        missing_reason=missing_reason,
                        now=_result_completion(ledger_payload, now),
                    )
                    censored_points.extend(
                        _apply_missingness_policy(
                            store=store,
                            schedule=schedule,
                            claim=claim,
                            terminal_state=terminal_state,
                            now=_result_completion(ledger_payload, now),
                        )
                    )
                    store.insert_due(
                        _due_copy(
                            claim,
                            state=terminal_state,
                            request_sha256=request_digest,
                            call_occurrence_id=occurrence,
                            payload={
                                "missing_reason": x_reason
                                or missing_reason
                                or ledger_payload.get("missing_reason")
                                or "RECOVERED_COMPLETED_LEDGER",
                                "response_sha256": ledger_payload.get("response_sha256"),
                                "request_started_at": ledger_payload.get(
                                    "request_started_at"
                                ),
                                "response_received_at": ledger_payload.get(
                                    "response_received_at"
                                ),
                                "first_reliable_available_at": ledger_payload.get(
                                    "first_reliable_available_at"
                                ),
                            },
                        ),
                        clock=now,
                    )
                    published_rows.append(
                        _observation_row(
                            claim,
                            terminal_state,
                            _result_completion(ledger_payload, now),
                            request_digest,
                            call_occurrence_id=occurrence,
                            response_payload=(
                                (ledger_payload.get("entities") or {})
                                .get(str(claim["entity_id"]), {})
                                .get("row")
                            ),
                            missing_reason=x_reason or missing_reason,
                            timing=ledger_payload,
                        )
                    )
                    published_rows.extend(
                        _observation_row(
                            item,
                            str(item.get("state") or "CENSORED"),
                            _result_completion(ledger_payload, now),
                            item.get("request_sha256"),
                            call_occurrence_id=item.get("call_occurrence_id"),
                            missing_reason=(item.get("payload") or {}).get("missing_reason"),
                        )
                        for item in censored_points
                    )
                continue
            if opener is None:
                stop_reason = "DEPENDENCY_MISSING"
                for claim in live:
                    store.insert_due(
                        _due_copy(
                            claim,
                            state="DEPENDENCY_MISSING",
                            request_sha256=request_digest,
                            call_occurrence_id=occurrence,
                            payload={"missing_reason": "TRANSPORT_UNAVAILABLE"},
                        ),
                        clock=now,
                    )
                    published_rows.append(
                        _observation_row(
                            claim,
                            "DEPENDENCY_MISSING",
                            now,
                            request_digest,
                            call_occurrence_id=occurrence,
                            missing_reason="TRANSPORT_UNAVAILABLE",
                        )
                    )
                continue
            blocked = accounts.gate(
                extra_credits=_primitive_credit_cost(accounts, SEARCH),
                now=execution_clock(),
            )
            if blocked:
                stop_reason = blocked
                break
            if holder is None and credential_loader is not None:
                holder = credential_loader()
                credential_reads += 1
            attempt_id = f"ATT-{uuid4().hex[:12].upper()}"
            start_state = store.start_call(
                request_sha256=request_digest,
                call_occurrence_id=occurrence,
                attempt_id=attempt_id,
                primitive_id=SEARCH,
                payload={
                    "url": url,
                    "call_occurrence_id": occurrence,
                    "claim_identity_set": sorted(
                        f'{item["entity_id"]}:{item["point_id"]}:{item["due_at"]}'
                        for item in live
                    ),
                },
                clock=now,
            )
            if start_state != "STARTED":
                terminal = "IN_FLIGHT_CALL_INDETERMINATE"
                for claim in live:
                    store.insert_due(
                        _due_copy(
                            claim,
                            state=terminal,
                            request_sha256=request_digest,
                            call_occurrence_id=occurrence,
                            payload={"missing_reason": terminal},
                        ),
                        clock=now,
                    )
                    published_rows.append(
                        _observation_row(
                            claim,
                            terminal,
                            now,
                            request_digest,
                            call_occurrence_id=occurrence,
                            missing_reason=terminal,
                        )
                    )
                continue
            result = execute_primitive(
                primitive_id=SEARCH,
                primitive_version="1.0",
                method="GET",
                url=url,
                opener=opener,
                clock=execution_clock,
                redact_with=holder,
                expected_entities=[str(item["entity_id"]) for item in live],
                schema_required_keys=SCHEMA_REQUIRED_KEYS.get(SEARCH),
            )
            if result.get("request_sha256") != request_digest:
                raise ObservationSchedulerError("REQUEST_HASH_MISMATCH")
            completion = _result_completion(result, now)
            accounts.note(
                raw_bytes=len(json.dumps(result.get("body"), default=str)),
                credits=_primitive_credit_cost(accounts, SEARCH),
                completed_at=completion,
            )
            provider_calls = accounts.tick_calls
            entity_payload = result.get("entities") or {}
            store.complete_call(
                request_sha256=request_digest,
                call_occurrence_id=occurrence,
                attempt_id=attempt_id,
                payload={
                    "response_sha256": result.get("response_sha256"),
                    "status": result.get("status"),
                    "entities": entity_payload,
                    "request_started_at": result.get("request_started_at"),
                    "response_received_at": result.get("response_received_at"),
                    "first_reliable_available_at": result.get(
                        "first_reliable_available_at"
                    ),
                    "buy_out_amount": None,
                },
                clock=completion,
            )
            for claim in live:
                previously = store.has_prior_observation(
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    entity_id=str(claim["entity_id"]),
                )
                terminal_state, missing_reason = _entity_terminal(
                    result,
                    str(claim["entity_id"]),
                    previously_observed=previously,
                )
                claim["request_sha256"] = request_digest
                claim["call_occurrence_id"] = occurrence
                terminal_state, x_reason, censored_points = _apply_x_phase(
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    claim=claim,
                    result=result,
                    terminal_state=terminal_state,
                    missing_reason=missing_reason,
                    now=completion,
                )
                censored_points.extend(
                    _apply_missingness_policy(
                        store=store,
                        schedule=schedule,
                        claim=claim,
                        terminal_state=terminal_state,
                        now=completion,
                    )
                )
                current_after_x = store.get_due(claim)
                if not (
                    current_after_x is not None
                    and current_after_x.get("state") == "CENSORED_LATE"
                    and terminal_state == "CENSORED_LATE"
                ):
                    store.insert_due(
                        _due_copy(
                            claim,
                            state=terminal_state,
                            request_sha256=request_digest,
                            call_occurrence_id=occurrence,
                            payload={
                                "missing_reason": x_reason
                                or missing_reason
                                or result.get("missing_reason"),
                                "response_sha256": result.get("response_sha256"),
                                "request_started_at": result.get("request_started_at"),
                                "response_received_at": result.get(
                                    "response_received_at"
                                ),
                                "first_reliable_available_at": result.get(
                                    "first_reliable_available_at"
                                ),
                            },
                        ),
                        clock=completion,
                    )
                else:
                    claim = current_after_x
                published_rows.append(
                    _observation_row(
                        claim,
                        terminal_state,
                        completion,
                        request_digest,
                        call_occurrence_id=occurrence,
                        response_payload=(
                            (entity_payload.get(str(claim["entity_id"])) or {}).get("row")
                        ),
                        missing_reason=x_reason or missing_reason,
                        timing=result,
                    )
                )
                published_rows.extend(
                    _observation_row(
                        item,
                        str(item.get("state") or "CENSORED"),
                        completion,
                        item.get("request_sha256"),
                        call_occurrence_id=item.get("call_occurrence_id"),
                        missing_reason=(item.get("payload") or {}).get("missing_reason"),
                    )
                    for item in censored_points
                )
        quote_claims = [
            item for item in claims if str(item["primitive_id"]) != SEARCH
        ]
        quote_claims.sort(
            key=lambda item: 1 if str(item["primitive_id"]) in SELL_PRIMITIVES else 0
        )
        for claim in quote_claims:
            current_due = store.get_due(claim)
            current_due_state = current_due.get("state") if current_due else None
            if current_due_state != "CLAIMED":
                continue
            claim = current_due
            deadline = parse_utc(claim["deadline_at"])
            if now > deadline:
                store.insert_due(
                    _due_copy(
                        claim,
                        state="CENSORED_LATE",
                        payload={"missing_reason": "CENSORED_LATE"},
                    ),
                    clock=now,
                )
                published_rows.append(
                    _observation_row(
                        claim,
                        "CENSORED_LATE",
                        now,
                        claim.get("request_sha256"),
                        missing_reason="CENSORED_LATE",
                    )
                )
                continue
            url_result = _url_for_claim(schedule, claim)
            if url_result is None:
                store.insert_due(
                    _due_copy(
                        claim,
                        state="DEPENDENCY_MISSING",
                        payload={"missing_reason": "DEPENDENCY_MISSING"},
                    ),
                    clock=now,
                )
                published_rows.append(_observation_row(claim, "DEPENDENCY_MISSING", now, None))
                continue
            url, version = url_result
            request_digest = request_sha256(
                method="GET",
                url=url,
                body=None,
                primitive_version=version,
            )
            occurrence = call_occurrence_id(
                schedule_sha256=digest,
                activation_id=activation_id,
                primitive_id=str(claim["primitive_id"]),
                point_id=str(claim["point_id"]),
                due_at=str(claim["due_at"]),
                claim_identity_set=[
                    f'{claim["entity_id"]}:{claim["point_id"]}:{claim["due_at"]}'
                ],
                request_digest=request_digest,
            )
            prior = store.call_state(occurrence)
            if prior == "STARTED":
                store.insert_due(
                    _due_copy(
                        claim,
                        state="IN_FLIGHT_CALL_INDETERMINATE",
                        request_sha256=request_digest,
                        call_occurrence_id=occurrence,
                        payload={"missing_reason": "IN_FLIGHT_CALL_INDETERMINATE"},
                    ),
                    clock=now,
                )
                published_rows.append(
                    _observation_row(
                        claim,
                        "IN_FLIGHT_CALL_INDETERMINATE",
                        now,
                        request_digest,
                        call_occurrence_id=occurrence,
                    )
                )
                continue
            if prior == "COMPLETED":
                ledger_payload = store.call_payload(occurrence) or {}
                previously = store.has_prior_observation(
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    entity_id=str(claim["entity_id"]),
                )
                recovered_state, recovered_reason = _entity_terminal(
                    {
                        "status": ledger_payload.get("status"),
                        "missing_reason": ledger_payload.get("missing_reason"),
                        "entities": ledger_payload.get("entities") or {},
                    },
                    str(claim["entity_id"]),
                    previously_observed=previously,
                )
                recovered_censored = _apply_missingness_policy(
                    store=store,
                    schedule=schedule,
                    claim=claim,
                    terminal_state=recovered_state,
                    now=_result_completion(ledger_payload, now),
                )
                store.insert_due(
                    _due_copy(
                        claim,
                        state=recovered_state,
                        request_sha256=request_digest,
                        call_occurrence_id=occurrence,
                        payload={
                            "missing_reason": recovered_reason
                            or ledger_payload.get("missing_reason")
                            or "RECOVERED_COMPLETED_LEDGER",
                            "response_sha256": ledger_payload.get("response_sha256"),
                            "buy_out_amount": (ledger_payload.get("entities") or {})
                            .get(str(claim["entity_id"]), {})
                            .get("buy_out_amount")
                            or ledger_payload.get("buy_out_amount"),
                        },
                    ),
                    clock=now,
                )
                recovered_buy = _first_non_none(
                    (ledger_payload.get("entities") or {})
                    .get(str(claim["entity_id"]), {})
                    .get("buy_out_amount"),
                    ledger_payload.get("buy_out_amount"),
                )
                if (
                    recovered_state == "OBSERVED"
                    and str(claim["primitive_id"]) in BUY_PRIMITIVES
                    and recovered_buy is not None
                    and str(recovered_buy) != ""
                ):
                    _propagate_buy_out(
                        store,
                        schedule=schedule,
                        activation_id=activation_id,
                        entity_id=str(claim["entity_id"]),
                        buy_out_amount=str(recovered_buy),
                        reverse_primitive_id=REVERSE_FOR_BUY[str(claim["primitive_id"])],
                        now=now,
                    )
                published_rows.append(
                    _observation_row(
                        claim,
                        recovered_state,
                        _result_completion(ledger_payload, now),
                        request_digest,
                        ledger_payload.get("buy_out_amount"),
                        call_occurrence_id=occurrence,
                        response_payload=(
                            (ledger_payload.get("entities") or {})
                            .get(str(claim["entity_id"]), {})
                            .get("row")
                        ),
                        missing_reason=recovered_reason,
                        timing=ledger_payload,
                    )
                )
                published_rows.extend(
                    _observation_row(
                        item,
                        str(item.get("state") or "CENSORED"),
                        _result_completion(ledger_payload, now),
                        item.get("request_sha256"),
                        call_occurrence_id=item.get("call_occurrence_id"),
                        missing_reason=(item.get("payload") or {}).get("missing_reason"),
                        timing=ledger_payload,
                    )
                    for item in recovered_censored
                )
                continue
            if opener is None:
                stop_reason = "DEPENDENCY_MISSING"
                store.insert_due(
                    _due_copy(
                        claim,
                        state="DEPENDENCY_MISSING",
                        request_sha256=request_digest,
                        call_occurrence_id=occurrence,
                        payload={"missing_reason": "TRANSPORT_UNAVAILABLE"},
                    ),
                    clock=now,
                )
                published_rows.append(
                    _observation_row(
                        claim,
                        "DEPENDENCY_MISSING",
                        now,
                        request_digest,
                        call_occurrence_id=occurrence,
                        missing_reason="TRANSPORT_UNAVAILABLE",
                    )
                )
                continue
            blocked = accounts.gate(
                extra_credits=_primitive_credit_cost(
                    accounts, str(claim["primitive_id"])
                ),
                now=execution_clock(),
            )
            if blocked:
                stop_reason = blocked
                break
            if holder is None and credential_loader is not None:
                holder = credential_loader()
                credential_reads += 1
            attempt_id = f"ATT-{uuid4().hex[:12].upper()}"
            start_state = store.start_call(
                request_sha256=request_digest,
                call_occurrence_id=occurrence,
                attempt_id=attempt_id,
                primitive_id=str(claim["primitive_id"]),
                payload={
                    "url": url,
                    "call_occurrence_id": occurrence,
                    "claim_identity_set": [
                        f'{claim["entity_id"]}:{claim["point_id"]}:{claim["due_at"]}'
                    ],
                },
                clock=now,
            )
            if start_state != "STARTED":
                terminal = "IN_FLIGHT_CALL_INDETERMINATE"
                store.insert_due(
                    _due_copy(
                        claim,
                        state=terminal,
                        request_sha256=request_digest,
                        call_occurrence_id=occurrence,
                        payload={"missing_reason": terminal},
                    ),
                    clock=now,
                )
                published_rows.append(
                    _observation_row(
                        claim,
                        terminal,
                        now,
                        request_digest,
                        call_occurrence_id=occurrence,
                        missing_reason=terminal,
                    )
                )
                continue
            result = execute_primitive(
                primitive_id=str(claim["primitive_id"]),
                primitive_version=version,
                method="GET",
                url=url,
                opener=opener,
                clock=execution_clock,
                redact_with=holder,
                expected_entities=[str(claim["entity_id"])],
                schema_required_keys=SCHEMA_REQUIRED_KEYS.get(str(claim["primitive_id"])),
            )
            if result.get("request_sha256") != request_digest:
                raise ObservationSchedulerError("REQUEST_HASH_MISMATCH")
            completion = _result_completion(result, now)
            accounts.note(
                raw_bytes=len(json.dumps(result.get("body"), default=str)),
                credits=_primitive_credit_cost(accounts, str(claim["primitive_id"])),
                completed_at=completion,
            )
            provider_calls = accounts.tick_calls
            buy_out = None
            body = result.get("body")
            if isinstance(body, Mapping):
                buy_out = body.get("outAmount")
            entity_map = result.get("entities") or {
                str(claim["entity_id"]): {
                    "status": result.get("status"),
                    "buy_out_amount": buy_out,
                    "row": body if isinstance(body, Mapping) else None,
                }
            }
            store.complete_call(
                request_sha256=request_digest,
                call_occurrence_id=occurrence,
                attempt_id=attempt_id,
                payload={
                    "response_sha256": result.get("response_sha256"),
                    "status": result.get("status"),
                    "buy_out_amount": buy_out,
                    "entities": entity_map,
                    "request_started_at": result.get("request_started_at"),
                    "response_received_at": result.get("response_received_at"),
                    "first_reliable_available_at": result.get(
                        "first_reliable_available_at"
                    ),
                },
                clock=completion,
            )
            previously = store.has_prior_observation(
                schedule_sha256=digest,
                activation_id=activation_id,
                entity_id=str(claim["entity_id"]),
            )
            terminal_state, missing_reason = _entity_terminal(
                result,
                str(claim["entity_id"]),
                previously_observed=previously,
            )
            claim["request_sha256"] = request_digest
            claim["call_occurrence_id"] = occurrence
            terminal_state, x_reason, x_censored_points = _apply_x_phase(
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                claim=claim,
                result={**result, "entities": entity_map},
                terminal_state=terminal_state,
                missing_reason=missing_reason,
                now=completion,
            )
            current_after_x = store.get_due(claim)
            if not (
                current_after_x is not None
                and current_after_x.get("state") == "CENSORED_LATE"
                and terminal_state == "CENSORED_LATE"
            ):
                store.insert_due(
                    _due_copy(
                        claim,
                        state=terminal_state,
                        request_sha256=request_digest,
                        call_occurrence_id=occurrence,
                        payload={
                            "missing_reason": x_reason or missing_reason or result.get("missing_reason"),
                            "late_seconds": max(
                                0,
                                int((now - parse_utc(claim["due_at"])).total_seconds()),
                            ),
                            "response_sha256": result.get("response_sha256"),
                            "buy_out_amount": buy_out,
                            "request_started_at": result.get("request_started_at"),
                            "response_received_at": result.get("response_received_at"),
                            "first_reliable_available_at": result.get(
                                "first_reliable_available_at"
                            ),
                            "x_evidence": (
                                (store.get_due(claim) or {}).get("payload", {}).get("x_evidence")
                            ),
                        },
                    ),
                    clock=completion,
                )
            else:
                claim = current_after_x
            censored_points = _apply_missingness_policy(
                store=store,
                schedule=schedule,
                claim=claim,
                terminal_state=terminal_state,
                now=completion,
            )
            censored_points.extend(x_censored_points)
            if (
                terminal_state == "OBSERVED"
                and str(claim["primitive_id"]) in BUY_PRIMITIVES
                and buy_out is not None
                and str(buy_out) != ""
            ):
                reverse_id = REVERSE_FOR_BUY[str(claim["primitive_id"])]
                _propagate_buy_out(
                    store,
                    schedule=schedule,
                    activation_id=activation_id,
                    entity_id=str(claim["entity_id"]),
                    buy_out_amount=str(buy_out),
                    reverse_primitive_id=reverse_id,
                    now=now,
                )
                for later in claims:
                    if (
                        later.get("entity_id") == claim["entity_id"]
                        and later.get("primitive_id") == reverse_id
                    ):
                        payload = dict(later.get("payload") or {})
                        payload["buy_out_amount"] = str(buy_out)
                        later["payload"] = payload
            published_rows.append(
                _observation_row(
                    claim,
                    terminal_state,
                    completion,
                    request_digest,
                    buy_out,
                    call_occurrence_id=occurrence,
                    response_payload=(
                        (entity_map.get(str(claim["entity_id"])) or {}).get("row")
                        if isinstance(entity_map, Mapping)
                        else None
                    ),
                    missing_reason=x_reason or missing_reason or result.get("missing_reason"),
                    timing=result,
                )
            )
            published_rows.extend(
                _observation_row(
                    item,
                    str(item.get("state") or "CENSORED"),
                    completion,
                    item.get("request_sha256"),
                    call_occurrence_id=item.get("call_occurrence_id"),
                    missing_reason=(item.get("payload") or {}).get("missing_reason"),
                )
                for item in censored_points
            )
        if stop_reason == "PACE_WAIT":
            for claim in claims:
                if store.due_state(claim) != "CLAIMED":
                    continue
                store.insert_due(
                    _due_copy(
                        claim,
                        state="PENDING",
                        payload={"deferred_reason": "PACE_WAIT"},
                    ),
                    clock=now,
                )
        if stop_reason == "BLOCKED_BUDGET":
            for claim in claims:
                current_state = store.due_state(claim)
                if current_state in {
                    "OBSERVED",
                    "MISSING_TYPED",
                    "DISAPPEARED",
                    "CENSORED",
                    "CENSORED_LATE",
                    "IN_FLIGHT_CALL_INDETERMINATE",
                    "DEPENDENCY_MISSING",
                    "X_POPULATION_INELIGIBLE",
                    "BLOCKED_BUDGET",
                }:
                    continue
                store.insert_due(
                    _due_copy(
                        claim,
                        state="BLOCKED_BUDGET",
                        payload={"missing_reason": "BLOCKED_BUDGET"},
                    ),
                    clock=now,
                )
                published_rows.append(
                    _observation_row(
                        claim,
                        "BLOCKED_BUDGET",
                        now,
                        claim.get("request_sha256"),
                        missing_reason="BLOCKED_BUDGET",
                    )
                )
        members = _member_snapshot(
            store,
            digest=digest,
            activation_id=activation_id,
            now=now,
            registry=registry,
        )
        if members and published_rows:
            publish_observation_batch(
                data_root=data_root,
                root=root,
                schedule=schedule,
                activation_id=activation_id,
                now=now,
                producer_git_sha=producer_git_sha,
                members=members,
                observations=published_rows,
                fault_after=fault_after,
            )
        draining_completion = None
        if state == "DRAINING":
            draining_completion = complete_draining_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=activation_id,
                now=now,
                producer_git_sha=producer_git_sha,
            )
        materialize_pending_observation_snapshots(
            data_root=data_root,
            store=store,
            schedule_sha256=digest,
            activation_id=activation_id,
            now=now,
            producer_git_sha=producer_git_sha,
        )
        store.record_event(
            "TICK",
            {
                "schedule_sha256": digest,
                "provider_calls": provider_calls,
                "credential_reads": credential_reads,
                "claims": len(claims),
            },
            clock=now,
        )
        return {
            "terminal": stop_reason or "TICK_COMPLETE",
            "provider_calls": accounts.tick_calls,
            "credential_reads": credential_reads,
            "claims": len(claims),
            "published": len(published_rows),
            "source_poll_reused": source_poll_reused,
            "activation_state": (
                draining_completion["state"]
                if draining_completion is not None
                else state
            ),
        }
    finally:
        store.release_lease(lease_token)


def _member_snapshot(
    store: ObservationScheduleStore,
    *,
    digest: str,
    activation_id: str,
    now: datetime,
    registry: ObservationPrimitiveRegistry | None = None,
) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    dues = store.due_in_states(
        (
            "PENDING",
            "DUE",
            "CLAIMED",
            "OBSERVED",
            "MISSING_TYPED",
            "DISAPPEARED",
            "CENSORED",
            "CENSORED_LATE",
            "IN_FLIGHT_CALL_INDETERMINATE",
            "DEPENDENCY_MISSING",
            "X_POPULATION_INELIGIBLE",
            "BLOCKED_BUDGET",
        )
    )
    due_by_entity: dict[str, list[dict[str, Any]]] = {}
    for row in dues:
        if row["schedule_sha256"] == digest and row["activation_id"] == activation_id:
            due_by_entity.setdefault(str(row["entity_id"]), []).append(row)
    for candidate in store.list_candidates(schedule_sha256=digest, activation_id=activation_id):
        entity_id = str(candidate["entity_id"])
        payload = candidate.get("payload") or {}
        points = due_by_entity.get(entity_id) or []
        membership_state = str(candidate["state"])
        state_map = {
            "CANDIDATE": "DISCOVERED",
            "NOT_SELECTED_PREDICATE": "PREDICATE_REJECTED",
            "NOT_SELECTED_HASH_SAMPLE": "PREDICATE_REJECTED",
            "NOT_SELECTED_CAPACITY": "CAPACITY_EXCLUDED",
            "ADMITTED": "ADMITTED",
            "SAMPLED_MEMBER": "SAMPLED_MEMBER",
            "ANCHOR_UNKNOWN": "PREDICATE_REJECTED",
            "X_POPULATION_INELIGIBLE": "X_POPULATION_INELIGIBLE",
        }
        membership_state = state_map.get(membership_state, membership_state)
        if membership_state == "X_POPULATION_INELIGIBLE" or str(
            payload.get("x_eligibility_state") or ""
        ) == "X_POPULATION_INELIGIBLE":
            membership_state = "X_POPULATION_INELIGIBLE"
        elif any(item["state"] == "DISAPPEARED" for item in points):
            membership_state = "DISAPPEARED"
        elif any(item["state"] == "MISSING_TYPED" for item in points):
            membership_state = "MISSING_TYPED"
        elif any(item["state"] == "CENSORED_LATE" for item in points):
            membership_state = "CENSORED_LATE"
        elif any(item["state"] == "CENSORED" for item in points):
            membership_state = "CENSORED"
        elif any(
            item["state"] in {"IN_FLIGHT_CALL_INDETERMINATE", "DEPENDENCY_MISSING"}
            for item in points
        ):
            membership_state = "MISSING_TYPED"
        elif any(item["state"] in {"PENDING", "DUE", "CLAIMED"} for item in points):
            membership_state = "SCHEDULED"
        elif any(item["state"] == "OBSERVED" for item in points):
            membership_state = "OBSERVED"
        members.append(
            {
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "entity_id": entity_id,
                "membership_state": membership_state,
                "candidate_state": candidate["state"],
                "authoritative_anchor": payload.get("authoritative_anchor")
                or payload.get("anchor_event_time"),
                "provisional_due": bool(
                    payload.get("provisional_due")
                    or payload.get("provisional_schedule_anchor")
                ),
                "inclusion_probability": payload.get("inclusion_probability"),
                "sampling_seed": payload.get("sampling_seed"),
                "event_time": payload.get("authoritative_anchor")
                or payload.get("anchor_event_time"),
                "first_reliable_available_at": payload.get("discovery_available_at")
                or render_utc(now),
                "field_values": _typed_member_values(
                    payload,
                    now,
                    registry=registry,
                ),
            }
        )
    return members


@lru_cache(maxsize=4)
def _default_value_registry(root: str) -> ObservationPrimitiveRegistry:
    try:
        return load_observation_primitive_registry(Path(root))
    except PrimitiveRegistryError as exc:
        raise ObservationSchedulerError("TYPED_VALUE_REGISTRY_INVALID") from exc


def _value_registry(
    registry: ObservationPrimitiveRegistry | None,
) -> ObservationPrimitiveRegistry:
    return registry or _default_value_registry(str(Path(__file__).resolve().parents[3]))


def _registered_output_fields(
    registry: ObservationPrimitiveRegistry,
    primitive_id: str,
) -> list[tuple[str, str]]:
    try:
        primitive = registry.require_primitive(primitive_id)
        return [
            (
                str(field_id),
                str(registry.require_field(str(field_id))["value_kind"]),
            )
            for field_id in primitive.get("output_field_ids") or []
        ]
    except PrimitiveRegistryError as exc:
        raise ObservationSchedulerError("TYPED_VALUE_REGISTRY_INVALID") from exc


def _typed_member_values(
    payload: Mapping[str, Any],
    now: datetime,
    *,
    registry: ObservationPrimitiveRegistry | None = None,
) -> list[dict[str, Any]]:
    source = payload.get("source_row")
    source_row = source if isinstance(source, Mapping) else {}
    anchor = _first_non_none(
        payload.get("authoritative_anchor"), payload.get("anchor_event_time")
    )
    value_registry = _value_registry(registry)
    fields = _registered_output_fields(value_registry, DISCOVERY)
    result: list[dict[str, Any]] = []
    for field_id, value_kind in fields:
        if field_id == "FIELD-FIRST-POOL-CREATED-AT-001":
            value = anchor
            state = "OBSERVED" if value is not None else "MISSING_TYPED"
            missing_reason = None if value is not None else "FIELD_ABSENT"
        elif field_id == "FIELD-FIRST-SEEN-AT-001":
            value = payload.get("first_seen_at")
            state = "OBSERVED" if value is not None else "MISSING_TYPED"
            missing_reason = None if value is not None else "FIELD_ABSENT"
        elif field_id in TOKENS_V2_FIELD_KINDS:
            value, state, missing_reason = project_tokens_v2_field(source_row, field_id)
        else:
            value = _row_field(source_row, field_id)
            state = "OBSERVED" if value is not None else "MISSING_TYPED"
            missing_reason = None if value is not None else "FIELD_ABSENT"
        result.append(
            {
                "field_id": field_id,
                "value_kind": value_kind,
                "typed_value_or_null": str(value) if value is not None else None,
                "state": state,
                "missing_reason": missing_reason,
                "primitive_id": DISCOVERY,
                "point_id": "MEMBER",
                "event_time": anchor,
                "first_reliable_available_at": payload.get("discovery_available_at")
                or render_utc(now),
                "request_sha256": payload.get("discovery_request_sha256"),
                "call_occurrence_id": payload.get("discovery_call_occurrence_id"),
            }
        )
    return result


def _sanitized_source_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return sanitize_tokens_v2_source_row(row)


def _due_copy(
    claim: Mapping[str, Any],
    *,
    state: str,
    payload: Mapping[str, Any],
    request_sha256: str | None = None,
    call_occurrence_id: str | None = None,
) -> dict[str, Any]:
    merged_payload = dict(claim.get("payload") or {})
    merged_payload.update(dict(payload))
    return {
        "schedule_sha256": claim["schedule_sha256"],
        "activation_id": claim["activation_id"],
        "entity_id": claim["entity_id"],
        "point_id": claim["point_id"],
        "primitive_id": claim["primitive_id"],
        "due_at": claim["due_at"],
        "deadline_at": claim["deadline_at"],
        "state": state,
        "request_sha256": request_sha256,
        "call_occurrence_id": call_occurrence_id or claim.get("call_occurrence_id"),
        "payload": merged_payload,
    }


def _observation_row(
    claim: Mapping[str, Any],
    state: str,
    now: datetime,
    request_digest: str | None,
    buy_out: object | None = None,
    *,
    call_occurrence_id: str | None = None,
    response_payload: Mapping[str, Any] | None = None,
    missing_reason: str | None = None,
    timing: Mapping[str, Any] | None = None,
    registry: ObservationPrimitiveRegistry | None = None,
) -> dict[str, Any]:
    payload = claim.get("payload") or {}
    anchor = payload.get("authoritative_anchor") or payload.get("anchor_event_time")
    provisional = bool(
        payload.get("provisional_due")
        or payload.get("provisional_schedule_anchor")
    )
    if isinstance(anchor, str) and anchor:
        event_time = anchor
    elif provisional:
        event_time = None
    else:
        event_time = claim["due_at"]
    availability = (
        timing.get("first_reliable_available_at")
        if isinstance(timing, Mapping)
        else None
    ) or render_utc(now)
    values = _typed_observation_values(
        claim=claim,
        state=state,
        response_payload=response_payload,
        buy_out=buy_out,
        missing_reason=missing_reason,
        registry=registry,
    )
    for value in values:
        value["event_time"] = event_time
        value["first_reliable_available_at"] = availability
        value["request_sha256"] = request_digest
        value["call_occurrence_id"] = (
            call_occurrence_id or claim.get("call_occurrence_id")
        )
    return {
        "schedule_sha256": claim["schedule_sha256"],
        "activation_id": claim["activation_id"],
        "entity_id": claim["entity_id"],
        "point_id": claim["point_id"],
        "primitive_id": claim["primitive_id"],
        "state": state,
        "event_time": event_time,
        "first_reliable_available_at": availability,
        "request_started_at": (
            timing.get("request_started_at")
            if isinstance(timing, Mapping)
            else None
        ),
        "response_received_at": (
            timing.get("response_received_at")
            if isinstance(timing, Mapping)
            else None
        ),
        "request_sha256": request_digest,
        "call_occurrence_id": call_occurrence_id or claim.get("call_occurrence_id"),
        "buy_out_amount": buy_out,
        "sell_out_amount": (
            response_payload.get("outAmount")
            if isinstance(response_payload, Mapping)
            and str(claim["primitive_id"]) in SELL_PRIMITIVES
            else None
        ),
        "provisional_due": provisional,
        "authoritative_anchor": anchor,
        "missing_reason": missing_reason,
        "field_values": values,
    }


def _typed_observation_values(
    *,
    claim: Mapping[str, Any],
    state: str,
    response_payload: Mapping[str, Any] | None,
    buy_out: object | None,
    missing_reason: str | None,
    registry: ObservationPrimitiveRegistry | None = None,
) -> list[dict[str, Any]]:
    primitive_id = str(claim["primitive_id"])
    fields = _registered_output_fields(_value_registry(registry), primitive_id)
    projection = None
    if isinstance(response_payload, Mapping) and primitive_id in BUY_PRIMITIVES | SELL_PRIMITIVES:
        pointer = None
        payload_pointer = claim.get("payload") if isinstance(claim.get("payload"), Mapping) else {}
        raw_pointer = payload_pointer.get("response_sha256") if isinstance(payload_pointer, Mapping) else None
        if isinstance(raw_pointer, str) and len(raw_pointer) == 64:
            pointer = raw_pointer
        elif response_payload is not None:
            pointer = hash_raw_response(response_payload)
        try:
            projection = project_quote_surface(response_payload, response_sha256=pointer)
        except QuoteSurfaceProjectionError:
            projection = None
            missing_reason = missing_reason or "INVALID_RESPONSE"
    result: list[dict[str, Any]] = []
    for field_id, value_kind in fields:
        value: object | None
        missing_for_field = missing_reason
        typed_state: str | None = None
        if field_id == "FIELD-QUOTE-BUY-OUT-AMOUNT-001":
            value = buy_out
        elif field_id == "FIELD-QUOTE-SELL-OUT-AMOUNT-001":
            value = (
                response_payload.get("outAmount")
                if isinstance(response_payload, Mapping)
                else None
            )
        elif field_id in SURFACE_FIELD_KEYS and projection is not None:
            surface = projection.get(SURFACE_FIELD_KEYS[field_id]) or {}
            status = str(surface.get("status") or "")
            if status == SURFACE_OBSERVED:
                value = surface.get("value")
            else:
                value = None
                missing_for_field = status or "FIELD_ABSENT"
        elif (
            field_id in TOKENS_V2_FIELD_KINDS
            and isinstance(response_payload, Mapping)
        ):
            value, typed_state, typed_missing = project_tokens_v2_field(
                response_payload, field_id
            )
            missing_for_field = typed_missing
        elif isinstance(response_payload, Mapping):
            value = _row_field(response_payload, field_id)
        else:
            value = None
        if typed_state is not None:
            present = typed_state == STATE_OBSERVED and state == "OBSERVED"
            row_state = typed_state if state == "OBSERVED" else (
                state if state != "OBSERVED" else typed_state
            )
            row_missing = None if present else (missing_for_field or "FIELD_ABSENT")
        else:
            present = value is not None and state == "OBSERVED"
            row_state = "OBSERVED" if present else (
                state if state != "OBSERVED" else "MISSING_TYPED"
            )
            row_missing = None if present else (
                missing_for_field or "FIELD_ABSENT"
            )
        result.append(
            {
                "field_id": field_id,
                "value_kind": value_kind,
                "typed_value_or_null": str(value) if present else None,
                "state": row_state,
                "missing_reason": row_missing,
                "primitive_id": primitive_id,
                "point_id": claim["point_id"],
                "event_time": claim.get("event_time"),
                "first_reliable_available_at": claim.get(
                    "first_reliable_available_at"
                ),
                "request_sha256": claim.get("request_sha256"),
                "call_occurrence_id": claim.get("call_occurrence_id"),
            }
        )
    return result


def _url_for_claim(schedule: Mapping[str, Any], claim: Mapping[str, Any]) -> tuple[str, str] | None:
    primitive_id = str(claim["primitive_id"])
    entity_id = str(claim["entity_id"])
    if primitive_id == "PRIM-JUPITER-TOKENS-V2-RECENT-001":
        return RECENT_URL, "1.0"
    if primitive_id == "PRIM-JUPITER-TOKENS-V2-SEARCH-001":
        return search_url([entity_id]), "1.0"
    if primitive_id in QUOTE_AMOUNT:
        return quote_url(
            input_mint=SOL_MINT,
            output_mint=entity_id,
            amount=QUOTE_AMOUNT[primitive_id],
        ), "1.0"
    if primitive_id in SELL_PRIMITIVES:
        payload = claim.get("payload") or {}
        amount = payload.get("buy_out_amount")
        if not amount:
            return None
        return quote_url(input_mint=entity_id, output_mint=SOL_MINT, amount=str(amount)), "1.0"
    raise ObservationSchedulerError("CHANGE_LANE_PRIMITIVE_GAP")


def _propagate_buy_out(
    store: ObservationScheduleStore,
    *,
    schedule: Mapping[str, Any],
    activation_id: str,
    entity_id: str,
    buy_out_amount: str,
    reverse_primitive_id: str,
    now: datetime,
) -> None:
    digest = str(schedule["schedule_sha256"])
    pending = store.due_in_states(("PENDING", "DUE", "CLAIMED"))
    for row in pending:
        if (
            row["schedule_sha256"] == digest
            and row["activation_id"] == activation_id
            and row["entity_id"] == entity_id
            and row["primitive_id"] == reverse_primitive_id
        ):
            store.merge_due_payload(row, {"buy_out_amount": buy_out_amount}, clock=now)


def _admit_candidates(
    *,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    rows: Sequence[Mapping[str, Any]],
    now: datetime,
    accounts: _Accounting,
    discovery_context: Mapping[str, Any] | None = None,
) -> None:
    digest = str(schedule["schedule_sha256"])
    discovery_context = dict(discovery_context or {})
    sampling = schedule["sampling"]
    member_cap = int(sampling["max_members_per_utc_day"])
    candidate_cap = int(sampling["max_candidates_per_utc_day"])
    day_members = int(accounts.day.get("members") or 0)
    day_candidates = int(accounts.day.get("candidates") or 0)
    stops = parse_utc(schedule["activation"]["stops_admitting_at"])
    if now >= stops:
        return
    rollover_cutover: datetime | None = None
    predecessor_rollover = False
    successor_rollover = False
    predecessor_schedule_for_rollover: str | None = None
    predecessor_activation_for_rollover: str | None = None
    for rollover in store.list_rollovers():
        if (
            str(rollover["predecessor_schedule_sha256"]) == digest
            and str(rollover["predecessor_activation_id"]) == activation_id
        ):
            rollover_cutover = parse_utc(str(rollover["cutover_at"]))
            predecessor_rollover = True
            predecessor_schedule_for_rollover = str(
                rollover["predecessor_schedule_sha256"]
            )
            predecessor_activation_for_rollover = str(
                rollover["predecessor_activation_id"]
            )
            if now >= parse_utc(str(rollover["cutover_at"])):
                return
        if (
            str(rollover["successor_schedule_sha256"]) == digest
            and str(rollover["successor_activation_id"]) == activation_id
        ):
            rollover_cutover = parse_utc(str(rollover["cutover_at"]))
            successor_rollover = True
            predecessor_schedule_for_rollover = str(
                rollover["predecessor_schedule_sha256"]
            )
            predecessor_activation_for_rollover = str(
                rollover["predecessor_activation_id"]
            )
            if now < parse_utc(str(rollover["cutover_at"])):
                return
    for row in rows:
        entity_id = str(row.get("id") or row.get("mint") or "")
        if not entity_id:
            continue
        if rollover_cutover is not None:
            candidate_time = parse_first_seen(row) or now
            if predecessor_rollover and candidate_time >= rollover_cutover:
                continue
            if successor_rollover and candidate_time < rollover_cutover:
                continue
        if (
            successor_rollover
            and predecessor_schedule_for_rollover is not None
            and predecessor_activation_for_rollover is not None
            and store.candidate_exists(
                schedule_sha256=predecessor_schedule_for_rollover,
                activation_id=predecessor_activation_for_rollover,
                entity_id=entity_id,
            )
        ):
            continue
        inserted = store.insert_candidate(
            {
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "entity_id": entity_id,
                "state": "CANDIDATE",
                "payload": {
                    "first_seen_at": (
                        str(row["first_seen_at"])
                        if isinstance(row.get("first_seen_at"), str)
                        else render_utc(now)
                    ),
                    "discovery_available_at": discovery_context.get(
                        "first_reliable_available_at"
                    )
                    or render_utc(now),
                    "discovery_request_sha256": discovery_context.get("request_sha256"),
                    "discovery_call_occurrence_id": discovery_context.get(
                        "call_occurrence_id"
                    ),
                    "discovery_request_started_at": discovery_context.get(
                        "request_started_at"
                    ),
                    "discovery_response_received_at": discovery_context.get(
                        "response_received_at"
                    ),
                    "inclusion_probability": sampling["inclusion_probability"],
                    "sampling_seed": sampling["seed"],
                    "source_row": _sanitized_source_row(row),
                },
            },
            clock=now,
        )
        if inserted is False:
            continue
        day_candidates += 1
        accounts.day["candidates"] = day_candidates
        accounts.store.save_accounting(
            schedule_sha256=digest,
            activation_id=activation_id,
            utc_day=accounts.utc_day,
            values=accounts.day,
            clock=now,
        )
        if day_candidates > candidate_cap:
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "NOT_SELECTED_CAPACITY",
                    "payload": {"reason": "MAX_CANDIDATES_PER_UTC_DAY", "discovered": day_candidates},
                },
                clock=now,
            )
            continue
        if not _population_eligible(schedule, row):
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "NOT_SELECTED_PREDICATE",
                    "payload": {"reason": "POPULATION_PREDICATE_FAIL_CLOSED"},
                },
                clock=now,
            )
            continue
        if not _sample_included(
            seed=str(sampling["seed"]),
            entity_id=entity_id,
            schedule_digest=digest,
            probability=str(sampling["inclusion_probability"]),
        ):
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "NOT_SELECTED_HASH_SAMPLE",
                    "payload": {"inclusion_probability": sampling["inclusion_probability"]},
                },
                clock=now,
            )
            continue
        if day_members >= member_cap:
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "NOT_SELECTED_CAPACITY",
                    "payload": {"universe_count": len(rows), "admitted": day_members},
                },
                clock=now,
            )
            continue
        # Discovery may carry a look-alike anchor. It is retained only as a
        # provisional wake-up anchor; the registered SEARCH primitive remains
        # authoritative for the scientific time axis.
        anchor = parse_anchor(row)
        provisional = anchor is not None
        if anchor is None and str(schedule["population"]["scheduling_fallback"]) == "FIRST_SEEN_AT_ONLY":
            seen = parse_first_seen(row)
            if seen is None and isinstance(row.get("first_seen_at"), str) is False:
                seen = now
            if seen is not None:
                anchor = seen
                provisional = True
        if anchor is None:
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "ANCHOR_UNKNOWN",
                    "payload": {"scheduling_fallback": schedule["population"]["scheduling_fallback"]},
                },
                clock=now,
            )
            continue
        day_members += 1
        accounts.day["members"] = day_members
        accounts.store.save_accounting(
            schedule_sha256=digest,
            activation_id=activation_id,
            utc_day=accounts.utc_day,
            values=accounts.day,
            clock=now,
        )
        store.set_candidate_state(
            {
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "entity_id": entity_id,
                "state": "ADMITTED",
                "payload": {
                    "authoritative_anchor": None if provisional else render_utc(anchor),
                    "provisional_schedule_anchor": render_utc(anchor)
                    if provisional
                    else None,
                    "provisional_due": provisional,
                    "provisional_due_at": render_utc(anchor) if provisional else None,
                },
            },
            clock=now,
        )
        _enqueue_points(
            store,
            schedule,
            activation_id,
            entity_id,
            anchor,
            now,
            provisional=provisional,
        )


def _enqueue_points(
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    entity_id: str,
    anchor: datetime,
    now: datetime,
    *,
    provisional: bool = False,
) -> None:
    digest = str(schedule["schedule_sha256"])
    points = [schedule["x_point"], *list(schedule["y_points"])]
    for point in points:
        for bundle_id in point["bundle_ids"]:
            primitive_id = BUNDLE_TO_PRIMITIVE[str(bundle_id)]
            due_at, deadline_at = _due_times(
                anchor,
                int(point["due_offset_seconds"]),
                int(point["allowed_lateness_seconds"]),
            )
            store.insert_due(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "point_id": str(point["point_id"]),
                    "primitive_id": primitive_id,
                    "state": "PENDING",
                    "due_at": due_at,
                    "deadline_at": deadline_at,
                    "payload": {
                        "authoritative_anchor": None if provisional else render_utc(anchor),
                        "provisional_schedule_anchor": render_utc(anchor)
                        if provisional
                        else None,
                        "provisional_due": provisional,
                    },
                },
                clock=now,
            )


def apply_recovery_gap(store: ObservationScheduleStore, *, cutoff: datetime) -> int:
    return store.mark_recovery_gap(cutoff=cutoff)


__all__ = [
    "ObservationSchedulerError",
    "apply_recovery_gap",
    "poll_slot_id",
    "tick_once",
]
