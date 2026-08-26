CREATE TABLE _research_events (
    record_id VARCHAR PRIMARY KEY,
    record_kind VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    stable_id VARCHAR NOT NULL,
    hypothesis_version_id VARCHAR,
    run_id VARCHAR,
    transaction_id VARCHAR NOT NULL,
    effective_at TIMESTAMP NOT NULL,
    first_reliable_available_at TIMESTAMP NOT NULL,
    supersedes_record_id VARCHAR,
    payload_json JSON NOT NULL,
    payload_sha256 VARCHAR NOT NULL,
    definition_sha256 VARCHAR,
    run_key_sha256 VARCHAR,
    schema_version VARCHAR NOT NULL,
    producer_capability_id VARCHAR NOT NULL,
    producer_git_sha VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX research_events_run_key_idx
ON _research_events (record_kind, run_key_sha256);

CREATE INDEX research_events_stable_id_idx
ON _research_events (record_kind, stable_id);

CREATE TABLE _projection_metadata (
    singleton BOOLEAN PRIMARY KEY,
    projection_digest_sha256 VARCHAR NOT NULL,
    record_count BIGINT NOT NULL,
    partition_count BIGINT NOT NULL,
    schema_version VARCHAR NOT NULL,
    CHECK (singleton = TRUE)
);

CREATE VIEW hypotheses AS
SELECT
    stable_id AS hypothesis_version_id,
    json_extract_string(payload_json, '$.family_id') AS family_id,
    TRY_CAST(json_extract_string(payload_json, '$.version_ordinal') AS INTEGER)
        AS version_ordinal,
    json_extract_string(payload_json, '$.origin_id') AS origin_id,
    COALESCE(
        json_extract_string(payload_json, '$.origin_kind'),
        (
            SELECT json_extract_string(origin.payload_json, '$.origin_kind')
            FROM _research_events AS origin
            WHERE origin.record_kind = 'HYPOTHESIS_ORIGIN'
              AND (
                  origin.hypothesis_version_id = hypothesis.stable_id
                  OR origin.stable_id = json_extract_string(
                      hypothesis.payload_json,
                      '$.origin_id'
                  )
              )
            ORDER BY
                origin.effective_at DESC,
                origin.first_reliable_available_at DESC,
                origin.record_id DESC
            LIMIT 1
        )
    ) AS origin_kind,
    json_extract_string(payload_json, '$.research_cycle_id') AS research_cycle_id,
    definition_sha256,
    json_extract_string(payload_json, '$.statement') AS statement,
    json_extract_string(payload_json, '$.mechanism') AS mechanism,
    json_extract_string(payload_json, '$.falsifier') AS falsifier,
    json_extract(payload_json, '$.expected_regime_terms') AS expected_regime_terms,
    json_extract_string(payload_json, '$.what_changed') AS what_changed,
    effective_at,
    first_reliable_available_at,
    record_id,
    payload_sha256,
    COALESCE(
        (
            SELECT CASE json_extract_string(decision.payload_json, '$.decision_kind')
                WHEN 'REJECT' THEN 'REJECTED'
                WHEN 'REVISE' THEN 'REVISION_REQUIRED'
                WHEN 'PROMOTE' THEN 'PROMOTED'
                WHEN 'PAUSE' THEN 'PAUSED'
                WHEN 'MARK_DORMANT' THEN 'DORMANT'
                WHEN 'RETIRE' THEN 'RETIRED'
                WHEN 'REACTIVATE' THEN 'REACTIVATED'
                ELSE NULL
            END
            FROM _research_events AS decision
            WHERE decision.record_kind = 'DECISION_EVENT'
              AND decision.hypothesis_version_id = hypothesis.stable_id
            ORDER BY
                decision.effective_at DESC,
                decision.first_reliable_available_at DESC,
                decision.record_id DESC
            LIMIT 1
        ),
        (
            SELECT json_extract_string(run.payload_json, '$.scientific_terminal')
            FROM _research_events AS run
            WHERE run.record_kind IN ('RUN_COMPLETED', 'RUN_INVALID')
              AND run.hypothesis_version_id = hypothesis.stable_id
            ORDER BY
                run.effective_at DESC,
                run.first_reliable_available_at DESC,
                run.record_id DESC
            LIMIT 1
        ),
        'NO_DECISION'
    ) AS derived_state
FROM _research_events AS hypothesis
WHERE record_kind = 'HYPOTHESIS_VERSION';

CREATE VIEW hypothesis_events AS
SELECT
    record_id AS hypothesis_event_id,
    record_kind AS event_kind,
    stable_id,
    hypothesis_version_id,
    json_extract_string(payload_json, '$.decision_kind') AS decision_kind,
    json_extract_string(payload_json, '$.derivation_kind') AS derivation_kind,
    json_extract_string(payload_json, '$.activation_epoch_id')
        AS activation_epoch_id,
    supersedes_record_id,
    payload_json,
    payload_sha256,
    effective_at,
    first_reliable_available_at
FROM _research_events
WHERE record_kind IN (
    'DECISION_EVENT',
    'DERIVATION_EDGE',
    'ACTIVATION_EPOCH'
);

CREATE VIEW experiment_runs AS
SELECT
    stable_id AS run_id,
    hypothesis_version_id,
    record_kind AS run_event_kind,
    run_key_sha256,
    json_extract_string(payload_json, '$.trial_id') AS trial_id,
    json_extract_string(payload_json, '$.execution_status') AS execution_status,
    json_extract_string(payload_json, '$.trial_outcome') AS trial_outcome,
    json_extract_string(payload_json, '$.scientific_terminal')
        AS scientific_terminal,
    json_extract_string(payload_json, '$.result_digest_sha256')
        AS result_digest_sha256,
    json_extract_string(payload_json, '$.artifact_manifest_sha256')
        AS artifact_manifest_sha256,
    json_extract(payload_json, '$.dataset_manifest_ids') AS dataset_manifest_ids,
    json_extract(payload_json, '$.dataset_fingerprints') AS dataset_fingerprints,
    json_extract(payload_json, '$.query_recipe_ids') AS query_recipe_ids,
    json_extract_string(payload_json, '$.runner_capability_id')
        AS runner_capability_id,
    json_extract_string(payload_json, '$.what_changed') AS what_changed,
    payload_json,
    payload_sha256,
    effective_at,
    first_reliable_available_at,
    record_id
FROM _research_events
WHERE record_kind IN (
    'RUN_STARTED',
    'RUN_COMPLETED',
    'RUN_ABORTED',
    'RUN_INVALID'
);

CREATE VIEW experiment_metrics AS
SELECT
    stable_id AS metric_id,
    run_id,
    hypothesis_version_id,
    json_extract_string(payload_json, '$.metric_name') AS metric_name,
    CASE
        WHEN json_type(payload_json, '$.scalar_value') IN ('NULL', NULL) THEN NULL
        ELSE json_extract_string(payload_json, '$.scalar_value')
    END AS scalar_value,
    json_extract_string(payload_json, '$.scalar_type') AS scalar_type,
    json_extract_string(payload_json, '$.unit') AS unit,
    payload_sha256,
    effective_at,
    first_reliable_available_at,
    record_id
FROM _research_events
WHERE record_kind = 'EXPERIMENT_METRIC';

CREATE VIEW evidence_bindings AS
SELECT
    stable_id AS evidence_binding_id,
    run_id,
    hypothesis_version_id,
    json_extract_string(payload_json, '$.binding_kind') AS binding_kind,
    json_extract_string(payload_json, '$.content_sha256') AS content_sha256,
    json_extract_string(payload_json, '$.logical_uri') AS logical_uri,
    json_extract_string(payload_json, '$.dataset_manifest_id')
        AS dataset_manifest_id,
    json_extract_string(payload_json, '$.query_recipe_id') AS query_recipe_id,
    json_extract_string(payload_json, '$.code_sha256') AS code_sha256,
    json_extract_string(payload_json, '$.config_sha256') AS config_sha256,
    payload_sha256,
    effective_at,
    first_reliable_available_at,
    record_id
FROM _research_events
WHERE record_kind = 'EVIDENCE_BINDING';

CREATE VIEW promotion_candidates AS
SELECT
    stable_id AS promotion_candidate_id,
    run_id,
    hypothesis_version_id,
    json_extract_string(payload_json, '$.nomination_state')
        AS nomination_state,
    json_extract_string(payload_json, '$.owner_state') AS owner_state,
    json_extract_string(payload_json, '$.packet_sha256') AS packet_sha256,
    payload_sha256,
    effective_at,
    first_reliable_available_at,
    record_id
FROM _research_events
WHERE record_kind = 'PROMOTION_CANDIDATE';

CREATE VIEW prior_work AS
SELECT
    stable_id AS hypothesis_version_id,
    json_extract_string(payload_json, '$.family_id') AS family_id,
    definition_sha256,
    json_extract_string(payload_json, '$.statement') AS statement,
    json_extract_string(payload_json, '$.mechanism') AS mechanism,
    json_extract_string(payload_json, '$.falsifier') AS falsifier,
    json_extract(payload_json, '$.expected_regime_terms') AS regime_terms,
    COALESCE(
        json_extract_string(payload_json, '$.origin_kind'),
        (
            SELECT json_extract_string(origin.payload_json, '$.origin_kind')
            FROM _research_events AS origin
            WHERE origin.record_kind = 'HYPOTHESIS_ORIGIN'
              AND (
                  origin.hypothesis_version_id = hypothesis.stable_id
                  OR origin.stable_id = json_extract_string(
                      hypothesis.payload_json,
                      '$.origin_id'
                  )
              )
            ORDER BY
                origin.effective_at DESC,
                origin.first_reliable_available_at DESC,
                origin.record_id DESC
            LIMIT 1
        )
    ) AS origin_kind,
    json_extract_string(payload_json, '$.what_changed') AS what_changed,
    payload_sha256,
    effective_at,
    first_reliable_available_at,
    record_id
FROM _research_events AS hypothesis
WHERE record_kind = 'HYPOTHESIS_VERSION';

CREATE VIEW capability_gaps AS
SELECT
    stable_id AS capability_gap_id,
    hypothesis_version_id,
    run_id,
    json_extract_string(payload_json, '$.capability_id') AS capability_id,
    json_extract_string(payload_json, '$.reason_code') AS reason_code,
    json_extract_string(payload_json, '$.required_contract')
        AS required_contract,
    payload_sha256,
    effective_at,
    first_reliable_available_at,
    record_id
FROM _research_events
WHERE record_kind = 'CAPABILITY_GAP';

CREATE VIEW hfic_sessions AS
WITH receipt_sessions AS (
    SELECT DISTINCT json_extract_string(payload_json, '$.session_id') AS session_id
    FROM _research_events
    WHERE record_kind = 'RESEARCH_ARTIFACT'
      AND json_extract_string(payload_json, '$.artifact_kind') = 'SESSION_RECEIPT'
),
critic_sessions AS (
    SELECT DISTINCT json_extract_string(payload_json, '$.session_id') AS session_id
    FROM _research_events
    WHERE record_kind = 'RESEARCH_ARTIFACT'
      AND json_extract_string(payload_json, '$.artifact_kind') = 'CRITIC_RESULT'
),
scored AS (
    SELECT
        json_extract_string(cycle.payload_json, '$.session_id') AS session_id,
        CASE
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'SYNTHESIS_COMPLETE'
                 AND rec.session_id IS NULL
            THEN CASE
                WHEN art.session_id IS NOT NULL THEN 'CRITIC_RESULT_READY'
                ELSE 'FROZEN_AWAITING_CRITIC'
            END
            ELSE json_extract_string(cycle.payload_json, '$.phase')
        END AS session_state,
        json_extract_string(cycle.payload_json, '$.evidence_epoch_sha256')
            AS evidence_epoch_sha256,
        json_extract_string(cycle.payload_json, '$.focus_key_sha256')
            AS focus_key_sha256,
        json_extract_string(cycle.payload_json, '$.search_key_sha256')
            AS search_key_sha256,
        json_extract_string(cycle.payload_json, '$.prompt_version')
            AS prompt_version,
        json_extract_string(cycle.payload_json, '$.owner_focus') AS owner_focus,
        cycle.producer_git_sha AS live_git_head,
        cycle.payload_sha256,
        cycle.effective_at,
        cycle.first_reliable_available_at,
        cycle.record_id,
        CASE
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'SYNTHESIS_COMPLETE'
                 AND rec.session_id IS NOT NULL THEN 0
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'LEGACY_PARTIAL' THEN 0
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'AWAITING_CLASSIFICATION' THEN 1
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'REVISED_AWAITING_CRITIC' THEN 1
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'REVISION_REQUIRED' THEN 2
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'SYNTHESIS_COMPLETE'
                 AND art.session_id IS NOT NULL THEN 3
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'CRITIC_RESULT_READY' THEN 3
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'SYNTHESIS_COMPLETE' THEN 4
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'FROZEN_AWAITING_CRITIC' THEN 4
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'DRAFT_VALIDATED' THEN 5
            WHEN json_extract_string(cycle.payload_json, '$.phase')
                 = 'PREFLIGHT_PROVEN' THEN 6
            ELSE 6
        END AS phase_rank
    FROM _research_events AS cycle
    LEFT JOIN receipt_sessions AS rec
      ON rec.session_id
         = json_extract_string(cycle.payload_json, '$.session_id')
    LEFT JOIN critic_sessions AS art
      ON art.session_id
         = json_extract_string(cycle.payload_json, '$.session_id')
    WHERE cycle.record_kind = 'RESEARCH_CYCLE'
      AND json_extract_string(cycle.payload_json, '$.hfic_protocol') IS NOT NULL
),
ranked AS (
    SELECT
        scored.*,
        row_number() OVER (
            PARTITION BY session_id
            ORDER BY phase_rank ASC, effective_at DESC, record_id ASC
        ) AS cycle_rank
    FROM scored
)
SELECT
    session_id,
    session_state,
    evidence_epoch_sha256,
    focus_key_sha256,
    search_key_sha256,
    prompt_version,
    owner_focus,
    live_git_head,
    payload_sha256,
    effective_at,
    first_reliable_available_at,
    record_id
FROM ranked
WHERE cycle_rank = 1;

CREATE VIEW hfic_candidates AS
SELECT
    json_extract_string(payload_json, '$.session_id') AS session_id,
    stable_id AS candidate_id,
    definition_sha256,
    json_extract_string(payload_json, '$.statement') AS claim,
    json_extract_string(payload_json, '$.mechanism') AS mechanism,
    json_extract_string(payload_json, '$.primary_x_family') AS primary_x_family,
    json_extract_string(payload_json, '$.role_in_session') AS role_in_session,
    payload_sha256,
    effective_at,
    first_reliable_available_at,
    record_id
FROM _research_events
WHERE record_kind = 'HYPOTHESIS_VERSION'
  AND json_extract_string(payload_json, '$.hfic_protocol') IS NOT NULL;

CREATE VIEW hfic_candidate_decisions AS
SELECT
    json_extract_string(payload_json, '$.session_id') AS session_id,
    hypothesis_version_id AS candidate_id,
    json_extract_string(payload_json, '$.decision_kind') AS decision_kind,
    json_extract_string(payload_json, '$.reason_code') AS reason_code,
    payload_sha256,
    effective_at,
    first_reliable_available_at,
    record_id
FROM _research_events
WHERE record_kind = 'DECISION_EVENT'
  AND json_extract_string(payload_json, '$.hfic_protocol') IS NOT NULL;

CREATE VIEW hfic_search_budget AS
SELECT
    evidence_epoch_sha256,
    focus_key_sha256,
    search_key_sha256,
    prompt_version,
    session_id,
    session_state,
    effective_at,
    record_id
FROM hfic_sessions;

CREATE VIEW hfic_pending_sessions AS
SELECT
    session_id,
    session_state,
    evidence_epoch_sha256,
    focus_key_sha256,
    search_key_sha256,
    prompt_version,
    effective_at,
    record_id
FROM hfic_sessions
WHERE session_state IN (
    'PREFLIGHT_PROVEN',
    'DRAFT_VALIDATED',
    'FROZEN_AWAITING_CRITIC',
    'REVISED_AWAITING_CRITIC',
    'REVISION_REQUIRED',
    'AWAITING_CLASSIFICATION',
    'CRITIC_RESULT_READY'
);
