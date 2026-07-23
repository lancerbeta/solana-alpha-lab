"""Strict Pydantic v2 boundary models for TASK-05 canonical schema v1."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Hash64 = Annotated[
    str,
    Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Decimals = Annotated[int, Field(ge=0, le=30)]
Confidence = Annotated[Decimal, Field(ge=0, le=1)]


class StrictContractModel(BaseModel):
    """No coercion, no undeclared fields and no mutation after validation."""

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        use_enum_values=True,
    )


class RawResponseStatus(StrEnum):
    SUCCESS = "SUCCESS"
    HTTP_ERROR = "HTTP_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"
    INVALID_RESPONSE = "INVALID_RESPONSE"


class LifecycleState(StrEnum):
    DISCOVERED = "DISCOVERED"
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    MIGRATION_STARTED = "MIGRATION_STARTED"
    MIGRATED = "MIGRATED"
    INACTIVE = "INACTIVE"
    UNKNOWN = "UNKNOWN"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class EntityType(StrEnum):
    HOLDER = "HOLDER"
    DEPLOYER = "DEPLOYER"
    WALLET = "WALLET"
    CLUSTER = "CLUSTER"
    UNKNOWN = "UNKNOWN"


class SignalDecision(StrEnum):
    ENTER = "ENTER"
    EXIT = "EXIT"
    HOLD = "HOLD"
    REJECT = "REJECT"


class QuoteStatus(StrEnum):
    QUOTE_AVAILABLE = "QUOTE_AVAILABLE"
    NO_ROUTE = "NO_ROUTE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    TIMEOUT = "TIMEOUT"


class ExecutionTerminalState(StrEnum):
    REJECTED_BEFORE_SEND = "REJECTED_BEFORE_SEND"
    DROPPED_OR_EXPIRED_NOT_PROCESSED = "DROPPED_OR_EXPIRED_NOT_PROCESSED"
    LANDED_FAILED = "LANDED_FAILED"
    LANDED_SUCCESS = "LANDED_SUCCESS"
    UNKNOWN_REQUIRES_RECONCILIATION = "UNKNOWN_REQUIRES_RECONCILIATION"


class OutcomeType(StrEnum):
    TOUCH_RETURN = "TouchReturn"
    FILLABLE_RETURN = "FillableReturn"
    REALIZED_VWAP_RETURN = "RealizedVWAPReturn"
    NET_RETURN = "NetReturn"
    PATH_RISK = "PathRisk"


class InventoryState(StrEnum):
    FLAT = "FLAT"
    OPEN = "OPEN"
    UNRESOLVED_REQUIRES_RECOVERY = "UNRESOLVED_REQUIRES_RECOVERY"
    RECOVERED = "RECOVERED"


class MigrationKind(StrEnum):
    DDL = "DDL"
    DATA_BACKFILL = "DATA_BACKFILL"
    REBUILD = "REBUILD"
    REPAIR = "REPAIR"


class ApplicationState(StrEnum):
    DECLARED = "DECLARED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


class FailedExitState(StrEnum):
    NO_ROUTE = "NO_ROUTE"
    EXIT_FAILED = "EXIT_FAILED"
    UNKNOWN_REQUIRES_RECONCILIATION = "UNKNOWN_REQUIRES_RECONCILIATION"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_revision(
    row_id: str,
    revision_number: int,
    revision_of: str | None,
) -> None:
    _require(revision_number >= 1, "revision_number_must_be_positive")
    _require(revision_of is None or revision_of != row_id, "revision_self_reference")


def _validate_availability(
    first_reliable_available_at: datetime,
    available_to_strategy_at: datetime,
) -> None:
    _require(
        first_reliable_available_at <= available_to_strategy_at,
        "first_reliable_availability_after_strategy_availability",
    )


class RawApiEvent(StrictContractModel):
    raw_event_id: str
    idempotency_key: str
    source: str
    source_version: str
    endpoint_or_method: str
    request_hash: Hash64
    response_status: RawResponseStatus
    error_class: str | None
    redacted_body: bytes
    content_sha256: Hash64
    redaction_version: str
    event_time: AwareDatetime | None
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    provider_version: str | None
    schema_version: str
    protocol_version: str | None
    revision_number: PositiveInt
    revision_of: str | None
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> RawApiEvent:
        _require(bool(self.raw_event_id), "raw_event_id_empty")
        _require(bool(self.idempotency_key), "idempotency_key_empty")
        _validate_revision(
            self.raw_event_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        if self.response_status == RawResponseStatus.SUCCESS:
            _require(self.error_class is None, "success_cannot_have_error")
        else:
            _require(self.error_class is not None, "error_status_requires_error")
        return self


class CanonicalObservation(StrictContractModel):
    observation_id: str
    idempotency_key: str
    business_key: str
    entity_type: str
    entity_id: str
    observation_type: str
    value_decimal: Decimal | None
    value_atomic: NonNegativeInt | None
    unit: str | None
    amount_mint: str | None
    amount_decimals: Decimals | None
    event_time: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    source: str
    source_version: str
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    raw_event_id: str | None
    content_sha256: Hash64
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> CanonicalObservation:
        _require(bool(self.observation_id), "observation_id_empty")
        _require(bool(self.idempotency_key), "idempotency_key_empty")
        _require(bool(self.business_key), "business_key_empty")
        _validate_revision(
            self.observation_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        if self.value_atomic is None:
            _require(
                self.amount_mint is None and self.amount_decimals is None,
                "missing_atomic_amount_requires_missing_provenance",
            )
        else:
            _require(
                self.amount_mint is not None and self.amount_decimals is not None,
                "atomic_amount_requires_mint_and_decimals",
            )
        return self


class TokenLifecycleEvent(StrictContractModel):
    lifecycle_event_id: str
    idempotency_key: str
    business_key: str
    token_mint: str
    lifecycle_state: LifecycleState
    related_pool_id: str | None
    migrated_to_program: str | None
    migrated_to_pool_id: str | None
    event_time: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    source: str
    source_version: str
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    raw_event_id: str | None
    content_sha256: Hash64
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> TokenLifecycleEvent:
        _validate_revision(
            self.lifecycle_event_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        if self.lifecycle_state == LifecycleState.MIGRATED:
            _require(
                self.migrated_to_program is not None
                and self.migrated_to_pool_id is not None,
                "migrated_state_requires_destination",
            )
        return self


class PoolStateSnapshot(StrictContractModel):
    pool_snapshot_id: str
    idempotency_key: str
    business_key: str
    pool_id: str
    base_mint: str
    quote_mint: str
    base_decimals: Decimals
    quote_decimals: Decimals
    base_reserve_atomic: NonNegativeInt | None
    quote_reserve_atomic: NonNegativeInt | None
    context_slot: NonNegativeInt | None
    event_time: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    source: str
    source_version: str
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    raw_event_id: str | None
    content_sha256: Hash64
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> PoolStateSnapshot:
        _require(self.base_mint != self.quote_mint, "pool_mints_must_differ")
        _validate_revision(
            self.pool_snapshot_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        return self


class TradeOrderflowInput(StrictContractModel):
    trade_input_id: str
    idempotency_key: str
    business_key: str
    pool_id: str
    side: Side
    input_mint: str
    input_amount_atomic: NonNegativeInt
    input_decimals: Decimals
    output_mint: str
    output_amount_atomic: NonNegativeInt
    output_decimals: Decimals
    trader_entity_id: str | None
    transaction_signature: str | None
    context_slot: NonNegativeInt | None
    event_time: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    source: str
    source_version: str
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    raw_event_id: str | None
    content_sha256: Hash64
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> TradeOrderflowInput:
        _require(self.input_mint != self.output_mint, "trade_mints_must_differ")
        _validate_revision(
            self.trade_input_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        return self


class EntityInputSnapshot(StrictContractModel):
    entity_snapshot_id: str
    idempotency_key: str
    business_key: str
    entity_type: EntityType
    entity_id: str
    token_mint: str | None
    metric_name: str
    metric_value_decimal: Decimal | None
    metric_value_atomic: NonNegativeInt | None
    unit: str | None
    amount_decimals: Decimals | None
    event_time: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    source: str
    source_version: str
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    raw_event_id: str | None
    content_sha256: Hash64
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> EntityInputSnapshot:
        _validate_revision(
            self.entity_snapshot_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        if self.metric_value_atomic is not None:
            _require(
                self.token_mint is not None and self.amount_decimals is not None,
                "atomic_metric_requires_mint_and_decimals",
            )
        return self


class FeatureObservation(StrictContractModel):
    feature_observation_id: str
    idempotency_key: str
    business_key: str
    entity_type: str
    entity_id: str
    feature_name: str
    feature_version: str
    value_decimal: Decimal | None
    unit: str | None
    event_time: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    source: str
    source_version: str
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    lineage_dataset_id: str
    lineage_dataset_version: str
    lineage_fingerprint: Hash64
    content_sha256: Hash64
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> FeatureObservation:
        _validate_revision(
            self.feature_observation_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        return self


class RegimeObservation(StrictContractModel):
    regime_observation_id: str
    idempotency_key: str
    business_key: str
    regime_name: str
    regime_version: str
    regime_state: str
    confidence_decimal: Confidence | None
    event_time: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    source: str
    source_version: str
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    lineage_fingerprint: Hash64
    content_sha256: Hash64
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> RegimeObservation:
        _validate_revision(
            self.regime_observation_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        return self


class SignalDecisionEvent(StrictContractModel):
    signal_decision_id: str
    idempotency_key: str
    business_key: str
    strategy_id: str
    strategy_version: str
    entity_id: str
    decision: SignalDecision
    side: Side | None
    decision_as_of: AwareDatetime
    event_time: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    source: str
    source_version: str
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    feature_set_fingerprint: Hash64
    content_sha256: Hash64
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> SignalDecisionEvent:
        if self.decision in {SignalDecision.ENTER, SignalDecision.EXIT}:
            _require(self.side is not None, "action_decision_requires_side")
        else:
            _require(self.side is None, "non_action_decision_forbids_side")
        _require(
            self.available_to_strategy_at <= self.decision_as_of,
            "decision_uses_future_availability",
        )
        _validate_revision(
            self.signal_decision_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        return self


class QuoteAttempt(StrictContractModel):
    quote_attempt_id: str
    idempotency_key: str
    business_key: str
    request_hash: Hash64
    provider: str
    provider_version: str
    side: Side
    input_mint: str
    input_requested_atomic: NonNegativeInt
    input_decimals: Decimals
    output_mint: str
    output_quoted_atomic: NonNegativeInt | None
    output_decimals: Decimals
    route_id: str | None
    route_count: NonNegativeInt | None
    context_slot: NonNegativeInt | None
    requested_at: AwareDatetime
    response_at: AwareDatetime | None
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    quote_age_ms: NonNegativeInt | None
    provider_latency_ms: NonNegativeInt | None
    provider_fee_atomic: NonNegativeInt | None
    platform_fee_atomic: NonNegativeInt | None
    fee_mint: str | None
    included_in_output_amount: bool | None
    status: QuoteStatus
    error_class: str | None
    raw_event_id: str
    response_content_sha256: Hash64
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> QuoteAttempt:
        _require(self.input_mint != self.output_mint, "quote_mints_must_differ")
        _validate_revision(
            self.quote_attempt_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        if self.response_at is not None:
            _require(
                self.response_at >= self.requested_at,
                "response_before_request",
            )
        fees_absent = (
            self.provider_fee_atomic is None
            and self.platform_fee_atomic is None
            and self.fee_mint is None
            and self.included_in_output_amount is None
        )
        fees_present = (
            (
                self.provider_fee_atomic is not None
                or self.platform_fee_atomic is not None
            )
            and self.fee_mint is not None
            and self.included_in_output_amount is not None
        )
        _require(fees_absent or fees_present, "quote_fee_provenance_incoherent")

        if self.status == QuoteStatus.QUOTE_AVAILABLE:
            _require(
                self.output_quoted_atomic is not None
                and self.route_id is not None
                and self.route_count is not None
                and self.route_count > 0
                and self.response_at is not None
                and self.error_class is None,
                "quote_available_state_incoherent",
            )
        elif self.status == QuoteStatus.NO_ROUTE:
            _require(
                self.output_quoted_atomic is None
                and self.route_id is None
                and self.route_count == 0
                and self.response_at is not None
                and self.error_class is None,
                "no_route_state_incoherent",
            )
        else:
            _require(
                self.output_quoted_atomic is None
                and self.route_id is None
                and self.route_count in {None, 0}
                and self.error_class is not None,
                "quote_error_state_incoherent",
            )
        return self


class ExecutionAttempt(StrictContractModel):
    execution_attempt_id: str
    idempotency_key: str
    business_key: str
    quote_attempt_id: str | None
    signal_decision_id: str | None
    side: Side
    input_mint: str
    requested_input_atomic: NonNegativeInt
    input_decimals: Decimals
    output_mint: str
    output_decimals: Decimals
    submitted_at: AwareDatetime | None
    terminal_at: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    terminal_state: ExecutionTerminalState
    processed_on_chain: bool | None
    transaction_signature: str | None
    realized_input_atomic: NonNegativeInt | None
    realized_output_atomic: NonNegativeInt | None
    actual_network_fee_lamports: NonNegativeInt | None
    actual_relay_tip_lamports: NonNegativeInt | None
    actual_ata_rent_lamports: NonNegativeInt | None
    fee_payer_mint: str | None
    error_class: str | None
    reconciliation_reference: str | None
    source: str
    source_version: str
    content_sha256: Hash64
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    raw_event_id: str | None
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> ExecutionAttempt:
        _require(
            self.input_mint != self.output_mint,
            "execution_mints_must_differ",
        )
        if self.submitted_at is not None:
            _require(self.terminal_at >= self.submitted_at, "terminal_before_submit")
        _require(
            self.observed_at <= self.available_to_strategy_at,
            "execution_available_before_observed",
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        _validate_revision(
            self.execution_attempt_id,
            self.revision_number,
            self.revision_of,
        )

        if self.terminal_state == ExecutionTerminalState.REJECTED_BEFORE_SEND:
            valid = (
                self.submitted_at is None
                and self.processed_on_chain is False
                and self.transaction_signature is None
                and self.realized_input_atomic is None
                and self.realized_output_atomic is None
                and self.actual_network_fee_lamports is None
                and self.actual_relay_tip_lamports is None
                and self.actual_ata_rent_lamports is None
                and self.fee_payer_mint is None
                and self.error_class is not None
                and self.reconciliation_reference is None
            )
        elif (
            self.terminal_state
            == ExecutionTerminalState.DROPPED_OR_EXPIRED_NOT_PROCESSED
        ):
            valid = (
                self.submitted_at is not None
                and self.processed_on_chain is False
                and self.transaction_signature is not None
                and self.realized_input_atomic is None
                and self.realized_output_atomic is None
                and self.actual_network_fee_lamports is None
                and self.actual_relay_tip_lamports is None
                and self.actual_ata_rent_lamports is None
                and self.fee_payer_mint is None
                and self.error_class is not None
                and self.reconciliation_reference is None
            )
        elif self.terminal_state == ExecutionTerminalState.LANDED_FAILED:
            valid = (
                self.submitted_at is not None
                and self.processed_on_chain is True
                and self.transaction_signature is not None
                and self.realized_input_atomic is None
                and self.realized_output_atomic is None
                and self.actual_network_fee_lamports is not None
                and self.fee_payer_mint is not None
                and self.error_class is not None
                and self.reconciliation_reference is None
            )
        elif self.terminal_state == ExecutionTerminalState.LANDED_SUCCESS:
            valid = (
                self.submitted_at is not None
                and self.processed_on_chain is True
                and self.transaction_signature is not None
                and self.realized_input_atomic is not None
                and self.realized_output_atomic is not None
                and self.actual_network_fee_lamports is not None
                and self.fee_payer_mint is not None
                and self.error_class is None
                and self.reconciliation_reference is None
            )
        else:
            valid = (
                self.submitted_at is not None
                and self.processed_on_chain is None
                and self.transaction_signature is not None
                and self.realized_input_atomic is None
                and self.realized_output_atomic is None
                and self.actual_network_fee_lamports is None
                and self.actual_relay_tip_lamports is None
                and self.actual_ata_rent_lamports is None
                and self.fee_payer_mint is None
                and self.error_class is not None
                and self.reconciliation_reference is not None
            )
        _require(valid, "execution_terminal_state_incoherent")
        return self


class StrategyOutcome(StrictContractModel):
    strategy_outcome_id: str
    idempotency_key: str
    business_key: str
    strategy_id: str
    strategy_version: str
    position_id: str
    outcome_type: OutcomeType
    outcome_value_decimal: Decimal | None
    outcome_unit: str | None
    measured_as_of: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    inventory_state: InventoryState
    remaining_inventory_atomic: NonNegativeInt
    remaining_inventory_mint: str | None
    remaining_inventory_decimals: Decimals | None
    last_executable_liquidation_quote_id: str | None
    recovery_lower_bound_decimal: Decimal | None
    recovery_upper_bound_decimal: Decimal | None
    recovery_unit: str | None
    recovery_currency_or_mint: str | None
    failed_exit_state: FailedExitState | None
    source: str
    source_version: str
    schema_version: str
    revision_number: PositiveInt
    revision_of: str | None
    content_sha256: Hash64
    quality_flags: str | None

    @model_validator(mode="after")
    def validate_state(self) -> StrategyOutcome:
        _validate_revision(
            self.strategy_outcome_id,
            self.revision_number,
            self.revision_of,
        )
        _validate_availability(
            self.first_reliable_available_at,
            self.available_to_strategy_at,
        )
        _require(
            self.measured_as_of <= self.available_to_strategy_at,
            "outcome_available_before_measurement_cutoff",
        )
        if self.inventory_state in {InventoryState.FLAT, InventoryState.RECOVERED}:
            valid = (
                self.remaining_inventory_atomic == 0
                and self.remaining_inventory_mint is None
                and self.remaining_inventory_decimals is None
                and self.recovery_lower_bound_decimal is None
                and self.recovery_upper_bound_decimal is None
                and self.recovery_unit is None
                and self.recovery_currency_or_mint is None
                and self.failed_exit_state is None
            )
        elif self.inventory_state == InventoryState.OPEN:
            valid = (
                self.remaining_inventory_atomic > 0
                and self.remaining_inventory_mint is not None
                and self.remaining_inventory_decimals is not None
                and self.recovery_lower_bound_decimal is None
                and self.recovery_upper_bound_decimal is None
                and self.recovery_unit is None
                and self.recovery_currency_or_mint is None
                and self.failed_exit_state is None
            )
        else:
            valid = (
                self.remaining_inventory_atomic > 0
                and self.remaining_inventory_mint is not None
                and self.remaining_inventory_decimals is not None
                and self.recovery_lower_bound_decimal is not None
                and self.recovery_upper_bound_decimal is not None
                and self.recovery_lower_bound_decimal
                <= self.recovery_upper_bound_decimal
                and self.recovery_unit is not None
                and self.recovery_currency_or_mint is not None
                and self.failed_exit_state is not None
            )
        _require(valid, "strategy_inventory_state_incoherent")
        return self


class DatasetManifest(StrictContractModel):
    dataset_manifest_id: str
    dataset_id: str
    dataset_version: str
    schema_id: str
    schema_sha256: Hash64
    dataset_fingerprint: Hash64
    generation_task_id: str
    generation_run_id: str
    validation_receipt_sha256: Hash64
    first_reliable_available_at: AwareDatetime
    created_at: AwareDatetime
    content_sha256: Hash64

    @model_validator(mode="after")
    def validate_state(self) -> DatasetManifest:
        _require(
            self.first_reliable_available_at >= self.created_at,
            "dataset_reliable_before_creation",
        )
        return self


class PartitionManifest(StrictContractModel):
    partition_manifest_id: str
    dataset_manifest_id: str
    partition_id: str
    logical_location: str
    file_sha256: Hash64
    content_sha256: Hash64
    row_count: NonNegativeInt
    min_event_time: AwareDatetime | None
    max_event_time: AwareDatetime | None
    min_available_to_strategy_at: AwareDatetime | None
    max_available_to_strategy_at: AwareDatetime | None
    first_reliable_available_at: AwareDatetime
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_state(self) -> PartitionManifest:
        _require(bool(self.logical_location), "logical_location_empty")
        _require(
            (self.min_event_time is None and self.max_event_time is None)
            or (
                self.min_event_time is not None
                and self.max_event_time is not None
                and self.min_event_time <= self.max_event_time
            ),
            "event_bounds_incoherent",
        )
        _require(
            (
                self.min_available_to_strategy_at is None
                and self.max_available_to_strategy_at is None
            )
            or (
                self.min_available_to_strategy_at is not None
                and self.max_available_to_strategy_at is not None
                and self.min_available_to_strategy_at
                <= self.max_available_to_strategy_at
            ),
            "availability_bounds_incoherent",
        )
        _require(
            self.first_reliable_available_at >= self.created_at,
            "partition_reliable_before_creation",
        )
        return self


class MigrationManifest(StrictContractModel):
    migration_manifest_id: str
    migration_id: str
    migration_order: PositiveInt
    migration_kind: MigrationKind
    schema_version: str
    content_sha256: Hash64
    supersedes_migration_id: str | None
    application_state: ApplicationState
    applied_at: AwareDatetime | None
    application_receipt_sha256: Hash64 | None
    first_reliable_available_at: AwareDatetime
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_state(self) -> MigrationManifest:
        _require(
            self.supersedes_migration_id is None
            or self.supersedes_migration_id != self.migration_id,
            "migration_self_supersedes",
        )
        if self.application_state == ApplicationState.DECLARED:
            _require(
                self.applied_at is None
                and self.application_receipt_sha256 is None,
                "declared_migration_has_application_evidence",
            )
        else:
            _require(
                self.applied_at is not None
                and self.application_receipt_sha256 is not None,
                "terminal_migration_missing_application_evidence",
            )
        _require(
            self.first_reliable_available_at >= self.created_at,
            "migration_reliable_before_creation",
        )
        return self


RELATION_MODELS: dict[str, type[StrictContractModel]] = {
    "raw_api_events": RawApiEvent,
    "canonical_observations": CanonicalObservation,
    "token_lifecycle_events": TokenLifecycleEvent,
    "pool_state_snapshots": PoolStateSnapshot,
    "trade_orderflow_inputs": TradeOrderflowInput,
    "entity_input_snapshots": EntityInputSnapshot,
    "feature_observations": FeatureObservation,
    "regime_observations": RegimeObservation,
    "signal_decision_events": SignalDecisionEvent,
    "quote_attempts": QuoteAttempt,
    "execution_attempts": ExecutionAttempt,
    "strategy_outcomes": StrategyOutcome,
    "dataset_manifests": DatasetManifest,
    "partition_manifests": PartitionManifest,
    "migration_manifests": MigrationManifest,
}

RELATION_INSERTION_ORDER: tuple[str, ...] = tuple(RELATION_MODELS)


def validate_relation_json(
    relation: str,
    payload: str | bytes,
) -> StrictContractModel:
    """Validate one exact JSON row against its relation boundary model."""

    try:
        model = RELATION_MODELS[relation]
    except KeyError as exc:
        raise ValueError(f"unknown_relation:{relation}") from exc
    return model.model_validate_json(payload)


def duckdb_row(model: StrictContractModel) -> dict[str, object]:
    """Return typed Python values suitable for parameterized DuckDB insertion."""

    return model.model_dump(mode="python")
