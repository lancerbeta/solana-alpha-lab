"""Generic research-to-paper plane: StrategyVersion configs in, bot and
position lifecycle out. Owns no scientific truth and never produces
REAL_FILL.

v1.0 commissioning path retains declarative signal_rule evaluation.
v1.1 candidate path consumes already-frozen SignalDecision / ExitDecision
and never inspects scientific feature names.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterator, Mapping
from uuid import uuid4

from solana_alpha_lab.factory.strategy_runtime import (
    PaperPlaneError,
    canonical_spec_sha256,
    load_strategy_version,
    normalize_strategy,
    position_id_for_signal_decision,
    validate_exit_decision,
    validate_signal_decision,
)

SIGNAL_MAX_CLOCK_SKEW_SECONDS = 2

# Re-export for legacy callers/tests.
__all__ = [
    "PaperPlaneError",
    "PaperPlaneStore",
    "accept_exit_decision",
    "accept_signal_decision",
    "accept_signal_decision_outcome",
    "load_strategy_version",
    "modeled_unrealized_mark",
    "observe_shadow",
    "run_commissioning",
    "run_shadow_tick",
    "signal_kind_for",
    "PRE_ATTEMPT_STATES",
    "IN_FLIGHT_STATES",
    "OPERATOR_SETTLED_STATES",
    "DRAIN_CLEARED_STATES",
    "DEFINITIVE_NON_FILL_REASONS",
    "CANCEL_REASONS",
]


def _identity_fields(source: Mapping[str, Any]) -> dict[str, Any]:
    version = source.get("strategy_version") or source.get("strategy_version_label")
    payload: dict[str, Any] = {}
    for key in (
        "signal_decision_id",
        "strategy_id",
        "activation_epoch_id",
        "mint",
        "action",
        "reason_code",
        "decision_at",
    ):
        value = source.get(key)
        if value not in {None, ""}:
            payload[key] = value
    if version not in {None, ""}:
        payload["strategy_version"] = version
    return payload

SIGNAL_KINDS = frozenset(
    {
        "NO_SIGNAL",
        "NO_ROUTE",
        "QUOTE_UNAVAILABLE",
        "UNKNOWN",
        "SIMULATED_FILL",
        "SHADOW_EXECUTABLE",
        "REAL_FILL",
    }
)
POSITION_STATES = (
    "WATCHED",
    "SIGNALLED",
    "INTENT_CREATED",
    "ATTEMPTING",
    "OPEN",
    "PARTIAL",
    "UNKNOWN",
    "EXIT_REQUIRED",
    "EXITING",
    "CLOSED",
    "UNRESOLVED",
    "RECONCILED",
    "CANCELLED",
)
TRANSITIONS: dict[str, set[str]] = {
    "WATCHED": {"SIGNALLED", "CANCELLED"},
    "SIGNALLED": {"INTENT_CREATED", "CANCELLED"},
    "INTENT_CREATED": {"ATTEMPTING", "CANCELLED"},
    "ATTEMPTING": {"OPEN", "PARTIAL", "UNKNOWN", "UNRESOLVED", "CANCELLED"},
    "OPEN": {"EXIT_REQUIRED", "EXITING"},
    "PARTIAL": {"EXIT_REQUIRED", "EXITING"},
    "UNKNOWN": {"OPEN", "PARTIAL", "CANCELLED", "EXIT_REQUIRED", "EXITING", "UNRESOLVED", "RECONCILED"},
    "EXIT_REQUIRED": {"EXITING", "CANCELLED"},
    "EXITING": {"CLOSED", "UNRESOLVED"},
    "CLOSED": {"RECONCILED"},
    "UNRESOLVED": {"RECONCILED"},
    "RECONCILED": set(),
    "CANCELLED": set(),
}
PRE_ATTEMPT_STATES = frozenset({"WATCHED", "SIGNALLED", "INTENT_CREATED"})
IN_FLIGHT_STATES = frozenset({"ATTEMPTING", "UNKNOWN"})
OPERATOR_SETTLED_STATES = frozenset({"CLOSED", "RECONCILED", "CANCELLED"})
DRAIN_CLEARED_STATES = frozenset({"RECONCILED", "CANCELLED"})
CLOSING_STATES = frozenset({"CLOSED", "RECONCILED", "CANCELLED"})
DEFINITIVE_NON_FILL_REASONS = frozenset(
    {"REJECTED_BEFORE_SEND", "DROPPED_OR_EXPIRED_NOT_PROCESSED"}
)
CANCEL_REASONS = frozenset(
    {
        "OPERATOR_CANCEL",
        "OPERATOR_CLOSE_ALL",
        "OPERATOR_STOP",
        "ENTRIES_PAUSED",
        "NEW_ENTRIES_DISABLED",
        "RUNTIME_POLICY_INVALID",
        "BOT_DRAINING",
        "BOT_STOPPED",
        "SIGNAL_EXPIRED",
        "OPERATING_SAFETY_VETO",
    }
) | DEFINITIVE_NON_FILL_REASONS
FORBIDDEN_SIGNAL_KINDS = frozenset({"REAL_FILL"})
OPEN_RISK_STATES = frozenset(
    {"WATCHED", "SIGNALLED", "INTENT_CREATED", "ATTEMPTING", "OPEN", "PARTIAL", "UNKNOWN"}
)
# A query/index prefilter only. The policy owner still validates each candidate.
# Exact zero strings are intentionally conservative; unusual representations
# remain candidates rather than acquiring a guessed release proof.
_KNOWN_FLAT_SQL = """state='RECONCILED' AND exit_notional_usd_dec IS NOT NULL
    AND pnl_evidence_class IS NOT NULL
    AND pnl_evidence_class IN ('PAPER_RECONCILED_MODEL','SHADOW_RECONCILED_QUOTE_MODEL')
    AND qty_dec IS NOT NULL AND json_valid(qty_dec) AND CAST(qty_dec AS REAL)>0
    AND (remaining_qty_dec IS NULL OR (
        remaining_qty_dec IN ('0','0.0','0.00')
        AND remaining_cost_basis_usd_dec IS NOT NULL AND remaining_cost_basis_usd_dec IN ('0','0.0','0.00')
        AND remaining_entry_fee_usd_dec IS NOT NULL AND remaining_entry_fee_usd_dec IN ('0','0.0','0.00')))"""
_KNOWN_RELEASED_SQL = f"""({_KNOWN_FLAT_SQL}) OR (state='CANCELLED'
    AND qty_dec IS NULL AND entry_price_dec IS NULL AND remaining_qty_dec IS NOT NULL AND remaining_qty_dec IN ('0','0.0','0.00')
    AND remaining_cost_basis_usd_dec IS NOT NULL AND remaining_cost_basis_usd_dec IN ('0','0.0','0.00')
    AND remaining_entry_fee_usd_dec IS NOT NULL AND remaining_entry_fee_usd_dec IN ('0','0.0','0.00'))"""
_OBLIGATION_CANDIDATE_SQL = f"NOT ({_KNOWN_RELEASED_SQL})"


def modeled_final_witness_valid(attempt: Mapping[str, Any], final: Mapping[str, Any] | None,
                                accepted: Mapping[str, Any], *, mode: str,
                                legacy_original_quantity: Any = None,
                                original_position: Mapping[str, Any] | None = None) -> bool:
    """Validate original provenance; a missing final validates an observation only."""
    try:
        body, terminal, payload = attempt["payload"], final["payload"] if final is not None else {}, accepted["payload"]
        if not all(isinstance(value, Mapping) for value in (body, terminal, payload)):
            return False
        result = payload.get("result")
        if not isinstance(result, Mapping):
            return False
        allowed = {"attempt_id", "result_id", "outcome", "observed_at", "unit_price_usd", "filled_notional_usd", "chargeable_cost_usd"}
        if result.get("schema_version") == "1.1":
            allowed |= {"schema_version", "quantity_filled", "quantity_sold", "quantity_unit", "remaining_quantity", "fee_semantics"}
        if set(result) - allowed or set(payload) != {"result", "evidence_class", "chargeable_cost_status"}:
            return False
        identity = {key: body[key] for key in ("position_id", "side", "mode", "attempt_key")}
        aid = "ATTEMPT-" + canonical_spec_sha256(identity).upper()
        rid = "RESULT-" + canonical_spec_sha256({"result_id": result["result_id"]}).upper()
        outcome = result["outcome"]
        if (mode not in {"PAPER", "SHADOW"} or body["mode"] != mode or body["side"] not in {"ENTRY", "EXIT"}
            or attempt["event_type"] != "MODELED_ATTEMPT_STARTED" or attempt["event_id"] != aid or body["attempt_id"] != aid
            or accepted["event_type"] != "MODELED_RESULT_ACCEPTED" or accepted["event_id"] != rid
            or result["attempt_id"] != aid
            or outcome not in {"NO_ROUTE", "REJECTED_BEFORE_SEND", "DROPPED_OR_EXPIRED_NOT_PROCESSED", "LANDED_FAILED", "LANDED_SUCCESS", "PARTIAL", "UNKNOWN_REQUIRES_RECONCILIATION"}
            or any(event["position_id"] != body["position_id"] or event["bot_instance_id"] != attempt["bot_instance_id"]
                for event in ((final, accepted) if final is not None else (accepted,)))
            or attempt["position_id"] != body["position_id"]
            or payload.get("evidence_class") != body["evidence_class"]
            or body["evidence_class"] != ("PAPER_MODEL" if mode == "PAPER" else "SHADOW_QUOTE_MODEL")
            or not isinstance(result["result_id"], str) or not 0 < len(result["result_id"]) <= 120
            or attempt["created_at"] != body["as_of"] or accepted["created_at"] != result["observed_at"]
            or _parse_utc(result["observed_at"]) < _parse_utc(body["as_of"])):
            return False
        version = result.get("schema_version", "1.0")
        if version not in {"1.0", "1.1"}:
            return False
        if final is not None and (outcome == "UNKNOWN_REQUIRES_RECONCILIATION"
                or final["event_type"] != "MODELED_ATTEMPT_FINAL" or final["event_id"] != "FINAL-" + aid
                or final["created_at"] != result["observed_at"]
                or terminal != {"outcome": outcome, "result_event_id": rid,
                    **({"schema_version": "1.1"} if version == "1.1" else {})}):
            return False
        cost = result.get("chargeable_cost_usd")
        if payload.get("chargeable_cost_status") != ("KNOWN" if cost is not None else "UNKNOWN"):
            return False
        if cost is not None:
            _positive_model_decimal(cost, "MODELED_RESULT_COST_INVALID", allow_zero=True)
        positive = outcome in {"LANDED_SUCCESS", "PARTIAL"}
        if not positive:
            return all(result.get(key) is None for key in ("unit_price_usd", "filled_notional_usd", "quantity_filled", "quantity_sold", "remaining_quantity"))
        price = _positive_model_decimal(result.get("unit_price_usd"), "MODELED_FILL_DETAILS_INVALID")
        if body["side"] == "ENTRY":
            notional = _positive_model_decimal(result.get("filled_notional_usd"), "MODELED_FILL_DETAILS_INVALID")
            if original_position is not None:
                original_qty = _positive_model_decimal(original_position.get("qty_dec"), "MODELED_QUANTITY_INVALID")
                admitted = _positive_model_decimal(original_position.get("admitted_entry_notional_usd_dec"), "MODELED_FILL_DETAILS_INVALID")
                if (price != _positive_model_decimal(original_position.get("entry_price_dec"), "MODELED_FILL_DETAILS_INVALID")
                    or notional != _positive_model_decimal(original_position.get("entered_notional_usd_dec"), "MODELED_FILL_DETAILS_INVALID")
                    or notional > admitted or (outcome == "PARTIAL") != (notional < admitted)):
                    return False
                quantity = (_positive_model_decimal(result.get("quantity_filled"), "MODELED_QUANTITY_INVALID") if version == "1.1"
                    else (notional / price).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))
                if quantity != original_qty or version == "1.1" and result.get("fee_semantics") != original_position.get("entry_fee_semantics"):
                    return False
            if version == "1.0" and legacy_original_quantity is not None:
                original = _positive_model_decimal(legacy_original_quantity, "MODELED_QUANTITY_INVALID")
                if (notional / price).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP) != original:
                    return False
        if version == "1.1":
            if result.get("quantity_unit") != "TOKEN_UNITS" or result.get("fee_semantics") not in {"SEPARATE_MODELED_FEE", "INCLUDED_IN_UNIT_PRICE"}:
                return False
            quantity = _positive_model_decimal(result.get("quantity_filled" if body["side"] == "ENTRY" else "quantity_sold"), "MODELED_QUANTITY_INVALID")
            if body["side"] == "ENTRY":
                if "quantity_sold" in result or "remaining_quantity" in result:
                    return False
                if (price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != notional.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
                    return False
            if body["side"] == "EXIT":
                if "quantity_filled" in result or "filled_notional_usd" in result:
                    return False
                remainder = _positive_model_decimal(result.get("remaining_quantity"), "MODELED_QUANTITY_INVALID", allow_zero=True)
                if body.get("remaining_quantity") is None:
                    # v1.0 entry has no quantity reservation in its first EXIT
                    # attempt; its retained immutable entry quantity is the bound.
                    if "quantity_unit" in body:
                        return False
                    original = _positive_model_decimal(legacy_original_quantity, "MODELED_QUANTITY_INVALID")
                else:
                    if body.get("quantity_unit") != "TOKEN_UNITS":
                        return False
                    original = _positive_model_decimal(body["remaining_quantity"], "MODELED_QUANTITY_INVALID")
                if quantity + remainder != original or (outcome == "PARTIAL") != (remainder > 0):
                    return False
        elif body["side"] == "EXIT" and (outcome != "LANDED_SUCCESS" or result.get("filled_notional_usd") is not None):
            return False
        return True
    except (KeyError, TypeError, ValueError, ArithmeticError, PaperPlaneError):
        return False


def assert_quantity_inventory_witness(store: PaperPlaneStore, position: Mapping[str, Any], *,
                                      pending_attempt_id: str | None = None,
                                      allow_pending: bool = False, force_quantity: bool = False) -> None:
    """A mutable remainder is never authority for the next quantity EXIT.

    Fold only this position's existing original final/results and quantity legs.
    Legacy execution without quantity accounting keeps its released payloads.
    The caller supplies its read snapshot or immediate claim/result transaction.
    """
    events = store.filtered_execution_events(position_ids=[position["position_id"]])
    quantitative = force_quantity or position.get("entry_fee_semantics") is not None or any(
        event["event_type"] == "MODELED_EXIT_QUANTITY_LEG"
        or event["event_type"] == "MODELED_ATTEMPT_FINAL" and isinstance(event["payload"], Mapping)
           and event["payload"].get("schema_version") == "1.1"
        or event["event_type"] == "MODELED_RESULT_ACCEPTED" and isinstance(event["payload"], Mapping)
           and isinstance(event["payload"].get("result"), Mapping)
           and event["payload"]["result"].get("schema_version") == "1.1" for event in events)
    if not quantitative:
        return
    try:
        pid, bot = position["position_id"], position["bot_instance_id"]
        mode = store.get_bot(bot)["mode"]
        starts = [event for event in events if event["event_type"] == "MODELED_ATTEMPT_STARTED"]
        attempts = {event["event_id"]: event for event in starts}
        finals = {event["event_id"]: event for event in events if event["event_type"] == "MODELED_ATTEMPT_FINAL"}
        observations = {event["event_id"]: event for event in events if event["event_type"] == "MODELED_RESULT_ACCEPTED"}
        original = _positive_model_decimal(position["qty_dec"], "EXIT_INVENTORY_WITNESS_CONFLICT")
        legacy = original if position.get("entry_fee_semantics") is None else None
        for event in observations.values():
            attempt = attempts.get(event["payload"]["result"]["attempt_id"])
            if attempt is None or not modeled_final_witness_valid(attempt, None, event, mode=mode,
                    legacy_original_quantity=legacy, original_position=position):
                raise ValueError()
        if any(event["event_id"].removeprefix("FINAL-") not in attempts for event in finals.values()):
            raise ValueError()
        entry = [event for event in starts if event["payload"]["side"] == "ENTRY"]
        if len(entry) != 1:
            raise ValueError()
        terminal = finals["FINAL-" + entry[0]["event_id"]]
        accepted = observations[terminal["payload"]["result_event_id"]]
        if not modeled_final_witness_valid(entry[0], terminal, accepted, mode=mode,
                legacy_original_quantity=legacy, original_position=position):
            raise ValueError()
        filled = accepted["payload"]["result"]
        if filled["outcome"] not in {"LANDED_SUCCESS", "PARTIAL"}:
            raise ValueError()
        notional = _positive_model_decimal(filled["filled_notional_usd"], "EXIT_INVENTORY_WITNESS_CONFLICT")
        if (Decimal(position["entered_notional_usd_dec"]) != notional
            or Decimal(position["entry_price_dec"]) != Decimal(filled["unit_price_usd"])):
            raise ValueError()
        fee_bps = _bound_entry_fee_bps(position, int(position["fee_bps"]))
        entry_fee = (Decimal("0") if filled.get("fee_semantics") == "INCLUDED_IN_UNIT_PRICE" else
                     (notional * Decimal(fee_bps) / Decimal("10000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        native_entry = [event for event in events if event["event_type"] in {"PAPER_SIMULATION_OBSERVED", "SHADOW_EXECUTABLE_OBSERVED"}
                        and event["payload"].get("side") == "ENTRY"]
        if len(native_entry) != 1 or native_entry[0]["bot_instance_id"] != bot or native_entry[0]["position_id"] != pid:
            raise ValueError()
        source_entry = native_entry[0]["payload"]
        for key, value in (("qty_dec", original), ("entry_price_dec", Decimal(filled["unit_price_usd"])),
                           ("entry_gross_notional_usd_dec", notional), ("entry_fee_usd_dec", entry_fee)):
            if Decimal(source_entry[key]) != value:
                raise ValueError()
        if Decimal(position["entry_fee_usd_dec"]) != entry_fee or source_entry["mode"] != mode:
            raise ValueError()
        remainder, proceeds, exit_fees, allocated_fee = original, Decimal("0"), Decimal("0"), Decimal("0")
        gross, net = Decimal("0"), Decimal("0")
        legs = {event["event_id"]: event for event in events if event["event_type"] == "MODELED_EXIT_QUANTITY_LEG"}
        consumed = set()
        for attempt in starts:
            body = attempt["payload"]
            if body["side"] != "EXIT":
                continue
            if body.get("remaining_quantity") is not None:
                if Decimal(body["remaining_quantity"]) != remainder or body.get("quantity_unit") != "TOKEN_UNITS":
                    raise ValueError()
            elif legacy is None or remainder != original:
                raise ValueError()
            final = finals.get("FINAL-" + attempt["event_id"])
            if final is None:
                if not (allow_pending or pending_attempt_id == attempt["event_id"]):
                    raise ValueError()
                if any(event["payload"]["result"]["outcome"] != "UNKNOWN_REQUIRES_RECONCILIATION"
                       for event in observations.values() if event["payload"]["result"]["attempt_id"] == attempt["event_id"]):
                    raise ValueError()
                continue
            accepted = observations[final["payload"]["result_event_id"]]
            if not modeled_final_witness_valid(attempt, final, accepted, mode=mode,
                    legacy_original_quantity=legacy, original_position=position):
                raise ValueError()
            result = accepted["payload"]["result"]
            if result["outcome"] not in {"LANDED_SUCCESS", "PARTIAL"}:
                continue
            modern = result.get("schema_version") == "1.1"
            sold = Decimal(result["quantity_sold"]) if modern else remainder
            remaining = Decimal(result["remaining_quantity"]) if modern else Decimal("0")
            if sold + remaining != remainder:
                raise ValueError()
            semantics = result.get("fee_semantics", "SEPARATE_MODELED_FEE")
            price = Decimal(result["unit_price_usd"])
            leg_proceeds = (price * sold).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            leg_fee = (Decimal("0") if semantics == "INCLUDED_IN_UNIT_PRICE" else
                       (leg_proceeds * Decimal(fee_bps) / Decimal("10000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            proceeds += leg_proceeds
            exit_fees += leg_fee
            cost = notional * remaining / original
            next_fee = (entry_fee * (original - remaining) / original).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            next_gross = (proceeds - (notional - cost)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            next_net = (next_gross - next_fee - exit_fees).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if modern:
                leg = legs.get("LEG-" + accepted["event_id"])
            else:
                matches = [event for event in legs.values() if event["event_id"] not in consumed
                    and event["payload"]["request"]["quantity_sold"] == format(sold, "f")
                    and event["payload"]["request"]["remaining_quantity"] == format(remaining, "f")]
                leg = matches[0] if len(matches) == 1 else None
            if leg is None or leg["position_id"] != pid or leg["bot_instance_id"] != bot:
                raise ValueError()
            clock = result["observed_at"] if modern else leg["created_at"]
            expected = {"schema_version": "1.1", "request": {"quantity_sold": format(sold, "f"),
                "remaining_quantity": format(remaining, "f"), "unit_price_usd": format(price, "f"),
                "fee_semantics": semantics, "observed_at": clock, "mode": mode}, "quantity_unit": "TOKEN_UNITS",
                "proceeds_usd": format(leg_proceeds, "f"), "exit_fee_usd": format(leg_fee, "f"),
                "allocated_entry_fee_total_usd": format(next_fee, "f"), "allocated_entry_fee_usd": format(next_fee - allocated_fee, "f"),
                "realized_gross_pnl_usd": format(next_gross - gross, "f"), "realized_trade_net_usd": format(next_net - net, "f"),
                "remaining_cost_basis_usd": format(cost, "f"), "realized_trade_net_total_usd": format(next_net, "f"), "evidence_class": mode + "_MODEL"}
            if leg["created_at"] != clock or leg["payload"] != expected:
                raise ValueError()
            consumed.add(leg["event_id"])
            remainder, allocated_fee, gross, net = remaining, next_fee, next_gross, next_net
        if consumed != set(legs):
            raise ValueError()
        if position.get("remaining_qty_dec") is not None:
            for key, value in (("remaining_qty_dec", remainder), ("remaining_cost_basis_usd_dec", notional * remainder / original),
                               ("remaining_entry_fee_usd_dec", entry_fee - allocated_fee)):
                if Decimal(position[key]) != value:
                    raise ValueError()
        elif position.get("entry_fee_semantics") is not None or consumed:
            raise ValueError()
        for key, value in (("exit_notional_usd_dec", proceeds), ("exit_fee_usd_dec", exit_fees),
                           ("realized_gross_pnl_usd_dec", gross), ("realized_net_pnl_usd_dec", net)):
            if (position.get(key) is None and consumed) or position.get(key) is not None and Decimal(position[key]) != value:
                raise ValueError()
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, PaperPlaneError):
        raise PaperPlaneError("EXIT_INVENTORY_WITNESS_CONFLICT") from None


def _sql_modeled_final_witness(*values: Any) -> int:
    try:
        keys = ("event_type", "event_id", "bot_instance_id", "position_id", "created_at", "payload")
        events = [dict(zip(keys, values[offset:offset + 6])) for offset in (0, 6, 12)]
        for offset, event in enumerate(events):
            if offset == 1 and event["event_id"] is None:
                events[offset] = None
            else:
                event["payload"] = json.loads(event["payload"])
        return int(modeled_final_witness_valid(*events, mode=values[18], legacy_original_quantity=values[19],
            original_position=json.loads(values[20])))
    except (TypeError, ValueError):
        return 0


def unattempted_cancel_witness_valid(position: Mapping[str, Any], event: Mapping[str, Any]) -> bool:
    """Only an original cancellation from a pre-attempt state proves no send."""
    try:
        payload = event["payload"]
        return (isinstance(payload, Mapping) and event["event_type"] == "ENTRY_INTENT_CANCELLED"
            and event["position_id"] == position["position_id"] and event["bot_instance_id"] == position["bot_instance_id"]
            and isinstance(payload.get("from_state"), str) and payload["from_state"] in PRE_ATTEMPT_STATES
            and isinstance(payload.get("cancel_reason_code"), str) and payload["cancel_reason_code"] in CANCEL_REASONS
            and payload["cancel_reason_code"] == position.get("cancel_reason_code"))
    except (KeyError, TypeError, ValueError):
        return False


def _sql_unattempted_cancel_witness(pid: Any, bot: Any, reason: Any, event_type: Any,
                                  event_bot: Any, event_pid: Any, raw: Any) -> int:
    try:
        return int(unattempted_cancel_witness_valid(
            {"position_id": pid, "bot_instance_id": bot, "cancel_reason_code": reason},
            {"event_type": event_type, "bot_instance_id": event_bot, "position_id": event_pid, "payload": json.loads(raw)}))
    except (TypeError, ValueError):
        return 0


_LEGACY_QUANTITY_SQL = """CASE WHEN positions.entry_fee_semantics IS NULL AND EXISTS(
    SELECT 1 FROM execution_events la JOIN execution_events lr ON la.event_id=
        json_extract(CASE WHEN json_valid(lr.payload_json) THEN lr.payload_json ELSE '{}' END,'$.result.attempt_id')
    WHERE la.position_id=positions.position_id AND la.event_type='MODELED_ATTEMPT_STARTED'
    AND json_extract(CASE WHEN json_valid(la.payload_json) THEN la.payload_json ELSE '{}' END,'$.side')='ENTRY'
    AND lr.position_id=positions.position_id AND lr.event_type='MODELED_RESULT_ACCEPTED'
    AND json_extract(CASE WHEN json_valid(lr.payload_json) THEN lr.payload_json ELSE '{}' END,'$.result.schema_version') IS NULL
    AND json_extract(CASE WHEN json_valid(lr.payload_json) THEN lr.payload_json ELSE '{}' END,'$.result.outcome') IN ('LANDED_SUCCESS','PARTIAL'))
    THEN positions.qty_dec ELSE NULL END"""
_ORIGINAL_ENTRY_SQL = """json_object('qty_dec',positions.qty_dec,'entry_price_dec',positions.entry_price_dec,
    'entered_notional_usd_dec',positions.entered_notional_usd_dec,'entry_fee_semantics',positions.entry_fee_semantics,
    'admitted_entry_notional_usd_dec',positions.admitted_entry_notional_usd_dec)"""
_FINAL_WITNESS_JOIN_SQL = f"""execution_events f JOIN execution_events r ON r.event_id=
    json_extract(CASE WHEN json_valid(f.payload_json) THEN f.payload_json ELSE '{{}}' END,'$.result_event_id')
    WHERE f.event_id='FINAL-'||a.event_id AND a.bot_instance_id=positions.bot_instance_id
    AND modeled_final_witness_v1(a.event_type,a.event_id,a.bot_instance_id,a.position_id,a.created_at,a.payload_json,
        f.event_type,f.event_id,f.bot_instance_id,f.position_id,f.created_at,f.payload_json,
        r.event_type,r.event_id,r.bot_instance_id,r.position_id,r.created_at,r.payload_json,bot_instances.mode,
        {_LEGACY_QUANTITY_SQL},{_ORIGINAL_ENTRY_SQL})=1"""
_ALL_ATTEMPTS_FINAL_SQL = f"""NOT EXISTS(SELECT 1 FROM execution_events a
    WHERE a.position_id=positions.position_id AND a.event_type='MODELED_ATTEMPT_STARTED'
    AND NOT EXISTS(SELECT 1 FROM {_FINAL_WITNESS_JOIN_SQL}))"""
_NO_MODELED_EVENTS_SQL = """NOT EXISTS(SELECT 1 FROM execution_events e WHERE e.position_id=positions.position_id
    AND e.event_type IN ('MODELED_ATTEMPT_STARTED','MODELED_ATTEMPT_FINAL','MODELED_RESULT_ACCEPTED'))"""
_UNATTEMPTED_CANCEL_PROOF_SQL = f"""({_NO_MODELED_EVENTS_SQL}) AND EXISTS(SELECT 1 FROM execution_events c
    WHERE c.position_id=positions.position_id AND c.event_type='ENTRY_INTENT_CANCELLED'
    AND unattempted_cancel_witness_v1(positions.position_id,positions.bot_instance_id,positions.cancel_reason_code,
        c.event_type,c.bot_instance_id,c.position_id,c.payload_json)=1)"""
_NO_ORPHAN_MODELED_EVENTS_SQL = f"""NOT EXISTS(SELECT 1 FROM execution_events e
    WHERE e.position_id=positions.position_id AND (
        (e.event_type='MODELED_ATTEMPT_FINAL' AND NOT EXISTS(SELECT 1 FROM execution_events a
            WHERE a.position_id=positions.position_id AND e.event_id='FINAL-'||a.event_id
            AND a.event_type='MODELED_ATTEMPT_STARTED' AND EXISTS(SELECT 1 FROM {_FINAL_WITNESS_JOIN_SQL})))
        OR (e.event_type='MODELED_RESULT_ACCEPTED' AND NOT EXISTS(SELECT 1 FROM execution_events a
            WHERE a.event_id=json_extract(CASE WHEN json_valid(e.payload_json) THEN e.payload_json ELSE '{{}}' END,'$.result.attempt_id')
            AND a.position_id=positions.position_id AND a.bot_instance_id=positions.bot_instance_id
            AND modeled_final_witness_v1(a.event_type,a.event_id,a.bot_instance_id,a.position_id,a.created_at,a.payload_json,
                NULL,NULL,NULL,NULL,NULL,NULL,e.event_type,e.event_id,e.bot_instance_id,e.position_id,e.created_at,e.payload_json,bot_instances.mode,
                {_LEGACY_QUANTITY_SQL},{_ORIGINAL_ENTRY_SQL})=1))))"""
_PROVED_RELEASE_SQL = f"""({_ALL_ATTEMPTS_FINAL_SQL}) AND ({_NO_ORPHAN_MODELED_EVENTS_SQL}) AND (
    (state='CANCELLED' AND (EXISTS(SELECT 1 FROM execution_events a
        WHERE a.position_id=positions.position_id AND a.event_type='MODELED_ATTEMPT_STARTED'
        AND json_extract(CASE WHEN json_valid(a.payload_json) THEN a.payload_json ELSE '{{}}' END,'$.side')='ENTRY'
        AND EXISTS(SELECT 1 FROM {_FINAL_WITNESS_JOIN_SQL}
            AND json_extract(CASE WHEN json_valid(f.payload_json) THEN f.payload_json ELSE '{{}}' END,'$.outcome') IN ('NO_ROUTE','REJECTED_BEFORE_SEND','DROPPED_OR_EXPIRED_NOT_PROCESSED','LANDED_FAILED')))
        OR ({_UNATTEMPTED_CANCEL_PROOF_SQL})))
    OR (state='RECONCILED' AND (EXISTS(SELECT 1 FROM execution_events a
        WHERE a.position_id=positions.position_id AND a.event_type='MODELED_ATTEMPT_STARTED'
        AND json_extract(CASE WHEN json_valid(a.payload_json) THEN a.payload_json ELSE '{{}}' END,'$.side')='EXIT'
        AND EXISTS(SELECT 1 FROM {_FINAL_WITNESS_JOIN_SQL} AND json_extract(CASE WHEN json_valid(f.payload_json) THEN f.payload_json ELSE '{{}}' END,'$.outcome')='LANDED_SUCCESS')
        AND (COALESCE(ordinary_operating,0)=0 OR EXISTS(SELECT 1 FROM execution_events a
            WHERE a.position_id=positions.position_id AND a.event_type='MODELED_ATTEMPT_STARTED'
            AND json_extract(CASE WHEN json_valid(a.payload_json) THEN a.payload_json ELSE '{{}}' END,'$.side')='ENTRY'
            AND EXISTS(SELECT 1 FROM {_FINAL_WITNESS_JOIN_SQL}
                AND json_extract(CASE WHEN json_valid(f.payload_json) THEN f.payload_json ELSE '{{}}' END,'$.outcome') IN ('LANDED_SUCCESS','PARTIAL')))))
        OR (COALESCE(ordinary_operating,0)=0 AND {_NO_MODELED_EVENTS_SQL}))))"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _positive_model_decimal(value: Any, code: str, *, allow_zero: bool = False) -> Decimal:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or not allow_zero and amount == 0:
            raise ValueError()
    except (ValueError, ArithmeticError):
        raise PaperPlaneError(code) from None
    return amount


def modeled_unrealized_mark(
    *,
    mark_price: Decimal,
    qty: Decimal,
    entered_notional: Decimal,
    entry_fee: Decimal,
    fee_bps: int,
) -> dict[str, Decimal]:
    """Canonical open-mark economics after modeled entry+exit fees.

    Does not persist. Forward `record_position_mark` and owner projection
    must use this helper so Workbench cannot keep a second formula.
    """

    mark_value = (mark_price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    unrealized_gross = (mark_value - entered_notional).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    modeled_exit_fee = (mark_value * Decimal(fee_bps) / Decimal("10000")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    unrealized_net = (unrealized_gross - entry_fee - modeled_exit_fee).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return {
        "mark_value": mark_value,
        "unrealized_gross": unrealized_gross,
        "modeled_exit_fee_at_mark": modeled_exit_fee,
        "unrealized_net": unrealized_net,
    }


def signal_kind_for(
    strategy: Mapping[str, Any],
    row: Mapping[str, Any],
) -> str:
    """Evaluate one decision-time row against one declarative signal rule.

    Legacy v1.0 compatibility path only. v1.1 must not call this.
    Missing feature data yields UNKNOWN, never zero.
    """

    if str(strategy.get("schema_version", "1.0")) == "1.1":
        raise PaperPlaneError("SIGNAL_KIND_FOR_FORBIDDEN_ON_V1_1")
    rule = strategy["signal_rule"]
    value = row.get(str(rule["feature"]))
    if value is None:
        return "UNKNOWN"
    threshold = Decimal(str(rule["bin_threshold"]))
    try:
        numeric = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "UNKNOWN"
    op = str(rule["bin_op"])
    high = numeric >= threshold if op == ">=" else numeric > threshold
    entry_kinds = list(strategy["entry_rule"]["when_signal_kind_in"])
    return entry_kinds[0] if high else "NO_SIGNAL"


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl_type: str) -> None:
    if column in _table_columns(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def _connect_sqlite(path: Path, *, readonly: bool) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        conn.isolation_level = None
    else:
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.isolation_level = None
        conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    conn.create_function("modeled_final_witness_v1", 21, _sql_modeled_final_witness, deterministic=True)
    conn.create_function("unattempted_cancel_witness_v1", 7, _sql_unattempted_cancel_witness, deterministic=True)
    if readonly:
        try:
            # Validate actual source access now, so discovery can report an
            # unreadable/corrupt source before projecting any runtime values.
            conn.execute("PRAGMA schema_version").fetchone()
        except sqlite3.Error:
            conn.close()
            raise
    return conn


class PaperPlaneStore:
    def __init__(self, path: Path, *, readonly: bool = False) -> None:
        self.path = path
        self.readonly = readonly
        self._txn_depth = threading.local()
        self._write_lock = threading.Lock()
        if readonly:
            if not path.is_file():
                raise PaperPlaneError("SOURCE_NOT_PRESENT")
            self._conn = _connect_sqlite(path, readonly=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = _connect_sqlite(path, readonly=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_instances (
                bot_instance_id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                mode TEXT NOT NULL CHECK (mode IN ('PAPER','SHADOW')),
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                stopped_at TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                bot_instance_id TEXT NOT NULL,
                mint TEXT NOT NULL,
                state TEXT NOT NULL,
                signal_kind TEXT,
                entered_notional_usd REAL,
                exit_notional_usd REAL,
                opened_at TEXT,
                closed_at TEXT
            )
            """
        )
        self._migrate_v1_1_lineage()
        self._migrate_accounting_control_v1()
        self._migrate_trading_runtime_policy_v1()
        self._migrate_entry_intent_integrity_v1()
        self._migrate_decision_identity_v1()
        self._migrate_operational_accounting_v1()
        self._commit()

    @contextmanager
    def read_snapshot(self) -> Iterator[None]:
        """One readonly projection snapshot; release it before the next read.

        Writable callers retain their existing transaction semantics. Native
        SQLite WAL/SHM coordination is permitted; SQL/business writes are not.
        """
        if not self.readonly or self._conn.in_transaction:
            yield
            return
        self._conn.execute("BEGIN")
        try:
            yield
        finally:
            self._conn.execute("ROLLBACK")

    def _migrate_v1_1_lineage(self) -> None:
        """Idempotent additive columns for v1.1 lineage. Legacy rows may be NULL."""

        _ensure_column(self._conn, "bot_instances", "activation_epoch_id", "TEXT")
        _ensure_column(self._conn, "bot_instances", "runtime_schema_version", "TEXT")
        _ensure_column(self._conn, "positions", "signal_decision_id", "TEXT")
        _ensure_column(self._conn, "positions", "activation_epoch_id", "TEXT")
        _ensure_column(self._conn, "positions", "strategy_id", "TEXT")
        _ensure_column(self._conn, "positions", "strategy_version_label", "TEXT")
        _ensure_column(self._conn, "positions", "exit_decision_id", "TEXT")
        _ensure_column(self._conn, "positions", "reason_code", "TEXT")
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_positions_signal_decision_id
            ON positions(signal_decision_id)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bot_activation_epoch_id
            ON bot_instances(activation_epoch_id)
            """
        )

    def _migrate_accounting_control_v1(self) -> None:
        """Idempotent PAPER/SHADOW accounting + operator-control columns/tables."""

        _ensure_column(self._conn, "bot_instances", "entries_paused", "INTEGER NOT NULL DEFAULT 0")
        for col, typ in (
            ("entry_price_dec", "TEXT"),
            ("exit_price_dec", "TEXT"),
            ("qty_dec", "TEXT"),
            ("fee_bps", "INTEGER"),
            ("entry_fee_usd_dec", "TEXT"),
            ("exit_fee_usd_dec", "TEXT"),
            ("entered_notional_usd_dec", "TEXT"),
            ("exit_notional_usd_dec", "TEXT"),
            ("realized_gross_pnl_usd_dec", "TEXT"),
            ("realized_net_pnl_usd_dec", "TEXT"),
            ("pnl_evidence_class", "TEXT"),
            ("mark_price_dec", "TEXT"),
            ("mark_as_of", "TEXT"),
            ("unrealized_gross_pnl_usd_dec", "TEXT"),
            ("unrealized_net_pnl_usd_dec", "TEXT"),
            ("unrealized_evidence_class", "TEXT"),
        ):
            _ensure_column(self._conn, "positions", col, typ)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                bot_instance_id TEXT,
                position_id TEXT,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operator_commands (
                idempotency_key TEXT PRIMARY KEY,
                command_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                request_json TEXT NOT NULL,
                result_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS position_marks (
                mark_id TEXT PRIMARY KEY,
                position_id TEXT NOT NULL,
                mark_price_dec TEXT,
                as_of TEXT NOT NULL,
                evidence_class TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

    def _migrate_trading_runtime_policy_v1(self) -> None:
        """Append-only runtime policy revisions plus frozen admission lineage."""

        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_runtime_policy_revisions (
                mode TEXT NOT NULL CHECK (mode IN ('PAPER','SHADOW')),
                revision INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                policy_json TEXT NOT NULL,
                policy_sha256 TEXT NOT NULL,
                previous_policy_sha256 TEXT NOT NULL,
                PRIMARY KEY (mode, revision)
            )
            """
        )
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_trp_mode_sha256
            ON trading_runtime_policy_revisions(mode, policy_sha256)
            """
        )
        for col, typ in (
            ("admitted_entry_notional_usd_dec", "TEXT"),
            ("strategy_requested_notional_usd_dec", "TEXT"),
            ("runtime_policy_mode", "TEXT"),
            ("runtime_policy_revision", "INTEGER"),
            ("runtime_policy_sha256", "TEXT"),
        ):
            _ensure_column(self._conn, "positions", col, typ)

    def _migrate_entry_intent_integrity_v1(self) -> None:
        """Idempotent cancel reason and frozen admission fee. Legacy rows may be NULL."""

        _ensure_column(self._conn, "positions", "cancel_reason_code", "TEXT")
        _ensure_column(self._conn, "positions", "admitted_fee_bps", "INTEGER")

    def _migrate_decision_identity_v1(self) -> None:
        """Idempotent decision fingerprint and separate exit reason. Legacy rows may be NULL."""

        _ensure_column(self._conn, "positions", "signal_decision_sha256", "TEXT")
        _ensure_column(self._conn, "positions", "strategy_spec_sha256", "TEXT")
        _ensure_column(self._conn, "positions", "exit_reason_code", "TEXT")
        _ensure_column(self._conn, "bot_instances", "strategy_spec_sha256", "TEXT")

    def _migrate_operational_accounting_v1(self) -> None:
        """Additive remaining inventory; legacy fill/event bytes are untouched."""
        for column, kind in (
            ("ordinary_operating", "INTEGER"),
            ("ordinary_envelope_sha256", "TEXT"),
            ("entry_fee_semantics", "TEXT"),
            ("remaining_qty_dec", "TEXT"),
            ("remaining_cost_basis_usd_dec", "TEXT"),
            ("remaining_entry_fee_usd_dec", "TEXT"),
        ):
            _ensure_column(self._conn, "positions", column, kind)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_events_type ON execution_events(event_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_events_position_type ON execution_events(position_id,event_type)")
        self._conn.execute(f"CREATE INDEX IF NOT EXISTS idx_positions_outstanding_candidates_v1 ON positions(bot_instance_id) WHERE {_OBLIGATION_CANDIDATE_SQL}")

    def _commit(self) -> None:
        # Writable connections use isolation_level=None. Statements persist
        # immediately unless immediate_write() opened BEGIN IMMEDIATE.
        return

    @contextmanager
    def immediate_write(self) -> Iterator[None]:
        if self.readonly:
            raise PaperPlaneError("READONLY_STORE")
        depth = int(getattr(self._txn_depth, "value", 0))
        if depth:
            yield
            return
        with self._write_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            self._txn_depth.value = 1
            try:
                yield
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
            finally:
                self._txn_depth.value = 0

    def close(self) -> None:
        if not self.readonly:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._conn.close()

    def start_bot(
        self,
        strategy: Mapping[str, Any],
        *,
        mode: str = "PAPER",
        activation_epoch_id: str | None = None,
    ) -> dict[str, Any]:
        if mode not in {"PAPER", "SHADOW"}:
            raise PaperPlaneError("BOT_MODE_INVALID")
        schema_version = str(strategy.get("schema_version", "1.0"))
        if schema_version == "1.1":
            if not activation_epoch_id:
                raise PaperPlaneError("ACTIVATION_EPOCH_REQUIRED")
            bot_instance_id = (
                f"BOT-{strategy['strategy_id']}-{strategy['strategy_version']}"
                f"-{mode}-{activation_epoch_id}"
            )
        else:
            bot_instance_id = (
                f"BOT-{strategy['strategy_id']}-{strategy['strategy_version']}-{mode}"
            )
            activation_epoch_id = None
        spec = str(strategy.get("spec_sha256") or "") or None
        existing = self.get_bot(bot_instance_id)
        if existing is not None:
            known_raw = existing.get("strategy_spec_sha256")
            known = str(known_raw) if known_raw not in {None, ""} else ""
            if known and spec and known != spec:
                raise PaperPlaneError("STRATEGY_SPEC_DRIFT")
            if not known and spec:
                self._conn.execute(
                    """
                    UPDATE bot_instances
                    SET strategy_spec_sha256 = ?
                    WHERE bot_instance_id = ? AND strategy_spec_sha256 IS NULL
                    """,
                    (spec, bot_instance_id),
                )
                self._commit()
                refreshed = self.get_bot(bot_instance_id)
                assert refreshed is not None
                return refreshed
            status = str(existing.get("status") or "")
            if status == "RUNNING":
                return existing
            if status in {"DRAINING", "STOPPED"}:
                # Never resurrect control-plane status via start_bot side effect.
                return existing
        record = {
            "bot_instance_id": bot_instance_id,
            "strategy_id": str(strategy["strategy_id"]),
            "strategy_version": f"{strategy['strategy_id']}-{strategy['strategy_version']}",
            "mode": mode,
            "status": "RUNNING",
            "started_at": _now(),
            "stopped_at": None,
            "activation_epoch_id": activation_epoch_id,
            "runtime_schema_version": schema_version,
        }
        self._conn.execute(
            """
            INSERT INTO bot_instances(
                bot_instance_id, strategy_id, strategy_version, mode,
                status, started_at, stopped_at, activation_epoch_id,
                runtime_schema_version, strategy_spec_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bot_instance_id) DO UPDATE SET
                status=CASE
                    WHEN bot_instances.status IN ('DRAINING','STOPPED')
                    THEN bot_instances.status
                    ELSE excluded.status
                END,
                stopped_at=CASE
                    WHEN bot_instances.status IN ('DRAINING','STOPPED')
                    THEN bot_instances.stopped_at
                    ELSE excluded.stopped_at
                END,
                activation_epoch_id=COALESCE(excluded.activation_epoch_id, bot_instances.activation_epoch_id),
                runtime_schema_version=COALESCE(excluded.runtime_schema_version, bot_instances.runtime_schema_version),
                strategy_spec_sha256=COALESCE(bot_instances.strategy_spec_sha256, excluded.strategy_spec_sha256)
            """,
            (
                record["bot_instance_id"],
                record["strategy_id"],
                record["strategy_version"],
                record["mode"],
                record["status"],
                record["started_at"],
                None,
                record["activation_epoch_id"],
                record["runtime_schema_version"],
                spec,
            ),
        )
        self._commit()
        refreshed = self.get_bot(bot_instance_id)
        assert refreshed is not None
        return refreshed

    def get_bot(self, bot_instance_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM bot_instances WHERE bot_instance_id = ?", (bot_instance_id,)
        ).fetchone()
        return dict(row) if row else None

    def bots(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM bot_instances ORDER BY started_at").fetchall()
        return [dict(row) for row in rows]

    def open_position(self, *, bot_instance_id: str, mint: str, signal_kind: str) -> str:
        if signal_kind in FORBIDDEN_SIGNAL_KINDS:
            raise PaperPlaneError("REAL_FILL_FORBIDDEN_IN_PAPER_PLANE")
        if signal_kind not in SIGNAL_KINDS:
            raise PaperPlaneError("SIGNAL_KIND_INVALID")
        position_id = f"POS-{bot_instance_id}-{mint[:12]}-{signal_kind}"
        self._conn.execute(
            """
            INSERT INTO positions(
                position_id, bot_instance_id, mint, state, signal_kind,
                opened_at
            ) VALUES (?, ?, ?, 'WATCHED', ?, ?)
            ON CONFLICT(position_id) DO NOTHING
            """,
            (position_id, bot_instance_id, mint, signal_kind, _now()),
        )
        self._commit()
        return position_id

    def open_position_from_signal(
        self,
        *,
        bot_instance_id: str,
        signal_decision: Mapping[str, Any],
        signal_kind: str = "SIMULATED_FILL",
        signal_decision_sha256: str | None = None,
        strategy_spec_sha256: str | None = None,
    ) -> str:
        signal_decision_id = str(signal_decision["signal_decision_id"])
        position_id = position_id_for_signal_decision(signal_decision_id)
        self._conn.execute(
            """
            INSERT INTO positions(
                position_id, bot_instance_id, mint, state, signal_kind,
                opened_at, signal_decision_id, activation_epoch_id,
                strategy_id, strategy_version_label, reason_code,
                signal_decision_sha256, strategy_spec_sha256
            ) VALUES (?, ?, ?, 'WATCHED', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(position_id) DO NOTHING
            """,
            (
                position_id,
                bot_instance_id,
                str(signal_decision["mint"]),
                signal_kind,
                _now(),
                signal_decision_id,
                str(signal_decision["activation_epoch_id"]),
                str(signal_decision["strategy_id"]),
                str(signal_decision["strategy_version"]),
                str(signal_decision["reason_code"]),
                signal_decision_sha256,
                strategy_spec_sha256,
            ),
        )
        self._commit()
        return position_id

    def transition(
        self, position_id: str, to_state: str, *, commit: bool = True
    ) -> dict[str, Any]:
        # `commit` is kept for call-site compatibility; every transition is atomic.
        del commit
        with self.immediate_write():
            row = self._conn.execute(
                "SELECT state FROM positions WHERE position_id = ?", (position_id,)
            ).fetchone()
            if row is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            current = str(row["state"])
            if to_state not in TRANSITIONS.get(current, set()):
                raise PaperPlaneError(f"ILLEGAL_TRANSITION:{current}->{to_state}")
            closed_at = _now() if to_state in CLOSING_STATES else None
            cursor = self._conn.execute(
                """
                UPDATE positions SET state = ?, closed_at = COALESCE(?, closed_at)
                WHERE position_id = ? AND state = ?
                """,
                (to_state, closed_at, position_id, current),
            )
            if cursor.rowcount != 1:
                raise PaperPlaneError(f"STALE_STATE:{current}->{to_state}")
            updated = self.get_position(position_id)
        assert updated is not None
        return updated

    def get_position(self, position_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM positions WHERE position_id = ?", (position_id,)
        ).fetchone()
        return dict(row) if row else None

    def position_id_for(self, *, bot_instance_id: str, mint: str, signal_kind: str) -> str:
        return f"POS-{bot_instance_id}-{mint[:12]}-{signal_kind}"

    def positions(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM positions ORDER BY opened_at").fetchall()
        return [dict(row) for row in rows]

    def obligation_positions(self, mode: str) -> list[dict[str, Any]]:
        """Terminal rows require live indexed witnesses, never a cached release."""
        predicate = (f"({_OBLIGATION_CANDIDATE_SQL}) OR NOT ({_PROVED_RELEASE_SQL})" if "remaining_qty_dec" in _table_columns(self._conn, "positions")
                     else "1=1")  # Pre-migration readonly legacy compatibility.
        rows = self._conn.execute(f"""SELECT positions.*, bot_instances.mode AS obligation_mode
            FROM positions LEFT JOIN bot_instances USING(bot_instance_id)
            WHERE ({predicate}) AND (bot_instances.mode=? OR bot_instances.mode IS NULL)""", (mode,)).fetchall()
        return [dict(row) for row in rows]

    def open_risk_count(self, bot_instance_id: str) -> int:
        rows = self._conn.execute(
            "SELECT state FROM positions WHERE bot_instance_id = ?",
            (bot_instance_id,),
        ).fetchall()
        return sum(1 for row in rows if str(row["state"]) in OPEN_RISK_STATES)

    def open_positions_for_bot(self, bot_instance_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM positions
            WHERE bot_instance_id = ?
              AND state IN (
                'WATCHED','SIGNALLED','INTENT_CREATED','ATTEMPTING',
                'OPEN','PARTIAL','UNKNOWN','EXIT_REQUIRED','EXITING','UNRESOLVED'
              )
            ORDER BY position_id
            """,
            (bot_instance_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def set_entries_paused(self, bot_instance_id: str, *, paused: bool) -> None:
        with self.immediate_write():
            bot = self.get_bot(bot_instance_id)
            if bot is None:
                raise PaperPlaneError("BOT_NOT_FOUND")
            self._conn.execute(
                "UPDATE bot_instances SET entries_paused = ? WHERE bot_instance_id = ?",
                (1 if paused else 0, bot_instance_id),
            )
            self._commit()

    def set_bot_status(
        self,
        bot_instance_id: str,
        status: str,
        *,
        stopped_at: str | None = None,
    ) -> None:
        with self.immediate_write():
            bot = self.get_bot(bot_instance_id)
            if bot is None:
                raise PaperPlaneError("BOT_NOT_FOUND")
            self._conn.execute(
                """
                UPDATE bot_instances
                SET status = ?, stopped_at = COALESCE(?, stopped_at)
                WHERE bot_instance_id = ?
                """,
                (status, stopped_at, bot_instance_id),
            )
            self._commit()

    def append_execution_event(
        self,
        *,
        event_type: str,
        bot_instance_id: str | None,
        position_id: str | None,
        payload: Mapping[str, Any],
        event_id: str | None = None,
        created_at: str | None = None,
    ) -> str:
        eid = event_id or f"EVT-{uuid4().hex[:16].upper()}"
        self._conn.execute(
            """
            INSERT INTO execution_events(
                event_id, event_type, bot_instance_id, position_id, created_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                eid,
                event_type,
                bot_instance_id,
                position_id,
                created_at or _now(),
                json.dumps(dict(payload), sort_keys=True),
            ),
        )
        self._commit()
        return eid

    def execution_events(self) -> list[dict[str, Any]]:
        return self.filtered_execution_events()

    def filtered_execution_events(self, *, event_type: str | None = None,
                                  position_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if position_ids == []:
            return []
        groups = [None] if position_ids is None else [position_ids[i:i + 500] for i in range(0, len(position_ids), 500)]
        rows = []
        for group in groups:
            conditions = []
            parameters: list[Any] = []
            if event_type is not None:
                conditions.append("event_type=?")
                parameters.append(event_type)
            if group is not None:
                conditions.append("position_id IN (" + ",".join("?" for _ in group) + ")")
                parameters.extend(group)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            rows.extend(self._conn.execute("SELECT rowid AS event_sequence,* FROM execution_events" + where + " ORDER BY rowid", parameters).fetchall())
        rows.sort(key=lambda row: row["event_sequence"])
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item.pop("event_sequence")
            raw = item.pop("payload_json")
            try:
                item["payload"] = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                item["payload"] = {}
            out.append(item)
        return out

    def get_execution_event(self, event_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM execution_events WHERE event_id = ?", (event_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        try:
            item["payload"] = json.loads(item.pop("payload_json"))
        except (TypeError, ValueError):
            raise PaperPlaneError("EXECUTION_EVENT_CORRUPT") from None
        return item

    def get_operator_command(self, idempotency_key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM operator_commands WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None

    def record_operator_command(
        self,
        *,
        idempotency_key: str,
        command_type: str,
        request: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO operator_commands(
                idempotency_key, command_type, created_at, request_json, result_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                idempotency_key,
                command_type,
                _now(),
                json.dumps(dict(request), sort_keys=True),
                json.dumps(dict(result), sort_keys=True),
            ),
        )
        self._commit()

    def latest_runtime_policy_row(self, mode: str) -> dict[str, Any] | None:
        if self.readonly:
            tables = {
                str(row[0])
                for row in self._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "trading_runtime_policy_revisions" not in tables:
                return None
        row = self._conn.execute(
            """
            SELECT * FROM trading_runtime_policy_revisions
            WHERE mode = ?
            ORDER BY revision DESC
            LIMIT 1
            """,
            (mode,),
        ).fetchone()
        return dict(row) if row else None

    def runtime_policy_history(self, mode: str) -> list[dict[str, Any]]:
        if self.readonly:
            tables = {
                str(row[0])
                for row in self._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "trading_runtime_policy_revisions" not in tables:
                return []
        rows = self._conn.execute(
            """
            SELECT mode, revision, created_at, reason, policy_sha256, previous_policy_sha256
            FROM trading_runtime_policy_revisions
            WHERE mode = ?
            ORDER BY revision DESC
            """,
            (mode,),
        ).fetchall()
        return [dict(row) for row in rows]

    def runtime_policy_by_sha256(self, mode: str, policy_sha256: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM trading_runtime_policy_revisions
            WHERE mode = ? AND policy_sha256 = ?
            """,
            (mode, policy_sha256),
        ).fetchone()
        return dict(row) if row else None

    def append_runtime_policy_revision(self, policy: Mapping[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO trading_runtime_policy_revisions(
                mode, revision, created_at, reason, policy_json,
                policy_sha256, previous_policy_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(policy["mode"]),
                int(policy["revision"]),
                str(policy["created_at"]),
                str(policy["reason"]),
                json.dumps(dict(policy), sort_keys=True),
                str(policy["policy_sha256"]),
                str(policy["previous_policy_sha256"]),
            ),
        )

    def cancel_entry_intent(self, position_id: str, *, reason_code: str) -> dict[str, Any]:
        if reason_code not in CANCEL_REASONS:
            raise PaperPlaneError("CANCEL_REASON_INVALID")
        with self.immediate_write():
            position = self.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            state = str(position["state"])
            if state == "CANCELLED":
                return position
            if state == "ATTEMPTING" and reason_code not in DEFINITIVE_NON_FILL_REASONS:
                raise PaperPlaneError("CANCEL_REQUIRES_DEFINITIVE_NON_FILL:ATTEMPTING")
            if state not in PRE_ATTEMPT_STATES and state != "ATTEMPTING":
                raise PaperPlaneError(f"CANCEL_STATE_INVALID:{state}")
            if position.get("entry_price_dec") not in {None, ""}:
                raise PaperPlaneError("CANCEL_AFTER_FILL_FORBIDDEN")
            self.transition(position_id, "CANCELLED")
            self._conn.execute(
                "UPDATE positions SET cancel_reason_code = ?, remaining_qty_dec='0', remaining_cost_basis_usd_dec='0', remaining_entry_fee_usd_dec='0' WHERE position_id = ?",
                (reason_code, position_id),
            )
            self.append_execution_event(
                event_type="ENTRY_INTENT_CANCELLED",
                bot_instance_id=str(position["bot_instance_id"]),
                position_id=position_id,
                payload={
                    **_identity_fields(position),
                    "from_state": state,
                    "cancel_reason_code": reason_code,
                },
            )
            updated = self.get_position(position_id)
        assert updated is not None
        return updated

    def freeze_admission_binding(
        self,
        position_id: str,
        *,
        admitted_entry_notional_usd_dec: str,
        strategy_requested_notional_usd_dec: str,
        runtime_policy_mode: str | None,
        runtime_policy_revision: int | None,
        runtime_policy_sha256: str | None,
        admitted_fee_bps: int | None = None,
    ) -> None:
        with self.immediate_write():
            self._freeze_admission_binding_locked(
                position_id,
                admitted_entry_notional_usd_dec=admitted_entry_notional_usd_dec,
                strategy_requested_notional_usd_dec=strategy_requested_notional_usd_dec,
                runtime_policy_mode=runtime_policy_mode,
                runtime_policy_revision=runtime_policy_revision,
                runtime_policy_sha256=runtime_policy_sha256,
                admitted_fee_bps=admitted_fee_bps,
            )

    def _freeze_admission_binding_locked(
        self,
        position_id: str,
        *,
        admitted_entry_notional_usd_dec: str,
        strategy_requested_notional_usd_dec: str,
        runtime_policy_mode: str | None,
        runtime_policy_revision: int | None,
        runtime_policy_sha256: str | None,
        admitted_fee_bps: int | None = None,
    ) -> None:
        self._conn.execute(
            """
            UPDATE positions
            SET admitted_entry_notional_usd_dec = COALESCE(admitted_entry_notional_usd_dec, ?),
                strategy_requested_notional_usd_dec = COALESCE(strategy_requested_notional_usd_dec, ?),
                runtime_policy_mode = COALESCE(runtime_policy_mode, ?),
                runtime_policy_revision = COALESCE(runtime_policy_revision, ?),
                runtime_policy_sha256 = COALESCE(runtime_policy_sha256, ?),
                admitted_fee_bps = COALESCE(admitted_fee_bps, ?)
            WHERE position_id = ?
            """,
            (
                admitted_entry_notional_usd_dec,
                strategy_requested_notional_usd_dec,
                runtime_policy_mode,
                runtime_policy_revision,
                runtime_policy_sha256,
                admitted_fee_bps,
                position_id,
            ),
        )

    def open_risk_inventory(
        self,
        *,
        mode: str,
        strategy_id: str,
        mint: str,
        bot_instance_id: str = "",
    ) -> dict[str, Any]:
        rows = self._conn.execute(
            """
            SELECT p.* FROM positions p
            JOIN bot_instances b ON b.bot_instance_id = p.bot_instance_id
            WHERE b.mode = ?
            """,
            (mode,),
        ).fetchall()
        global_count = 0
        strategy_count = 0
        mint_count = 0
        bot_count = 0
        strategy_identity_unknown = False
        global_notional = Decimal("0")
        strategy_notional = Decimal("0")
        mint_notional = Decimal("0")
        global_unknown = False
        strategy_unknown = False
        mint_unknown = False

        def _exposure(item: Mapping[str, Any]) -> tuple[Decimal | None, bool]:
            entered = item.get("entered_notional_usd_dec")
            if entered not in {None, ""}:
                return Decimal(str(entered)), False
            admitted = item.get("admitted_entry_notional_usd_dec")
            if admitted not in {None, ""}:
                return Decimal(str(admitted)), False
            return None, True
        for row in rows:
            item = dict(row)
            if str(item["state"]) not in OPEN_RISK_STATES:
                continue
            global_count += 1
            notional, unknown = _exposure(item)
            if unknown:
                global_unknown = True
            elif notional is not None:
                global_notional += notional
            if bot_instance_id and str(item.get("bot_instance_id") or "") == bot_instance_id:
                bot_count += 1
            sid = str(item.get("strategy_id") or "")
            if not sid:
                strategy_identity_unknown = True
                strategy_unknown = True
            elif sid == strategy_id:
                strategy_count += 1
                if unknown:
                    strategy_unknown = True
                elif notional is not None:
                    strategy_notional += notional
            if str(item.get("mint") or "") == mint:
                mint_count += 1
                if unknown:
                    mint_unknown = True
                elif notional is not None:
                    mint_notional += notional
        return {
            "global_count": global_count,
            "strategy_count": strategy_count,
            "mint_count": mint_count,
            "bot_count": bot_count,
            "strategy_identity_unknown": strategy_identity_unknown,
            "global_notional": None if global_unknown else global_notional,
            "strategy_notional": None if strategy_unknown else strategy_notional,
            "mint_notional": None if mint_unknown else mint_notional,
            "global_unknown": global_unknown,
            "strategy_unknown": strategy_unknown,
            "mint_unknown": mint_unknown,
        }

    def record_position_mark(
        self,
        *,
        position_id: str,
        mark_price_dec: str | None,
        as_of: str,
        evidence_class: str,
    ) -> str:
        allowed = {
            "PAPER_MARK_TO_MODEL",
            "SHADOW_EXECUTABLE_QUOTE_MARK",
            "UNKNOWN",
        }
        if evidence_class not in allowed:
            raise PaperPlaneError("MARK_EVIDENCE_CLASS_INVALID")
        with self.immediate_write():
            mark_id = f"MARK-{uuid4().hex[:12].upper()}"
            self._conn.execute(
                """
                INSERT INTO position_marks(
                    mark_id, position_id, mark_price_dec, as_of, evidence_class, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mark_id, position_id, mark_price_dec, as_of, evidence_class, _now()),
            )
            unrealized = None
            unrealized_net = None
            position = self.get_position(position_id)
            if (
                position is not None
                and mark_price_dec is not None
                and evidence_class != "UNKNOWN"
                and position.get("entry_price_dec")
                and position.get("qty_dec")
                and position.get("entered_notional_usd_dec") is not None
            ):
                qty = Decimal(str(position.get("remaining_qty_dec") if position.get("remaining_qty_dec") is not None else position["qty_dec"]))
                mark = Decimal(str(mark_price_dec))
                entry_notional = Decimal(str(position.get("remaining_cost_basis_usd_dec") if position.get("remaining_cost_basis_usd_dec") is not None else position["entered_notional_usd_dec"]))
                entry_fee_raw = position.get("remaining_entry_fee_usd_dec") if position.get("remaining_entry_fee_usd_dec") is not None else position.get("entry_fee_usd_dec")
                fee_bps_raw = position.get("fee_bps")
                if entry_fee_raw not in {None, ""} and fee_bps_raw is not None:
                    derived = modeled_unrealized_mark(
                        mark_price=mark,
                        qty=qty,
                        entered_notional=entry_notional,
                        entry_fee=Decimal(str(entry_fee_raw)),
                        fee_bps=int(fee_bps_raw),
                    )
                    unrealized = format(derived["unrealized_gross"], "f")
                    unrealized_net = format(derived["unrealized_net"], "f")
                else:
                    mark_value = (mark * qty).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    gross = (mark_value - entry_notional).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    unrealized = format(gross, "f")
                    unrealized_net = None
            self._conn.execute(
                """
                UPDATE positions
                SET mark_price_dec = ?,
                    mark_as_of = ?,
                    unrealized_gross_pnl_usd_dec = ?,
                    unrealized_net_pnl_usd_dec = ?,
                    unrealized_evidence_class = ?
                WHERE position_id = ?
                """,
                (
                    mark_price_dec,
                    as_of,
                    unrealized,
                    unrealized_net,
                    evidence_class,
                    position_id,
                ),
            )
            self._commit()
            return mark_id

    def apply_paper_entry_fill(
        self,
        *,
        position_id: str,
        entry_unit_price_usd: str,
        entry_gross_notional_usd: str,
        fee_bps: int | None = None,
        mode: str,
        reconcile_pending_close: bool = False,
        entry_quantity_units: str | None = None,
        fee_semantics: str | None = None,
    ) -> dict[str, Any]:
        if mode not in {"PAPER", "SHADOW"}:
            raise PaperPlaneError("BOT_MODE_INVALID")
        with self.immediate_write():
            position = self.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            state = str(position["state"])
            pending_close = reconcile_pending_close and state == "EXIT_REQUIRED" and position.get("entry_price_dec") is None
            if state in {"CLOSED", "RECONCILED", "UNRESOLVED", "EXIT_REQUIRED", "EXITING"} and not pending_close:
                raise PaperPlaneError(f"ENTRY_FILL_STATE_INVALID:{state}")
            if state in {"WATCHED", "SIGNALLED", "INTENT_CREATED"}:
                raise PaperPlaneError(f"ENTRY_FILL_STATE_INVALID:{state}")
            if state not in {"ATTEMPTING", "OPEN", "PARTIAL", "UNKNOWN"} and not pending_close:
                raise PaperPlaneError(f"ENTRY_FILL_STATE_INVALID:{state}")
            price = Decimal(str(entry_unit_price_usd))
            notional = Decimal(str(entry_gross_notional_usd))
            if not price.is_finite() or not notional.is_finite() or price <= 0 or notional <= 0:
                raise PaperPlaneError("ENTRY_FILL_INVALID")
            fee_bps = _bound_entry_fee_bps(position, fee_bps)
            if fee_semantics not in {None, "SEPARATE_MODELED_FEE", "INCLUDED_IN_UNIT_PRICE"}:
                raise PaperPlaneError("MODELED_FEE_SEMANTICS_UNSUPPORTED")
            quantity = (notional / price).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
            if entry_quantity_units is not None:
                quantity = _positive_model_decimal(entry_quantity_units, "MODELED_QUANTITY_INVALID")
                if (price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != notional.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
                    raise PaperPlaneError("MODELED_ENTRY_QUANTITY_PRICE_CONFLICT")
            entry_fee = (Decimal("0") if fee_semantics == "INCLUDED_IN_UNIT_PRICE" else
                         (notional * Decimal(fee_bps) / Decimal(10000)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            bot = self.get_bot(str(position["bot_instance_id"]))
            if bot is None or str(bot.get("mode")) != mode:
                raise PaperPlaneError("ENTRY_FILL_MODE_MISMATCH")
            if position.get("entry_price_dec") not in {None, ""}:
                if (
                    Decimal(str(position["entry_price_dec"])) != price
                    or Decimal(str(position["entered_notional_usd_dec"])) != notional
                    or int(position["fee_bps"]) != fee_bps
                ):
                    raise PaperPlaneError("ENTRY_FILL_CONTENT_CONFLICT")
                if position.get("entry_fee_semantics") != fee_semantics:
                    raise PaperPlaneError("ENTRY_FILL_CONTENT_CONFLICT")
                for field, expected in (("qty_dec", quantity), ("entry_fee_usd_dec", entry_fee)):
                    if position.get(field) not in {None, ""} and Decimal(str(position[field])) != expected:
                        raise PaperPlaneError("ENTRY_ACCOUNTING_CONTENT_CONFLICT")
                if position.get("qty_dec") in {None, ""} or position.get("entry_fee_usd_dec") in {None, ""}:
                    self._conn.execute("UPDATE positions SET qty_dec=?, entry_fee_usd_dec=? WHERE position_id=?",
                                       (format(quantity, "f"), format(entry_fee, "f"), position_id))
                    self.append_execution_event(event_type="ENTRY_ACCOUNTING_RECOVERED", bot_instance_id=bot["bot_instance_id"],
                        position_id=position_id, payload={**_identity_fields(position), "basis": "EXACT_ORIGINATING_ENTRY_BINDING"})
                    recovered = self.get_position(position_id)
                    assert recovered is not None
                    return recovered
                return position
            admitted = position.get("admitted_entry_notional_usd_dec")
            if admitted not in {None, ""} and notional > Decimal(str(admitted)):
                raise PaperPlaneError("ENTRY_FILL_NOTIONAL_EXCEEDS_ADMISSION")
            if state in {"ATTEMPTING", "UNKNOWN"}:
                self.transition(position_id, "PARTIAL" if admitted not in {None, ""} and notional < Decimal(str(admitted)) else "OPEN")
                position = self.get_position(position_id)
                assert position is not None
            evidence = (
                "PAPER_RECONCILED_MODEL" if mode == "PAPER" else "SHADOW_RECONCILED_QUOTE_MODEL"
            )
            # Entry alone is not yet reconciled; keep class for lineage, PnL null until exit.
            self._conn.execute(
                """
                UPDATE positions
                SET entry_price_dec = ?,
                    qty_dec = ?,
                    fee_bps = ?,
                    entry_fee_usd_dec = ?,
                    entered_notional_usd = ?,
                    entered_notional_usd_dec = ?,
                    pnl_evidence_class = NULL,
                    realized_gross_pnl_usd_dec = NULL,
                    realized_net_pnl_usd_dec = NULL
                WHERE position_id = ?
                """,
                (
                    format(price, "f"),
                    format(quantity, "f"),
                    fee_bps,
                    format(entry_fee, "f"),
                    float(notional),
                    format(notional, "f"),
                    position_id,
                ),
            )
            if fee_semantics is not None:
                self._conn.execute("UPDATE positions SET entry_fee_semantics=?, remaining_qty_dec=?, remaining_cost_basis_usd_dec=?, remaining_entry_fee_usd_dec=? WHERE position_id=?",
                    (fee_semantics, format(quantity, "f"), format(notional, "f"), format(entry_fee, "f"), position_id))
            event_type = (
                "PAPER_SIMULATION_OBSERVED" if mode == "PAPER" else "SHADOW_EXECUTABLE_OBSERVED"
            )
            self.append_execution_event(
                event_type=event_type,
                bot_instance_id=str(position["bot_instance_id"]),
                position_id=position_id,
                payload={
                    **_identity_fields(position),
                    "side": "ENTRY",
                    "entry_price_dec": format(price, "f"),
                    "qty_dec": format(quantity, "f"),
                    "entry_fee_usd_dec": format(entry_fee, "f"),
                    "entry_gross_notional_usd_dec": format(notional, "f"),
                    "mode": mode,
                    "pending_reconcile_class": evidence,
                },
            )
            updated = self.get_position(position_id)
            assert updated is not None
            return updated

    def apply_paper_exit_fill(
        self,
        *,
        position_id: str,
        exit_unit_price_usd: str | None,
        mode: str,
        unresolved: bool = False,
    ) -> dict[str, Any]:
        if mode not in {"PAPER", "SHADOW"}:
            raise PaperPlaneError("BOT_MODE_INVALID")
        with self.immediate_write():
            position = self.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            if not unresolved and exit_unit_price_usd is not None and position.get("remaining_qty_dec") is not None:
                return self.apply_quantity_exit_fill(position_id=position_id, mode=mode,
                    quantity_sold=str(position["remaining_qty_dec"]), remaining_quantity="0",
                    exit_unit_price_usd=exit_unit_price_usd, fee_semantics="SEPARATE_MODELED_FEE",
                    observed_at=_now(), leg_id="LEG-" + uuid4().hex.upper())
            state0 = str(position["state"])
            if state0 == "RECONCILED":
                raise PaperPlaneError(f"EXIT_FILL_STATE_INVALID:{state0}")

            def _advance_to_exiting(current: dict[str, Any]) -> dict[str, Any]:
                state = str(current["state"])
                if state in {"OPEN", "PARTIAL", "UNKNOWN"}:
                    current = self.transition(position_id, "EXIT_REQUIRED")
                    state = str(current["state"])
                if state == "EXIT_REQUIRED":
                    current = self.transition(position_id, "EXITING")
                return current

            if unresolved or exit_unit_price_usd is None:
                if state0 not in {
                    "OPEN",
                    "PARTIAL",
                    "UNKNOWN",
                    "EXIT_REQUIRED",
                    "EXITING",
                    "UNRESOLVED",
                }:
                    raise PaperPlaneError(f"EXIT_FILL_STATE_INVALID:{state0}")
                position = _advance_to_exiting(position)
                if str(position["state"]) == "EXITING":
                    position = self.transition(position_id, "UNRESOLVED")
                elif str(position["state"]) != "UNRESOLVED":
                    raise PaperPlaneError(f"EXIT_FILL_STATE_INVALID:{position['state']}")
                self._conn.execute(
                    """
                    UPDATE positions
                    SET pnl_evidence_class = NULL,
                        realized_gross_pnl_usd_dec = CASE WHEN remaining_qty_dec IS NULL THEN NULL ELSE realized_gross_pnl_usd_dec END,
                        realized_net_pnl_usd_dec = CASE WHEN remaining_qty_dec IS NULL THEN NULL ELSE realized_net_pnl_usd_dec END
                    WHERE position_id = ?
                    """,
                    (position_id,),
                )
                self.append_execution_event(
                    event_type="RECONCILIATION",
                    bot_instance_id=str(position["bot_instance_id"]),
                    position_id=position_id,
                    payload={
                        **_identity_fields(position),
                        "result": "UNRESOLVED",
                        "mode": mode,
                        "pnl_status": "UNKNOWN",
                    },
                )
                updated = self.get_position(position_id)
                assert updated is not None
                return updated

            if not position.get("entry_price_dec") or not position.get("qty_dec"):
                raise PaperPlaneError("EXIT_FILL_REQUIRES_ENTRY")
            notional_raw = position.get("entered_notional_usd_dec")
            if notional_raw is None:
                raise PaperPlaneError("EXIT_FILL_REQUIRES_ENTRY_NOTIONAL")
            if position.get("entry_fee_usd_dec") in {None, ""}:
                raise PaperPlaneError("EXIT_FILL_REQUIRES_ENTRY_FEE")
            qty = Decimal(str(position["qty_dec"]))
            fee_bps = int(position["fee_bps"] or 0)
            price = Decimal(str(exit_unit_price_usd))
            entry_notional = Decimal(str(notional_raw))
            entry_fee = Decimal(str(position["entry_fee_usd_dec"]))
            exit_gross = (price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            exit_fee = (exit_gross * Decimal(fee_bps) / Decimal(10000)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            gross = (exit_gross - entry_notional).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            net = (gross - entry_fee - exit_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            evidence = (
                "PAPER_RECONCILED_MODEL" if mode == "PAPER" else "SHADOW_RECONCILED_QUOTE_MODEL"
            )
            if state0 == "UNRESOLVED":
                self.transition(position_id, "RECONCILED")
            elif state0 == "CLOSED":
                self.transition(position_id, "RECONCILED")
            else:
                position = _advance_to_exiting(position)
                if str(position["state"]) == "EXITING":
                    self.transition(position_id, "CLOSED")
                closed = self.get_position(position_id)
                assert closed is not None
                if str(closed["state"]) == "CLOSED":
                    self.transition(position_id, "RECONCILED")
            self._conn.execute(
                """
                UPDATE positions
                SET exit_price_dec = ?,
                    exit_fee_usd_dec = ?,
                    exit_notional_usd = ?,
                    exit_notional_usd_dec = ?,
                    entered_notional_usd_dec = COALESCE(entered_notional_usd_dec, ?),
                    realized_gross_pnl_usd_dec = ?,
                    realized_net_pnl_usd_dec = ?,
                    pnl_evidence_class = ?,
                    closed_at = COALESCE(closed_at, ?)
                WHERE position_id = ?
                """,
                (
                    format(price, "f"),
                    format(exit_fee, "f"),
                    float(exit_gross),
                    format(exit_gross, "f"),
                    format(entry_notional, "f"),
                    format(gross, "f"),
                    format(net, "f"),
                    evidence,
                    _now(),
                    position_id,
                ),
            )
            exit_event = "PAPER_EXIT_OBSERVED" if mode == "PAPER" else "SHADOW_EXIT_EXECUTABLE_OBSERVED"
            self.append_execution_event(
                event_type=exit_event,
                bot_instance_id=str(position["bot_instance_id"]),
                position_id=position_id,
                payload={
                    **_identity_fields(position),
                    "side": "EXIT",
                    "exit_price_dec": format(price, "f"),
                    "exit_fee_usd_dec": format(exit_fee, "f"),
                    "realized_net_pnl_usd_dec": format(net, "f"),
                    "mode": mode,
                },
            )
            self.append_execution_event(
                event_type="RECONCILIATION",
                bot_instance_id=str(position["bot_instance_id"]),
                position_id=position_id,
                payload={
                    **_identity_fields(position),
                    "result": "RECONCILED",
                    "pnl_status": "KNOWN",
                    "net_pnl_usd_dec": format(net, "f"),
                    "pnl_evidence_class": evidence,
                    "mode": mode,
                },
            )
            updated = self.get_position(position_id)
            assert updated is not None
            return updated

    def apply_quantity_exit_fill(self, *, position_id: str, mode: str,
                                 quantity_sold: str, remaining_quantity: str,
                                 exit_unit_price_usd: str, fee_semantics: str,
                                 observed_at: str, leg_id: str) -> dict[str, Any]:
        """A definitive v1.1 leg finalizes one attempt, conserving its remainder."""
        sold = _positive_model_decimal(quantity_sold, "MODELED_QUANTITY_INVALID")
        remaining = _positive_model_decimal(remaining_quantity, "MODELED_QUANTITY_INVALID", allow_zero=True)
        price = _positive_model_decimal(exit_unit_price_usd, "MODELED_FILL_DETAILS_INVALID")
        if fee_semantics not in {"SEPARATE_MODELED_FEE", "INCLUDED_IN_UNIT_PRICE"}:
            raise PaperPlaneError("MODELED_FEE_SEMANTICS_UNSUPPORTED")
        with self.immediate_write():
            position = self.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            bot = self.get_bot(str(position["bot_instance_id"]))
            if bot is None or bot["mode"] != mode:
                raise PaperPlaneError("EXIT_FILL_MODE_MISMATCH")
            request = {"quantity_sold": format(sold, "f"), "remaining_quantity": format(remaining, "f"),
                       "unit_price_usd": format(price, "f"), "fee_semantics": fee_semantics,
                       "observed_at": observed_at, "mode": mode}
            previous = self.get_execution_event(leg_id)
            if previous is not None:
                if previous["position_id"] != position_id or previous["payload"].get("request") != request:
                    raise PaperPlaneError("EXIT_LEG_CONTENT_CONFLICT")
                return position
            if position["state"] not in {"OPEN", "PARTIAL", "EXIT_REQUIRED", "EXITING", "UNRESOLVED"}:
                raise PaperPlaneError("EXIT_QUANTITY_STATE_INVALID")
            original = _positive_model_decimal(position.get("qty_dec"), "EXIT_FILL_REQUIRES_ENTRY")
            prior_remaining = original if position.get("remaining_qty_dec") is None else _positive_model_decimal(
                position["remaining_qty_dec"], "MODELED_QUANTITY_INVALID")
            if sold > prior_remaining or sold + remaining != prior_remaining:
                raise PaperPlaneError("MODELED_EXIT_QUANTITY_CONFLICT")
            entry_notional = _positive_model_decimal(position.get("entered_notional_usd_dec"), "EXIT_FILL_REQUIRES_ENTRY_NOTIONAL")
            entry_fee = _positive_model_decimal(position.get("entry_fee_usd_dec"), "EXIT_FILL_REQUIRES_ENTRY_FEE", allow_zero=True)
            previous_exit = Decimal(str(position.get("exit_notional_usd_dec") or "0"))
            previous_fee = Decimal(str(position.get("exit_fee_usd_dec") or "0"))
            proceeds = (price * sold).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            leg_fee = (Decimal("0") if fee_semantics == "INCLUDED_IN_UNIT_PRICE" else
                       (proceeds * Decimal(int(position["fee_bps"])) / Decimal("10000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            remaining_cost = entry_notional * remaining / original
            allocated_cost = entry_notional - remaining_cost
            allocated_fee = (entry_fee * (original - remaining) / original).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            remaining_fee = entry_fee - allocated_fee
            prior_allocated_fee = entry_fee - Decimal(str(position.get("remaining_entry_fee_usd_dec")
                if position.get("remaining_entry_fee_usd_dec") is not None else entry_fee))
            exit_total = previous_exit + proceeds
            exit_fee = previous_fee + leg_fee
            gross = (exit_total - allocated_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            net = (gross - allocated_fee - exit_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            evidence = None if remaining else ("PAPER_RECONCILED_MODEL" if mode == "PAPER" else "SHADOW_RECONCILED_QUOTE_MODEL")
            # A completed partial leg returns to the same originating exit;
            # ordinary successor/control state cannot replace this obligation.
            self._conn.execute("""UPDATE positions SET state=?, remaining_qty_dec=?, remaining_cost_basis_usd_dec=?,
                remaining_entry_fee_usd_dec=?, exit_price_dec=?, exit_notional_usd=?, exit_notional_usd_dec=?,
                exit_fee_usd_dec=?, realized_gross_pnl_usd_dec=?, realized_net_pnl_usd_dec=?, pnl_evidence_class=?,
                closed_at=CASE WHEN ?=1 THEN COALESCE(closed_at,?) ELSE closed_at END,
                mark_price_dec=NULL, mark_as_of=NULL, unrealized_gross_pnl_usd_dec=NULL,
                unrealized_net_pnl_usd_dec=NULL, unrealized_evidence_class=NULL WHERE position_id=?""",
                ("EXIT_REQUIRED" if remaining else "RECONCILED", format(remaining, "f"), format(remaining_cost, "f"),
                 format(remaining_fee, "f"), format(exit_total / (original - remaining), "f"), float(exit_total),
                 format(exit_total, "f"), format(exit_fee, "f"), format(gross, "f"), format(net, "f"), evidence,
                 int(remaining == 0), observed_at, position_id))
            self.append_execution_event(event_type="MODELED_EXIT_QUANTITY_LEG", event_id=leg_id,
                bot_instance_id=bot["bot_instance_id"], position_id=position_id, created_at=observed_at,
                payload={"schema_version": "1.1", "request": request, "quantity_unit": "TOKEN_UNITS",
                         "proceeds_usd": format(proceeds, "f"), "exit_fee_usd": format(leg_fee, "f"),
                         "allocated_entry_fee_total_usd": format(allocated_fee, "f"),
                         "allocated_entry_fee_usd": format(allocated_fee - prior_allocated_fee, "f"),
                         "realized_gross_pnl_usd": format(gross - Decimal(str(position.get("realized_gross_pnl_usd_dec") or "0")), "f"),
                         "realized_trade_net_usd": format(net - Decimal(str(position.get("realized_net_pnl_usd_dec") or "0")), "f"),
                         "remaining_cost_basis_usd": format(remaining_cost, "f"),
                         "realized_trade_net_total_usd": format(net, "f"), "evidence_class": bot["mode"] + "_MODEL"})
            updated = self.get_position(position_id)
            assert updated is not None
            return updated

    def pre_trade_risk_snapshot(
        self,
        *,
        bot_instance_id: str,
        max_open_positions: int | None,
    ) -> dict[str, Any]:
        if max_open_positions is None:
            return {
                "decision": "UNKNOWN",
                "reason": "MAX_OPEN_POSITIONS_UNKNOWN",
                "current_open_risk_count": self.open_risk_count(bot_instance_id),
                "max_open_positions": None,
            }
        current = self.open_risk_count(bot_instance_id)
        if current >= int(max_open_positions):
            return {
                "decision": "BLOCK_MAX_OPEN_POSITIONS",
                "reason": "MAX_OPEN_REACHED",
                "current_open_risk_count": current,
                "max_open_positions": int(max_open_positions),
            }
        return {
            "decision": "ALLOW",
            "reason": "WITHIN_LIMIT",
            "current_open_risk_count": current,
            "max_open_positions": int(max_open_positions),
        }

    def fill_paper(self, *, bot_instance_id: str, mint: str, notional_usd: Decimal) -> tuple[str, str]:
        with self.immediate_write():
            position_id = self.open_position(
                bot_instance_id=bot_instance_id,
                mint=mint,
                signal_kind="SIMULATED_FILL",
            )
            self.transition(position_id, "SIGNALLED")
            self.transition(position_id, "INTENT_CREATED")
            self.transition(position_id, "ATTEMPTING")
            self.transition(position_id, "OPEN")
            self._conn.execute(
                "UPDATE positions SET entered_notional_usd=? WHERE position_id=?",
                (float(notional_usd), position_id),
            )
            return position_id, "SIMULATED_FILL"

    def fill_paper_from_signal(
        self,
        *,
        bot_instance_id: str,
        signal_decision: Mapping[str, Any],
        notional_usd: Decimal,
        signal_kind: str = "SIMULATED_FILL",
    ) -> tuple[str, str]:
        if signal_kind not in {"SIMULATED_FILL", "SHADOW_EXECUTABLE"}:
            raise PaperPlaneError("SIGNAL_KIND_INVALID")
        position_id = position_id_for_signal_decision(
            str(signal_decision["signal_decision_id"])
        )
        with self.immediate_write():
            existing = self.get_position(position_id)
            if existing is None:
                self.open_position_from_signal(
                    bot_instance_id=bot_instance_id,
                    signal_decision=signal_decision,
                    signal_kind=signal_kind,
                )
                existing = self.get_position(position_id)
            assert existing is not None
            if existing["state"] in {
                "OPEN",
                "PARTIAL",
                "EXIT_REQUIRED",
                "EXITING",
                "CLOSED",
                "RECONCILED",
                "UNRESOLVED",
            }:
                return position_id, str(existing.get("signal_kind") or signal_kind)
            state = str(existing["state"])
            if state == "WATCHED":
                self._conn.execute(
                    "UPDATE positions SET signal_kind=? WHERE position_id=?",
                    (signal_kind, position_id),
                )
                self.transition(position_id, "SIGNALLED")
                state = "SIGNALLED"
            if state == "SIGNALLED":
                self.transition(position_id, "INTENT_CREATED")
                state = "INTENT_CREATED"
            if state == "INTENT_CREATED":
                self.transition(position_id, "ATTEMPTING")
                state = "ATTEMPTING"
            if state == "ATTEMPTING":
                self.transition(position_id, "OPEN")
            self._conn.execute(
                "UPDATE positions SET entered_notional_usd=?, signal_kind=? WHERE position_id=?",
                (float(notional_usd), signal_kind, position_id),
            )
        return position_id, signal_kind

    def apply_exit_decision(
        self,
        *,
        exit_decision: Mapping[str, Any],
    ) -> dict[str, Any]:
        position_id = str(exit_decision["position_id"])
        with self.immediate_write():
            position = self.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            action = str(exit_decision["action"])
            if action != "EXIT":
                return {
                    "position_id": position_id,
                    "applied": False,
                    "action": action,
                    "state": position["state"],
                }
            if position["state"] == "EXIT_REQUIRED":
                self._conn.execute(
                    "UPDATE positions SET exit_decision_id=?, exit_reason_code=? WHERE position_id=?",
                    (
                        str(exit_decision["exit_decision_id"]),
                        str(exit_decision["reason_code"]),
                        position_id,
                    ),
                )
                self._commit()
                updated = self.get_position(position_id)
                assert updated is not None
                return {
                    "position_id": position_id,
                    "applied": True,
                    "action": action,
                    "state": updated["state"],
                    "fill_claimed": False,
                }
            if position["state"] not in {"OPEN", "PARTIAL", "UNKNOWN"}:
                raise PaperPlaneError(f"EXIT_DECISION_STATE_INVALID:{position['state']}")
            from_state = str(position["state"])
            self.transition(position_id, "EXIT_REQUIRED")
            self._conn.execute(
                "UPDATE positions SET exit_decision_id=?, exit_reason_code=? WHERE position_id=?",
                (
                    str(exit_decision["exit_decision_id"]),
                    str(exit_decision["reason_code"]),
                    position_id,
                ),
            )
            self.append_execution_event(
                event_type="EXIT_DECISION_ACCEPTED",
                bot_instance_id=str(position["bot_instance_id"]),
                position_id=position_id,
                payload={
                    **_identity_fields(position),
                    "exit_decision_id": str(exit_decision["exit_decision_id"]),
                    "exit_reason_code": str(exit_decision["reason_code"]),
                    "from_state": from_state,
                    "to_state": "EXIT_REQUIRED",
                    "exit_decision_at": exit_decision.get("decision_at"),
                    "evidence_refs": list(exit_decision.get("evidence_refs") or []),
                },
            )
            self._commit()
            refreshed = self.get_position(position_id)
            assert refreshed is not None
            return {
                "position_id": position_id,
                "applied": True,
                "action": action,
                "state": refreshed["state"],
                "fill_claimed": False,
            }


def resolve_activation_epoch(
    activation_epoch_id: str,
    *,
    known_activation_epochs: Mapping[str, Any] | set[str] | frozenset[str],
) -> None:
    if isinstance(known_activation_epochs, Mapping):
        ok = activation_epoch_id in known_activation_epochs
    else:
        ok = activation_epoch_id in known_activation_epochs
    if not ok:
        raise PaperPlaneError("ACTIVATION_EPOCH_UNRESOLVED")


def _bound_entry_fee_bps(position: Mapping[str, Any], requested: int | None) -> int:
    admitted = position.get("admitted_fee_bps")
    if admitted is not None:
        if requested is not None and int(requested) != int(admitted):
            raise PaperPlaneError("ENTRY_FILL_FEE_MISMATCH")
        return int(admitted)
    if requested is None:
        raise PaperPlaneError("ENTRY_FILL_FEE_REQUIRED")
    return int(requested)


def _resume_block(
    store: PaperPlaneStore, bot: Mapping[str, Any], mode: str, *, stale: bool
) -> tuple[str | None, str | None]:
    """Stop dominance for an admitted, unattempted intent (design §6.1 order)."""

    if stale:
        return "SIGNAL_DECISION_STALE", "SIGNAL_EXPIRED"
    status = str(bot.get("status") or "")
    if status in {"DRAINING", "STOPPED"}:
        return f"BOT_STATUS_BLOCKS_ENTRY:{status}", f"BOT_{status}"
    if int(bot.get("entries_paused") or 0) == 1:
        return "ENTRIES_PAUSED", "ENTRIES_PAUSED"
    from solana_alpha_lab.factory.trading_runtime_policy import (
        STATUS_INVALID,
        STATUS_VALID,
        resolve_current_policy,
    )

    current = resolve_current_policy(store, mode)
    if current["status"] == STATUS_INVALID:
        return "RUNTIME_POLICY_INVALID", "RUNTIME_POLICY_INVALID"
    policy = current.get("policy")
    if current["status"] == STATUS_VALID and policy is not None and not policy.get("new_entries_enabled"):
        return "BLOCK_NEW_ENTRIES_DISABLED", "NEW_ENTRIES_DISABLED"
    return None, None


def _append_exact_admission_event(store, *, event_type, bot_instance_id, position_id, payload, as_of):
    event_id = "ADMISSION-" + canonical_spec_sha256({"event_type": event_type, "payload": payload})
    previous = store.get_execution_event(event_id)
    if previous is not None:
        if (previous["event_type"], previous["bot_instance_id"], previous["position_id"], previous["payload"]) != (
            event_type, bot_instance_id, position_id, payload):
            raise PaperPlaneError("ADMISSION_EVALUATION_CONTENT_CONFLICT")
        return event_id, True
    store.append_execution_event(event_type=event_type, event_id=event_id,
        bot_instance_id=bot_instance_id, position_id=position_id, payload=payload, created_at=as_of)
    return event_id, False


def _signal_refusal(store, *, decision, lineage, bot, mode, as_of, reason_code,
                    position=None, risk_event_id=None, current_policy=None):
    policy = (current_policy or {}).get("policy")
    payload = {**_identity_fields(decision), **lineage, "outcome": "DENIED",
        "source_reason_code": decision["reason_code"], "reason_code": reason_code,
        "mode": mode, "evaluated_at": as_of, "bot_status": bot["status"],
        "entries_paused": int(bot.get("entries_paused") or 0),
        "state": None if position is None else position["state"],
        "cancel_reason_code": None if position is None else position.get("cancel_reason_code"),
        "risk_event_id": risk_event_id,
        "runtime_policy_status": (current_policy or {}).get("status"),
        "runtime_policy_revision": None if policy is None else policy.get("revision"),
        "runtime_policy_sha256": None if policy is None else policy.get("policy_sha256")}
    position_id = None if position is None else position["position_id"]
    event_id, replay = _append_exact_admission_event(store, event_type="SIGNAL_ADMISSION_DENIED",
        bot_instance_id=bot["bot_instance_id"], position_id=position_id, payload=payload, as_of=as_of)
    return {**payload, "opened": False, "position_id": position_id,
        "bot_instance_id": bot["bot_instance_id"], "evaluation_event_id": event_id, "idempotent": replay}


def accept_signal_decision(
    root: Path, store: PaperPlaneStore, *, strategy: Mapping[str, Any],
    signal_decision: Mapping[str, Any],
    known_activation_epochs: Mapping[str, Any] | set[str] | frozenset[str],
    mode: str = "PAPER", as_of: str | None = None, skip_fill: bool = False,
    ordinary_operating: bool = False,
) -> dict[str, Any]:
    """Legacy exception API; orchestration transactions use the outcome API."""
    outcome = accept_signal_decision_outcome(root, store, strategy=strategy,
        signal_decision=signal_decision, known_activation_epochs=known_activation_epochs,
        mode=mode, as_of=as_of, skip_fill=skip_fill, ordinary_operating=ordinary_operating)
    if outcome.get("outcome") == "DENIED":
        raise PaperPlaneError(outcome["reason_code"])
    return outcome


def accept_signal_decision_outcome(
    root: Path,
    store: PaperPlaneStore,
    *,
    strategy: Mapping[str, Any],
    signal_decision: Mapping[str, Any],
    known_activation_epochs: Mapping[str, Any] | set[str] | frozenset[str],
    mode: str = "PAPER",
    as_of: str | None = None,
    skip_fill: bool = False,
    ordinary_operating: bool = False,
) -> dict[str, Any]:
    """Return a normal refusal without aborting the caller's atomic transaction.

    Malformed/conflicting input, storage failures and unexpected exceptions still
    propagate. No exception catch or transaction behavior is changed here.
    """

    if mode not in {"PAPER", "SHADOW"}:
        raise PaperPlaneError("BOT_MODE_INVALID")
    if not as_of:
        raise PaperPlaneError("SIGNAL_AS_OF_REQUIRED")
    normalized = normalize_strategy(strategy)
    if normalized["runtime_path"] != "CANDIDATE_V1_1":
        raise PaperPlaneError("SIGNAL_DECISION_REQUIRES_V1_1")
    eligibility = strategy.get("mode_eligibility", {})
    if mode == "PAPER" and eligibility.get("paper") is not True:
        raise PaperPlaneError("PAPER_MODE_NOT_ELIGIBLE")
    if mode == "SHADOW" and eligibility.get("shadow") is not True:
        raise PaperPlaneError("SHADOW_MODE_NOT_ELIGIBLE")
    if eligibility.get("micro_live") is not False:
        raise PaperPlaneError("MICRO_LIVE_FORBIDDEN")
    decision = validate_signal_decision(root, signal_decision)
    if decision["strategy_id"] != strategy["strategy_id"]:
        raise PaperPlaneError("SIGNAL_STRATEGY_ID_MISMATCH")
    if decision["strategy_version"] != strategy["strategy_version"]:
        raise PaperPlaneError("SIGNAL_STRATEGY_VERSION_MISMATCH")
    resolve_activation_epoch(
        str(decision["activation_epoch_id"]),
        known_activation_epochs=known_activation_epochs,
    )
    decision_sha256 = canonical_spec_sha256(decision)
    as_of_dt = _parse_utc(as_of)
    decision_at = _parse_utc(decision["decision_at"])
    if (decision_at - as_of_dt).total_seconds() > SIGNAL_MAX_CLOCK_SKEW_SECONDS:
        raise PaperPlaneError("SIGNAL_DECISION_FROM_FUTURE")
    if _parse_utc(decision["first_reliable_available_at"]) > decision_at:
        if decision["action"] == "ENTER":
            raise PaperPlaneError("SIGNAL_FUTURE_AVAILABLE_ENTER_FORBIDDEN")
    lineage = {
        "signal_decision_sha256": decision_sha256,
        "evidence_refs": list(decision["evidence_refs"]),
        "source_hypothesis_refs": list(decision["source_hypothesis_refs"]),
        "first_reliable_available_at": decision["first_reliable_available_at"],
        "strategy_spec_sha256": strategy.get("spec_sha256"),
    }
    position_id = position_id_for_signal_decision(str(decision["signal_decision_id"]))
    action = str(decision["action"])
    if action != "ENTER":
        with store.immediate_write():
            if store.get_position(position_id) is not None:
                raise PaperPlaneError("SIGNAL_DECISION_IDEMPOTENCY_MISMATCH")
            event_id = "DECISION-" + str(decision["signal_decision_id"])
            previous = store.get_execution_event(event_id)
            if previous is not None:
                if previous["payload"].get("signal_decision_sha256") != decision_sha256:
                    raise PaperPlaneError("SIGNAL_DECISION_IDEMPOTENCY_MISMATCH")
                return {"opened": False, "action": action, "reason_code": decision["reason_code"],
                        "signal_decision_id": decision["signal_decision_id"], "position_id": None, "idempotent": True}
            store.append_execution_event(
            event_type="SIGNAL_DECISION_ACCEPTED",
            bot_instance_id=None,
            position_id=None,
            event_id=event_id,
            payload={
                **_identity_fields(decision),
                "strategy_id": strategy["strategy_id"],
                "strategy_version": strategy["strategy_version"],
                "opened": False,
                **lineage,
            },
        )
        return {
            "opened": False,
            "action": action,
            "reason_code": decision["reason_code"],
            "signal_decision_id": decision["signal_decision_id"],
            "position_id": None,
        }
    max_age = int(strategy["signal_input"]["max_age_seconds"])
    stale = (as_of_dt - decision_at).total_seconds() > max_age
    admitted_notional = Decimal(str(strategy["notional_policy"]["notional_usd"]))
    was_existing = False
    resume_only = False
    bot_instance_id = ""
    with store.immediate_write():
        existing = store.get_position(position_id)
        if existing is not None:
            stored = existing.get("signal_decision_sha256")
            if stored not in {None, ""} and str(stored) != decision_sha256:
                raise PaperPlaneError("SIGNAL_DECISION_IDEMPOTENCY_MISMATCH")
            if existing.get("activation_epoch_id") and str(existing["activation_epoch_id"]) != str(
                decision["activation_epoch_id"]
            ):
                raise PaperPlaneError("SIGNAL_ACTIVATION_EPOCH_MISMATCH")
            if existing.get("strategy_id") and str(existing["strategy_id"]) != str(
                decision["strategy_id"]
            ):
                raise PaperPlaneError("SIGNAL_POSITION_STRATEGY_MISMATCH")
            expected_bot_id = (
                f"BOT-{strategy['strategy_id']}-{strategy['strategy_version']}"
                f"-{mode}-{decision['activation_epoch_id']}"
            )
            if existing.get("bot_instance_id") and str(existing["bot_instance_id"]) != expected_bot_id:
                raise PaperPlaneError("SIGNAL_BOT_INSTANCE_MISMATCH")
        bot = store.start_bot(
            strategy,
            mode=mode,
            activation_epoch_id=str(decision["activation_epoch_id"]),
        )
        if stale and existing is None:
            return _signal_refusal(store, decision=decision, lineage=lineage, bot=bot,
                mode=mode, as_of=as_of, reason_code="SIGNAL_DECISION_STALE")
        if existing is not None:
            was_existing = True
            state = str(existing["state"])
            base = {
                "action": action,
                "reason_code": decision["reason_code"],
                "signal_decision_id": decision["signal_decision_id"],
                "position_id": position_id,
                "idempotent": True,
                "state": state,
                "bot_instance_id": bot["bot_instance_id"],
                "activation_epoch_id": decision["activation_epoch_id"],
            }
            if state == "OPEN":
                return {**base, "opened": True}
            if state in IN_FLIGHT_STATES:
                return {**base, "opened": False, "reconciliation_required": True}
            if state not in PRE_ATTEMPT_STATES:
                return {**base, "opened": state == "PARTIAL"}
            block_code, cancel_reason = _resume_block(store, bot, mode, stale=stale)
            if block_code is not None:
                cancelled = store.cancel_entry_intent(position_id, reason_code=str(cancel_reason))
                from solana_alpha_lab.factory.trading_runtime_policy import resolve_current_policy
                policy_used = block_code in {"RUNTIME_POLICY_INVALID", "BLOCK_NEW_ENTRIES_DISABLED"}
                return _signal_refusal(store, decision=decision, lineage=lineage, bot=bot,
                    mode=mode, as_of=as_of, reason_code=block_code, position=cancelled,
                    current_policy=resolve_current_policy(store, mode) if policy_used else None)
            else:
                frozen = existing.get("admitted_entry_notional_usd_dec")
                if frozen not in {None, ""}:
                    admitted_notional = Decimal(str(frozen))
                else:
                    from solana_alpha_lab.factory.trading_runtime_policy import (
                        STATUS_INVALID,
                        STATUS_VALID,
                        resolve_current_policy,
                    )

                    if str(resolve_current_policy(store, mode)["status"]) in {
                        STATUS_VALID,
                        STATUS_INVALID,
                    }:
                        raise PaperPlaneError("ADMISSION_BINDING_MISSING")
                resume_only = True
        if not resume_only:
            if str(bot.get("status")) in {"DRAINING", "STOPPED"}:
                return _signal_refusal(store, decision=decision, lineage=lineage, bot=bot,
                    mode=mode, as_of=as_of, reason_code=f"BOT_STATUS_BLOCKS_ENTRY:{bot['status']}")
            if int(bot.get("entries_paused") or 0) == 1:
                return _signal_refusal(store, decision=decision, lineage=lineage, bot=bot,
                    mode=mode, as_of=as_of, reason_code="ENTRIES_PAUSED")
            from solana_alpha_lab.factory.trading_runtime_policy import (
                evaluate_admission,
                resolve_current_policy,
            )

            current_policy = resolve_current_policy(store, mode)
            inventory = store.open_risk_inventory(
                mode=mode,
                strategy_id=str(strategy["strategy_id"]),
                mint=str(decision["mint"]),
                bot_instance_id=str(bot["bot_instance_id"]),
            )
            risk = evaluate_admission(
                mode=mode,
                strategy=strategy,
                bot=bot,
                mint=str(decision["mint"]),
                policy_status=str(current_policy["status"]),
                policy=current_policy.get("policy"),
                inventory=inventory,
            )
            if ordinary_operating and risk["decision"] == "ALLOW":
                from solana_alpha_lab.factory.trading_runtime_policy import enforce_operating_envelope
                operating_risk = enforce_operating_envelope(store, mode=mode,
                    admitted_notional_usd=risk["effective_entry_notional_usd_dec"])
                risk["ordinary_operating_envelope"] = operating_risk
                if operating_risk["decision"] != "ALLOW":
                    risk["decision"] = operating_risk["reason_code"]
                    risk["reason_codes"] = [operating_risk["reason_code"]]
            risk["signal_decision_id"] = decision["signal_decision_id"]
            risk_event_id, _ = _append_exact_admission_event(store,
                event_type="PRE_TRADE_RISK_SNAPSHOT",
                bot_instance_id=bot["bot_instance_id"],
                position_id=position_id if existing else None,
                payload={
                    **risk, **lineage, "evaluated_at": as_of,
                    **_identity_fields(decision),
                    "strategy_id": strategy["strategy_id"],
                    "strategy_version": strategy["strategy_version"],
                }, as_of=as_of,
            )
            if str(risk["decision"]) != "ALLOW":
                return _signal_refusal(store, decision=decision, lineage=lineage, bot=bot,
                    mode=mode, as_of=as_of, reason_code=str(risk["decision"]),
                    risk_event_id=risk_event_id, current_policy=current_policy)
            else:
                if existing is None:
                    store.open_position_from_signal(
                        bot_instance_id=bot["bot_instance_id"],
                        signal_decision=decision,
                        signal_kind="SHADOW_EXECUTABLE" if mode == "SHADOW" else "SIMULATED_FILL",
                        signal_decision_sha256=decision_sha256,
                        strategy_spec_sha256=(
                            None
                            if strategy.get("spec_sha256") in {None, ""}
                            else str(strategy.get("spec_sha256"))
                        ),
                    )
                admitted_notional = Decimal(str(risk["effective_entry_notional_usd_dec"]))
                store.freeze_admission_binding(
                    position_id,
                    admitted_entry_notional_usd_dec=format(admitted_notional, "f"),
                    strategy_requested_notional_usd_dec=str(risk["strategy_requested_notional_usd_dec"]),
                    admitted_fee_bps=int(strategy["notional_policy"]["fee_bps"]),
                    runtime_policy_mode=mode if current_policy.get("policy") else None,
                    runtime_policy_revision=(
                        None
                        if current_policy.get("policy") is None
                        else current_policy["policy"].get("revision")
                    ),
                    runtime_policy_sha256=(
                        None
                        if current_policy.get("policy") is None
                        else current_policy["policy"].get("policy_sha256")
                    ),
                )
                if ordinary_operating:
                    store._conn.execute("UPDATE positions SET ordinary_operating=1, ordinary_envelope_sha256=? WHERE position_id=?",
                        (operating_risk["envelope"]["envelope_sha256"], position_id))
                store.append_execution_event(
                    event_type="SIGNAL_DECISION_ACCEPTED",
                    bot_instance_id=bot["bot_instance_id"],
                    position_id=position_id,
                    payload={
                        **_identity_fields(decision),
                        "strategy_id": strategy["strategy_id"],
                        "strategy_version": strategy["strategy_version"],
                        "admitted_entry_notional_usd_dec": format(admitted_notional, "f"),
                        "runtime_policy_revision": None
                        if current_policy.get("policy") is None
                        else current_policy["policy"].get("revision"),
                        "runtime_policy_sha256": None
                        if current_policy.get("policy") is None
                        else current_policy["policy"].get("policy_sha256"),
                        **lineage,
                    },
                )
        bot_instance_id = bot["bot_instance_id"]
    if skip_fill:
        reserved = store.get_position(position_id)
        assert reserved is not None
        return {
            "opened": reserved["state"] == "OPEN",
            "action": action,
            "reason_code": decision["reason_code"],
            "signal_decision_id": decision["signal_decision_id"],
            "position_id": position_id,
            "idempotent": was_existing,
            "state": reserved["state"],
            "bot_instance_id": bot_instance_id,
            "activation_epoch_id": decision["activation_epoch_id"],
            "admitted_entry_notional_usd_dec": reserved.get("admitted_entry_notional_usd_dec"),
            "fill_deferred": True,
        }
    signal_kind = "SHADOW_EXECUTABLE" if mode == "SHADOW" else "SIMULATED_FILL"
    with store.immediate_write():
        before = store.get_position(position_id)
        if before is not None and str(before["state"]) in PRE_ATTEMPT_STATES:
            current_bot = store.get_bot(bot_instance_id)
            assert current_bot is not None
            final_block, cancel_reason = _resume_block(store, current_bot, mode, stale=stale)
            if final_block is not None:
                cancelled = store.cancel_entry_intent(position_id, reason_code=str(cancel_reason))
                return {
                    "opened": False, "action": "BLOCKED", "reason_code": final_block,
                    "signal_decision_id": decision["signal_decision_id"],
                    "position_id": position_id, "state": cancelled["state"],
                    "bot_instance_id": bot_instance_id, "idempotent": was_existing,
                }
        filled_now = before is None or str(before["state"]) != "OPEN"
        opened_id, realized = store.fill_paper_from_signal(
            bot_instance_id=bot_instance_id,
            signal_decision=decision,
            notional_usd=admitted_notional,
            signal_kind=signal_kind,
        )
        if filled_now:
            store.append_execution_event(
                event_type="EXECUTION_INTENT_CREATED",
                bot_instance_id=bot_instance_id,
                position_id=opened_id,
                payload={
                    **_identity_fields(decision),
                    "strategy_id": strategy["strategy_id"],
                    "strategy_version": strategy["strategy_version"],
                    "signal_kind": realized,
                    "mode": mode,
                },
            )
            store.append_execution_event(
                event_type="POSITION_TRANSITION",
                bot_instance_id=bot_instance_id,
                position_id=opened_id,
                payload={
                    **_identity_fields(decision),
                    "strategy_id": strategy["strategy_id"],
                    "strategy_version": strategy["strategy_version"],
                    "to_state": "OPEN",
                    "signal_kind": realized,
                },
            )
    refreshed = store.get_position(opened_id)
    assert refreshed is not None
    return {
        "opened": refreshed["state"] == "OPEN",
        "action": action,
        "reason_code": decision["reason_code"],
        "signal_decision_id": decision["signal_decision_id"],
        "position_id": opened_id,
        "idempotent": was_existing,
        "state": refreshed["state"],
        "realized_signal_kind": realized,
        "bot_instance_id": bot_instance_id,
        "activation_epoch_id": decision["activation_epoch_id"],
        "admitted_entry_notional_usd_dec": refreshed.get("admitted_entry_notional_usd_dec"),
    }


def accept_exit_decision(
    root: Path,
    store: PaperPlaneStore,
    *,
    strategy: Mapping[str, Any],
    exit_decision: Mapping[str, Any],
    known_activation_epochs: Mapping[str, Any] | set[str] | frozenset[str],
) -> dict[str, Any]:
    normalized = normalize_strategy(strategy)
    if normalized["runtime_path"] != "CANDIDATE_V1_1":
        raise PaperPlaneError("EXIT_DECISION_REQUIRES_V1_1")
    decision = validate_exit_decision(root, exit_decision)
    if decision["strategy_id"] != strategy["strategy_id"]:
        raise PaperPlaneError("EXIT_STRATEGY_ID_MISMATCH")
    if decision["strategy_version"] != strategy["strategy_version"]:
        raise PaperPlaneError("EXIT_STRATEGY_VERSION_MISMATCH")
    resolve_activation_epoch(
        str(decision["activation_epoch_id"]),
        known_activation_epochs=known_activation_epochs,
    )
    if _parse_utc(decision["first_reliable_available_at"]) > _parse_utc(decision["decision_at"]):
        if decision["action"] == "EXIT":
            raise PaperPlaneError("EXIT_FUTURE_AVAILABLE_FORBIDDEN")
    position = store.get_position(str(decision["position_id"]))
    if position is None:
        raise PaperPlaneError("POSITION_NOT_FOUND")
    if position.get("activation_epoch_id") and str(position["activation_epoch_id"]) != str(
        decision["activation_epoch_id"]
    ):
        raise PaperPlaneError("EXIT_ACTIVATION_EPOCH_MISMATCH")
    if position.get("strategy_id") and str(position["strategy_id"]) != str(decision["strategy_id"]):
        raise PaperPlaneError("EXIT_POSITION_STRATEGY_MISMATCH")
    label = position.get("strategy_version_label")
    if label and str(label) != str(decision["strategy_version"]):
        raise PaperPlaneError("EXIT_POSITION_VERSION_MISMATCH")
    result = store.apply_exit_decision(exit_decision=decision)
    result["exit_decision_id"] = decision["exit_decision_id"]
    result["fill_claimed"] = False
    return result


def begin_modeled_attempt(store: PaperPlaneStore, *, position_id: str, side: str,
                         mode: str, attempt_key: str, decision_at: str,
                         max_age_seconds: int, as_of: str,
                         ordinary_operating: bool = False) -> dict[str, Any]:
    """Persist before the external boundary. Replays never authorize another send."""
    if side not in {"ENTRY", "EXIT"} or mode not in {"PAPER", "SHADOW"}:
        raise PaperPlaneError("MODELED_ATTEMPT_SCOPE_INVALID")
    if not attempt_key or len(attempt_key) > 120:
        raise PaperPlaneError("MODELED_ATTEMPT_KEY_INVALID")
    identity = {"position_id": position_id, "side": side, "mode": mode, "attempt_key": attempt_key}
    attempt_id = "ATTEMPT-" + canonical_spec_sha256(identity).upper()
    with store.immediate_write():
        previous = store.get_execution_event(attempt_id)
        if previous is not None:
            return {**previous["payload"], "send_permitted": False, "idempotent": True}
        position = store.get_position(position_id)
        if position is None:
            raise PaperPlaneError("POSITION_NOT_FOUND")
        bot = store.get_bot(str(position["bot_instance_id"]))
        if bot is None or bot["mode"] != mode:
            raise PaperPlaneError("MODELED_ATTEMPT_MODE_MISMATCH")
        prior = [event for event in store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED",position_ids=[position_id])
                 if event["event_type"] == "MODELED_ATTEMPT_STARTED" and event["position_id"] == position_id
                 and event["payload"].get("side") == side]
        if prior:
            if side == "ENTRY":
                raise PaperPlaneError("ENTRY_ATTEMPT_ALREADY_EXISTS")
            last = store.get_execution_event("FINAL-" + prior[-1]["event_id"])
            permitted = last is not None and last["payload"]["outcome"] in {"NO_ROUTE", "REJECTED_BEFORE_SEND", "DROPPED_OR_EXPIRED_NOT_PROCESSED", "LANDED_FAILED"}
            if last is not None and last["payload"]["outcome"] == "PARTIAL" and last["payload"].get("schema_version") == "1.1":
                permitted = position.get("remaining_qty_dec") is not None and Decimal(str(position["remaining_qty_dec"])) > 0
            if not permitted:
                raise PaperPlaneError("ATTEMPT_RECONCILIATION_REQUIRED")
        state = str(position["state"])
        if side == "ENTRY":
            if state not in PRE_ATTEMPT_STATES:
                raise PaperPlaneError("ENTRY_ATTEMPT_STATE_INVALID")
            stale = (_parse_utc(as_of) - _parse_utc(decision_at)).total_seconds() > max_age_seconds
            if _parse_utc(as_of) < _parse_utc(decision_at):
                raise PaperPlaneError("MODELED_ATTEMPT_FROM_FUTURE")
            block, cancel = _resume_block(store, bot, mode, stale=stale)
            if block:
                store.cancel_entry_intent(position_id, reason_code=str(cancel))
                return {"send_permitted": False, "action": "BLOCKED", "reason_code": block,
                        "position_id": position_id, "state": "CANCELLED"}
            if ordinary_operating or position.get("ordinary_operating") == 1:
                from solana_alpha_lab.factory.trading_runtime_policy import enforce_operating_envelope
                safety = enforce_operating_envelope(store, mode=mode,
                    admitted_notional_usd=position.get("admitted_entry_notional_usd_dec"),
                    exclude_position_id=position_id)
                if safety["decision"] != "ALLOW":
                    store.cancel_entry_intent(position_id, reason_code="OPERATING_SAFETY_VETO")
                    return {"send_permitted": False, "action": "BLOCKED", "reason_code": safety["reason_code"],
                            "position_id": position_id, "state": "CANCELLED", "ordinary_operating_envelope": safety}
            if state == "WATCHED":
                store.transition(position_id, "SIGNALLED")
            if state in {"WATCHED", "SIGNALLED"}:
                store.transition(position_id, "INTENT_CREATED")
            store.transition(position_id, "ATTEMPTING")
        elif state not in {"EXIT_REQUIRED", "EXITING", "UNRESOLVED"}:
            raise PaperPlaneError("EXIT_ATTEMPT_REQUIRES_ORIGINATING_EXIT")
        if side == "EXIT":
            assert_quantity_inventory_witness(store, position)
            if position.get("entry_price_dec") is None:
                raise PaperPlaneError("EXIT_ATTEMPT_REQUIRES_ENTRY_RECONCILIATION")
            clocks = [decision_at]
            for event in store.filtered_execution_events(event_type="MODELED_RESULT_ACCEPTED",position_ids=[position_id]):
                if event["position_id"] == position_id and event["event_type"] == "MODELED_RESULT_ACCEPTED":
                    clocks.append(event["payload"]["result"]["observed_at"])
            if _parse_utc(as_of) < max(_parse_utc(clock) for clock in clocks):
                raise PaperPlaneError("MODELED_ATTEMPT_CAUSAL_CLOCK_INVALID")
        if side == "EXIT" and state == "EXIT_REQUIRED":
            store.transition(position_id, "EXITING")
        payload = {**identity, "attempt_id": attempt_id, "as_of": as_of,
                   "evidence_class": "PAPER_MODEL" if mode == "PAPER" else "SHADOW_QUOTE_MODEL"}
        if side == "EXIT" and position.get("remaining_qty_dec") is not None:
            payload.update(remaining_quantity=position["remaining_qty_dec"], quantity_unit="TOKEN_UNITS")
        store.append_execution_event(event_type="MODELED_ATTEMPT_STARTED", event_id=attempt_id,
                                     bot_instance_id=bot["bot_instance_id"], position_id=position_id,
                                     payload=payload, created_at=as_of)
        return {**payload, "send_permitted": True, "idempotent": False}


def accept_modeled_result(store: PaperPlaneStore, *, result: Mapping[str, Any]) -> dict[str, Any]:
    """Provider-neutral modeled result; append-only identity and atomic effect.

    UNKNOWN can acquire one later definitive result. A definitive result is
    immutable. Chargeable failure costs are retained separately from trade PnL.
    This boundary cannot claim an on-chain fill or accept signing material.
    """
    version = result.get("schema_version", "1.0")
    if version not in {"1.0", "1.1"}:
        raise PaperPlaneError("MODELED_RESULT_VERSION_UNSUPPORTED")
    allowed = {"attempt_id", "result_id", "outcome", "observed_at", "unit_price_usd", "filled_notional_usd", "chargeable_cost_usd"}
    if version == "1.1":
        allowed |= {"schema_version", "quantity_sold", "quantity_filled", "quantity_unit", "remaining_quantity", "fee_semantics"}
    if set(result) - allowed or not {"attempt_id", "result_id", "outcome", "observed_at"} <= set(result):
        raise PaperPlaneError("MODELED_RESULT_INVALID")
    outcome = result["outcome"]
    if outcome not in {"NO_ROUTE", "REJECTED_BEFORE_SEND", "DROPPED_OR_EXPIRED_NOT_PROCESSED", "LANDED_FAILED", "LANDED_SUCCESS", "PARTIAL", "UNKNOWN_REQUIRES_RECONCILIATION"}:
        raise PaperPlaneError("MODELED_RESULT_CLASS_UNSUPPORTED")
    if not isinstance(result["result_id"], str) or not result["result_id"] or len(result["result_id"]) > 120:
        raise PaperPlaneError("MODELED_RESULT_ID_INVALID")
    positive = outcome in {"LANDED_SUCCESS", "PARTIAL"}
    if version == "1.1" and positive:
        if result.get("quantity_unit") != "TOKEN_UNITS":
            raise PaperPlaneError("MODELED_QUANTITY_UNIT_UNSUPPORTED")
        if result.get("fee_semantics") not in {"SEPARATE_MODELED_FEE", "INCLUDED_IN_UNIT_PRICE"}:
            raise PaperPlaneError("MODELED_FEE_SEMANTICS_UNSUPPORTED")
    if not positive and any(result.get(field) is not None for field in ("quantity_sold", "quantity_filled", "remaining_quantity")):
        raise PaperPlaneError("NON_FILL_RESULT_HAS_FILL")
    if positive:
        for field in ("unit_price_usd", "filled_notional_usd"):
            if result.get(field) is not None:
                try:
                    value = Decimal(str(result[field]))
                    if not value.is_finite() or value <= 0:
                        raise ValueError()
                except (ValueError, ArithmeticError):
                    raise PaperPlaneError("MODELED_FILL_DETAILS_INVALID") from None
    if not positive and any(result.get(field) is not None for field in ("unit_price_usd", "filled_notional_usd")):
        raise PaperPlaneError("NON_FILL_RESULT_HAS_FILL")
    cost = result.get("chargeable_cost_usd")
    if cost is not None:
        try:
            value = Decimal(str(cost))
            if not value.is_finite() or value < 0:
                raise ValueError()
        except (ValueError, ArithmeticError):
            raise PaperPlaneError("MODELED_RESULT_COST_INVALID") from None
    with store.immediate_write():
        attempt = store.get_execution_event(str(result["attempt_id"]))
        if attempt is None or attempt["event_type"] != "MODELED_ATTEMPT_STARTED":
            raise PaperPlaneError("MODELED_ATTEMPT_UNRESOLVED")
        bound = attempt["payload"]
        position = store.get_position(bound["position_id"])
        if position is None:
            raise PaperPlaneError("POSITION_NOT_FOUND")
        if bound["side"] == "EXIT":
            assert_quantity_inventory_witness(store, position, pending_attempt_id=attempt["event_id"],
                force_quantity=version == "1.1" and positive)
        if _parse_utc(str(result["observed_at"])) < _parse_utc(bound["as_of"]):
            raise PaperPlaneError("MODELED_RESULT_CLOCK_INVALID")
        rid = "RESULT-" + canonical_spec_sha256({"result_id": result["result_id"]}).upper()
        previous = store.get_execution_event(rid)
        if previous is not None:
            if previous["payload"].get("result") != dict(result):
                raise PaperPlaneError("MODELED_RESULT_CONTENT_CONFLICT")
            return {"idempotent": True, "attempt_id": result["attempt_id"],
                    "position": store.get_position(bound["position_id"])}
        final_id = "FINAL-" + str(result["attempt_id"])
        if store.get_execution_event(final_id) is not None:
            raise PaperPlaneError("MODELED_RESULT_ALREADY_FINAL")
        # Observations describe a cumulative cost, never a replaceable estimate.
        # A later unknown total may retain uncertainty, but cannot erase known costs.
        prior_known_cost = Decimal("0")
        for event in store.filtered_execution_events(event_type="MODELED_RESULT_ACCEPTED",position_ids=[bound["position_id"]]):
            if event["event_type"] != "MODELED_RESULT_ACCEPTED":
                continue
            prior = event["payload"].get("result") or {}
            if prior.get("attempt_id") != result["attempt_id"]:
                continue
            if _parse_utc(str(result["observed_at"])) < _parse_utc(str(prior["observed_at"])):
                raise PaperPlaneError("MODELED_RESULT_CLOCK_REGRESSION")
            if prior.get("chargeable_cost_usd") is not None:
                try:
                    prior_value = Decimal(str(prior["chargeable_cost_usd"]))
                    if not prior_value.is_finite() or prior_value < 0:
                        raise ValueError()
                except (ValueError, ArithmeticError):
                    raise PaperPlaneError("MODELED_RESULT_SOURCE_CORRUPT") from None
                prior_known_cost = max(prior_known_cost, prior_value)
        if cost is not None and Decimal(str(cost)) < prior_known_cost:
            raise PaperPlaneError("MODELED_RESULT_COST_REGRESSION")
        position = store.get_position(bound["position_id"])
        if position is None:
            raise PaperPlaneError("POSITION_NOT_FOUND")
        if bound["side"] == "ENTRY":
            if positive:
                filled = result.get("filled_notional_usd")
                if filled is None or result.get("unit_price_usd") is None:
                    raise PaperPlaneError("MODELED_FILL_DETAILS_REQUIRED")
                admitted = Decimal(str(position["admitted_entry_notional_usd_dec"]))
                if (outcome == "PARTIAL") != (Decimal(str(filled)) < admitted):
                    raise PaperPlaneError("MODELED_FILL_AMOUNT_CLASS_CONFLICT")
                if version == "1.1":
                    if "quantity_sold" in result or "remaining_quantity" in result:
                        raise PaperPlaneError("MODELED_ENTRY_QUANTITY_FIELDS_INVALID")
                    _positive_model_decimal(result.get("quantity_filled"), "MODELED_QUANTITY_INVALID")
                store.apply_paper_entry_fill(position_id=bound["position_id"],
                    entry_unit_price_usd=str(result["unit_price_usd"]), entry_gross_notional_usd=str(filled),
                    fee_bps=int(position["admitted_fee_bps"]), mode=bound["mode"], reconcile_pending_close=True,
                    entry_quantity_units=str(result["quantity_filled"]) if version == "1.1" else None,
                    fee_semantics=str(result["fee_semantics"]) if version == "1.1" else None)
            elif outcome == "UNKNOWN_REQUIRES_RECONCILIATION":
                if position["state"] == "ATTEMPTING":
                    store.transition(bound["position_id"], "UNKNOWN")
            else:
                store.transition(bound["position_id"], "CANCELLED")
                store._conn.execute("UPDATE positions SET remaining_qty_dec='0', remaining_cost_basis_usd_dec='0', remaining_entry_fee_usd_dec='0' WHERE position_id=?", (bound["position_id"],))
        elif positive:
            if version == "1.0":
                if outcome == "PARTIAL" or result.get("filled_notional_usd") is not None:
                    raise PaperPlaneError("PARTIAL_EXIT_MODEL_UNSUPPORTED")
                if result.get("unit_price_usd") is None:
                    raise PaperPlaneError("MODELED_FILL_DETAILS_REQUIRED")
                store.apply_paper_exit_fill(position_id=bound["position_id"],
                    exit_unit_price_usd=str(result["unit_price_usd"]), mode=bound["mode"])
            else:
                if "filled_notional_usd" in result or "quantity_filled" in result:
                    raise PaperPlaneError("MODELED_EXIT_QUANTITY_FIELDS_INVALID")
                remaining = _positive_model_decimal(result.get("remaining_quantity"), "MODELED_QUANTITY_INVALID", allow_zero=True)
                if (outcome == "PARTIAL") != (remaining > 0):
                    raise PaperPlaneError("MODELED_EXIT_AMOUNT_CLASS_CONFLICT")
                store.apply_quantity_exit_fill(position_id=bound["position_id"], mode=bound["mode"],
                    quantity_sold=str(result.get("quantity_sold")), remaining_quantity=str(remaining),
                    exit_unit_price_usd=str(result.get("unit_price_usd")), fee_semantics=str(result["fee_semantics"]),
                    observed_at=str(result["observed_at"]), leg_id="LEG-" + rid)
        else:
            store.apply_paper_exit_fill(position_id=bound["position_id"], exit_unit_price_usd=None,
                                       mode=bound["mode"], unresolved=True)
        payload = {"result": dict(result), "evidence_class": bound["evidence_class"],
                   "chargeable_cost_status": "KNOWN" if cost is not None else "UNKNOWN"}
        store.append_execution_event(event_type="MODELED_RESULT_ACCEPTED", event_id=rid,
            bot_instance_id=attempt["bot_instance_id"], position_id=bound["position_id"],
            payload=payload, created_at=str(result["observed_at"]))
        if outcome != "UNKNOWN_REQUIRES_RECONCILIATION":
            store.append_execution_event(event_type="MODELED_ATTEMPT_FINAL", event_id=final_id,
                bot_instance_id=attempt["bot_instance_id"], position_id=bound["position_id"],
                payload={"outcome": outcome, "result_event_id": rid,
                         **({"schema_version": "1.1"} if version == "1.1" else {})}, created_at=str(result["observed_at"]))
        return {"idempotent": False, "attempt_id": result["attempt_id"],
                "position": store.get_position(bound["position_id"])}


def run_commissioning(
    root: Path,
    *,
    strategy_relatives: list[str],
    store_path: Path,
    cohort: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Drive both config-only strategies through the identical engine."""

    store = PaperPlaneStore(store_path)
    try:
        per_strategy: list[dict[str, Any]] = []
        for relative in strategy_relatives:
            strategy = load_strategy_version(root, relative)
            if str(strategy.get("schema_version", "1.0")) != "1.0":
                raise PaperPlaneError("COMMISSIONING_REQUIRES_V1_0")
            bot = store.start_bot(strategy, mode="PAPER")
            filled = 0
            skipped = 0
            for row in cohort:
                kind = signal_kind_for(strategy, row)
                if kind == "SIMULATED_FILL":
                    position_id = store.position_id_for(
                        bot_instance_id=bot["bot_instance_id"],
                        mint=str(row.get("mint")),
                        signal_kind="SIMULATED_FILL",
                    )
                    existing = store.get_position(position_id)
                    if existing is not None and existing["state"] == "RECONCILED":
                        filled += 1
                        continue
                    _, realized = store.fill_paper(
                        bot_instance_id=bot["bot_instance_id"],
                        mint=str(row.get("mint")),
                        notional_usd=Decimal(
                            str(strategy["notional_policy"]["notional_usd"])
                        ),
                    )
                    if realized == "SIMULATED_FILL":
                        filled += 1
                    store.transition(position_id, "EXIT_REQUIRED")
                    store.transition(position_id, "EXITING")
                    store.transition(position_id, "CLOSED")
                    store.transition(position_id, "RECONCILED")
                else:
                    skipped += 1
            per_strategy.append(
                {
                    "strategy_relative": relative,
                    "strategy_id": strategy["strategy_id"],
                    "strategy_version": strategy["strategy_version"],
                    "signal_feature": strategy["signal_rule"]["feature"],
                    "bot_instance_id": bot["bot_instance_id"],
                    "simulated_fills": filled,
                    "no_signal_or_unknown": skipped,
                }
            )
        return {
            "engine": "paper_plane_v1",
            "factory_core_python_changed": False,
            "per_strategy": per_strategy,
            "bot_instances": store.bots(),
            "positions": store.positions(),
        }
    finally:
        store.close()


def observe_shadow(
    store: PaperPlaneStore,
    *,
    bot_instance_id: str,
    mint: str,
    notional_usd: Decimal,
) -> tuple[str, str]:
    """SHADOW observation lifecycle. Never REAL_FILL."""

    with store.immediate_write():
        position_id = store.open_position(
            bot_instance_id=bot_instance_id,
            mint=mint,
            signal_kind="SHADOW_EXECUTABLE",
        )
        store.transition(position_id, "SIGNALLED")
        store.transition(position_id, "INTENT_CREATED")
        store.transition(position_id, "ATTEMPTING")
        store.transition(position_id, "OPEN")
        store._conn.execute(
            "UPDATE positions SET entered_notional_usd=? WHERE position_id=?",
            (float(notional_usd), position_id),
        )
        return position_id, "SHADOW_EXECUTABLE"


def run_shadow_tick(
    root: Path,
    *,
    strategy_relative: str,
    store_path: Path,
    cohort: list[Mapping[str, Any]],
    max_rows: int | None = None,
) -> dict[str, Any]:
    """One unattended SHADOW tick for a COMMISSIONING_ONLY StrategyVersion."""

    strategy = load_strategy_version(root, strategy_relative)
    if strategy.get("commissioning_only") is not True:
        raise PaperPlaneError("SHADOW_REQUIRES_COMMISSIONING_ONLY")
    if strategy.get("mode_eligibility", {}).get("shadow") is not True:
        raise PaperPlaneError("SHADOW_MODE_NOT_ELIGIBLE")
    if strategy.get("mode_eligibility", {}).get("micro_live") is not False:
        raise PaperPlaneError("MICRO_LIVE_FORBIDDEN")

    store = PaperPlaneStore(store_path)
    try:
        bot = store.start_bot(strategy, mode="SHADOW")
        observed = 0
        skipped = 0
        rows = list(cohort) if max_rows is None else list(cohort)[:max_rows]
        for row in rows:
            kind = signal_kind_for(strategy, row)
            if kind == "REAL_FILL":
                raise PaperPlaneError("REAL_FILL_FORBIDDEN_IN_SHADOW_TICK")
            # Config entry may name SIMULATED_FILL; SHADOW tick maps a positive
            # signal to SHADOW_EXECUTABLE observation without claiming fill.
            if kind in {"SIMULATED_FILL", "SHADOW_EXECUTABLE"}:
                position_id = store.position_id_for(
                    bot_instance_id=bot["bot_instance_id"],
                    mint=str(row.get("mint")),
                    signal_kind="SHADOW_EXECUTABLE",
                )
                existing = store.get_position(position_id)
                if existing is not None and existing["state"] == "RECONCILED":
                    observed += 1
                    continue
                _, realized = observe_shadow(
                    store,
                    bot_instance_id=bot["bot_instance_id"],
                    mint=str(row.get("mint")),
                    notional_usd=Decimal(str(strategy["notional_policy"]["notional_usd"])),
                )
                if realized != "SHADOW_EXECUTABLE":
                    raise PaperPlaneError("SHADOW_SIGNAL_DRIFT")
                store.transition(position_id, "EXIT_REQUIRED")
                store.transition(position_id, "EXITING")
                store.transition(position_id, "CLOSED")
                store.transition(position_id, "RECONCILED")
                observed += 1
            else:
                skipped += 1
        progress_at = _now()
        return {
            "engine": "paper_plane_v1",
            "mode": "SHADOW",
            "commissioning_only": True,
            "factory_core_python_changed": False,
            "strategy_relative": strategy_relative,
            "strategy_id": strategy["strategy_id"],
            "bot_instance_id": bot["bot_instance_id"],
            "shadow_observations": observed,
            "no_signal_or_unknown": skipped,
            "progress_at": progress_at,
            "bot_instances": store.bots(),
            "positions": store.positions(),
            "open_positions": sum(
                1 for item in store.positions() if item["state"] not in {"RECONCILED", "CLOSED"}
            ),
        }
    finally:
        store.close()
