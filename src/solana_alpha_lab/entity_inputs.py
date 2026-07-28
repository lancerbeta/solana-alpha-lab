"""Fail-closed offline entity-input reducer for TASK-11."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from solana_alpha_lab.contracts.schema_v1 import (
    EntityInputSnapshot,
    EntityType,
)

CONTRACT_VERSION = "1.0"
CONTRACT_AS_OF = "2026-07-28"
FROZEN_FIXTURE_SHA256 = (
    "b5fe517e3ddd6d0668edc3576210882082203edbf1f3bfca92b38a9164a1c686"
)
NETWORK_DISABLED_BY_DEFAULT = True
PRIMARY_PROVIDER = "HELIUS_STANDARD_SOLANA_RPC"
PRIMARY_METHODS = (
    "getTokenSupply",
    "getTokenLargestAccounts",
    "getMultipleAccounts",
)
MAX_LARGEST_ACCOUNTS = 20
EXPECTED_EVIDENCE_CLASSES = (
    "RAW_ONCHAIN",
    "DERIVED_ADJUSTED",
    "VENDOR_LABEL",
    "PROJECT_INFERENCE",
)
EXPECTED_METRICS = (
    "raw_top_accounts_amount_atomic",
    "raw_top_accounts_supply_share",
    "adjusted_top_accounts_supply_share",
    "unresolved_owner_account_count",
    "context_slot_spread",
)
EXPECTED_MANAGED_FILES = (
    "docs/contracts/entity_input_observation_contract_v1.md",
    "src/solana_alpha_lab/entity_inputs.py",
    "tests/fixtures/task11/entity_input_observation_contract_v1.json",
    "tests/test_task11_entity_inputs.py",
)
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "xapikey",
        "apikey",
        "accesstoken",
        "authtoken",
        "refreshtoken",
        "password",
        "secret",
        "privatekey",
        "seed",
        "seedphrase",
        "mnemonic",
        "cookie",
    }
)


class EntityInputContractError(ValueError):
    """The frozen TASK-11 contract or an entity claim is incoherent."""


class OfflineBoundaryError(EntityInputContractError):
    """The offline atom attempted to cross its authority boundary."""


class EvidenceClass(StrEnum):
    RAW_ONCHAIN = "RAW_ONCHAIN"
    DERIVED_ADJUSTED = "DERIVED_ADJUSTED"
    VENDOR_LABEL = "VENDOR_LABEL"
    PROJECT_INFERENCE = "PROJECT_INFERENCE"


class ExclusionDisposition(StrEnum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    UNRESOLVED = "UNRESOLVED"


class ConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class AvailabilityClass(StrEnum):
    RECONSTRUCTIBLE_CURRENT_SNAPSHOT = "RECONSTRUCTIBLE_CURRENT_SNAPSHOT"
    PARTIAL_CURRENT_SNAPSHOT = "PARTIAL_CURRENT_SNAPSHOT"
    VENDOR_DEPENDENT = "VENDOR_DEPENDENT"
    FORWARD_ONLY = "FORWARD_ONLY"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EntityInputContractError(message)


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def validate_timestamp_order(
    *,
    event_time: datetime,
    observed_at: datetime,
    first_reliable_available_at: datetime,
    available_to_strategy_at: datetime,
    ingested_at: datetime,
) -> None:
    values = (
        event_time,
        observed_at,
        first_reliable_available_at,
        available_to_strategy_at,
        ingested_at,
    )
    _require(all(_aware(value) for value in values), "timestamps_must_be_aware")
    _require(
        event_time
        <= observed_at
        <= first_reliable_available_at
        <= available_to_strategy_at
        <= ingested_at,
        "timestamp_order_violation",
    )


@dataclass(frozen=True, slots=True)
class HolderAccountObservation:
    token_account: str
    owner: str | None
    amount_atomic: int
    context_slot: int

    def __post_init__(self) -> None:
        _require(bool(self.token_account), "token_account_required")
        _require(
            self.owner is None or bool(self.owner),
            "owner_must_be_nonempty_or_null",
        )
        _require(
            isinstance(self.amount_atomic, int)
            and not isinstance(self.amount_atomic, bool)
            and self.amount_atomic >= 0,
            "amount_atomic_must_be_nonnegative_integer",
        )
        _require(
            isinstance(self.context_slot, int)
            and not isinstance(self.context_slot, bool)
            and self.context_slot >= 0,
            "context_slot_must_be_nonnegative_integer",
        )


@dataclass(frozen=True, slots=True)
class ExclusionAssessment:
    token_account: str
    disposition: ExclusionDisposition
    reason: str | None
    evidence_ref: str | None
    evidence_class: EvidenceClass
    confidence: ConfidenceLevel

    def __post_init__(self) -> None:
        _require(bool(self.token_account), "exclusion_token_account_required")
        if self.disposition == ExclusionDisposition.EXCLUDE:
            _require(bool(self.reason), "excluded_account_reason_required")
            _require(
                bool(self.evidence_ref),
                "excluded_account_evidence_ref_required",
            )
            _require(
                self.evidence_class
                in {
                    EvidenceClass.RAW_ONCHAIN,
                    EvidenceClass.PROJECT_INFERENCE,
                },
                "vendor_label_cannot_exclude_account",
            )
            _require(
                self.confidence
                in {ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM},
                "excluded_account_confidence_insufficient",
            )
        elif self.disposition == ExclusionDisposition.INCLUDE:
            _require(
                self.evidence_class != EvidenceClass.VENDOR_LABEL,
                "vendor_label_cannot_include_account_as_fact",
            )
        else:
            _require(
                self.reason is not None,
                "unresolved_account_reason_required",
            )


@dataclass(frozen=True, slots=True)
class HolderSnapshotInput:
    snapshot_id: str
    mint: str
    decimals: int
    supply_atomic: int
    supply_context_slot: int
    largest_accounts_context_slot: int
    owners_context_slot: int
    accounts: tuple[HolderAccountObservation, ...]
    event_time: datetime
    observed_at: datetime
    first_reliable_available_at: datetime
    available_to_strategy_at: datetime
    ingested_at: datetime
    source: str
    source_version: str
    revision_number: int
    revision_of: str | None
    raw_event_ids: tuple[str, str, str]

    def __post_init__(self) -> None:
        _require(bool(self.snapshot_id), "snapshot_id_required")
        _require(bool(self.mint), "mint_required")
        _require(
            isinstance(self.decimals, int)
            and not isinstance(self.decimals, bool)
            and 0 <= self.decimals <= 30,
            "decimals_out_of_range",
        )
        _require(
            isinstance(self.supply_atomic, int)
            and not isinstance(self.supply_atomic, bool)
            and self.supply_atomic >= 0,
            "supply_atomic_must_be_nonnegative_integer",
        )
        for name, slot in (
            ("supply", self.supply_context_slot),
            ("largest_accounts", self.largest_accounts_context_slot),
            ("owners", self.owners_context_slot),
        ):
            _require(
                isinstance(slot, int)
                and not isinstance(slot, bool)
                and slot >= 0,
                f"{name}_context_slot_must_be_nonnegative_integer",
            )
        _require(
            1 <= len(self.accounts) <= MAX_LARGEST_ACCOUNTS,
            "largest_account_count_out_of_range",
        )
        token_accounts = [account.token_account for account in self.accounts]
        _require(
            len(token_accounts) == len(set(token_accounts)),
            "duplicate_token_account",
        )
        _require(
            sum(account.amount_atomic for account in self.accounts)
            <= self.supply_atomic,
            "largest_accounts_exceed_supply",
        )
        _require(bool(self.source), "source_required")
        _require(bool(self.source_version), "source_version_required")
        _require(
            isinstance(self.revision_number, int)
            and not isinstance(self.revision_number, bool)
            and self.revision_number >= 1,
            "revision_number_must_be_positive",
        )
        _require(
            self.revision_of is None or self.revision_of != self.snapshot_id,
            "revision_self_reference",
        )
        _require(
            len(set(self.raw_event_ids)) == 3
            and all(bool(value) for value in self.raw_event_ids),
            "three_unique_raw_event_ids_required",
        )
        validate_timestamp_order(
            event_time=self.event_time,
            observed_at=self.observed_at,
            first_reliable_available_at=self.first_reliable_available_at,
            available_to_strategy_at=self.available_to_strategy_at,
            ingested_at=self.ingested_at,
        )


@dataclass(frozen=True, slots=True)
class HolderConcentrationMetrics:
    raw_top_accounts_amount_atomic: int
    raw_top_accounts_supply_share: Decimal | None
    adjusted_top_accounts_supply_share: Decimal | None
    excluded_top_accounts_amount_atomic: int
    unresolved_owner_account_count: int
    unresolved_exclusion_account_count: int
    context_slot_min: int
    context_slot_max: int
    context_slot_spread: int
    exclusion_inventory_evidence_ref: str | None
    availability_class: AvailabilityClass
    quality_flags: tuple[str, ...]


def calculate_holder_metrics(
    snapshot: HolderSnapshotInput,
    assessments: Sequence[ExclusionAssessment],
    *,
    exclusion_inventory_complete: bool,
    excluded_supply_atomic_total: int | None,
    exclusion_inventory_evidence_ref: str | None,
) -> HolderConcentrationMetrics:
    by_account: dict[str, ExclusionAssessment] = {}
    for assessment in assessments:
        _require(
            assessment.token_account not in by_account,
            "duplicate_exclusion_assessment",
        )
        by_account[assessment.token_account] = assessment
    account_ids = {account.token_account for account in snapshot.accounts}
    _require(
        set(by_account).issubset(account_ids),
        "assessment_for_unknown_token_account",
    )

    unresolved = 0
    excluded_top = 0
    included_top = 0
    for account in snapshot.accounts:
        assessment = by_account.get(account.token_account)
        if (
            assessment is None
            or assessment.disposition == ExclusionDisposition.UNRESOLVED
        ):
            unresolved += 1
            continue
        if assessment.disposition == ExclusionDisposition.EXCLUDE:
            excluded_top += account.amount_atomic
        else:
            included_top += account.amount_atomic

    raw_top = sum(account.amount_atomic for account in snapshot.accounts)
    raw_share = (
        Decimal(raw_top) / Decimal(snapshot.supply_atomic)
        if snapshot.supply_atomic > 0
        else None
    )
    adjusted_share: Decimal | None = None
    if exclusion_inventory_complete:
        _require(unresolved == 0, "complete_exclusion_inventory_has_unresolved")
        _require(
            excluded_supply_atomic_total is not None,
            "complete_exclusion_inventory_requires_total",
        )
        _require(
            bool(exclusion_inventory_evidence_ref),
            "complete_exclusion_inventory_requires_evidence_ref",
        )
        _require(
            isinstance(excluded_supply_atomic_total, int)
            and not isinstance(excluded_supply_atomic_total, bool)
            and excluded_top
            <= excluded_supply_atomic_total
            <= snapshot.supply_atomic,
            "excluded_supply_total_out_of_range",
        )
        adjusted_supply = snapshot.supply_atomic - excluded_supply_atomic_total
        adjusted_share = (
            Decimal(included_top) / Decimal(adjusted_supply)
            if adjusted_supply > 0
            else None
        )
    else:
        _require(
            excluded_supply_atomic_total is None,
            "partial_exclusion_inventory_cannot_claim_total",
        )
        _require(
            exclusion_inventory_evidence_ref is None,
            "partial_exclusion_inventory_cannot_claim_evidence_ref",
        )

    unresolved_owners = sum(
        account.owner is None for account in snapshot.accounts
    )
    slots = (
        snapshot.supply_context_slot,
        snapshot.largest_accounts_context_slot,
        snapshot.owners_context_slot,
    )
    flags = [
        "RAW_TOP_ACCOUNTS_CURRENT_SNAPSHOT",
        "EVENT_TIME_PROXY_OBSERVED_AT_NO_BLOCK_TIME",
    ]
    if raw_share is None:
        flags.append("ZERO_SUPPLY_SHARE_UNDEFINED")
    if unresolved_owners:
        flags.append("OWNER_RESOLUTION_PARTIAL")
    if adjusted_share is None:
        flags.append("ADJUSTED_CONCENTRATION_UNAVAILABLE")
    else:
        flags.append(
            "EXCLUSION_INVENTORY_EVIDENCE_REF="
            f"{exclusion_inventory_evidence_ref}"
        )
    if max(slots) != min(slots):
        flags.append("MULTI_SLOT_SNAPSHOT")
    availability = (
        AvailabilityClass.RECONSTRUCTIBLE_CURRENT_SNAPSHOT
        if not unresolved_owners and exclusion_inventory_complete
        else AvailabilityClass.PARTIAL_CURRENT_SNAPSHOT
    )
    return HolderConcentrationMetrics(
        raw_top_accounts_amount_atomic=raw_top,
        raw_top_accounts_supply_share=raw_share,
        adjusted_top_accounts_supply_share=adjusted_share,
        excluded_top_accounts_amount_atomic=excluded_top,
        unresolved_owner_account_count=unresolved_owners,
        unresolved_exclusion_account_count=unresolved,
        context_slot_min=min(slots),
        context_slot_max=max(slots),
        context_slot_spread=max(slots) - min(slots),
        exclusion_inventory_evidence_ref=(
            exclusion_inventory_evidence_ref
        ),
        availability_class=availability,
        quality_flags=tuple(flags),
    )


def _content_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def project_entity_snapshots(
    snapshot: HolderSnapshotInput,
    metrics: HolderConcentrationMetrics,
) -> tuple[EntityInputSnapshot, ...]:
    metric_values: tuple[
        tuple[str, Decimal | None, int | None, str, str], ...
    ] = (
        (
            "raw_top_accounts_amount_atomic",
            None,
            metrics.raw_top_accounts_amount_atomic,
            "token_atomic",
            "RAW_ONCHAIN",
        ),
        (
            "raw_top_accounts_supply_share",
            metrics.raw_top_accounts_supply_share,
            None,
            "ratio",
            "RAW_ONCHAIN",
        ),
        (
            "adjusted_top_accounts_supply_share",
            metrics.adjusted_top_accounts_supply_share,
            None,
            "ratio",
            "DERIVED_ADJUSTED",
        ),
        (
            "unresolved_owner_account_count",
            Decimal(metrics.unresolved_owner_account_count),
            None,
            "count",
            "RAW_ONCHAIN",
        ),
        (
            "context_slot_spread",
            Decimal(metrics.context_slot_spread),
            None,
            "slots",
            "RAW_ONCHAIN",
        ),
    )
    result: list[EntityInputSnapshot] = []
    for metric_name, decimal_value, atomic_value, unit, evidence_class in (
        metric_values
    ):
        business_key = f"{snapshot.mint}:{metric_name}:{snapshot.snapshot_id}"
        row_payload = {
            "snapshot_id": snapshot.snapshot_id,
            "business_key": business_key,
            "mint": snapshot.mint,
            "decimals": snapshot.decimals,
            "metric_name": metric_name,
            "metric_value_decimal": (
                str(decimal_value) if decimal_value is not None else None
            ),
            "metric_value_atomic": atomic_value,
            "unit": unit,
            "evidence_class": evidence_class,
            "event_time": snapshot.event_time.isoformat(),
            "observed_at": snapshot.observed_at.isoformat(),
            "first_reliable_available_at": (
                snapshot.first_reliable_available_at.isoformat()
            ),
            "available_to_strategy_at": (
                snapshot.available_to_strategy_at.isoformat()
            ),
            "ingested_at": snapshot.ingested_at.isoformat(),
            "source": snapshot.source,
            "source_version": snapshot.source_version,
            "revision_number": snapshot.revision_number,
            "revision_of": snapshot.revision_of,
            "exclusion_inventory_evidence_ref": (
                metrics.exclusion_inventory_evidence_ref
            ),
            "raw_event_ids": snapshot.raw_event_ids,
            "quality_flags": metrics.quality_flags,
        }
        content_sha256 = _content_sha256(row_payload)
        row_id = f"entity-{content_sha256}"
        quality_flags = ";".join(
            (f"EVIDENCE_CLASS={evidence_class}", *metrics.quality_flags)
        )
        result.append(
            EntityInputSnapshot(
                entity_snapshot_id=row_id,
                idempotency_key=content_sha256,
                business_key=business_key,
                entity_type=EntityType.HOLDER,
                entity_id=snapshot.mint,
                token_mint=snapshot.mint,
                metric_name=metric_name,
                metric_value_decimal=decimal_value,
                metric_value_atomic=atomic_value,
                unit=unit,
                amount_decimals=(
                    snapshot.decimals if atomic_value is not None else None
                ),
                event_time=snapshot.event_time,
                observed_at=snapshot.observed_at,
                available_to_strategy_at=snapshot.available_to_strategy_at,
                ingested_at=snapshot.ingested_at,
                first_reliable_available_at=(
                    snapshot.first_reliable_available_at
                ),
                source=snapshot.source,
                source_version=snapshot.source_version,
                schema_version=CONTRACT_VERSION,
                revision_number=snapshot.revision_number,
                revision_of=snapshot.revision_of,
                raw_event_id=";".join(snapshot.raw_event_ids),
                content_sha256=content_sha256,
                quality_flags=quality_flags,
            )
        )
    return tuple(result)


def validate_durable_metadata(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _require(isinstance(key, str), "durable_metadata_key_must_be_text")
            _require(
                _normalize_key(key) not in _SENSITIVE_KEYS,
                "sensitive_key_forbidden",
            )
            validate_durable_metadata(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            validate_durable_metadata(item)
        return
    if isinstance(value, str):
        _require(
            _WINDOWS_ABSOLUTE_RE.match(value) is None
            and not value.startswith(("/home/", "/Users/")),
            "absolute_machine_path_forbidden",
        )


def assert_atom2_offline_boundary(
    *,
    provider_calls: int,
    credentials_used: int,
    cash_spend_usd_cents: int,
    wallet_signer_transaction_actions: int,
) -> None:
    checks = (
        (provider_calls == 0, "provider_calls_forbidden_in_atom2"),
        (credentials_used == 0, "credentials_forbidden_in_atom2"),
        (cash_spend_usd_cents == 0, "cash_spend_forbidden_in_atom2"),
        (
            wallet_signer_transaction_actions == 0,
            "wallet_signer_transaction_actions_forbidden_in_atom2",
        ),
    )
    for condition, message in checks:
        if not condition:
            raise OfflineBoundaryError(message)


def compile_entity_contract(document: Mapping[str, Any]) -> None:
    _require(
        document.get("schema")
        == "solana_alpha_lab.entity_input_observation_contract",
        "schema_drift",
    )
    _require(
        document.get("schema_version") == CONTRACT_VERSION,
        "version_drift",
    )
    _require(document.get("task_id") == "TASK-11", "task_id_drift")
    _require(document.get("atom_id") == "T11-A2", "atom_id_drift")
    _require(document.get("as_of") == CONTRACT_AS_OF, "as_of_drift")
    evidence = document.get("evidence_classes")
    _require(isinstance(evidence, list), "evidence_classes_must_be_list")
    _require(
        all(isinstance(item, Mapping) for item in evidence),
        "evidence_class_item_must_be_mapping",
    )
    _require(
        tuple(item.get("class") for item in evidence)
        == EXPECTED_EVIDENCE_CLASSES,
        "evidence_class_inventory_or_order_drift",
    )
    provider = document.get("primary_provider")
    _require(isinstance(provider, Mapping), "primary_provider_must_be_mapping")
    _require(provider.get("provider_id") == PRIMARY_PROVIDER, "provider_drift")
    _require(
        tuple(provider.get("methods", ())) == PRIMARY_METHODS,
        "primary_method_inventory_or_order_drift",
    )
    authority = document.get("authority")
    _require(isinstance(authority, Mapping), "authority_must_be_mapping")
    _require(
        tuple(authority.get("managed_files", ())) == EXPECTED_MANAGED_FILES,
        "managed_file_inventory_or_order_drift",
    )
    _require(
        authority.get("network_calls") == 0
        and authority.get("provider_api_rpc_wss_calls") == 0
        and authority.get("cash_spend_usd_cents") == 0,
        "offline_authority_drift",
    )
    metrics = document.get("projection_metrics")
    _require(
        tuple(metrics) == EXPECTED_METRICS,
        "projection_metric_inventory_or_order_drift",
    )
    validate_durable_metadata(document)


def load_frozen_entity_contract(path: Path) -> Mapping[str, Any]:
    fixture_bytes = path.read_bytes()
    _require(
        hashlib.sha256(fixture_bytes).hexdigest() == FROZEN_FIXTURE_SHA256,
        "fixture_sha256_drift",
    )
    try:
        document = json.loads(fixture_bytes)
    except json.JSONDecodeError as exc:
        raise EntityInputContractError("fixture_json_invalid") from exc
    _require(isinstance(document, Mapping), "fixture_root_must_be_mapping")
    compile_entity_contract(document)
    return document
