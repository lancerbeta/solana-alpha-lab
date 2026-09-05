---
task_id: RESEARCH_LIFECYCLE_WORKBENCH_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-05"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 97281cccca06365515b282868174cdfd0b023845
  expected_upstream: origin/main
  expected_upstream_oid: 97281cccca06365515b282868174cdfd0b023845
  expected_branch: cursor/research-lifecycle-workbench-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Turn /research into the first useful owner-facing research lifecycle
  workflow over LifecycleProjectionV1, without a second truth store,
  research mutation, new semantic route, or production deploy.
managed_write_set:
  - docs/tasks/RESEARCH_LIFECYCLE_WORKBENCH_V1.md
  - docs/contracts/research_lifecycle_workbench_v1.md
  - docs/contracts/owner_lifecycle_projection_spine_v1.md
  - configs/owner_lifecycle_projection_v1.yaml
  - catalog/schemas/owner_lifecycle_projection_v1.schema.json
  - src/solana_alpha_lab/factory/lifecycle_projection.py
  - src/solana_alpha_lab/factory/research_store.py
  - src/solana_alpha_lab/factory/data_root.py
  - src/solana_alpha_lab/factory/research_workbench.py
  - src/solana_alpha_lab/factory/visual_os.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/workbench.py
  - scripts/run_factory_workbench.py
  - tests/test_research_lifecycle_workbench_v1.py
  - tests/test_owner_lifecycle_projection_spine_v1.py
  - tests/test_factory_v1_owner_cockpit.py
  - tests/test_owner_operations_cockpit_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_factory_semantic_operability.py
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/research_lifecycle_workbench/a1_delivery_completion_evidence_v1.json
  - docs/evidence/research_lifecycle_workbench/a1_delivery_independent_review_v1.json
  - docs/evidence/research_lifecycle_workbench/a1_delivery_factory_fit_v1.json
  - docs/reports/research_lifecycle_workbench/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - MOVE0_NOT_CANONICAL
  - GLOBAL_TRIAL_LEDGER_OWNER_CONFLICT
  - RESEARCHSTORE_READ_REQUIRES_MAJOR_STORAGE_REWRITE
  - SECOND_TRUTH_STORE_REQUIRED
  - NEW_DATABASE_REQUIRED
  - NEW_FRONTEND_FRAMEWORK_REQUIRED
  - NEW_BACKGROUND_SERVICE_REQUIRED
  - UI_MUST_REBUILD_LIFECYCLE_JOINS
  - GENERIC_HYPOTHESIS_STATE_MACHINE_REQUIRED
  - MOVE2_EVIDENCE_PLATFORM_REQUIRED
  - PROMOTION_COMMAND_REQUIRED
  - CURRENT_OPERATIONS_COMMAND_SEMANTICS_MUST_CHANGE
  - PROVIDER_OR_EXTERNAL_CALL_REQUIRED
  - DEPLOYMENT_REQUIRED
  - CREDENTIAL_REQUIRED
  - REAL_MONEY_REQUIRED
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
    - docs/evidence/research_lifecycle_workbench/a1_delivery_completion_evidence_v1.json
    - docs/evidence/research_lifecycle_workbench/a1_delivery_independent_review_v1.json
    - docs/evidence/research_lifecycle_workbench/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RESEARCH_LIFECYCLE_WORKBENCH_V1

## SPEC_ROUTE

`BOTH` — owner packet is the PRD; this file is the exact Git task contract;
`docs/contracts/research_lifecycle_workbench_v1.md` is the durable human
contract. No second machine projection schema.

## DECISION_DELTA

Move 1 / WAVE A Product Truth: `/research` becomes a read-only owner
workflow over `LifecycleProjectionV1`. Workbench composes overview/detail;
it does not own lifecycle identity or invent joins.

## UNCERTAINTY_REMOVED

Petr can answer what exists, what is active, what was tested, what is
known/blocked/unknown, and where a selected object came from, without Git,
SSH, or SQLite archaeology.

## CAPABILITY_OR_EVIDENCE

Read-only ResearchStore boundary, global-trial-ledger adapter, typed
research overview/detail, plane-safe locator, STEEL_SIGNAL shell,
SEM-OWNER-LIFECYCLE second binding, Catalog/generated navigation.

## NON-GOALS

No research mutation; no new semantic route; no new database; no frontend
framework; no systemd/deploy; no Move-2 evidence-quality platform; no
invented lifecycle states; no README/AGENTS edit.

## ENTRY VERDICT

`START`

Revalidated `origin/main=97281cccca06365515b282868174cdfd0b023845`
(PR #268, post-merge CI run 33990262803 success). Plane-ambiguity patch
`86032126` is in that merge. `REGISTRY-GLOBAL-TRIAL-LEDGER-001` remains
`VALIDATED_ACTIVE`.

## FACTORY FIT / PRODUCT HORIZON

`NOW` because Move 0 is canonical and `/research` is still a selected-spec
placeholder. Does not establish alpha, experiment evidence quality, or VPS
deployed state.

`WATCH`: `EXPERIMENT_EVIDENCE_DECISION_V1`. Do not auto-start.

## CHEAPEST FALSIFIER

Real `TRIAL-RC002-H11-NEXT-GTA-TARGET-001`,
`EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001`, and
`NEGATIVE-T30-CURRENT-DATA-ROUTE-001` appear through `/research`;
missing ResearchStore stays missing; plane-conflict locators stay distinct.

## DONE

`RESEARCH_LIFECYCLE_WORKBENCH_V1_PASS` when the four owner loops, read-only
proof, Visual OS shell, existing-route semantic closure, isolated critics,
Factory Fit, and exact-head CI/harness evidence are complete.
