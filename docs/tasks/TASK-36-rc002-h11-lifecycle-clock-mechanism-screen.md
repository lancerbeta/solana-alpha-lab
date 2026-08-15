---
task_id: TASK-36
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ea90d5152d06719224cbf971116584452494a0ef
  expected_upstream: origin/main
  expected_upstream_oid: ea90d5152d06719224cbf971116584452494a0ef
  expected_branch: cursor/task36-rc002-h11-lifecycle-clock-screen
  dirty_mode: ALLOW_REPORTED
objective: Run one frozen exploratory H11 lifecycle-clock mechanism screen on a new RC-002 cycle using adopted historical reconstruction, without starting H13/H02 or mutating RC-001.
managed_write_set:
  - docs/tasks/TASK-36-rc002-h11-lifecycle-clock-mechanism-screen.md
  - docs/contracts/task36_rc002_h11_lifecycle_clock_screen_contract_v1.md
  - configs/task36_rc002_h11_lifecycle_clock_screen_v1.yaml
  - catalog/schemas/task36_rc002_h11_lifecycle_clock_screen.schema.json
  - src/solana_alpha_lab/task36_h11_lifecycle_clock_screen.py
  - scripts/run_task36_rc002_h11_lifecycle_clock_screen.py
  - tests/fixtures/task36/h11_lifecycle_clock_screen_v1.json
  - tests/test_task36_rc002_h11_lifecycle_clock_screen.py
  - docs/evidence/task36/a1_h11_lifecycle_clock_screen_runtime_receipt_v1.json
  - docs/evidence/task36/a1_h11_lifecycle_clock_screen_acceptance_v1.json
  - docs/reports/task36/a1_h11_lifecycle_clock_screen_owner_readout_v1.md
  - docs/evidence/task36/a1_delivery_completion_evidence_v1.json
  - docs/evidence/task36/a1_delivery_independent_review_v1.json
  - docs/evidence/task36/a1_delivery_factory_fit_v1.json
  - registries/global_trial_ledger.yaml
  - registries/decisions_negative_results.yaml
  - tests/fixtures/task28/rc001_registry_freeze_v1.json
  - docs/evidence/task28/a1_rc001_registry_freeze_acceptance_v1.json
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
  - PARAMETER_OR_ML_SEARCH
  - MISSING_TO_ZERO
  - SECOND_PROVIDER_PIVOT
  - PAID_PLAN_OR_NEW_ACCOUNT
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - H13_OR_H02_TRIAL_STARTED
  - GENERIC_COLLECTOR_FRAMEWORK
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
    - EVIDENCE-T30-A24-RAW-TO-PIT-001
    - EVIDENCE-T30-A27-H07-H01-LIQUIDITY-RETENTION-PARK-001
  l2_roles: [DELIVERY_EVIDENCE, LIFECYCLE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE:
      - registries/global_trial_ledger.yaml
      - registries/decisions_negative_results.yaml
      - registries/holdout_consumption.yaml
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/task08/lifecycle_discovery_probe_execution_receipt_v1.json
      - docs/evidence/task09/pumpswap_touch_probe_execution_receipt_v1.json
      - docs/evidence/task21/effective_sample_summary_v1.json
      - docs/evidence/task30/a24_raw_to_pit_admissibility_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-36 RC002 — H11 lifecycle-clock mechanism screen

## Task Outcome Brief

- **Owner decision:** accept H11 as the next cheap falsifier after parking H07/H01. Reorder remaining RC-001 work behind this screen.
- **Product outcome:** a reproducible exploratory H11 mechanism verdict from a bounded predeclared post-migration cohort, or an explicit historical-route inadequacy decision.
- **Named consumer:** Alpha Factory throughput — idea → cheap falsifier → kill or earn-next-evidence.
- **Cheapest falsifier:** freeze the protocol, register the trial, then inspect whether adopted historical routes can reconstruct lifecycle clocks and whether those clocks add stable OOS information beyond UTC/session.
- **Terminal outcomes:** `H11_SCREEN_NEGATIVE_DEPRIORITIZE_OR_CLOSE` | `H11_SCREEN_POSITIVE_EARNS_PROSPECTIVE_CONFIRMATION` | `H11_SCREEN_INCONCLUSIVE_DATA_SCALE` | `HISTORICAL_ROUTE_INADEQUATE_REPLAN` | `STOP_INTEGRITY_CONFLICT`.
- **User-visible result:** Russian owner readout with the exact terminal enum, N / independent units, and non-claims.
- **Evidence budget:** tracked Git bytes only; `cash_usd: 0`; one provider-route identity at most; no paid plan.
- **Non-goals:** alpha; NetReturn / RealizedVWAP / fillability; strategy/bot; RC-001 mutation; entity graph; route-feasibility/quote panel; wallet; cockpit/UI; deployment; unattended collector; new DB/framework; ML search; H13/H02 trials.
- **Replan trigger:** second provider pivot; paid capture required; RC-001 hash drift; holdout consumption; live-PIT conversion.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`ADOPTION_ROUTE=ADOPT_EXISTING_LIFECYCLE_HELIUS_PUMPSWAP_HISTORY`

`ROADMAP_VERDICT=REORDER`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## Frozen mission fields

- **DECISION_DELTA:** remaining blocked RC-001 families are deprioritized; RC-002 H11 is the next cheap screen.
- **UNCERTAINTY_REMOVED:** whether lifecycle-relative clocks, reconstructed retrospectively, contain stable incremental information beyond wall-clock/session — or whether the adopted historical route cannot even form those clocks.
- **CAPABILITY_OR_EVIDENCE:** thin analysis over adopted TASK-08/09/21/30 receipts plus a task-owned RC-002 register and one trial row.
- **STOP:** no H13/H02, no collector framework, no RC-001 mutation, no holdout, no paid/API/wallet/deploy.
- **NEXT:** after exact-head CI, stop for the repository merge phrase. After merge, act only on the terminal research verdict.

## Definition of Done

- protocol frozen in Git before outcome inspection
- exploratory trial registered before first outcome read
- RC-001 freeze hashes unchanged; holdout empty
- targeted tests for decision-time ordering, running-peak no-future, cohort freeze, typed missingness, fingerprints, trial-before-outcome, and no RC-001/holdout mutation
- Factory Fit + Product Horizon Radar
- exact PR; merge waits for owner phrase
