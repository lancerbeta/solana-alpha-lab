---
task_id: DECLARATIVE_OBSERVATION_SCHEDULE_BRIDGE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-28'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: c795952e166a2c5f0f5c967b84ee6457c3b0dc80
  expected_upstream: origin/main
  expected_upstream_oid: c795952e166a2c5f0f5c967b84ee6457c3b0dc80
  expected_branch: cursor/declarative-observation-schedule-bridge-v1
  dirty_mode: ALLOW_REPORTED
objective: Compile ExperimentSpec v1.2 observation requests into immutable hash-bound
  ObservationSchedule v1.0 records in the Research Data Plane, then execute only
  registered primitives through a crash-safe tick --once scheduler so common
  outcome-blind PIT panels feed many hypotheses without Git for in-envelope timing
  changes.
managed_write_set:
- docs/tasks/DECLARATIVE_OBSERVATION_SCHEDULE_BRIDGE_V1.md
- docs/decisions/ADR-007-declarative-observation-schedule-bridge.md
- catalog/schemas/observation_schedule_v1.schema.json
- catalog/schemas/observation_primitive_descriptor_v1.schema.json
- catalog/schemas/observation_panel_snapshot_v1.schema.json
- catalog/schemas/observation_schedule_authority_v1.schema.json
- catalog/schemas/experiment_spec_v1_2.schema.json
- catalog/schemas/observation_primitive_registry_v1.schema.json
- catalog/schemas/factory_remote_operations_v1_1.schema.json
- catalog/schemas/research_event_envelope.schema.json
- catalog/schemas/run_passport.schema.json
- configs/observation_primitive_registry_v1.yaml
- configs/experiment_capability_registry_v2.yaml
- configs/factory_remote_operations_v1_1.yaml
- configs/factory_remote_ops/factory-observation-schedule.service
- configs/factory_remote_ops/factory-observation-schedule.timer
- schemas/research_memory_projection_v1.sql
- src/solana_alpha_lab/factory/experiment_spec.py
- src/solana_alpha_lab/factory/lane_classifier.py
- src/solana_alpha_lab/factory/run_passport.py
- src/solana_alpha_lab/factory/research_store.py
- src/solana_alpha_lab/factory/hfic_preflight.py
- src/solana_alpha_lab/factory/capabilities.py
- src/solana_alpha_lab/factory/remote_ops.py
- src/solana_alpha_lab/factory/observation_schedule.py
- src/solana_alpha_lab/factory/observation_primitive_registry.py
- src/solana_alpha_lab/factory/observation_schedule_compiler.py
- src/solana_alpha_lab/factory/observation_panel_coverage.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/observation_primitives.py
- src/solana_alpha_lab/factory/observation_schedule_capability.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/observation_panel_publisher.py
- scripts/observation_schedule.py
- tests/test_observation_schedule_schemas.py
- tests/test_observation_primitive_registry.py
- tests/test_observation_schedule_compiler.py
- tests/test_observation_schedule_store.py
- tests/test_observation_primitives.py
- tests/test_observation_scheduler.py
- tests/test_observation_panel_publisher.py
- tests/test_observation_schedule_rdp.py
- tests/test_hfic_preflight.py
- tests/test_observation_schedule_remote_ops.py
- tests/test_observation_schedule_artifact_pin.py
- tests/fixtures/observation_schedule/common_panel.yaml
- tests/fixtures/observation_schedule/x300_y900.yaml
- tests/fixtures/observation_schedule/successor_y259200.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- .github/workflows/ci.yml
- scripts/validate_ci.py
- tests/test_ci.py
- tests/test_factory_ordinary_market_hypothesis.py
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/evidence/declarative_observation_schedule_bridge/a1_delivery_completion_evidence_v1.json
- docs/evidence/declarative_observation_schedule_bridge/a1_delivery_independent_review_v1.json
- docs/evidence/declarative_observation_schedule_bridge/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_PROVIDER_CALL_BEFORE_MERGE
- CREDENTIAL_READ_BEFORE_MERGE
- DEPLOYMENT_OR_COMMISSIONING
- LIVE_OBSERVATION_SCHEDULE_ACTIVATION
- NEW_PROVIDER_ENDPOINT_AUTH
- WALLET_BUILD_EXECUTE_TRANSACTION
- RETRY_OR_FALLBACK
- CASH_SPEND
- REOPEN_EARLY_TAKER_VOLUME_MIX_FAMILY
- MODIFY_COMPLETED_V2_SLEEP_OR_PR211_RUNNER
- ARBITRARY_URL_PYTHON_SQL_EXPRESSION
- NEW_ESTIMATOR_SCORER_OR_HYPOTHESIS_TERMINAL
- SECOND_ORCHESTRATOR_OR_SCIENTIFIC_DATABASE
- AUTOMATIC_PROMOTION
context_requirements:
  catalog_asset_ids:
  - ADR-006-HYPOTHESIS-FAST-LANE-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  - SCHEMA-EXPERIMENT-SPEC-V1-1-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
    ARCHITECTURE_DECISIONS:
    - ADR-006-HYPOTHESIS-FAST-LANE-001
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/decisions/ADR-007-declarative-observation-schedule-bridge.md
    DELIVERY_EVIDENCE:
    - docs/evidence/declarative_observation_schedule_bridge/a1_delivery_independent_review_v1.json
    - docs/evidence/declarative_observation_schedule_bridge/a1_delivery_completion_evidence_v1.json
    - docs/evidence/declarative_observation_schedule_bridge/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# DECLARATIVE_OBSERVATION_SCHEDULE_BRIDGE_V1

## Task Outcome Brief

- **DECISION_DELTA:** compiler plus one-shot `ObservationSchedule v1.0` bridge;
  in-envelope timing/population/sampling changes become runtime data.
- **UNCERTAINTY_REMOVED:** whether a new Y horizon can be registered without Git;
  whether crash/restore is fail-closed; whether `.decision.json` sidecars false-warn.
- **CAPABILITY_OR_EVIDENCE:** schemas, primitive registry, compiler, SQLite due-work
  store, `tick --once`, RDP panels, remote-ops units, zero-network proof.
- **STOP:** `DECLARATIVE_OBSERVATION_SCHEDULE_BRIDGE_READY_FOR_RUNTIME_SPECS` at
  the exact merge gate. No live activation, deployment, or commissioning.
- **NEXT:** exact owner merge phrase bound to PR/head; after merge one bounded
  commissioning phrase that this atom does not execute.
- **SPEC_ROUTE:** BOTH
- **REPLAN_TRIGGER:** a new allowed horizon still needs Git; Y can affect
  selection; an in-flight call can repeat; a schedule can mutate; a partial
  dataset becomes visible; restore/PIT identity is unproved; scope expands to a
  new provider/estimator/scorer.

## Owner decision

`OK DECLARATIVE_OBSERVATION_SCHEDULE_BRIDGE_V1` on main descended from
`c795952e166a2c5f0f5c967b84ee6457c3b0dc80`. The attached PRD+SSD is the
authoritative implementation contract. Cursor never merges.

## Product goal

Turn a validated ExperimentSpec v1.2 observation request into an immutable
content-addressed ObservationSchedule v1.0, execute only registered primitives
through a crash-safe one-shot scheduler tick, and publish outcome-blind PIT
panels into the existing Research Data Plane.

This is not an API gateway, event bus, workflow engine, plugin platform, new
provider layer, or hypothesis-specific runner.

## Success criteria

1. Two valid runtime documents with the same normalized collection semantics
   produce the same `schedule_sha256` and one collection plan.
2. A new Y horizon inside V1 bounds produces a new immutable schedule version
   with zero Git changes.
3. A hypothesis can bind an exact panel snapshot at an availability cutoff and
   receive a hash-resolved run passport.
4. A request for an unknown field/parser/route/estimator fails before credentials
   or network with a typed `CHANGE_LANE_*` reason.
5. The scheduler survives restart, missed ticks, partial responses and an
   indeterminate in-flight call without replaying an external call or inventing
   a value.
6. Dataset event time and availability time remain distinct and auditable.
7. Daily partitions, RDP events, scheduler operational state and the active
   journal can be backed up and restored in isolation.
8. Current v1.1 Fast Lane, completed V2 artifacts, prior SLEEP artifacts, PR #211
   dataset and scorer remain byte-identical.

## Non-goals

No new provider, paid plan, endpoint, RPC, WSS or authentication method. No
wallet, signer, transaction, `/build`, `/execute`, or real money. No arbitrary
URLs, Python, SQL, expressions, field paths, plugins or user-supplied code in
runtime YAML. No new estimator, scorer, threshold search, model selection or
hypothesis terminal. Do not reopen the closed early taker-volume-mix family.
No historical reconstruction of uncaptured observations. No silent retry,
fallback, imputation, `UNKNOWN=0`, row deletion or survivor-only panels. No
mutation of an activated schedule, dataset manifest, partition or RDP event.
No web UI, distributed scheduler, queue, Kubernetes, Kafka or second scientific
database. No automatic provider purchase, promotion, Shadow, Strategy or Bot.

## Planes

1. Git capability plane.
2. Research Data Plane (immutable scientific truth).
3. Operational SQLite due-work (rebuildable except indeterminate calls).
4. DuckDB projection (rebuildable views only).

## Compiler terminals

`PANEL_REUSE_READY`, `ATTACHED_TO_ACTIVE_SCHEDULE`,
`SCHEDULE_ACTIVATION_REQUIRED`, `NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED`,
`CHANGE_LANE_PRIMITIVE_GAP`, `CHANGE_LANE_ESTIMATOR_GAP`,
`CHANGE_LANE_SAFETY_CONTRACT_GAP`, `BLOCKED_BUDGET`, `BLOCKED_AUTHORITY`,
`DENY_OUTCOME_LEAKAGE`, `DENY_RETROACTIVE_MUTATION`, `DENY_UNSAFE_RUNTIME_CODE`.

## V1 safety envelope

TOKEN_MINT only. One X point. 1..8 absolute Y points from the same entity
anchor. Offsets 0..2592000 seconds. Discovery cadence in {60, 300, 900, 3600,
86400}. Provider calls read-only and zero-cash. Retry and fallback false.
Registered IDs only.

## Inventory repair

Enumerate canonical `dataset-[0-9a-f]{64}.json` plus existing stable-ID
DatasetManifest filenames. Ignore `.labels.json` and `.decision.json`. Warn on
a corrupt canonical manifest. Direct stable-ID resolution unchanged. PR #211
target found exactly once with no target warning.

## Product terminal

`DECLARATIVE_OBSERVATION_SCHEDULE_BRIDGE_READY_FOR_RUNTIME_SPECS`

## Failure terminals

`BRIDGE_SCHEMA_OR_PIT_CONTRACT_INVALID`,
`BRIDGE_CANNOT_ADD_HORIZON_WITHOUT_GIT`,
`BRIDGE_OPERATIONAL_RECOVERY_UNPROVED`,
`BRIDGE_DUPLICATE_CALL_OR_MUTATION_RISK`,
`BRIDGE_SCOPE_EXPANDED_REPLAN_REQUIRED`

## Merge gate

Exact-head CI plus isolated code, Goal/DoD and architecture/PIT reviews.
Stop at merge gate. Owner never clicks GitHub Merge. Cursor never merges.
After merge return one new bounded commissioning phrase; do not run it.
