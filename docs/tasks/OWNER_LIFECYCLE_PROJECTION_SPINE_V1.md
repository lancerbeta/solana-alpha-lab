---
task_id: OWNER_LIFECYCLE_PROJECTION_SPINE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-05'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5e9779e448543752ed19d5209b3f7184ae5d2196
  expected_upstream: origin/main
  expected_upstream_oid: 5e9779e448543752ed19d5209b3f7184ae5d2196
  expected_branch: cursor/owner-lifecycle-projection-spine-v1
  dirty_mode: ALLOW_REPORTED
objective: Give owner-facing consumers one derived lifecycle index of what objects
  exist, where their truth lives, and which explicit relations connect them, without
  a second truth store or Workbench redesign.
managed_write_set:
- docs/tasks/OWNER_LIFECYCLE_PROJECTION_SPINE_V1.md
- docs/contracts/owner_lifecycle_projection_spine_v1.md
- configs/owner_lifecycle_projection_v1.yaml
- catalog/schemas/owner_lifecycle_projection_v1.schema.json
- src/solana_alpha_lab/factory/lifecycle_projection.py
- src/solana_alpha_lab/factory/application.py
- scripts/show_owner_lifecycle_projection.py
- tests/test_owner_lifecycle_projection_spine_v1.py
- configs/execution_domain_v1.json
- configs/factory_semantic_operability_v1.yaml
- configs/factory_v1_operational_readiness_v1.yaml
- catalog/catalog_manifest.yaml
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- catalog/fixtures/semantic_route_gold_queries_v1.yaml
- tests/test_factory_semantic_operability.py
- tests/test_catalog_canonical_binding_discovery.py
- docs/FACTORY_SEMANTIC_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/PROJECT_MAP.md
- docs/evidence/owner_lifecycle_projection_spine/a1_delivery_completion_evidence_v1.json
- docs/evidence/owner_lifecycle_projection_spine/a1_delivery_independent_review_v1.json
- docs/evidence/owner_lifecycle_projection_spine/a1_delivery_factory_fit_v1.json
- docs/reports/owner_lifecycle_projection_spine/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- SECOND_LIFECYCLE_TRUTH_STORE_REQUIRED
- LEGACY_REGISTRY_BACKFILL_REQUIRED
- HISTORICAL_SEMANTICS_MUST_BE_INVENTED
- RELATION_REQUIRES_FILENAME_OR_TEXT_GUESS
- NEW_DATABASE_REQUIRED
- GRAPH_DATABASE_REQUIRED
- NEW_BACKGROUND_SERVICE_REQUIRED
- WORKBENCH_REDESIGN_REQUIRED
- DOMAIN_LIFECYCLE_REWRITE_REQUIRED
- RESEARCHSTORE_MIGRATION_REQUIRED
- PAPERPLANE_POSITION_MODEL_REPLACEMENT_REQUIRED
- PROVIDER_OR_EXTERNAL_READ_REQUIRED
- DEPLOYMENT_REQUIRED
- CREDENTIAL_REQUIRED
- REAL_MONEY_OR_WALLET_REQUIRED
- UNRESOLVED_MATERIAL_IDENTITY_CONFLICT
- REPEATED_MATERIAL_BLOCKER
context_requirements:
  catalog_asset_ids: []
  l2_roles:
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
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/owner_lifecycle_projection_spine/a1_delivery_completion_evidence_v1.json
    - docs/evidence/owner_lifecycle_projection_spine/a1_delivery_independent_review_v1.json
    - docs/evidence/owner_lifecycle_projection_spine/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OWNER_LIFECYCLE_PROJECTION_SPINE_V1

## SPEC_ROUTE

`BOTH` — owner packet is the PRD; this file is the exact Git task contract;
`docs/contracts/owner_lifecycle_projection_spine_v1.md` plus
`configs/owner_lifecycle_projection_v1.yaml` are the durable design spec.

## DECISION_DELTA

Move 0 / WAVE A Product Truth: one derived `LifecycleProjectionV1` index over
existing source owners. Incomplete explicit graph with `GAP`/`UNKNOWN` is
success. A guessed complete graph is failure.

## UNCERTAINTY_REMOVED

A fresh owner-facing consumer can ask which lifecycle objects exist, where
each fact comes from, and which explicit relations connect them, without
manual Git/SQLite archaeology.

## CAPABILITY_OR_EVIDENCE

Derived index envelope, FactoryApplication read API, read-only inspection CLI,
Catalog binding `ACTIVE-OWNER-LIFECYCLE-PROJECTION`, semantic route
`SEM-OWNER-LIFECYCLE`, gold queries, generated navigation.

## NON-GOALS

No Workbench redesign; no lifecycle migration; no new database; no graph
platform; no workflow engine; no runtime deployment; no scientific experiment;
no strategy promotion; no alpha/economic claim; no legacy-registry backfill.

## ENTRY VERDICT

`START_AS_WRITTEN`

Revalidated `origin/main=5e9779e448543752ed19d5209b3f7184ae5d2196`. No competing
`OWNER_LIFECYCLE_PROJECTION` owner on main.

## FACTORY FIT / PRODUCT HORIZON

`NOW` because named downstream consumers already exist. Does not establish
alpha, Owner Workbench complete, or runtime health.

`WATCH`: `RESEARCH_LIFECYCLE_WORKBENCH_V1` consumes this index. Do not auto-start.

## CHEAPEST FALSIFIER

Tracked objects `NEGATIVE-T30-CURRENT-DATA-ROUTE-001`,
`EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001`, and `STRAT-V-EARLY-LIQ-FLOOR@V1`
appear with explicit provenance; missing hypothesis targets stay `TARGET_GAP`;
filename/summary inference is absent; empty legacy registries stay empty.

## DONE

`OWNER_LIFECYCLE_PROJECTION_SPINE_V1_PASS` when the derived contract, adapters,
inspection surface, Catalog route, isolated critics, Factory Fit, and
exact-head CI/harness evidence are complete, with no second truth store and
no Workbench redesign.
