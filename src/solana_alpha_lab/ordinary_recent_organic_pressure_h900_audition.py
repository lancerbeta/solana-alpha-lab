"""One fresh, quote-only organic-pressure H900 audition."""

from __future__ import annotations

import json
import hashlib
import math
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import yaml

from solana_alpha_lab.pmf_quote_slice_one_shot import QuoteShotError, credential_free_preflight
from solana_alpha_lab.provider_route_capability_registry_v10 import (
    SEARCH_ROUTE_ID,
    resolve_provider_route_v10,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (
    QualificationError,
    _transport_view,
    perform_credentialed_get,
)
from solana_alpha_lab.quote_native_evidence_fit_panel import PanelError, project_quote


ATOM_ID = "ORDINARY_RECENT_ORGANIC_PRESSURE_H900_AUDITION_V1"
API_HOST = "api.jup.ag"
RECENT_ROUTE_ID = "JUPITER-SOLANA-TOKENS-V2-RECENT-FREE-API-KEY-001"
QUOTE_ROUTE_ID = "JUPITER-SOLANA-SWAP-V2-ORDER-FREE-API-KEY-001"
RECENT_ENDPOINT = "https://api.jup.ag/tokens/v2/recent"
SEARCH_ENDPOINT = "https://api.jup.ag/tokens/v2/search"
ORDER_ENDPOINT = "https://api.jup.ag/swap/v2/order"
WRAPPED_SOL = "So11111111111111111111111111111111111111112"
NOTIONAL_ATOMIC = "10000000"
SLIPPAGE_BPS = "100"
H900 = 900
SEASONING_SECONDS = 300
TARGET_CANDIDATES = 24
CALL_CAP = 60
MARKET_EXECUTION_UNAVAILABLE = "MARKET_EXECUTION_UNAVAILABLE"
NOTIONAL_EXECUTION_UNAVAILABLE = "NOTIONAL_EXECUTION_UNAVAILABLE"
PROVIDER_MEASUREMENT_FAILURE = "PROVIDER_MEASUREMENT_FAILURE"
CLIENT_CONTRACT_FAILURE = "CLIENT_CONTRACT_FAILURE"
UNKNOWN_TYPED_FAILURE = "UNKNOWN_TYPED_FAILURE"
QUOTE_OBSERVED = "QUOTE_OBSERVED"
MAX_ATOMIC_DIGITS = 40

AUTHORITY_PHRASE = (
    "OK ORDINARY_RECENT_ORGANIC_PRESSURE_H900_AUDITION_V1: one bounded Jupiter "
    "Free-key read-only campaign using a local process-environment key only; "
    "Tokens V2 /recent plus one bulk /tokens/v2/search for frozen mints plus "
    "quote-only /swap/v2/order; x-api-key header only; no .env read, no key in "
    "URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, "
    "transaction, paid plan, second provider, retry or fallback; cash cap $0; "
    "call cap 60; global provider pace >=3s; 24 fresh project-eligible recent "
    "candidates excluding all prior consumed mints; wait until pool age >=5m "
    "before the single bulk T0 resnapshot; X = "
    "(stats5m.buyOrganicVolume - stats5m.sellOrganicVolume) / top-level "
    "liquidity from that T0 snapshot only; quote-only BUY at T0 and quote-only "
    "SELL at H900; UNKNOWN is never zero; H3600/H4, Strategy, Bot, Shadow, "
    "alpha and NetReturn forbidden."
)


class OrganicPressureError(ValueError):
    """The bounded audition contract cannot be satisfied."""

    def __init__(self, code: str, *, provider_requests: int | None = None) -> None:
        super().__init__(code)
        self.provider_requests = provider_requests


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise OrganicPressureError(code)


def _number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _parse_datetime(value: object, code: str) -> datetime:
    _require(isinstance(value, str) and bool(value), code)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise OrganicPressureError(code) from exc
    _require(parsed.tzinfo is not None, code)
    return parsed.astimezone(UTC)


def _format_utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_search_url(mints: Sequence[str]) -> str:
    values = [str(mint) for mint in mints]
    _require(1 <= len(values) <= 100, "SEARCH_MINT_COUNT_INVALID")
    _require(len(set(values)) == len(values), "SEARCH_MINT_DUPLICATE")
    _require(all(value and "," not in value for value in values), "SEARCH_MINT_INVALID")
    return f"{SEARCH_ENDPOINT}?{urlencode({'query': ','.join(values)})}"


def select_frozen_candidates(
    rows: Iterable[Mapping[str, Any]],
    *,
    excluded_mints: set[str],
    target: int = TARGET_CANDIDATES,
) -> list[dict[str, Any]]:
    _require(target > 0, "TARGET_INVALID")
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        mint = raw.get("id")
        if not isinstance(mint, str) or not mint:
            continue
        if raw.get("launchpad") != "pump.fun" or mint in excluded_mints or mint in seen:
            continue
        seen.add(mint)
        selected.append(dict(raw))
        if len(selected) == target:
            break
    return selected


def project_organic_pressure(
    row: Mapping[str, Any],
    *,
    snapshot_at: datetime,
    seasoning_seconds: int = SEASONING_SECONDS,
) -> dict[str, object]:
    _require(snapshot_at.tzinfo is not None, "SNAPSHOT_CLOCK_INVALID")
    result: dict[str, object] = {"status": "MISSING", "value": None}
    if row.get("launchpad") != "pump.fun":
        result["reason"] = "PROJECT_PREDICATE_FALSE"
        return result
    pool = row.get("firstPool")
    stats = row.get("stats5m")
    if not isinstance(pool, Mapping) or not isinstance(stats, Mapping):
        result["reason"] = "REQUIRED_OBJECT_ABSENT"
        return result
    try:
        created_at = _parse_datetime(pool.get("createdAt"), "FIRST_POOL_TIMESTAMP_INVALID")
        updated_at = _parse_datetime(row.get("updatedAt"), "UPDATED_TIMESTAMP_INVALID")
    except OrganicPressureError as exc:
        result["reason"] = str(exc)
        return result
    observed_at = snapshot_at.astimezone(UTC)
    age_seconds = (observed_at - created_at).total_seconds()
    result["age_seconds"] = age_seconds
    if created_at > observed_at:
        result["reason"] = "FIRST_POOL_TIMESTAMP_IN_FUTURE"
        return result
    if age_seconds < seasoning_seconds:
        result["status"] = "TOO_YOUNG"
        result["reason"] = "POOL_AGE_BELOW_SEASONING"
        return result
    if updated_at < created_at:
        result["reason"] = "UPDATED_TIMESTAMP_BEFORE_POOL_CREATION"
        return result
    if updated_at > observed_at:
        result["reason"] = "UPDATED_TIMESTAMP_IN_FUTURE"
        return result
    liquidity = row.get("liquidity")
    buy = stats.get("buyOrganicVolume")
    sell = stats.get("sellOrganicVolume")
    if not (
        _number(liquidity)
        and float(liquidity) > 0
        and _number(buy)
        and _number(sell)
        and float(buy) >= 0
        and float(sell) >= 0
    ):
        result["reason"] = "ORGANIC_OR_LIQUIDITY_FIELD_MISSING_OR_INVALID"
        return result
    value = (float(buy) - float(sell)) / float(liquidity)
    if not math.isfinite(value):
        result["reason"] = "ORGANIC_PRESSURE_NONFINITE"
        return result
    result["status"] = "ELIGIBLE"
    result["value"] = value
    return result


def _valid_atomic_amount(value: object) -> bool:
    if not isinstance(value, str) or not value.isdigit() or len(value) > MAX_ATOMIC_DIGITS:
        return False
    try:
        return int(value) > 0
    except ValueError:
        return False


def classify_organic_quote(
    body: bytes,
    *,
    http_status: int | None,
    expected_in_amount: str | None = None,
    expected_input_mint: str | None = None,
    expected_output_mint: str | None = None,
) -> dict[str, object]:
    if http_status is None or http_status in {401, 403, 404, 429} or http_status >= 500:
        return {"terminal": PROVIDER_MEASUREMENT_FAILURE, "y": None, "quote": None}
    if http_status not in {200, 400, 422}:
        return {"terminal": PROVIDER_MEASUREMENT_FAILURE, "y": None, "quote": None}
    try:
        quote = project_quote(body)
    except (PanelError, AttributeError, TypeError):
        return {
            "terminal": CLIENT_CONTRACT_FAILURE if http_status == 400 else PROVIDER_MEASUREMENT_FAILURE,
            "y": None,
            "quote": None,
        }
    terminal = str(quote.get("terminal_class") or UNKNOWN_TYPED_FAILURE)
    if http_status != 200 and terminal == QUOTE_OBSERVED:
        terminal = CLIENT_CONTRACT_FAILURE if http_status in {400, 422} else PROVIDER_MEASUREMENT_FAILURE
    if terminal == QUOTE_OBSERVED:
        if not _valid_atomic_amount(quote.get("in_amount")) or not _valid_atomic_amount(quote.get("out_amount")):
            terminal = CLIENT_CONTRACT_FAILURE
        elif expected_in_amount is not None and quote.get("in_amount") != str(expected_in_amount):
            terminal = CLIENT_CONTRACT_FAILURE
        elif expected_input_mint is not None and quote.get("input_mint") != str(expected_input_mint):
            terminal = CLIENT_CONTRACT_FAILURE
        elif expected_output_mint is not None and quote.get("output_mint") != str(expected_output_mint):
            terminal = CLIENT_CONTRACT_FAILURE
    return {"terminal": terminal, "y": None, "quote": quote}


def _kendall_tau_b(rows: Sequence[Mapping[str, Any]]) -> float | None:
    pairs = 0
    concordant = 0
    discordant = 0
    ties_x = 0
    ties_y = 0
    ties_both = 0
    for left_index, left in enumerate(rows):
        for right in rows[left_index + 1 :]:
            x_left = float(left["x"])
            x_right = float(right["x"])
            y_left = float(left["y"])
            y_right = float(right["y"])
            dx = x_left - x_right
            dy = y_left - y_right
            pairs += 1
            if dx == 0 and dy == 0:
                ties_both += 1
            elif dx == 0:
                ties_x += 1
            elif dy == 0:
                ties_y += 1
            elif dx * dy > 0:
                concordant += 1
            else:
                discordant += 1
    if pairs == 0:
        return None
    denominator = math.sqrt(
        (concordant + discordant + ties_x)
        * (concordant + discordant + ties_y)
    )
    if denominator == 0:
        return 0.0
    return (concordant - discordant) / denominator


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def score_audition(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_decision_time_eligible: int,
    min_rankable_h900: int,
    tau_floor: float,
    leave_one_out_positive_share: float,
    close_terminal: str = "CLOSE_ORGANIC_PRESSURE_CANDIDATE",
) -> dict[str, object]:
    eligible = [row for row in rows if _number(row.get("x"))]
    rankable = [
        row
        for row in eligible
        if row.get("h900_terminal") == QUOTE_OBSERVED and _number(row.get("y"))
    ]
    result: dict[str, object] = {
        "decision_time_eligible": len(eligible),
        "rankable_h900": len(rankable),
        "tau_b": None,
        "top_quartile_median_y": None,
        "rest_median_y": None,
        "leave_one_out_positive_share": None,
        "selected_market_execution_unavailable": False,
        "selected_top_quartile_non_quote": False,
    }
    if len(eligible) < min_decision_time_eligible or len(rankable) < min_rankable_h900:
        return {"terminal": "INVALID_EVIDENCE_YIELD", **result}
    tau = _kendall_tau_b(rankable)
    top_count = max(1, math.ceil(len(eligible) / 4))
    ordered = sorted(eligible, key=lambda row: (-float(row["x"]), str(row.get("mint"))))
    top = ordered[:top_count]
    rest = ordered[top_count:]
    top_rankable = [row for row in top if row in rankable]
    rest_rankable = [row for row in rest if row in rankable]
    loo_positive = 0
    loo_total = 0
    if len(rankable) > 2:
        for removed in range(len(rankable)):
            subset = [row for index, row in enumerate(rankable) if index != removed]
            loo_tau = _kendall_tau_b(subset)
            if loo_tau is not None:
                loo_total += 1
                loo_positive += int(loo_tau > 0)
    loo_share = (loo_positive / loo_total) if loo_total else None
    result.update(
        {
            "tau_b": tau,
            "top_quartile_median_y": _median([float(row["y"]) for row in top_rankable]),
            "rest_median_y": _median([float(row["y"]) for row in rest_rankable]),
            "leave_one_out_positive_share": loo_share,
            "selected_market_execution_unavailable": any(
                row.get("h900_terminal") == MARKET_EXECUTION_UNAVAILABLE for row in top
            ),
            "selected_top_quartile_non_quote": any(
                row.get("h900_terminal") != QUOTE_OBSERVED for row in top
            ),
        }
    )
    if bool(result["selected_top_quartile_non_quote"]) and not bool(
        result["selected_market_execution_unavailable"]
    ):
        return {"terminal": "INVALID_EVIDENCE_YIELD", **result}
    passes = (
        tau is not None
        and tau >= tau_floor
        and result["top_quartile_median_y"] is not None
        and float(result["top_quartile_median_y"]) > 0
        and result["rest_median_y"] is not None
        and float(result["top_quartile_median_y"]) > float(result["rest_median_y"])
        and loo_share is not None
        and loo_share >= leave_one_out_positive_share
        and not bool(result["selected_market_execution_unavailable"])
    )
    return {"terminal": "EARN_FRESH_OOS" if passes else close_terminal, **result}


def score_sign_only_kendall(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_decision_time_eligible: int,
    min_rankable_h900: int,
    expected_direction: str,
    close_terminal: str,
    earn_terminal: str,
    invalid_terminal: str,
) -> dict[str, object]:
    _require(expected_direction == "NEGATIVE", "EXPECTED_DIRECTION_UNSUPPORTED")
    eligible = [row for row in rows if _number(row.get("x"))]
    rankable = [
        row
        for row in eligible
        if row.get("h900_terminal") == QUOTE_OBSERVED and _number(row.get("y"))
    ]
    result: dict[str, object] = {
        "decision_time_eligible": len(eligible),
        "rankable_h900": len(rankable),
        "tau_b": None,
        "score_kind": "SIGN_ONLY_KENDALL_TAU_B",
        "expected_direction": expected_direction,
        "top_quartile_median_y": None,
        "rest_median_y": None,
        "leave_one_out_positive_share": None,
        "selected_market_execution_unavailable": False,
        "selected_top_quartile_non_quote": False,
    }
    if len(eligible) < min_decision_time_eligible or len(rankable) < min_rankable_h900:
        return {"terminal": invalid_terminal, **result}
    x_values = [float(row["x"]) for row in rankable]
    y_values = [float(row["y"]) for row in rankable]
    if len(set(x_values)) < 2 or len(set(y_values)) < 2:
        return {"terminal": invalid_terminal, **result}
    tau = _kendall_tau_b(rankable)
    result["tau_b"] = tau
    if tau is None:
        return {"terminal": invalid_terminal, **result}
    if tau < 0:
        return {"terminal": earn_terminal, **result}
    return {"terminal": close_terminal, **result}


LEGACY_DECISION_KEYS = (
    "tau_b_floor",
    "top_x_quartile",
    "top_quartile_median_y_gt",
    "top_quartile_median_gt_rest",
    "leave_one_out_positive_share",
    "selected_market_execution_unavailable_forbidden",
)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def validate_policy(
    policy: Mapping[str, Any],
    *,
    root: Path,
    expected_atom_id: str = ATOM_ID,
    expected_authority_phrase: str = AUTHORITY_PHRASE,
    expected_schema: str = "smial.ordinary-recent-organic-pressure-h900-audition",
    expected_x_formula: str = (
        "(stats5m.buyOrganicVolume - stats5m.sellOrganicVolume) / top-level liquidity"
    ),
    require_legacy_decision_rule: bool = True,
) -> None:
    _require(policy.get("schema") == expected_schema, "SCHEMA_DRIFT")
    _require(policy.get("schema_version") == "1.0", "SCHEMA_VERSION_DRIFT")
    _require(policy.get("atom_id") == expected_atom_id, "ATOM_ID_DRIFT")
    authority = _mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    _require(authority.get("owner_phrase") == expected_authority_phrase, "AUTHORITY_PHRASE_DRIFT")
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
    routes = _mapping(policy.get("routes"), "ROUTES_INVALID")
    recent = _mapping(routes.get("recent"), "RECENT_ROUTE_INVALID")
    search = _mapping(routes.get("search"), "SEARCH_ROUTE_INVALID")
    quote = _mapping(routes.get("quote"), "QUOTE_ROUTE_INVALID")
    _require(recent.get("route_id") == RECENT_ROUTE_ID, "RECENT_ROUTE_ID_DRIFT")
    _require(search.get("route_id") == SEARCH_ROUTE_ID, "SEARCH_ROUTE_ID_DRIFT")
    _require(quote.get("route_id") == QUOTE_ROUTE_ID, "QUOTE_ROUTE_ID_DRIFT")
    _require(recent.get("endpoint") == RECENT_ENDPOINT, "RECENT_ENDPOINT_DRIFT")
    _require(search.get("endpoint") == SEARCH_ENDPOINT, "SEARCH_ENDPOINT_DRIFT")
    _require(quote.get("endpoint") == ORDER_ENDPOINT, "QUOTE_ENDPOINT_DRIFT")
    _require(recent.get("method") == "GET" and search.get("method") == "GET" and quote.get("method") == "GET", "METHOD_DRIFT")
    population = _mapping(policy.get("population"), "POPULATION_INVALID")
    _require(population.get("launchpad") == "pump.fun", "POPULATION_PREDICATE_DRIFT")
    _require(population.get("target_candidates") == TARGET_CANDIDATES, "TARGET_CANDIDATE_DRIFT")
    _require(population.get("seasoning_seconds") == SEASONING_SECONDS, "SEASONING_DRIFT")
    _require(population.get("prior_mints_required") is True, "PRIOR_MINT_EXCLUSION_NOT_REQUIRED")
    snapshot = _mapping(policy.get("decision_snapshot"), "DECISION_SNAPSHOT_INVALID")
    _require(snapshot.get("source") == "TOKENS_V2_SEARCH_BULK_RESPONSE", "SNAPSHOT_SOURCE_DRIFT")
    _require(snapshot.get("one_call_max_mints") == 100, "SEARCH_BATCH_LIMIT_DRIFT")
    _require(snapshot.get("x_formula") == expected_x_formula, "X_FORMULA_DRIFT")
    _require(snapshot.get("missing_is_zero") is False, "MISSING_ZERO_DRIFT")
    quote_policy = _mapping(policy.get("quote"), "QUOTE_POLICY_INVALID")
    _require(quote_policy.get("slippage_bps") == SLIPPAGE_BPS, "SLIPPAGE_DRIFT")
    _require(quote_policy.get("notional_atomic") == NOTIONAL_ATOMIC, "NOTIONAL_DRIFT")
    _require(quote_policy.get("horizon_seconds") == H900, "H900_DRIFT")
    _require(quote_policy.get("lateness_slack_seconds") == 120, "LATENESS_SLACK_DRIFT")
    decision_rule = _mapping(policy.get("decision_rule"), "DECISION_RULE_INVALID")
    _require(decision_rule.get("min_decision_time_eligible") == 18, "DECISION_YIELD_DRIFT")
    _require(decision_rule.get("min_rankable_h900") == 14, "RANKABLE_YIELD_DRIFT")
    if require_legacy_decision_rule:
        _require(decision_rule.get("tau_b_floor") == "0.20", "TAU_FLOOR_DRIFT")
        _require(decision_rule.get("top_x_quartile") is True, "TOP_QUARTILE_DRIFT")
        _require(decision_rule.get("top_quartile_median_y_gt") == 0, "TOP_MEDIAN_FLOOR_DRIFT")
        _require(decision_rule.get("top_quartile_median_gt_rest") is True, "TOP_REST_MEDIAN_DRIFT")
        _require(decision_rule.get("leave_one_out_positive_share") == "0.75", "LOO_FLOOR_DRIFT")
        _require(decision_rule.get("selected_market_execution_unavailable_forbidden") is True, "MARKET_TERMINAL_RULE_DRIFT")
    else:
        for key in LEGACY_DECISION_KEYS:
            _require(key not in decision_rule, f"LEGACY_DECISION_KEY_FORBIDDEN:{key}")
        _require(decision_rule.get("expected_direction") == "NEGATIVE", "EXPECTED_DIRECTION_DRIFT")
        _require(decision_rule.get("score_kind") == "SIGN_ONLY_KENDALL_TAU_B", "SCORE_KIND_DRIFT")
        for name in ("close_terminal", "earn_terminal", "invalid_terminal"):
            value = decision_rule.get(name)
            _require(isinstance(value, str) and bool(value), f"DECISION_TERMINAL_DRIFT:{name}")
    controls = _mapping(policy.get("execution_controls"), "CONTROLS_INVALID")
    _require(controls.get("retries") == 0, "RETRY_NOT_FORBIDDEN")
    _require(controls.get("fallback") is False, "FALLBACK_NOT_FORBIDDEN")
    _require(controls.get("persist_transaction_bytes") is False, "TX_PERSIST_NOT_FORBIDDEN")
    _require(controls.get("provider_requests_max") == CALL_CAP, "REQUEST_BUDGET_DRIFT")
    _require(controls.get("min_interval_seconds") == 3, "PACE_DRIFT")
    _require(controls.get("second_provider") is False, "SECOND_PROVIDER_NOT_FORBIDDEN")
    _require(controls.get("paid_plan") is False, "PAID_PLAN_NOT_FORBIDDEN")
    _require(controls.get("background_scheduler") is False, "SCHEDULER_NOT_FORBIDDEN")
    retention = _mapping(policy.get("raw_retention"), "RAW_RETENTION_INVALID")
    _require(retention.get("body") == "A4_OUTSIDE_GIT", "RAW_BODY_RETENTION_DRIFT")
    _require(retention.get("response_headers") == "SAFE_ALLOWLIST_ONLY", "RAW_HEADER_RETENTION_DRIFT")
    non_claims = _mapping(policy.get("non_claims"), "NON_CLAIMS_INVALID")
    for name in ("alpha", "netreturn", "execution", "strategy", "shadow"):
        _require(non_claims.get(name) is False, f"NON_CLAIM_DRIFT:{name}")


def _search_rows(result: Mapping[str, object]) -> tuple[str, str | None, list[Mapping[str, Any]] | None]:
    status = result.get("http_status")
    if status is None:
        return PROVIDER_MEASUREMENT_FAILURE, "TRANSPORT_UNKNOWN", None
    if int(status) in {401, 403, 429} or int(status) >= 500:
        return PROVIDER_MEASUREMENT_FAILURE, f"HTTP_{status}", None
    if int(status) != 200:
        return CLIENT_CONTRACT_FAILURE, f"HTTP_{status}", None
    try:
        payload = json.loads(bytes(result["body"]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return PROVIDER_MEASUREMENT_FAILURE, "JSON", None
    if not isinstance(payload, list):
        return PROVIDER_MEASUREMENT_FAILURE, "NOT_LIST", None
    return "TOKEN_LIST_OBSERVED", None, [item for item in payload if isinstance(item, Mapping)]


def _row_sha256(row: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OrganicPressureError("SEARCH_ROW_NOT_CANONICAL") from exc
    return hashlib.sha256(encoded).hexdigest()


def _order_url(*, input_mint: str, output_mint: str, amount: str, slippage_bps: str) -> str:
    query = urlencode(
        [
            ("inputMint", input_mint),
            ("outputMint", output_mint),
            ("amount", amount),
            ("slippageBps", slippage_bps),
        ]
    )
    return f"{ORDER_ENDPOINT}?{query}"


def _body_contains_secret(body: object, secret: str) -> bool:
    return isinstance(body, bytes) and bool(secret) and secret.encode("utf-8") in body


def _assert_quote_body_has_no_transaction(body: bytes) -> None:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    if isinstance(payload, Mapping) and payload.get("transaction") is not None:
        raise OrganicPressureError("QUOTE_RETURNED_TRANSACTION")


def _raw_observation(
    *,
    observation_id: str,
    result: Mapping[str, object],
    credential: str,
    raw_sink: Any,
) -> None:
    body = result.get("body")
    if raw_sink is None or not isinstance(body, bytes):
        return
    _require(not _body_contains_secret(body, credential), "RAW_BODY_CONTAINS_CREDENTIAL")
    observed_at = result.get("observed_at")
    _require(isinstance(observed_at, str), "OBSERVED_AT_MISSING")
    raw_sink(observation_id, body, observed_at)


def _failure_receipt(
    *,
    terminal: str,
    preflight: Mapping[str, Any],
    credential_reads: int,
    provider_requests: int,
    discovery_observations: list[dict[str, object]],
    non_claims: list[str],
    atom_id: str = ATOM_ID,
    receipt_schema: str = "smial.ordinary-recent-organic-pressure-h900-audition.runtime-receipt",
) -> dict[str, object]:
    return {
        "schema": receipt_schema,
        "schema_version": "1.0",
        "atom_id": atom_id,
        "terminal_outcome": terminal,
        "preflight": dict(preflight),
        "credential_reads": credential_reads,
        "provider_requests": provider_requests,
        "retries": 0,
        "fallbacks": 0,
        "execute_calls": 0,
        "discovery_observations": discovery_observations,
        "candidate_observations": [],
        "observations": [],
        "decision_time_eligible": 0,
        "rankable_h900": 0,
        "score": {"terminal": terminal},
        "non_claims": non_claims,
    }


def run_campaign(
    policy: Mapping[str, Any],
    *,
    authority_phrase: str,
    reservation: Mapping[str, Any],
    excluded_mints: set[str],
    credential_loader: Any,
    preflight_fn: Any = credential_free_preflight,
    opener: object | None = None,
    clock: Any = lambda: datetime.now(UTC),
    sleeper: Any = time.sleep,
    monotonic_clock: Any = time.monotonic,
    raw_sink: Any = None,
    atom_id: str = ATOM_ID,
    expected_authority_phrase: str = AUTHORITY_PHRASE,
    expected_schema: str = "smial.ordinary-recent-organic-pressure-h900-audition",
    expected_x_formula: str = (
        "(stats5m.buyOrganicVolume - stats5m.sellOrganicVolume) / top-level liquidity"
    ),
    receipt_schema: str = "smial.ordinary-recent-organic-pressure-h900-audition.runtime-receipt",
    close_terminal: str = "CLOSE_ORGANIC_PRESSURE_CANDIDATE",
    project_x: Any = None,
    score_fn: Any = None,
    require_legacy_decision_rule: bool = True,
    insufficient_yield_terminal: str = "INVALID_EVIDENCE_YIELD",
) -> dict[str, object]:
    validate_policy(
        policy,
        root=Path(__file__).resolve().parents[2],
        expected_atom_id=atom_id,
        expected_authority_phrase=expected_authority_phrase,
        expected_schema=expected_schema,
        expected_x_formula=expected_x_formula,
        require_legacy_decision_rule=require_legacy_decision_rule,
    )
    authority = _mapping(policy["external_authority"], "AUTHORITY_INVALID")
    _require(authority_phrase == authority.get("owner_phrase") == expected_authority_phrase, "AUTHORITY_PHRASE_INVALID")
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
    waiter = sleeper
    monotonic = monotonic_clock
    selected_project_x = project_x

    def default_project_x(
        _recent_row: Mapping[str, Any],
        t5_row: Mapping[str, Any] | None,
        snapshot_at: datetime,
    ) -> dict[str, object]:
        if not isinstance(t5_row, Mapping):
            return {"status": "MISSING", "value": None, "reason": "SEARCH_MINT_NOT_RETURNED"}
        return project_organic_pressure(t5_row, snapshot_at=snapshot_at)

    if selected_project_x is None:
        selected_project_x = default_project_x

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
            raise OrganicPressureError(
                "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
                provider_requests=provider_requests,
            )
        result["observed_at"] = _format_utc(clock())
        return result

    non_claims = [
        "NO_EXECUTE",
        "NO_TAKER_OR_SIGNER",
        "NO_TRANSACTION_BYTES_IN_GIT",
        "NO_ALPHA",
        "NO_NETRETURN",
        "NO_STRATEGY_OR_SHADOW",
        "NO_H3600_OR_H4",
        "NO_SECOND_PROVIDER",
    ]
    discovery_observations: list[dict[str, object]] = []
    recent_result = call(RECENT_ENDPOINT)
    _raw_observation(
        observation_id="DISCOVERY:RECENT",
        result=recent_result,
        credential=credential,
        raw_sink=raw_sink,
    )
    recent_terminal, recent_error, recent_rows = _search_rows(recent_result)
    discovery_observations.append(
        {
            "observation_id": "DISCOVERY:RECENT",
            "terminal": recent_terminal,
            "terminal_error": recent_error,
            "observed_at": recent_result.get("observed_at"),
            "transport": _transport_view(recent_result),
            "consumed_call": True,
        }
    )
    if recent_terminal != "TOKEN_LIST_OBSERVED" or recent_rows is None:
        return _failure_receipt(
            terminal="INVALID_EVIDENCE_REPLAN",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_observations=discovery_observations,
            non_claims=non_claims,
            atom_id=atom_id,
            receipt_schema=receipt_schema,
        )
    try:
        recent_observed_at = _parse_datetime(recent_result["observed_at"], "RECENT_TIMESTAMP_INVALID")
    except OrganicPressureError as exc:
        return _failure_receipt(
            terminal="INVALID_EVIDENCE_REPLAN",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_observations=discovery_observations,
            non_claims=non_claims,
            atom_id=atom_id,
            receipt_schema=receipt_schema,
        ) | {"terminal_error_code": str(exc)}
    candidates = select_frozen_candidates(
        recent_rows,
        excluded_mints=excluded_mints,
        target=TARGET_CANDIDATES,
    )
    if len(candidates) != TARGET_CANDIDATES:
        return _failure_receipt(
            terminal=insufficient_yield_terminal,
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_observations=discovery_observations,
            non_claims=non_claims,
            atom_id=atom_id,
            receipt_schema=receipt_schema,
        ) | {"frozen_mints": [str(row["id"]) for row in candidates]}
    seasoning_due = recent_observed_at + timedelta(seconds=SEASONING_SECONDS)
    for candidate in candidates:
        pool = candidate.get("firstPool")
        if not isinstance(pool, Mapping):
            continue
        try:
            created_at = _parse_datetime(pool.get("createdAt"), "FIRST_POOL_TIMESTAMP_INVALID")
        except OrganicPressureError:
            continue
        if created_at > recent_observed_at:
            continue
        seasoning_due = max(seasoning_due, created_at + timedelta(seconds=SEASONING_SECONDS))
    wait_seconds = (seasoning_due - clock()).total_seconds()
    if wait_seconds > 0:
        waiter(wait_seconds)
    search_result = call(build_search_url([str(row["id"]) for row in candidates]))
    _raw_observation(
        observation_id="DISCOVERY:SEARCH_T5",
        result=search_result,
        credential=credential,
        raw_sink=raw_sink,
    )
    search_terminal, search_error, search_rows = _search_rows(search_result)
    discovery_observations.append(
        {
            "observation_id": "DISCOVERY:SEARCH_T5",
            "terminal": search_terminal,
            "terminal_error": search_error,
            "observed_at": search_result.get("observed_at"),
            "transport": _transport_view(search_result),
            "consumed_call": True,
        }
    )
    if search_terminal != "TOKEN_LIST_OBSERVED" or search_rows is None:
        return _failure_receipt(
            terminal="INVALID_EVIDENCE_REPLAN",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_observations=discovery_observations,
            non_claims=non_claims,
            atom_id=atom_id,
            receipt_schema=receipt_schema,
        ) | {"frozen_mints": [str(row["id"]) for row in candidates]}
    expected_mints = [str(row["id"]) for row in candidates]
    expected_mint_set = set(expected_mints)
    search_by_mint: dict[str, Mapping[str, Any]] = {}
    duplicate_mints: list[str] = []
    for row in search_rows:
        mint = row.get("id")
        if not isinstance(mint, str) or mint not in expected_mint_set:
            continue
        if mint in search_by_mint:
            duplicate_mints.append(mint)
            continue
        search_by_mint[mint] = row
    missing_mints = [mint for mint in expected_mints if mint not in search_by_mint]
    if duplicate_mints or missing_mints:
        return _failure_receipt(
            terminal="INVALID_EVIDENCE_REPLAN",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_observations=discovery_observations,
            non_claims=non_claims,
            atom_id=atom_id,
            receipt_schema=receipt_schema,
        ) | {
            "frozen_mints": expected_mints,
            "snapshot_response_sha256": search_result.get("response_sha256"),
            "snapshot_error": {
                "duplicate_mints": sorted(set(duplicate_mints)),
                "missing_mints": missing_mints,
            },
        }
    try:
        search_observed_at = _parse_datetime(search_result["observed_at"], "SEARCH_TIMESTAMP_INVALID")
    except OrganicPressureError as exc:
        return _failure_receipt(
            terminal="INVALID_EVIDENCE_REPLAN",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_observations=discovery_observations,
            non_claims=non_claims,
            atom_id=atom_id,
            receipt_schema=receipt_schema,
        ) | {
            "frozen_mints": expected_mints,
            "snapshot_response_sha256": search_result.get("response_sha256"),
            "terminal_error_code": str(exc),
        }
    candidate_observations: list[dict[str, object]] = []
    for candidate in candidates:
        mint = str(candidate["id"])
        row = search_by_mint.get(mint)
        x_result = selected_project_x(candidate, row if isinstance(row, Mapping) else None, search_observed_at)
        row_sha256 = _row_sha256(row) if isinstance(row, Mapping) else None
        stats = row.get("stats5m") if isinstance(row, Mapping) else None
        first_pool = row.get("firstPool") if isinstance(row, Mapping) else None
        default_field_paths = [
            "stats5m.buyOrganicVolume",
            "stats5m.sellOrganicVolume",
            "liquidity",
            "firstPool.createdAt",
            "updatedAt",
        ]
        default_inputs = {
            "stats5m.buyOrganicVolume": stats.get("buyOrganicVolume") if isinstance(stats, Mapping) else None,
            "stats5m.sellOrganicVolume": stats.get("sellOrganicVolume") if isinstance(stats, Mapping) else None,
            "liquidity": row.get("liquidity") if isinstance(row, Mapping) else None,
            "firstPool.createdAt": first_pool.get("createdAt") if isinstance(first_pool, Mapping) else None,
            "updatedAt": row.get("updatedAt") if isinstance(row, Mapping) else None,
        }
        field_paths = x_result.get("field_paths")
        inputs = x_result.get("inputs")
        candidate_observations.append(
            {
                "mint": mint,
                "decision_snapshot_at": search_result["observed_at"],
                "x_status": x_result["status"],
                "x": x_result.get("value"),
                "x_reason": x_result.get("reason"),
                "age_seconds": x_result.get("age_seconds"),
                "x_source": {
                    "observation_id": "DISCOVERY:SEARCH_T5",
                    "response_sha256": search_result.get("response_sha256"),
                    "recent_response_sha256": recent_result.get("response_sha256"),
                    "row_sha256": row_sha256,
                    "recent_row_sha256": _row_sha256(candidate),
                    "row_mint": mint,
                    "field_paths": field_paths if isinstance(field_paths, list) else default_field_paths,
                },
                "x_inputs": inputs if isinstance(inputs, Mapping) else default_inputs,
            }
        )
    eligible = [row for row in candidate_observations if row.get("x_status") == "ELIGIBLE"]
    decision_rules = _mapping(policy["decision_rule"], "DECISION_RULE_INVALID")
    if len(eligible) < int(decision_rules["min_decision_time_eligible"]):
        return _failure_receipt(
            terminal=insufficient_yield_terminal,
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_observations=discovery_observations,
            non_claims=non_claims,
            atom_id=atom_id,
            receipt_schema=receipt_schema,
        ) | {
            "frozen_mints": [str(row["id"]) for row in candidates],
            "candidate_observations": candidate_observations,
            "decision_time_eligible": len(eligible),
        }
    quote_policy = _mapping(policy["quote"], "QUOTE_POLICY_INVALID")
    rows_for_score: list[dict[str, object]] = []
    timing_by_mint: dict[str, tuple[datetime, datetime]] = {}
    panel_started_at = clock()
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
        observation_id = f"{mint}:BUY_T0"
        buy_body = buy_result.get("body") if isinstance(buy_result.get("body"), bytes) else b""
        _assert_quote_body_has_no_transaction(buy_body)
        _raw_observation(observation_id=observation_id, result=buy_result, credential=credential, raw_sink=raw_sink)
        classified_buy = classify_organic_quote(
            buy_body,
            http_status=buy_result.get("http_status"),
            expected_in_amount=NOTIONAL_ATOMIC,
            expected_input_mint=WRAPPED_SOL,
            expected_output_mint=mint,
        )
        quote = classified_buy.get("quote")
        buy_observed = classified_buy["terminal"] == QUOTE_OBSERVED and isinstance(quote, Mapping)
        buy_in_amount = quote.get("in_amount") if buy_observed else None
        buy_out_amount = quote.get("out_amount") if buy_observed else None
        buy_clock_error: str | None = None
        buy_observed_at: datetime | None = None
        if buy_observed:
            try:
                buy_observed_at = _parse_datetime(buy_result.get("observed_at"), "T0_TIMESTAMP_INVALID")
            except OrganicPressureError as exc:
                buy_clock_error = str(exc)
        buy_observation_id = f"{mint}:BUY_T0"
        row = {
            **candidate,
            "buy_terminal": classified_buy["terminal"],
            "buy_transport": _transport_view(buy_result),
            "buy_observed_at": buy_result.get("observed_at"),
            "buy_clock_valid": buy_observed and buy_clock_error is None,
            "buy_clock_error": buy_clock_error,
            "buy_out_amount": buy_out_amount,
            "t0": {
                "source_observation_id": buy_observation_id,
                "observed_at": buy_result.get("observed_at"),
                "input_mint": quote.get("input_mint") if buy_observed else None,
                "output_mint": quote.get("output_mint") if buy_observed else None,
                "expected_input_amount": NOTIONAL_ATOMIC,
                "input_amount": buy_in_amount,
                "output_amount": buy_out_amount,
            },
            "h900_terminal": "NOT_ATTEMPTED",
            "h900": None,
            "y": None,
        }
        if buy_observed_at is not None and buy_clock_error is None:
            due_at = buy_observed_at + timedelta(seconds=H900)
            lateness_deadline = due_at + timedelta(seconds=int(quote_policy["lateness_slack_seconds"]))
            timing_by_mint[mint] = (due_at, lateness_deadline)
            row["h900_due_at"] = _format_utc(due_at)
            row["h900_lateness_deadline"] = _format_utc(lateness_deadline)
        rows_for_score.append(row)

    h900_schedule = [
        {
            "mint": str(row["mint"]),
            "t0_observed_at": row["buy_observed_at"],
            "due_at": row.get("h900_due_at"),
            "lateness_deadline": row.get("h900_lateness_deadline"),
        }
        for row in rows_for_score
        if str(row.get("mint")) in timing_by_mint
    ]
    timing_fields = {
        "h900_schedule": h900_schedule,
        "h900_due_at": h900_schedule[0]["due_at"] if h900_schedule else None,
        "h900_lateness_deadline": h900_schedule[0]["lateness_deadline"] if h900_schedule else None,
    }
    invalid_t0_clock = next(
        (row for row in rows_for_score if row.get("buy_clock_error")),
        None,
    )
    if invalid_t0_clock is not None:
        return _failure_receipt(
            terminal="INVALID_EVIDENCE_REPLAN",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests,
            discovery_observations=discovery_observations,
            non_claims=non_claims,
            atom_id=atom_id,
            receipt_schema=receipt_schema,
        ) | {
            "frozen_mints": expected_mints,
            "candidate_observations": candidate_observations,
            "observations": rows_for_score,
            "decision_time_eligible": len(eligible),
            "t0_reference_at": _format_utc(panel_started_at),
            **timing_fields,
            "terminal_error_code": str(invalid_t0_clock["buy_clock_error"]),
        }
    for row in rows_for_score:
        if row.get("buy_terminal") != QUOTE_OBSERVED or not isinstance(row.get("buy_out_amount"), str):
            row["h900_terminal"] = "NOT_ATTEMPTED"
            continue
        mint = str(row["mint"])
        timing = timing_by_mint.get(mint)
        if timing is None:
            row["h900_terminal"] = "NOT_ATTEMPTED"
            continue
        due_at, lateness_deadline = timing
        wait_seconds = (due_at - clock()).total_seconds()
        if wait_seconds > 0:
            waiter(wait_seconds)
        if clock() > lateness_deadline:
            return _failure_receipt(
                terminal="INVALID_EVIDENCE_REPLAN",
                preflight=preflight,
                credential_reads=credential_reads,
                provider_requests=provider_requests,
                discovery_observations=discovery_observations,
                non_claims=non_claims,
                atom_id=atom_id,
                receipt_schema=receipt_schema,
            ) | {
                "frozen_mints": expected_mints,
                "candidate_observations": candidate_observations,
                "observations": rows_for_score,
                "decision_time_eligible": len(eligible),
                "t0_reference_at": _format_utc(panel_started_at),
                **timing_fields,
                "terminal_error_code": "H900_LATE_BEFORE_QUOTE",
            }
        sell_result = call(
            _order_url(
                input_mint=mint,
                output_mint=WRAPPED_SOL,
                amount=str(row["buy_out_amount"]),
                slippage_bps=SLIPPAGE_BPS,
            )
        )
        observation_id = f"{mint}:SELL_H900"
        sell_body = sell_result.get("body") if isinstance(sell_result.get("body"), bytes) else b""
        _assert_quote_body_has_no_transaction(sell_body)
        _raw_observation(observation_id=observation_id, result=sell_result, credential=credential, raw_sink=raw_sink)
        try:
            sell_observed_at = _parse_datetime(sell_result["observed_at"], "H900_TIMESTAMP_INVALID")
        except OrganicPressureError as exc:
            return _failure_receipt(
                terminal="INVALID_EVIDENCE_REPLAN",
                preflight=preflight,
                credential_reads=credential_reads,
                provider_requests=provider_requests,
                discovery_observations=discovery_observations,
                non_claims=non_claims,
                atom_id=atom_id,
                receipt_schema=receipt_schema,
            ) | {
                "frozen_mints": expected_mints,
                "candidate_observations": candidate_observations,
                "observations": rows_for_score,
                "decision_time_eligible": len(eligible),
                "t0_reference_at": _format_utc(panel_started_at),
                **timing_fields,
                "terminal_error_code": str(exc),
            }
        if sell_observed_at < due_at:
            row["h900_terminal"] = PROVIDER_MEASUREMENT_FAILURE
            row["h900"] = {
                "source_observation_id": f"{mint}:SELL_H900",
                "observed_at": sell_result.get("observed_at"),
                "transport": _transport_view(sell_result),
                "timing": "BEFORE_H900",
            }
            return _failure_receipt(
                terminal="INVALID_EVIDENCE_REPLAN",
                preflight=preflight,
                credential_reads=credential_reads,
                provider_requests=provider_requests,
                discovery_observations=discovery_observations,
                non_claims=non_claims,
                atom_id=atom_id,
                receipt_schema=receipt_schema,
            ) | {
                "frozen_mints": expected_mints,
                "candidate_observations": candidate_observations,
                "observations": rows_for_score,
                "decision_time_eligible": len(eligible),
                "t0_reference_at": _format_utc(panel_started_at),
                **timing_fields,
                "terminal_error_code": "H900_EARLY",
            }
        if sell_observed_at > lateness_deadline:
            row["h900_terminal"] = PROVIDER_MEASUREMENT_FAILURE
            row["h900"] = {
                "source_observation_id": f"{mint}:SELL_H900",
                "observed_at": sell_result.get("observed_at"),
                "transport": _transport_view(sell_result),
                "lateness": "BEYOND_H900_SLACK",
            }
            return _failure_receipt(
                terminal="INVALID_EVIDENCE_REPLAN",
                preflight=preflight,
                credential_reads=credential_reads,
                provider_requests=provider_requests,
                discovery_observations=discovery_observations,
                non_claims=non_claims,
                atom_id=atom_id,
                receipt_schema=receipt_schema,
            ) | {
                "frozen_mints": expected_mints,
                "candidate_observations": candidate_observations,
                "observations": rows_for_score,
                "decision_time_eligible": len(eligible),
                "t0_reference_at": _format_utc(panel_started_at),
                **timing_fields,
                "terminal_error_code": "H900_LATE",
            }
        classified_sell = classify_organic_quote(
            sell_body,
            http_status=sell_result.get("http_status"),
            expected_in_amount=str(row["buy_out_amount"]),
            expected_input_mint=mint,
            expected_output_mint=WRAPPED_SOL,
        )
        sell_quote = classified_sell.get("quote")
        row["h900_terminal"] = classified_sell["terminal"]
        row["h900"] = {
            "source_observation_id": f"{mint}:SELL_H900",
            "observed_at": sell_result.get("observed_at"),
            "transport": _transport_view(sell_result),
            "due_at": _format_utc(due_at),
            "lateness_deadline": _format_utc(lateness_deadline),
            "input_mint": sell_quote.get("input_mint") if isinstance(sell_quote, Mapping) else None,
            "output_mint": sell_quote.get("output_mint") if isinstance(sell_quote, Mapping) else None,
            "expected_input_amount": str(row["buy_out_amount"]),
            "input_amount": sell_quote.get("in_amount") if isinstance(sell_quote, Mapping) else None,
            "output_amount": sell_quote.get("out_amount") if isinstance(sell_quote, Mapping) else None,
        }
        if classified_sell["terminal"] == QUOTE_OBSERVED and isinstance(sell_quote, Mapping):
            out_amount = sell_quote.get("out_amount")
            if isinstance(out_amount, str) and out_amount:
                try:
                    row["y"] = float(Decimal(out_amount) / Decimal(NOTIONAL_ATOMIC) - Decimal(1))
                except (InvalidOperation, OverflowError, ValueError):
                    row["h900_terminal"] = CLIENT_CONTRACT_FAILURE
                    row["y"] = None
    if score_fn is None:
        score = score_audition(
            rows_for_score,
            min_decision_time_eligible=int(decision_rules["min_decision_time_eligible"]),
            min_rankable_h900=int(decision_rules["min_rankable_h900"]),
            tau_floor=float(decision_rules["tau_b_floor"]),
            leave_one_out_positive_share=float(decision_rules["leave_one_out_positive_share"]),
            close_terminal=close_terminal,
        )
    else:
        score = score_fn(rows_for_score)
        _require(isinstance(score, Mapping) and isinstance(score.get("terminal"), str), "SCORE_FN_INVALID")
    return {
        "schema": receipt_schema,
        "schema_version": "1.0",
        "atom_id": atom_id,
        "terminal_outcome": score["terminal"],
        "preflight": preflight,
        "credential_reads": credential_reads,
        "provider_requests": provider_requests,
        "retries": 0,
        "fallbacks": 0,
        "execute_calls": 0,
        "frozen_mints": [str(row["id"]) for row in candidates],
        "t0_reference_at": _format_utc(panel_started_at),
        **timing_fields,
        "snapshot_response_sha256": search_result.get("response_sha256"),
        "discovery_observations": discovery_observations,
        "candidate_observations": candidate_observations,
        "observations": rows_for_score,
        "decision_time_eligible": score["decision_time_eligible"],
        "rankable_h900": score["rankable_h900"],
        "score": score,
        "raw_retention": {"mode": "A4_OUTSIDE_GIT"},
        "non_claims": non_claims,
    }
