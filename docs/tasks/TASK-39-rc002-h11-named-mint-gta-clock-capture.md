---
task_id: TASK-39
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 55479f7f6e23d81c0692f011fa10ed7b98d0614e
  expected_upstream: origin/main
  expected_upstream_oid: 55479f7f6e23d81c0692f011fa10ed7b98d0614e
  expected_branch: cursor/task39-rc002-h11-named-mint-gta
  dirty_mode: ALLOW_REPORTED
objective: Execute one bounded Helius getTransactionsForAddress of the TASK-38 named mint, decode with the pinned Pump subset, and decide whether H11 create/migration clocks reconstruct without GTA of the Pump program.
managed_write_set:
  - docs/tasks/TASK-39-rc002-h11-named-mint-gta-clock-capture.md
  - docs/contracts/task39_rc002_h11_named_mint_gta_clock_capture_contract_v1.md
  - configs/task39_rc002_h11_named_mint_gta_clock_capture_v1.yaml
  - catalog/schemas/task39_rc002_h11_named_mint_gta_clock_capture.schema.json
  - src/solana_alpha_lab/task39_h11_named_mint_gta_clock_capture.py
  - scripts/run_task39_rc002_h11_named_mint_gta_clock_capture.py
  - tests/fixtures/task39/h11_named_mint_gta_clock_capture_v1.json
  - tests/test_task39_rc002_h11_named_mint_gta_clock_capture.py
  - docs/evidence/task39/a1_h11_named_mint_gta_runtime_receipt_v1.json
  - docs/evidence/task39/a1_h11_named_mint_gta_acceptance_v1.json
  - docs/reports/task39/a1_h11_named_mint_gta_owner_readout_v1.md
  - docs/evidence/task39/a1_delivery_completion_evidence_v1.json
  - docs/evidence/task39/a1_delivery_independent_review_v1.json
  - docs/evidence/task39/a1_delivery_factory_fit_v1.json
  - registries/global_trial_ledger.yaml
  - registries/decisions_negative_results.yaml
  - tests/test_catalog.py
  - tests/test_lifecycle_registries.py
  - tests/test_task23_catalog_repository_factory_fit.py
  - tests/fixtures/task28/rc001_registry_freeze_v1.json
  - docs/evidence/task28/a1_rc001_registry_freeze_acceptance_v1.json
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
external_caps:
  network: true
  credentials: true
  external_system: true
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
  - UNBOUNDED_PUMP_PROGRAM_GTA
  - CASH_SPEND_REQUESTED
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
    - EVIDENCE-T38-RC002-H11-NEXT-GTA-001
    - EVIDENCE-T37-RC002-H11-CLOCK-CAPTURE-001
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
      - docs/evidence/task39/a1_h11_named_mint_gta_runtime_receipt_v1.json
      - docs/evidence/task39/a1_h11_named_mint_gta_acceptance_v1.json
      - docs/evidence/task39/a1_delivery_completion_evidence_v1.json
      - docs/evidence/task39/a1_delivery_independent_review_v1.json
      - docs/evidence/task39/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-39 RC002 — named-mint GTA clock capture

## Task Outcome Brief

Owner phrase `OK T39-RC002 H11_NAMED_MINT_GTA_ONE_SHOT` authorizes one bounded Helius GTA of mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` (TASK-38 named target). Payload is the sealed A22 body with two deltas: the address is that mint, and the one-day pool window is omitted so CreateEvent is not cut off. At most three pages. Pump program GTA remains forbidden.

## Decision capsule

- `DECISION_DELTA`: live mint GTA, not pool GTA and not H13/H02.
- `UNCERTAINTY_REMOVED`: whether earliest mint history contains Create/CompletePumpAmmMigration under the pinned decoder.
- `CAPABILITY_OR_EVIDENCE`: retained A4 pages plus a terminal clock verdict.
- `STOP`: merge phrase; no further provider calls in this atom.
- `NEXT`: owner only if a different bounded address (bonding_curve) is later named; do not GTA the Pump program.
- `ROADMAP_VERDICT`: KEEP RC002 H11.
- `strongest_rejected_alternative`: start H13/H02 or GTA the whole Pump program.

## Definition of Done

Pinned mint GTA ran, raw pages retained outside git, TASK-37 scan applied, terminal enum recorded, RC001 unmutated, cash 0.
