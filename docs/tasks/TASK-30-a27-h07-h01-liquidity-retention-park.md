---
task_id: TASK-30
task_version: '27.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 87283799319c1fc073b162dd36027ae80cb402da
  expected_upstream: origin/main
  expected_upstream_oid: 87283799319c1fc073b162dd36027ae80cb402da
  expected_branch: cursor/task30-a27-h07-h01-liquidity-retention-park
  dirty_mode: ALLOW_REPORTED
objective: Apply the exact A26 retire phrase as a park-from-priority decision for RC001-H07-H01, keep A24/A25/A26 science in git, and leave TASK-30 BLOCKED_DATA.
managed_write_set:
  - docs/tasks/TASK-30-a27-h07-h01-liquidity-retention-park.md
  - docs/contracts/task30_a27_h07_h01_liquidity_retention_park_contract_v1.md
  - configs/task30_a27_h07_h01_liquidity_retention_park_v1.yaml
  - catalog/schemas/task30_a27_h07_h01_liquidity_retention_park.schema.json
  - src/solana_alpha_lab/task30_h07_h01_liquidity_retention_park.py
  - scripts/run_task30_a27_h07_h01_liquidity_retention_park.py
  - tests/fixtures/task30/h07_h01_liquidity_retention_park_v1.json
  - tests/test_task30_a27_h07_h01_liquidity_retention_park.py
  - docs/evidence/task30/a27_h07_h01_liquidity_retention_park_runtime_receipt_v1.json
  - docs/evidence/task30/a27_h07_h01_liquidity_retention_park_acceptance_v1.json
  - docs/reports/task30/a27_h07_h01_liquidity_retention_park_owner_readout_v1.md
  - docs/evidence/task30/a27_delivery_completion_evidence_v1.json
  - docs/evidence/task30/a27_delivery_independent_review_v1.json
  - docs/evidence/task30/a27_delivery_factory_fit_v1.json
  - registries/decisions_negative_results.yaml
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - tests/test_lifecycle_registries.py
  - tests/test_catalog.py
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - A26_ACCEPTANCE_HASH_DRIFT
  - A26_TERMINAL_DRIFT
  - OWNER_PHRASE_DRIFT
  - RETAINED_EVIDENCE_MISSING_OR_HASH_DRIFT
  - RC001_FREEZE_MUTATED
  - SCIENCE_DELETION_ATTEMPTED
  - NOTIONAL_BUCKETS_FROZEN
  - ROUTE_FEASIBILITY_CAPTURE_AUTHORIZED
  - H13_OR_H02_TRIAL_STARTED
  - PROVIDER_OR_CREDENTIAL_CALL_REQUIRED
  - CASH_OR_WALLET_OR_SIGNER_ACTION
  - TASK30_OR_RC001_PROMOTION
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-T30-A24-RAW-TO-PIT-001
    - EVIDENCE-T30-A25-H07-H01-MEASURABILITY-001
    - EVIDENCE-T30-A26-H07-H01-OWNER-FORK-001
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
  l2_roles: [DELIVERY_EVIDENCE, LIFECYCLE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE:
      - registries/decisions_negative_results.yaml
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/task30/a27_h07_h01_liquidity_retention_park_runtime_receipt_v1.json
      - docs/evidence/task30/a27_h07_h01_liquidity_retention_park_acceptance_v1.json
      - docs/evidence/task30/a27_delivery_completion_evidence_v1.json
      - docs/evidence/task30/a27_delivery_independent_review_v1.json
      - docs/evidence/task30/a27_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-30 A27 — park RC001 H07/H01 from priority

## Task Outcome Brief

- **Owner decision:** park `RC001-H07-H01-LIQUIDITY-RETENTION` from factory priority after the exact A26 retire phrase. Keep science. Do not start H13 or H02 trials.
- **Product outcome:** a hash-bound park decision that closes future unpaid/paid spend on this family without deleting A24/A25/A26 evidence.
- **Named consumers:** `RC001-H07-H01-LIQUIDITY-RETENTION` and the factory's next-family priority.
- **Cheapest falsifier:** re-read frozen A26 acceptance, retained A24/A25/A26 hashes and the RC001 freeze. If any drifted, or if the phrase is not exact, this packet is false.
- **Terminal outcomes:** `RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED` or `STOP_INTEGRITY_CONFLICT`.
- **User-visible result:** Russian owner readout that the family is parked, science is retained, TASK-30 stays `BLOCKED_DATA`.
- **Evidence budget:** tracked Git bytes only; zero provider, credential, network or cash side effects.
- **Non-goals:** TASK-30 DONE; RC001 definition change; H07/H01 trial; H13/H02 trials; notional freeze; `ROUTE_FEASIBILITY` capture; provider purchase; science deletion; alpha; cashflow.
- **Replan trigger:** A26 or retained-evidence drift; freeze mutation; any spend, capture or trial becoming necessary.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`ADOPTION_ROUTE=WRAP_FROZEN_A26_OWNER_FORK`

`OWNER_CAPTURE_PHRASE=OK T30-A26 RETIRE_RC001_H07_H01_LIQUIDITY_RETENTION`

## Frozen mission fields

- **DECISION_DELTA:** H07/H01 leaves the live priority queue. Retirement here means park-from-priority; research memory stays.
- **UNCERTAINTY_REMOVED:** whether the owner chose retire/park versus freeze notionals or later capture. They chose park.
- **CAPABILITY_OR_EVIDENCE:** append-only decision plus retained-evidence proof. No decoder, route, dependency or trial.
- **STOP:** zero provider, credential, network, cash, wallet or signer side effects; no TASK-30 or RC001 promotion; no freeze mutation; no H13/H02 start.
- **NEXT:** after exact-head CI, stop for the repository merge phrase. After merge the factory picks the next bounded family without treating this as TASK-30 DONE.
