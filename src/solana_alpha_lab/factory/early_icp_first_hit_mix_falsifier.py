"""WRAP: first-hit mix falsifier over V2 capture primitives. Scorer unchanged."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.early_market_panel_field_semantics import classify_r0_mix
from solana_alpha_lab.factory.forward_h900_quote_capture import (
    CALL_CAP,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    H900,
    LATENESS_SLACK_SECONDS,
    LIQUIDITY_USD_MIN,
    MIN_ELIGIBLE_BEFORE_QUOTES,
    NOTIONAL_ATOMIC,
    QUOTE_PAIR_CAP,
    R0_AGE_MAX_EXCLUSIVE,
    R0_AGE_MIN,
    RECENT_ENDPOINT,
    SLIPPAGE_BPS,
    WRAPPED_SOL,
    complete_marker,
    consumed_mints_from_git,
    select_eligible,
)
from solana_alpha_lab.factory.forward_mix_offline import score_frozen_mix_dataset
from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (
    QUOTE_OBSERVED,
    _assert_quote_body_has_no_transaction,
    _format_utc,
    _order_url,
    _parse_datetime,
    _search_rows,
    build_search_url,
    classify_organic_quote,
)
from solana_alpha_lab.pmf_quote_slice_one_shot import QuoteShotError, credential_free_preflight
from solana_alpha_lab.quote_native_evidence_channel_qualification import (
    QualificationError,
    load_process_credential,
    perform_credentialed_get,
)
from solana_alpha_lab.storage.manifests import canonical_manifest_bytes

ATOM_ID = "EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1"
CAPABILITY_ID = "CAP-JUPITER-FREE-KEY-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001"
POLICY_RELATIVE = "configs/early_icp_first_hit_mix_falsifier_v1.yaml"
POLICY_SCHEMA = "smial.early-icp-first-hit-mix-falsifier"
RECEIPT_SCHEMA = "smial.early-icp-first-hit-mix-falsifier.runtime-receipt"
MAX_DENSITY_CHECKS = 20
DENSITY_CHECK_PERIOD_SECONDS = 60
QUOTE_CALL_RESERVE = 20
PACE_SECONDS = 3
SLEEP_TERMINAL = "SLEEP_ELIGIBLE_BELOW_10"
IN_FLIGHT_TERMINAL = "IN_FLIGHT_CALL_INDETERMINATE"
NOT_QUOTED = "NOT_QUOTED_CAPACITY"
DATASET_MANIFEST_ID = "DATASET-MANIFEST-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001"
DATASET_ID = "DATASET-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001"
PARTITION_ID = "PARTITION-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001"
PARTITION_MANIFEST_ID = "PARTITION-MANIFEST-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001"
SCHEMA_ID = "SCHEMA-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001"
COMMIT_POINT_KIND = "EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_PUBLICATION_V1"
AUTHORITY_PHRASE = (
    "OK EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1: one bounded Jupiter Free-key "
    "foreground falsifier using a local process-environment key only; this "
    "exact pre-registered falsifier is authorized; any other experiment, "
    "promotion, Shadow, TWO_RUNG and /hypothesis-forge are forbidden; up to "
    "20 quote-free density checks of Tokens V2 /recent plus one bulk "
    "/tokens/v2/search each, period 60s, pace >=3s; the first search with "
    "select_eligible >=10 is the sole R0 snapshot, its search bytes are "
    "hash-bound, and a second /search is forbidden; quote-only /swap/v2/order "
    "BUY at that R0 then quote-only SELL at absolute create_at+H900; after "
    "internal CAPTURE_COMPLETE, publish one immutable dataset bundle with "
    "commit-marker last and run existing unchanged score_frozen_mix_dataset; "
    "persist exactly one scientific terminal INVALID_EVIDENCE_REPLAN, "
    "CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY or EARN_ONE_CONFIRMATORY_FRESH_OOS "
    "and mark that Y consumed; x-api-key header only; no .env read, no key in "
    "URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, "
    "transaction, paid plan, second provider, retry, fallback or mid-run "
    "owner intervention; cash cap $0; call cap 60 covering checks and quotes "
    "without raising the cap; quote_call_reserve 20; quoted = min(eligible, "
    "remaining/2, 29) and never below 10; Y-blind V2 search order; unquoted "
    "eligible rows kept with typed Y-null; floors mix_eligible >=10, "
    "decision-time eligible >=10, rankable H900 >=8; typed missingness, no "
    "imputation, no universe deletion, UNKNOWN never zero; ICP-EARLY-PUMPFUN-V1 "
    "exclusions include the 2026-08-24 valuation window and the completed V2 "
    "STOP_BEFORE_QUOTES window; after 20 misses SLEEP_ELIGIBLE_BELOW_10 with "
    "no dataset, no score, no ResearchStore append and evidence_epoch "
    "unchanged; one Y-bearing window only on a new atom root; do not write or "
    "reopen V2 COMPLETE; X = R0_TAKER_VOLUME_MIX from stats5m buyVolume/"
    "(buyVolume+sellVolume) at that R0 only (dimensionless; no USD volume "
    "claim; no R1 search); no ln(R1/R0), no closed-family threshold, window, "
    "quartile, LOO or tau_b_floor reopen; Factory runner unchanged; Discovery, "
    "A7, Strategy, Bot, Shadow, alpha, NetReturn, micro-live, promotion and "
    "confirmatory second window forbidden."
)

MANIFEST_RELATIVE = f"datasets/manifests/{DATASET_MANIFEST_ID}.json"
LABELS_RELATIVE = f"datasets/manifests/{DATASET_MANIFEST_ID}.labels.json"
PARTITION_RELATIVE = f"datasets/manifests/partitions/{PARTITION_MANIFEST_ID}.json"
LOGICAL_LOCATION = f"datasets/partitions/{PARTITION_ID}.parquet"
PUBLISHED_RELATIVE = f"datasets/manifests/{DATASET_MANIFEST_ID}.published"
DECISION_RELATIVE = f"datasets/manifests/{DATASET_MANIFEST_ID}.decision.json"
CANONICAL_TARGET_RELATIVES = (
    LOGICAL_LOCATION,
    PARTITION_RELATIVE,
    LABELS_RELATIVE,
    DECISION_RELATIVE,
    MANIFEST_RELATIVE,
    PUBLISHED_RELATIVE,
)


class FirstHitError(ValueError):
    def __init__(self, code: str, *, provider_requests: int = 0) -> None:
        super().__init__(code)
        self.provider_requests = provider_requests


def _require(condition: bool, code: str, *, provider_requests: int = 0) -> None:
    if not condition:
        raise FirstHitError(code, provider_requests=provider_requests)


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def v2_complete_path(data_root: Path) -> Path:
    return complete_marker(Path(data_root))


def published_marker_path(data_root: Path) -> Path:
    return Path(data_root) / PUBLISHED_RELATIVE


def load_policy(repo_root: Path) -> dict[str, Any]:
    path = Path(repo_root) / POLICY_RELATIVE
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "CAPTURE_POLICY_INVALID")
    return loaded


def validate_policy(policy: Mapping[str, Any], *, repo_root: Path) -> None:
    _require(policy.get("schema") == POLICY_SCHEMA, "POLICY_SCHEMA_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    _require(policy.get("capability_id") == CAPABILITY_ID, "CAPABILITY_ID_DRIFT")
    authority = policy.get("external_authority")
    _require(isinstance(authority, Mapping), "AUTHORITY_INVALID")
    _require(authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_DRIFT")
    _require(int(authority.get("call_cap") or 0) == CALL_CAP, "CALL_CAP_DRIFT")
    _require(authority.get("execute") is False, "EXECUTE_NOT_FORBIDDEN")
    _require(authority.get("build") is False, "BUILD_NOT_FORBIDDEN")
    cadence = policy.get("cadence")
    _require(isinstance(cadence, Mapping), "CADENCE_INVALID")
    _require(int(cadence.get("max_density_checks") or 0) == MAX_DENSITY_CHECKS, "CHECK_CAP_DRIFT")
    _require(
        int(cadence.get("density_check_period_seconds") or 0) == DENSITY_CHECK_PERIOD_SECONDS,
        "PERIOD_DRIFT",
    )
    _require(int(cadence.get("quote_call_reserve") or 0) == QUOTE_CALL_RESERVE, "RESERVE_DRIFT")
    _require(int(cadence.get("provider_pace_seconds") or 0) == PACE_SECONDS, "PACE_DRIFT")
    controls = policy.get("execution_controls")
    _require(isinstance(controls, Mapping), "CONTROLS_INVALID")
    _require(controls.get("retries") == 0, "RETRIES_NOT_ZERO")
    _require(controls.get("fallback") is False, "FALLBACK_NOT_FORBIDDEN")
    _require(controls.get("background_scheduler") is False, "SCHEDULER_NOT_FORBIDDEN")
    _require(str(policy.get("factory_runner")) == FACTORY_RUNNER, "FACTORY_RUNNER_PATH_DRIFT")
    runner = Path(repo_root) / FACTORY_RUNNER
    _require(runner.is_file(), "FACTORY_RUNNER_MISSING")
    observed = _sha256_bytes(runner.read_bytes())
    _require(observed == FACTORY_RUNNER_SHA256, "FACTORY_RUNNER_CHANGED")
    _require(str(policy.get("factory_runner_sha256")) == FACTORY_RUNNER_SHA256, "FACTORY_RUNNER_PIN_DRIFT")
    decision = policy.get("decision_rule")
    _require(isinstance(decision, Mapping), "DECISION_INVALID")
    _require(decision.get("scorer") == "score_frozen_mix_dataset", "SCORER_DRIFT")
    _require(decision.get("scorer_mutation") == "forbidden", "SCORER_MUTATION_NOT_FORBIDDEN")


def quote_capacity(provider_requests: int) -> int:
    remaining = CALL_CAP - int(provider_requests)
    return min(QUOTE_PAIR_CAP, remaining // 2)


def _schema_sha256() -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "columns": [
                    {"name": "mint", "type": "string"},
                    {"name": "quoted", "type": "bool"},
                    {"name": "r0_taker_volume_mix", "type": "float64"},
                    {"name": "missingness_code", "type": "string"},
                    {"name": "buy_terminal", "type": "string"},
                    {"name": "h900_terminal", "type": "string"},
                    {"name": "y", "type": "float64"},
                ]
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _journal_path(staging_root: Path) -> Path:
    return Path(staging_root) / "journal.json"


def _load_journal(staging_root: Path) -> dict[str, Any]:
    path = _journal_path(staging_root)
    if not path.is_file():
        return {"observations": {}, "last_call_at": None, "hit_check_index": None}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "JOURNAL_INVALID")
    return loaded


def _save_journal(staging_root: Path, journal: Mapping[str, Any]) -> None:
    path = _journal_path(staging_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json(journal))


def credential_free_first_hit_preflight(
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
        raise FirstHitError(str(exc)) from exc
    _require(int(preflight.get("credential_reads") or 0) == 0, "CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT")
    return {
        "status": "PREFLIGHT_OK",
        "credential_reads": 0,
        "provider_requests": 0,
        "max_density_checks": MAX_DENSITY_CHECKS,
        "density_check_period_seconds": DENSITY_CHECK_PERIOD_SECONDS,
        "quote_call_reserve": QUOTE_CALL_RESERVE,
        "call_cap": CALL_CAP,
        "retries": 0,
        "fallback": False,
        "second_search_after_r0": "forbidden",
        "factory_runner_sha256": FACTORY_RUNNER_SHA256,
    }


def _assert_v2_complete_unchanged(data_root: Path, before: bytes | None) -> None:
    path = v2_complete_path(data_root)
    if before is None:
        _require(not path.exists(), "V2_COMPLETE_CREATED")
        return
    _require(path.is_file(), "V2_COMPLETE_MISSING")
    _require(path.read_bytes() == before, "V2_COMPLETE_MUTATED")


def _load_published_bundle(data_root: Path) -> dict[str, Any] | None:
    marker = published_marker_path(data_root)
    if not marker.is_file():
        return None
    decision_path = Path(data_root) / DECISION_RELATIVE
    if not decision_path.is_file():
        return None
    loaded = json.loads(decision_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    return loaded


def _row_complete_for_score(row: Mapping[str, Any]) -> bool:
    if not row.get("quoted"):
        return True
    return isinstance(row.get("h900_terminal"), str) and bool(row.get("h900_terminal"))


def _parquet_and_manifests(
    *,
    rows: Sequence[Mapping[str, Any]],
    score: Mapping[str, Any],
    r0_search_sha256: str,
    available_at: datetime,
    generation_run_id: str,
    provider_requests: int,
) -> dict[str, bytes]:
    mints: list[str] = []
    quoted: list[bool] = []
    mixes: list[float | None] = []
    missing: list[str | None] = []
    buy_terms: list[str | None] = []
    h900_terms: list[str | None] = []
    ys: list[float | None] = []
    for row in rows:
        mint = str(row["mint"])
        search_row = row.get("search_row")
        mix_value, mix_code = (
            classify_r0_mix(search_row) if isinstance(search_row, Mapping) else (None, "SEARCH_ROW_ABSENT")
        )
        mints.append(mint)
        quoted.append(bool(row.get("quoted")))
        mixes.append(float(mix_value) if mix_value is not None else None)
        missing.append(str(mix_code) if mix_code else None)
        buy_terms.append(str(row["buy_terminal"]) if row.get("buy_terminal") else None)
        h900_terms.append(str(row["h900_terminal"]) if row.get("h900_terminal") else None)
        y_value = row.get("y")
        ys.append(float(y_value) if isinstance(y_value, (int, float)) and not isinstance(y_value, bool) else None)
    table = pa.table(
        {
            "mint": pa.array(mints, type=pa.string()),
            "quoted": pa.array(quoted, type=pa.bool_()),
            "r0_taker_volume_mix": pa.array(mixes, type=pa.float64()),
            "missingness_code": pa.array(missing, type=pa.string()),
            "buy_terminal": pa.array(buy_terms, type=pa.string()),
            "h900_terminal": pa.array(h900_terms, type=pa.string()),
            "y": pa.array(ys, type=pa.float64()),
        }
    )
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink)
    parquet_bytes = sink.getvalue().to_pybytes()
    file_sha256 = _sha256_bytes(parquet_bytes)
    fingerprint = canonical_sha256(
        {
            "dataset_manifest_id": DATASET_MANIFEST_ID,
            "r0_search_sha256": r0_search_sha256,
            "parquet_sha256": file_sha256,
            "scientific_terminal": score.get("terminal"),
        }
    )
    labels = {
        "evidence_role": "PRIMARY_FORWARD_FALSIFIER",
        "outcome_previously_consumed": True,
        "confirmatory_reuse_forbidden": True,
        "consumer_visible_requires_commit_marker": True,
        "scientific_terminal": score.get("terminal"),
        "r0_search_sha256": r0_search_sha256,
        "mix_eligible": score.get("mix_eligible"),
        "rankable_h900": score.get("rankable_h900"),
        "provider_calls_actual": provider_requests,
        "row_count": table.num_rows,
        "dataset_fingerprint": fingerprint,
    }
    partition = PartitionManifest(
        partition_manifest_id=PARTITION_MANIFEST_ID,
        dataset_manifest_id=DATASET_MANIFEST_ID,
        partition_id=PARTITION_ID,
        logical_location=LOGICAL_LOCATION,
        file_sha256=file_sha256,
        content_sha256=file_sha256,
        row_count=table.num_rows,
        min_event_time=available_at,
        max_event_time=available_at,
        min_available_to_strategy_at=available_at,
        max_available_to_strategy_at=available_at,
        first_reliable_available_at=available_at,
        created_at=available_at,
    )
    dataset = DatasetManifest(
        dataset_manifest_id=DATASET_MANIFEST_ID,
        dataset_id=DATASET_ID,
        dataset_version="1.0",
        schema_id=SCHEMA_ID,
        schema_sha256=_schema_sha256(),
        dataset_fingerprint=fingerprint,
        generation_task_id=ATOM_ID,
        generation_run_id=generation_run_id,
        validation_receipt_sha256=canonical_sha256({"score": score, "r0": r0_search_sha256}),
        first_reliable_available_at=available_at,
        created_at=available_at,
        content_sha256=canonical_sha256({"fingerprint": fingerprint, "file": file_sha256}),
    )
    decision = {
        "schema": RECEIPT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "scientific_terminal": score.get("terminal"),
        "internal_capture_state": "CAPTURE_COMPLETE",
        "score": dict(score),
        "r0_search_sha256": r0_search_sha256,
        "dataset_fingerprint": fingerprint,
        "provider_requests": provider_requests,
        "outcome_consumed": True,
    }
    published = {
        "commit_point": COMMIT_POINT_KIND,
        "dataset_manifest_id": DATASET_MANIFEST_ID,
        "dataset_fingerprint": fingerprint,
    }
    return {
        LOGICAL_LOCATION: parquet_bytes,
        PARTITION_RELATIVE: canonical_manifest_bytes(partition),
        LABELS_RELATIVE: json.dumps(labels, ensure_ascii=True, sort_keys=True, indent=2).encode("utf-8")
        + b"\n",
        DECISION_RELATIVE: _canonical_json(decision),
        MANIFEST_RELATIVE: canonical_manifest_bytes(dataset),
        PUBLISHED_RELATIVE: _canonical_json(published) + b"\n",
    }


def _install_canonical_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = src.read_bytes()
    if dest.exists() or dest.is_symlink():
        _require(dest.is_file() and not dest.is_symlink(), "CANONICAL_TARGET_SYMLINK")
        _require(dest.read_bytes() == payload, "CANONICAL_TARGET_DRIFT")
        return
    tmp = dest.with_name(dest.name + ".install-tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, dest)


def _publish_bundle(
    staging_payload: Path,
    data_root: Path,
    *,
    publication_hook: Callable[[], None] | None = None,
) -> None:
    payload_relatives = CANONICAL_TARGET_RELATIVES[:-1]
    marker_relative = CANONICAL_TARGET_RELATIVES[-1]
    for relative in payload_relatives:
        _install_canonical_file(staging_payload / relative, Path(data_root) / relative)
    if publication_hook is not None:
        publication_hook()
    _install_canonical_file(staging_payload / marker_relative, Path(data_root) / marker_relative)


def run_first_hit_mix_falsifier(
    *,
    repo_root: Path,
    data_root: Path,
    staging_root: Path,
    authority_phrase: str,
    excluded_mints: set[str] | None = None,
    credential_loader: Callable[[], str] | None = None,
    opener: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] = time.sleep,
    monotonic_clock: Callable[[], float] = time.monotonic,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    publication_hook: Callable[[], None] | None = None,
) -> dict[str, Any]:
    v2_before = v2_complete_path(data_root).read_bytes() if v2_complete_path(data_root).is_file() else None
    published = _load_published_bundle(data_root)
    if published is not None:
        published["provider_requests_new"] = 0
        published["resume"] = "IDEMPOTENT_PUBLISHED"
        _assert_v2_complete_unchanged(data_root, v2_before)
        return published
    policy = load_policy(repo_root)
    validate_policy(policy, repo_root=repo_root)
    _require(authority_phrase == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_INVALID")
    staging = Path(staging_root).resolve()
    _require(not Path(staging_root).is_symlink(), "STAGING_SYMLINK")
    data = Path(data_root).resolve()
    _require(staging != data, "STAGING_INSIDE_RDP")
    try:
        staging.relative_to(data)
    except ValueError:
        pass
    else:
        raise FirstHitError("STAGING_INSIDE_RDP")
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
        raise FirstHitError(str(exc)) from exc
    _require(int(preflight.get("credential_reads") or 0) == 0, "CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT")
    loader = credential_loader or (lambda: load_process_credential({}))
    credential = loader()
    _require(isinstance(credential, str) and bool(credential.strip()), "JUPITER_API_KEY_MISSING_OR_EMPTY")
    credential_reads = 1
    limits = policy.get("runtime_limits") if isinstance(policy.get("runtime_limits"), Mapping) else {}
    staging.mkdir(parents=True, exist_ok=True)
    journal = _load_journal(staging)
    observations: dict[str, Any] = dict(journal.get("observations") or {})
    provider_requests = sum(
        1
        for item in observations.values()
        if isinstance(item, Mapping) and item.get("state") == "COMPLETED"
    )
    last_monotonic: float | None = None

    def persist_raw(observation_id: str, body: bytes, observed_at: str) -> None:
        raw_path = staging / "raw" / f"{observation_id.replace(':', '_')}.body"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if not raw_path.exists():
            raw_path.write_bytes(body)
        env_path = staging / "raw" / f"{observation_id.replace(':', '_')}.envelope.json"
        if not env_path.exists():
            env_path.write_bytes(
                _canonical_json(
                    {
                        "observation_id": observation_id,
                        "observed_at": observed_at,
                        "sha256": _sha256_bytes(body),
                        "bytes": len(body),
                    }
                )
            )

    def call(url: str, observation_id: str) -> dict[str, Any]:
        nonlocal provider_requests, last_monotonic
        cached = observations.get(observation_id)
        if isinstance(cached, Mapping) and cached.get("state") == "COMPLETED" and cached.get("body_sha256"):
            raw_path = staging / "raw" / f"{observation_id.replace(':', '_')}.body"
            body = raw_path.read_bytes()
            return {
                "http_status": int(cached.get("http_status") or 200),
                "body": body,
                "observed_at": cached.get("observed_at"),
                "url_has_api_key": False,
                "response_sha256": cached.get("body_sha256"),
                "resumed": True,
            }
        if isinstance(cached, Mapping) and cached.get("state") == "STARTED":
            raise FirstHitError(IN_FLIGHT_TERMINAL, provider_requests=provider_requests)
        last_at = journal.get("last_call_at")
        if isinstance(last_at, str) and last_at:
            last_wall = _parse_datetime(last_at, "LAST_CALL_AT_INVALID")
            elapsed_wall = (clock() - last_wall).total_seconds()
            if elapsed_wall < PACE_SECONDS:
                sleeper(PACE_SECONDS - elapsed_wall)
        elif last_monotonic is not None:
            elapsed = monotonic_clock() - last_monotonic
            if elapsed < PACE_SECONDS:
                sleeper(PACE_SECONDS - elapsed)
        _require(provider_requests < CALL_CAP, "CALL_CAP_EXCEEDED", provider_requests=provider_requests)
        observations[observation_id] = {
            "state": "STARTED",
            "url": url.split("?", 1)[0],
            "started_at": _format_utc(clock()),
        }
        journal["observations"] = observations
        _save_journal(staging, journal)
        try:
            result = perform_credentialed_get(
                url,
                api_key=credential,
                limits=limits,
                opener=opener,
            )
        except QualificationError as exc:
            raise FirstHitError(str(exc), provider_requests=provider_requests) from exc
        last_monotonic = monotonic_clock()
        if result.get("url_has_api_key") is True:
            raise FirstHitError("API_KEY_IN_URL_LOG_RECEIPT_OR_GIT", provider_requests=provider_requests)
        result["observed_at"] = _format_utc(clock())
        body = result.get("body")
        if isinstance(body, bytes):
            if credential.encode("utf-8") in body:
                raise FirstHitError("RAW_BODY_CONTAINS_CREDENTIAL", provider_requests=provider_requests)
            _assert_quote_body_has_no_transaction(body)
            persist_raw(observation_id, body, str(result["observed_at"]))
        provider_requests += 1
        observations[observation_id] = {
            "state": "COMPLETED",
            "http_status": result.get("http_status"),
            "body_sha256": result.get("response_sha256"),
            "observed_at": result.get("observed_at"),
            "url": url.split("?", 1)[0],
        }
        journal["observations"] = observations
        journal["last_call_at"] = result["observed_at"]
        _save_journal(staging, journal)
        return result

    def sleep_receipt() -> dict[str, Any]:
        _assert_v2_complete_unchanged(data_root, v2_before)
        _require(not published_marker_path(data_root).exists(), "SLEEP_PUBLISHED_DATASET")
        return {
            "schema": RECEIPT_SCHEMA,
            "schema_version": "1.0",
            "atom_id": ATOM_ID,
            "terminal_outcome": SLEEP_TERMINAL,
            "scientific_terminal": None,
            "internal_capture_state": None,
            "provider_requests": provider_requests,
            "credential_reads": credential_reads,
            "density_checks": MAX_DENSITY_CHECKS,
            "quotes_attempted": 0,
            "dataset_published": False,
            "score": None,
            "preflight": preflight,
            "retries": 0,
            "fallbacks": 0,
            "execute_calls": 0,
            "build_calls": 0,
            "wallet_signer_transaction_actions": 0,
            "r1_search_calls": 0,
        }

    hit_index = journal.get("hit_check_index")
    eligible: list[dict[str, Any]] = []
    search_at: datetime | None = None
    r0_sha: str | None = None
    start_index = 0
    if isinstance(hit_index, int):
        start_index = hit_index
    else:
        start_index = MAX_DENSITY_CHECKS
        for check_probe in range(MAX_DENSITY_CHECKS):
            recent_obs = observations.get(f"CHECK:{check_probe:02d}:RECENT")
            search_obs = observations.get(f"CHECK:{check_probe:02d}:SEARCH")
            recent_done = isinstance(recent_obs, Mapping) and recent_obs.get("state") == "COMPLETED"
            if not recent_done:
                start_index = check_probe
                break
            if isinstance(search_obs, Mapping) and search_obs.get("state") == "STARTED":
                start_index = check_probe
                break
            if search_obs is None:
                start_index = check_probe
                break
        else:
            start_index = MAX_DENSITY_CHECKS
    for check_index in range(start_index, MAX_DENSITY_CHECKS):
        cycle_started = clock()
        recent_result = call(RECENT_ENDPOINT, f"CHECK:{check_index:02d}:RECENT")
        recent_terminal, _recent_error, recent_rows = _search_rows(recent_result)
        if recent_terminal != "TOKEN_LIST_OBSERVED" or recent_rows is None:
            if isinstance(hit_index, int):
                raise FirstHitError("INVALID_EVIDENCE_REPLAN", provider_requests=provider_requests)
            observations[f"CHECK:{check_index:02d}:SEARCH"] = {
                "state": "SKIPPED",
                "reason": "RECENT_NOT_OBSERVED",
            }
            journal["observations"] = observations
            _save_journal(staging, journal)
            elapsed = (clock() - cycle_started).total_seconds()
            wait = DENSITY_CHECK_PERIOD_SECONDS - elapsed
            if wait > 0:
                sleeper(wait)
            continue
        search_pool = [
            row
            for row in recent_rows
            if isinstance(row, Mapping)
            and isinstance(row.get("id"), str)
            and row.get("launchpad") == "pump.fun"
            and row.get("id") not in excluded
        ][:100]
        if not search_pool:
            observations[f"CHECK:{check_index:02d}:SEARCH"] = {
                "state": "SKIPPED",
                "reason": "EMPTY_SEARCH_POOL",
            }
            journal["observations"] = observations
            _save_journal(staging, journal)
            elapsed = (clock() - cycle_started).total_seconds()
            wait = DENSITY_CHECK_PERIOD_SECONDS - elapsed
            if wait > 0:
                sleeper(wait)
            continue
        search_url = build_search_url([str(row["id"]) for row in search_pool])
        search_result = call(search_url, f"CHECK:{check_index:02d}:SEARCH")
        search_terminal, _search_error, search_rows = _search_rows(search_result)
        if search_terminal != "TOKEN_LIST_OBSERVED" or search_rows is None:
            elapsed = (clock() - cycle_started).total_seconds()
            wait = DENSITY_CHECK_PERIOD_SECONDS - elapsed
            if wait > 0:
                sleeper(wait)
            continue
        search_at = _parse_datetime(search_result["observed_at"], "SEARCH_TIMESTAMP_INVALID")
        eligible = select_eligible(search_rows, excluded_mints=excluded, snapshot_at=search_at)
        if len(eligible) < MIN_ELIGIBLE_BEFORE_QUOTES:
            elapsed = (clock() - cycle_started).total_seconds()
            wait = DENSITY_CHECK_PERIOD_SECONDS - elapsed
            if wait > 0:
                sleeper(wait)
            continue
        journal["hit_check_index"] = check_index
        _save_journal(staging, journal)
        body = search_result.get("body") if isinstance(search_result.get("body"), bytes) else b""
        r0_sha = str(search_result.get("response_sha256") or _sha256_bytes(body))
        break
    else:
        return sleep_receipt()

    _require(search_at is not None and r0_sha is not None, "R0_UNBOUND", provider_requests=provider_requests)
    capacity = quote_capacity(provider_requests)
    _require(capacity >= MIN_ELIGIBLE_BEFORE_QUOTES, "QUOTE_RESERVE_EXHAUSTED", provider_requests=provider_requests)
    quoted_n = min(len(eligible), capacity)
    quoted = eligible[:quoted_n]
    unquoted = eligible[quoted_n:]
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
                "quoted": True,
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
    for item in unquoted:
        rows.append(
            {
                "mint": str(item["id"]),
                "search_row": item,
                "quoted": False,
                "buy_terminal": None,
                "h900_terminal": NOT_QUOTED,
                "y": None,
            }
        )
    _require(all(_row_complete_for_score(row) for row in rows), "PARTIAL_QUOTE_SCORE_FORBIDDEN")
    score = score_frozen_mix_dataset(rows)
    _require(
        score.get("terminal")
        in {
            "INVALID_EVIDENCE_REPLAN",
            "CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY",
            "EARN_ONE_CONFIRMATORY_FRESH_OOS",
        },
        "SCIENTIFIC_TERMINAL_INVALID",
    )
    available_at = search_at if search_at is not None else clock()
    bundle = _parquet_and_manifests(
        rows=rows,
        score=score,
        r0_search_sha256=str(r0_sha),
        available_at=available_at,
        generation_run_id="run-" + hashlib.sha256((_format_utc(available_at) + str(r0_sha)).encode()).hexdigest()[:16],
        provider_requests=provider_requests,
    )
    payload_dir = staging / f"publish-{uuid.uuid4().hex}"
    payload_dir.mkdir(parents=True, exist_ok=False)
    for relative in CANONICAL_TARGET_RELATIVES:
        dest = payload_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bundle[relative])
    _publish_bundle(payload_dir, data_root, publication_hook=publication_hook)
    shutil.rmtree(payload_dir, ignore_errors=True)
    _assert_v2_complete_unchanged(data_root, v2_before)
    decision = json.loads((Path(data_root) / DECISION_RELATIVE).read_text(encoding="utf-8"))
    decision["terminal_outcome"] = score.get("terminal")
    decision["eligible_count"] = len(eligible)
    decision["quoted_count"] = quoted_n
    decision["unquoted_count"] = len(unquoted)
    decision["credential_reads"] = credential_reads
    decision["dataset_published"] = True
    decision["internal_capture_state"] = "CAPTURE_COMPLETE"
    return decision
