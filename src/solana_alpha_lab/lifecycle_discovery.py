"""Fail-closed offline contract for the TASK-08 lifecycle discovery pilot."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias

from solana_alpha_lab.contracts.schema_v1 import LifecycleState

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

CONTRACT_VERSION = "1.0"
CONTRACT_AS_OF = "2026-07-25"
FROZEN_FIXTURE_SHA256 = "409fa9f409af5f374d9ff59dff4e3e442bb6c31e0367412f41f4af2bbee1169d"
NETWORK_DISABLED_BY_DEFAULT = True
OFFICIAL_PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
OFFICIAL_PUMP_IDL_BLOB_SHA = "062e66f032bb9f295353b573be3400070bd55e5b"
OFFICIAL_PUMP_IDL_PATH = "idl/pump.json"
PUMP_EVENT_SUBSET_FIXTURE = (
    "tests/fixtures/task08/pump_event_idl_subset_v1.json"
)

EXPECTED_TIMESTAMP_FIELDS = (
    "event_at",
    "observed_at",
    "first_reliable_available_at",
    "available_at",
    "ingested_at",
)
EXPECTED_EVENT_MAP = {
    "CreateEvent": LifecycleState.CREATED,
    "TradeEvent": LifecycleState.ACTIVE,
    "CompleteEvent": LifecycleState.MIGRATION_STARTED,
    "CompletePumpAmmMigrationEvent": LifecycleState.MIGRATED,
}
EXPECTED_CATALOG_IDS = (
    "CTRL-TASK-08-001",
    "CONTRACT-T08-LIFECYCLE-DISCOVERY-001",
    "MODULE-T08-LIFECYCLE-DISCOVERY-001",
    "FIXTURE-T08-LIFECYCLE-DISCOVERY-001",
    "TEST-T08-LIFECYCLE-DISCOVERY-001",
)
EXPECTED_CONSUMERS = (
    "TASK-09",
    "TASK-11",
    "TASK-12",
    "TASK-13",
    "TASK-18",
    "TASK-19",
)

PROBE_BUDGET = {
    "elapsed_seconds": 600,
    "wss_connections": 1,
    "wss_subscriptions": 1,
    "notifications": 500,
    "stream_bytes": 1_000_000,
    "rpc_followups": 20,
    "helius_credits": 41,
    "solana_tracker_requests": 8,
    "received_and_stored_bytes": 5_000_000,
    "concurrency": 1,
    "retries": 0,
    "cash_spend_usd_cents": 0,
}
PILOT_BUDGET = {
    "elapsed_hours": 24,
    "intake_hours": 2,
    "followup_hours": 22,
    "wss_initial_connections": 1,
    "wss_reconnects": 6,
    "stream_bytes": 500_000_000,
    "rpc_followups": 5_000,
    "helius_credits": 16_000,
    "solana_tracker_requests": 1_200,
    "solana_tracker_allowance_reserve": 1_300,
    "dataset_bytes": 1_073_741_824,
    "partition_bytes": 67_108_864,
    "minimum_free_bytes_after_write": 21_474_836_480,
    "concurrency": 1,
    "cash_spend_usd_cents": 0,
}

_TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "schema_version",
        "task_id",
        "atom_id",
        "as_of",
        "status",
        "protocol",
        "event_vocabulary",
        "derived_states",
        "universes",
        "timestamps",
        "provider_roles",
        "provider_facts",
        "probe_budget",
        "pilot_budget",
        "security",
        "catalog",
    }
)
_FORBIDDEN_SELECTION_FIELDS = frozenset(
    {
        "liquidity",
        "volume",
        "market_cap",
        "price_return",
        "holder_count",
        "risk_score",
        "migration_outcome",
        "future_availability",
        "popularity",
    }
)
_FORBIDDEN_DURABLE_KEYS = frozenset(
    {
        "authorization",
        "xapikey",
        "apikey",
        "cookie",
        "password",
        "privatekey",
        "seedphrase",
        "secret",
        "tokenvalue",
    }
)
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


class DiscoveryContractError(ValueError):
    """The frozen TASK-08 contract or a derived claim is invalid."""


class CoverageInvariantError(DiscoveryContractError):
    """A cohort, lifecycle or point-in-time coverage rule was violated."""


class BudgetInvariantError(DiscoveryContractError):
    """A bounded probe or pilot usage claim exceeded its frozen cap."""


class ExternalActionDisabledError(DiscoveryContractError):
    """Atom 2 attempted to cross its offline authority boundary."""


@dataclass(frozen=True, slots=True)
class EventRule:
    source_event: str
    lifecycle_state: LifecycleState
    requires_success: bool
    destination_required: bool


@dataclass(frozen=True, slots=True)
class ProviderRole:
    role_id: str
    provider: str
    surface: str
    event_owner: bool
    paths: tuple[str, ...]
    method: str | None
    commitment: str | None
    pacing_requests_per_second: int | None


@dataclass(frozen=True, slots=True)
class DiscoveryPlan:
    fixture_sha256: str
    event_rules: tuple[EventRule, ...]
    provider_roles: tuple[ProviderRole, ...]
    timestamp_fields: tuple[str, ...]
    intake_seconds: int
    followup_seconds: int
    inactive_after_seconds: int
    cohort_identity_fields: tuple[str, ...]
    probe_budget: dict[str, int]
    pilot_budget: dict[str, int]
    catalog_ids: tuple[str, ...]
    named_consumers: tuple[str, ...]

    @property
    def event_rule_by_name(self) -> dict[str, EventRule]:
        return {rule.source_event: rule for rule in self.event_rules}

    @property
    def provider_role_by_id(self) -> dict[str, ProviderRole]:
        return {role.role_id: role for role in self.provider_roles}


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DiscoveryContractError(f"{name}_must_be_mapping")
    if not all(isinstance(key, str) for key in value):
        raise DiscoveryContractError(f"{name}_keys_must_be_text")
    return value


def _sequence(name: str, value: object) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DiscoveryContractError(f"{name}_must_be_sequence")
    return value


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DiscoveryContractError(f"{name}_must_be_integer")
    if value < 0:
        raise DiscoveryContractError(f"{name}_must_be_nonnegative")
    return value


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise DiscoveryContractError(f"{name}_must_be_nonempty_text")
    return value


def _exact(name: str, value: object, expected: object) -> None:
    if value != expected:
        raise DiscoveryContractError(f"{name}_drift")


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _compile_event_rules(value: object) -> tuple[EventRule, ...]:
    rows = _sequence("event_vocabulary", value)
    rules: list[EventRule] = []
    for index, item in enumerate(rows):
        row = _mapping(f"event_vocabulary_{index}", item)
        _exact(
            f"event_vocabulary_{index}_keys",
            set(row),
            {
                "source_event",
                "lifecycle_state",
                "requires_success",
                "destination_required",
            },
        )
        event_name = _text("source_event", row["source_event"])
        if event_name not in EXPECTED_EVENT_MAP:
            raise DiscoveryContractError(f"unexpected_source_event:{event_name}")
        expected_state = EXPECTED_EVENT_MAP[event_name]
        _exact(
            f"event_state_{event_name}",
            row["lifecycle_state"],
            expected_state.value,
        )
        _exact(f"event_requires_success_{event_name}", row["requires_success"], True)
        destination_required = event_name == "CompletePumpAmmMigrationEvent"
        _exact(
            f"event_destination_required_{event_name}",
            row["destination_required"],
            destination_required,
        )
        rules.append(
            EventRule(
                source_event=event_name,
                lifecycle_state=expected_state,
                requires_success=True,
                destination_required=destination_required,
            )
        )
    if [rule.source_event for rule in rules] != list(EXPECTED_EVENT_MAP):
        raise DiscoveryContractError("event_vocabulary_order_or_inventory_drift")
    return tuple(rules)


def _compile_provider_roles(value: object) -> tuple[ProviderRole, ...]:
    document = _mapping("provider_roles", value)
    _exact(
        "provider_role_inventory",
        tuple(document),
        ("HELIUS_CHAIN_PRIMARY", "SOLANA_TRACKER_REST_FALLBACK"),
    )

    primary = _mapping("helius_primary", document["HELIUS_CHAIN_PRIMARY"])
    _exact(
        "helius_primary",
        primary,
        {
            "provider": "HELIUS",
            "surface": "STANDARD_WSS",
            "event_owner": True,
            "method": "logsSubscribe",
            "program_id": OFFICIAL_PUMP_PROGRAM_ID,
            "mentions": [OFFICIAL_PUMP_PROGRAM_ID],
            "commitment": "confirmed",
            "auth_mode": "LOCAL_USER_BOUNDARY",
            "auth_material_persisted": False,
        },
    )
    fallback = _mapping(
        "solana_tracker_fallback",
        document["SOLANA_TRACKER_REST_FALLBACK"],
    )
    _exact(
        "solana_tracker_fallback",
        fallback,
        {
            "provider": "SOLANA_TRACKER",
            "surface": "REST",
            "event_owner": False,
            "paths": [
                "/tokens/latest",
                "/tokens/multi/graduating",
                "/tokens/multi/graduated",
            ],
            "pacing_requests_per_second": 1,
            "auth_mode": "LOCAL_USER_BOUNDARY",
            "auth_material_persisted": False,
            "premium_datastream_allowed": False,
        },
    )
    return (
        ProviderRole(
            role_id="HELIUS_CHAIN_PRIMARY",
            provider="HELIUS",
            surface="STANDARD_WSS",
            event_owner=True,
            paths=(),
            method="logsSubscribe",
            commitment="confirmed",
            pacing_requests_per_second=None,
        ),
        ProviderRole(
            role_id="SOLANA_TRACKER_REST_FALLBACK",
            provider="SOLANA_TRACKER",
            surface="REST",
            event_owner=False,
            paths=tuple(fallback["paths"]),
            method=None,
            commitment=None,
            pacing_requests_per_second=1,
        ),
    )


def compile_discovery_contract(
    document: Mapping[str, Any],
    *,
    fixture_sha256: str = FROZEN_FIXTURE_SHA256,
) -> DiscoveryPlan:
    """Compile the exact frozen JSON document without performing I/O."""

    root = _mapping("contract", document)
    _exact("top_level_keys", set(root), _TOP_LEVEL_KEYS)
    _exact("schema", root["schema"], "solana_alpha_lab.lifecycle_discovery_contract")
    _exact("schema_version", root["schema_version"], CONTRACT_VERSION)
    _exact("task_id", root["task_id"], "TASK-08")
    _exact("atom_id", root["atom_id"], "T08-A3")
    _exact("as_of", root["as_of"], CONTRACT_AS_OF)
    _exact("status", root["status"], "OFFLINE_PROTOCOL_PINNED_CANDIDATE")

    protocol = _mapping("protocol", root["protocol"])
    _exact(
        "protocol",
        protocol,
        {
            "official_source": "github:pump-fun/pump-public-docs",
            "pin_state": "PINNED_OFFICIAL_IDL_BLOB",
            "program_id": OFFICIAL_PUMP_PROGRAM_ID,
            "idl_path": OFFICIAL_PUMP_IDL_PATH,
            "idl_blob_sha": OFFICIAL_PUMP_IDL_BLOB_SHA,
            "event_subset_fixture": PUMP_EVENT_SUBSET_FIXTURE,
        },
    )
    event_rules = _compile_event_rules(root["event_vocabulary"])
    _exact(
        "derived_states",
        root["derived_states"],
        {
            "DISCOVERED": "FIRST_INDEXED_PROVIDER_OBSERVATION_ONLY",
            "INACTIVE": {
                "minimum_quiet_seconds": 21_600,
                "complete_coverage_required": True,
            },
            "UNKNOWN": [
                "INSUFFICIENT_FOLLOWUP",
                "COVERAGE_GAP",
                "PROVIDER_DISAGREEMENT",
                "PROTOCOL_OR_SCHEMA_DRIFT",
            ],
        },
    )

    universes = _mapping("universes", root["universes"])
    _exact(
        "universe_contract",
        universes,
        {
            "domain": "PUMPFUN",
            "launch": {
                "source_role": "HELIUS_CHAIN_PRIMARY",
                "source_event": "CreateEvent",
                "transaction_must_succeed": True,
                "intake_seconds": 7_200,
                "selection_fields": [],
            },
            "followup_seconds": 79_200,
            "post_migration": "SUBSET_OF_LAUNCH_UNIVERSE",
            "signal": "NONE",
            "execution": "NONE",
            "failed_transactions": "RAW_EVIDENCE_ONLY",
            "right_censoring": "UNKNOWN",
            "cohort_identity_fields": [
                "program_id",
                "signature",
                "instruction_index",
                "mint",
            ],
            "forbidden_selection_fields": sorted(_FORBIDDEN_SELECTION_FIELDS),
        },
    )
    selection_fields = set(universes["launch"]["selection_fields"])
    if selection_fields & _FORBIDDEN_SELECTION_FIELDS:
        raise CoverageInvariantError("outcome_dependent_launch_filter")

    timestamp_fields = tuple(
        _text("timestamp_field", value)
        for value in _sequence("timestamps", root["timestamps"])
    )
    _exact("timestamp_fields", timestamp_fields, EXPECTED_TIMESTAMP_FIELDS)
    provider_roles = _compile_provider_roles(root["provider_roles"])
    _exact(
        "provider_facts",
        root["provider_facts"],
        {
            "as_of": CONTRACT_AS_OF,
            "helius_free_monthly_credits": 1_000_000,
            "helius_rpc_requests_per_second": 10,
            "helius_wss_connection_credit": 1,
            "helius_wss_credits_per_100000_bytes": 2,
            "solana_tracker_documented_free_requests": 10_000,
            "solana_tracker_product_page_free_requests": 2_500,
            "solana_tracker_conservative_allowance": 2_500,
            "solana_tracker_published_requests_per_second": 3,
            "dashboard_readback_required": True,
        },
    )
    _exact("probe_budget", root["probe_budget"], PROBE_BUDGET)
    _exact("pilot_budget", root["pilot_budget"], PILOT_BUDGET)
    _exact(
        "security",
        root["security"],
        {
            "network_enabled": False,
            "credential_use_enabled": False,
            "local_data_write_enabled": False,
            "dependency_changes_enabled": False,
            "cash_spend_usd_cents": 0,
            "wallet_signer_transaction_actions": 0,
            "durable_absolute_paths_allowed": False,
            "durable_auth_material_allowed": False,
            "transport_imports_allowed": False,
        },
    )
    catalog = _mapping("catalog", root["catalog"])
    _exact("catalog_ids", tuple(catalog["future_asset_ids"]), EXPECTED_CATALOG_IDS)
    _exact(
        "catalog_consumers",
        tuple(catalog["named_consumers"]),
        EXPECTED_CONSUMERS,
    )
    _exact("catalog_update_in_atom", catalog["update_in_this_atom"], False)

    if projected_helius_credits(
        stream_bytes=PROBE_BUDGET["stream_bytes"],
        rpc_calls=PROBE_BUDGET["rpc_followups"],
        connections=PROBE_BUDGET["wss_connections"],
    ) != PROBE_BUDGET["helius_credits"]:
        raise BudgetInvariantError("probe_credit_formula_drift")
    projected_pilot_credits = projected_helius_credits(
        stream_bytes=PILOT_BUDGET["stream_bytes"],
        rpc_calls=PILOT_BUDGET["rpc_followups"],
        connections=(
            PILOT_BUDGET["wss_initial_connections"]
            + PILOT_BUDGET["wss_reconnects"]
        ),
    )
    if projected_pilot_credits > PILOT_BUDGET["helius_credits"]:
        raise BudgetInvariantError("pilot_credit_cap_insufficient")
    if (
        PILOT_BUDGET["solana_tracker_requests"]
        + PILOT_BUDGET["solana_tracker_allowance_reserve"]
        != 2_500
    ):
        raise BudgetInvariantError("solana_tracker_allowance_not_conservative")

    return DiscoveryPlan(
        fixture_sha256=fixture_sha256,
        event_rules=event_rules,
        provider_roles=provider_roles,
        timestamp_fields=timestamp_fields,
        intake_seconds=7_200,
        followup_seconds=79_200,
        inactive_after_seconds=21_600,
        cohort_identity_fields=tuple(universes["cohort_identity_fields"]),
        probe_budget=dict(PROBE_BUDGET),
        pilot_budget=dict(PILOT_BUDGET),
        catalog_ids=EXPECTED_CATALOG_IDS,
        named_consumers=EXPECTED_CONSUMERS,
    )


def load_frozen_discovery_plan(path: Path) -> DiscoveryPlan:
    """Read and verify the exact fixture before compiling it."""

    payload = path.read_bytes()
    observed_hash = hashlib.sha256(payload).hexdigest()
    if observed_hash != FROZEN_FIXTURE_SHA256:
        raise DiscoveryContractError(
            f"frozen_fixture_hash_mismatch:{observed_hash}"
        )
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DiscoveryContractError("frozen_fixture_invalid_json") from exc
    return compile_discovery_contract(document, fixture_sha256=observed_hash)


def classify_protocol_event(
    plan: DiscoveryPlan,
    *,
    source_event: str,
    transaction_succeeded: bool,
    destination_program: str | None = None,
    destination_pool: str | None = None,
) -> LifecycleState | None:
    """Map one pinned Pump event to a lifecycle state without future inference."""

    if not transaction_succeeded:
        return None
    rule = plan.event_rule_by_name.get(source_event)
    if rule is None:
        raise CoverageInvariantError(f"unrecognized_protocol_event:{source_event}")
    if rule.destination_required and (
        not destination_program or not destination_pool
    ):
        raise CoverageInvariantError("migration_destination_required")
    if not rule.destination_required and (
        destination_program is not None or destination_pool is not None
    ):
        raise CoverageInvariantError("unexpected_migration_destination")
    return rule.lifecycle_state


def cohort_eligible(
    plan: DiscoveryPlan,
    *,
    provider_role: str,
    source_event: str,
    transaction_succeeded: bool,
    seconds_since_intake_start: int,
) -> bool:
    """Apply only the pre-outcome launch-universe rule."""

    if seconds_since_intake_start < 0:
        raise CoverageInvariantError("event_before_intake_start")
    return (
        provider_role == "HELIUS_CHAIN_PRIMARY"
        and source_event == "CreateEvent"
        and transaction_succeeded
        and seconds_since_intake_start < plan.intake_seconds
    )


def derive_quiet_state(
    plan: DiscoveryPlan,
    *,
    complete_coverage: bool,
    followup_seconds: int,
    quiet_seconds: int,
) -> LifecycleState | None:
    """Return INACTIVE only with complete coverage; otherwise preserve unknown."""

    for name, value in (
        ("followup_seconds", followup_seconds),
        ("quiet_seconds", quiet_seconds),
    ):
        _integer(name, value)
    if not complete_coverage:
        return LifecycleState.UNKNOWN
    if followup_seconds < plan.inactive_after_seconds:
        return LifecycleState.UNKNOWN
    if quiet_seconds >= plan.inactive_after_seconds:
        return LifecycleState.INACTIVE
    return None


def validate_timestamp_order(
    *,
    event_at: datetime,
    observed_at: datetime,
    first_reliable_available_at: datetime,
    available_at: datetime,
    ingested_at: datetime,
) -> None:
    """Enforce aware UTC-compatible PIT ordering without rewriting timestamps."""

    values = (
        event_at,
        observed_at,
        first_reliable_available_at,
        available_at,
        ingested_at,
    )
    if any(value.tzinfo is None or value.utcoffset() is None for value in values):
        raise CoverageInvariantError("timestamp_must_be_timezone_aware")
    if list(values) != sorted(values):
        raise CoverageInvariantError("timestamp_order_invalid")


def projected_helius_credits(
    *,
    stream_bytes: int,
    rpc_calls: int,
    connections: int,
) -> int:
    """Apply the frozen 2026-07-25 Helius standard-WSS credit model."""

    stream_bytes = _integer("stream_bytes", stream_bytes)
    rpc_calls = _integer("rpc_calls", rpc_calls)
    connections = _integer("connections", connections)
    stream_credits = math.ceil(stream_bytes / 100_000) * 2
    return stream_credits + rpc_calls + connections


def validate_probe_usage(
    plan: DiscoveryPlan,
    *,
    elapsed_seconds: int,
    wss_connections: int,
    wss_subscriptions: int,
    notifications: int,
    stream_bytes: int,
    rpc_followups: int,
    solana_tracker_requests: int,
    received_and_stored_bytes: int,
    concurrency: int,
    retries: int,
    cash_spend_usd_cents: int,
) -> dict[str, int]:
    """Validate a sanitized probe usage claim and return derived credits."""

    usage = {
        "elapsed_seconds": elapsed_seconds,
        "wss_connections": wss_connections,
        "wss_subscriptions": wss_subscriptions,
        "notifications": notifications,
        "stream_bytes": stream_bytes,
        "rpc_followups": rpc_followups,
        "solana_tracker_requests": solana_tracker_requests,
        "received_and_stored_bytes": received_and_stored_bytes,
        "concurrency": concurrency,
        "retries": retries,
        "cash_spend_usd_cents": cash_spend_usd_cents,
    }
    _validate_usage_caps("probe", usage, plan.probe_budget)
    credits = projected_helius_credits(
        stream_bytes=stream_bytes,
        rpc_calls=rpc_followups,
        connections=wss_connections,
    )
    if credits > plan.probe_budget["helius_credits"]:
        raise BudgetInvariantError("probe_helius_credits_exceeded")
    return {**usage, "helius_credits": credits}


def validate_pilot_usage(
    plan: DiscoveryPlan,
    *,
    elapsed_hours: int,
    wss_initial_connections: int,
    wss_reconnects: int,
    stream_bytes: int,
    rpc_followups: int,
    solana_tracker_requests: int,
    dataset_bytes: int,
    largest_partition_bytes: int,
    free_bytes_after_write: int,
    concurrency: int,
    cash_spend_usd_cents: int,
) -> dict[str, int]:
    """Validate a sanitized pilot usage claim against the outer envelope."""

    usage = {
        "elapsed_hours": elapsed_hours,
        "wss_initial_connections": wss_initial_connections,
        "wss_reconnects": wss_reconnects,
        "stream_bytes": stream_bytes,
        "rpc_followups": rpc_followups,
        "solana_tracker_requests": solana_tracker_requests,
        "dataset_bytes": dataset_bytes,
        "partition_bytes": largest_partition_bytes,
        "concurrency": concurrency,
        "cash_spend_usd_cents": cash_spend_usd_cents,
    }
    _validate_usage_caps("pilot", usage, plan.pilot_budget)
    free_bytes_after_write = _integer(
        "free_bytes_after_write",
        free_bytes_after_write,
    )
    if free_bytes_after_write < plan.pilot_budget[
        "minimum_free_bytes_after_write"
    ]:
        raise BudgetInvariantError("pilot_free_space_reserve_breached")
    connections = wss_initial_connections + wss_reconnects
    credits = projected_helius_credits(
        stream_bytes=stream_bytes,
        rpc_calls=rpc_followups,
        connections=connections,
    )
    if credits > plan.pilot_budget["helius_credits"]:
        raise BudgetInvariantError("pilot_helius_credits_exceeded")
    return {
        **usage,
        "free_bytes_after_write": free_bytes_after_write,
        "helius_credits": credits,
    }


def _validate_usage_caps(
    phase: str,
    usage: Mapping[str, int],
    budget: Mapping[str, int],
) -> None:
    for name, value in usage.items():
        value = _integer(name, value)
        if name not in budget:
            raise BudgetInvariantError(f"{phase}_unknown_usage_field:{name}")
        cap = budget[name]
        if name in {"concurrency"}:
            if value != cap:
                raise BudgetInvariantError(f"{phase}_{name}_must_equal_cap")
        elif name in {"retries", "cash_spend_usd_cents"}:
            if value != 0:
                raise BudgetInvariantError(f"{phase}_{name}_forbidden")
        elif value > cap:
            raise BudgetInvariantError(f"{phase}_{name}_exceeded")


def validate_durable_metadata(
    value: JsonValue,
    *,
    explicit_sensitive_values: Sequence[str] = (),
) -> bytes:
    """Reject secret-like keys, absolute paths and explicit sensitive values."""

    def visit(item: JsonValue) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if _normalized_key(key) in _FORBIDDEN_DURABLE_KEYS:
                    raise DiscoveryContractError("forbidden_durable_auth_field")
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)
        elif isinstance(item, str):
            if (
                _WINDOWS_ABSOLUTE_RE.match(item)
                or item.startswith("\\\\")
                or item.casefold().startswith("file://")
            ):
                raise DiscoveryContractError("absolute_machine_path_forbidden")
            for sensitive in explicit_sensitive_values:
                if sensitive and sensitive in item:
                    raise DiscoveryContractError("explicit_sensitive_value_detected")

    visit(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DiscoveryContractError("durable_metadata_must_be_json") from exc


def assert_atom2_offline_boundary(
    *,
    network_requested: bool = False,
    credential_use_requested: bool = False,
    local_data_write_requested: bool = False,
    dependency_change_requested: bool = False,
) -> None:
    """Keep every external, data-write and dependency action disabled."""

    requested = {
        "network": network_requested,
        "credential_use": credential_use_requested,
        "local_data_write": local_data_write_requested,
        "dependency_change": dependency_change_requested,
    }
    for name, enabled in requested.items():
        if enabled:
            raise ExternalActionDisabledError(f"atom2_{name}_disabled")
