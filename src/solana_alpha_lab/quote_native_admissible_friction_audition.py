"""Admissible Free-key capture plus frozen H900 friction audition."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.pmf_quote_slice_one_shot import credential_free_preflight
from solana_alpha_lab.provider_route_capability_registry_v9 import (
    FREE_KEY_ROUTE_IDS,
    resolve_provider_route_v9,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (
    API_HOST,
    CALL_CAP,
    H14400,
    LATE_SLACK_SECONDS,
    MIN_INTERVAL_SECONDS,
    QualificationError,
    RECENT_ENDPOINT,
    TRADED_ENDPOINT,
    V6_REGISTRY_PATH,
    V7_REGISTRY_PATH,
    V8_REGISTRY_PATH,
    V9_REGISTRY_PATH,
    _classify_discovery,
    _execute_schedule,
    _format_utc,
    _policy_mapping,
    _terminal_from_observations,
    _transport_view,
    load_process_credential,
    perform_credentialed_get,
)
from solana_alpha_lab.quote_native_friction_h900_falsifier import score_mechanism
from solana_alpha_lab.quote_native_live_variation_campaign import (
    H3600,
    H900,
    build_schedule,
    score_campaign,
    select_cohort,
)

ATOM_ID = "QUOTE_NATIVE_ADMISSIBLE_FRICTION_AUDITION_V1"
AUTHORITY_PHRASE = (
    "OK QUOTE_NATIVE_ADMISSIBLE_FRICTION_AUDITION_V1: one fresh Jupiter "
    "Free-key quote-native campaign; local process-environment key only; "
    "Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; "
    "x-api-key header only; no .env; no key in URL/log/receipt/Git; no taker, "
    "/build, /execute, wallet, signer, transaction, paid plan, second "
    "provider, retry or fallback; cash cap $0; call cap 60; global pace >=3s; "
    "6 RECENT + 6 TRADED live outcome-blind cohort; hash-bound row observed_at "
    "and attempt reservation before credential read required for capture PASS; "
    "freeze QuotedRoundTripFriction(t0) to QuotedLiquidationRecovery(H900) "
    "before first call; H3600 collected as predeclared robustness not a "
    "second searchable Y; capture FAIL pauses the route with no recapture-only "
    "retry; capture PASS plus sample invalid does not close the family; "
    "capture PASS plus sample valid plus no direction closes the exact "
    "mechanism; directional hint stops and leaves MOVE 2 as a later contract; "
    "no H13/H11/H07/H02 unpark; no NetReturn/alpha."
)
ENVELOPE_SCHEMA = "smial.quote-native-admissible-friction-audition.capture-envelope"
RESERVATION_SCHEMA = "smial.quote-native-admissible-friction-audition.attempt-reservation"
SEARCHABLE_Y_KIND = "SELL_H900"
SEARCHABLE_Y_KINDS = frozenset({"BUY_T0", "REVERSE_T0", "SELL_H900"})
UNSCORED_INVALID_CAPTURE = "NOT_SCORED_INVALID_CAPTURE"


class AuditionError(QualificationError):
    """Raised when the admissible friction audition contract is violated."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise AuditionError(code)


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def capture_envelope(
    *,
    observation_id: str,
    observed_at: str,
    body_sha256: str,
) -> dict[str, str]:
    payload = {
        "body_sha256": body_sha256,
        "observation_id": observation_id,
        "observed_at": observed_at,
        "schema": ENVELOPE_SCHEMA,
        "schema_version": "1.0",
    }
    return {
        **payload,
        "envelope_sha256": sha256_bytes(canonical_json(payload)),
    }


def attempt_reservation_document(*, started_at: str, policy_sha256: str) -> dict[str, object]:
    payload = {
        "atom_id": ATOM_ID,
        "credential_reads": 0,
        "policy_sha256": policy_sha256,
        "provider_requests": 0,
        "schema": RESERVATION_SCHEMA,
        "schema_version": "1.0",
        "started_at": started_at,
        "state": "STARTED",
    }
    return {
        **payload,
        "reservation_sha256": sha256_bytes(canonical_json(payload)),
    }


def evaluate_capture(
    *,
    reservation: Mapping[str, Any],
    consumed_rows: list[Mapping[str, Any]],
) -> dict[str, object]:
    blockers: list[str] = []
    if reservation.get("credential_reads") != 0:
        blockers.append("RESERVATION_AFTER_CREDENTIAL_READ")
    if reservation.get("schema") != RESERVATION_SCHEMA:
        blockers.append("RESERVATION_SCHEMA_DRIFT")
    expected_reservation = attempt_reservation_document(
        started_at=str(reservation.get("started_at") or ""),
        policy_sha256=str(reservation.get("policy_sha256") or ""),
    )
    if reservation.get("reservation_sha256") != expected_reservation["reservation_sha256"]:
        blockers.append("RESERVATION_HASH_MISMATCH")
    if not consumed_rows:
        blockers.append("NO_CONSUMED_OBSERVATIONS")
    for row in consumed_rows:
        observation_id = str(row.get("observation_id") or "")
        observed_at = str(row.get("observed_at") or "")
        transport = row.get("transport")
        body_sha256 = ""
        if isinstance(transport, Mapping):
            body_sha256 = str(transport.get("response_sha256") or "")
        if not observed_at:
            blockers.append("OBSERVED_AT_MISSING")
            continue
        if not body_sha256:
            blockers.append("BODY_SHA256_MISSING")
            continue
        expected = capture_envelope(
            observation_id=observation_id,
            observed_at=observed_at,
            body_sha256=body_sha256,
        )
        if row.get("capture_envelope_sha256") != expected["envelope_sha256"]:
            blockers.append("CAPTURE_TIME_NOT_HASH_BOUND_AT_WRITE")
    unique = sorted(set(blockers))
    return {
        "accepted": not unique,
        "blockers": unique,
        "consumed_count": len(consumed_rows),
        "searchable_y_kind": SEARCHABLE_Y_KIND,
    }


def classify_audition_terminal(
    *,
    capture: Mapping[str, Any],
    campaign: Mapping[str, Any],
    mechanism: Mapping[str, Any],
) -> str:
    if capture.get("accepted") is not True:
        return "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
    campaign_verdict = str(campaign.get("campaign_verdict") or "")
    if campaign_verdict == "VARIATION_ABSENT_ON_TRADED_CONTROL":
        return "SAMPLE_INVALID_TRADED_CONTROL_KILL"
    if campaign_verdict != "VARIATION_PRESENT_NOT_MECHANISM":
        return "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"
    mechanism_verdict = str(mechanism.get("verdict") or "")
    if mechanism_verdict == "DIRECTIONAL_HINT_NOT_CONFIRMATION":
        return "DIRECTIONAL_HINT_NOT_CONFIRMATION"
    if mechanism_verdict == "MECHANISM_NOT_SUPPORTED_ON_THIS_SAMPLE":
        return "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM"
    return "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"


def family_closed(terminal: str) -> bool:
    return terminal == "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM"


def searchable_y_observations(observations: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in observations
        if str(row.get("kind") or "") in SEARCHABLE_Y_KINDS
    ]


def unscored_campaign(*, reason: str) -> dict[str, object]:
    return {"campaign_verdict": reason}


def unscored_mechanism(*, reason: str) -> dict[str, object]:
    return {
        "verdict": reason,
        "scored": False,
        "searchable_y_kind": SEARCHABLE_Y_KIND,
    }


def sanitize_wrapped_score(payload: Mapping[str, Any]) -> dict[str, object]:
    cleaned = dict(payload)
    cleaned.pop("non_claims", None)
    cleaned.pop("family_close", None)
    return cleaned


def _validate_policy_shape(policy: Mapping[str, Any]) -> None:
    authority = _policy_mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    controls = _policy_mapping(policy.get("execution_controls"), "CONTROLS_INVALID")
    quote_route = _policy_mapping(policy.get("quote_route"), "QUOTE_ROUTE_INVALID")
    discovery = _policy_mapping(policy.get("discovery_routes"), "DISCOVERY_INVALID")
    recent = _policy_mapping(discovery.get("recent"), "DISCOVERY_RECENT_INVALID")
    traded = _policy_mapping(discovery.get("traded"), "DISCOVERY_TRADED_INVALID")
    success = _policy_mapping(policy.get("success"), "SUCCESS_INVALID")
    control_kill = _policy_mapping(policy.get("control_kill"), "CONTROL_KILL_INVALID")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    _require(authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_DRIFT")
    _require(authority.get("credential_name") == "JUPITER_API_KEY", "CREDENTIAL_NAME_DRIFT")
    _require(authority.get("credential_reads") == 1, "CREDENTIAL_READ_BUDGET_DRIFT")
    _require(authority.get("dotenv_reads") is False, "DOTENV_READ_NOT_FORBIDDEN")
    _require(authority.get("execute") is False, "EXECUTE_NOT_FORBIDDEN")
    _require(authority.get("build") is False, "BUILD_NOT_FORBIDDEN")
    _require(authority.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(authority.get("cash_cap_usd_cents") == 0, "CASH_CAP_DRIFT")
    _require(authority.get("call_cap") == CALL_CAP, "CALL_CAP_DRIFT")
    _require(quote_route.get("endpoint") == "https://api.jup.ag/swap/v2/order", "QUOTE_ENDPOINT_DRIFT")
    _require(quote_route.get("host") == API_HOST, "QUOTE_HOST_DRIFT")
    _require(quote_route.get("method") == "GET", "QUOTE_METHOD_DRIFT")
    _require(recent.get("endpoint") == RECENT_ENDPOINT, "RECENT_ENDPOINT_DRIFT")
    _require(traded.get("endpoint") == TRADED_ENDPOINT, "TRADED_ENDPOINT_DRIFT")
    _require(policy.get("recent_cell_count") == 6, "RECENT_COUNT_DRIFT")
    _require(policy.get("traded_cell_count") == 6, "TRADED_COUNT_DRIFT")
    _require(policy.get("liquidity_floor_usd") == 1000, "LIQUIDITY_FLOOR_DRIFT")
    _require(policy.get("notional_atomic") == "10000000", "NOTIONAL_DRIFT")
    _require(policy.get("slippage_bps") == "100", "SLIPPAGE_DRIFT")
    _require(policy.get("min_interval_seconds") == MIN_INTERVAL_SECONDS, "PACE_DRIFT")
    _require(policy.get("observable_horizon_seconds") == [H900, H3600], "HORIZON_DRIFT")
    _require(policy.get("gap_horizon_seconds") == [H14400], "GAP_HORIZON_DRIFT")
    _require(policy.get("lateness_slack_seconds") == LATE_SLACK_SECONDS, "SLACK_DRIFT")
    _require(policy.get("searchable_y_horizon_seconds") == H900, "SEARCHABLE_Y_DRIFT")
    _require(
        policy.get("h3600_role") == "PREDECLARED_ROBUSTNESS_NOT_SEARCHABLE_Y",
        "H3600_ROLE_DRIFT",
    )
    _require(success.get("min_complete_xy") == 10, "SUCCESS_COMPLETE_DRIFT")
    _require(success.get("min_time_separated") == 6, "SUCCESS_SEPARATED_DRIFT")
    _require(control_kill.get("min_complete_cells") == 6, "KILL_COMPLETE_DRIFT")
    _require(control_kill.get("min_time_separated_share") == "0.5", "KILL_SHARE_DRIFT")
    _require(controls.get("retries") == 0, "RETRY_NOT_FORBIDDEN")
    _require(controls.get("fallback") is False, "FALLBACK_NOT_FORBIDDEN")
    _require(controls.get("persist_transaction_bytes") is False, "TX_PERSIST_NOT_FORBIDDEN")
    _require(controls.get("provider_requests_max") == CALL_CAP, "REQUEST_BUDGET_DRIFT")
    _require(controls.get("background_scheduler") is False, "SCHEDULER_NOT_FORBIDDEN")
    _require(controls.get("second_provider") is False, "SECOND_PROVIDER_NOT_FORBIDDEN")
    _require(controls.get("paid_plan") is False, "PAID_PLAN_NOT_FORBIDDEN")


def validate_policy(policy: Mapping[str, Any], *, root: Path) -> None:
    _validate_policy_shape(policy)
    _require(policy.get("registry") == V9_REGISTRY_PATH, "REGISTRY_BIND_DRIFT")
    quote_route = _policy_mapping(policy.get("quote_route"), "QUOTE_ROUTE_INVALID")
    discovery = _policy_mapping(policy.get("discovery_routes"), "DISCOVERY_INVALID")
    recent = _policy_mapping(discovery.get("recent"), "DISCOVERY_RECENT_INVALID")
    traded = _policy_mapping(discovery.get("traded"), "DISCOVERY_TRADED_INVALID")
    _require(
        tuple(
            (
                str(recent.get("route_id")),
                str(traded.get("route_id")),
                str(quote_route.get("route_id")),
            )
        )
        == FREE_KEY_ROUTE_IDS,
        "FREE_KEY_ROUTE_BIND_DRIFT",
    )

    def load_yaml(relative: str) -> Mapping[str, Any]:
        loaded = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        _require(isinstance(loaded, Mapping), "REGISTRY_DOCUMENT_INVALID")
        return loaded

    v6_path = root / V6_REGISTRY_PATH
    v7_path = root / V7_REGISTRY_PATH
    v8_path = root / V8_REGISTRY_PATH
    v6 = load_yaml(V6_REGISTRY_PATH)
    v7 = load_yaml(V7_REGISTRY_PATH)
    v8 = load_yaml(V8_REGISTRY_PATH)
    v9 = load_yaml(V9_REGISTRY_PATH)
    v6_sha = hashlib.sha256(v6_path.read_bytes()).hexdigest()
    v7_sha = hashlib.sha256(v7_path.read_bytes()).hexdigest()
    v8_sha = hashlib.sha256(v8_path.read_bytes()).hexdigest()
    for route_id in FREE_KEY_ROUTE_IDS:
        resolve_provider_route_v9(
            v9,
            route_id,
            predecessor=v8,
            predecessor_sha256=v8_sha,
            v7_registry=v7,
            v7_sha256=v7_sha,
            v6_registry=v6,
            v6_sha256=v6_sha,
        )


def _attach_envelopes(
    rows: list[dict[str, object]],
    envelopes: Mapping[str, str],
) -> list[dict[str, object]]:
    attached: list[dict[str, object]] = []
    for row in rows:
        recorded = dict(row)
        observation_id = str(recorded.get("observation_id") or "")
        if observation_id in envelopes:
            recorded["capture_envelope_sha256"] = envelopes[observation_id]
        attached.append(recorded)
    return attached


def _consumed_rows(*groups: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    consumed: list[Mapping[str, Any]] = []
    for group in groups:
        for row in group:
            if row.get("consumed_call") is True:
                consumed.append(row)
    return consumed


def _terminal_receipt(
    *,
    terminal: str,
    preflight: Mapping[str, Any],
    credential_reads: int,
    provider_requests: int,
    discovery_rows: list[dict[str, object]],
    observations: list[dict[str, object]],
    reservation: Mapping[str, Any],
    frozen_cells: list[object] | None = None,
    capture: Mapping[str, Any] | None = None,
    campaign: Mapping[str, Any] | None = None,
    mechanism: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    selected_capture = dict(capture or {"accepted": False, "blockers": ["CAMPAIGN_INCOMPLETE"]})
    selected_campaign = dict(
        campaign
        or unscored_campaign(reason="NOT_SCORED_CAPTURE_OR_SAMPLE_GATE")
    )
    selected_mechanism = dict(
        mechanism or unscored_mechanism(reason="NOT_SCORED_CAPTURE_OR_SAMPLE_GATE")
    )
    return {
        "schema": "smial.quote-native-admissible-friction-audition.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_outcome": terminal,
        "preflight": dict(preflight),
        "credential_reads": credential_reads,
        "provider_requests": provider_requests,
        "retries": 0,
        "fallbacks": 0,
        "execute_calls": 0,
        "frozen_cells": list(frozen_cells or []),
        "discovery_observations": discovery_rows,
        "observations": observations,
        "attempt_reservation": dict(reservation),
        "capture": selected_capture,
        "campaign": selected_campaign,
        "mechanism": selected_mechanism,
        "family_close": family_closed(terminal),
        "h3600_role": "PREDECLARED_ROBUSTNESS_NOT_SEARCHABLE_Y",
        "searchable_y_kind": SEARCHABLE_Y_KIND,
        "non_claims": [
            "NO_EXECUTE",
            "NO_TAKER_OR_SIGNER",
            "NO_TRANSACTION_BYTES_IN_GIT",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_MOVE_2",
            "NO_PAID_PLAN",
            "NO_SECOND_PROVIDER",
            "NO_H3600_SEARCHABLE_Y",
            "NO_RECAPTURE_ONLY_SUFFIX",
        ],
    }


def run_campaign(
    policy: Mapping[str, Any],
    *,
    reservation: Mapping[str, Any],
    credential_loader: Callable[[], str],
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    opener: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] | None = None,
    monotonic_clock: Callable[[], float] | None = None,
    raw_sink: Callable[[str, bytes, str, str], None] | None = None,
    select_cohort_fn: Callable[[list[Mapping[str, Any]], list[Mapping[str, Any]]], dict[str, object]] | None = None,
) -> dict[str, object]:
    _validate_policy_shape(policy)
    _require(reservation.get("credential_reads") == 0, "CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION")
    limits = _policy_mapping(policy.get("runtime_limits"), "LIMITS_INVALID")
    quote_route = _policy_mapping(policy.get("quote_route"), "QUOTE_ROUTE_INVALID")
    discovery = _policy_mapping(policy.get("discovery_routes"), "DISCOVERY_INVALID")
    waiter = time.sleep if sleeper is None else sleeper
    monotonic = time.monotonic if monotonic_clock is None else monotonic_clock
    started_at = clock()
    preflight = dict(
        preflight_fn(
            {"provider_route": {"endpoint": quote_route["endpoint"]}},
            observed_at=_format_utc(started_at),
        )
    )
    _require(preflight.get("credential_reads") == 0, "PREFLIGHT_CREDENTIAL_READ_DRIFT")
    credential = credential_loader()
    _require(bool(credential.strip()), "JUPITER_API_KEY_MISSING_OR_EMPTY")
    credential_reads = 1
    provider_requests = 0
    last_call_monotonic: float | None = None
    envelopes: dict[str, str] = {}

    def call(url: str, observation_id: str) -> dict[str, object]:
        nonlocal provider_requests, last_call_monotonic
        if last_call_monotonic is not None:
            elapsed = monotonic() - last_call_monotonic
            if elapsed < MIN_INTERVAL_SECONDS:
                waiter(MIN_INTERVAL_SECONDS - elapsed)
        if provider_requests >= CALL_CAP:
            raise AuditionError("CALL_CAP_EXCEEDED", provider_requests=provider_requests)
        provider_requests += 1
        try:
            observed = perform_credentialed_get(
                url,
                api_key=credential,
                limits=limits,
                opener=opener,
            )
        except QualificationError as exc:
            last_call_monotonic = monotonic()
            raise AuditionError(str(exc), provider_requests=provider_requests) from exc
        last_call_monotonic = monotonic()
        if observed.get("url_has_api_key") is True:
            raise AuditionError(
                "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
                provider_requests=provider_requests,
            )
        completed_at = clock()
        observed_at = _format_utc(completed_at)
        body_sha256 = str(observed.get("response_sha256") or "")
        envelope = capture_envelope(
            observation_id=observation_id,
            observed_at=observed_at,
            body_sha256=body_sha256,
        )
        observed["observed_at"] = observed_at
        observed["capture_envelope_sha256"] = envelope["envelope_sha256"]
        envelopes[observation_id] = envelope["envelope_sha256"]
        return observed

    def retain_raw(
        observation_id: str,
        observed: Mapping[str, object],
        *,
        reject_transaction_body: bool,
    ) -> None:
        body = observed.get("body")
        if raw_sink is None or not isinstance(body, bytes):
            return
        from solana_alpha_lab.quote_native_evidence_channel_qualification import (
            _body_contains_secret,
            _body_contains_transaction,
        )

        if reject_transaction_body and _body_contains_transaction(body):
            return
        if _body_contains_secret(body, credential):
            raise AuditionError("RAW_BODY_CONTAINS_CREDENTIAL", provider_requests=provider_requests)
        observed_at = observed.get("observed_at")
        envelope_sha256 = observed.get("capture_envelope_sha256")
        _require(isinstance(observed_at, str), "OBSERVED_AT_MISSING")
        _require(isinstance(envelope_sha256, str), "CAPTURE_ENVELOPE_MISSING")
        raw_sink(observation_id, body, observed_at, envelope_sha256)

    discovery_rows: list[dict[str, object]] = []
    result = call(
        str(_policy_mapping(discovery["recent"], "DISCOVERY_RECENT_INVALID")["endpoint"]),
        "DISCOVERY:RECENT",
    )
    retain_raw("DISCOVERY:RECENT", result, reject_transaction_body=True)
    terminal, error, recent_payload = _classify_discovery(result)
    discovery_rows.append(
        {
            "observation_id": "DISCOVERY:RECENT",
            "kind": "DISCOVERY_RECENT",
            "terminal": terminal,
            "terminal_error": error,
            "observed_at": result["observed_at"],
            "capture_envelope_sha256": result["capture_envelope_sha256"],
            "transport": _transport_view(result),
            "consumed_call": True,
        }
    )
    if terminal != "TOKEN_LIST_OBSERVED":
        attached = _attach_envelopes(discovery_rows, envelopes)
        capture = evaluate_capture(reservation=reservation, consumed_rows=_consumed_rows(attached))
        mapped = (
            "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
            if terminal in {"RATE_LIMITED", "PROVIDER_TYPED_FAILURE", "TOKEN_LIST_SHAPE_INVALID"}
            else terminal
        )
        return _terminal_receipt(
            terminal=mapped,
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_rows=attached,
            observations=[],
            reservation=reservation,
            capture=capture,
        )
    result = call(
        str(_policy_mapping(discovery["traded"], "DISCOVERY_TRADED_INVALID")["endpoint"]),
        "DISCOVERY:TRADED",
    )
    retain_raw("DISCOVERY:TRADED", result, reject_transaction_body=True)
    terminal, error, traded_payload = _classify_discovery(result)
    discovery_rows.append(
        {
            "observation_id": "DISCOVERY:TRADED",
            "kind": "DISCOVERY_TRADED",
            "terminal": terminal,
            "terminal_error": error,
            "observed_at": result["observed_at"],
            "capture_envelope_sha256": result["capture_envelope_sha256"],
            "transport": _transport_view(result),
            "consumed_call": True,
        }
    )
    if terminal != "TOKEN_LIST_OBSERVED":
        attached = _attach_envelopes(discovery_rows, envelopes)
        capture = evaluate_capture(reservation=reservation, consumed_rows=_consumed_rows(attached))
        mapped = (
            "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
            if terminal in {"RATE_LIMITED", "PROVIDER_TYPED_FAILURE", "TOKEN_LIST_SHAPE_INVALID"}
            else terminal
        )
        return _terminal_receipt(
            terminal=mapped,
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_rows=attached,
            observations=[],
            reservation=reservation,
            capture=capture,
        )
    choose_cohort = select_cohort if select_cohort_fn is None else select_cohort_fn
    cohort = choose_cohort(recent_payload or [], traded_payload or [])
    cells = cohort["cells"]
    if not cohort["sufficient"] or not isinstance(cells, list):
        attached = _attach_envelopes(discovery_rows, envelopes)
        capture = evaluate_capture(reservation=reservation, consumed_rows=_consumed_rows(attached))
        return _terminal_receipt(
            terminal="PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_rows=attached,
            observations=[],
            reservation=reservation,
            frozen_cells=cells if isinstance(cells, list) else [],
            capture=capture,
        )

    panel_started_at = clock()
    panel_started_monotonic = monotonic()
    schedule = build_schedule(cells, panel_started_at=panel_started_at)
    observations = _execute_schedule(
        schedule=schedule,
        policy=policy,
        call=call,
        clock=clock,
        sleeper=waiter,
        panel_started_at=panel_started_at,
        panel_started_monotonic=panel_started_monotonic,
        monotonic_clock=monotonic,
        retain_order_raw=lambda observation_id, observed: retain_raw(
            observation_id,
            observed,
            reject_transaction_body=True,
        ),
    )
    observations = _attach_envelopes(observations, envelopes)
    discovery_rows = _attach_envelopes(discovery_rows, envelopes)
    capture = evaluate_capture(
        reservation=reservation,
        consumed_rows=_consumed_rows(discovery_rows, observations),
    )
    if capture["accepted"] is not True:
        return {
            **_terminal_receipt(
                terminal="PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
                preflight=preflight,
                credential_reads=credential_reads,
                provider_requests=provider_requests,
                discovery_rows=discovery_rows,
                observations=observations,
                reservation=reservation,
                frozen_cells=cells,
                capture=capture,
                campaign=unscored_campaign(reason=UNSCORED_INVALID_CAPTURE),
                mechanism=unscored_mechanism(reason=UNSCORED_INVALID_CAPTURE),
            ),
            "panel_started_at": _format_utc(panel_started_at),
        }
    transport_terminal = _terminal_from_observations(observations)
    if transport_terminal != "COMPLETE":
        return {
            **_terminal_receipt(
                terminal=transport_terminal,
                preflight=preflight,
                credential_reads=credential_reads,
                provider_requests=provider_requests,
                discovery_rows=discovery_rows,
                observations=observations,
                reservation=reservation,
                frozen_cells=cells,
                capture=capture,
                campaign=unscored_campaign(reason="NOT_SCORED_INCOMPLETE_TRANSPORT"),
                mechanism=unscored_mechanism(reason="NOT_SCORED_INCOMPLETE_TRANSPORT"),
            ),
            "panel_started_at": _format_utc(panel_started_at),
        }
    campaign = sanitize_wrapped_score(score_campaign(observations))
    mechanism = sanitize_wrapped_score(score_mechanism(searchable_y_observations(observations)))
    mechanism["scored"] = True
    mechanism["searchable_y_kind"] = SEARCHABLE_Y_KIND
    campaign["h3600_role"] = "PREDECLARED_ROBUSTNESS_NOT_SEARCHABLE_Y"
    terminal_outcome = classify_audition_terminal(
        capture=capture,
        campaign=campaign,
        mechanism=mechanism,
    )
    return {
        **_terminal_receipt(
            terminal=terminal_outcome,
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_rows=discovery_rows,
            observations=observations,
            reservation=reservation,
            frozen_cells=cells,
            capture=capture,
            campaign=campaign,
            mechanism=mechanism,
        ),
        "panel_started_at": _format_utc(panel_started_at),
    }
