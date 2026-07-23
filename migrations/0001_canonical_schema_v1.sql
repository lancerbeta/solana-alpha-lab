-- TASK-05 Atom 2: DuckDB v1 rebuildable projection contract.
-- Durable truth is immutable Parquet plus manifests; this schema is single-writer.

CREATE TABLE raw_api_events (
    raw_event_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    endpoint_or_method VARCHAR NOT NULL,
    request_hash VARCHAR NOT NULL,
    response_status VARCHAR NOT NULL,
    error_class VARCHAR,
    redacted_body BLOB NOT NULL,
    content_sha256 VARCHAR NOT NULL,
    redaction_version VARCHAR NOT NULL,
    event_time TIMESTAMPTZ,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    provider_version VARCHAR,
    schema_version VARCHAR NOT NULL,
    protocol_version VARCHAR,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    quality_flags VARCHAR,
    CHECK (raw_event_id <> ''),
    CHECK (idempotency_key <> ''),
    CHECK (length(request_hash) = 64),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> raw_event_id),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    CHECK ((
        (response_status = 'SUCCESS' AND error_class IS NULL)
        OR
        (response_status IN ('HTTP_ERROR', 'PROVIDER_ERROR', 'TIMEOUT', 'INVALID_RESPONSE')
         AND error_class IS NOT NULL)
    ) IS TRUE),
    FOREIGN KEY (revision_of) REFERENCES raw_api_events(raw_event_id)
);

CREATE TABLE canonical_observations (
    observation_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    entity_type VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    observation_type VARCHAR NOT NULL,
    value_decimal DECIMAL(38, 18),
    value_atomic HUGEINT,
    unit VARCHAR,
    amount_mint VARCHAR,
    amount_decimals INTEGER,
    event_time TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    raw_event_id VARCHAR,
    content_sha256 VARCHAR NOT NULL,
    quality_flags VARCHAR,
    CHECK (observation_id <> ''),
    CHECK (idempotency_key <> ''),
    CHECK (business_key <> ''),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> observation_id),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    CHECK ((
        (value_atomic IS NULL AND amount_mint IS NULL AND amount_decimals IS NULL)
        OR
        (value_atomic IS NOT NULL AND value_atomic >= 0 AND amount_mint IS NOT NULL
         AND amount_decimals BETWEEN 0 AND 30)
    ) IS TRUE),
    FOREIGN KEY (revision_of) REFERENCES canonical_observations(observation_id),
    FOREIGN KEY (raw_event_id) REFERENCES raw_api_events(raw_event_id)
);

CREATE TABLE token_lifecycle_events (
    lifecycle_event_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    token_mint VARCHAR NOT NULL,
    lifecycle_state VARCHAR NOT NULL,
    related_pool_id VARCHAR,
    migrated_to_program VARCHAR,
    migrated_to_pool_id VARCHAR,
    event_time TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    raw_event_id VARCHAR,
    content_sha256 VARCHAR NOT NULL,
    quality_flags VARCHAR,
    CHECK (lifecycle_state IN ('DISCOVERED', 'CREATED', 'ACTIVE', 'MIGRATION_STARTED',
                               'MIGRATED', 'INACTIVE', 'UNKNOWN')),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> lifecycle_event_id),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    CHECK ((
        lifecycle_state <> 'MIGRATED'
        OR (migrated_to_program IS NOT NULL AND migrated_to_pool_id IS NOT NULL)
    ) IS TRUE),
    FOREIGN KEY (revision_of) REFERENCES token_lifecycle_events(lifecycle_event_id),
    FOREIGN KEY (raw_event_id) REFERENCES raw_api_events(raw_event_id)
);

CREATE TABLE pool_state_snapshots (
    pool_snapshot_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    pool_id VARCHAR NOT NULL,
    base_mint VARCHAR NOT NULL,
    quote_mint VARCHAR NOT NULL,
    base_decimals INTEGER NOT NULL,
    quote_decimals INTEGER NOT NULL,
    base_reserve_atomic HUGEINT,
    quote_reserve_atomic HUGEINT,
    context_slot UBIGINT,
    event_time TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    raw_event_id VARCHAR,
    content_sha256 VARCHAR NOT NULL,
    quality_flags VARCHAR,
    CHECK (base_mint <> quote_mint),
    CHECK (base_decimals BETWEEN 0 AND 30),
    CHECK (quote_decimals BETWEEN 0 AND 30),
    CHECK (base_reserve_atomic IS NULL OR base_reserve_atomic >= 0),
    CHECK (quote_reserve_atomic IS NULL OR quote_reserve_atomic >= 0),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> pool_snapshot_id),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    FOREIGN KEY (revision_of) REFERENCES pool_state_snapshots(pool_snapshot_id),
    FOREIGN KEY (raw_event_id) REFERENCES raw_api_events(raw_event_id)
);

CREATE TABLE trade_orderflow_inputs (
    trade_input_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    pool_id VARCHAR NOT NULL,
    side VARCHAR NOT NULL,
    input_mint VARCHAR NOT NULL,
    input_amount_atomic HUGEINT NOT NULL,
    input_decimals INTEGER NOT NULL,
    output_mint VARCHAR NOT NULL,
    output_amount_atomic HUGEINT NOT NULL,
    output_decimals INTEGER NOT NULL,
    trader_entity_id VARCHAR,
    transaction_signature VARCHAR,
    context_slot UBIGINT,
    event_time TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    raw_event_id VARCHAR,
    content_sha256 VARCHAR NOT NULL,
    quality_flags VARCHAR,
    CHECK (side IN ('BUY', 'SELL')),
    CHECK (input_mint <> output_mint),
    CHECK (input_amount_atomic >= 0),
    CHECK (output_amount_atomic >= 0),
    CHECK (input_decimals BETWEEN 0 AND 30),
    CHECK (output_decimals BETWEEN 0 AND 30),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> trade_input_id),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    FOREIGN KEY (revision_of) REFERENCES trade_orderflow_inputs(trade_input_id),
    FOREIGN KEY (raw_event_id) REFERENCES raw_api_events(raw_event_id)
);

CREATE TABLE entity_input_snapshots (
    entity_snapshot_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    entity_type VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    token_mint VARCHAR,
    metric_name VARCHAR NOT NULL,
    metric_value_decimal DECIMAL(38, 18),
    metric_value_atomic HUGEINT,
    unit VARCHAR,
    amount_decimals INTEGER,
    event_time TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    raw_event_id VARCHAR,
    content_sha256 VARCHAR NOT NULL,
    quality_flags VARCHAR,
    CHECK (entity_type IN ('HOLDER', 'DEPLOYER', 'WALLET', 'CLUSTER', 'UNKNOWN')),
    CHECK (metric_value_atomic IS NULL OR metric_value_atomic >= 0),
    CHECK (amount_decimals IS NULL OR amount_decimals BETWEEN 0 AND 30),
    CHECK ((
        metric_value_atomic IS NULL
        OR (token_mint IS NOT NULL AND amount_decimals IS NOT NULL)
    ) IS TRUE),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> entity_snapshot_id),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    FOREIGN KEY (revision_of) REFERENCES entity_input_snapshots(entity_snapshot_id),
    FOREIGN KEY (raw_event_id) REFERENCES raw_api_events(raw_event_id)
);

CREATE TABLE feature_observations (
    feature_observation_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    entity_type VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    feature_name VARCHAR NOT NULL,
    feature_version VARCHAR NOT NULL,
    value_decimal DECIMAL(38, 18),
    unit VARCHAR,
    event_time TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    lineage_dataset_id VARCHAR NOT NULL,
    lineage_dataset_version VARCHAR NOT NULL,
    lineage_fingerprint VARCHAR NOT NULL,
    content_sha256 VARCHAR NOT NULL,
    quality_flags VARCHAR,
    CHECK (length(lineage_fingerprint) = 64),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> feature_observation_id),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    FOREIGN KEY (revision_of) REFERENCES feature_observations(feature_observation_id)
);

CREATE TABLE regime_observations (
    regime_observation_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    regime_name VARCHAR NOT NULL,
    regime_version VARCHAR NOT NULL,
    regime_state VARCHAR NOT NULL,
    confidence_decimal DECIMAL(9, 8),
    event_time TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    lineage_fingerprint VARCHAR NOT NULL,
    content_sha256 VARCHAR NOT NULL,
    quality_flags VARCHAR,
    CHECK (confidence_decimal IS NULL
           OR (confidence_decimal >= 0 AND confidence_decimal <= 1)),
    CHECK (length(lineage_fingerprint) = 64),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> regime_observation_id),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    FOREIGN KEY (revision_of) REFERENCES regime_observations(regime_observation_id)
);

CREATE TABLE signal_decision_events (
    signal_decision_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    strategy_id VARCHAR NOT NULL,
    strategy_version VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    decision VARCHAR NOT NULL,
    side VARCHAR,
    decision_as_of TIMESTAMPTZ NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    feature_set_fingerprint VARCHAR NOT NULL,
    content_sha256 VARCHAR NOT NULL,
    quality_flags VARCHAR,
    CHECK (decision IN ('ENTER', 'EXIT', 'HOLD', 'REJECT')),
    CHECK ((
        (decision IN ('ENTER', 'EXIT') AND side IN ('BUY', 'SELL'))
        OR (decision IN ('HOLD', 'REJECT') AND side IS NULL)
    ) IS TRUE),
    CHECK (available_to_strategy_at <= decision_as_of),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    CHECK (length(feature_set_fingerprint) = 64),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> signal_decision_id),
    FOREIGN KEY (revision_of) REFERENCES signal_decision_events(signal_decision_id)
);

CREATE TABLE quote_attempts (
    quote_attempt_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    request_hash VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    provider_version VARCHAR NOT NULL,
    side VARCHAR NOT NULL,
    input_mint VARCHAR NOT NULL,
    input_requested_atomic HUGEINT NOT NULL,
    input_decimals INTEGER NOT NULL,
    output_mint VARCHAR NOT NULL,
    output_quoted_atomic HUGEINT,
    output_decimals INTEGER NOT NULL,
    route_id VARCHAR,
    route_count INTEGER,
    context_slot UBIGINT,
    requested_at TIMESTAMPTZ NOT NULL,
    response_at TIMESTAMPTZ,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    quote_age_ms BIGINT,
    provider_latency_ms BIGINT,
    provider_fee_atomic HUGEINT,
    platform_fee_atomic HUGEINT,
    fee_mint VARCHAR,
    included_in_output_amount BOOLEAN,
    status VARCHAR NOT NULL,
    error_class VARCHAR,
    raw_event_id VARCHAR NOT NULL,
    response_content_sha256 VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    quality_flags VARCHAR,
    CHECK (side IN ('BUY', 'SELL')),
    CHECK (input_mint <> output_mint),
    CHECK (input_requested_atomic >= 0),
    CHECK (input_decimals BETWEEN 0 AND 30),
    CHECK (output_decimals BETWEEN 0 AND 30),
    CHECK (quote_age_ms IS NULL OR quote_age_ms >= 0),
    CHECK (provider_latency_ms IS NULL OR provider_latency_ms >= 0),
    CHECK (provider_fee_atomic IS NULL OR provider_fee_atomic >= 0),
    CHECK (platform_fee_atomic IS NULL OR platform_fee_atomic >= 0),
    CHECK ((
        (provider_fee_atomic IS NULL AND platform_fee_atomic IS NULL
         AND fee_mint IS NULL AND included_in_output_amount IS NULL)
        OR
        ((provider_fee_atomic IS NOT NULL OR platform_fee_atomic IS NOT NULL)
         AND fee_mint IS NOT NULL AND included_in_output_amount IS NOT NULL)
    ) IS TRUE),
    CHECK (response_at IS NULL OR response_at >= requested_at),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    CHECK (length(request_hash) = 64),
    CHECK (length(response_content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> quote_attempt_id),
    CHECK (status IN ('QUOTE_AVAILABLE', 'NO_ROUTE', 'PROVIDER_ERROR',
                      'INVALID_RESPONSE', 'TIMEOUT')),
    CHECK ((
        (status = 'QUOTE_AVAILABLE'
         AND output_quoted_atomic IS NOT NULL AND output_quoted_atomic >= 0
         AND route_id IS NOT NULL AND route_count IS NOT NULL AND route_count > 0
         AND response_at IS NOT NULL AND error_class IS NULL)
        OR
        (status = 'NO_ROUTE'
         AND output_quoted_atomic IS NULL AND route_id IS NULL AND route_count = 0
         AND response_at IS NOT NULL AND error_class IS NULL)
        OR
        (status IN ('PROVIDER_ERROR', 'INVALID_RESPONSE', 'TIMEOUT')
         AND output_quoted_atomic IS NULL AND route_id IS NULL
         AND (route_count IS NULL OR route_count = 0) AND error_class IS NOT NULL)
    ) IS TRUE),
    FOREIGN KEY (raw_event_id) REFERENCES raw_api_events(raw_event_id),
    FOREIGN KEY (revision_of) REFERENCES quote_attempts(quote_attempt_id)
);

CREATE TABLE execution_attempts (
    execution_attempt_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    quote_attempt_id VARCHAR,
    signal_decision_id VARCHAR,
    side VARCHAR NOT NULL,
    input_mint VARCHAR NOT NULL,
    requested_input_atomic HUGEINT NOT NULL,
    input_decimals INTEGER NOT NULL,
    output_mint VARCHAR NOT NULL,
    output_decimals INTEGER NOT NULL,
    submitted_at TIMESTAMPTZ,
    terminal_at TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    terminal_state VARCHAR NOT NULL,
    processed_on_chain BOOLEAN,
    transaction_signature VARCHAR,
    realized_input_atomic HUGEINT,
    realized_output_atomic HUGEINT,
    actual_network_fee_lamports HUGEINT,
    actual_relay_tip_lamports HUGEINT,
    actual_ata_rent_lamports HUGEINT,
    fee_payer_mint VARCHAR,
    error_class VARCHAR,
    reconciliation_reference VARCHAR,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    content_sha256 VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    raw_event_id VARCHAR,
    quality_flags VARCHAR,
    CHECK (side IN ('BUY', 'SELL')),
    CHECK (input_mint <> output_mint),
    CHECK (requested_input_atomic >= 0),
    CHECK (input_decimals BETWEEN 0 AND 30),
    CHECK (output_decimals BETWEEN 0 AND 30),
    CHECK (submitted_at IS NULL OR terminal_at >= submitted_at),
    CHECK (observed_at <= available_to_strategy_at),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    CHECK (actual_network_fee_lamports IS NULL OR actual_network_fee_lamports >= 0),
    CHECK (actual_relay_tip_lamports IS NULL OR actual_relay_tip_lamports >= 0),
    CHECK (actual_ata_rent_lamports IS NULL OR actual_ata_rent_lamports >= 0),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> execution_attempt_id),
    CHECK (terminal_state IN (
        'REJECTED_BEFORE_SEND',
        'DROPPED_OR_EXPIRED_NOT_PROCESSED',
        'LANDED_FAILED',
        'LANDED_SUCCESS',
        'UNKNOWN_REQUIRES_RECONCILIATION'
    )),
    CHECK ((
        (terminal_state = 'REJECTED_BEFORE_SEND'
         AND submitted_at IS NULL AND processed_on_chain = FALSE
         AND transaction_signature IS NULL AND realized_input_atomic IS NULL
         AND realized_output_atomic IS NULL AND actual_network_fee_lamports IS NULL
         AND actual_relay_tip_lamports IS NULL AND actual_ata_rent_lamports IS NULL
         AND fee_payer_mint IS NULL AND error_class IS NOT NULL
         AND reconciliation_reference IS NULL)
        OR
        (terminal_state = 'DROPPED_OR_EXPIRED_NOT_PROCESSED'
         AND submitted_at IS NOT NULL AND processed_on_chain = FALSE
         AND transaction_signature IS NOT NULL AND realized_input_atomic IS NULL
         AND realized_output_atomic IS NULL AND actual_network_fee_lamports IS NULL
         AND actual_relay_tip_lamports IS NULL AND actual_ata_rent_lamports IS NULL
         AND fee_payer_mint IS NULL AND error_class IS NOT NULL
         AND reconciliation_reference IS NULL)
        OR
        (terminal_state = 'LANDED_FAILED'
         AND submitted_at IS NOT NULL AND processed_on_chain = TRUE
         AND transaction_signature IS NOT NULL AND realized_input_atomic IS NULL
         AND realized_output_atomic IS NULL AND actual_network_fee_lamports IS NOT NULL
         AND fee_payer_mint IS NOT NULL AND error_class IS NOT NULL
         AND reconciliation_reference IS NULL)
        OR
        (terminal_state = 'LANDED_SUCCESS'
         AND submitted_at IS NOT NULL AND processed_on_chain = TRUE
         AND transaction_signature IS NOT NULL
         AND realized_input_atomic IS NOT NULL AND realized_input_atomic >= 0
         AND realized_output_atomic IS NOT NULL AND realized_output_atomic >= 0
         AND actual_network_fee_lamports IS NOT NULL
         AND fee_payer_mint IS NOT NULL AND error_class IS NULL
         AND reconciliation_reference IS NULL)
        OR
        (terminal_state = 'UNKNOWN_REQUIRES_RECONCILIATION'
         AND submitted_at IS NOT NULL AND processed_on_chain IS NULL
         AND transaction_signature IS NOT NULL AND realized_input_atomic IS NULL
         AND realized_output_atomic IS NULL AND actual_network_fee_lamports IS NULL
         AND actual_relay_tip_lamports IS NULL AND actual_ata_rent_lamports IS NULL
         AND fee_payer_mint IS NULL AND error_class IS NOT NULL
         AND reconciliation_reference IS NOT NULL)
    ) IS TRUE),
    FOREIGN KEY (quote_attempt_id) REFERENCES quote_attempts(quote_attempt_id),
    FOREIGN KEY (signal_decision_id) REFERENCES signal_decision_events(signal_decision_id),
    FOREIGN KEY (revision_of) REFERENCES execution_attempts(execution_attempt_id),
    FOREIGN KEY (raw_event_id) REFERENCES raw_api_events(raw_event_id)
);

CREATE TABLE strategy_outcomes (
    strategy_outcome_id VARCHAR PRIMARY KEY,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    business_key VARCHAR NOT NULL,
    strategy_id VARCHAR NOT NULL,
    strategy_version VARCHAR NOT NULL,
    position_id VARCHAR NOT NULL,
    outcome_type VARCHAR NOT NULL,
    outcome_value_decimal DECIMAL(38, 18),
    outcome_unit VARCHAR,
    measured_as_of TIMESTAMPTZ NOT NULL,
    available_to_strategy_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    inventory_state VARCHAR NOT NULL,
    remaining_inventory_atomic HUGEINT NOT NULL,
    remaining_inventory_mint VARCHAR,
    remaining_inventory_decimals INTEGER,
    last_executable_liquidation_quote_id VARCHAR,
    recovery_lower_bound_decimal DECIMAL(38, 18),
    recovery_upper_bound_decimal DECIMAL(38, 18),
    recovery_unit VARCHAR,
    recovery_currency_or_mint VARCHAR,
    failed_exit_state VARCHAR,
    source VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    revision_number BIGINT NOT NULL,
    revision_of VARCHAR,
    content_sha256 VARCHAR NOT NULL,
    quality_flags VARCHAR,
    CHECK (outcome_type IN ('TouchReturn', 'FillableReturn', 'RealizedVWAPReturn',
                            'NetReturn', 'PathRisk')),
    CHECK (inventory_state IN ('FLAT', 'OPEN', 'UNRESOLVED_REQUIRES_RECOVERY', 'RECOVERED')),
    CHECK (remaining_inventory_atomic >= 0),
    CHECK (remaining_inventory_decimals IS NULL OR remaining_inventory_decimals BETWEEN 0 AND 30),
    CHECK (first_reliable_available_at <= available_to_strategy_at),
    CHECK (measured_as_of <= available_to_strategy_at),
    CHECK (length(content_sha256) = 64),
    CHECK (revision_number >= 1),
    CHECK (revision_of IS NULL OR revision_of <> strategy_outcome_id),
    CHECK ((
        (inventory_state IN ('FLAT', 'RECOVERED')
         AND remaining_inventory_atomic = 0
         AND remaining_inventory_mint IS NULL
         AND remaining_inventory_decimals IS NULL
         AND recovery_lower_bound_decimal IS NULL
         AND recovery_upper_bound_decimal IS NULL
         AND recovery_unit IS NULL AND recovery_currency_or_mint IS NULL
         AND failed_exit_state IS NULL)
        OR
        (inventory_state = 'OPEN'
         AND remaining_inventory_atomic > 0
         AND remaining_inventory_mint IS NOT NULL
         AND remaining_inventory_decimals IS NOT NULL
         AND recovery_lower_bound_decimal IS NULL
         AND recovery_upper_bound_decimal IS NULL
         AND recovery_unit IS NULL AND recovery_currency_or_mint IS NULL
         AND failed_exit_state IS NULL)
        OR
        (inventory_state = 'UNRESOLVED_REQUIRES_RECOVERY'
         AND remaining_inventory_atomic > 0
         AND remaining_inventory_mint IS NOT NULL
         AND remaining_inventory_decimals IS NOT NULL
         AND recovery_lower_bound_decimal IS NOT NULL
         AND recovery_upper_bound_decimal IS NOT NULL
         AND recovery_lower_bound_decimal <= recovery_upper_bound_decimal
         AND recovery_unit IS NOT NULL AND recovery_currency_or_mint IS NOT NULL
         AND failed_exit_state IN ('NO_ROUTE', 'EXIT_FAILED',
                                    'UNKNOWN_REQUIRES_RECONCILIATION'))
    ) IS TRUE),
    FOREIGN KEY (revision_of) REFERENCES strategy_outcomes(strategy_outcome_id),
    FOREIGN KEY (last_executable_liquidation_quote_id)
        REFERENCES quote_attempts(quote_attempt_id)
);

CREATE TABLE dataset_manifests (
    dataset_manifest_id VARCHAR PRIMARY KEY,
    dataset_id VARCHAR NOT NULL,
    dataset_version VARCHAR NOT NULL,
    schema_id VARCHAR NOT NULL,
    schema_sha256 VARCHAR NOT NULL,
    dataset_fingerprint VARCHAR NOT NULL,
    generation_task_id VARCHAR NOT NULL,
    generation_run_id VARCHAR NOT NULL,
    validation_receipt_sha256 VARCHAR NOT NULL,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    content_sha256 VARCHAR NOT NULL,
    UNIQUE (dataset_id, dataset_version),
    CHECK (length(schema_sha256) = 64),
    CHECK (length(dataset_fingerprint) = 64),
    CHECK (length(validation_receipt_sha256) = 64),
    CHECK (length(content_sha256) = 64),
    CHECK (first_reliable_available_at >= created_at)
);

CREATE TABLE partition_manifests (
    partition_manifest_id VARCHAR PRIMARY KEY,
    dataset_manifest_id VARCHAR NOT NULL,
    partition_id VARCHAR NOT NULL,
    logical_location VARCHAR NOT NULL,
    file_sha256 VARCHAR NOT NULL,
    content_sha256 VARCHAR NOT NULL,
    row_count UBIGINT NOT NULL,
    min_event_time TIMESTAMPTZ,
    max_event_time TIMESTAMPTZ,
    min_available_to_strategy_at TIMESTAMPTZ,
    max_available_to_strategy_at TIMESTAMPTZ,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (dataset_manifest_id, partition_id),
    UNIQUE (dataset_manifest_id, logical_location),
    CHECK (logical_location <> ''),
    CHECK (length(file_sha256) = 64),
    CHECK (length(content_sha256) = 64),
    CHECK (((min_event_time IS NULL AND max_event_time IS NULL)
           OR (min_event_time IS NOT NULL AND max_event_time IS NOT NULL
                AND min_event_time <= max_event_time)) IS TRUE),
    CHECK (((min_available_to_strategy_at IS NULL AND max_available_to_strategy_at IS NULL)
           OR (min_available_to_strategy_at IS NOT NULL
                AND max_available_to_strategy_at IS NOT NULL
                AND min_available_to_strategy_at <= max_available_to_strategy_at)) IS TRUE),
    CHECK (first_reliable_available_at >= created_at),
    FOREIGN KEY (dataset_manifest_id) REFERENCES dataset_manifests(dataset_manifest_id)
);

CREATE TABLE migration_manifests (
    migration_manifest_id VARCHAR PRIMARY KEY,
    migration_id VARCHAR NOT NULL UNIQUE,
    migration_order UBIGINT NOT NULL UNIQUE,
    migration_kind VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    content_sha256 VARCHAR NOT NULL,
    supersedes_migration_id VARCHAR,
    application_state VARCHAR NOT NULL,
    applied_at TIMESTAMPTZ,
    application_receipt_sha256 VARCHAR,
    first_reliable_available_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CHECK (migration_order > 0),
    CHECK (migration_kind IN ('DDL', 'DATA_BACKFILL', 'REBUILD', 'REPAIR')),
    CHECK (length(content_sha256) = 64),
    CHECK (supersedes_migration_id IS NULL OR supersedes_migration_id <> migration_id),
    CHECK (application_state IN ('DECLARED', 'APPLIED', 'FAILED')),
    CHECK ((
        (application_state = 'DECLARED'
         AND applied_at IS NULL AND application_receipt_sha256 IS NULL)
        OR
        (application_state IN ('APPLIED', 'FAILED')
         AND applied_at IS NOT NULL
         AND application_receipt_sha256 IS NOT NULL
         AND length(application_receipt_sha256) = 64)
    ) IS TRUE),
    CHECK (first_reliable_available_at >= created_at)
);

CREATE MACRO decision_safe_observations(as_of_timestamp) AS TABLE (
    SELECT *
    FROM canonical_observations
    WHERE available_to_strategy_at <= as_of_timestamp
      AND first_reliable_available_at <= as_of_timestamp
);
