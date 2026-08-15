"""Exploratory H11 lifecycle-clock mechanism screen (retrospective only).

The live universe is admitted from already-tracked historical receipts.
Synthetic cohorts exist only as protocol tests and are never the live
research verdict. RC-001 definitions, holdouts and paid capture stay
untouched.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ATOM_ID = "T36-A1_RC002_H11_LIFECYCLE_CLOCK_MECHANISM_SCREEN_V1"
SCHEMA = "smial.task36.rc002-h11-lifecycle-clock-screen.policy"
RESULT_SCHEMA = "smial.task36.rc002-h11-lifecycle-clock-screen.result"
RESEARCH_CYCLE_ID = "RESEARCH-CYCLE-RC002-001"
HYPOTHESIS_ID = "HYP-RC002-H11-LIFECYCLE-CLOCK-V1"
TRIAL_ID = "TRIAL-RC002-H11-LIFECYCLE-CLOCK-SCREEN-001"
FAMILY = "H11_LIFECYCLE_CLOCK"
TERMINAL_OUTCOMES = (
    "H11_SCREEN_NEGATIVE_DEPRIORITIZE_OR_CLOSE",
    "H11_SCREEN_POSITIVE_EARNS_PROSPECTIVE_CONFIRMATION",
    "H11_SCREEN_INCONCLUSIVE_DATA_SCALE",
    "HISTORICAL_ROUTE_INADEQUATE_REPLAN",
    "STOP_INTEGRITY_CONFLICT",
)
PRIMARY_FEATURES = (
    "time_since_migration",
    "time_since_decision_time_running_peak",
)
RC001_GROUPS = (
    "RC001-H13-COMPOSITE-VETO",
    "RC001-H07-H01-LIQUIDITY-RETENTION",
    "RC001-H02-H10-H14-PULLBACK-RECLAIM",
)


class H11Error(ValueError):
    """Policy or protocol identity is invalid."""


class H11IntegrityError(H11Error):
    """Frozen RC-001, holdout or historical-source identity drifted."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise H11Error(code)


def _integrity(condition: bool, code: str) -> None:
    if not condition:
        raise H11IntegrityError(code)


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
    _require(policy.get("task_id") == "TASK-36", "POLICY_TASK_DRIFT")
    _require(
        list(policy.get("terminal_outcomes") or []) == list(TERMINAL_OUTCOMES),
        "POLICY_TERMINAL_OUTCOME_DRIFT",
    )
    protocol = dict(_mapping(policy.get("screen_protocol"), "PROTOCOL_INVALID"))
    _require(protocol.get("family") == FAMILY, "PROTOCOL_FAMILY_DRIFT")
    _require(
        protocol.get("stage") == "EXPLORATORY_MECHANISM_SCREEN",
        "PROTOCOL_STAGE_DRIFT",
    )
    _require(
        protocol.get("data_semantics") == "RETROSPECTIVE_EVENT_TIME_RECONSTRUCTION",
        "PROTOCOL_SEMANTICS_DRIFT",
    )
    _require(protocol.get("live_PIT_claim") is False, "LIVE_PIT_CLAIM_FORBIDDEN")
    _require(protocol.get("execution_claim") is False, "EXECUTION_CLAIM_FORBIDDEN")
    _require(
        list(protocol.get("primary_features") or []) == list(PRIMARY_FEATURES),
        "PRIMARY_FEATURE_DRIFT",
    )
    _require(protocol.get("parameter_search") is False, "PARAMETER_SEARCH_FORBIDDEN")
    _require(protocol.get("ml_search") is False, "ML_SEARCH_FORBIDDEN")
    _require(
        protocol.get("missing_to_zero_or_flat") is False,
        "MISSING_TO_ZERO_FORBIDDEN",
    )
    _require(protocol.get("random_row_split") is False, "RANDOM_SPLIT_FORBIDDEN")
    policy["screen_protocol"] = protocol
    return policy


def protocol_fingerprint(policy: Mapping[str, Any]) -> str:
    protocol = dict(_mapping(policy.get("screen_protocol"), "PROTOCOL_INVALID"))
    return sha256_bytes(canonical_json(protocol))


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H11IntegrityError(code) from exc
    return dict(_mapping(payload, code))


def _load_yaml(path: Path, code: str) -> dict[str, Any]:
    import yaml

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise H11IntegrityError(code) from exc
    return dict(_mapping(payload, code))


def _bind_file(repo_root: Path, spec: Mapping[str, Any], code: str) -> dict[str, Any]:
    relative = _text(spec.get("path"), code)
    expected = _text(spec.get("sha256"), code)
    path = repo_root / relative
    _integrity(path.is_file(), f"{code}_MISSING")
    observed = sha256_bytes(path.read_bytes())
    _integrity(observed == expected, f"{code}_HASH_DRIFT")
    return {"path": relative, "sha256": observed}


def bind_rc001_freeze(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    spec = dict(_mapping(policy.get("rc001_freeze"), "RC001_FREEZE_INVALID"))
    _integrity(spec.get("mutation_authorized") is False, "RC001_FREEZE_MUTATED")
    bound = _bind_file(repo_root, spec, "RC001_FREEZE")
    freeze = _load_yaml(repo_root / bound["path"], "RC001_FREEZE_INVALID")
    groups = {
        str(group.get("group_id")): group
        for group in _sequence(freeze.get("hypothesis_groups"), "RC001_GROUPS")
        if isinstance(group, Mapping)
    }
    required = dict(_mapping(spec.get("required_definition_sha256"), "RC001_HASHES"))
    observed_hashes: dict[str, str] = {}
    for group_id in RC001_GROUPS:
        _integrity(group_id in groups, f"RC001_GROUP_MISSING:{group_id}")
        group = dict(_mapping(groups[group_id], "RC001_GROUP"))
        digest = str(group.get("definition_sha256") or "")
        _integrity(digest == required[group_id], f"RC001_DEFINITION_DRIFT:{group_id}")
        observed_hashes[group_id] = digest
    cycle = dict(_mapping(freeze.get("research_cycle"), "RC001_CYCLE"))
    _integrity(cycle.get("holdout_consumed") is False, "RC001_HOLDOUT_CONSUMED")
    _integrity(cycle.get("trial_record_created") is False, "RC001_TRIAL_CREATED")
    return {
        "path": bound["path"],
        "sha256": bound["sha256"],
        "mutation_authorized": False,
        "holdout_consumed": False,
        "trial_record_created": False,
        "definition_sha256": observed_hashes,
        "remaining_families_deprioritized": True,
    }


def bind_holdout(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    spec = dict(_mapping(policy.get("holdout_guard"), "HOLDOUT_GUARD_INVALID"))
    bound = _bind_file(repo_root, spec, "HOLDOUT")
    document = _load_yaml(repo_root / bound["path"], "HOLDOUT_INVALID")
    records = list(_sequence(document.get("records"), "HOLDOUT_RECORDS"))
    _integrity(records == [], "HOLDOUT_CONSUMED")
    return {"path": bound["path"], "sha256": bound["sha256"], "records": 0}


def bind_historical_sources(
    repo_root: Path, policy: Mapping[str, Any]
) -> list[dict[str, Any]]:
    sources = []
    for spec in _sequence(policy.get("historical_sources"), "HISTORICAL_SOURCES"):
        item = dict(_mapping(spec, "HISTORICAL_SOURCE"))
        bound = _bind_file(repo_root, item, f"SOURCE_{item.get('source_id')}")
        payload = _load_json(repo_root / bound["path"], "HISTORICAL_SOURCE_JSON")
        sources.append(
            {
                "source_id": _text(item.get("source_id"), "SOURCE_ID"),
                "path": bound["path"],
                "sha256": bound["sha256"],
                "payload": payload,
            }
        )
    _require(len(sources) >= 4, "HISTORICAL_SOURCE_COUNT")
    return sources


def inventory_historical_routes(
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_id = {str(item["source_id"]): item for item in sources}
    task08 = dict(_mapping(by_id["TASK08_LIFECYCLE"]["payload"], "TASK08"))
    accepted08 = dict(_mapping(task08.get("accepted_result"), "TASK08_RESULT"))
    task09 = dict(_mapping(by_id["TASK09_PUMPSWAP"]["payload"], "TASK09"))
    accepted09 = dict(_mapping(task09.get("accepted_result"), "TASK09_RESULT"))
    task21 = dict(_mapping(by_id["TASK21_SAMPLE"]["payload"], "TASK21"))
    population = dict(_mapping(task21.get("population"), "TASK21_POP"))
    eligibility = dict(_mapping(task21.get("task22_eligibility"), "TASK21_SPLIT"))
    a24 = dict(_mapping(by_id["TASK30_A24"]["payload"], "A24"))
    limitations = [
        str(item) for item in _sequence(a24.get("limitations"), "A24_LIMITS")
    ]
    inventory = {
        "task08": {
            "create_events": int(accepted08.get("create_events") or 0),
            "decoded_events": int(accepted08.get("decoded_events") or 0),
            "coverage_disposition": accepted08.get("coverage_disposition"),
            "migration_at": "MISSING_UNKNOWN",
            "contiguous_post_migration_universe": False,
        },
        "task09": {
            "coverage_disposition": accepted09.get("coverage_disposition"),
            "decoded_events": int(accepted09.get("decoded_events") or 0),
            "migration_at": "MISSING_UNKNOWN",
            "contiguous_post_migration_universe": False,
        },
        "task21": {
            "complete_members": int(population.get("complete_members") or 0),
            "complete_member_clusters": int(
                population.get("complete_member_clusters") or 0
            ),
            "outcomes_opened": bool(eligibility.get("outcomes_opened")),
            "holdout_protected": True,
            "lifecycle_clocks": "MISSING_UNKNOWN",
        },
        "task30_a24": {
            "pools": 1,
            "days": 1,
            "transaction_count": int(
                dict(_mapping(a24.get("identity"), "A24_ID")).get(
                    "transaction_count"
                )
                or 0
            ),
            "post_migration_continuation": "MISSING_UNKNOWN",
            "migration_at": "MISSING_UNKNOWN",
            "limitations": limitations,
        },
    }
    _integrity(
        eligibility.get("outcomes_opened") is False,
        "TASK21_OUTCOMES_OPENED",
    )
    _integrity(
        "NO_POST_MIGRATION_CONTINUATION_PROOF" in limitations,
        "A24_MIGRATION_CONTEXT_CLAIMED",
    )
    reconstructable = (
        inventory["task08"]["create_events"] > 0
        and inventory["task08"]["contiguous_post_migration_universe"]
        and inventory["task08"]["migration_at"] != "MISSING_UNKNOWN"
    )
    return {
        "sources": inventory,
        "migration_clock_reconstructable": reconstructable,
        "running_peak_with_migration_anchor": False,
        "contiguous_outcome_independent_universe": False,
        "adopted_routes": [
            "TASK08_LIFECYCLE",
            "TASK09_PUMPSWAP",
            "TASK21_SAMPLE",
            "TASK30_A24",
        ],
        "new_collector": False,
        "provider_calls": 0,
    }


class OutcomeGuard:
    """Fail closed if outcome values are read before the trial is registered."""

    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = [dict(row) for row in rows]
        self._allowed = False
        self._reads = 0

    def register_trial(self) -> None:
        self._allowed = True

    @property
    def registered(self) -> bool:
        return self._allowed

    def identities(self) -> list[str]:
        return [str(row.get("row_id")) for row in self._rows]

    def selection_fields(self) -> list[dict[str, Any]]:
        fields = []
        for row in self._rows:
            fields.append(
                {
                    "row_id": row.get("row_id"),
                    "pool_id": row.get("pool_id"),
                    "deployer_id": row.get("deployer_id"),
                    "day_id": row.get("day_id"),
                    "migration_at": row.get("migration_at"),
                    "decision_time": row.get("decision_time"),
                }
            )
        return fields

    def inspect(self) -> list[dict[str, Any]]:
        if not self._allowed:
            raise H11Error("OUTCOME_INSPECTION_BEFORE_TRIAL")
        self._reads += 1
        return [dict(row) for row in self._rows]


def parse_epoch(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str) and value:
        if value.endswith("Z"):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(parsed.timestamp())
        if value.isdigit():
            return int(value)
    return None


def assign_bin(seconds: int | None, edges: Sequence[int]) -> str:
    if seconds is None:
        return "MISSING_UNKNOWN"
    if seconds < 0:
        return "MISSING_UNKNOWN"
    for index, upper in enumerate(edges):
        if seconds < upper:
            return f"B{index}"
    return f"B{len(edges)}"


def session_bin(decision_epoch: int | None) -> str:
    if decision_epoch is None:
        return "MISSING_UNKNOWN"
    hour = datetime.fromtimestamp(decision_epoch, tz=UTC).hour
    if hour < 8:
        return "ASIA"
    if hour < 16:
        return "EU"
    return "US"


def utc_coarse_bin(decision_epoch: int | None) -> str:
    if decision_epoch is None:
        return "MISSING_UNKNOWN"
    hour = datetime.fromtimestamp(decision_epoch, tz=UTC).hour
    return f"UTC_{hour // 6 * 6:02d}"


def running_peak_at_decision(
    events: Sequence[Mapping[str, Any]], decision_epoch: int
) -> tuple[int | None, str]:
    peak_value: float | None = None
    peak_at: int | None = None
    for event in events:
        event_at = parse_epoch(event.get("event_at"))
        if event_at is None or event_at > decision_epoch:
            continue
        raw = event.get("price")
        if raw is None:
            continue
        try:
            price = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(price):
            continue
        if peak_value is None or price > peak_value:
            peak_value = price
            peak_at = event_at
    if peak_at is None:
        return None, "MISSING_UNKNOWN"
    return peak_at, "OBSERVED"


def decision_time_features(
    row: Mapping[str, Any], protocol: Mapping[str, Any]
) -> dict[str, Any]:
    decision_epoch = parse_epoch(row.get("decision_time"))
    migration_epoch = parse_epoch(row.get("migration_at"))
    missingness: list[str] = []
    if decision_epoch is None:
        missingness.append("DECISION_TIME_MISSING")
    time_since_migration = None
    migration_state = "MISSING_UNKNOWN"
    if decision_epoch is not None and migration_epoch is not None:
        time_since_migration = decision_epoch - migration_epoch
        migration_state = "OBSERVED"
    else:
        missingness.append("MIGRATION_AT_MISSING")
    peak_age = None
    peak_state = "MISSING_UNKNOWN"
    if decision_epoch is not None:
        events = list(_sequence(row.get("events") or [], "EVENTS"))
        peak_at, peak_state = running_peak_at_decision(events, decision_epoch)
        if peak_at is not None:
            peak_age = decision_epoch - peak_at
        else:
            missingness.append("RUNNING_PEAK_MISSING")
    else:
        missingness.append("RUNNING_PEAK_MISSING")
    migration_edges = [
        int(item)
        for item in _sequence(
            protocol.get("time_since_migration_bin_edges_seconds"),
            "MIGRATION_EDGES",
        )
    ]
    peak_edges = [
        int(item)
        for item in _sequence(
            protocol.get("peak_age_bin_edges_seconds"),
            "PEAK_EDGES",
        )
    ]
    coerced = row.get("time_since_migration") == 0 and migration_epoch is None
    _require(not coerced, "MISSING_TO_ZERO")
    return {
        "time_since_migration": time_since_migration,
        "time_since_migration_state": migration_state,
        "time_since_migration_bin": assign_bin(time_since_migration, migration_edges),
        "time_since_decision_time_running_peak": peak_age,
        "peak_state": peak_state,
        "peak_age_bin": assign_bin(peak_age, peak_edges),
        "session_bin": session_bin(decision_epoch),
        "utc_bin": utc_coarse_bin(decision_epoch),
        "missingness": missingness,
    }


def freeze_cohort(
    rows: Sequence[Mapping[str, Any]], protocol: Mapping[str, Any]
) -> dict[str, Any]:
    del protocol
    identities = []
    for row in rows:
        item = dict(_mapping(row, "COHORT_ROW"))
        identities.append(
            {
                "row_id": _text(item.get("row_id"), "ROW_ID"),
                "pool_id": _text(item.get("pool_id"), "POOL_ID"),
                "deployer_id": str(item.get("deployer_id") or "MISSING_UNKNOWN"),
                "day_id": str(item.get("day_id") or "MISSING_UNKNOWN"),
                "migration_at": item.get("migration_at"),
                "decision_time": item.get("decision_time"),
            }
        )
    identities.sort(key=lambda item: (str(item["migration_at"]), str(item["row_id"])))
    return {
        "row_ids": [item["row_id"] for item in identities],
        "fingerprint": sha256_bytes(canonical_json(identities)),
        "n": len(identities),
        "pools": sorted({item["pool_id"] for item in identities}),
        "days": sorted({item["day_id"] for item in identities}),
        "deployers": sorted({item["deployer_id"] for item in identities}),
    }


def chronological_group_split(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    first_key: dict[str, str] = {}
    for row in rows:
        item = dict(row)
        group_id = str(item.get("deployer_id") or item.get("pool_id"))
        grouped[group_id].append(item)
        migration = str(item.get("migration_at") or item.get("decision_time") or "")
        previous = first_key.get(group_id)
        if previous is None or migration < previous:
            first_key[group_id] = migration
    ordered = sorted(grouped, key=lambda key: (first_key[key], key))
    cut = max(1, len(ordered) // 2) if len(ordered) > 1 else 1
    early_keys = set(ordered[:cut])
    early = [row for key in ordered[:cut] for row in grouped[key]]
    late = [row for key in ordered[cut:] for row in grouped[key]]
    if not late:
        late = list(early)
        early_keys = set(ordered)
    return early, late


def _continuation(row: Mapping[str, Any]) -> int | None:
    outcome = row.get("outcome")
    if outcome in {None, "MISSING_UNKNOWN", "INACTIVE_TYPED_GAP"}:
        return None
    if outcome == "CONTINUATION":
        return 1
    if outcome == "FAST_DEATH":
        return 0
    return None


def g_test_incremental(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    usable: list[dict[str, Any]] = []
    typed_missing = 0
    for row in rows:
        item = dict(row)
        y = _continuation(item)
        session = str(item.get("session_bin") or "MISSING_UNKNOWN")
        clock = str(item.get("time_since_migration_bin") or "MISSING_UNKNOWN")
        if (
            y is None
            or session == "MISSING_UNKNOWN"
            or clock == "MISSING_UNKNOWN"
            or item.get("time_since_migration_state") == "MISSING_UNKNOWN"
        ):
            typed_missing += 1
            continue
        usable.append({"y": y, "session": session, "clock": clock, **item})
    if len(usable) < 4:
        return {
            "g_stat": None,
            "direction": "MISSING_UNKNOWN",
            "usable_n": len(usable),
            "typed_missing": typed_missing,
            "max_unit_share": None,
        }

    def _ll(table: Mapping[tuple[str, int], int], margins: Mapping[str, int]) -> float:
        total = 0.0
        for (key, y), count in table.items():
            n = margins[key]
            if n <= 0 or count <= 0:
                continue
            p = count / n
            total += count * math.log(p)
        return total

    nested: dict[tuple[str, str, int], int] = defaultdict(int)
    session_y: dict[tuple[str, int], int] = defaultdict(int)
    session_n: dict[str, int] = defaultdict(int)
    nested_n: dict[tuple[str, str], int] = defaultdict(int)
    early_clock_cont = 0
    early_clock_n = 0
    late_clock_cont = 0
    late_clock_n = 0
    unit_counts: dict[str, int] = defaultdict(int)
    for item in usable:
        session = str(item["session"])
        clock = str(item["clock"])
        y = int(item["y"])
        nested[(session, clock, y)] += 1
        session_y[(session, y)] += 1
        session_n[session] += 1
        nested_n[(session, clock)] += 1
        unit = str(item.get("pool_id") or item.get("row_id"))
        unit_counts[unit] += 1
        if clock in {"B0", "B1"}:
            early_clock_cont += y
            early_clock_n += 1
        else:
            late_clock_cont += y
            late_clock_n += 1
    ll1 = 0.0
    for (session, clock), n in nested_n.items():
        for y in (0, 1):
            count = nested.get((session, clock, y), 0)
            if count > 0 and n > 0:
                ll1 += count * math.log(count / n)
    ll0 = _ll(session_y, session_n)
    g_stat = 2.0 * (ll1 - ll0)
    early_rate = early_clock_cont / early_clock_n if early_clock_n else None
    late_rate = late_clock_cont / late_clock_n if late_clock_n else None
    if early_rate is None or late_rate is None:
        direction = "MISSING_UNKNOWN"
    elif early_rate > late_rate:
        direction = "EARLY_CLOCK_MORE_CONTINUATION"
    elif early_rate < late_rate:
        direction = "LATE_CLOCK_MORE_CONTINUATION"
    else:
        direction = "FLAT"
    total = sum(unit_counts.values())
    max_share = max(unit_counts.values()) / total if total else None
    return {
        "g_stat": g_stat,
        "direction": direction,
        "usable_n": len(usable),
        "typed_missing": typed_missing,
        "max_unit_share": max_share,
        "early_rate": early_rate,
        "late_rate": late_rate,
    }


def classify_verdict(
    *,
    inventory: Mapping[str, Any],
    cohort: Mapping[str, Any],
    protocol: Mapping[str, Any],
    folds: Sequence[Mapping[str, Any]],
) -> str:
    if not inventory.get("migration_clock_reconstructable"):
        if cohort["n"] == 0:
            return "HISTORICAL_ROUTE_INADEQUATE_REPLAN"
    floors = dict(_mapping(protocol.get("minimum_independent_units"), "FLOORS"))
    min_raw = int(protocol.get("minimum_raw_n") or 0)
    if (
        cohort["n"] < min_raw
        or len(cohort["pools"]) < int(floors.get("pools") or 0)
        or len(cohort["days"]) < int(floors.get("days") or 0)
        or len(cohort["deployers"]) < int(floors.get("deployers") or 0)
    ):
        if cohort["n"] == 0 or not inventory.get("migration_clock_reconstructable"):
            return "HISTORICAL_ROUTE_INADEQUATE_REPLAN"
        return "H11_SCREEN_INCONCLUSIVE_DATA_SCALE"
    threshold = float(protocol.get("incremental_g_threshold") or 0)
    max_share = float(protocol.get("max_single_unit_share") or 1)
    if len(folds) != 2:
        return "H11_SCREEN_INCONCLUSIVE_DATA_SCALE"
    stats = list(folds)
    if any(item.get("g_stat") is None for item in stats):
        return "H11_SCREEN_INCONCLUSIVE_DATA_SCALE"
    directions = {str(item.get("direction")) for item in stats}
    strong = all(float(item["g_stat"]) > threshold for item in stats)
    concentrated = any(
        item.get("max_unit_share") is not None
        and float(item["max_unit_share"]) > max_share
        for item in stats
    )
    stable_direction = len(directions) == 1 and "FLAT" not in directions
    if (
        strong
        and stable_direction
        and not concentrated
        and "MISSING_UNKNOWN" not in directions
    ):
        return "H11_SCREEN_POSITIVE_EARNS_PROSPECTIVE_CONFIRMATION"
    return "H11_SCREEN_NEGATIVE_DEPRIORITIZE_OR_CLOSE"


def register_trial(protocol_hash: str, cohort_fingerprint: str) -> dict[str, Any]:
    return {
        "record_kind": "trial",
        "record_id": TRIAL_ID,
        "status": "RECORDED",
        "created_at": "2026-08-15T17:30:00Z",
        "evidence_asset_ids": ["EVIDENCE-T36-RC002-H11-LIFECYCLE-CLOCK-001"],
        "hypothesis_id": HYPOTHESIS_ID,
        "research_cycle_id": RESEARCH_CYCLE_ID,
        "protocol_sha256": protocol_hash,
        "cohort_fingerprint": cohort_fingerprint,
        "outcome": "PENDING",
        "live_PIT_claim": False,
        "execution_claim": False,
    }


def map_trial_outcome(verdict: str) -> str:
    if verdict == "H11_SCREEN_POSITIVE_EARNS_PROSPECTIVE_CONFIRMATION":
        return "PASS"
    if verdict == "H11_SCREEN_NEGATIVE_DEPRIORITIZE_OR_CLOSE":
        return "FAIL"
    return "INCONCLUSIVE"


def execute_screen(
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    cohort_rows: Sequence[Mapping[str, Any]] | None = None,
    inspect_outcomes: bool = True,
) -> dict[str, Any]:
    protocol = dict(_mapping(policy.get("screen_protocol"), "PROTOCOL_INVALID"))
    protocol_hash = protocol_fingerprint(policy)
    freeze = bind_rc001_freeze(repo_root, policy)
    holdout = bind_holdout(repo_root, policy)
    sources = bind_historical_sources(repo_root, policy)
    inventory = inventory_historical_routes(sources)
    live_universe = cohort_rows is None
    if live_universe:
        rows: list[dict[str, Any]] = []
    else:
        rows = [dict(item) for item in cohort_rows]
    guard = OutcomeGuard(rows)
    frozen = freeze_cohort(guard.selection_fields(), protocol)
    trial = register_trial(protocol_hash, str(frozen["fingerprint"]))
    guard.register_trial()
    if not inspect_outcomes:
        return {
            "schema": RESULT_SCHEMA,
            "schema_version": "1.0",
            "atom_id": ATOM_ID,
            "research_cycle_id": RESEARCH_CYCLE_ID,
            "protocol_sha256": protocol_hash,
            "trial": trial,
            "cohort": frozen,
            "inventory": inventory,
            "rc001_freeze": freeze,
            "holdout": holdout,
            "terminal_decision": None,
            "live_universe": live_universe,
        }
    inspected = guard.inspect()
    featured = []
    for row in inspected:
        features = decision_time_features(row, protocol)
        featured.append({**row, **features})
    early, late = chronological_group_split(featured) if featured else ([], [])
    fold_stats = [g_test_incremental(early), g_test_incremental(late)] if featured else []
    if live_universe:
        verdict = "HISTORICAL_ROUTE_INADEQUATE_REPLAN"
    else:
        verdict = classify_verdict(
            inventory={
                **inventory,
                "migration_clock_reconstructable": True,
            },
            cohort=frozen,
            protocol=protocol,
            folds=fold_stats,
        )
    trial = dict(trial)
    trial["outcome"] = map_trial_outcome(verdict)
    return {
        "schema": RESULT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "research_cycle_id": RESEARCH_CYCLE_ID,
        "family": FAMILY,
        "stage": "EXPLORATORY_MECHANISM_SCREEN",
        "data_semantics": "RETROSPECTIVE_EVENT_TIME_RECONSTRUCTION",
        "protocol_sha256": protocol_hash,
        "terminal_decision": verdict,
        "trial": trial,
        "cohort": frozen,
        "fold_stats": fold_stats,
        "inventory": inventory,
        "rc001_freeze": freeze,
        "holdout": holdout,
        "live_universe": live_universe,
        "live_PIT_claim": False,
        "execution_claim": False,
        "alpha_claim": False,
        "rc001_mutated": False,
        "holdout_consumed": False,
        "remaining_rc001_deprioritized": True,
        "side_effects": {
            "provider_requests": 0,
            "credential_reads": 0,
            "retries": 0,
            "fallbacks": 0,
            "cash_spend_usd_cents": 0,
            "wallet_signer_transaction_actions": 0,
        },
        "non_claims": [
            "NO_LIVE_PIT_CLAIM",
            "NO_EXECUTION_CLAIM",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_RC001_MUTATION",
            "NO_HOLDOUT_CONSUMPTION",
            "NO_AVAILABLE_TO_STRATEGY_AT_CONVERSION",
        ],
    }


def format_owner_readout(result: Mapping[str, Any]) -> str:
    verdict = str(result.get("terminal_decision"))
    inventory = dict(_mapping(result.get("inventory"), "INVENTORY"))
    cohort = dict(_mapping(result.get("cohort"), "COHORT"))
    trial = dict(_mapping(result.get("trial"), "TRIAL"))
    lines = [
        "# TASK-36 RC002 — экран H11 lifecycle-clock",
        "",
        f"**Терминальное решение:** `{verdict}`",
        "",
        "Это exploratory mechanism screen с семантикой",
        "`RETROSPECTIVE_EVENT_TIME_RECONSTRUCTION`. Это не live PIT,",
        "не execution, не альфа и не cashflow.",
        "",
        "## Что проверено",
        "",
        f"- family: `{FAMILY}`",
        f"- research cycle: `{RESEARCH_CYCLE_ID}` (task-owned, не RC001)",
        f"- trial: `{trial.get('record_id')}` outcome `{trial.get('outcome')}`",
        f"- protocol SHA-256: `{result.get('protocol_sha256')}`",
        f"- live universe N: `{cohort.get('n')}`",
        f"- pools/days/deployers: `{len(list(cohort.get('pools') or []))}` / "
        f"`{len(list(cohort.get('days') or []))}` / "
        f"`{len(list(cohort.get('deployers') or []))}`",
        f"- migration clock reconstructable: `{inventory.get('migration_clock_reconstructable')}`",
        "- RC001 definitions unchanged; remaining H13/H02 deprioritized",
        "- RC001 holdout not consumed",
        "",
        "## Исторические маршруты",
        "",
        "- TASK-08: CreateEvent=0, coverage blocker, migration_at MISSING_UNKNOWN",
        "- TASK-09: bounded post-migration touch, не contiguous universe",
        "- TASK-21: 5 complete members, outcomes unopened, holdout protected",
        "- TASK-30 A24: 1 pool-day, NO_POST_MIGRATION_CONTINUATION_PROOF",
        "",
        "## Что этим атомом не делается",
        "",
        "- live PIT / available_to_strategy_at",
        "- H13 или H02 trial",
        "- prospective collector",
        "- RC001 mutation",
        "- wallet, signer, tx, paid plan, deployment",
        "",
        "Это не product DONE, не альфа и не cashflow.",
    ]
    return "\n".join(lines) + "\n"
