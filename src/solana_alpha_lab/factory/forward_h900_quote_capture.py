"""Reusable Jupiter free-key capture: recent → one R0 search → floor gate → R0 BUY → absolute H900 SELL.

Hypothesis logic does not belong here. Mix classification is offline over the frozen dataset.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (
    CALL_CAP,
    H900,
    NOTIONAL_ATOMIC,
    QUOTE_OBSERVED,
    RECENT_ENDPOINT,
    SEARCH_ENDPOINT,
    SLIPPAGE_BPS,
    WRAPPED_SOL,
    OrganicPressureError,
    _assert_quote_body_has_no_transaction,
    _format_utc,
    _order_url,
    _parse_datetime,
    _raw_observation,
    _search_rows,
    build_search_url,
    classify_organic_quote,
)
from solana_alpha_lab.pmf_quote_slice_one_shot import QuoteShotError, credential_free_preflight
from solana_alpha_lab.provider_route_capability_registry_v10 import (
    SEARCH_ROUTE_ID,
    V9_PATH,
    resolve_provider_route_v10,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (
    QualificationError,
    load_process_credential,
    perform_credentialed_get,
)

ATOM_ID = "FORWARD_H900_QUOTE_CAPTURE_V1"
CAPABILITY_ID = "CAP-JUPITER-FREE-KEY-FORWARD-H900-QUOTE-CAPTURE-001"
CONSUMER_HYPOTHESIS_ID = "HYP-EARLY-TAKER-VOLUME-MIX-H900-V1"
EXPERIMENT_ID = "EXP-EARLY-TAKER-VOLUME-MIX-H900-V1"
POLICY_RELATIVE = "configs/forward_h900_quote_capture_v1.yaml"
POLICY_SCHEMA = "smial.forward-h900-quote-capture"
RECEIPT_SCHEMA = "smial.forward-h900-quote-capture.runtime-receipt"
FACTORY_RUNNER = "src/solana_alpha_lab/factory/runner.py"
FACTORY_RUNNER_SHA256 = "d8d22bcb51fb6992d40f09e58274c52e0f9942c12d043cc57b96ffca524e918f"
CAPTURE_ROOT_NAME = "forward_h900_quote_capture"
MIN_ELIGIBLE_BEFORE_QUOTES = 10
QUOTE_PAIR_CAP = 29
R0_AGE_MIN = 300
R0_AGE_MAX_EXCLUSIVE = 600
LIQUIDITY_USD_MIN = 1000.0
LATENESS_SLACK_SECONDS = 120
ICP_ID = "ICP-EARLY-PUMPFUN-V1"
AUTHORITY_PHRASE = (
    "OK HFIC_NEXT_FORWARD_EVIDENCE_OPTION_V2: one bounded Jupiter Free-key "
    "read-only PIT capture using a local process-environment key only; Tokens "
    "V2 /recent plus one bulk /tokens/v2/search R0 snapshot plus quote-only "
    "/swap/v2/order; x-api-key header only; no .env read, no key in URL/log/"
    "receipt/Git, no taker, /build, /execute, wallet, signer, transaction, "
    "paid plan, second provider, retry or fallback; cash cap $0; call cap 60; "
    "global provider pace >=3s; ICP-EARLY-PUMPFUN-V1 fresh mints only excluding "
    "all prior consumed mints including the 2026-08-24 valuation window; X = "
    "R0_TAKER_VOLUME_MIX from stats5m buyVolume/(buyVolume+sellVolume) at one "
    "prospective search snapshot (dimensionless; UNKNOWN never zero; no USD "
    "volume claim; no R1 search); stop before quotes if valid-mix eligible < "
    "10; quote-only BUY at R0 and quote-only SELL at H900; Y previously "
    "unconsumed; no ln(R1/R0), no closed-family threshold, window, quartile or "
    "LOO reopen; one window only; Factory runner unchanged; Discovery, A7, "
    "Strategy, Bot, Shadow, alpha, NetReturn, micro-live and /hypothesis-forge "
    "forbidden."
)

FROZEN_FENCES = {
    "discovery_panel": "DISCOVERY_ONLY_SECOND_LOOK_NOT_THIS_WINDOW",
    "this_window": "PRIMARY_FORWARD_FALSIFIER",
    "confirmatory_second_window": "FORBIDDEN",
    "consumed_y_reuse": "FORBIDDEN",
    "closed_family_reopen": "FORBIDDEN",
}


class ForwardCaptureError(ValueError):
    def __init__(self, code: str, *, provider_requests: int = 0) -> None:
        super().__init__(code)
        self.provider_requests = provider_requests


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ForwardCaptureError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return float(value) == float(value) and float(value) not in {
            float("inf"),
            float("-inf"),
        }
    except (OverflowError, ValueError):
        return False


def capture_dir(data_root: Path) -> Path:
    return Path(data_root) / CAPTURE_ROOT_NAME


def complete_marker(data_root: Path) -> Path:
    return capture_dir(data_root) / "COMPLETE.json"


def window_lock(data_root: Path) -> Path:
    return capture_dir(data_root) / "window.lock"


def frozen_dir(data_root: Path) -> Path:
    return capture_dir(data_root) / "frozen"


def run_dir(data_root: Path, run_id: str) -> Path:
    return capture_dir(data_root) / "runs" / run_id


def load_policy(repo_root: Path) -> dict[str, Any]:
    path = Path(repo_root) / POLICY_RELATIVE
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "CAPTURE_POLICY_INVALID")
    return loaded


def validate_policy(policy: Mapping[str, Any], *, repo_root: Path) -> None:
    _require(policy.get("schema") == POLICY_SCHEMA, "POLICY_SCHEMA_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    _require(policy.get("capability_id") == CAPABILITY_ID, "CAPABILITY_ID_DRIFT")
    authority = _mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    _require(authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_DRIFT")
    _require(authority.get("credential_name") == "JUPITER_API_KEY", "CREDENTIAL_NAME_DRIFT")
    _require(authority.get("dotenv_reads") is False, "DOTENV_READ")
    _require(authority.get("execute") is False, "EXECUTE_NOT_FORBIDDEN")
    _require(authority.get("build") is False, "BUILD_NOT_FORBIDDEN")
    _require(authority.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(int(authority.get("call_cap") or 0) == CALL_CAP, "CALL_CAP_DRIFT")
    _require(authority.get("cash_cap_usd_cents") == 0, "CASH_CAP_DRIFT")
    controls = _mapping(policy.get("execution_controls"), "CONTROLS_INVALID")
    _require(controls.get("retries") == 0, "RETRIES_NOT_ZERO")
    _require(controls.get("fallback") is False, "FALLBACK_NOT_FORBIDDEN")
    _require(int(controls.get("min_interval_seconds") or 0) >= 3, "PACE_DRIFT")
    _require(controls.get("second_provider") is False, "SECOND_PROVIDER")
    _require(controls.get("paid_plan") is False, "PAID_PLAN")
    windows = _mapping(policy.get("windows"), "WINDOWS_INVALID")
    _require(int(windows.get("max_windows") or 0) == 1, "MAX_WINDOWS_DRIFT")
    _require(windows.get("second_window") == "forbidden", "SECOND_WINDOW_NOT_FORBIDDEN")
    quote = _mapping(policy.get("quote"), "QUOTE_INVALID")
    _require(quote.get("r1_search") == "forbidden", "R1_SEARCH_NOT_FORBIDDEN")
    _require(quote.get("horizon_kind") == "ABSOLUTE_CREATE_AT_PLUS_H900", "H900_KIND_DRIFT")
    _require(int(quote.get("horizon_seconds") or 0) == H900, "H900_DRIFT")
    _require(quote.get("buy_after") == "R0_SEARCH", "BUY_AFTER_DRIFT")
    _require(str(quote.get("slippage_bps")) == str(SLIPPAGE_BPS), "SLIPPAGE_DRIFT")
    _require(str(quote.get("notional_atomic")) == str(NOTIONAL_ATOMIC), "NOTIONAL_DRIFT")
    _require(int(quote.get("lateness_slack_seconds") or 0) == LATENESS_SLACK_SECONDS, "SLACK_DRIFT")
    population = _mapping(policy.get("population"), "POPULATION_INVALID")
    _require(population.get("icp_id") == ICP_ID, "ICP_DRIFT")
    band = _mapping(population.get("r0_age_band_seconds"), "AGE_BAND_INVALID")
    _require(int(band.get("min") or 0) == R0_AGE_MIN, "R0_AGE_MIN_DRIFT")
    _require(int(band.get("max_exclusive") or 0) == R0_AGE_MAX_EXCLUSIVE, "R0_AGE_MAX_DRIFT")
    _require(str(policy.get("factory_runner")) == FACTORY_RUNNER, "FACTORY_RUNNER_PATH_DRIFT")
    runner = Path(repo_root) / FACTORY_RUNNER
    _require(runner.is_file(), "FACTORY_RUNNER_MISSING")
    observed = hashlib.sha256(runner.read_bytes()).hexdigest()
    _require(observed == FACTORY_RUNNER_SHA256, "FACTORY_RUNNER_CHANGED")
    _require(str(policy.get("factory_runner_sha256")) == FACTORY_RUNNER_SHA256, "FACTORY_RUNNER_PIN_DRIFT")
    _require(str(policy.get("registry")) == "configs/provider_route_capability_registry_v10.yaml", "REGISTRY_BIND_DRIFT")
    registry_path = Path(repo_root) / "configs/provider_route_capability_registry_v10.yaml"
    predecessor_path = Path(repo_root) / V9_PATH
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
    search = _mapping(routes.get("search"), "SEARCH_ROUTE_INVALID")
    _require(search.get("route_id") == SEARCH_ROUTE_ID, "SEARCH_ROUTE_DRIFT")
    _require(search.get("endpoint") == SEARCH_ENDPOINT, "SEARCH_ENDPOINT_DRIFT")


def consumed_mints_from_git(repo_root: Path, policy: Mapping[str, Any]) -> set[str]:
    mints: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, Mapping):
            mint = node.get("mint") or node.get("id")
            if isinstance(mint, str) and mint.endswith("pump"):
                mints.add(mint)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for relative in policy.get("consumed_mint_receipts") or []:
        path = Path(repo_root) / str(relative)
        _require(path.is_file() and not path.is_symlink(), "CONSUMED_RECEIPT_MISSING")
        loaded = json.loads(path.read_text(encoding="utf-8"))
        walk(loaded)
    _require(bool(mints), "PRIOR_MINT_EXCLUSION_INPUT_REQUIRED")
    return mints


def select_eligible(
    rows: Sequence[Mapping[str, Any]],
    *,
    excluded_mints: set[str],
    snapshot_at: datetime,
    liquidity_min: float = LIQUIDITY_USD_MIN,
) -> list[dict[str, Any]]:
    _require(snapshot_at.tzinfo is not None, "SNAPSHOT_CLOCK_INVALID")
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
        if not _number(raw.get("liquidity")) or float(raw["liquidity"]) < liquidity_min:
            continue
        if not _number(raw.get("mcap")):
            continue
        stats = raw.get("stats5m")
        if not isinstance(stats, Mapping):
            continue
        pool = raw.get("firstPool")
        if not isinstance(pool, Mapping):
            continue
        try:
            created_at = _parse_datetime(pool.get("createdAt"), "FIRST_POOL_TIMESTAMP_INVALID")
        except OrganicPressureError:
            continue
        age = (snapshot_at.astimezone(UTC) - created_at).total_seconds()
        if age < float(R0_AGE_MIN) or age >= float(R0_AGE_MAX_EXCLUSIVE):
            continue
        seen.add(mint)
        selected.append(dict(raw))
        if len(selected) >= 100:
            break
    return selected


def planned_calls(eligible_count: int) -> int:
    quoted = min(max(eligible_count, 0), QUOTE_PAIR_CAP)
    if eligible_count < MIN_ELIGIBLE_BEFORE_QUOTES:
        return 2
    return 2 + 2 * quoted


def _write_create_only(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        existing = path.read_bytes()
        if existing != payload:
            raise ForwardCaptureError("IMMUTABLE_TARGET_CONFLICT") from exc


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def build_experiment_spec(*, policy_sha256: str, repo_relative_policy: str) -> dict[str, Any]:
    return {
        "schema": "smial.experiment-spec",
        "schema_version": "1.0",
        "experiment_id": EXPERIMENT_ID,
        "hypothesis_version": CONSUMER_HYPOTHESIS_ID,
        "question": "Does R0 taker volume mix predict unconsumed quote-only H900 PathRisk on fresh ICP-EARLY-PUMPFUN-V1 mints?",
        "estimand": "sign-only Kendall tau_b of R0_TAKER_VOLUME_MIX versus quote-only round-trip Y at absolute create_at+H900",
        "population": "ICP-EARLY-PUMPFUN-V1 pump.fun fresh mints age [300,600) excluding consumed mints",
        "data_requirements": [
            {
                "requirement_id": "CAPTURE_POLICY",
                "kind": "CAPTURE_POLICY",
                "path": repo_relative_policy,
                "sha256": policy_sha256,
            },
            {
                "requirement_id": "RUNTIME_RECEIPT",
                "kind": "PROVIDER_BOUNDED_CAPTURE",
                "path": "local/forward_h900_quote_capture/COMPLETE.json",
            },
        ],
        "capabilities": [CAPABILITY_ID],
        "falsifier": "tau_b <= 0 or coverage floors fail closes the mix family; no closed-family score reopen",
        "method": "sign_only_kendall_tau_b_offline",
        "parameters": {
            "primary_x": "R0_TAKER_VOLUME_MIX",
            "primary_y": "QUOTE_ONLY_ROUND_TRIP_AT_ABSOLUTE_H900",
            "r1_search": "forbidden",
            "tau_b_floor": "forbidden",
            "quartile": False,
            "leave_one_out": False,
            "required_owner_phrase": AUTHORITY_PHRASE,
        },
        "evidence_budget": {"provider_api_rpc_wss_calls": 60},
        "holdout_policy": "No untouched holdout is opened; this window is the first unconsumed Y pairing",
        "terminal_outcomes": [
            "STOP_BEFORE_QUOTES_ELIGIBLE_BELOW_FLOOR",
            "INVALID_EVIDENCE_REPLAN",
            "CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY",
            "EARN_ONE_CONFIRMATORY_FRESH_OOS",
            "SECOND_WINDOW_FORBIDDEN",
        ],
    }


def freeze_contract(
    *,
    repo_root: Path,
    data_root: Path,
    git_sha: str,
) -> dict[str, Any]:
    policy = load_policy(repo_root)
    validate_policy(policy, repo_root=repo_root)
    policy_bytes = (Path(repo_root) / POLICY_RELATIVE).read_bytes()
    policy_sha256 = hashlib.sha256(policy_bytes).hexdigest()
    spec = build_experiment_spec(
        policy_sha256=policy_sha256,
        repo_relative_policy=POLICY_RELATIVE,
    )
    hypothesis = {
        "hypothesis_version_id": CONSUMER_HYPOTHESIS_ID,
        "claim": "R0 taker mix predicts later quote-only PathRisk on a fresh pre-registered forward sample",
        "primary_x_family": "R0_TAKER_VOLUME_MIX",
        "primary_y": "quote-only round trip at absolute create_at+H900",
        "population": ICP_ID,
        "fences": dict(FROZEN_FENCES),
    }
    git_sha = str(git_sha).lower()
    _require(len(git_sha) == 40 and all(char in "0123456789abcdef" for char in git_sha), "GIT_SHA_INVALID")
    packet = {
        "hypothesis": hypothesis,
        "experiment_spec": spec,
        "primary_x": "R0_TAKER_VOLUME_MIX",
        "primary_y": "QUOTE_ONLY_ROUND_TRIP_AT_ABSOLUTE_CREATE_AT_PLUS_H900",
        "population": {
            "icp_id": ICP_ID,
            "launchpad": "pump.fun",
            "r0_age_band_seconds": {"min": R0_AGE_MIN, "max_exclusive": R0_AGE_MAX_EXCLUSIVE},
            "liquidity_usd_min": LIQUIDITY_USD_MIN,
        },
        "exclusions": {
            "consumed_mint_receipts": list(policy.get("consumed_mint_receipts") or []),
            "prior_valuation_window": "2026-08-24",
        },
        "floors": {
            "min_eligible_before_quotes": MIN_ELIGIBLE_BEFORE_QUOTES,
            "min_rankable_h900_offline": 8,
            "quote_pair_cap": QUOTE_PAIR_CAP,
        },
        "missingness": {
            "unknown_never_zero": True,
            "stats5m_absent": "not_eligible_for_quotes",
            "mix_unknown": "offline_drop_not_zero",
            "meu_or_unobserved_y": "keep_row_y_null",
        },
        "stop_rules": {
            "eligible_lt_10": "STOP_BEFORE_QUOTES_ELIGIBLE_BELOW_FLOOR",
            "call_cap": CALL_CAP,
            "retries": 0,
            "fallback": False,
            "second_window": "FORBIDDEN",
            "r1_search": "FORBIDDEN",
            "confirmatory_second_window": "FORBIDDEN",
        },
        "fences": dict(FROZEN_FENCES),
        "policy_sha256": policy_sha256,
        "capability_id": CAPABILITY_ID,
        "atom_id": ATOM_ID,
        "live_git_head": git_sha,
    }
    encoded = _canonical_json(packet)
    digest = hashlib.sha256(encoded).hexdigest()
    target = frozen_dir(data_root) / f"{digest}.json"
    _write_create_only(target, encoded)
    alias = frozen_dir(data_root) / "CURRENT.json"
    if alias.exists():
        if alias.read_bytes() != encoded:
            raise ForwardCaptureError("FROZEN_CONTRACT_DRIFT")
        return {
            "frozen_contract_sha256": digest,
            "policy_sha256": policy_sha256,
            "hypothesis_version": CONSUMER_HYPOTHESIS_ID,
            "experiment_id": EXPERIMENT_ID,
            "fences": dict(FROZEN_FENCES),
            "provider_requests": 0,
            "credential_reads": 0,
        }
    alias.write_bytes(encoded)
    from solana_alpha_lab.factory.research_store import (
        RecordKind,
        ResearchEvent,
        ResearchStore,
        ResearchStoreError,
    )

    now = datetime.now(UTC)
    store = ResearchStore(Path(data_root))
    payload = json.dumps(
        {
            "research_artifact_id": f"FWD-ART-{digest[:16].upper()}",
            "artifact_kind": "FORWARD_CAPTURE_FROZEN_CONTRACT",
            "payload_sha256": digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    event = ResearchEvent(
        record_id=f"FWD-ART-{digest[:16].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=CONSUMER_HYPOTHESIS_ID,
        hypothesis_version_id=CONSUMER_HYPOTHESIS_ID,
        run_id=None,
        transaction_id=f"RESEARCH-TXN-FWD-{digest[:16].upper()}",
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload,
        payload_sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=CAPABILITY_ID,
        producer_git_sha=git_sha.lower(),
        created_at=now,
    )
    hyp_payload = json.dumps(hypothesis, sort_keys=True, separators=(",", ":"))
    hyp_event = ResearchEvent(
        record_id=f"FWD-HYP-{digest[:16].upper()}",
        record_kind=RecordKind.HYPOTHESIS_VERSION,
        entity_id=CONSUMER_HYPOTHESIS_ID,
        hypothesis_version_id=CONSUMER_HYPOTHESIS_ID,
        run_id=None,
        transaction_id=f"RESEARCH-TXN-FWDHYP-{digest[:16].upper()}",
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=hyp_payload,
        payload_sha256=hashlib.sha256(hyp_payload.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=CAPABILITY_ID,
        producer_git_sha=git_sha.lower(),
        created_at=now,
    )
    try:
        store.append([event], transaction_id=str(event.transaction_id))
        store.append([hyp_event], transaction_id=str(hyp_event.transaction_id))
        store.rebuild_projection()
    except ResearchStoreError as exc:
        if str(exc) not in {
            "TRANSACTION_CONFLICT",
            "DUPLICATE_RECORD_ID",
            "WRITER_BUSY",
        }:
            raise ForwardCaptureError(str(exc)) from exc
    return {
        "frozen_contract_sha256": digest,
        "policy_sha256": policy_sha256,
        "hypothesis_version": CONSUMER_HYPOTHESIS_ID,
        "experiment_id": EXPERIMENT_ID,
        "fences": dict(FROZEN_FENCES),
        "provider_requests": 0,
        "credential_reads": 0,
    }


def load_frozen_contract(data_root: Path) -> dict[str, Any]:
    alias = frozen_dir(data_root) / "CURRENT.json"
    _require(alias.is_file(), "FROZEN_CONTRACT_MISSING")
    loaded = json.loads(alias.read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "FROZEN_CONTRACT_INVALID")
    _require(loaded.get("hypothesis", {}).get("hypothesis_version_id") == CONSUMER_HYPOTHESIS_ID, "HYPOTHESIS_MISMATCH")
    _require(loaded.get("primary_x") == "R0_TAKER_VOLUME_MIX", "X_MISMATCH")
    _require(loaded.get("fences", {}).get("confirmatory_second_window") == "FORBIDDEN", "FENCE_MISMATCH")
    _require(loaded.get("stop_rules", {}).get("second_window") == "FORBIDDEN", "STOP_RULE_MISMATCH")
    _require(loaded.get("experiment_spec", {}).get("parameters", {}).get("r1_search") == "forbidden", "R1_FENCE_MISMATCH")
    return loaded


def credential_free_capture_preflight(
    repo_root: Path,
    *,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
) -> dict[str, Any]:
    policy = load_policy(repo_root)
    validate_policy(policy, repo_root=repo_root)
    started = _format_utc(datetime.now(UTC))
    try:
        preflight = dict(
            preflight_fn(
                {"provider_route": {"endpoint": RECENT_ENDPOINT}},
                observed_at=started,
            )
        )
    except QuoteShotError as exc:
        raise ForwardCaptureError(str(exc)) from exc
    _require(int(preflight.get("credential_reads") or 0) == 0, "CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT")
    planned = planned_calls(QUOTE_PAIR_CAP)
    _require(planned <= CALL_CAP, "PLANNED_CALLS_EXCEED_CAP")
    return {
        "status": "PREFLIGHT_OK",
        "credential_reads": 0,
        "provider_requests": 0,
        "planned_calls_max": planned,
        "min_interval_seconds": 3,
        "retries": 0,
        "fallback": False,
        "factory_runner_sha256": FACTORY_RUNNER_SHA256,
        "r1_search": "forbidden",
        "second_window": "forbidden",
    }


def _journal_path(folder: Path) -> Path:
    return folder / "journal.json"


def _load_journal(folder: Path) -> dict[str, Any]:
    path = _journal_path(folder)
    if not path.is_file():
        return {"observations": {}}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ForwardCaptureError("JOURNAL_INVALID")
    return loaded


def _save_journal(folder: Path, journal: Mapping[str, Any]) -> None:
    path = _journal_path(folder)
    encoded = _canonical_json(journal)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)


def run_forward_capture(
    *,
    repo_root: Path,
    data_root: Path,
    authority_phrase: str,
    excluded_mints: set[str] | None = None,
    credential_loader: Callable[[], str] | None = None,
    opener: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] = time.sleep,
    monotonic_clock: Callable[[], float] = time.monotonic,
    environ: Mapping[str, str] | None = None,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
) -> dict[str, Any]:
    if complete_marker(data_root).is_file():
        loaded = json.loads(complete_marker(data_root).read_text(encoding="utf-8"))
        loaded["provider_requests_new"] = 0
        loaded["resume"] = "IDEMPOTENT_COMPLETE"
        loaded["second_window"] = "FORBIDDEN"
        return loaded
    policy = load_policy(repo_root)
    validate_policy(policy, repo_root=repo_root)
    frozen = load_frozen_contract(data_root)
    policy_sha256 = hashlib.sha256((Path(repo_root) / POLICY_RELATIVE).read_bytes()).hexdigest()
    _require(frozen.get("policy_sha256") == policy_sha256, "FROZEN_POLICY_MISMATCH")
    _require(authority_phrase == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_INVALID")
    git_exclusions = consumed_mints_from_git(repo_root, policy)
    excluded = set(excluded_mints or set()) | git_exclusions
    _require(bool(excluded), "PRIOR_MINT_EXCLUSION_INPUT_REQUIRED")
    started_at = clock()
    try:
        preflight = dict(
            preflight_fn(
                {"provider_route": {"endpoint": RECENT_ENDPOINT}},
                observed_at=_format_utc(started_at),
            )
        )
    except QuoteShotError as exc:
        raise ForwardCaptureError(str(exc)) from exc
    except OrganicPressureError as exc:
        raise ForwardCaptureError(str(exc)) from exc
    _require(int(preflight.get("credential_reads") or 0) == 0, "CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT")
    loader = credential_loader or (lambda: load_process_credential(environ or {}))
    credential = loader()
    _require(isinstance(credential, str) and bool(credential.strip()), "JUPITER_API_KEY_MISSING_OR_EMPTY")
    credential_reads = 1
    limits = _mapping(policy.get("runtime_limits"), "LIMITS_INVALID")
    last_monotonic: float | None = None
    run_id = "run-" + hashlib.sha256(
        (_format_utc(started_at) + policy_sha256).encode("utf-8")
    ).hexdigest()[:16]
    folder = run_dir(data_root, run_id)
    folder.mkdir(parents=True, exist_ok=True)
    lock = window_lock(data_root)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock_payload = _canonical_json({"run_id": run_id, "atom_id": ATOM_ID})
    if lock.exists():
        existing_lock = json.loads(lock.read_text(encoding="utf-8"))
        run_id = str(existing_lock.get("run_id") or run_id)
        folder = run_dir(data_root, run_id)
        folder.mkdir(parents=True, exist_ok=True)
    else:
        _write_create_only(lock, lock_payload)
    journal = _load_journal(folder)
    observations: dict[str, Any] = dict(journal.get("observations") or {})
    provider_requests = sum(
        1
        for item in observations.values()
        if isinstance(item, Mapping) and item.get("body_sha256")
    )

    def persist_raw(observation_id: str, body: bytes, observed_at: str) -> None:
        raw_path = folder / "raw" / f"{observation_id.replace(':', '_')}.body"
        _write_create_only(raw_path, body)
        env_path = folder / "raw" / f"{observation_id.replace(':', '_')}.envelope.json"
        _write_create_only(
            env_path,
            _canonical_json(
                {
                    "observation_id": observation_id,
                    "observed_at": observed_at,
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "bytes": len(body),
                }
            ),
        )

    def call(url: str, observation_id: str) -> dict[str, Any]:
        nonlocal provider_requests, last_monotonic
        cached = observations.get(observation_id)
        if isinstance(cached, Mapping) and cached.get("body_sha256"):
            raw_path = folder / "raw" / f"{observation_id.replace(':', '_')}.body"
            body = raw_path.read_bytes()
            return {
                "http_status": int(cached.get("http_status") or 200),
                "body": body,
                "observed_at": cached.get("observed_at"),
                "url_has_api_key": False,
                "response_sha256": cached.get("body_sha256"),
                "resumed": True,
            }
        last_at = journal.get("last_call_at")
        if isinstance(last_at, str) and last_at:
            last_wall = _parse_datetime(last_at, "LAST_CALL_AT_INVALID")
            elapsed_wall = (clock() - last_wall).total_seconds()
            if elapsed_wall < 3:
                sleeper(3 - elapsed_wall)
        elif last_monotonic is not None:
            elapsed = monotonic_clock() - last_monotonic
            if elapsed < 3:
                sleeper(3 - elapsed)
        if provider_requests >= CALL_CAP:
            raise ForwardCaptureError("CALL_CAP_EXCEEDED", provider_requests=provider_requests)
        provider_requests += 1
        try:
            result = perform_credentialed_get(
                url,
                api_key=credential,
                limits=limits,
                opener=opener,
            )
        except QualificationError as exc:
            raise ForwardCaptureError(str(exc), provider_requests=provider_requests) from exc
        last_monotonic = monotonic_clock()
        if result.get("url_has_api_key") is True:
            raise ForwardCaptureError("API_KEY_IN_URL_LOG_RECEIPT_OR_GIT", provider_requests=provider_requests)
        result["observed_at"] = _format_utc(clock())
        body = result.get("body")
        if isinstance(body, bytes):
            if credential.encode("utf-8") in body:
                raise ForwardCaptureError("RAW_BODY_CONTAINS_CREDENTIAL", provider_requests=provider_requests)
            _assert_quote_body_has_no_transaction(body)
            persist_raw(observation_id, body, str(result["observed_at"]))
        observations[observation_id] = {
            "http_status": result.get("http_status"),
            "body_sha256": result.get("response_sha256"),
            "observed_at": result.get("observed_at"),
            "url": url.split("?", 1)[0],
        }
        journal["observations"] = observations
        journal["last_call_at"] = result["observed_at"]
        _save_journal(folder, journal)
        _raw_observation(
            observation_id=observation_id,
            result=result,
            credential=credential,
            raw_sink=None,
        )
        return result

    try:
        return _run_capture_body(
            call=call,
            clock=clock,
            sleeper=sleeper,
            excluded=excluded,
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests_ref=lambda: provider_requests,
            data_root=data_root,
            run_id=run_id,
        )
    except OrganicPressureError as exc:
        raise ForwardCaptureError(str(exc), provider_requests=provider_requests) from exc


def _run_capture_body(
    *,
    call: Callable[[str, str], dict[str, Any]],
    clock: Callable[[], datetime],
    sleeper: Callable[[float], None],
    excluded: set[str],
    preflight: Mapping[str, Any],
    credential_reads: int,
    provider_requests_ref: Callable[[], int],
    data_root: Path,
    run_id: str,
) -> dict[str, Any]:
    recent_result = call(RECENT_ENDPOINT, "CAPTURE:RECENT")
    recent_terminal, recent_error, recent_rows = _search_rows(recent_result)
    if recent_terminal != "TOKEN_LIST_OBSERVED" or recent_rows is None:
        return _receipt(
            terminal="INVALID_EVIDENCE_REPLAN",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests_ref(),
            extra={"recent_error": recent_error},
        )
    snapshot_at = _parse_datetime(recent_result["observed_at"], "RECENT_TIMESTAMP_INVALID")
    search_pool = [
        row
        for row in recent_rows
        if isinstance(row, Mapping)
        and isinstance(row.get("id"), str)
        and row.get("launchpad") == "pump.fun"
        and row.get("id") not in excluded
    ][:100]
    if not search_pool:
        return _receipt(
            terminal="INVALID_EVIDENCE_REPLAN",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests_ref(),
        )
    search_url = build_search_url([str(row["id"]) for row in search_pool])
    search_result = call(search_url, "CAPTURE:SEARCH_R0")
    search_terminal, search_error, search_rows = _search_rows(search_result)
    if search_terminal != "TOKEN_LIST_OBSERVED" or search_rows is None:
        return _receipt(
            terminal="INVALID_EVIDENCE_REPLAN",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests_ref(),
            extra={"search_error": search_error},
        )
    search_at = _parse_datetime(search_result["observed_at"], "SEARCH_TIMESTAMP_INVALID")
    eligible = select_eligible(search_rows, excluded_mints=excluded, snapshot_at=search_at)
    if len(eligible) < MIN_ELIGIBLE_BEFORE_QUOTES:
        receipt = _receipt(
            terminal="STOP_BEFORE_QUOTES_ELIGIBLE_BELOW_FLOOR",
            preflight=preflight,
            credential_reads=credential_reads,
            provider_requests=provider_requests_ref(),
            extra={
                "eligible_count": len(eligible),
                "search_mints": [str(row["id"]) for row in eligible],
                "quotes_attempted": 0,
                "window_complete": True,
            },
        )
        _write_create_only(complete_marker(data_root), _canonical_json(receipt))
        return receipt
    quoted = eligible[:QUOTE_PAIR_CAP]
    pending: list[dict[str, Any]] = []
    for item in quoted:
        mint = str(item["id"])
        buy_url = _order_url(
            input_mint=WRAPPED_SOL,
            output_mint=mint,
            amount=NOTIONAL_ATOMIC,
            slippage_bps=SLIPPAGE_BPS,
        )
        buy_result = call(buy_url, f"{mint}:BUY_R0")
        buy_body = buy_result.get("body") if isinstance(buy_result.get("body"), bytes) else b""
        classified_buy = classify_organic_quote(
            buy_body,
            http_status=buy_result.get("http_status") if isinstance(buy_result.get("http_status"), int) else None,
            expected_in_amount=NOTIONAL_ATOMIC,
            expected_input_mint=WRAPPED_SOL,
            expected_output_mint=mint,
        )
        quote = classified_buy.get("quote") if isinstance(classified_buy.get("quote"), Mapping) else {}
        buy_out = quote.get("out_amount") if classified_buy.get("terminal") == QUOTE_OBSERVED else None
        created_at = _parse_datetime(item["firstPool"]["createdAt"], "FIRST_POOL_TIMESTAMP_INVALID")
        due_at = created_at + timedelta(seconds=H900)
        pending.append(
            {
                "mint": mint,
                "search_row": item,
                "buy_terminal": classified_buy.get("terminal"),
                "buy_out_amount": buy_out,
                "due_at": due_at,
                "h900_due_at": _format_utc(due_at),
                "y": None,
                "h900_terminal": None,
            }
        )
    pending.sort(key=lambda row: row["due_at"])
    rows: list[dict[str, Any]] = []
    for row in pending:
        mint = str(row["mint"])
        due_at = row["due_at"]
        wait = (due_at - clock()).total_seconds()
        if wait > 0:
            sleeper(wait)
        now = clock()
        late_limit = due_at + timedelta(seconds=LATENESS_SLACK_SECONDS)
        if now > late_limit:
            row["h900_terminal"] = "H900_LATE_BEFORE_QUOTE"
            rows.append(row)
            continue
        buy_out = row.get("buy_out_amount")
        if row.get("buy_terminal") != QUOTE_OBSERVED or not isinstance(buy_out, str):
            row["h900_terminal"] = "BUY_NOT_OBSERVED"
            rows.append(row)
            continue
        sell_url = _order_url(
            input_mint=mint,
            output_mint=WRAPPED_SOL,
            amount=str(buy_out),
            slippage_bps=SLIPPAGE_BPS,
        )
        sell_result = call(sell_url, f"{mint}:SELL_H900")
        sell_body = sell_result.get("body") if isinstance(sell_result.get("body"), bytes) else b""
        classified_sell = classify_organic_quote(
            sell_body,
            http_status=sell_result.get("http_status") if isinstance(sell_result.get("http_status"), int) else None,
            expected_in_amount=str(buy_out),
            expected_input_mint=mint,
            expected_output_mint=WRAPPED_SOL,
        )
        row["h900_terminal"] = classified_sell.get("terminal")
        sell_quote = classified_sell.get("quote") if isinstance(classified_sell.get("quote"), Mapping) else {}
        if classified_sell.get("terminal") == QUOTE_OBSERVED:
            out_amount = sell_quote.get("out_amount")
            if isinstance(out_amount, str) and out_amount:
                try:
                    row["y"] = float(Decimal(out_amount) / Decimal(NOTIONAL_ATOMIC) - Decimal(1))
                except (InvalidOperation, ValueError):
                    row["y"] = None
        sell_at = _parse_datetime(sell_result["observed_at"], "H900_TIMESTAMP_INVALID")
        if sell_at < due_at:
            row["h900_terminal"] = "H900_EARLY"
            row["y"] = None
        elif sell_at > late_limit:
            row["h900_terminal"] = "H900_LATE"
            row["y"] = None
        rows.append(row)
    receipt = _receipt(
        terminal="CAPTURE_COMPLETE",
        preflight=preflight,
        credential_reads=credential_reads,
        provider_requests=provider_requests_ref(),
        extra={
            "eligible_count": len(eligible),
            "quoted_count": len(quoted),
            "rows": [
                {
                    "mint": row["mint"],
                    "buy_terminal": row["buy_terminal"],
                    "h900_terminal": row["h900_terminal"],
                    "y": row["y"],
                    "h900_due_at": row["h900_due_at"],
                    "search_row": row["search_row"],
                }
                for row in rows
            ],
            "run_id": run_id,
            "window_complete": True,
            "wallet_signer_transaction_actions": 0,
            "execute_calls": 0,
            "build_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
    )
    _write_create_only(complete_marker(data_root), _canonical_json(receipt))
    return receipt


def _receipt(
    *,
    terminal: str,
    preflight: Mapping[str, Any],
    credential_reads: int,
    provider_requests: int,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "capability_id": CAPABILITY_ID,
        "terminal_outcome": terminal,
        "preflight": dict(preflight),
        "credential_reads": credential_reads,
        "provider_requests": provider_requests,
        "retries": 0,
        "fallbacks": 0,
        "execute_calls": 0,
        "build_calls": 0,
        "wallet_signer_transaction_actions": 0,
        "r1_search_calls": 0,
        "window_complete": False,
        "non_claims": [
            "NO_EXECUTE",
            "NO_TAKER_OR_SIGNER",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_HYPOTHESIS_SPECIFIC_PROVIDER_RUNNER",
            "NO_R1_SEARCH",
            "NO_CLOSED_FAMILY_REOPEN",
        ],
    }
    if extra:
        body.update(dict(extra))
    return body
