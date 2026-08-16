---
task_id: TASK-40
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 6089e1d011562de43068a26a8f5feb17c4c2abcf
  expected_upstream: origin/main
  expected_upstream_oid: 6089e1d011562de43068a26a8f5feb17c4c2abcf
  expected_branch: cursor/task40-rc002-h11-bonding-curve-pda-gta
  dirty_mode: ALLOW_REPORTED
objective: Derive the unique Pump bonding_curve PDA for the TASK-38 mint from a pinned official IDL seed subset, then run one bounded Helius GTA of that address and decide whether H11 create/migration clocks reconstruct.
managed_write_set:
  - docs/tasks/TASK-40-rc002-h11-bonding-curve-pda-gta-clock-capture.md
  - docs/contracts/task40_rc002_h11_bonding_curve_pda_gta_clock_capture_contract_v1.md
  - configs/task40_rc002_h11_bonding_curve_pda_gta_clock_capture_v1.yaml
  - catalog/schemas/task40_rc002_h11_bonding_curve_pda_gta_clock_capture.schema.json
  - tests/fixtures/task08/pump_bonding_curve_pda_subset_v1.json
  - src/solana_alpha_lab/task40_h11_bonding_curve_pda_gta_clock_capture.py
  - scripts/run_task40_rc002_h11_bonding_curve_pda_gta_clock_capture.py
  - tests/fixtures/task40/h11_bonding_curve_pda_gta_clock_capture_v1.json
  - tests/test_task40_rc002_h11_bonding_curve_pda_gta_clock_capture.py
  - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_runtime_receipt_v1.json
  - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_acceptance_v1.json
  - docs/reports/task40/a1_h11_bonding_curve_pda_gta_owner_readout_v1.md
  - docs/evidence/task40/a1_delivery_completion_evidence_v1.json
  - docs/evidence/task40/a1_delivery_independent_review_v1.json
  - docs/evidence/task40/a1_delivery_factory_fit_v1.json
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
  - PDA_ADDRESS_DRIFT
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
    - EVIDENCE-T39-RC002-H11-NAMED-MINT-GTA-001
    - EVIDENCE-T38-RC002-H11-NEXT-GTA-001
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
      - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_runtime_receipt_v1.json
      - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_acceptance_v1.json
      - docs/evidence/task40/a1_delivery_completion_evidence_v1.json
      - docs/evidence/task40/a1_delivery_independent_review_v1.json
      - docs/evidence/task40/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-40 RC002 — bonding_curve PDA GTA clock capture

## Task Outcome Brief

After TASK-39 `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT` on mint GTA, name the unique Pump `bonding_curve` by PDA seeds from the official IDL, then run one bounded Helius GTA of that address. Payload is the sealed A22 body with two deltas: the address is the derived curve, and the one-day pool window is omitted. At most three pages. Pump program GTA remains forbidden.

## Decision capsule

- `DECISION_DELTA`: live bonding_curve GTA, not mint GTA, not pool GTA, not H13/H02.
- `UNCERTAINTY_REMOVED`: whether earliest bonding_curve history contains Create/CompletePumpAmmMigration under the pinned decoder.
- `CAPABILITY_OR_EVIDENCE`: pinned PDA subset plus retained A4 pages plus a terminal clock verdict.
- `STOP`: merge phrase; no further provider calls in this atom.
- `NEXT`: after exact-head CI, stop for the repository merge phrase. Act only on the terminal capture verdict.
- `ROADMAP_VERDICT`: KEEP RC002 H11.
- `strongest_rejected_alternative`: naming-only atom (prepares work without a falsifier); further mint pagination (oldest 3000 already had zero Create/Migration); GTA of the Pump program.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`ADOPTION_ROUTE=ADOPT_EXISTING_HELIUS_GTA_AND_PINNED_PUMP_PDA`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## Definition of Done

Pinned PDA derives the frozen curve address, bounded GTA ran, raw pages retained outside git, TASK-37 scan applied, terminal enum recorded, RC001 unmutated, cash 0.
