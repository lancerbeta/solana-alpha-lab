"""Name a bounded next GTA target from adopted pool-history bytes.

The unique resolver is frozen before candidate inspection. Naming a
target does not authorize a network call. The Pump program and the
already-scanned pool are never next GTA targets.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from solana_alpha_lab.lifecycle_discovery_transport import (
    ProgramLogAttributionError,
    _decode_attributed_events,
)
from solana_alpha_lab.pump_event_decoder import (
    PUMP_PROGRAM_ID,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.task37_h11_migration_clock_capture import (
    CaptureError,
    CaptureIntegrityError,
    OutcomeGuard,
    _account_keys,
    _mapping,
    _require,
    _sequence,
    _text,
    canonical_json,
    format_utc,
    load_live_pages,
    sha256_bytes,
    verify_rc001_and_holdout,
)

ATOM_ID = "T38-A1_RC002_H11_NEXT_GTA_TARGET_FROM_POOL_HISTORY_V1"
SCHEMA = "smial.task38.rc002-h11-next-gta-target.policy"
RESULT_SCHEMA = "smial.task38.rc002-h11-next-gta-target.result"
RESEARCH_CYCLE_ID = "RESEARCH-CYCLE-RC002-001"
HYPOTHESIS_ID = "HYP-RC002-H11-LIFECYCLE-CLOCK-V1"
TRIAL_ID = "TRIAL-RC002-H11-NEXT-GTA-TARGET-001"
FAMILY = "H11_LIFECYCLE_CLOCK"
ROUTE_ID = "HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001"
WSOL_MINT = "So11111111111111111111111111111111111111112"
CREATE_EVENT = "CreateEvent"
TERMINAL_OUTCOMES = (
    "NEXT_BOUNDED_GTA_TARGET_NAMED",
    "CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY",
)
ALLOWED_KINDS = ("TOKEN_MINT", "BONDING_CURVE")
TOKEN_BALANCE_OWNER_SCOPE = "SCANNED_POOL_ONLY"


class TargetError(CaptureError):
    """Policy or protocol identity is invalid."""


class TargetIntegrityError(CaptureIntegrityError):
    """Frozen RC-001, holdout or adopted-route identity drifted."""


def load_policy(path: Path) -> dict[str, Any]:
    import yaml

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    policy = dict(_mapping(document, "POLICY_INVALID"))
    _require(policy.get("schema") == SCHEMA, "POLICY_SCHEMA_DRIFT")
    _require(policy.get("schema_version") == "1.0", "POLICY_VERSION_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "POLICY_ATOM_DRIFT")
    _require(policy.get("task_id") == "TASK-38", "POLICY_TASK_DRIFT")
    _require(
        list(policy.get("terminal_outcomes") or []) == list(TERMINAL_OUTCOMES),
        "POLICY_TERMINAL_OUTCOME_DRIFT",
    )
    resolver = dict(_mapping(policy.get("target_resolver"), "RESOLVER_INVALID"))
    _require(
        resolver.get("freeze_before_candidate_inspection") is True,
        "RESOLVER_NOT_FROZEN",
    )
    _require(
        list(resolver.get("allowed_kinds") or []) == list(ALLOWED_KINDS),
        "ALLOWED_KINDS_DRIFT",
    )
    _require(resolver.get("prefer_kind") == "TOKEN_MINT", "PREFER_KIND_DRIFT")
    _require(
        resolver.get("token_balance_owner_scope") == TOKEN_BALANCE_OWNER_SCOPE,
        "OWNER_SCOPE_DRIFT",
    )
    exclude = dict(_mapping(resolver.get("exclude"), "EXCLUDE_INVALID"))
    _require(exclude.get("pump_program") is True, "PUMP_PROGRAM_MUST_BE_EXCLUDED")
    _require(exclude.get("scanned_pool") is True, "SCANNED_POOL_MUST_BE_EXCLUDED")
    _require(exclude.get("wrapped_sol_quote") is True, "WSOL_QUOTE_MUST_BE_EXCLUDED")
    _require(resolver.get("wrapped_sol_mint") == WSOL_MINT, "WSOL_MINT_DRIFT")
    _require(
        resolver.get("pump_program_id") == PUMP_PROGRAM_ID,
        "PUMP_PROGRAM_ID_DRIFT",
    )
    _require(
        list(resolver.get("create_event_fields") or []) == ["mint", "bonding_curve"],
        "CREATE_EVENT_FIELDS_DRIFT",
    )
    _require(
        resolver.get("unbounded_gta_forbidden") is True,
        "UNBOUNDED_GTA_MUST_STAY_FORBIDDEN",
    )
    _require(
        resolver.get("naming_does_not_authorize_network") is True,
        "NAMING_MUST_NOT_AUTHORIZE_NETWORK",
    )
    route = dict(_mapping(policy.get("adopted_route"), "ROUTE_INVALID"))
    _require(route.get("route_id") == ROUTE_ID, "ROUTE_ID_DRIFT")
    _require(route.get("provider_routes_max") == 1, "SECOND_PROVIDER_FORBIDDEN")
    _require(
        route.get("target_kind") == "PUMPSWAP_POOL_ADDRESS",
        "TARGET_KIND_DRIFT",
    )
    authority = dict(_mapping(policy.get("external_authority"), "AUTHORITY_INVALID"))
    _require(authority.get("network") is False, "NETWORK_FORBIDDEN")
    _require(authority.get("credentials") is False, "CREDENTIALS_FORBIDDEN")
    _require(authority.get("cash_spend") is False, "CASH_SPEND_FORBIDDEN")
    _require(authority.get("paid_plan") is False, "PAID_PLAN_FORBIDDEN")
    policy["target_resolver"] = resolver
    policy["adopted_route"] = route
    return policy


def resolver_fingerprint(policy: Mapping[str, Any]) -> str:
    resolver = dict(_mapping(policy.get("target_resolver"), "RESOLVER_INVALID"))
    return sha256_bytes(canonical_json(resolver))


def _token_balances(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    meta = dict(_mapping(row.get("meta") or {}, "META_INVALID"))
    collected: list[Mapping[str, Any]] = []
    for key in ("preTokenBalances", "postTokenBalances"):
        raw = meta.get(key) or []
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            continue
        for item in raw:
            if isinstance(item, Mapping):
                collected.append(item)
    return collected


def _excluded(address: str, *, pool_address: str) -> bool:
    return address in {PUMP_PROGRAM_ID, pool_address, WSOL_MINT}


def scan_pool_history(
    rows: Sequence[Mapping[str, Any]],
    *,
    plan: Any,
    pool_address: str,
) -> dict[str, Any]:
    pool_owned_mints: set[str] = set()
    incidental_mints: set[str] = set()
    create_mints: set[str] = set()
    bonding_curves: set[str] = set()
    pump_in_keys = 0
    create_events = 0
    attribution_errors: dict[str, int] = {}
    for raw in rows:
        row = dict(_mapping(raw, "ROW_INVALID"))
        keys = _account_keys(row)
        if PUMP_PROGRAM_ID in keys:
            pump_in_keys += 1
        for balance in _token_balances(row):
            mint = balance.get("mint")
            owner = balance.get("owner")
            if not isinstance(mint, str) or not mint:
                continue
            if owner == pool_address:
                pool_owned_mints.add(mint)
            else:
                incidental_mints.add(mint)
        meta = dict(_mapping(row.get("meta") or {}, "META_INVALID"))
        logs = meta.get("logMessages") or []
        if not isinstance(logs, Sequence) or isinstance(logs, (str, bytes)):
            logs = []
        ok = meta.get("err") is None
        try:
            decoded, _unsupported = _decode_attributed_events(
                plan,
                logs=[str(item) for item in logs],
                transaction_succeeded=bool(ok),
                allow_unclosed_stack=True,
            )
        except ProgramLogAttributionError as exc:
            code = str(exc)
            attribution_errors[code] = attribution_errors.get(code, 0) + 1
            continue
        for event in decoded:
            if event.event_name != CREATE_EVENT:
                continue
            create_events += 1
            mint = event.mint
            curve = event.fields.get("bonding_curve")
            if isinstance(mint, str) and mint:
                create_mints.add(mint)
            if isinstance(curve, str) and curve:
                bonding_curves.add(curve)
    pool_owned_mints = {item for item in pool_owned_mints if not _excluded(item, pool_address=pool_address)}
    create_mints = {item for item in create_mints if not _excluded(item, pool_address=pool_address)}
    bonding_curves = {
        item for item in bonding_curves if not _excluded(item, pool_address=pool_address)
    }
    incidental_mints = {
        item for item in incidental_mints if not _excluded(item, pool_address=pool_address)
    }
    missingness: list[str] = []
    if not pool_owned_mints and not create_mints:
        missingness.append("NO_UNIQUE_POOL_OWNED_OR_CREATE_MINT")
    if not bonding_curves:
        missingness.append("NO_CREATE_EVENT_BONDING_CURVE")
    if pump_in_keys == 0:
        missingness.append("PUMP_PROGRAM_NOT_IN_ACCOUNT_KEYS")
    return {
        "transaction_count": len(rows),
        "pump_program_in_account_keys": pump_in_keys,
        "create_events": create_events,
        "pool_owned_mints": sorted(pool_owned_mints),
        "create_mints": sorted(create_mints),
        "bonding_curves": sorted(bonding_curves),
        "incidental_mints": sorted(incidental_mints),
        "attribution_errors": attribution_errors,
        "missingness": missingness,
        "pool_address": pool_address,
        "emitting_program_id": PUMP_PROGRAM_ID,
        "route_id": ROUTE_ID,
    }


def decide_terminal(scan: Mapping[str, Any]) -> dict[str, Any]:
    mints = set(_sequence(scan.get("pool_owned_mints") or [], "POOL_OWNED_INVALID"))
    mints.update(_sequence(scan.get("create_mints") or [], "CREATE_MINTS_INVALID"))
    curves = set(_sequence(scan.get("bonding_curves") or [], "CURVES_INVALID"))
    named_address = None
    named_kind = None
    if len(mints) == 1:
        named_address = next(iter(mints))
        named_kind = "TOKEN_MINT"
        terminal = "NEXT_BOUNDED_GTA_TARGET_NAMED"
    elif len(mints) == 0 and len(curves) == 1:
        named_address = next(iter(curves))
        named_kind = "BONDING_CURVE"
        terminal = "NEXT_BOUNDED_GTA_TARGET_NAMED"
    else:
        terminal = "CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY"
    if named_address in {PUMP_PROGRAM_ID, scan.get("pool_address"), WSOL_MINT}:
        terminal = "CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY"
        named_address = None
        named_kind = None
    ambiguous = len(mints) > 1 or (len(mints) == 0 and len(curves) > 1)
    return {
        "terminal_decision": terminal,
        "named_target_kind": named_kind,
        "named_target_address": named_address,
        "ambiguous": ambiguous,
        "network_authorized": False,
    }


def execute_target(
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    pages: Sequence[Mapping[str, Any]] | None = None,
    compact_scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolver_sha = resolver_fingerprint(policy)
    rc001 = verify_rc001_and_holdout(repo_root, policy)
    guard = OutcomeGuard()
    trial = guard.register(
        {
            "record_id": TRIAL_ID,
            "record_kind": "trial",
            "status": "PENDING",
            "created_at": "2026-08-15T22:00:00Z",
            "hypothesis_id": HYPOTHESIS_ID,
            "research_cycle_id": RESEARCH_CYCLE_ID,
            "resolver_sha256": resolver_sha,
            "live_PIT_claim": False,
            "execution_claim": False,
        }
    )
    guard.allow()
    route = dict(_mapping(policy.get("adopted_route"), "ROUTE_INVALID"))
    pool_address = _text(route.get("pool_address"), "POOL_INVALID")
    plan = load_pinned_pump_event_plan(
        repo_root / _text(route.get("decoder_idl_path"), "IDL_PATH_INVALID")
    )
    live_universe = False
    if pages is not None:
        scan = scan_pool_history(pages, plan=plan, pool_address=pool_address)
    elif compact_scan is not None:
        scan = dict(compact_scan)
        scan.setdefault("pool_owned_mints", [])
        scan.setdefault("create_mints", [])
        scan.setdefault("bonding_curves", [])
        scan.setdefault("incidental_mints", [])
        scan.setdefault("missingness", [])
        scan.setdefault("attribution_errors", {})
        scan.setdefault("create_events", 0)
        scan.setdefault("pump_program_in_account_keys", 0)
    else:
        live_pages = load_live_pages(repo_root, policy)
        _require(live_pages is not None, "LIVE_A4_BYTES_MISSING")
        scan = scan_pool_history(live_pages, plan=plan, pool_address=pool_address)
        live_universe = True
    decision = decide_terminal(scan)
    terminal = str(decision["terminal_decision"])
    trial_outcome = {
        "NEXT_BOUNDED_GTA_TARGET_NAMED": "PASS",
        "CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY": "INCONCLUSIVE",
    }[terminal]
    trial["status"] = "RECORDED"
    trial["outcome"] = trial_outcome
    trial["evidence_asset_ids"] = ["EVIDENCE-T38-RC002-H11-NEXT-GTA-001"]
    exact_gap = None
    if terminal == "CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY":
        exact_gap = (
            "pool-history bytes do not name a unique mint or bonding_curve "
            "after excluding Pump program, scanned pool and wrapped-SOL quote"
        )
    elif terminal == "NEXT_BOUNDED_GTA_TARGET_NAMED":
        exact_gap = (
            "named target is not a network authorization; "
            "getTransactionsForAddress remains forbidden in this atom"
        )
    return {
        "schema": RESULT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_decision": terminal,
        "research_cycle_id": RESEARCH_CYCLE_ID,
        "resolver_sha256": resolver_sha,
        "trial": trial,
        "named_target": {
            "kind": decision["named_target_kind"],
            "address": decision["named_target_address"],
            "ambiguous": decision["ambiguous"],
            "network_authorized": False,
        },
        "scan": {
            "transaction_count": scan.get("transaction_count"),
            "pump_program_in_account_keys": scan.get("pump_program_in_account_keys"),
            "create_events": scan.get("create_events"),
            "pool_owned_mints": list(scan.get("pool_owned_mints") or []),
            "create_mints": list(scan.get("create_mints") or []),
            "bonding_curves": list(scan.get("bonding_curves") or []),
            "incidental_mint_count": len(list(scan.get("incidental_mints") or [])),
            "attribution_errors": scan.get("attribution_errors") or {},
            "missingness": scan.get("missingness") or [],
            "pool_address": pool_address,
            "route_id": ROUTE_ID,
            "scanned_target_kind": "PUMPSWAP_POOL_ADDRESS",
            "exact_gap": exact_gap,
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
        "network_authorized": False,
        "rc001_mutated": False,
        "holdout_consumed": False,
        "remaining_rc001_deprioritized": True,
        "side_effects": {
            "cash_spend_usd_cents": 0,
            "credential_reads": 0,
            "fallbacks": 0,
            "provider_requests": 0,
            "retries": 0,
            "wallet_signer_transaction_actions": 0,
        },
        "non_claims": [
            "NO_LIVE_PIT_CLAIM",
            "NO_EXECUTION_CLAIM",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_RC001_MUTATION",
            "NO_HOLDOUT_CONSUMPTION",
            "NO_H11_EFFECT_SCREEN",
            "NO_NETWORK_OR_NEW_HELIUS_CALL",
            "NO_UNBOUNDED_PUMP_PROGRAM_GTA",
            "NAMING_IS_NOT_GTA_AUTHORIZATION",
        ],
    }


def format_owner_readout(result: Mapping[str, Any]) -> str:
    scan = dict(_mapping(result.get("scan"), "SCAN_INVALID"))
    named = dict(_mapping(result.get("named_target"), "TARGET_INVALID"))
    address = named.get("address") or "нет"
    kind = named.get("kind") or "нет"
    gap = scan.get("exact_gap") or "нет"
    return (
        "# TASK-38 RC002 — следующий bounded GTA target\n\n"
        f"**Терминальное решение:** `{result['terminal_decision']}`\n\n"
        "Это offline naming адреса из уже захваченных A22/A23 байт. "
        "Это не новый Helius-вызов, не live PIT, не execution, не альфа "
        "и не cashflow. Именование цели не разрешает GTA.\n\n"
        "## Что проверено\n\n"
        f"- family: `{FAMILY}`\n"
        f"- research cycle: `{result['research_cycle_id']}`\n"
        f"- trial: `{result['trial']['record_id']}` outcome "
        f"`{result['trial']['outcome']}`\n"
        f"- resolver SHA-256: `{result['resolver_sha256']}`\n"
        f"- named kind: `{kind}`\n"
        f"- named address: `{address}`\n"
        f"- network authorized: `{result['network_authorized']}`\n"
        f"- live universe txs: `{scan.get('transaction_count')}`\n"
        f"- pool-owned mints after exclusions: "
        f"`{len(scan.get('pool_owned_mints') or [])}`\n"
        f"- CreateEvent mints / bonding_curve: "
        f"`{len(scan.get('create_mints') or [])}` / "
        f"`{len(scan.get('bonding_curves') or [])}`\n"
        f"- incidental other-owner mints: `{scan.get('incidental_mint_count')}`\n"
        f"- Pump program in account keys: `{scan.get('pump_program_in_account_keys')}`\n"
        f"- exact gap: {gap}\n"
        "- RC001 definitions unchanged; remaining H13/H02 deprioritized\n"
        "- RC001 holdout not consumed\n\n"
        "## Маршрут\n\n"
        f"- scanned `{scan.get('route_id')}` target=`{scan.get('scanned_target_kind')}` "
        f"pool=`{scan.get('pool_address')}`\n"
        "- decoder: pinned TASK-08 Pump Create/Complete/CompletePumpAmmMigration\n"
        "- unique resolver: pool-owned vault mint, else CreateEvent mint, "
        "else unique bonding_curve; never Pump program, never scanned pool, "
        "never wrapped-SOL quote\n"
        "- new provider requests: 0; cash: 0\n\n"
        "## Что этим атомом не делается\n\n"
        "- новый getTransactionsForAddress / Helius call\n"
        "- GTA всего Pump program "
        f"`{PUMP_PROGRAM_ID}`\n"
        "- live PIT / available_to_strategy_at\n"
        "- H11 effect screen, H13 или H02 trial\n"
        "- paid capture / второй провайдер\n"
        "- RC001 mutation, wallet, signer, tx, deployment\n\n"
        "Это не product DONE, не альфа и не cashflow.\n"
    )


__all__ = [
    "ATOM_ID",
    "FAMILY",
    "TERMINAL_OUTCOMES",
    "TRIAL_ID",
    "TargetError",
    "TargetIntegrityError",
    "WSOL_MINT",
    "decide_terminal",
    "execute_target",
    "format_owner_readout",
    "format_utc",
    "load_policy",
    "resolver_fingerprint",
    "scan_pool_history",
    "sha256_bytes",
    "canonical_json",
]
