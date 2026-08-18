"""Quote-native t0-friction → +15m quoted-liquidation mechanism look."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from solana_alpha_lab.pmf_quote_slice_one_shot import credential_free_preflight
from solana_alpha_lab.quote_native_evidence_fit_panel import (
    A24_MINT,
    EXPECTED_ENDPOINT,
    PanelError,
    ROUTE_ID,
    T21_MINTS,
    WRAPPED_SOL,
    bind_identity_sources,
    build_order_url,
    execute_observation,
)

ATOM_ID = "QUOTE_NATIVE_FRICTION_H900_FALSIFIER_V1"
AUTHORITY_PHRASE = (
    "OK QUOTE_NATIVE_FRICTION_H900_FALSIFIER_V1: Jupiter /swap/v2/order quote-only, "
    "taker omitted, execute forbidden, wallet/signer/transaction forbidden, "
    "cash cap $0, no retry/fallback, call cap 16, bind registry v7 route "
    "JUPITER-SOLANA-SWAP-V2-ORDER-001, unused T21 B/C plus R3 two mints only, "
    "one notional 0.01 SOL, t0 buy/reverse plus +15m sell, A24 and T21 A forbidden, "
    "+60m/+240m explicit gap no backfill, no live discovery"
)
CONFIG_RELATIVE = "configs/quote_native_friction_h900_falsifier_v1.yaml"
CONSUMED_RECEIPT = (
    "docs/evidence/quote_native_quoted_buy_h900_clock/"
    "a1_quote_native_quoted_buy_h900_clock_runtime_receipt_v1.json"
)
CONSUMED_ATOM = "QUOTE_NATIVE_QUOTED_BUY_H900_CLOCK_V1"
CALL_CAP = 16
T0_CALL_CAP = 8
H900 = 900
GAP_HORIZONS = (3600, 14400)
R3_MINTS = (
    "CWfuB1HDEp9W3xT3prBX8EPa1TQWKh1PmWFot3Gkpump",
    "8LRXPgAdhFktQzXjRVWgqWBWnMZTexjxsMrtQTQ6pump",
)
CELLS = (
    ("T21_R2_MINT_B", T21_MINTS[1], "10000000"),
    ("T21_R2_MINT_C", T21_MINTS[2], "10000000"),
    ("T21_R3_MINT_1", R3_MINTS[0], "10000000"),
    ("T21_R3_MINT_2", R3_MINTS[1], "10000000"),
)
FORBIDDEN_IDS = ("A24_POST_MIGRATION", "T21_R2_MINT_A")
FORBIDDEN_MINTS = (A24_MINT, T21_MINTS[0])
PROTOCOL_COMPARABLE = frozenset({"QUOTE_OBSERVED", "NO_ROUTE", "PROVIDER_TYPED_FAILURE"})
CONTINUABLE = frozenset({"SCHEDULED", "NOT_REACHED"})
SCHEDULE_COUNT = 20


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PanelError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _format_utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_decimal(value: object) -> Decimal | None:
    if type(value) is not str or not value.isdigit():
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    if parsed <= 0:
        return None
    return parsed


def validate_policy(policy: Mapping[str, Any], *, root: Path) -> None:
    authority = _mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    route = _mapping(policy.get("provider_route"), "ROUTE_INVALID")
    controls = _mapping(policy.get("execution_controls"), "CONTROLS_INVALID")
    cells = policy.get("cells")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_DRIFT")
    _require(authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_POLICY_DRIFT")
    _require(authority.get("capture_authorized") is True, "CAPTURE_NOT_AUTHORIZED")
    _require(authority.get("credential_reads") is False, "CREDENTIAL_READ_NOT_FORBIDDEN")
    _require(authority.get("dotenv_reads") is False, "DOTENV_READ_NOT_FORBIDDEN")
    _require(authority.get("execute") is False, "EXECUTE_NOT_FORBIDDEN")
    _require(authority.get("build") is False, "BUILD_NOT_FORBIDDEN")
    _require(authority.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(int(authority.get("call_cap", 0)) == CALL_CAP, "CALL_CAP_DRIFT")
    _require(int(authority.get("cash_cap_usd_cents", -1)) == 0, "CASH_CAP_DRIFT")
    _require(route.get("route_id") == ROUTE_ID, "ROUTE_ID_DRIFT")
    _require(route.get("endpoint") == EXPECTED_ENDPOINT, "ENDPOINT_DRIFT")
    _require(route.get("method") == "GET", "METHOD_DRIFT")
    _require(int(policy.get("observable_horizon_seconds", 0)) == H900, "H900_DRIFT")
    _require(
        tuple(int(item) for item in policy.get("gap_horizon_seconds") or []) == GAP_HORIZONS,
        "GAP_HORIZON_DRIFT",
    )
    _require(int(policy.get("lateness_slack_seconds", 0)) == 120, "SLACK_DRIFT")
    _require(isinstance(cells, list) and len(cells) == 4, "CELL_COUNT_DRIFT")
    observed: list[tuple[str, str, str]] = []
    for raw in cells:
        cell = _mapping(raw, "CELL_INVALID")
        _require(cell.get("source_kind") == "GIT_FROZEN", "LIVE_DISCOVERY_NOT_FORBIDDEN")
        identity_id = str(cell["identity_id"])
        mint = str(cell["mint"])
        notional = str(cell["notional_atomic"])
        _require(identity_id not in FORBIDDEN_IDS, "A24_OR_T21A_SELECTED")
        _require(mint not in FORBIDDEN_MINTS, "A24_OR_T21A_SELECTED")
        _require(notional == "10000000", "NOTIONAL_DRIFT")
        source_path = root / str(cell.get("source_path"))
        _require(source_path.is_file(), "IDENTITY_SOURCE_MISSING")
        _require(mint in source_path.read_text(encoding="utf-8"), "IDENTITY_SOURCE_DRIFT")
        observed.append((identity_id, mint, notional))
    _require(tuple(observed) == CELLS, "CELL_DRIFT")
    _require(controls.get("retries") == 0, "RETRY_NOT_FORBIDDEN")
    _require(controls.get("fallback") is False, "FALLBACK_NOT_FORBIDDEN")
    _require(controls.get("persist_transaction_bytes") is False, "TX_PERSIST_NOT_FORBIDDEN")
    _require(controls.get("live_market_discovery") is False, "LIVE_DISCOVERY_NOT_FORBIDDEN")
    _require(controls.get("second_provider") is False, "SECOND_PROVIDER_FORBIDDEN")
    _require(controls.get("background_scheduler") is False, "BACKGROUND_SCHEDULER")
    _require(int(controls.get("provider_requests_max", 0)) == CALL_CAP, "REQUEST_BUDGET_DRIFT")
    _require(int(controls.get("t0_provider_requests_max", 0)) == T0_CALL_CAP, "T0_BUDGET_DRIFT")
    _require(str(policy.get("consumed_outcome_receipt")) == CONSUMED_RECEIPT, "CONSUMED_PATH_DRIFT")
    _require((root / CONSUMED_RECEIPT).is_file(), "CONSUMED_RECEIPT_MISSING")


def build_schedule(policy: Mapping[str, Any], *, panel_started_at: datetime) -> list[dict[str, object]]:
    started = _format_utc(panel_started_at)
    slack = int(policy["lateness_slack_seconds"])
    rows: list[dict[str, object]] = []
    for cell in policy["cells"]:
        mapped = _mapping(cell, "CELL_INVALID")
        identity_id = str(mapped["identity_id"])
        mint = str(mapped["mint"])
        notional = str(mapped["notional_atomic"])
        buy_id = f"{identity_id}:{notional}:BUY_T0"
        rows.append(
            {
                "observation_id": buy_id,
                "identity_id": identity_id,
                "mint": mint,
                "kind": "BUY_T0",
                "wave": "t0",
                "input_mint": WRAPPED_SOL,
                "output_mint": mint,
                "amount": notional,
                "parent_id": None,
                "due_at": started,
                "horizon_seconds": 0,
                "post_migration_status": str(mapped["post_migration_status"]),
            }
        )
        rows.append(
            {
                "observation_id": f"{identity_id}:{notional}:REVERSE_T0",
                "identity_id": identity_id,
                "mint": mint,
                "kind": "REVERSE_T0",
                "wave": "t0",
                "input_mint": mint,
                "output_mint": WRAPPED_SOL,
                "amount": None,
                "parent_id": buy_id,
                "due_at": started,
                "horizon_seconds": 0,
                "post_migration_status": str(mapped["post_migration_status"]),
            }
        )
        h900_due = panel_started_at.astimezone(UTC) + timedelta(seconds=H900)
        rows.append(
            {
                "observation_id": f"{identity_id}:{notional}:SELL_H900",
                "identity_id": identity_id,
                "mint": mint,
                "kind": "SELL_H900",
                "wave": "horizon",
                "input_mint": mint,
                "output_mint": WRAPPED_SOL,
                "amount": None,
                "parent_id": buy_id,
                "due_at": _format_utc(h900_due),
                "horizon_seconds": H900,
                "lateness_slack_seconds": slack,
                "post_migration_status": str(mapped["post_migration_status"]),
            }
        )
        for horizon in GAP_HORIZONS:
            due = panel_started_at.astimezone(UTC) + timedelta(seconds=horizon)
            rows.append(
                {
                    "observation_id": f"{identity_id}:{notional}:SELL_H{horizon}",
                    "identity_id": identity_id,
                    "mint": mint,
                    "kind": f"SELL_H{horizon}",
                    "wave": "gap",
                    "input_mint": mint,
                    "output_mint": WRAPPED_SOL,
                    "amount": None,
                    "parent_id": buy_id,
                    "due_at": _format_utc(due),
                    "horizon_seconds": horizon,
                    "terminal": "EXPLICIT_GAP",
                    "consumed_call": False,
                    "post_migration_status": str(mapped["post_migration_status"]),
                }
            )
    _require(len(rows) == SCHEDULE_COUNT, "SCHEDULE_COUNT_DRIFT")
    return rows


def _ratio(out_amount: object, in_amount: object) -> str | None:
    out_value = _atomic_decimal(out_amount)
    in_value = _atomic_decimal(in_amount)
    if out_value is None or in_value is None:
        return None
    return str(out_value / in_value - Decimal(1))


def score_mechanism(observations: list[Mapping[str, Any]]) -> dict[str, object]:
    by_identity: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in observations:
        identity_id = str(row.get("identity_id") or "")
        kind = str(row.get("kind") or "")
        if not identity_id or kind not in {"BUY_T0", "REVERSE_T0", "SELL_H900"}:
            continue
        by_identity.setdefault(identity_id, {})[kind] = row
    cells: list[dict[str, object]] = []
    complete: list[tuple[str, Decimal, Decimal, bool]] = []
    h900_observed = 0
    h900_no_route = 0
    for identity_id, kinds in by_identity.items():
        buy = kinds.get("BUY_T0")
        reverse = kinds.get("REVERSE_T0")
        sell = kinds.get("SELL_H900")
        buy_ok = isinstance(buy, Mapping) and buy.get("terminal") == "QUOTE_OBSERVED"
        reverse_ok = isinstance(reverse, Mapping) and reverse.get("terminal") == "QUOTE_OBSERVED"
        sell_ok = isinstance(sell, Mapping) and sell.get("terminal") == "QUOTE_OBSERVED"
        buy_in = buy.get("amount") if isinstance(buy, Mapping) else None
        reverse_quote = reverse.get("quote") if isinstance(reverse, Mapping) else None
        sell_quote = sell.get("quote") if isinstance(sell, Mapping) else None
        reverse_out = reverse_quote.get("out_amount") if isinstance(reverse_quote, Mapping) else None
        sell_out = sell_quote.get("out_amount") if isinstance(sell_quote, Mapping) else None
        x_value = _ratio(reverse_out, buy_in) if buy_ok and reverse_ok else None
        y_value = _ratio(sell_out, buy_in) if buy_ok and sell_ok else None
        sell_terminal = str(sell.get("terminal") or "") if isinstance(sell, Mapping) else ""
        if sell_ok:
            h900_observed += 1
        if sell_terminal == "NO_ROUTE":
            h900_no_route += 1
        y_equals_x = (
            Decimal(x_value) == Decimal(y_value)
            if x_value is not None and y_value is not None
            else None
        )
        cell = {
            "identity_id": identity_id,
            "buy_terminal": str(buy.get("terminal") or "") if isinstance(buy, Mapping) else "",
            "reverse_terminal": str(reverse.get("terminal") or "") if isinstance(reverse, Mapping) else "",
            "h900_terminal": sell_terminal,
            "x_quoted_roundtrip_friction": x_value,
            "y_quoted_liquidation_recovery": y_value,
            "x_status": "OBSERVED" if x_value is not None else "MISSING",
            "y_status": "OBSERVED" if y_value is not None else "MISSING",
            "y_equals_x": y_equals_x,
            "router": (buy.get("quote") or {}).get("router") if isinstance(buy, Mapping) else None,
            "price_impact_pct": (buy.get("quote") or {}).get("price_impact_pct") if isinstance(buy, Mapping) else None,
            "fee_bps": (buy.get("quote") or {}).get("fee_bps") if isinstance(buy, Mapping) else None,
        }
        cells.append(cell)
        if x_value is not None and y_value is not None:
            complete.append((identity_id, Decimal(x_value), Decimal(y_value), bool(y_equals_x)))
    time_separated = [item for item in complete if not item[3]]
    concordant = 0
    discordant = 0
    tied = 0
    for index, (_, x_left, y_left, _) in enumerate(time_separated):
        for _, x_right, y_right, _ in time_separated[index + 1 :]:
            x_delta = x_left - x_right
            y_delta = y_left - y_right
            if x_delta == 0 or y_delta == 0:
                tied += 1
                continue
            if (x_delta > 0 and y_delta > 0) or (x_delta < 0 and y_delta < 0):
                concordant += 1
            else:
                discordant += 1
    comparable_pairs = concordant + discordant
    concordance_rate = (
        str(Decimal(concordant) / Decimal(comparable_pairs)) if comparable_pairs else None
    )
    y_equals_x_count = sum(1 for item in complete if item[3])
    if len(complete) < 2 and h900_observed == 0 and h900_no_route >= 1:
        verdict = "SAMPLE_INVALID_ROUTE_DOMINATED"
    elif len(time_separated) < 2 or comparable_pairs == 0:
        verdict = "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"
    elif concordant > discordant:
        verdict = "DIRECTIONAL_HINT_NOT_CONFIRMATION"
    else:
        verdict = "MECHANISM_NOT_SUPPORTED_ON_THIS_SAMPLE"
    non_claims = [
        "NOT_NETRETURN",
        "NOT_ALPHA",
        "NOT_LIVE_UNIVERSE",
        "NO_THRESHOLD_FIT",
        "NO_FAMILY_CLOSE_ON_SAMPLE_INVALID",
    ]
    if y_equals_x_count:
        non_claims.extend(
            ["NO_TIME_SEPARATED_MECHANISM_ON_Y_EQUALS_X", "NO_MOVE_2_EARNED"]
        )
    return {
        "expected_direction": "more_negative_t0_roundtrip_friction_ranks_more_negative_h900_quoted_recovery",
        "complete_xy_count": len(complete),
        "time_separated_complete_xy_count": len(time_separated),
        "y_equals_x_count": y_equals_x_count,
        "concordant_pairs": concordant,
        "discordant_pairs": discordant,
        "tied_pairs": tied,
        "concordance_rate": concordance_rate,
        "h900_quote_observed_count": h900_observed,
        "h900_no_route_count": h900_no_route,
        "verdict": verdict,
        "family_close": False,
        "cells": cells,
        "non_claims": non_claims,
    }


def _ticking_clock(start: datetime) -> Callable[[], datetime]:
    state = {"n": 0}

    def _tick() -> datetime:
        current = start + timedelta(seconds=state["n"])
        state["n"] += 1
        return current

    return _tick


def _halted_remainder(row: Mapping[str, Any], *, results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    recorded = dict(results.get(str(row["observation_id"])) or row)
    recorded["consumed_call"] = False
    kind = str(row.get("kind") or "")
    if str(row.get("wave")) == "gap" or str(recorded.get("terminal")) == "EXPLICIT_GAP":
        recorded["terminal"] = "EXPLICIT_GAP"
        return recorded
    if kind == "SELL_H900" and str(recorded.get("terminal") or "SCHEDULED") == "SCHEDULED":
        recorded["terminal"] = "SCHEDULED"
        return recorded
    parent = results.get(str(row.get("parent_id") or "")) if row.get("parent_id") else None
    if kind != "BUY_T0" and isinstance(parent, Mapping):
        parent_terminal = str(parent.get("terminal") or "")
        if parent.get("consumed_call") and parent_terminal != "QUOTE_OBSERVED":
            recorded["terminal"] = "SKIPPED_NO_ENTRY"
            recorded["quote"] = None
            return recorded
    if kind == "SELL_H900":
        recorded["terminal"] = "SCHEDULED"
        return recorded
    recorded["terminal"] = "NOT_REACHED"
    return recorded


def _require_schedule_matches_cells(schedule: list[Mapping[str, Any]]) -> None:
    seen: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    for row in schedule:
        identity_id = str(row.get("identity_id") or "")
        mint = str(row.get("mint") or "")
        _require(identity_id not in FORBIDDEN_IDS, "A24_OR_T21A_SELECTED")
        _require(mint not in FORBIDDEN_MINTS, "A24_OR_T21A_SELECTED")
        if identity_id not in seen_ids:
            seen_ids.add(identity_id)
            seen.append((identity_id, mint))
        if str(row.get("kind") or "") == "BUY_T0":
            _require(str(row.get("amount") or "") == "10000000", "NOTIONAL_DRIFT")
    _require(tuple(seen) == tuple((identity_id, mint) for identity_id, mint, _ in CELLS), "CELL_DRIFT")


def run_wave(
    policy: Mapping[str, Any],
    *,
    root: Path,
    wave: str,
    now: datetime,
    opener: object | None = None,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    prior_receipt: Mapping[str, Any] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    validate_policy(policy, root=root)
    _require(wave in {"t0", "due"}, "WAVE_INVALID")
    if wave == "due":
        _require(isinstance(prior_receipt, Mapping), "PRIOR_RECEIPT_REQUIRED")
        assert prior_receipt is not None
        _require(prior_receipt.get("atom_id") != CONSUMED_ATOM, "CONSUMED_H900_OUTCOME_REUSED")
        _require(prior_receipt.get("atom_id") == ATOM_ID, "OLD_DUE_AT_REBUILT_OR_OLD_RECEIPT_MUTATED")
    bindings = bind_identity_sources(root)
    started_at = now.astimezone(UTC)
    tick = clock or _ticking_clock(started_at)
    slack = int(policy["lateness_slack_seconds"])
    prior_requests = 0
    if wave == "due":
        assert prior_receipt is not None
        raw_schedule = prior_receipt.get("observations")
        _require(isinstance(raw_schedule, list) and len(raw_schedule) == SCHEDULE_COUNT, "PRIOR_SCHEDULE_INVALID")
        schedule = [dict(item) for item in raw_schedule if isinstance(item, Mapping)]
        _require(len(schedule) == SCHEDULE_COUNT, "SCHEDULE_COUNT_DRIFT")
        _require_schedule_matches_cells(schedule)
        prior_requests = int(prior_receipt.get("provider_requests", 0))
        _require(prior_requests >= 0, "PRIOR_REQUESTS_INVALID")
    else:
        schedule = build_schedule(policy, panel_started_at=started_at)
    preflight = dict(
        preflight_fn(
            {
                "provider_route": {
                    "endpoint": EXPECTED_ENDPOINT,
                    "host": "api.jup.ag",
                    "method": "GET",
                }
            },
            observed_at=_format_utc(started_at),
        )
    )
    _require(preflight.get("credential_reads") == 0, "PREFLIGHT_CREDENTIAL_READ_DRIFT")
    results: dict[str, dict[str, Any]] = {}
    selected_ids: list[str] = []
    for row in schedule:
        observation_id = str(row["observation_id"])
        due_at = datetime.fromisoformat(str(row["due_at"]).replace("Z", "+00:00"))
        terminal = row.get("terminal")
        already_consumed = bool(row.get("consumed_call")) or (
            terminal not in {None, ""} and str(terminal) not in CONTINUABLE
        )
        parent = results.get(str(row.get("parent_id") or "")) if row.get("parent_id") else None
        parent_quoted = isinstance(parent, Mapping) and parent.get("terminal") == "QUOTE_OBSERVED"
        if wave == "t0":
            selected = str(row["wave"]) == "t0" and not already_consumed
        else:
            late = started_at > due_at + timedelta(seconds=slack)
            selected = (
                str(row["kind"]) == "SELL_H900"
                and str(row["wave"]) == "horizon"
                and not already_consumed
                and str(terminal or "SCHEDULED") in CONTINUABLE
                and due_at <= started_at
                and not late
                and parent_quoted
            )
            if (
                str(row["kind"]) == "SELL_H900"
                and str(terminal or "SCHEDULED") in CONTINUABLE
                and parent_quoted
                and late
            ):
                row["terminal"] = "MISSED_OFFSET"
                row["consumed_call"] = False
        if selected:
            selected_ids.append(observation_id)
        elif wave == "t0" and str(row["wave"]) == "horizon":
            row["terminal"] = "SCHEDULED"
            row["consumed_call"] = False
        elif wave == "t0" and str(row["wave"]) == "gap":
            row["terminal"] = "EXPLICIT_GAP"
            row["consumed_call"] = False
        results[observation_id] = dict(row)

    provider_requests = 0
    stop_code: str | None = None
    comparable_identities: list[str] = []
    quoted_cells: list[str] = []
    remaining_cap = (T0_CALL_CAP if wave == "t0" else CALL_CAP) - prior_requests
    _require(remaining_cap >= 0, "CALL_CAP_EXCEEDED")
    halted = False
    for row in schedule:
        observation_id = str(row["observation_id"])
        if observation_id not in selected_ids:
            continue
        if halted:
            results[observation_id] = _halted_remainder(row, results=results)
            continue
        parent = results.get(str(row["parent_id"])) if row.get("parent_id") else None
        amount = row.get("amount")
        if row["kind"] != "BUY_T0":
            parent_quote = parent.get("quote") if parent else None
            parent_ok = (
                isinstance(parent, Mapping)
                and parent.get("terminal") == "QUOTE_OBSERVED"
                and isinstance(parent_quote, Mapping)
                and type(parent_quote.get("out_amount")) is str
                and bool(parent_quote.get("out_amount"))
            )
            if not parent_ok:
                results[observation_id] = {
                    **row,
                    "terminal": "SKIPPED_NO_ENTRY",
                    "consumed_call": False,
                    "quote": None,
                }
                continue
            amount = parent_quote["out_amount"]
        if provider_requests >= remaining_cap:
            stop_code = "CALL_CAP_EXCEEDED"
            halted = True
            results[observation_id] = _halted_remainder(row, results=results)
            continue
        request = {
            "input_mint": str(row["input_mint"]),
            "output_mint": str(row["output_mint"]),
            "amount": str(amount),
        }
        observed_at = tick()
        observed = execute_observation(policy, request, opener=opener)
        provider_requests += 1
        terminal = str(observed["terminal"])
        identity_id = str(row["identity_id"])
        if identity_id not in comparable_identities and terminal in PROTOCOL_COMPARABLE:
            comparable_identities.append(identity_id)
        if str(row["kind"]) == "BUY_T0" and terminal == "QUOTE_OBSERVED":
            quoted_cells.append(observation_id)
        body = observed.get("body")
        results[observation_id] = {
            **row,
            "amount": request["amount"],
            "observed_at": _format_utc(observed_at),
            "terminal": terminal,
            "terminal_error": observed.get("terminal_error"),
            "transport": observed.get("transport"),
            "quote": observed.get("quote"),
            "raw_sha256": hashlib.sha256(body).hexdigest() if isinstance(body, (bytes, bytearray)) else None,
            "body": body,
            "consumed_call": True,
        }
        if terminal in {"CREDENTIAL_REQUIRED_NOT_AUTHORIZED", "PANEL_PROTOCOL_FAIL"}:
            stop_code = terminal
            halted = True
            continue
        if terminal in {"RATE_LIMITED", "TRANSPORT_OR_QUOTE_UNKNOWN"}:
            stop_code = (
                "RATE_LIMIT_STOPPED_REMAINING"
                if terminal == "RATE_LIMITED"
                else "TRANSPORT_STOPPED_REMAINING"
            )
            halted = True

    for item in results.values():
        identity_id = str(item["identity_id"])
        terminal = str(item.get("terminal") or "")
        if identity_id not in comparable_identities and terminal in PROTOCOL_COMPARABLE:
            comparable_identities.append(identity_id)
        if str(item.get("kind")) == "BUY_T0" and terminal == "QUOTE_OBSERVED":
            if str(item["observation_id"]) not in quoted_cells:
                quoted_cells.append(str(item["observation_id"]))

    observations = []
    raw_bodies: dict[str, bytes] = {}
    for row in schedule:
        recorded = dict(results[str(row["observation_id"])])
        body = recorded.pop("body", None)
        if isinstance(body, (bytes, bytearray)):
            raw_bodies[str(row["observation_id"])] = bytes(body)
        observations.append(recorded)
    mechanism = score_mechanism(observations)
    y_equals_x_count = int(mechanism.get("y_equals_x_count") or 0)

    h900_missed = any(str(item.get("terminal")) == "MISSED_OFFSET" for item in observations)
    t0_buys_quoted = sum(
        1
        for item in observations
        if str(item.get("kind")) == "BUY_T0" and str(item.get("terminal")) == "QUOTE_OBSERVED"
    )
    if stop_code in {None, "RATE_LIMIT_STOPPED_REMAINING", "TRANSPORT_STOPPED_REMAINING"}:
        if wave == "due" and h900_missed and mechanism["h900_quote_observed_count"] == 0:
            stop_code = "H900_MISSED_OFFSET"
        elif wave == "due":
            stop_code = str(mechanism["verdict"])
        elif wave == "t0" and t0_buys_quoted == 4:
            stop_code = "T0_FRICTION_CLOCK_ARMED"
        elif stop_code == "RATE_LIMIT_STOPPED_REMAINING":
            stop_code = "PANEL_RATE_LIMITED"
        elif stop_code == "TRANSPORT_STOPPED_REMAINING":
            stop_code = "PANEL_TRANSPORT_UNKNOWN"
        elif wave == "t0" and t0_buys_quoted < 2:
            stop_code = "SECOND_IDENTITY_PROTOCOL_FAIL"
        else:
            stop_code = "PANEL_PROTOCOL_FAIL"

    return {
        "schema": "smial.quote-native-friction-h900-falsifier.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "hypothesis_id": "HYP-RC003-QUOTE-FRICTION-H900-V1",
        "route_id": ROUTE_ID,
        "owner_phrase": AUTHORITY_PHRASE,
        "terminal_outcome": stop_code,
        "started_at": _format_utc(started_at),
        "panel_started_at": (
            str(prior_receipt.get("panel_started_at") or prior_receipt.get("started_at"))
            if wave == "due" and prior_receipt is not None
            else _format_utc(started_at)
        ),
        "wave": wave,
        "identity_bindings": bindings,
        "preflight": preflight,
        "provider_requests": prior_requests + provider_requests,
        "new_provider_requests": provider_requests,
        "retries": 0,
        "fallbacks": 0,
        "credential_reads": 0,
        "execute_calls": 0,
        "comparable_identities": comparable_identities,
        "quoted_buy_ids": quoted_cells,
        "mechanism": mechanism,
        "limitations": [code for code in (
            "RATE_LIMIT_STOPPED_REMAINING_CELLS" if any(
                item.get("terminal") == "RATE_LIMITED" for item in results.values()
            ) else "",
            "STALE_OUTCOME_BLIND_T21_UNUSED_NOT_LIVE_UNIVERSE",
            "H3600_H14400_EXPLICIT_GAP_NO_BACKFILL",
            "Y_EQUALS_X_ON_COMPLETE_CELLS_QUOTE_UNCHANGED_OVER_900S" if y_equals_x_count else "",
        ) if code],
        "observations": observations,
        "raw_bodies": raw_bodies,
        "non_claims": [
            "NO_EXECUTE",
            "NO_TAKER_OR_SIGNER",
            "NO_TRANSACTION_BYTES_IN_GIT",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_CANONICAL_DONE",
            "NO_H13_OR_H02_TRIAL",
            "NO_LIVE_UNIVERSE",
            "NO_THRESHOLD_FIT",
            "NO_A24_OR_T21A_SAMPLE",
            "NO_H3600_OR_H14400_OBSERVATION",
            "NO_FAMILY_CLOSE_ON_SAMPLE_INVALID",
            *(
                ["NO_TIME_SEPARATED_MECHANISM_ON_Y_EQUALS_X", "NO_MOVE_2_EARNED"]
                if y_equals_x_count
                else []
            ),
        ],
    }
