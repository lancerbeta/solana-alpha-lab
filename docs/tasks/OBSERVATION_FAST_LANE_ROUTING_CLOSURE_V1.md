---
task_id: OBSERVATION_FAST_LANE_ROUTING_CLOSURE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-29'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 0e733c5a4434f936d51b27f3bdc49735c78be3a5
  expected_upstream: origin/main
  expected_upstream_oid: 0e733c5a4434f936d51b27f3bdc49735c78be3a5
  expected_branch: cursor/observation-fast-lane-routing-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: >
  Close the one remaining product-level routing gap between Hypothesis Forge /
  deterministic Fast Lane and the already-merged ObservationSchedule bridge.
  A valid ExperimentSpec v1.2 whose observation request is fully inside the
  accepted V1 envelope must remain on a no-Git/no-PR routine path and must not
  become CLASSIFIER_TERMINAL_MISMATCH or FAILED_INFRA merely because the
  ObservationSchedule compiler returned an observation-specific terminal.
managed_write_set:
- docs/tasks/OBSERVATION_FAST_LANE_ROUTING_CLOSURE_V1.md
- src/solana_alpha_lab/factory/observation_fast_lane_terminals.py
- src/solana_alpha_lab/factory/hfic_session.py
- src/solana_alpha_lab/factory/document_runner.py
- src/solana_alpha_lab/factory/observation_schedule_capability.py
- src/solana_alpha_lab/factory/observation_schedule_compiler.py
- src/solana_alpha_lab/factory/observation_panel_coverage.py
- src/solana_alpha_lab/factory/observation_panel_publisher.py
- src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/lane_classifier.py
- src/solana_alpha_lab/factory/capabilities.py
- scripts/hypothesis_fast_lane.py
- tests/test_observation_fast_lane_routing_closure.py
- tests/test_observation_fast_lane_p0_addendum.py
- docs/evidence/observation_fast_lane_routing_closure/a1_delivery_completion_evidence_v1.json
- docs/evidence/observation_fast_lane_routing_closure/a1_delivery_independent_review_v1.json
- docs/evidence/observation_fast_lane_routing_closure/a1_delivery_factory_fit_v1.json
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- .github/workflows/ci.yml
- scripts/validate_ci.py
- tests/test_ci.py
- delivery-harness/policies/solana-alpha-lab.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_PROVIDER_CALL
- CREDENTIAL_READ
- DEPLOYMENT_OR_COMMISSIONING
- LIVE_OBSERVATION_SCHEDULE_ACTIVATION
- NEW_PROVIDER_ENDPOINT_AUTH
- WALLET_BUILD_EXECUTE_TRANSACTION
- CASH_SPEND
- REDESIGN_OBSERVATION_SCHEDULER
- NEW_ESTIMATOR_SCORER_OR_WORKFLOW_ENGINE
- WEAKEN_OWNER_AUTHORITY_GATES
- COLLAPSE_PENDING_COLLECTION_INTO_COMPLETE_RUN
context_requirements:
  catalog_asset_ids:
  - ADR-006-HYPOTHESIS-FAST-LANE-001
  - SCHEMA-EXPERIMENT-SPEC-V1-1-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
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
    - docs/evidence/observation_fast_lane_routing_closure/a1_delivery_completion_evidence_v1.json
    - docs/evidence/observation_fast_lane_routing_closure/a1_delivery_independent_review_v1.json
    - docs/evidence/observation_fast_lane_routing_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OBSERVATION_FAST_LANE_ROUTING_CLOSURE_V1

## Task Outcome Brief

- **DECISION_DELTA:** one shared observation Fast Lane terminal contract; HFIC and
  the generic no-Git runner consume it. Pending collection stays typed
  authority/data, not infra and not a completed experiment.
- **UNCERTAINTY_REMOVED:** whether an in-envelope ExperimentSpec v1.2 still
  becomes `CLASSIFIER_TERMINAL_MISMATCH` or `FAILED_INFRA`; whether pending
  collection can poison `run_key` replay.
- **CAPABILITY_OR_EVIDENCE:** shared contract, runner/HFIC wiring, exact
  snapshot-bound passport for `PANEL_REUSE_READY`, killing tests, public smoke.
- **STOP:** PR + exact-head CI. No merge without the exact owner phrase.
- **NEXT:** exact owner merge phrase bound to PR/head.
- **SPEC_ROUTE:** NONE
- **REPLAN_TRIGGER:** pending state still `FAILED_INFRA`; panel reuse does not
  bind; false COMPLETE/REPLAY; owner gate weakened.

## Owner decision

Exact task contract `OBSERVATION_FAST_LANE_ROUTING_CLOSURE_V1` on
`DIRECT_CURSOR_DELIVERY` from `main@0e733c5a4434f936d51b27f3bdc49735c78be3a5`.

## Non-goals

No ObservationScheduler redesign. No new provider/endpoint/auth. No new
estimator/scorer. No trading/promotion. No live provider call. No credential
read. No deployment. No new workflow engine. Do not weaken owner authority
gates. Do not collapse distinct observation terminals into false
"experiment complete".
