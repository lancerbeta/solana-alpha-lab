---
task_id: MARKET_DATA_AWARENESS_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-07"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5feede9b9e66023e6e705710fc2f0b6201a0d30e
  expected_upstream: origin/main
  expected_upstream_oid: 5feede9b9e66023e6e705710fc2f0b6201a0d30e
  expected_branch: cursor/market-data-awareness-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Give Petr one honest owner-facing Market Context on GET /market: what is
  observed now in the tracked early pump.fun lifecycle population, how it
  compares with recent comparable history, how that is covered, and what may
  not be concluded — without a market platform, regime predictor, provider
  calls or deploy.
managed_write_set:
  - docs/tasks/MARKET_DATA_AWARENESS_V1.md
  - docs/contracts/market_data_awareness_v1.md
  - configs/market_context_definition_v1.yaml
  - catalog/schemas/market_context_definition_v1.schema.json
  - catalog/schemas/factory_v1_owner_cockpit.schema.json
  - configs/factory_v1_owner_cockpit_v1.yaml
  - configs/factory_v1_production_lite_runtime_v1.yaml
  - src/solana_alpha_lab/factory/market_context.py
  - src/solana_alpha_lab/factory/market_evidence.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/cockpit.py
  - src/solana_alpha_lab/factory/owner_language.py
  - scripts/show_market_context.py
  - tests/test_market_data_awareness_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_factory_v1_owner_cockpit.py
  - tests/test_owner_workbench_vertical_ux_foundation_v1.py
  - tests/test_owner_operations_cockpit_v1.py
  - tests/test_factory_semantic_operability.py
  - tests/test_catalog_canonical_binding_discovery.py
  - tests/test_owner_lifecycle_projection_spine_v1.py
  - catalog/fixtures/discovery_gold_queries_v1.yaml
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/market_data_awareness/a1_delivery_completion_evidence_v1.json
  - docs/evidence/market_data_awareness/a1_delivery_independent_review_v1.json
  - docs/evidence/market_data_awareness/a1_delivery_factory_fit_v1.json
  - docs/reports/market_data_awareness/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PREDECESSOR_NOT_CANONICALLY_INTEGRATED
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - FRESH_GIT_INVALIDATES_SOURCE_OWNERS
  - EVIDENCE_CANNOT_BE_READ_WITHOUT_MUTATION
  - PROVIDER_CALL_REQUIRED_FOR_MARKET
  - GIT_FIXTURE_USED_AS_CURRENT_MARKET
  - POPULATION_OR_LIFECYCLE_SEMANTICS_UNRECONSTRUCTABLE
  - SURVIVAL_DENOMINATOR_DISHONEST
  - REFERENCE_REQUIRES_FUZZY_INFERENCE
  - DEFINITION_REQUIRES_PNL_OR_OUTCOME
  - NEW_MARKET_DATABASE_OR_SERVICE_REQUIRED
  - SEMANTIC_CURRENT_BINDING_CANNOT_BE_ADDED
  - SEM_MARKET_V2_CREATED
  - SCOPE_EXPANDS_TO_MACRO_ORCH_STRATEGY_PROVIDER_OR_ML
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - delivery-harness/policies/solana-alpha-lab.md
      - docs/contracts/market_data_awareness_v1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/market_data_awareness/a1_delivery_completion_evidence_v1.json
      - docs/evidence/market_data_awareness/a1_delivery_independent_review_v1.json
      - docs/evidence/market_data_awareness/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# MARKET_DATA_AWARENESS_V1

## ENTRY

```text
START_WITH_PATCH
SPEC_ROUTE=BOTH
ROUTE=DIRECT_CURSOR_DELIVERY
PREDECESSOR=RISK_AND_ECONOMICS_V1 canonical on origin/main
BASE=5feede9b9e66023e6e705710fc2f0b6201a0d30e
TIME_GATES=none due
SEMANTIC_ROUTE=SEM-MARKET-DATA-FEATURES (reuse; second root slot free)
```

Design baseline SHA equals fresh `origin/main`. Route budget:
`max_routes=13` (at cap, no SEM-MARKET-V2), `max_root_bindings_per_route=2`
with one used, `max_search_terms_per_route=16` with 7 used.

## FALSIFIERS (fresh bytes)

```text
A /market HIDDEN            YES — cockpit hidden_nav = MARKET
B NO CONTEXT PROJECTOR      YES — no MarketContextProjectionV1
C SCHEDULE SHA COUPLING     YES — comparability would use whole schedule_sha256
D FEATURE SURFACE ≠ CONTEXT YES — SEM-MARKET answers only Git capability
```

## DECISION_DELTA

Market Context is a derived read model over immutable Observation RDP rows.
Git owns definition/compatibility. RDP owns observed values. System owns
runtime health. Relative HIGH/LOW is only vs recent comparable tracked-cohort
history. No composite regime.

## UNCERTAINTY_REMOVED

Whether Petr can see current tracked-cohort context vs recent comparable
history without mistaking Git capability, collector health, or a regime
label for market state.

## CAPABILITY_OR_EVIDENCE

GET `/market` in ≤30s shows SCOPE, AS OF, CONTEXT, RELATIVE STATE, COVERAGE,
INTERPRETATION, NON-CLAIMS. MARKET is the sixth Workbench surface.

## STOP

Exact-head CI + merge-readiness. No deploy. No provider. No VPS.

## NEXT

Owner merge phrase after readiness. Then guarded merge. Do not start
`OWNER_WORKBENCH_VPS_DEPLOY_AND_SMOKE_V1`.

## REPLAN_TRIGGER

Repeated schedule-SHA coupling, GET mutation, pooled lifecycle ages,
PIT leak, dishonest survival denominator, or semantic route budget breach.
