---
task_id: TASK-37
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 4a25bd3110ef73fa4b7c29851bef0c7261b649ff
  expected_upstream: origin/main
  expected_upstream_oid: 4a25bd3110ef73fa4b7c29851bef0c7261b649ff
  expected_branch: cursor/task37-rc002-h11-migration-clock-capture
  dirty_mode: ALLOW_REPORTED
objective: Reconstruct H11 migration clocks from the adopted Helius pool-history getTransactions batch using pinned Pump Create/migration decode, without a second provider, paid capture, H13/H02 or RC-001 mutation.
managed_write_set:
  - docs/tasks/TASK-37-rc002-h11-migration-clock-capture.md
  - docs/contracts/task37_rc002_h11_migration_clock_capture_contract_v1.md
  - configs/task37_rc002_h11_migration_clock_capture_v1.yaml
  - catalog/schemas/task37_rc002_h11_migration_clock_capture.schema.json
  - src/solana_alpha_lab/task37_h11_migration_clock_capture.py
  - scripts/run_task37_rc002_h11_migration_clock_capture.py
  - tests/fixtures/task37/h11_migration_clock_capture_v1.json
  - tests/test_task37_rc002_h11_migration_clock_capture.py
  - docs/evidence/task37/a1_h11_migration_clock_capture_runtime_receipt_v1.json
  - docs/evidence/task37/a1_h11_migration_clock_capture_acceptance_v1.json
  - docs/reports/task37/a1_h11_migration_clock_capture_owner_readout_v1.md
  - docs/evidence/task37/a1_delivery_completion_evidence_v1.json
  - docs/evidence/task37/a1_delivery_independent_review_v1.json
  - docs/evidence/task37/a1_delivery_factory_fit_v1.json
  - registries/global_trial_ledger.yaml
  - registries/decisions_negative_results.yaml
  - tests/test_catalog.py
  - tests/test_lifecycle_registries.py
  - tests/test_task23_catalog_repository_factory_fit.py
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - RC001_FREEZE_MUTATED
  - RC001_HOLDOUT_CONSUMED
  - LIVE_PIT_OR_EXECUTION_CLAIM
  - SECOND_PROVIDER_PIVOT
  - PAID_PLAN_OR_NEW_ACCOUNT
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - H13_OR_H02_TRIAL_STARTED
  - GENERIC_COLLECTOR_FRAMEWORK
  - H11_EFFECT_SCREEN_RERUN
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
    - EVIDENCE-T30-A24-RAW-TO-PIT-001
    - EVIDENCE-T36-RC002-H11-LIFECYCLE-CLOCK-001
    - MODULE-T08-PUMP-EVENT-DECODER-001
  l2_roles: [DELIVERY_EVIDENCE, LIFECYCLE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE:
      - registries/global_trial_ledger.yaml
      - registries/decisions_negative_results.yaml
      - registries/holdout_consumption.yaml
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v6.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/task37/a1_h11_migration_clock_capture_runtime_receipt_v1.json
      - docs/evidence/task37/a1_h11_migration_clock_capture_acceptance_v1.json
      - docs/evidence/task37/a1_delivery_completion_evidence_v1.json
      - docs/evidence/task37/a1_delivery_independent_review_v1.json
      - docs/evidence/task37/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-37 RC002 — H11 migration-clock capture

## Task Outcome Brief

- **Owner decision:** `делаем захват часов` — bounded historical reconstruction of H11 migration clocks after the TASK-36 `HISTORICAL_ROUTE_INADEQUATE_REPLAN`.
- **Product outcome:** reconstructed clocks plus an honest post-migration universe, or an exact address/event gap on the adopted pool-history route.
- **Named consumer:** RC002 H11 — clocks must exist before any effect re-screen.
- **Cheapest falsifier:** freeze clock definitions, register the trial, then decode the already-captured A22/A23 pool-history batch with the pinned Pump event subset.
- **Terminal outcomes:** `CLOCKS_RECONSTRUCTED_COHORT_READY` | `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT` | `INSUFFICIENT_SCALE_WITHOUT_PAID_CAPTURE` | `STOP_INTEGRITY_CONFLICT`.
- **User-visible result:** Russian readout with the exact terminal enum, N / clusters, and the Create/migration gap if present.
- **Evidence budget:** tracked Git bytes plus read-only local A4 already captured; `cash_usd: 0`; one provider-route identity; no paid plan; no new RPC.
- **Non-goals:** alpha; H11 effect test; H13/H02; quotes/ROUTE_FEASIBILITY; generic collector; RC-001 mutation; wallet; deployment.
- **Replan trigger:** second provider; paid capture required; RC-001 hash drift; holdout consumption; live-PIT conversion.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`ADOPTION_ROUTE=ADOPT_EXISTING_HELIUS_GTA_AND_PUMP_EVENT_DECODER`

`ROADMAP_VERDICT=PATCH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## Frozen mission fields

- **DECISION_DELTA:** H11 remains blocked on clocks, not on another mechanism screen; this atom asks whether the adopted pool-history route can form those clocks.
- **UNCERTAINTY_REMOVED:** whether Create/CompletePumpAmmMigrationEvent exist in `getTransactionsForAddress(pool)` and whether a contiguous outcome-independent cohort can be frozen from them.
- **CAPABILITY_OR_EVIDENCE:** thin decode over A22/A23 retained bytes plus a task-owned capture trial row.
- **STOP:** no H13/H02, no second provider, no paid/API/wallet/deploy, no H11 effect re-screen, no RC-001 mutation.
- **NEXT:** after exact-head CI, stop for the repository merge phrase. After merge, act only on the terminal capture verdict.

## Definition of Done

- clock definitions frozen in Git before event inspection
- capture trial registered before first live-scan outcome
- RC-001 freeze hashes unchanged; holdout empty
- targeted tests for no-future running peak, chain-event migration timestamp, typed missingness, fingerprints, trial-before-outcome, and no RC-001/holdout mutation
- Factory Fit + Product Horizon Radar
- TASK completion evidence in context L2 `DELIVERY_EVIDENCE`
- exact PR into `origin/main` after TASK-36 / PR #115 merged; merge waits for owner phrase
