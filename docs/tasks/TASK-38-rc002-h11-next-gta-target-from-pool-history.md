---
task_id: TASK-38
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: d438037a8ff63951c4cb4250e73149a37db1b050
  expected_upstream: origin/main
  expected_upstream_oid: d438037a8ff63951c4cb4250e73149a37db1b050
  expected_branch: cursor/task38-rc002-h11-next-gta-target-from-pool-history
  dirty_mode: ALLOW_REPORTED
objective: From frozen A22/A23 pool-history bytes and the pinned TASK-08 Pump decoder, decide whether a bounded next getTransactionsForAddress target can be named without network.
managed_write_set:
  - docs/tasks/TASK-38-rc002-h11-next-gta-target-from-pool-history.md
  - docs/contracts/task38_rc002_h11_next_gta_target_from_pool_history_contract_v1.md
  - configs/task38_rc002_h11_next_gta_target_from_pool_history_v1.yaml
  - catalog/schemas/task38_rc002_h11_next_gta_target_from_pool_history.schema.json
  - src/solana_alpha_lab/task38_h11_next_gta_target_from_pool_history.py
  - scripts/run_task38_rc002_h11_next_gta_target_from_pool_history.py
  - tests/fixtures/task38/h11_next_gta_target_from_pool_history_v1.json
  - tests/test_task38_rc002_h11_next_gta_target_from_pool_history.py
  - docs/evidence/task38/a1_h11_next_gta_target_runtime_receipt_v1.json
  - docs/evidence/task38/a1_h11_next_gta_target_acceptance_v1.json
  - docs/reports/task38/a1_h11_next_gta_target_owner_readout_v1.md
  - docs/evidence/task38/a1_delivery_completion_evidence_v1.json
  - docs/evidence/task38/a1_delivery_independent_review_v1.json
  - docs/evidence/task38/a1_delivery_factory_fit_v1.json
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
  - UNBOUNDED_PUMP_PROGRAM_GTA
  - NEW_HELIUS_OR_NETWORK_CALL
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
    - EVIDENCE-T30-A24-RAW-TO-PIT-001
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
      - docs/evidence/task38/a1_h11_next_gta_target_runtime_receipt_v1.json
      - docs/evidence/task38/a1_h11_next_gta_target_acceptance_v1.json
      - docs/evidence/task38/a1_delivery_completion_evidence_v1.json
      - docs/evidence/task38/a1_delivery_independent_review_v1.json
      - docs/evidence/task38/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-38 RC002 — next bounded GTA target from pool-history

## Task Outcome Brief

- **Owner decision:** after TASK-37 `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`, name a bounded next `getTransactionsForAddress` target from already captured pool-history bytes, or record that those bytes cannot name one.
- **Product outcome:** either one unique mint or bonding_curve address, or `CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY`.
- **Named consumer:** RC002 H11 — a bounded next GTA address, if any, before any new capture gate.
- **Cheapest falsifier:** freeze the unique resolver, register the trial, then scan adopted A22/A23 rows plus the pinned Pump CreateEvent subset with `network: false`.
- **Terminal outcomes:** `NEXT_BOUNDED_GTA_TARGET_NAMED` | `CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY`.
- **User-visible result:** Russian readout with the exact terminal enum, named kind/address or the resolve gap, and an explicit no-network limitation.
- **Evidence budget:** tracked Git bytes plus read-only local A4 already captured; `cash_usd: 0`; one provider-route identity; no paid plan; no new RPC.
- **Non-goals:** executing GTA; H11 effect test; H13/H02; quotes; entity graph; RC-001 mutation; wallet; deployment; GTA of the whole Pump program.
- **Replan trigger:** second provider; paid capture required; RC-001 hash drift; holdout consumption; treating naming as live GTA authority.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`ADOPTION_ROUTE=ADOPT_EXISTING_HELIUS_GTA_AND_PUMP_EVENT_DECODER`

`ROADMAP_VERDICT=PATCH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH`

## Frozen mission fields

- **DECISION_DELTA:** H11 remains blocked on Create/migration clocks; this atom asks whether pool-history bytes can name a *bounded* next GTA address without a new network call.
- **UNCERTAINTY_REMOVED:** whether a unique mint or bonding_curve is present after excluding the Pump program, the already-scanned pool and the wrapped-SOL quote.
- **CAPABILITY_OR_EVIDENCE:** thin scan over A22/A23 retained bytes plus a task-owned naming trial row.
- **STOP:** no new Helius/GTA call, no unbounded Pump-program GTA, no H13/H02, no paid/API/wallet/deploy, no H11 effect re-screen, no RC-001 mutation.
- **NEXT:** after exact-head CI, stop for the repository merge phrase. Naming is not capture authority.

## Frozen unique resolver

Bound in `configs/task38_rc002_h11_next_gta_target_from_pool_history_v1.yaml` before candidate inspection:

- candidates: pool-owned `preTokenBalances`/`postTokenBalances` mints, plus CreateEvent `mint` / `bonding_curve`
- owner scope: `SCANNED_POOL_ONLY` so incidental co-occurring tokens in the same transactions are not next-GTA candidates
- exclude: Pump program `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`, scanned pool, wrapped-SOL quote
- prefer unique `TOKEN_MINT`; else unique `BONDING_CURVE`; else `CANNOT_RESOLVE`
- multiple remaining mints without a unique resolver are ambiguous and cannot-resolve
- naming does not authorize network

## Definition of Done

- unique resolver frozen in Git before live candidate inspection
- capture trial registered PENDING before first live-scan outcome
- RC-001 freeze hashes unchanged; holdout empty
- targeted tests for unique mint, cannot-resolve (no mint / only program / only pool), incidental-mint non-ambiguity, trial-before-outcome, and no RC-001/holdout mutation
- Factory Fit + Product Horizon Radar
- TASK completion evidence in context L2 `DELIVERY_EVIDENCE`
- exact PR into `origin/main` after TASK-37 / PR #116 merged; merge waits for owner phrase
- no claim of live PIT, execution, alpha, cashflow or canonical DONE
