"""EARLY valuation-liquidity divergence: two PIT snapshots, X = ln(R1/R0)."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.ordinary_market_pit_primary_x import (
    PRIMARY_X_BOUND,
    PRIMARY_X_UNKNOWN,
    bind_primary_x,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (
    CALL_CAP,
    H900,
    NOTIONAL_ATOMIC,
    QUOTE_OBSERVED,
    QUOTE_ROUTE_ID,
    RECENT_ENDPOINT,
    RECENT_ROUTE_ID,
    SEARCH_ENDPOINT,
    SEASONING_SECONDS,
    SLIPPAGE_BPS,
    TARGET_CANDIDATES,
    WRAPPED_SOL,
    OrganicPressureError,
    _assert_quote_body_has_no_transaction,
    _failure_receipt,
    _format_utc,
    _kendall_tau_b,
    _order_url,
    _parse_datetime,
    _raw_observation,
    _require,
    _row_sha256,
    _search_rows,
    _transport_view,
    build_search_url,
    classify_organic_quote,
    select_frozen_candidates,
)
from solana_alpha_lab.pmf_quote_slice_one_shot import QuoteShotError, credential_free_preflight
from solana_alpha_lab.provider_route_capability_registry_v10 import (
    SEARCH_ROUTE_ID,
    resolve_provider_route_v10,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (
    QualificationError,
    perform_credentialed_get,
)

ATOM_ID = "EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1"
POLICY_SCHEMA = "smial.early-valuation-liquidity-divergence-confirmation"
RECEIPT_SCHEMA = "smial.early-valuation-liquidity-divergence-confirmation.runtime-receipt"
X_FORMULA = "ln(R1/R0)"
FEATURE_ID = "FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO"
ICP_ID = "ICP-EARLY-PUMPFUN-V1"
CLOSE_TERMINAL = "CLOSE_VALUATION_LIQUIDITY_DIVERGENCE_FAMILY"
EARN_TERMINAL = "EARN_ONE_CONFIRMATORY_FRESH_OOS"
INVALID_TERMINAL = "INVALID_EVIDENCE_REPLAN"
CONFIRMATION_SECONDS = 300
R0_AGE_MIN = 300
R0_AGE_MAX_EXCLUSIVE = 600
R1_AGE_MIN = 600
R1_AGE_MAX_EXCLUSIVE = 900
LIQUIDITY_USD_MIN = 1000.0
MIN_ELIGIBLE = 10
MIN_RANKABLE = 8
FACTORY_RUNNER = "src/solana_alpha_lab/factory/runner.py"
FACTORY_RUNNER_SHA256 = "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"
AUTHORITY_PHRASE = (
    "OK EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1: one bounded "
    "Jupiter Free-key read-only PIT campaign using a local "
    "process-environment key only; Tokens V2 /recent plus two bulk "
    "/tokens/v2/search snapshots 300s apart plus quote-only /swap/v2/order; "
    "x-api-key header only; no .env read, no key in URL/log/receipt/Git, no "
    "taker, /build, /execute, wallet, signer, transaction, paid plan, second "
    "provider, retry or fallback; cash cap $0; call cap 60; global provider "
    "pace >=3s; ICP-EARLY-PUMPFUN-V1 fresh mints only excluding all prior "
    "consumed mints; X = ln(R1/R0) from FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO "
    "at two prospective search snapshots (mcap != fdv; UNKNOWN never zero); "
    "no closed-family threshold, window or quartile reopen; quote-only BUY "
    "after the second snapshot and quote-only SELL at H900; one window only; "
    "Factory runner unchanged; Discovery, A7, Strategy, Bot, Shadow, alpha, "
    "NetReturn and micro-live forbidden."
)
FIELD_PATHS = ["liquidity", "mcap", "firstPool.createdAt", "updatedAt", "launchpad"]


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _ratio_bind(row: Mapping[str, Any] | None, observed_at: datetime) -> dict[str, Any]:
    observed_at_text = _format_utc(observed_at)
    if not isinstance(row, Mapping):
        return {
            "status": PRIMARY_X_UNKNOWN,
            "value": None,
            "reason": "SEARCH_MINT_NOT_RETURNED",
            "observed_at": observed_at_text,
            "substitute_rejected": False,
        }
    bound = bind_primary_x(row, observed_at=observed_at_text)
    if bound.get("substitute_rejected") is True:
        bound["reason"] = "FDV_OR_SUBSTITUTE_REJECTED"
    elif bound.get("status") != PRIMARY_X_BOUND:
        bound["reason"] = "MCAP_OR_LIQUIDITY_MISSING"
    return bound


def project_divergence(
    recent_row: Mapping[str, Any],
    r0_row: Mapping[str, Any] | None,
    r1_row: Mapping[str, Any] | None,
    snapshot_r0: datetime,
    snapshot_r1: datetime,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "MISSING",
        "value": None,
        "field_paths": list(FIELD_PATHS),
        "inputs": {},
        "icp_id": ICP_ID,
        "feature_id": FEATURE_ID,
        "x_formula": X_FORMULA,
    }
    if not isinstance(recent_row, Mapping):
        result["reason"] = "RECENT_ROW_MISSING"
        return result
    if recent_row.get("launchpad") != "pump.fun":
        result["reason"] = "PROJECT_PREDICATE_FALSE"
        return result
    if not isinstance(r0_row, Mapping) or not isinstance(r1_row, Mapping):
        result["reason"] = "SEARCH_MINT_NOT_RETURNED"
        return result
    if r0_row.get("launchpad") != "pump.fun" or r1_row.get("launchpad") != "pump.fun":
        result["reason"] = "PROJECT_PREDICATE_FALSE"
        return result
    if recent_row.get("id") != r0_row.get("id") or r0_row.get("id") != r1_row.get("id"):
        result["reason"] = "SNAPSHOT_MINT_MISMATCH"
        return result
    pool = r0_row.get("firstPool")
    pool_r1 = r1_row.get("firstPool")
    if not isinstance(pool, Mapping) or not isinstance(pool_r1, Mapping):
        result["reason"] = "REQUIRED_OBJECT_ABSENT"
        return result
    if pool.get("createdAt") != pool_r1.get("createdAt"):
        result["reason"] = "CREATED_AT_SNAPSHOT_MISMATCH"
        return result
    try:
        created_at = _parse_datetime(pool.get("createdAt"), "FIRST_POOL_TIMESTAMP_INVALID")
        updated_r0 = _parse_datetime(r0_row.get("updatedAt"), "UPDATED_TIMESTAMP_INVALID")
        updated_r1 = _parse_datetime(r1_row.get("updatedAt"), "UPDATED_TIMESTAMP_INVALID")
    except OrganicPressureError as exc:
        result["reason"] = str(exc)
        return result
    t0 = _utc(snapshot_r0)
    t1 = _utc(snapshot_r1)
    interval = (t1 - t0).total_seconds()
    age_r0 = (t0 - created_at).total_seconds()
    age_r1 = (t1 - created_at).total_seconds()
    result["age_r0_seconds"] = age_r0
    result["age_r1_seconds"] = age_r1
    result["confirmation_interval_seconds"] = interval
    result["inputs"] = {
        "r0.liquidity": r0_row.get("liquidity"),
        "r0.mcap": r0_row.get("mcap"),
        "r1.liquidity": r1_row.get("liquidity"),
        "r1.mcap": r1_row.get("mcap"),
        "firstPool.createdAt": pool.get("createdAt"),
        "r0.updatedAt": r0_row.get("updatedAt"),
        "r1.updatedAt": r1_row.get("updatedAt"),
    }
    if created_at > t0 or created_at > t1:
        result["reason"] = "FIRST_POOL_TIMESTAMP_IN_THE_FUTURE"
        return result
    if updated_r0 < created_at or updated_r1 < created_at:
        result["reason"] = "UPDATED_TIMESTAMP_BEFORE_POOL_CREATION"
        return result
    if updated_r0 > t0 or updated_r1 > t1:
        result["reason"] = "UPDATED_TIMESTAMP_IN_FUTURE"
        return result
    if interval < float(CONFIRMATION_SECONDS) or interval > float(CONFIRMATION_SECONDS) + 60.0:
        result["reason"] = "CONFIRMATION_INTERVAL_INVALID"
        return result
    if age_r0 < float(R0_AGE_MIN):
        result["status"] = "TOO_YOUNG"
        result["reason"] = "R0_AGE_BELOW_ICP_MIN"
        return result
    if age_r0 >= float(R0_AGE_MAX_EXCLUSIVE):
        result["status"] = "TOO_OLD_FOR_CONFIRMATION"
        result["reason"] = "R0_AGE_LEAVES_NO_IN_BAND_R1"
        return result
    if age_r1 < float(R1_AGE_MIN):
        result["status"] = "TOO_YOUNG"
        result["reason"] = "R1_AGE_BELOW_CONFIRMATION_BAND"
        return result
    if age_r1 >= float(R1_AGE_MAX_EXCLUSIVE):
        result["status"] = "TOO_OLD"
        result["reason"] = "R1_AGE_OUTSIDE_ICP_MAX"
        return result
    bound_r0 = _ratio_bind(r0_row, t0)
    bound_r1 = _ratio_bind(r1_row, t1)
    result["r0"] = bound_r0
    result["r1"] = bound_r1
    result["substitute_rejected"] = bool(bound_r0.get("substitute_rejected") or bound_r1.get("substitute_rejected"))
    if result["substitute_rejected"]:
        result["reason"] = "FDV_OR_SUBSTITUTE_REJECTED"
        return result
    liquidity_r0 = bound_r0.get("liquidity")
    liquidity_r1 = bound_r1.get("liquidity")
    if liquidity_r0 is None or float(liquidity_r0) < LIQUIDITY_USD_MIN:
        result["reason"] = "LIQUIDITY_BELOW_ICP_MIN"
        return result
    if liquidity_r1 is None or float(liquidity_r1) < LIQUIDITY_USD_MIN:
        result["reason"] = "R1_LIQUIDITY_BELOW_ICP_MIN"
        return result
    if bound_r0.get("status") != PRIMARY_X_BOUND or bound_r1.get("status") != PRIMARY_X_BOUND:
        result["reason"] = "PRIMARY_X_UNKNOWN"
        return result
    r0_value = float(bound_r0["value"])
    r1_value = float(bound_r1["value"])
    if r0_value <= 0 or r1_value <= 0:
        result["reason"] = "RATIO_NOT_POSITIVE"
        return result
    result["status"] = "ELIGIBLE"
    result["value"] = math.log(r1_value / r0_value)
    result["x_available_at"] = _format_utc(t1)
    return result


def score_divergence(rows: list[Mapping[str, Any]]) -> dict[str, object]:
    eligible = [row for row in rows if isinstance(row.get("x"), (int, float))]
    rankable = [
        row
        for row in eligible
        if row.get("h900_terminal") == QUOTE_OBSERVED and isinstance(row.get("y"), (int, float))
    ]
    result: dict[str, object] = {
        "decision_time_eligible": len(eligible),
        "rankable_h900": len(rankable),
        "tau_b": None,
        "score_kind": "SIGN_ONLY_KENDALL_TAU_B",
        "top_quartile_median_y": None,
        "leave_one_out_positive_share": None,
    }
    if len(eligible) < MIN_ELIGIBLE or len(rankable) < MIN_RANKABLE:
        return {"terminal": INVALID_TERMINAL, **result}
    tau = _kendall_tau_b(rankable)
    result["tau_b"] = tau
    if tau is None or tau <= 0:
        return {"terminal": CLOSE_TERMINAL, **result}
    return {"terminal": EARN_TERMINAL, **result}


def validate_divergence_policy(policy: Mapping[str, Any], *, root: Path) -> None:
    _require(policy.get("schema") == POLICY_SCHEMA, "SCHEMA_DRIFT")
    _require(policy.get("schema_version") == "1.0", "SCHEMA_VERSION_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    authority = policy.get("external_authority")
    _require(isinstance(authority, Mapping), "AUTHORITY_INVALID")
    _require(authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_DRIFT")
    _require(authority.get("credential_name") == "JUPITER_API_KEY", "CREDENTIAL_NAME_DRIFT")
    _require(authority.get("credential_reads") == 1, "CREDENTIAL_READ_BUDGET_DRIFT")
    _require(authority.get("dotenv_reads") is False, "DOTENV_READ_NOT_FORBIDDEN")
    _require(authority.get("execute") is False, "EXECUTE_NOT_FORBIDDEN")
    _require(authority.get("build") is False, "BUILD_NOT_FORBIDDEN")
    _require(authority.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(authority.get("cash_cap_usd_cents") == 0, "CASH_CAP_DRIFT")
    _require(authority.get("call_cap") == CALL_CAP, "CALL_CAP_DRIFT")
    _require(policy.get("wrapped_sol_mint") == WRAPPED_SOL, "WRAPPED_SOL_DRIFT")
    registry_relative = str(policy.get("registry"))
    _require(registry_relative == "configs/provider_route_capability_registry_v10.yaml", "REGISTRY_BIND_DRIFT")
    registry_path = root / registry_relative
    predecessor_path = root / "configs/provider_route_capability_registry_v9.yaml"
    _require(registry_path.is_file() and predecessor_path.is_file(), "REGISTRY_DOCUMENT_MISSING")
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    predecessor = yaml.safe_load(predecessor_path.read_text(encoding="utf-8"))
    _require(isinstance(registry, Mapping) and isinstance(predecessor, Mapping), "REGISTRY_DOCUMENT_INVALID")
    resolve_provider_route_v10(
        registry,
        SEARCH_ROUTE_ID,
        predecessor=predecessor,
        predecessor_sha256=hashlib.sha256(predecessor_path.read_bytes()).hexdigest(),
    )
    routes = policy.get("routes")
    _require(isinstance(routes, Mapping), "ROUTES_INVALID")
    recent = routes.get("recent")
    search = routes.get("search")
    quote = routes.get("quote")
    _require(isinstance(recent, Mapping) and recent.get("route_id") == RECENT_ROUTE_ID, "RECENT_ROUTE_ID_DRIFT")
    _require(isinstance(search, Mapping) and search.get("route_id") == SEARCH_ROUTE_ID, "SEARCH_ROUTE_ID_DRIFT")
    _require(isinstance(quote, Mapping) and quote.get("route_id") == QUOTE_ROUTE_ID, "QUOTE_ROUTE_ID_DRIFT")
    _require(recent.get("endpoint") == RECENT_ENDPOINT, "RECENT_ENDPOINT_DRIFT")
    _require(search.get("endpoint") == SEARCH_ENDPOINT, "SEARCH_ENDPOINT_DRIFT")
    population = policy.get("population")
    _require(isinstance(population, Mapping), "POPULATION_INVALID")
    _require(population.get("icp_id") == ICP_ID, "ICP_ID_DRIFT")
    _require(population.get("launchpad") == "pump.fun", "POPULATION_PREDICATE_DRIFT")
    _require(int(population.get("target_candidates", -1)) == TARGET_CANDIDATES, "TARGET_CANDIDATE_DRIFT")
    _require(int(population.get("seasoning_seconds", -1)) == SEASONING_SECONDS, "SEASONING_DRIFT")
    _require(int(population.get("confirmation_seconds", -1)) == CONFIRMATION_SECONDS, "CONFIRMATION_DRIFT")
    r0_band = population.get("r0_age_band_seconds")
    r1_band = population.get("r1_age_band_seconds")
    _require(isinstance(r0_band, Mapping) and int(r0_band.get("min", -1)) == R0_AGE_MIN, "R0_AGE_MIN_DRIFT")
    _require(isinstance(r0_band, Mapping) and int(r0_band.get("max_exclusive", -1)) == R0_AGE_MAX_EXCLUSIVE, "R0_AGE_MAX_DRIFT")
    _require(isinstance(r1_band, Mapping) and int(r1_band.get("min", -1)) == R1_AGE_MIN, "R1_AGE_MIN_DRIFT")
    _require(isinstance(r1_band, Mapping) and int(r1_band.get("max_exclusive", -1)) == R1_AGE_MAX_EXCLUSIVE, "R1_AGE_MAX_DRIFT")
    _require(float(population.get("liquidity_usd_min", -1)) == LIQUIDITY_USD_MIN, "LIQUIDITY_MIN_DRIFT")
    snapshot = policy.get("decision_snapshot")
    _require(isinstance(snapshot, Mapping), "DECISION_SNAPSHOT_INVALID")
    _require(snapshot.get("x_formula") == X_FORMULA, "X_FORMULA_DRIFT")
    _require(snapshot.get("feature_id") == FEATURE_ID, "FEATURE_ID_DRIFT")
    _require(snapshot.get("fdv_substitute") == "forbidden", "FDV_SUBSTITUTE_DRIFT")
    _require(snapshot.get("missing_is_zero") is False, "MISSING_ZERO_DRIFT")
    _require(snapshot.get("run_campaign_black_box") == "forbidden", "RUN_CAMPAIGN_REUSE_NOT_FORBIDDEN")
    quote_policy = policy.get("quote")
    _require(isinstance(quote_policy, Mapping), "QUOTE_POLICY_INVALID")
    _require(quote_policy.get("horizon_seconds") == H900, "H900_DRIFT")
    _require(quote_policy.get("buy_after") == "SECOND_SNAPSHOT", "BUY_AFTER_DRIFT")
    decision = policy.get("decision_rule")
    _require(isinstance(decision, Mapping), "DECISION_RULE_INVALID")
    _require(int(decision.get("min_decision_time_eligible", -1)) == MIN_ELIGIBLE, "ELIGIBLE_FLOOR_DRIFT")
    _require(int(decision.get("min_rankable_h900", -1)) == MIN_RANKABLE, "RANKABLE_FLOOR_DRIFT")
    _require(decision.get("score_kind") == "SIGN_ONLY_KENDALL_TAU_B", "SCORE_KIND_DRIFT")
    _require(decision.get("tau_b_floor") == "forbidden", "TAU_FLOOR_REOPENED")
    _require(decision.get("top_x_quartile") is False, "QUARTILE_REOPENED")
    _require(decision.get("leave_one_out_positive_share") == "forbidden", "LOO_REOPENED")
    _require(decision.get("close_if_tau_b_le_zero") is True, "SIGN_RULE_DRIFT")
    windows = policy.get("windows")
    _require(isinstance(windows, Mapping), "WINDOWS_INVALID")
    _require(int(windows.get("max_windows", -1)) == 1, "WINDOW_BUDGET_DRIFT")
    _require(windows.get("window_b") == "forbidden", "WINDOW_B_REOPENED")
    _require(windows.get("third_window") == "forbidden", "THIRD_WINDOW_REOPENED")
    _require(policy.get("factory_runner") == FACTORY_RUNNER, "FACTORY_RUNNER_PATH_DRIFT")
    _require(policy.get("factory_runner_sha256") == FACTORY_RUNNER_SHA256, "FACTORY_RUNNER_HASH_DRIFT")
    _require(hashlib.sha256((root / FACTORY_RUNNER).read_bytes()).hexdigest() == FACTORY_RUNNER_SHA256, "FACTORY_RUNNER_BYTES_DRIFT")


def _index_by_mint(rows: list[Mapping[str, Any]], expected: list[str]) -> dict[str, Mapping[str, Any]] | None:
    expected_set = set(expected)
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        mint = row.get("id")
        if not isinstance(mint, str) or mint not in expected_set or mint in indexed:
            if isinstance(mint, str) and mint in indexed:
                return None
            continue
        indexed[mint] = row
    if any(mint not in indexed for mint in expected):
        return None
    return indexed


def run_divergence_campaign(
    policy: Mapping[str, Any],
    *,
    authority_phrase: str,
    reservation: Mapping[str, Any],
    excluded_mints: set[str],
    credential_loader: Any,
    preflight_fn: Any = credential_free_preflight,
    opener: object | None = None,
    clock: Any = lambda: datetime.now(UTC),
    sleeper: Any = None,
    monotonic_clock: Any = None,
    raw_sink: Any = None,
) -> dict[str, object]:
    import time

    waiter = sleeper or time.sleep
    monotonic = monotonic_clock or time.monotonic
    root = Path(__file__).resolve().parents[2]
    validate_divergence_policy(policy, root=root)
    authority = policy["external_authority"]
    _require(authority_phrase == authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_INVALID")
    _require(reservation.get("state") == "STARTED", "ATTEMPT_RESERVATION_REQUIRED")
    _require(reservation.get("credential_reads") == 0, "CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION")
    _require(bool(excluded_mints), "PRIOR_MINT_EXCLUSION_INPUT_REQUIRED")
    started_at = clock()
    try:
        preflight = dict(
            preflight_fn(
                {"provider_route": {"endpoint": RECENT_ENDPOINT}},
                observed_at=_format_utc(started_at),
            )
        )
    except QuoteShotError as exc:
        raise OrganicPressureError(str(exc)) from exc
    _require(preflight.get("credential_reads") == 0, "CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT")
    credential = credential_loader()
    _require(isinstance(credential, str) and bool(credential.strip()), "JUPITER_API_KEY_MISSING_OR_EMPTY")
    credential_reads = 1
    provider_requests = 0
    last_monotonic: float | None = None

    def call(url: str) -> dict[str, object]:
        nonlocal provider_requests, last_monotonic
        if last_monotonic is not None:
            elapsed = monotonic() - last_monotonic
            if elapsed < 3:
                waiter(3 - elapsed)
        _require(provider_requests < CALL_CAP, "CALL_CAP_EXCEEDED")
        provider_requests += 1
        try:
            result = perform_credentialed_get(
                url,
                api_key=credential,
                limits=policy["runtime_limits"],
                opener=opener,
            )
        except QualificationError as exc:
            raise OrganicPressureError(str(exc), provider_requests=provider_requests) from exc
        last_monotonic = monotonic()
        if result.get("url_has_api_key") is True:
            raise OrganicPressureError("API_KEY_IN_URL_LOG_RECEIPT_OR_GIT", provider_requests=provider_requests)
        result["observed_at"] = _format_utc(clock())
        return result

    non_claims = [
        "NO_EXECUTE",
        "NO_TAKER_OR_SIGNER",
        "NO_TRANSACTION_BYTES_IN_GIT",
        "NO_ALPHA",
        "NO_NETRETURN",
        "NO_STRATEGY_OR_SHADOW",
        "NO_DISCOVERY_OR_A7",
        "NO_CLOSED_FAMILY_THRESHOLD_REOPEN",
        "NO_SECOND_PROVIDER",
    ]
    discovery: list[dict[str, object]] = []

    def fail(terminal: str, extra: dict[str, object] | None = None) -> dict[str, object]:
        receipt = _failure_receipt(
            terminal=terminal,
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_observations=discovery,
            non_claims=non_claims,
            atom_id=ATOM_ID,
            receipt_schema=RECEIPT_SCHEMA,
        )
        if extra:
            receipt.update(extra)
        return receipt

    recent_result = call(RECENT_ENDPOINT)
    _raw_observation(observation_id="DISCOVERY:RECENT", result=recent_result, credential=credential, raw_sink=raw_sink)
    recent_terminal, recent_error, recent_rows = _search_rows(recent_result)
    discovery.append(
        {
            "observation_id": "DISCOVERY:RECENT",
            "terminal": recent_terminal,
            "terminal_error": recent_error,
            "observed_at": recent_result.get("observed_at"),
            "transport": _transport_view(recent_result),
        }
    )
    if recent_terminal != "TOKEN_LIST_OBSERVED" or recent_rows is None:
        return fail(INVALID_TERMINAL)
    recent_observed_at = _parse_datetime(recent_result["observed_at"], "RECENT_TIMESTAMP_INVALID")
    candidates = select_frozen_candidates(recent_rows, excluded_mints=excluded_mints, target=TARGET_CANDIDATES)
    if len(candidates) != TARGET_CANDIDATES:
        return fail(INVALID_TERMINAL, {"frozen_mints": [str(row["id"]) for row in candidates]})
    seasoning_due = recent_observed_at + timedelta(seconds=SEASONING_SECONDS)
    for candidate in candidates:
        pool = candidate.get("firstPool")
        if not isinstance(pool, Mapping):
            continue
        try:
            created_at = _parse_datetime(pool.get("createdAt"), "FIRST_POOL_TIMESTAMP_INVALID")
        except OrganicPressureError:
            continue
        if created_at <= recent_observed_at:
            seasoning_due = max(seasoning_due, created_at + timedelta(seconds=SEASONING_SECONDS))
    wait_seconds = (seasoning_due - clock()).total_seconds()
    if wait_seconds > 0:
        waiter(wait_seconds)
    expected_mints = [str(row["id"]) for row in candidates]
    search_url = build_search_url(expected_mints)
    search_r0 = call(search_url)
    _raw_observation(observation_id="DISCOVERY:SEARCH_R0", result=search_r0, credential=credential, raw_sink=raw_sink)
    r0_terminal, r0_error, r0_rows = _search_rows(search_r0)
    discovery.append(
        {
            "observation_id": "DISCOVERY:SEARCH_R0",
            "terminal": r0_terminal,
            "terminal_error": r0_error,
            "observed_at": search_r0.get("observed_at"),
            "transport": _transport_view(search_r0),
        }
    )
    if r0_terminal != "TOKEN_LIST_OBSERVED" or r0_rows is None:
        return fail(INVALID_TERMINAL, {"frozen_mints": expected_mints})
    waiter(float(CONFIRMATION_SECONDS))
    search_r1 = call(search_url)
    _raw_observation(observation_id="DISCOVERY:SEARCH_R1", result=search_r1, credential=credential, raw_sink=raw_sink)
    r1_terminal, r1_error, r1_rows = _search_rows(search_r1)
    discovery.append(
        {
            "observation_id": "DISCOVERY:SEARCH_R1",
            "terminal": r1_terminal,
            "terminal_error": r1_error,
            "observed_at": search_r1.get("observed_at"),
            "transport": _transport_view(search_r1),
        }
    )
    if r1_terminal != "TOKEN_LIST_OBSERVED" or r1_rows is None:
        return fail(INVALID_TERMINAL, {"frozen_mints": expected_mints})
    r0_by_mint = _index_by_mint(r0_rows, expected_mints)
    r1_by_mint = _index_by_mint(r1_rows, expected_mints)
    if r0_by_mint is None or r1_by_mint is None:
        return fail(INVALID_TERMINAL, {"frozen_mints": expected_mints, "snapshot_error": "MINT_INDEX_INVALID"})
    t0 = _parse_datetime(search_r0["observed_at"], "SEARCH_R0_TIMESTAMP_INVALID")
    t1 = _parse_datetime(search_r1["observed_at"], "SEARCH_R1_TIMESTAMP_INVALID")
    candidate_observations: list[dict[str, object]] = []
    for candidate in candidates:
        mint = str(candidate["id"])
        projected = project_divergence(candidate, r0_by_mint.get(mint), r1_by_mint.get(mint), t0, t1)
        candidate_observations.append(
            {
                "mint": mint,
                "decision_snapshot_r0_at": search_r0["observed_at"],
                "decision_snapshot_r1_at": search_r1["observed_at"],
                "x_status": projected["status"],
                "x": projected.get("value"),
                "x_reason": projected.get("reason"),
                "age_r0_seconds": projected.get("age_r0_seconds"),
                "age_r1_seconds": projected.get("age_r1_seconds"),
                "confirmation_interval_seconds": projected.get("confirmation_interval_seconds"),
                "x_source": {
                    "r0_response_sha256": search_r0.get("response_sha256"),
                    "r1_response_sha256": search_r1.get("response_sha256"),
                    "r0_row_sha256": _row_sha256(r0_by_mint[mint]),
                    "r1_row_sha256": _row_sha256(r1_by_mint[mint]),
                    "field_paths": projected.get("field_paths"),
                },
                "x_inputs": projected.get("inputs"),
            }
        )
    eligible = [row for row in candidate_observations if row.get("x_status") == "ELIGIBLE"]
    if len(eligible) < MIN_ELIGIBLE:
        return fail(
            INVALID_TERMINAL,
            {
                "frozen_mints": expected_mints,
                "candidate_observations": candidate_observations,
                "decision_time_eligible": len(eligible),
            },
        )
    quote_policy = policy["quote"]
    rows_for_score: list[dict[str, object]] = []
    timing_by_mint: dict[str, tuple[datetime, datetime]] = {}
    for candidate in eligible:
        mint = str(candidate["mint"])
        buy_result = call(
            _order_url(
                input_mint=WRAPPED_SOL,
                output_mint=mint,
                amount=NOTIONAL_ATOMIC,
                slippage_bps=str(quote_policy["slippage_bps"]),
            )
        )
        buy_body = buy_result.get("body") if isinstance(buy_result.get("body"), bytes) else b""
        _assert_quote_body_has_no_transaction(buy_body)
        _raw_observation(observation_id=f"{mint}:BUY_T1", result=buy_result, credential=credential, raw_sink=raw_sink)
        classified_buy = classify_organic_quote(
            buy_body,
            http_status=buy_result.get("http_status"),
            expected_in_amount=NOTIONAL_ATOMIC,
            expected_input_mint=WRAPPED_SOL,
            expected_output_mint=mint,
        )
        quote = classified_buy.get("quote")
        buy_observed = classified_buy["terminal"] == QUOTE_OBSERVED and isinstance(quote, Mapping)
        buy_out_amount = quote.get("out_amount") if buy_observed else None
        row = {
            **candidate,
            "buy_terminal": classified_buy["terminal"],
            "buy_transport": _transport_view(buy_result),
            "buy_observed_at": buy_result.get("observed_at"),
            "buy_out_amount": buy_out_amount,
            "h900_terminal": "NOT_ATTEMPTED",
            "y": None,
        }
        if buy_observed:
            buy_observed_at = _parse_datetime(buy_result.get("observed_at"), "T1_TIMESTAMP_INVALID")
            due_at = buy_observed_at + timedelta(seconds=H900)
            lateness_deadline = due_at + timedelta(seconds=int(quote_policy["lateness_slack_seconds"]))
            timing_by_mint[mint] = (due_at, lateness_deadline)
            row["h900_due_at"] = _format_utc(due_at)
        rows_for_score.append(row)
    for row in rows_for_score:
        mint = str(row["mint"])
        if row.get("buy_terminal") != QUOTE_OBSERVED or not isinstance(row.get("buy_out_amount"), str):
            continue
        timing = timing_by_mint.get(mint)
        if timing is None:
            continue
        due_at, lateness_deadline = timing
        wait_h900 = (due_at - clock()).total_seconds()
        if wait_h900 > 0:
            waiter(wait_h900)
        if clock() > lateness_deadline:
            return fail(INVALID_TERMINAL, {"terminal_error_code": "H900_LATE_BEFORE_QUOTE", "observations": rows_for_score})
        sell_result = call(
            _order_url(
                input_mint=mint,
                output_mint=WRAPPED_SOL,
                amount=str(row["buy_out_amount"]),
                slippage_bps=SLIPPAGE_BPS,
            )
        )
        sell_body = sell_result.get("body") if isinstance(sell_result.get("body"), bytes) else b""
        _assert_quote_body_has_no_transaction(sell_body)
        _raw_observation(observation_id=f"{mint}:SELL_H900", result=sell_result, credential=credential, raw_sink=raw_sink)
        classified_sell = classify_organic_quote(
            sell_body,
            http_status=sell_result.get("http_status"),
            expected_in_amount=str(row["buy_out_amount"]),
            expected_input_mint=mint,
            expected_output_mint=WRAPPED_SOL,
        )
        sell_quote = classified_sell.get("quote")
        row["h900_terminal"] = classified_sell["terminal"]
        if classified_sell["terminal"] == QUOTE_OBSERVED and isinstance(sell_quote, Mapping):
            out_amount = sell_quote.get("out_amount")
            if isinstance(out_amount, str) and out_amount:
                try:
                    row["y"] = float(Decimal(out_amount) / Decimal(NOTIONAL_ATOMIC) - Decimal(1))
                except (InvalidOperation, OverflowError, ValueError):
                    row["y"] = None
    score = score_divergence(rows_for_score)
    return {
        "schema": RECEIPT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_outcome": score["terminal"],
        "preflight": preflight,
        "credential_reads": credential_reads,
        "provider_requests": provider_requests,
        "retries": 0,
        "fallbacks": 0,
        "execute_calls": 0,
        "discovery_observations": discovery,
        "candidate_observations": candidate_observations,
        "observations": rows_for_score,
        "score": score,
        "non_claims": non_claims,
        "factory_runner_sha256": FACTORY_RUNNER_SHA256,
    }


__all__ = [
    "ATOM_ID",
    "AUTHORITY_PHRASE",
    "CLOSE_TERMINAL",
    "EARN_TERMINAL",
    "FACTORY_RUNNER",
    "FACTORY_RUNNER_SHA256",
    "INVALID_TERMINAL",
    "X_FORMULA",
    "project_divergence",
    "run_divergence_campaign",
    "score_divergence",
    "validate_divergence_policy",
]
