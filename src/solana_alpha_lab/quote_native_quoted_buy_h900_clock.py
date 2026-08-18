"""New-clock quote-native +15m panel for already-quoted buys only."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

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

ATOM_ID = "QUOTE_NATIVE_QUOTED_BUY_H900_CLOCK_V1"
AUTHORITY_PHRASE = (
    "OK QUOTE_NATIVE_QUOTED_BUY_H900_CLOCK_V1: Jupiter /swap/v2/order quote-only, "
    "taker omitted, execute forbidden, wallet/signer/transaction forbidden, "
    "cash cap $0, no retry/fallback, call cap 16, bind registry v7 route "
    "JUPITER-SOLANA-SWAP-V2-ORDER-001, new clock A24 both notionals plus "
    "T21_R2_MINT_A 0.01 SOL only, t0 plus +15m only in this session, +60m and "
    "+240m explicit gap no backfill, leftover B/C and 0.001 forbidden, "
    "old due_at not rebuilt"
)
CONFIG_RELATIVE = "configs/quote_native_quoted_buy_h900_clock_v1.yaml"
PRIOR_PANEL_RECEIPT = (
    "docs/evidence/quote_native_evidence_fit_panel/"
    "a1_quote_native_evidence_fit_panel_runtime_receipt_v1.json"
)
OLD_PANEL_ATOM = "QUOTE_NATIVE_EVIDENCE_FIT_PANEL_V1"
CALL_CAP = 16
T0_CALL_CAP = 6
H900 = 900
GAP_HORIZONS = (3600, 14400)
CELLS = (
    ("A24_POST_MIGRATION", A24_MINT, "10000000"),
    ("A24_POST_MIGRATION", A24_MINT, "1000000"),
    ("T21_R2_MINT_A", T21_MINTS[0], "10000000"),
)
FORBIDDEN_IDS = ("T21_R2_MINT_B", "T21_R2_MINT_C")
PROTOCOL_COMPARABLE = frozenset({"QUOTE_OBSERVED", "NO_ROUTE", "PROVIDER_TYPED_FAILURE"})
CONTINUABLE = frozenset({"SCHEDULED", "NOT_REACHED"})


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
    _require(isinstance(cells, list) and len(cells) == 3, "CELL_COUNT_DRIFT")
    observed: list[tuple[str, str, str]] = []
    for raw in cells:
        cell = _mapping(raw, "CELL_INVALID")
        _require(cell.get("source_kind") == "GIT_FROZEN", "LIVE_DISCOVERY_NOT_FORBIDDEN")
        identity_id = str(cell["identity_id"])
        mint = str(cell["mint"])
        notional = str(cell["notional_atomic"])
        _require(identity_id not in FORBIDDEN_IDS, "LEFTOVER_B_C_OR_T21A_001")
        _require(not (identity_id == "T21_R2_MINT_A" and notional == "1000000"), "LEFTOVER_B_C_OR_T21A_001")
        source_path = root / str(cell.get("source_path"))
        _require(source_path.is_file(), "IDENTITY_SOURCE_MISSING")
        _require(mint in source_path.read_text(encoding="utf-8"), "IDENTITY_SOURCE_DRIFT")
        observed.append((identity_id, mint, notional))
    _require(tuple(observed) == CELLS, "CELL_DRIFT")
    _require(controls.get("retries") == 0, "RETRY_NOT_FORBIDDEN")
    _require(controls.get("fallback") is False, "FALLBACK_NOT_FORBIDDEN")
    _require(controls.get("persist_transaction_bytes") is False, "TX_PERSIST_NOT_FORBIDDEN")
    _require(controls.get("live_market_discovery") is False, "LIVE_DISCOVERY_NOT_FORBIDDEN")
    _require(controls.get("background_scheduler") is False, "BACKGROUND_SCHEDULER")
    _require(int(controls.get("provider_requests_max", 0)) == CALL_CAP, "REQUEST_BUDGET_DRIFT")
    _require(int(controls.get("t0_provider_requests_max", 0)) == T0_CALL_CAP, "T0_BUDGET_DRIFT")
    _require(str(policy.get("prior_panel_runtime_receipt")) == PRIOR_PANEL_RECEIPT, "PRIOR_PATH_DRIFT")
    _require((root / PRIOR_PANEL_RECEIPT).is_file(), "PRIOR_PANEL_RECEIPT_MISSING")


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
    _require(len(rows) == 15, "SCHEDULE_COUNT_DRIFT")
    return rows


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
        _require(prior_receipt.get("atom_id") == ATOM_ID, "OLD_DUE_AT_REBUILT_OR_OLD_RECEIPT_MUTATED")
        _require(prior_receipt.get("atom_id") != OLD_PANEL_ATOM, "OLD_DUE_AT_REBUILT_OR_OLD_RECEIPT_MUTATED")
    bindings = bind_identity_sources(root)
    started_at = now.astimezone(UTC)
    tick = clock or _ticking_clock(started_at)
    slack = int(policy["lateness_slack_seconds"])
    prior_requests = 0
    if wave == "due":
        assert prior_receipt is not None
        raw_schedule = prior_receipt.get("observations")
        _require(isinstance(raw_schedule, list) and len(raw_schedule) == 15, "PRIOR_SCHEDULE_INVALID")
        schedule = [dict(item) for item in raw_schedule if isinstance(item, Mapping)]
        _require(len(schedule) == 15, "SCHEDULE_COUNT_DRIFT")
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

    h900_observed = any(
        str(item.get("kind")) == "SELL_H900" and str(item.get("terminal")) == "QUOTE_OBSERVED"
        for item in results.values()
    )
    h900_missed = any(str(item.get("terminal")) == "MISSED_OFFSET" for item in results.values())
    t0_buys_quoted = sum(
        1
        for item in results.values()
        if str(item.get("kind")) == "BUY_T0" and str(item.get("terminal")) == "QUOTE_OBSERVED"
    )
    if stop_code in {None, "RATE_LIMIT_STOPPED_REMAINING", "TRANSPORT_STOPPED_REMAINING"}:
        if wave == "due" and h900_missed and not h900_observed:
            stop_code = "H900_MISSED_OFFSET"
        elif wave == "due" and h900_observed:
            stop_code = "H900_PANEL_OBSERVED"
        elif wave == "t0" and t0_buys_quoted == 3:
            stop_code = "T0_QUOTED_BUY_CLOCK_ARMED"
        elif stop_code == "RATE_LIMIT_STOPPED_REMAINING":
            stop_code = "PANEL_RATE_LIMITED"
        elif stop_code == "TRANSPORT_STOPPED_REMAINING":
            stop_code = "PANEL_TRANSPORT_UNKNOWN"
        elif wave == "t0" and t0_buys_quoted < 2:
            stop_code = "SECOND_CELL_PROTOCOL_FAIL"
        else:
            stop_code = "PANEL_PROTOCOL_FAIL"

    observations = []
    raw_bodies: dict[str, bytes] = {}
    for row in schedule:
        recorded = dict(results[str(row["observation_id"])])
        body = recorded.pop("body", None)
        if isinstance(body, (bytes, bytearray)):
            raw_bodies[str(row["observation_id"])] = bytes(body)
        observations.append(recorded)

    return {
        "schema": "smial.quote-native-quoted-buy-h900-clock.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
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
        "limitations": [code for code in (
            "RATE_LIMIT_STOPPED_REMAINING_CELLS" if any(
                item.get("terminal") == "RATE_LIMITED" for item in results.values()
            ) else "",
            "H3600_H14400_EXPLICIT_GAP_NO_BACKFILL",
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
            "NOT_A_HYPOTHESIS_TRIAL",
            "NO_LEFTOVER_B_C_OR_T21A_001",
            "NO_H3600_OR_H14400_OBSERVATION",
            "NO_OLD_CLOCK_DUE_REBUILD",
            "NO_POST_MIGRATION_INFERENCE_FOR_UNPROVEN_T21",
        ],
    }
