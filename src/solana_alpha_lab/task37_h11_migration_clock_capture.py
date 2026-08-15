"""Historical H11 migration-clock capture from adopted pool-history bytes.

Clock definitions are frozen before any event inspection. The live
universe is the A22/A23 Helius pool-history batch decoded with the
pinned Pump event subset. Synthetic pages exist only as protocol tests.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
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
from solana_alpha_lab.task30_raw_to_pit_admissibility import (
    _page_rows,
    sha256_bytes as a24_sha256_bytes,
)
from solana_alpha_lab.task36_h11_lifecycle_clock_screen import (
    freeze_cohort,
    running_peak_at_decision,
)

ATOM_ID = "T37-A1_RC002_H11_MIGRATION_CLOCK_CAPTURE_V1"
SCHEMA = "smial.task37.rc002-h11-migration-clock-capture.policy"
RESULT_SCHEMA = "smial.task37.rc002-h11-migration-clock-capture.result"
RESEARCH_CYCLE_ID = "RESEARCH-CYCLE-RC002-001"
HYPOTHESIS_ID = "HYP-RC002-H11-LIFECYCLE-CLOCK-V1"
TRIAL_ID = "TRIAL-RC002-H11-MIGRATION-CLOCK-CAPTURE-001"
FAMILY = "H11_LIFECYCLE_CLOCK"
ROUTE_ID = "HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001"
TERMINAL_OUTCOMES = (
    "CLOCKS_RECONSTRUCTED_COHORT_READY",
    "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT",
    "INSUFFICIENT_SCALE_WITHOUT_PAID_CAPTURE",
    "STOP_INTEGRITY_CONFLICT",
)
RC001_GROUPS = (
    "RC001-H13-COMPOSITE-VETO",
    "RC001-H07-H01-LIQUIDITY-RETENTION",
    "RC001-H02-H10-H14-PULLBACK-RECLAIM",
)
CREATE_EVENT = "CreateEvent"
MIGRATION_EVENT = "CompletePumpAmmMigrationEvent"
COMPLETE_EVENT = "CompleteEvent"


class CaptureError(ValueError):
    """Policy or protocol identity is invalid."""


class CaptureIntegrityError(CaptureError):
    """Frozen RC-001, holdout or adopted-route identity drifted."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CaptureError(code)


def _integrity(condition: bool, code: str) -> None:
    if not condition:
        raise CaptureIntegrityError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _sequence(value: object, code: str) -> Sequence[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        code,
    )
    return value


def _text(value: object, code: str) -> str:
    _require(isinstance(value, str) and value, code)
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_policy(path: Path) -> dict[str, Any]:
    import yaml

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    policy = dict(_mapping(document, "POLICY_INVALID"))
    _require(policy.get("schema") == SCHEMA, "POLICY_SCHEMA_DRIFT")
    _require(policy.get("schema_version") == "1.0", "POLICY_VERSION_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "POLICY_ATOM_DRIFT")
    _require(policy.get("task_id") == "TASK-37", "POLICY_TASK_DRIFT")
    _require(
        list(policy.get("terminal_outcomes") or []) == list(TERMINAL_OUTCOMES),
        "POLICY_TERMINAL_OUTCOME_DRIFT",
    )
    clocks = dict(_mapping(policy.get("clock_definitions"), "CLOCKS_INVALID"))
    _require(clocks.get("freeze_before_event_inspection") is True, "CLOCKS_NOT_FROZEN")
    migration = dict(_mapping(clocks.get("migration_at"), "MIGRATION_CLOCK_INVALID"))
    _require(migration.get("source_event") == MIGRATION_EVENT, "MIGRATION_SOURCE_DRIFT")
    _require(migration.get("field") == "timestamp", "MIGRATION_FIELD_DRIFT")
    _require(migration.get("time_basis") == "chain_event_i64", "MIGRATION_BASIS_DRIFT")
    _require(
        migration.get("complete_event_is_not_migration") is True,
        "COMPLETE_EVENT_MUST_NOT_SUBSTITUTE_MIGRATION",
    )
    forbidden = list(_sequence(migration.get("forbidden_sources"), "FORBIDDEN_INVALID"))
    _require(
        forbidden
        == [
            "later_price",
            "first_pumpswap_trade",
            "block_time_heuristic",
            "first_reliable_availability",
        ],
        "FORBIDDEN_SOURCE_DRIFT",
    )
    create = dict(_mapping(clocks.get("create_at"), "CREATE_CLOCK_INVALID"))
    _require(create.get("source_event") == CREATE_EVENT, "CREATE_SOURCE_DRIFT")
    peak = dict(_mapping(clocks.get("running_peak_at"), "PEAK_CLOCK_INVALID"))
    _require(peak.get("future_events") == "IGNORE", "FUTURE_PEAK_NOT_IGNORED")
    protocol = dict(_mapping(policy.get("capture_protocol"), "PROTOCOL_INVALID"))
    _require(protocol.get("family") == FAMILY, "PROTOCOL_FAMILY_DRIFT")
    _require(
        protocol.get("stage") == "HISTORICAL_CLOCK_RECONSTRUCTION",
        "PROTOCOL_STAGE_DRIFT",
    )
    _require(protocol.get("live_PIT_claim") is False, "LIVE_PIT_CLAIM_FORBIDDEN")
    _require(protocol.get("execution_claim") is False, "EXECUTION_CLAIM_FORBIDDEN")
    _require(protocol.get("h11_effect_screen") is False, "H11_EFFECT_SCREEN_FORBIDDEN")
    minima = dict(
        _mapping(protocol.get("minimum_independent_units"), "MINIMA_INVALID")
    )
    _require(minima.get("pools") == 8, "POOL_MINIMUM_DRIFT")
    _require(minima.get("days") == 2, "DAY_MINIMUM_DRIFT")
    _require(minima.get("deployers") == 2, "DEPLOYER_MINIMUM_DRIFT")
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
    policy["clock_definitions"] = clocks
    policy["capture_protocol"] = protocol
    policy["adopted_route"] = route
    return policy


def clock_fingerprint(policy: Mapping[str, Any]) -> str:
    clocks = dict(_mapping(policy.get("clock_definitions"), "CLOCKS_INVALID"))
    return sha256_bytes(canonical_json(clocks))


def verify_rc001_and_holdout(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    freeze_cfg = dict(_mapping(policy.get("rc001_freeze"), "RC001_FREEZE_INVALID"))
    freeze_path = repo_root / _text(freeze_cfg.get("path"), "RC001_PATH_INVALID")
    freeze_bytes = freeze_path.read_bytes()
    _integrity(
        sha256_bytes(freeze_bytes) == freeze_cfg.get("sha256"),
        "RC001_FREEZE_HASH_DRIFT",
    )
    import yaml

    freeze = dict(_mapping(yaml.safe_load(freeze_bytes), "RC001_FREEZE_INVALID"))
    groups = {
        str(item["group_id"]): str(item["definition_sha256"])
        for item in _sequence(freeze.get("hypothesis_groups"), "RC001_GROUPS_INVALID")
        if isinstance(item, Mapping)
    }
    required = dict(
        _mapping(freeze_cfg.get("required_definition_sha256"), "RC001_REQUIRED_INVALID")
    )
    observed = {group: groups[group] for group in RC001_GROUPS}
    _integrity(observed == required, "RC001_DEFINITION_HASH_DRIFT")
    holdout_cfg = dict(_mapping(policy.get("holdout_guard"), "HOLDOUT_INVALID"))
    holdout_path = repo_root / _text(holdout_cfg.get("path"), "HOLDOUT_PATH_INVALID")
    holdout_bytes = holdout_path.read_bytes()
    _integrity(
        sha256_bytes(holdout_bytes) == holdout_cfg.get("sha256"),
        "HOLDOUT_HASH_DRIFT",
    )
    holdout = dict(_mapping(yaml.safe_load(holdout_bytes), "HOLDOUT_INVALID"))
    records = list(_sequence(holdout.get("records") or [], "HOLDOUT_RECORDS_INVALID"))
    _integrity(records == [], "HOLDOUT_CONSUMED")
    return {
        "path": freeze_cfg["path"],
        "sha256": freeze_cfg["sha256"],
        "definition_sha256": observed,
        "mutation_authorized": False,
        "remaining_families_deprioritized": True,
        "holdout_consumed": False,
        "trial_record_created": False,
    }


class OutcomeGuard:
    """Fail closed if a live-scan outcome is read before trial registration."""

    def __init__(self) -> None:
        self.registered = False

    def register(self, trial: Mapping[str, Any]) -> dict[str, Any]:
        _require(trial.get("status") == "PENDING", "TRIAL_MUST_REGISTER_PENDING")
        self.registered = True
        return dict(trial)

    def allow(self) -> None:
        _require(self.registered, "TRIAL_BEFORE_OUTCOME_VIOLATION")


def _account_keys(row: Mapping[str, Any]) -> list[str]:
    transaction = dict(_mapping(row.get("transaction") or {}, "TRANSACTION_INVALID"))
    message = dict(_mapping(transaction.get("message") or {}, "MESSAGE_INVALID"))
    keys = message.get("accountKeys") or []
    _require(
        isinstance(keys, Sequence) and not isinstance(keys, (str, bytes)),
        "ACCOUNT_KEYS_INVALID",
    )
    return [str(item) for item in keys]


def scan_pool_history(
    rows: Sequence[Mapping[str, Any]],
    *,
    plan: Any,
    pool_address: str,
) -> dict[str, Any]:
    counts = {CREATE_EVENT: 0, COMPLETE_EVENT: 0, MIGRATION_EVENT: 0}
    pump_in_keys = 0
    attribution_errors: dict[str, int] = {}
    reconstructed: list[dict[str, Any]] = []
    creates_by_mint: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(rows):
        row = dict(_mapping(raw, "ROW_INVALID"))
        keys = _account_keys(row)
        if PUMP_PROGRAM_ID in keys:
            pump_in_keys += 1
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
        create_at = None
        migration_at = None
        deployer = None
        mint = None
        event_pool = None
        for event in decoded:
            name = event.event_name
            if name in counts:
                counts[name] += 1
            if name == CREATE_EVENT:
                create_at = event.event_timestamp
                user = event.fields.get("user")
                creator = event.fields.get("creator")
                deployer = str(creator or user or "") or None
                mint = event.mint
                creates_by_mint[mint] = {
                    "create_at": create_at,
                    "deployer_id": deployer,
                }
            elif name == MIGRATION_EVENT:
                migration_at = event.event_timestamp
                event_pool = event.destination_pool
                mint = mint or event.mint
        if mint and mint in creates_by_mint:
            prior = creates_by_mint[mint]
            create_at = create_at or prior.get("create_at")
            deployer = deployer or prior.get("deployer_id")
        if migration_at is not None:
            reconstructed.append(
                {
                    "row_id": f"P{index:04d}",
                    "pool_id": event_pool or pool_address,
                    "deployer_id": deployer,
                    "mint": mint,
                    "create_at": create_at,
                    "migration_at": migration_at,
                    "complete_event_only": False,
                }
            )
    missingness = []
    if counts[CREATE_EVENT] == 0:
        missingness.append("CREATE_EVENT_NOT_IN_ADDRESSED_HISTORY")
    if counts[MIGRATION_EVENT] == 0:
        missingness.append("MIGRATION_EVENT_NOT_IN_ADDRESSED_HISTORY")
    if pump_in_keys == 0:
        missingness.append("PUMP_PROGRAM_NOT_IN_ACCOUNT_KEYS")
    if counts[COMPLETE_EVENT] > 0 and counts[MIGRATION_EVENT] == 0:
        missingness.append("MIGRATION_STARTED_NOT_MIGRATED")
    return {
        "transaction_count": len(rows),
        "pump_program_in_account_keys": pump_in_keys,
        "create_events": counts[CREATE_EVENT],
        "complete_events": counts[COMPLETE_EVENT],
        "migration_events": counts[MIGRATION_EVENT],
        "attribution_errors": attribution_errors,
        "missingness": missingness,
        "reconstructed": reconstructed,
        "pool_address": pool_address,
        "emitting_program_id": PUMP_PROGRAM_ID,
        "route_id": ROUTE_ID,
    }


def decide_terminal(
    scan: Mapping[str, Any],
    *,
    minima: Mapping[str, Any],
) -> str:
    reconstructed = list(_sequence(scan.get("reconstructed") or [], "RECONSTRUCTED"))
    if scan.get("create_events") == 0 and scan.get("migration_events") == 0:
        return "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT"
    pools = {str(item.get("pool_id")) for item in reconstructed if item.get("pool_id")}
    days = set()
    deployers = {
        str(item.get("deployer_id"))
        for item in reconstructed
        if item.get("deployer_id")
    }
    for item in reconstructed:
        stamp = item.get("migration_at")
        if isinstance(stamp, int) and not isinstance(stamp, bool):
            days.add(
                datetime.fromtimestamp(stamp, tz=UTC).date().isoformat()
            )
    if (
        len(reconstructed) == 0
        or len(pools) < int(minima["pools"])
        or len(days) < int(minima["days"])
        or len(deployers) < int(minima["deployers"])
    ):
        return "INSUFFICIENT_SCALE_WITHOUT_PAID_CAPTURE"
    return "CLOCKS_RECONSTRUCTED_COHORT_READY"


def migration_timestamp_from_events(
    decoded_events: Sequence[Any],
    *,
    later_price: object = None,
) -> int | None:
    del later_price
    for event in decoded_events:
        if getattr(event, "event_name", None) == MIGRATION_EVENT:
            return int(event.event_timestamp)
    return None


def load_live_pages(repo_root: Path, policy: Mapping[str, Any]) -> list[Mapping[str, Any]] | None:
    route = dict(_mapping(policy.get("adopted_route"), "ROUTE_INVALID"))
    a22 = dict(_mapping(route.get("a22_raw"), "A22_INVALID"))
    a23 = dict(_mapping(route.get("a23_terminal_page"), "A23_INVALID"))
    a22_path = repo_root / _text(a22.get("path"), "A22_PATH_INVALID")
    a23_path = repo_root / _text(a23.get("path"), "A23_PATH_INVALID")
    if not a22_path.is_file() or not a23_path.is_file():
        return None
    a22_payload = a22_path.read_bytes()
    a23_payload = a23_path.read_bytes()
    _integrity(a24_sha256_bytes(a22_payload) == a22.get("sha256"), "A22_HASH_DRIFT")
    _integrity(len(a22_payload) == a22.get("bytes"), "A22_BYTES_DRIFT")
    _integrity(a24_sha256_bytes(a23_payload) == a23.get("sha256"), "A23_HASH_DRIFT")
    _integrity(len(a23_payload) == a23.get("bytes"), "A23_BYTES_DRIFT")
    rows, cursor = _page_rows(a22_payload)
    _integrity(len(rows) == 520, "A22_ROW_COUNT_DRIFT")
    _integrity(cursor is not None and cursor != "", "A22_CURSOR_MISSING")
    terminal_rows, terminal_cursor = _page_rows(a23_payload)
    _integrity(terminal_rows == [], "A23_TERMINAL_ROWS_DRIFT")
    _integrity(terminal_cursor is None, "A23_TERMINAL_CURSOR_DRIFT")
    return [dict(_mapping(row, "ROW_INVALID")) for row in rows]


def execute_capture(
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    pages: Sequence[Mapping[str, Any]] | None = None,
    compact_scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    clock_sha = clock_fingerprint(policy)
    rc001 = verify_rc001_and_holdout(repo_root, policy)
    guard = OutcomeGuard()
    trial = guard.register(
        {
            "record_id": TRIAL_ID,
            "record_kind": "trial",
            "status": "PENDING",
            "created_at": "2026-08-15T21:00:00Z",
            "hypothesis_id": HYPOTHESIS_ID,
            "research_cycle_id": RESEARCH_CYCLE_ID,
            "clock_sha256": clock_sha,
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
        scan.setdefault("reconstructed", [])
        scan.setdefault("missingness", [])
        scan.setdefault("attribution_errors", {})
    else:
        live_pages = load_live_pages(repo_root, policy)
        _require(live_pages is not None, "LIVE_A4_BYTES_MISSING")
        scan = scan_pool_history(live_pages, plan=plan, pool_address=pool_address)
        live_universe = True
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
                    datetime.fromtimestamp(int(item["migration_at"]), tz=UTC)
                    .date()
                    .isoformat()
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
    trial["evidence_asset_ids"] = ["EVIDENCE-T37-RC002-H11-CLOCK-CAPTURE-001"]
    return {
        "schema": RESULT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_decision": terminal,
        "research_cycle_id": RESEARCH_CYCLE_ID,
        "clock_sha256": clock_sha,
        "trial": trial,
        "cohort": cohort,
        "scan": {
            "transaction_count": scan.get("transaction_count"),
            "pump_program_in_account_keys": scan.get("pump_program_in_account_keys"),
            "create_events": scan.get("create_events"),
            "complete_events": scan.get("complete_events"),
            "migration_events": scan.get("migration_events"),
            "attribution_errors": scan.get("attribution_errors") or {},
            "missingness": scan.get("missingness") or [],
            "pool_address": pool_address,
            "route_id": ROUTE_ID,
            "target_kind": "PUMPSWAP_POOL_ADDRESS",
            "exact_gap": (
                "CreateEvent and CompletePumpAmmMigrationEvent are not present "
                "in getTransactionsForAddress(pool); Pump program is not in "
                "account keys"
                if terminal == "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT"
                else None
            ),
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
            "NO_AVAILABLE_TO_STRATEGY_AT_CONVERSION",
        ],
    }


def format_owner_readout(result: Mapping[str, Any]) -> str:
    scan = dict(_mapping(result.get("scan"), "SCAN_INVALID"))
    cohort = dict(_mapping(result.get("cohort"), "COHORT_INVALID"))
    gap = scan.get("exact_gap") or "нет"
    return (
        "# TASK-37 RC002 — захват часов H11\n\n"
        f"**Терминальное решение:** `{result['terminal_decision']}`\n\n"
        "Это historical reconstruction часов "
        "`RETROSPECTIVE_EVENT_TIME_RECONSTRUCTION`. Это не live PIT, "
        "не execution, не альфа, не H11 effect screen и не cashflow.\n\n"
        "## Что проверено\n\n"
        f"- family: `{FAMILY}`\n"
        f"- research cycle: `{result['research_cycle_id']}`\n"
        f"- trial: `{result['trial']['record_id']}` outcome "
        f"`{result['trial']['outcome']}`\n"
        f"- clock SHA-256: `{result['clock_sha256']}`\n"
        f"- live universe N: `{cohort.get('n')}`\n"
        f"- pools/days/deployers: `{len(cohort.get('pools') or [])}` / "
        f"`{len(cohort.get('days') or [])}` / "
        f"`{len(cohort.get('deployers') or [])}`\n"
        f"- CreateEvent: `{scan.get('create_events')}`\n"
        f"- CompletePumpAmmMigrationEvent: `{scan.get('migration_events')}`\n"
        f"- Pump program in account keys: `{scan.get('pump_program_in_account_keys')}`\n"
        f"- exact gap: {gap}\n"
        "- RC001 definitions unchanged; remaining H13/H02 deprioritized\n"
        "- RC001 holdout not consumed\n\n"
        "## Маршрут\n\n"
        f"- `{scan.get('route_id')}` target=`{scan.get('target_kind')}` "
        f"pool=`{scan.get('pool_address')}`\n"
        "- decoder: pinned TASK-08 Pump Create/Complete/CompletePumpAmmMigration\n"
        "- new provider requests: 0; cash: 0\n\n"
        "## Что этим атомом не делается\n\n"
        "- live PIT / available_to_strategy_at\n"
        "- повторный H11 effect screen\n"
        "- H13 или H02 trial\n"
        "- paid capture / второй провайдер\n"
        "- RC001 mutation, wallet, signer, tx, deployment\n\n"
        "Это не product DONE, не альфа и не cashflow.\n"
    )
