"""Bounded Helius GTA of the pinned Pump bonding_curve PDA, then TASK-37 clock scan.

The JSON-RPC body is the sealed A22 shape with two intentional deltas:
the address is the derived bonding_curve PDA of the TASK-38 mint, and the
one-day blockTime window is omitted. The Pump program is never a GTA target.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solders.pubkey import Pubkey

from solana_alpha_lab.pump_event_decoder import (
    PUMP_PROGRAM_ID,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.task30_helius_get_transactions_for_address import (
    EXPECTED_ENDPOINT,
    EXPECTED_METHOD,
)
from solana_alpha_lab.task37_h11_migration_clock_capture import (
    FAMILY,
    MIGRATION_EVENT,
    OutcomeGuard,
    canonical_json,
    clock_fingerprint,
    decide_terminal,
    format_utc,
    freeze_cohort,
    scan_pool_history,
    sha256_bytes,
    verify_rc001_and_holdout,
    _mapping,
    _require,
    _sequence,
    _text,
)
from solana_alpha_lab.task39_h11_named_mint_gta_clock_capture import (
    clocks_incomplete,
    credential_free_preflight,
    load_api_key,
    parse_gta_page,
    perform_http_post_once,
)

ATOM_ID = "T40-A1_RC002_H11_BONDING_CURVE_PDA_GTA_CLOCK_CAPTURE_V1"
SCHEMA = "smial.task40.rc002-h11-bonding-curve-pda-gta.policy"
RESULT_SCHEMA = "smial.task40.rc002-h11-bonding-curve-pda-gta.result"
RESEARCH_CYCLE_ID = "RESEARCH-CYCLE-RC002-001"
HYPOTHESIS_ID = "HYP-RC002-H11-LIFECYCLE-CLOCK-V1"
TRIAL_ID = "TRIAL-RC002-H11-BONDING-CURVE-PDA-GTA-001"
ROUTE_ID = "HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001"
NAMED_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
BONDING_CURVE = "ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC"
POOL_ADDRESS = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
OWNER_PHRASE = "OK T40-RC002 H11_BONDING_CURVE_PDA_GTA_ONE_SHOT"
CREDENTIAL_NAME = "HELIUS_API_KEY"
REQUEST_ID_PREFIX = "task40-rc002-h11-bonding-curve-pda-gta-page"
PDA_SEED_CONST = bytes([98, 111, 110, 100, 105, 110, 103, 45, 99, 117, 114, 118, 101])
EXPECTED_BUMP = 255
TERMINAL_OUTCOMES = (
    "CLOCKS_RECONSTRUCTED_COHORT_READY",
    "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT",
    "INSUFFICIENT_SCALE_WITHOUT_PAID_CAPTURE",
    "STOP_INTEGRITY_CONFLICT",
)


class CurveGtaError(ValueError):
    """Policy, PDA or transport identity is invalid."""


class CurveGtaIntegrityError(CurveGtaError):
    """Frozen RC-001, holdout or PDA identity drifted."""


def _integrity(condition: bool, code: str) -> None:
    if not condition:
        raise CurveGtaIntegrityError(code)


def load_pda_subset(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    subset = dict(_mapping(document, "PDA_SUBSET_INVALID"))
    _require(
        subset.get("schema") == "solana_alpha_lab.pump_bonding_curve_pda_subset",
        "PDA_SCHEMA_DRIFT",
    )
    _require(subset.get("schema_version") == "1.0", "PDA_VERSION_DRIFT")
    _require(subset.get("program_id") == PUMP_PROGRAM_ID, "PDA_PROGRAM_DRIFT")
    _require(subset.get("named_mint") == NAMED_MINT, "PDA_MINT_DRIFT")
    _require(subset.get("expected_address") == BONDING_CURVE, "PDA_ADDRESS_DRIFT")
    _require(subset.get("expected_bump") == EXPECTED_BUMP, "PDA_BUMP_DRIFT")
    seeds = list(_sequence(subset.get("seeds"), "PDA_SEEDS_INVALID"))
    _require(len(seeds) == 2, "PDA_SEEDS_DRIFT")
    const_seed = dict(_mapping(seeds[0], "PDA_CONST_SEED_INVALID"))
    account_seed = dict(_mapping(seeds[1], "PDA_ACCOUNT_SEED_INVALID"))
    _require(const_seed.get("kind") == "const", "PDA_CONST_KIND_DRIFT")
    _require(bytes(const_seed.get("value") or []) == PDA_SEED_CONST, "PDA_CONST_BYTES_DRIFT")
    _require(account_seed.get("kind") == "account", "PDA_ACCOUNT_KIND_DRIFT")
    _require(account_seed.get("path") == "mint", "PDA_ACCOUNT_PATH_DRIFT")
    return subset


def derive_bonding_curve_pda(subset: Mapping[str, Any]) -> tuple[str, int]:
    program = Pubkey.from_string(_text(subset.get("program_id"), "PDA_PROGRAM_INVALID"))
    mint = Pubkey.from_string(_text(subset.get("named_mint"), "PDA_MINT_INVALID"))
    pda, bump = Pubkey.find_program_address([PDA_SEED_CONST, bytes(mint)], program)
    address = str(pda)
    _require(address == BONDING_CURVE, "PDA_ADDRESS_DRIFT")
    _require(int(bump) == EXPECTED_BUMP, "PDA_BUMP_DRIFT")
    _require(address != PUMP_PROGRAM_ID, "UNBOUNDED_PUMP_PROGRAM_GTA")
    _require(address != POOL_ADDRESS, "POOL_IS_NOT_NEXT_GTA_TARGET")
    _require(address != NAMED_MINT, "MINT_IS_NOT_BONDING_CURVE")
    return address, int(bump)


def load_policy(path: Path) -> dict[str, Any]:
    import yaml

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    policy = dict(_mapping(document, "POLICY_INVALID"))
    _require(policy.get("schema") == SCHEMA, "POLICY_SCHEMA_DRIFT")
    _require(policy.get("schema_version") == "1.0", "POLICY_VERSION_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "POLICY_ATOM_DRIFT")
    _require(policy.get("task_id") == "TASK-40", "POLICY_TASK_DRIFT")
    _require(
        list(policy.get("terminal_outcomes") or []) == list(TERMINAL_OUTCOMES),
        "POLICY_TERMINAL_OUTCOME_DRIFT",
    )
    clocks = dict(_mapping(policy.get("clock_definitions"), "CLOCKS_INVALID"))
    _require(clocks.get("freeze_before_event_inspection") is True, "CLOCKS_NOT_FROZEN")
    migration = dict(_mapping(clocks.get("migration_at"), "MIGRATION_CLOCK_INVALID"))
    _require(migration.get("source_event") == MIGRATION_EVENT, "MIGRATION_SOURCE_DRIFT")
    protocol = dict(_mapping(policy.get("capture_protocol"), "PROTOCOL_INVALID"))
    _require(protocol.get("family") == FAMILY, "PROTOCOL_FAMILY_DRIFT")
    _require(protocol.get("live_PIT_claim") is False, "LIVE_PIT_CLAIM_FORBIDDEN")
    _require(protocol.get("h11_effect_screen") is False, "H11_EFFECT_SCREEN_FORBIDDEN")
    pda = dict(_mapping(policy.get("pda_subset"), "PDA_POLICY_INVALID"))
    _require(pda.get("expected_address") == BONDING_CURVE, "PDA_ADDRESS_DRIFT")
    _require(pda.get("named_mint") == NAMED_MINT, "PDA_MINT_DRIFT")
    _require(pda.get("program_id") == PUMP_PROGRAM_ID, "PDA_PROGRAM_DRIFT")
    route = dict(_mapping(policy.get("adopted_route"), "ROUTE_INVALID"))
    _require(route.get("route_id") == ROUTE_ID, "ROUTE_ID_DRIFT")
    _require(route.get("endpoint") == EXPECTED_ENDPOINT, "ENDPOINT_INVALID")
    _require(route.get("method") == EXPECTED_METHOD, "METHOD_INVALID")
    _require(route.get("target_kind") == "BONDING_CURVE", "TARGET_KIND_DRIFT")
    _require(route.get("mint_address") == NAMED_MINT, "NAMED_MINT_DRIFT")
    _require(route.get("bonding_curve_address") == BONDING_CURVE, "BONDING_CURVE_DRIFT")
    _require(route.get("pool_address") == POOL_ADDRESS, "POOL_DRIFT")
    _require(route.get("bonding_curve_address") != PUMP_PROGRAM_ID, "UNBOUNDED_PUMP_PROGRAM_GTA")
    _require(route.get("bonding_curve_address") != POOL_ADDRESS, "POOL_IS_NOT_NEXT_GTA_TARGET")
    _require(route.get("bonding_curve_address") != NAMED_MINT, "MINT_IS_NOT_BONDING_CURVE")
    request = dict(_mapping(policy.get("request"), "REQUEST_INVALID"))
    _require(request.get("omit_block_time_filter") is True, "BLOCK_TIME_FILTER_MUST_BE_OMITTED")
    _require(request.get("sort_order") == "asc", "SORT_ORDER_DRIFT")
    _require(request.get("transaction_details") == "full", "DETAILS_DRIFT")
    _require(request.get("limit") == 1000, "LIMIT_DRIFT")
    authority = dict(_mapping(policy.get("external_authority"), "AUTHORITY_INVALID"))
    _require(authority.get("network") is True, "NETWORK_MUST_BE_AUTHORIZED")
    _require(authority.get("credentials") is True, "CREDENTIALS_MUST_BE_AUTHORIZED")
    _require(authority.get("cash_spend") is False, "CASH_SPEND_FORBIDDEN")
    _require(authority.get("owner_phrase") == OWNER_PHRASE, "OWNER_PHRASE_DRIFT")
    _require(authority.get("credential_reference") == CREDENTIAL_NAME, "CREDENTIAL_NAME_DRIFT")
    controls = dict(_mapping(policy.get("execution_controls"), "CONTROLS_INVALID"))
    for key in ("retry", "fallback", "redirect", "scheduler", "background_process"):
        _require(controls.get(key) is False, f"{key.upper()}_FORBIDDEN")
    _require(controls.get("pagination") is True, "PAGINATION_REQUIRED")
    policy["clock_definitions"] = clocks
    policy["capture_protocol"] = protocol
    policy["pda_subset"] = pda
    policy["adopted_route"] = route
    policy["request"] = request
    policy["external_authority"] = authority
    policy["execution_controls"] = controls
    return policy


def build_curve_gta_payload(
    policy: Mapping[str, Any],
    *,
    page_number: int,
    cursor: str | None = None,
) -> dict[str, Any]:
    """A22-shaped body: derived bonding_curve, oldest-first, no one-day window."""

    route = dict(_mapping(policy.get("adopted_route"), "ROUTE_INVALID"))
    request = dict(_mapping(policy.get("request"), "REQUEST_INVALID"))
    _require(type(page_number) is int and page_number in (0, 1, 2), "PAGE_NUMBER_INVALID")
    curve = _text(route.get("bonding_curve_address"), "BONDING_CURVE_INVALID")
    _require(curve == BONDING_CURVE, "BONDING_CURVE_DRIFT")
    _require(curve != PUMP_PROGRAM_ID, "UNBOUNDED_PUMP_PROGRAM_GTA")
    options: dict[str, Any] = {
        "transactionDetails": "full",
        "sortOrder": "asc",
        "limit": int(request["limit"]),
        "commitment": "finalized",
        "encoding": "json",
        "maxSupportedTransactionVersion": 0,
        "filters": {
            "status": "succeeded",
            "tokenAccounts": "none",
        },
    }
    _require("blockTime" not in options["filters"], "BLOCK_TIME_FILTER_FORBIDDEN")
    if cursor is not None:
        _require(type(cursor) is str and cursor, "CURSOR_INVALID")
        options["paginationToken"] = cursor
    return {
        "jsonrpc": "2.0",
        "id": f"{REQUEST_ID_PREFIX}-{page_number}",
        "method": EXPECTED_METHOD,
        "params": [curve, options],
    }


def write_raw_page(raw_root: Path, *, run_id: str, page_number: int, body: bytes) -> dict[str, Any]:
    page_root = raw_root / f"run={run_id}" / f"page={page_number:03d}"
    page_root.mkdir(parents=True, exist_ok=True)
    path = page_root / "raw_response.json"
    path.write_bytes(body)
    digest = sha256_bytes(body)
    manifest = {
        "schema": "smial.task40.bonding-curve-pda-gta.raw-manifest",
        "schema_version": "1.0",
        "run_id": run_id,
        "page_number": page_number,
        "response_bytes": len(body),
        "raw_sha256": digest,
        "retention_class": "A4_OUTSIDE_GIT",
    }
    (page_root / "raw_manifest_v1.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def execute_live_pages(
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    credential: str,
    raw_root: Path,
    run_id: str,
    opener: object | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    limits = dict(_mapping(policy.get("runtime_limits"), "LIMITS_INVALID"))
    max_requests = int(limits["max_provider_requests"])
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    requests = 0
    pages: list[dict[str, Any]] = []
    for page_number in range(0, 3):
        if requests >= max_requests:
            break
        payload = build_curve_gta_payload(policy, page_number=page_number, cursor=cursor)
        transport = perform_http_post_once(policy, payload, credential, opener=opener)
        requests += 1
        _require(transport["http_status"] == 200, "HTTP_STATUS_ERROR")
        body = transport["body"]
        _require(type(body) is bytes, "RESPONSE_BODY_INVALID")
        write_raw_page(raw_root, run_id=run_id, page_number=page_number, body=body)
        page_rows, next_cursor, err = parse_gta_page(body, page_id=str(payload["id"]))
        pages.append(
            {
                "page_number": page_number,
                "transaction_count": len(page_rows),
                "response_bytes": transport["response_bytes"],
                "request_body_sha256": transport["request_body_sha256"],
                "pagination_token_present": next_cursor is not None,
                "provider_error_code": err.get("provider_error_code"),
            }
        )
        if err.get("provider_error_code") is not None:
            raise CurveGtaError("PROVIDER_TYPED_FAILURE")
        rows.extend(page_rows)
        cursor = next_cursor
        if cursor is None:
            break
        plan = load_pinned_pump_event_plan(
            repo_root / str(policy["adopted_route"]["decoder_idl_path"])
        )
        scan = scan_pool_history(rows, plan=plan, pool_address=POOL_ADDRESS)
        if not clocks_incomplete(scan):
            break
    return rows, {"provider_requests": requests, "pages": pages}


def execute_capture(
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    pages: Sequence[Mapping[str, Any]] | None = None,
    live_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    pda = load_pda_subset(repo_root / str(policy["pda_subset"]["path"]))
    derived, bump = derive_bonding_curve_pda(pda)
    clock_sha = clock_fingerprint(policy)
    rc001 = verify_rc001_and_holdout(repo_root, policy)
    guard = OutcomeGuard()
    trial = guard.register(
        {
            "record_id": TRIAL_ID,
            "record_kind": "trial",
            "status": "PENDING",
            "created_at": "2026-08-16T00:00:00Z",
            "hypothesis_id": HYPOTHESIS_ID,
            "research_cycle_id": RESEARCH_CYCLE_ID,
            "clock_sha256": clock_sha,
            "live_PIT_claim": False,
            "execution_claim": False,
        }
    )
    guard.allow()
    route = dict(_mapping(policy.get("adopted_route"), "ROUTE_INVALID"))
    plan = load_pinned_pump_event_plan(repo_root / _text(route.get("decoder_idl_path"), "IDL_PATH_INVALID"))
    live_universe = live_meta is not None
    if pages is None:
        raise CurveGtaError("PAGES_REQUIRED")
    scan = scan_pool_history(list(pages), plan=plan, pool_address=POOL_ADDRESS)
    minima = dict(
        _mapping(
            dict(_mapping(policy.get("capture_protocol"), "PROTOCOL_INVALID")).get(
                "minimum_independent_units"
            ),
            "MINIMA_INVALID",
        )
    )
    terminal = decide_terminal(scan, minima=minima)
    reconstructed = list(scan.get("reconstructed") or [])
    cohort_rows = []
    for item in reconstructed:
        cohort_rows.append(
            {
                "row_id": item["row_id"],
                "pool_id": item["pool_id"],
                "deployer_id": item.get("deployer_id") or "MISSING_UNKNOWN",
                "day_id": (
                    datetime.fromtimestamp(int(item["migration_at"]), tz=UTC).date().isoformat()
                    if item.get("migration_at") is not None
                    else "MISSING_UNKNOWN"
                ),
                "migration_at": item.get("migration_at"),
                "create_at": item.get("create_at"),
            }
        )
    protocol = {
        "minimum_independent_units": minima,
        "include_fast_deaths": True,
        "include_inactive_paths": True,
        "missing_as_typed_gaps": True,
    }
    if cohort_rows:
        cohort = freeze_cohort(cohort_rows, protocol)
    else:
        cohort = {
            "n": 0,
            "pools": [],
            "days": [],
            "deployers": [],
            "row_ids": [],
            "fingerprint": sha256_bytes(canonical_json([])),
        }
    trial_outcome = {
        "CLOCKS_RECONSTRUCTED_COHORT_READY": "PASS",
        "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT": "INCONCLUSIVE",
        "INSUFFICIENT_SCALE_WITHOUT_PAID_CAPTURE": "INCONCLUSIVE",
        "STOP_INTEGRITY_CONFLICT": "INCONCLUSIVE",
    }[terminal]
    trial["status"] = "RECORDED"
    trial["outcome"] = trial_outcome
    trial["evidence_asset_ids"] = ["EVIDENCE-T40-RC002-H11-BONDING-CURVE-PDA-GTA-001"]
    side_effects = {
        "cash_spend_usd_cents": 0,
        "credential_reads": 1 if live_universe else 0,
        "fallbacks": 0,
        "provider_requests": int((live_meta or {}).get("provider_requests") or 0),
        "retries": 0,
        "wallet_signer_transaction_actions": 0,
    }
    return {
        "schema": RESULT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_decision": terminal,
        "research_cycle_id": RESEARCH_CYCLE_ID,
        "clock_sha256": clock_sha,
        "trial": trial,
        "cohort": cohort,
        "derived_pda": {"address": derived, "bump": bump},
        "scan": {
            "transaction_count": scan.get("transaction_count"),
            "pump_program_in_account_keys": scan.get("pump_program_in_account_keys"),
            "create_events": scan.get("create_events"),
            "complete_events": scan.get("complete_events"),
            "migration_events": scan.get("migration_events"),
            "attribution_errors": scan.get("attribution_errors") or {},
            "missingness": scan.get("missingness") or [],
            "pool_address": POOL_ADDRESS,
            "mint_address": NAMED_MINT,
            "bonding_curve_address": BONDING_CURVE,
            "route_id": ROUTE_ID,
            "target_kind": "BONDING_CURVE",
            "pages": list((live_meta or {}).get("pages") or []),
        },
        "rc001_freeze": rc001,
        "holdout": {
            "path": policy["holdout_guard"]["path"],
            "records": 0,
            "sha256": policy["holdout_guard"]["sha256"],
        },
        "live_universe": live_universe,
        "live_PIT_claim": False,
        "execution_claim": False,
        "alpha_claim": False,
        "rc001_mutated": False,
        "holdout_consumed": False,
        "remaining_rc001_deprioritized": True,
        "side_effects": side_effects,
        "non_claims": [
            "NO_LIVE_PIT_CLAIM",
            "NO_EXECUTION_CLAIM",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_RC001_MUTATION",
            "NO_HOLDOUT_CONSUMPTION",
            "NO_H11_EFFECT_SCREEN",
            "NO_UNBOUNDED_PUMP_PROGRAM_GTA",
            "NO_H13_OR_H02_TRIAL",
        ],
    }


def format_owner_readout(result: Mapping[str, Any]) -> str:
    scan = dict(result.get("scan") or {})
    cohort = dict(result.get("cohort") or {})
    side = dict(result.get("side_effects") or {})
    pda = dict(result.get("derived_pda") or {})
    return "\n".join(
        [
            "# TASK-40 RC002 — GTA bonding_curve PDA, часы H11",
            "",
            f"**Терминальное решение:** `{result.get('terminal_decision')}`",
            "",
            "Это один bounded Helius getTransactionsForAddress по bonding_curve,",
            "выведенному PDA-семенами официального Pump IDL из mint TASK-38.",
            "Это не live PIT, не execution, не альфа и не cashflow.",
            "",
            "## Что проверено",
            "",
            f"- family: `{FAMILY}`",
            f"- trial: `{result.get('trial', {}).get('record_id')}` outcome `{result.get('trial', {}).get('outcome')}`",
            f"- mint: `{scan.get('mint_address')}`",
            f"- bonding_curve: `{scan.get('bonding_curve_address')}` bump `{pda.get('bump')}`",
            f"- txs: `{scan.get('transaction_count')}`",
            f"- CreateEvent / CompleteEvent / CompletePumpAmmMigrationEvent: `{scan.get('create_events')}` / `{scan.get('complete_events')}` / `{scan.get('migration_events')}`",
            f"- Pump program in account keys: `{scan.get('pump_program_in_account_keys')}`",
            f"- cohort n/pools/days/deployers: `{cohort.get('n')}` / `{len(cohort.get('pools') or [])}` / `{len(cohort.get('days') or [])}` / `{len(cohort.get('deployers') or [])}`",
            f"- missingness: `{scan.get('missingness')}`",
            f"- provider_requests: `{side.get('provider_requests')}`; cash: `{side.get('cash_spend_usd_cents')}`",
            "",
            "## Что этим атомом не делается",
            "",
            "- GTA всего Pump program",
            "- повторный GTA mint",
            "- H13 / H02 trial",
            "- paid capture / второй провайдер",
            "- live PIT / alpha / cashflow",
            "",
            "Это не product DONE.",
            "",
        ]
    )
