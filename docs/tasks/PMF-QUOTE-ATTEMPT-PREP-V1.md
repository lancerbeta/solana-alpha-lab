---
task_id: PMF-QUOTE-ATTEMPT-PREP-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 9e00d9543224d34a2aa935196694f5afd614f37c
  expected_upstream: origin/main
  expected_upstream_oid: 9e00d9543224d34a2aa935196694f5afd614f37c
  expected_branch: cursor/pmf-quote-attempt-prep
  dirty_mode: ALLOW_REPORTED
objective: Freeze an offline TASK-26 ATTEMPT contract over the merged owner-fork packet so a later keyed /order with taker pubkey is named, while this atom supplies no wallet, no provider call, no /execute and no seed.
managed_write_set:
  - docs/tasks/PMF-QUOTE-ATTEMPT-PREP-V1.md
  - configs/pmf_quote_attempt_prep_v1.yaml
  - src/solana_alpha_lab/pmf_quote_attempt_prep.py
  - tests/test_pmf_quote_attempt_prep.py
  - scripts/run_pmf_quote_attempt_prep.py
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_attempt_prep_runtime_receipt_v1.json
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_attempt_prep_acceptance_v1.json
  - docs/reports/pmf_quote_slice/a1_attempt_prep_owner_readout_v1.md
  - docs/evidence/pmf_quote_slice/a1_attempt_prep_delivery_completion_evidence_v1.json
  - docs/evidence/pmf_quote_slice/a1_attempt_prep_delivery_independent_review_v1.json
  - docs/evidence/pmf_quote_slice/a1_attempt_prep_delivery_factory_fit_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
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
  - AUTHORITY_WIDENING
  - PROVIDER_OR_NETWORK_CALL
  - CREDENTIAL_OR_API_KEY_READ
  - JUPITER_EXECUTE_OR_BUILD
  - TAKER_OR_SIGNER_SUPPLIED
  - SEED_OR_PRIVATE_KEY_IN_GIT
  - TRANSACTION_BYTES_IN_GIT
  - FROZEN_QUOTE_USED_AS_ATTEMPT_QUOTE
  - PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE
  - MISSING_FEE_TREATED_AS_ZERO
  - NETRETURN_OR_CASHFLOW_CLAIM
  - LOCAL_RAW_USED_AS_GIT_TRUTH
  - H11_UNPARK_OR_SAMPLE_CAMPAIGN
  - H13_OR_H02_TRIAL_STARTED
  - RC001_FREEZE_MUTATED
  - V6_OR_V7_REGISTRY_REWRITE
  - TRIAL_LEDGER_REWRITE
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - MERGE_GATE_OR_CONTROL_RUNTIME_CHANGE
  - EXECUTE_PHRASE_OFFERED_AS_AUTHORIZED
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-PMF-QUOTE-OWNER-FORK-ACCEPTANCE-001
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/pmf_quote_attempt_prep_v1.yaml
      - configs/pmf_quote_owner_fork_v1.yaml
      - docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_owner_fork_runtime_receipt_v1.json
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_owner_fork_acceptance_v1.json
      - docs/evidence/pmf_quote_slice/a1_attempt_prep_delivery_completion_evidence_v1.json
      - docs/evidence/pmf_quote_slice/a1_attempt_prep_delivery_independent_review_v1.json
      - docs/evidence/pmf_quote_slice/a1_attempt_prep_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PMF-QUOTE-ATTEMPT-PREP-V1

Owner phrase `OK PMF-QUOTE-ATTEMPT-PREP: offline attempt contract only, no wallet, no execute, no provider`.

WRAP TASK-26 `ATTEMPT` vocabulary and the official Jupiter Swap V2 `/order` then `/execute` split over the merged owner-fork packet. This atom does not call a provider, does not read a credential, does not supply a taker, and does not execute.

## Task Outcome Brief

- **Owner decision:** freeze what a later keyed attempt is allowed to do tonight, without doing it now.
- **Product outcome:** one offline attempt-prep packet — status `NOT_ATTEMPTED`, frozen quote is not the attempt quote, execute stays forbidden.
- **Named consumers:** goal owner returning with a taker pubkey for a later keyed `/order`.
- **Cheapest falsifier:** packet issues an attempt_id; supplies a taker; treats the morning quote as the attempt quote; offers `/execute`; a provider GET runs.
- **Terminal outcome:** `QUOTE_ATTEMPT_PREP_BOUND_NOT_ATTEMPTED` or `QUOTE_ATTEMPT_PREP_PREREQUISITES_DRIFT`. Not alpha, PIT, fill, cashflow or canonical DONE.
- **User-visible result:** Russian readout naming the later unpaid attempt phrase and the hard no's (execute, seed, tx-in-git).
- **Non-goals:** no provider/network, no credential, no wallet/taker/signer now, no `/execute`/`/build`, no H11 unpark, no H13/H02, no fee promotion from local raw, no canonical DONE.
- **Evidence budget:** git receipts only; zero provider requests; no local full gate before PR.
- **Replan trigger:** owner-fork hash drifts; owner authorizes execute instead of `/order` with taker; a taker pubkey is pasted into this packet.

## Decision capsule

- `DECISION_DELTA`: evening work is a named ATTEMPT contract, not a second quote and not execute.
- `UNCERTAINTY_REMOVED`: what the later atom may call (`GET /order` with taker pubkey), what it must not (`/execute`, seed in git, reuse stale quote).
- `CAPABILITY_OR_EVIDENCE`: one hash-bound prep over the owner-fork packet and TASK-26 ATTEMPT layer.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: do not auto-start the keyed `/order`, execute, H13, H02 or H11.
- `SPEC_ROUTE=PRD_LITE`
- `ROADMAP_VERDICT=KEEP`
- `strongest_rejected_alternative`: another `/order` without taker, Solana `simulateTransaction` as a substitute Fillable, or `/execute` tonight.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=WRAP_TASK26_ATTEMPT_AND_JUPITER_ORDER_EXECUTE_SPLIT`

`OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-ATTEMPT-PREP: offline attempt contract only, no wallet, no execute, no provider`

## Frozen later-atom rules (not executed here)

- Later call: keyed Jupiter Swap V2 `GET /order` with the same mint/notional and a taker **pubkey only**.
- Frozen morning quote is stale. It is a prerequisite identity, not the attempt quote.
- `/execute` and `/build` stay forbidden. Transaction bytes stay A4 outside git.
- Seed / private key / signer material never enter git or chat receipts.
- Credential `JUPITER_API_KEY` is named for the later atom and is not read here.
- TASK-26: later atom issues `attempt_id` / `intent_id`; this packet keeps them `RESERVED_NOT_ISSUED` and terminal `NOT_ATTEMPTED`.

## Unpaid owner phrase (not executed by this atom)

- `OK PMF-QUOTE-ATTEMPT: keyed /order with taker pubkey only, no /execute, no seed in git`

## Definition of Done

1. Packet reads only the frozen owner-fork receipts plus TASK-26 vocabulary; no network, credential, `/execute`, `/build`, taker or seed.
2. Owner-fork terminal stays `QUOTE_OWNER_FORK_MISSING_FACTS_NAMED`; identity matches A24 mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` / notional `10000000`.
3. Attempt status is `NOT_ATTEMPTED`; frozen quote is not the attempt quote; execute is ineligible.
4. Russian readout names the later unpaid attempt phrase and the hard no's.
5. v6/v7 registries, RC001 freeze, H11 park and the trial ledger are not in the write set.
