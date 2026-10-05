"""OPPORTUNITY_EPISODES domain owner.

One small unit for the episode schedule document, the versioned point/clock
resolver, the metadata-only protection gate, closed-frame selection,
deterministic tickets/quotas and admission identity. It owns no store, no
transport and no evaluator; producer, release and Forge consumers call it.
Contract: ``docs/contracts/opportunity_episodes_jupiter_v1.md``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import jsonschema

from solana_alpha_lab.factory.observation_schedule import (
    ObservationScheduleError,
    canonical_sha256,
    parse_utc,
    render_utc,
    schedule_sha256,
)
from solana_alpha_lab.factory.tokens_v2_typed_projection import (
    STATE_OBSERVED,
    project_tokens_v2_field,
)

EPISODE_SCHEDULE_SCHEMA = "smial.opportunity-episode-schedule"
EPISODE_SCHEDULE_SCHEMA_VERSION = "1.0"
EPISODE_SCHEDULE_SCHEMA_RELATIVE = "catalog/schemas/opportunity_episode_schedule_v1.schema.json"
SCHEDULE_CONTRACT = "OPPORTUNITY_EPISODE_SCHEDULE_V1"
POPULATION = "OPPORTUNITY_EPISODES"
POPULATION_CONTRACT = "OPPORTUNITY_EPISODES_V1"
ANCHOR_KIND = "NOMINATION_T0"
LOGICAL_DATASET_ID = "DATASET-OPPORTUNITY-EPISODES-DISCOVERY-CORPUS-001"
COLLECTION = "OPPORTUNITY_EPISODES"
COLLECTION_KIND = "JUPITER_CORE_OPPORTUNITY_EPISODES_V1"
NOMINATION_PRIMITIVE = "PRIM-JUPITER-TOKENS-V2-CATEGORY-NOMINATION-001"
SEARCH_PRIMITIVE = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
WITNESS_POINT = "E0"
TICKET_VERSION = "OPPORTUNITY_EPISODE_TICKET_V1"
EPISODE_ID_VERSION = "OPPORTUNITY_EPISODE_ID_V1"
LINEAGE_VERSION = "OPPORTUNITY_EPISODE_LINEAGE_V1"
FRAME_VERSION = "OPPORTUNITY_EPISODE_FRAME_V1"
PROTECTION_VERSION = "OPPORTUNITY_EPISODE_PROTECTION_V1"
ASSIGNMENT_SCHEMA = "smial.protected-identity-assignment"
ASSIGNMENT_DIR = "protection/assignments"
TIME_FEATURE_CLOCK = "FIRST_RELIABLE_AVAILABLE_AT"
# Ordinary Forge collection scope. The owner focus carries it so every
# search-key recomputation from the stored focus keeps the same scope.
EPISODE_FOCUS_PREFIX = "OPPORTUNITY_EPISODES:"
ROUNDS_PER_DAY = 96
MAX_QUERY_POINTS = 8

PRICE = "FIELD-USD-PRICE-001"
LIQUIDITY = "FIELD-LIQUIDITY-USD-001"
HOLDER_COUNT = "FIELD-HOLDER-COUNT-001"
MINT_FIELD = "FIELD-TOKEN-MINT-001"
CORE_FIELDS = (PRICE, LIQUIDITY, HOLDER_COUNT)

# Frozen V1 grid. A different grid is a new schedule contract version.
V1_DENSE_STEP = 300
V1_DENSE_UNTIL = 21600
V1_HOURLY_STEP = 3600
V1_HORIZON = 259200
V1_SOURCES = (
    ("toporganicscore_5m", "toporganicscore", "5m"),
    ("toptraded_5m", "toptraded", "5m"),
    ("toptrending_5m", "toptrending", "5m"),
)

ALLOW = "ALLOW"
DENY_PROTECTED = "DENY_PROTECTED"
UNRESOLVED_SCOPE = "UNRESOLVED_SCOPE"

FRAME_PASS = "PASS"
FRAME_PROTECTED = "PROTECTED"
FRAME_UNRESOLVED = "PROTECTION_UNRESOLVED"
FRAME_ASSET_EXCLUDED = "ASSET_EXCLUDED"
FRAME_CORE_UNUSABLE = "CORE_UNUSABLE"


class OpportunityEpisodeError(ValueError):
    """Typed fail-closed episode contract failure."""


# --------------------------------------------------------------------------
# Schedule document


def is_episode_schedule(document: object) -> bool:
    return isinstance(document, Mapping) and document.get("schema") == EPISODE_SCHEDULE_SCHEMA


def collection_for_focus(owner_focus: object) -> str | None:
    """OPPORTUNITY_EPISODES when the focus names that collection, else legacy."""

    text = str(owner_focus or "")
    return COLLECTION if text.startswith(EPISODE_FOCUS_PREFIX) else None


def episode_focus(owner_focus: str) -> str:
    text = str(owner_focus or "").strip()
    return text if text.startswith(EPISODE_FOCUS_PREFIX) else f"{EPISODE_FOCUS_PREFIX}{text}"


def v1_offsets() -> tuple[int, ...]:
    dense = range(V1_DENSE_STEP, V1_DENSE_UNTIL + 1, V1_DENSE_STEP)
    hourly = range(V1_DENSE_UNTIL + V1_HOURLY_STEP, V1_HORIZON + 1, V1_HOURLY_STEP)
    return (0, *dense, *hourly)


def point_id_for_offset(offset: int) -> str:
    return f"E{int(offset)}"


def point_offset(point_id: object) -> int:
    text = str(point_id or "")
    if not text.startswith("E") or not text[1:].isdigit():
        raise OpportunityEpisodeError("EPISODE_POINT_UNKNOWN")
    offset = int(text[1:])
    if point_id_for_offset(offset) != text or offset not in _V1_OFFSET_SET:
        raise OpportunityEpisodeError("EPISODE_POINT_UNKNOWN")
    return offset


_V1_OFFSET_SET = frozenset(v1_offsets())


def episode_point_ids() -> tuple[str, ...]:
    return tuple(point_id_for_offset(item) for item in v1_offsets())


def _load_schema(root: Path) -> dict[str, Any]:
    try:
        loaded = json.loads((root / EPISODE_SCHEDULE_SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_SCHEMA_MISSING") from exc
    if not isinstance(loaded, dict):
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_SCHEMA_INVALID")
    return loaded


def _decimal(value: object, code: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ObservationScheduleError(code) from exc
    if not number.is_finite():
        raise ObservationScheduleError(code)
    return number


def validate_episode_schedule_semantics(document: Mapping[str, Any]) -> None:
    """Semantic checks beyond JSON schema. Legacy X/Y rules never apply."""

    from solana_alpha_lab.factory.observation_schedule import _reject_unsafe

    _reject_unsafe(document)
    population = document["population"]
    expected_population = {
        "population": POPULATION,
        "population_contract": POPULATION_CONTRACT,
        "anchor_kind": ANCHOR_KIND,
        "logical_dataset_id": LOGICAL_DATASET_ID,
    }
    for key, value in expected_population.items():
        if population.get(key) != value:
            raise ObservationScheduleError("EPISODE_POPULATION_CONTRACT_INVALID")
    if document.get("collection_kind") != COLLECTION_KIND:
        raise ObservationScheduleError("EPISODE_POPULATION_CONTRACT_INVALID")
    nomination = document["nomination"]
    if nomination["primitive_id"] != NOMINATION_PRIMITIVE:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    sources = [
        (str(item["source_id"]), str(item["category"]), str(item["interval"]))
        for item in nomination["sources"]
    ]
    if tuple(sources) != V1_SOURCES:
        raise ObservationScheduleError("EPISODE_SOURCE_SET_INVALID")
    for item in nomination["sources"]:
        if not 1 <= int(item["limit"]) <= 100:
            raise ObservationScheduleError("EPISODE_SOURCE_SET_INVALID")
    if int(nomination["round_period_seconds"]) != 900:
        raise ObservationScheduleError("EPISODE_ROUND_INVALID")
    if not 0 < int(nomination["round_slack_seconds"]) < 900:
        raise ObservationScheduleError("EPISODE_ROUND_INVALID")
    if not 0 < int(nomination["witness_max_age_seconds"]) <= 900:
        raise ObservationScheduleError("EPISODE_ROUND_INVALID")
    floor = document["capture_floor"]
    low = _decimal(floor["liquidity_usd_min"], "EPISODE_CAPTURE_FLOOR_INVALID")
    high = _decimal(floor["liquidity_usd_max"], "EPISODE_CAPTURE_FLOOR_INVALID")
    if not (0 < low <= high) or int(floor["holders_min"]) < 0:
        raise ObservationScheduleError("EPISODE_CAPTURE_FLOOR_INVALID")
    if floor.get("price_usd_positive") is not True:
        raise ObservationScheduleError("EPISODE_CAPTURE_FLOOR_INVALID")
    sampling = document["sampling"]
    if sampling["cycle"] != "WEEKLY_MONDAY_UTC":
        raise ObservationScheduleError("EPISODE_SAMPLING_INVALID")
    ceiling = int(sampling["daily_normal_ceiling"])
    if not 1 <= ceiling <= 100:
        raise ObservationScheduleError("EPISODE_SAMPLING_INVALID")
    if int(sampling["rolling_24h_max"]) > ceiling:
        raise ObservationScheduleError("EPISODE_SAMPLING_INVALID")
    if int(sampling["max_episodes_per_mint_per_cycle"]) != 1 or int(
        sampling["max_active_per_mint"]
    ) != 1:
        raise ObservationScheduleError("EPISODE_SAMPLING_INVALID")
    if int(sampling["active_episode_cap"]) < 1:
        raise ObservationScheduleError("EPISODE_SAMPLING_INVALID")
    schedule = document["observation_schedule"]
    expected_schedule = {
        "schedule_contract": SCHEDULE_CONTRACT,
        "primitive_id": SEARCH_PRIMITIVE,
        "dense_step_seconds": V1_DENSE_STEP,
        "dense_until_seconds": V1_DENSE_UNTIL,
        "hourly_step_seconds": V1_HOURLY_STEP,
        "horizon_seconds": V1_HORIZON,
    }
    for key, value in expected_schedule.items():
        if schedule.get(key) != value:
            raise ObservationScheduleError("EPISODE_SCHEDULE_GRID_INVALID")
    dispatch = int(schedule["dispatch_window_seconds"])
    grace = int(schedule["availability_grace_seconds"])
    if not 0 < dispatch <= grace <= V1_DENSE_STEP:
        raise ObservationScheduleError("EPISODE_SCHEDULE_GRID_INVALID")
    if not 1 <= int(schedule["max_batch_size"]) <= 100:
        raise ObservationScheduleError("EPISODE_SCHEDULE_GRID_INVALID")
    protection = document["protection"]
    if not protection.get("assignment_sources"):
        raise ObservationScheduleError("EPISODE_PROTECTION_SOURCES_REQUIRED")
    activation = document["activation"]
    if parse_utc(activation["stops_admitting_at"]) <= parse_utc(activation["starts_at"]):
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    budgets = document["budgets"]
    if (
        str(budgets["cash_usd_max"]) != "0"
        or budgets["retry"] is not False
        or budgets["fallback"] is not False
    ):
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    if int(budgets["min_provider_pace_seconds"]) < 3:
        raise ObservationScheduleError("CHANGE_LANE_SAFETY_CONTRACT_GAP")
    required_retention = math.ceil((V1_HORIZON + grace) / 86400) + 7
    if int(document["retention"]["raw_retention_days"]) < required_retention:
        raise ObservationScheduleError("BLOCKED_BUDGET")


def validate_episode_schedule(document: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    if not is_episode_schedule(document):
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_INVALID")
    try:
        jsonschema.validate(dict(document), _load_schema(root))
    except jsonschema.ValidationError as exc:
        raise ObservationScheduleError("OBSERVATION_SCHEDULE_SCHEMA_INVALID") from exc
    validate_episode_schedule_semantics(document)
    payload = dict(document)
    digest = schedule_sha256(payload)
    existing = payload.get("schedule_sha256")
    if existing is not None and existing != digest:
        raise ObservationScheduleError("INVALID_IDENTITY")
    payload["schedule_sha256"] = digest
    return payload


def collection_lineage_id(document: Mapping[str, Any]) -> str:
    """Ticket/cap lineage. Capture-profile edits never reset tickets or caps."""

    return canonical_sha256(
        {
            "version": LINEAGE_VERSION,
            "collection_kind": document["collection_kind"],
            "logical_dataset_id": document["population"]["logical_dataset_id"],
            "seed": document["sampling"]["seed"],
        }
    )


def episode_provider_primitives(document: Mapping[str, Any]) -> list[str]:
    return sorted(
        {str(document["nomination"]["primitive_id"]), str(document["observation_schedule"]["primitive_id"])}
    )


def episode_minimum_expiry(document: Mapping[str, Any]) -> datetime:
    grace = int(document["observation_schedule"]["availability_grace_seconds"])
    # Last admission + 72h, rounded to the hourly grid, plus availability grace.
    return parse_utc(document["activation"]["stops_admitting_at"]) + timedelta(
        seconds=V1_HORIZON + V1_HOURLY_STEP + grace
    )


def episode_cohort_family_key(document: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            "collection_lineage_id": collection_lineage_id(document),
            "nomination": document["nomination"],
            "capture_floor": document["capture_floor"],
            "observation_schedule": document["observation_schedule"],
        }
    )


def schedule_binding(document: Mapping[str, Any]) -> dict[str, Any]:
    """Portable clock binding frozen into releases and query bindings."""

    schedule = document["observation_schedule"]
    return {
        "schedule_contract": SCHEDULE_CONTRACT,
        "schedule_sha256": str(document.get("schedule_sha256") or schedule_sha256(document)),
        "dense_step_seconds": int(schedule["dense_step_seconds"]),
        "dense_until_seconds": int(schedule["dense_until_seconds"]),
        "hourly_step_seconds": int(schedule["hourly_step_seconds"]),
        "horizon_seconds": int(schedule["horizon_seconds"]),
        "dispatch_window_seconds": int(schedule["dispatch_window_seconds"]),
        "availability_grace_seconds": int(schedule["availability_grace_seconds"]),
        "witness_max_age_seconds": int(document["nomination"]["witness_max_age_seconds"]),
    }


# --------------------------------------------------------------------------
# Point / clock resolver


@dataclass(frozen=True)
class PointWindow:
    point_id: str
    offset_seconds: int
    nominal_due: datetime
    assigned_at: datetime | None
    request_not_before: datetime
    dispatch_deadline: datetime | None
    availability_deadline: datetime


def _ceil_grid(value: datetime, step: int) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    seconds = (value - epoch).total_seconds()
    whole = math.ceil(seconds / step) * step
    return epoch + timedelta(seconds=whole)


def require_binding(binding: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(binding, Mapping) or binding.get("schedule_contract") != SCHEDULE_CONTRACT:
        raise OpportunityEpisodeError("EPISODE_SCHEDULE_BINDING_UNKNOWN")
    for key, expected in (
        ("dense_step_seconds", V1_DENSE_STEP),
        ("dense_until_seconds", V1_DENSE_UNTIL),
        ("hourly_step_seconds", V1_HOURLY_STEP),
        ("horizon_seconds", V1_HORIZON),
    ):
        if binding.get(key) != expected:
            raise OpportunityEpisodeError("EPISODE_SCHEDULE_BINDING_UNKNOWN")
    for key in ("dispatch_window_seconds", "availability_grace_seconds", "witness_max_age_seconds"):
        value = binding.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise OpportunityEpisodeError("EPISODE_SCHEDULE_BINDING_UNKNOWN")
    return binding


def resolve_point(binding: Mapping[str, Any], t0: datetime, point: str) -> PointWindow:
    """The one versioned point/clock resolver for every episode consumer."""

    require_binding(binding)
    if t0.tzinfo is None:
        raise OpportunityEpisodeError("TIMESTAMP_INVALID")
    t0 = t0.astimezone(UTC)
    offset = point_offset(point)
    if offset == 0:
        max_age = int(binding["witness_max_age_seconds"])
        return PointWindow(
            point_id=point,
            offset_seconds=0,
            nominal_due=t0,
            assigned_at=None,
            request_not_before=t0 - timedelta(seconds=max_age),
            dispatch_deadline=None,
            availability_deadline=t0,
        )
    nominal = t0 + timedelta(seconds=offset)
    step = (
        int(binding["dense_step_seconds"])
        if offset <= int(binding["dense_until_seconds"])
        else int(binding["hourly_step_seconds"])
    )
    assigned = _ceil_grid(nominal, step)
    return PointWindow(
        point_id=point,
        offset_seconds=offset,
        nominal_due=nominal,
        assigned_at=assigned,
        request_not_before=assigned,
        dispatch_deadline=assigned + timedelta(seconds=int(binding["dispatch_window_seconds"])),
        availability_deadline=assigned + timedelta(seconds=int(binding["availability_grace_seconds"])),
    )


def final_availability_deadline(binding: Mapping[str, Any], t0: datetime) -> datetime:
    return resolve_point(binding, t0, point_id_for_offset(V1_HORIZON)).availability_deadline


# --------------------------------------------------------------------------
# Cycles, tickets, identities, cohorts


def cycle_start(instant: datetime) -> datetime:
    instant = instant.astimezone(UTC)
    day = datetime(instant.year, instant.month, instant.day, tzinfo=UTC)
    return day - timedelta(days=day.weekday())


def round_start(instant: datetime, period: int = 900) -> datetime:
    instant = instant.astimezone(UTC)
    day = datetime(instant.year, instant.month, instant.day, tzinfo=UTC)
    elapsed = int((instant - day).total_seconds())
    return day + timedelta(seconds=(elapsed // period) * period)


def round_index(instant: datetime, period: int = 900) -> int:
    start = round_start(instant, period)
    day = datetime(start.year, start.month, start.day, tzinfo=UTC)
    return int((start - day).total_seconds()) // period


def round_id(activation_id: str, start: datetime) -> str:
    return f"ROUND-{activation_id}-{start.strftime('%Y%m%dT%H%M%SZ')}"


def round_quota(daily_ceiling: int, index: int) -> int:
    """k_j = floor(C(j+1)/96) - floor(Cj/96); idle quota is never carried."""

    if not 0 <= index < ROUNDS_PER_DAY:
        raise OpportunityEpisodeError("EPISODE_ROUND_INVALID")
    c = int(daily_ceiling)
    return (c * (index + 1)) // ROUNDS_PER_DAY - (c * index) // ROUNDS_PER_DAY


def ticket_priority(*, seed: str, cycle: datetime, mint: str) -> str:
    return canonical_sha256(
        {"version": TICKET_VERSION, "seed": str(seed), "cycle_start": render_utc(cycle), "mint": str(mint)}
    )


def episode_id_for(*, lineage_id: str, cycle: datetime, mint: str) -> str:
    digest = canonical_sha256(
        {
            "version": EPISODE_ID_VERSION,
            "collection_lineage_id": str(lineage_id),
            "cycle_start": render_utc(cycle),
            "mint": str(mint),
        }
    )
    return f"EP-{digest[:32]}"


def cohort_id_for_admission(t0: datetime) -> str:
    t0 = t0.astimezone(UTC)
    start = datetime(t0.year, t0.month, t0.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    return f"REL-{start.strftime('%Y%m%dT%H%M%SZ')}-{end.strftime('%Y%m%dT%H%M%SZ')}"


def cohort_day_bounds(cohort_id: str) -> tuple[datetime, datetime]:
    text = str(cohort_id or "")
    parts = text.split("-")
    if len(parts) != 3 or parts[0] != "REL":
        raise OpportunityEpisodeError("EPISODE_COHORT_ID_INVALID")
    try:
        start = datetime.strptime(parts[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        end = datetime.strptime(parts[2], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise OpportunityEpisodeError("EPISODE_COHORT_ID_INVALID") from exc
    if end - start != timedelta(days=1) or start.hour or start.minute or start.second:
        raise OpportunityEpisodeError("EPISODE_COHORT_ID_INVALID")
    return start, end


# --------------------------------------------------------------------------
# Protection gate (metadata only)


@dataclass(frozen=True)
class ProtectionInventory:
    status: str
    sources: tuple[dict[str, Any], ...]
    entries: dict[str, tuple[dict[str, Any], ...]]
    reason: str | None

    def fingerprint(self) -> str:
        return canonical_sha256(
            {
                "version": PROTECTION_VERSION,
                "status": self.status,
                "sources": list(self.sources),
                "reason": self.reason,
            }
        )


def _assignment_path(data_root: Path, assignment_id: str) -> Path:
    if not assignment_id or any(ch in assignment_id for ch in "/\\:") or ".." in assignment_id:
        raise OpportunityEpisodeError("PROTECTION_SOURCE_ID_UNSAFE")
    return Path(data_root) / ASSIGNMENT_DIR / f"{assignment_id}.json"


def assignment_document_sha256(document: Mapping[str, Any]) -> str:
    return canonical_sha256(dict(document))


def load_protection_inventory(
    data_root: Path,
    sources: Sequence[Mapping[str, Any]],
    *,
    extra_documents: Sequence[Mapping[str, Any]] = (),
) -> ProtectionInventory:
    """Load registered assignment metadata. Never opens an outcome partition.

    A missing, tampered or incomplete source makes the whole inventory
    UNRESOLVED_SCOPE: a partial inventory is never a blanket ALLOW.
    """

    documents: list[Mapping[str, Any]] = []
    if not sources:
        return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_SOURCES_EMPTY")
    for source in sources:
        assignment_id = str(source.get("assignment_id") or "")
        expected = str(source.get("sha256") or "")
        try:
            path = _assignment_path(data_root, assignment_id)
        except OpportunityEpisodeError:
            return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_SOURCE_ID_UNSAFE")
        if not path.is_file() or path.is_symlink():
            return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_SOURCE_MISSING")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_SOURCE_UNREADABLE")
        if not isinstance(document, Mapping):
            return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_SOURCE_UNREADABLE")
        if assignment_document_sha256(document) != expected:
            return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_SOURCE_HASH_MISMATCH")
        documents.append(document)
    documents.extend(extra_documents)
    return inventory_from_documents(documents)


def inventory_from_documents(documents: Sequence[Mapping[str, Any]]) -> ProtectionInventory:
    """One fail-closed inventory from already loaded assignment documents."""

    loaded: list[dict[str, Any]] = []
    entries: dict[str, list[dict[str, Any]]] = {}
    if not documents:
        return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_SOURCES_EMPTY")
    for document in documents:
        if not isinstance(document, Mapping):
            return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_SOURCE_UNREADABLE")
        if document.get("schema") != ASSIGNMENT_SCHEMA or document.get("schema_version") != "1.0":
            return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_SOURCE_SCHEMA_UNKNOWN")
        completeness = document.get("completeness")
        if not isinstance(completeness, Mapping) or completeness.get("complete") is not True:
            return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_COMPLETENESS_UNPROVEN")
        loaded.append(
            {
                "assignment_id": str(document.get("assignment_id") or ""),
                "sha256": assignment_document_sha256(document),
                "interpretation_version": str(document.get("interpretation_version") or ""),
            }
        )
        for entry in document.get("entries") or []:
            if not isinstance(entry, Mapping) or entry.get("identity_kind") != "MINT":
                return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_ENTRY_INVALID")
            identity = str(entry.get("identity") or "")
            if not identity:
                return ProtectionInventory(UNRESOLVED_SCOPE, (), {}, "PROTECTION_ENTRY_INVALID")
            entries.setdefault(identity, []).append(dict(entry))
    return ProtectionInventory(
        ALLOW,
        tuple(sorted(loaded, key=lambda item: item["assignment_id"])),
        {key: tuple(value) for key, value in entries.items()},
        None,
    )


def protection_decision(
    inventory: ProtectionInventory,
    mint: str,
    *,
    interval_start: datetime,
    interval_end: datetime,
) -> tuple[str, str | None]:
    """ALLOW / DENY_PROTECTED / UNRESOLVED_SCOPE for one identity and interval."""

    if inventory.status != ALLOW:
        return UNRESOLVED_SCOPE, inventory.reason or "PROTECTION_INVENTORY_UNRESOLVED"
    decision = ALLOW
    reason: str | None = None
    for entry in inventory.entries.get(str(mint), ()):
        scope = entry.get("scope") if isinstance(entry.get("scope"), Mapping) else {}
        kind = scope.get("kind")
        if kind == "ALL_TIME":
            return DENY_PROTECTED, str(entry.get("role") or "PROTECTED")
        if kind == "INTERVAL":
            try:
                start = parse_utc(str(scope.get("start")))
                end = parse_utc(str(scope.get("end")))
            except (ObservationScheduleError, ValueError):
                decision, reason = UNRESOLVED_SCOPE, "PROTECTION_SCOPE_MALFORMED"
                continue
            if start < interval_end and interval_start < end:
                return DENY_PROTECTED, str(entry.get("role") or "PROTECTED")
            continue
        decision, reason = UNRESOLVED_SCOPE, "PROTECTION_SCOPE_UNKNOWN"
    return decision, reason


# --------------------------------------------------------------------------
# Closed frame


def _object_mint(row: Mapping[str, Any]) -> str | None:
    value, state, _missing = project_tokens_v2_field(row, MINT_FIELD)
    if state != STATE_OBSERVED or not isinstance(value, str):
        return None
    text = value.strip()
    if text != value or not 32 <= len(text) <= 44 or not text.isalnum():
        return None
    return text


def object_sha256(row: Mapping[str, Any]) -> str:
    return canonical_sha256(dict(row))


def _asset_class(row: Mapping[str, Any], mint: str, policy: Mapping[str, Any]) -> tuple[str, str | None]:
    if mint in {str(item) for item in policy.get("excluded_mints") or []}:
        return "EXCLUDED", "EXCLUDED_MINT"
    tags = row.get("tags")
    tag_set = {str(item).casefold() for item in tags} if isinstance(tags, list) else set()
    excluded = {str(item).casefold() for item in policy.get("excluded_tags") or []}
    hit = sorted(tag_set & excluded)
    if hit:
        return "EXCLUDED", f"EXCLUDED_TAG:{hit[0]}"
    if not tag_set:
        return "UNKNOWN", None
    return "SPECULATIVE_ALLOWED", None


def _core_floor(row: Mapping[str, Any], floor: Mapping[str, Any]) -> tuple[bool, str | None, dict[str, Any]]:
    values: dict[str, Any] = {}
    for field_id in CORE_FIELDS:
        value, state, missing = project_tokens_v2_field(row, field_id)
        if state != STATE_OBSERVED:
            return False, f"{field_id}:{missing or state}", values
        values[field_id] = value
    price = Decimal(str(values[PRICE]))
    liquidity = Decimal(str(values[LIQUIDITY]))
    holders = Decimal(str(values[HOLDER_COUNT]))
    if price <= 0:
        return False, "PRICE_NOT_POSITIVE", values
    if holders != holders.to_integral_value() or holders < int(floor["holders_min"]):
        return False, "HOLDERS_BELOW_FLOOR", values
    low = Decimal(str(floor["liquidity_usd_min"]))
    high = Decimal(str(floor["liquidity_usd_max"]))
    if liquidity < low:
        return False, "LIQUIDITY_BELOW_FLOOR", values
    if liquidity > high:
        return False, "LIQUIDITY_ABOVE_CEILING", values
    return True, None, values


def build_frame(
    *,
    document: Mapping[str, Any],
    activation_id: str,
    round_started_at: datetime,
    source_results: Sequence[Mapping[str, Any]],
    inventory: ProtectionInventory,
) -> dict[str, Any]:
    """One closed frame from one round. Protection precedes value projection."""

    nomination = document["nomination"]
    declared = [str(item["source_id"]) for item in nomination["sources"]]
    slack = int(nomination["round_slack_seconds"])
    by_source = {str(item.get("source_id")): item for item in source_results}
    source_status: list[dict[str, Any]] = []
    complete = True
    for order, source_id in enumerate(declared):
        result = by_source.get(source_id)
        status = "MISSING"
        if result is not None:
            status = str(result.get("status") or "MISSING")
            body = result.get("body")
            received = result.get("response_received_at")
            in_round = False
            if isinstance(received, str):
                at = parse_utc(received)
                in_round = round_started_at <= at <= round_started_at + timedelta(seconds=slack)
            if status == "OBSERVED" and not isinstance(body, list):
                status = "INVALID_BODY"
            elif status == "OBSERVED" and not in_round:
                status = "OUTSIDE_ROUND"
        if status != "OBSERVED":
            complete = False
        source_status.append(
            {
                "source_id": source_id,
                "order": order,
                "status": status,
                "missing_reason": None if result is None else result.get("missing_reason"),
                "call_occurrence_id": None if result is None else result.get("call_occurrence_id"),
                "response_sha256": None if result is None else result.get("response_sha256"),
                "response_received_at": None if result is None else result.get("response_received_at"),
            }
        )
    counts = {
        "received": 0,
        "identity_invalid": 0,
        "protected": 0,
        "protection_unresolved": 0,
        "asset_excluded": 0,
        "core_unusable": 0,
        "deduplicated": 0,
        "eligible": 0,
    }
    frame = {
        "frame_version": FRAME_VERSION,
        "activation_id": activation_id,
        "round_id": round_id(activation_id, round_started_at),
        "round_started_at": render_utc(round_started_at),
        "complete": complete,
        "sources": source_status,
        "protection_fingerprint": inventory.fingerprint(),
        "counts": counts,
        "candidates": [],
        "overlap": {},
    }
    if not complete:
        frame["terminal"] = "ROUND_INCOMPLETE"
        return frame
    horizon_end = round_started_at + timedelta(seconds=V1_HORIZON + 2 * V1_HOURLY_STEP)
    occurrences: dict[str, list[tuple[datetime, int, str, str, int, Mapping[str, Any]]]] = {}
    overlap: dict[str, list[str]] = {}
    for order, source_id in enumerate(declared):
        result = by_source[source_id]
        received = parse_utc(str(result["response_received_at"]))
        for rank, row in enumerate(result.get("body") or []):
            counts["received"] += 1
            if not isinstance(row, Mapping):
                counts["identity_invalid"] += 1
                continue
            mint = _object_mint(row)
            if mint is None:
                counts["identity_invalid"] += 1
                continue
            occurrences.setdefault(mint, []).append(
                (received, order, object_sha256(row), source_id, rank, row)
            )
            overlap.setdefault(mint, [])
            if source_id not in overlap[mint]:
                overlap[mint].append(source_id)
    asset_policy = document.get("asset_exclusion") or {}
    floor = document["capture_floor"]
    candidates: list[dict[str, Any]] = []
    for mint in sorted(occurrences):
        items = occurrences[mint]
        counts["deduplicated"] += len(items) - 1
        decision, reason = protection_decision(
            inventory, mint, interval_start=round_started_at - timedelta(days=1), interval_end=horizon_end
        )
        if decision == DENY_PROTECTED:
            counts["protected"] += 1
            continue
        if decision == UNRESOLVED_SCOPE:
            counts["protection_unresolved"] += 1
            continue
        # Freshest whole object; ties by frozen source order then object hash.
        chosen = sorted(items, key=lambda item: (-item[0].timestamp(), item[1], item[2]))[0]
        received, order, object_hash, source_id, rank, row = chosen
        asset_class, asset_reason = _asset_class(row, mint, asset_policy)
        status = FRAME_PASS
        status_reason: str | None = None
        core: dict[str, Any] = {}
        if asset_class == "EXCLUDED":
            status, status_reason = FRAME_ASSET_EXCLUDED, asset_reason
            counts["asset_excluded"] += 1
        else:
            passed, failure, core = _core_floor(row, floor)
            if not passed:
                status, status_reason = FRAME_CORE_UNUSABLE, failure
                counts["core_unusable"] += 1
            else:
                counts["eligible"] += 1
        source = by_source[source_id]
        candidates.append(
            {
                "mint": mint,
                "status": status,
                "reason": status_reason,
                "asset_class": asset_class,
                "selected_source_id": source_id,
                "selected_rank": rank,
                "selected_object_sha256": object_hash,
                "selected_received_at": render_utc(received),
                "selected_call_occurrence_id": source.get("call_occurrence_id"),
                "selected_request_sha256": source.get("request_sha256"),
                "selected_request_started_at": source.get("request_started_at"),
                "selected_response_received_at": source.get("response_received_at"),
                "selected_first_reliable_available_at": source.get("first_reliable_available_at"),
                "selected_response_sha256": source.get("response_sha256"),
                "selected_raw_body_rel": source.get("raw_body_rel"),
                "core_values": {key: str(value) for key, value in core.items()},
                "object": dict(row) if status == FRAME_PASS else None,
            }
        )
    frame["candidates"] = candidates
    # Overlap edges only for identities that passed protection: protected or
    # unresolved identities appear as counts, never as named evidence.
    allowed = {item["mint"] for item in candidates}
    frame["overlap"] = {key: overlap[key] for key in sorted(overlap) if key in allowed}
    frame["terminal"] = "FRAME_CLOSED"
    return frame


def frame_receipt(frame: Mapping[str, Any]) -> dict[str, Any]:
    """Bounded selection evidence; never carries protected values."""

    body = {
        key: frame[key]
        for key in (
            "frame_version",
            "activation_id",
            "round_id",
            "round_started_at",
            "complete",
            "sources",
            "protection_fingerprint",
            "counts",
            "overlap",
            "terminal",
        )
        if key in frame
    }
    body["candidates"] = [
        {
            key: item.get(key)
            for key in (
                "mint",
                "status",
                "reason",
                "asset_class",
                "selected_source_id",
                "selected_rank",
                "selected_object_sha256",
                "selected_call_occurrence_id",
            )
        }
        for item in frame.get("candidates") or []
    ]
    body["frame_sha256"] = canonical_sha256(body)
    return body


# --------------------------------------------------------------------------
# Admission selection


def select_admissions(
    *,
    frame: Mapping[str, Any],
    seed: str,
    cycle: datetime,
    quota: int,
    blocked_mints: Iterable[str],
) -> dict[str, Any]:
    """Deterministic (priority, mint) order over eligible tickets of this frame."""

    blocked = {str(item) for item in blocked_mints}
    pending = []
    for item in frame.get("candidates") or []:
        if item.get("status") != FRAME_PASS:
            continue
        mint = str(item["mint"])
        if mint in blocked:
            continue
        pending.append((ticket_priority(seed=seed, cycle=cycle, mint=mint), mint, item))
    pending.sort(key=lambda entry: (entry[0], entry[1]))
    winners = pending[: max(0, int(quota))]
    return {
        "eligible_pending": len(pending),
        "quota": int(quota),
        "winners": [
            {"mint": mint, "ticket_priority": priority, "candidate": candidate}
            for priority, mint, candidate in winners
        ],
        "not_selected": [mint for _priority, mint, _item in pending[len(winners):]],
    }


def admission_record(
    *,
    document: Mapping[str, Any],
    activation_id: str,
    lineage_id: str,
    cycle: datetime,
    mint: str,
    t0: datetime,
    ticket_priority_value: str,
    candidate: Mapping[str, Any],
    frame_sha256: str,
    protection_fingerprint: str,
    round_id_value: str,
) -> dict[str, Any]:
    """Immutable admission fact. Published as the episode member row."""

    episode_id = episode_id_for(lineage_id=lineage_id, cycle=cycle, mint=mint)
    return {
        "entity_id": episode_id,
        "episode_id": episode_id,
        "mint": mint,
        "population": POPULATION,
        "population_contract": POPULATION_CONTRACT,
        "anchor_kind": ANCHOR_KIND,
        "collection_kind": COLLECTION_KIND,
        "collection_lineage_id": lineage_id,
        "schedule_sha256": str(document["schedule_sha256"]),
        "activation_id": activation_id,
        "cycle_start": render_utc(cycle),
        "ticket_priority": ticket_priority_value,
        "t0": render_utc(t0),
        "cohort_id": cohort_id_for_admission(t0),
        "membership_state": "ADMITTED",
        "witness_point_id": WITNESS_POINT,
        "witness_source_id": candidate.get("selected_source_id"),
        "witness_rank": candidate.get("selected_rank"),
        "witness_object_sha256": candidate.get("selected_object_sha256"),
        "witness_call_occurrence_id": candidate.get("selected_call_occurrence_id"),
        "witness_request_sha256": candidate.get("selected_request_sha256"),
        "witness_request_started_at": candidate.get("selected_request_started_at"),
        "witness_response_received_at": candidate.get("selected_response_received_at"),
        "witness_first_reliable_available_at": candidate.get("selected_first_reliable_available_at"),
        "witness_response_sha256": candidate.get("selected_response_sha256"),
        "witness_raw_body_rel": candidate.get("selected_raw_body_rel"),
        "asset_class": candidate.get("asset_class"),
        "frame_sha256": frame_sha256,
        "protection_fingerprint": protection_fingerprint,
        "round_id": round_id_value,
    }


def admission_content_sha256(record: Mapping[str, Any]) -> str:
    return canonical_sha256(dict(record))


def witness_age_ok(record: Mapping[str, Any], binding: Mapping[str, Any]) -> bool:
    request = record.get("witness_request_started_at")
    if not isinstance(request, str):
        return False
    t0 = parse_utc(str(record["t0"]))
    return parse_utc(request) >= t0 - timedelta(seconds=int(binding["witness_max_age_seconds"]))
