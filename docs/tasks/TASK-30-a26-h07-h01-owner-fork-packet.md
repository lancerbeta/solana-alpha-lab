---
task_id: TASK-30
task_version: '26.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-15'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 0b89358b2f060a6d89c69dfed6563c2f6c966a67
  expected_upstream: origin/main
  expected_upstream_oid: 0b89358b2f060a6d89c69dfed6563c2f6c966a67
  expected_branch: cursor/task30-a26-h07-h01-owner-fork-packet
  dirty_mode: ALLOW_REPORTED
objective: Prove from frozen A25 evidence and the current provider registry that a $5 Helius one-shot cannot falsify RC001-H07-H01, and encode the exact unpaid owner fork without spending or capturing.
managed_write_set:
  - docs/tasks/TASK-30-a26-h07-h01-owner-fork-packet.md
  - docs/contracts/task30_a26_h07_h01_owner_fork_packet_contract_v1.md
  - configs/task30_a26_h07_h01_owner_fork_packet_v1.yaml
  - catalog/schemas/task30_a26_h07_h01_owner_fork_packet.schema.json
  - src/solana_alpha_lab/task30_h07_h01_owner_fork_packet.py
  - scripts/run_task30_a26_h07_h01_owner_fork_packet.py
  - tests/fixtures/task30/h07_h01_owner_fork_packet_v1.json
  - tests/test_task30_a26_h07_h01_owner_fork_packet.py
  - docs/evidence/task30/a26_h07_h01_owner_fork_packet_runtime_receipt_v1.json
  - docs/evidence/task30/a26_h07_h01_owner_fork_packet_acceptance_v1.json
  - docs/reports/task30/a26_h07_h01_owner_fork_packet_owner_readout_v1.md
  - docs/evidence/task30/a26_delivery_completion_evidence_v1.json
  - docs/evidence/task30/a26_delivery_independent_review_v1.json
  - docs/evidence/task30/a26_delivery_factory_fit_v1.json
  - registries/decisions_negative_results.yaml
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
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
  - A25_TERMINAL_DRIFT
  - A25_ACCEPTANCE_HASH_DRIFT
  - PROVIDER_REGISTRY_DRIFT
  - ROUTE_FEASIBILITY_ROUTE_SILENTLY_INVENTED
  - NOTIONAL_BUCKETS_GUESSED
  - FIVE_DOLLAR_SPEND_TREATED_AS_FALSIFIER
  - PROVIDER_OR_CREDENTIAL_CALL_REQUIRED
  - CASH_OR_WALLET_OR_SIGNER_ACTION
  - TASK30_OR_RC001_PROMOTION
  - HYPOTHESIS_RETIRED_WITHOUT_OWNER_PHRASE
  - EVIDENCE_OR_TIME_BUDGET_EXCEEDED
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-T30-A25-H07-H01-MEASURABILITY-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-006
    - CONFIG-T28-RC001-REGISTRY-FREEZE-001
  l2_roles: [DELIVERY_EVIDENCE, ARCHITECTURE_DECISIONS]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/decisions/ADR-002-mvp-stack.md
    DELIVERY_EVIDENCE:
      - docs/evidence/task30/a26_h07_h01_owner_fork_packet_runtime_receipt_v1.json
      - docs/evidence/task30/a26_h07_h01_owner_fork_packet_acceptance_v1.json
      - docs/evidence/task30/a26_delivery_completion_evidence_v1.json
      - docs/evidence/task30/a26_delivery_independent_review_v1.json
      - docs/evidence/task30/a26_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TASK-30 A26 — $5 cannot falsify H07/H01 owner-fork packet

## Task Outcome Brief

- **Owner decision:** whether to retire `RC001-H07-H01-LIQUIDITY-RETENTION`, freeze `NOTIONAL_BUCKET_SET_V1`, or later fund a ≥4 `POOL_DAY` `ROUTE_FEASIBILITY` variance-calibration. This atom does not choose.
- **Product outcome:** a machine-checked proof that a ~$5 Helius one-shot cannot falsify the frozen estimand, plus exact owner phrases for the unpaid fork.
- **Named consumers:** `RC001-H07-H01-LIQUIDITY-RETENTION` and the owner's spend-versus-retire decision.
- **Cheapest falsifier:** re-read the frozen A25 acceptance and provider registry v6. If Helius can supply the 13 `ROUTE_FEASIBILITY` fields, or if 4 clusters are already present, or if `$5` can buy them, this packet is false.
- **Terminal outcomes:** `FIVE_DOLLAR_HELIUS_CANNOT_FALSIFY_OWNER_FORK_READY` or `STOP_INTEGRITY_CONFLICT`.
- **User-visible result:** Russian owner readout with the proof, the registry gap, and three exact next phrases. No purchase, no capture.
- **Evidence budget:** tracked Git bytes only; zero provider, credential, network or cash side effects; about 20 minutes for the cheapest falsifier.
- **Non-goals:** TASK-30 acceptance or DONE; H07/H01 trial; alpha; PnL/NetReturn/cashflow; notional-bucket guessing; Jupiter or Helius calls; registry mutation; subscription; wallet/signer/card; retiring the hypothesis.
- **Replan trigger:** A25 or registry drift; a `ROUTE_FEASIBILITY` route appearing without an observed receipt; a guessed notional set; any spend or provider call becoming necessary.

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=BOTH`

`ADOPTION_ROUTE=WRAP_FROZEN_A25_AND_CURRENT_REGISTRY`

`OWNER_CAPTURE_PHRASE=OK T30-A26 H07_H01_FIVE_DOLLAR_CANNOT_FALSIFY_OWNER_FORK_PACKET`

## Frozen mission fields

- **DECISION_DELTA:** `$5` Helius is not the next product spend; the owner must choose retire / freeze notionals / later fund a real `ROUTE_FEASIBILITY` calibration.
- **UNCERTAINTY_REMOVED:** whether unpaid local evidence already falsifies the `$5` plan. It does.
- **CAPABILITY_OR_EVIDENCE:** hash-bound proof packet and exact owner phrases. No new decoder, provider route or dependency.
- **STOP:** zero provider, credential, network, cash, wallet or signer side effects; no TASK-30 or RC001 promotion; no guessed notionals; no silent registry insert.
- **NEXT:** after exact-head CI, stop for the repository merge phrase. After merge the owner still owes one of the three fork phrases. That later phrase is not this PR.

## Owner fork phrases (not executed by this atom)

- `OK T30-A26 RETIRE_RC001_H07_H01_LIQUIDITY_RETENTION`
- `OK T30-A26 FREEZE_NOTIONAL_BUCKET_SET_V1`
- `OK T30-A26 AUTHORIZE_VARIANCE_CALIBRATION_CAPTURE` — currently `INELIGIBLE` until notionals are frozen, a `ROUTE_FEASIBILITY` route exists in the registry with an observed receipt, and ≥4 `POOL_DAY` clusters are in the exact later atom.
