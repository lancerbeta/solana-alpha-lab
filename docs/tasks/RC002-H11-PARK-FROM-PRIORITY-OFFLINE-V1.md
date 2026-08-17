---
task_id: RC002-H11-PARK-FROM-PRIORITY-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: f551066c0350d7b0a58c0bb12d12c7090ebfe9c9
  expected_upstream: origin/main
  expected_upstream_oid: f551066c0350d7b0a58c0bb12d12c7090ebfe9c9
  expected_branch: cursor/rc002-h11-park-from-priority
  dirty_mode: ALLOW_REPORTED
objective: Offline-bind the owner phrase H11 паркуем as a park-from-priority decision for RC002-H11, retaining science, naming exact return triggers and forbidden follow-ons, without provider calls or rewriting TASK-36/37/40 receipts.
managed_write_set:
  - docs/tasks/RC002-H11-PARK-FROM-PRIORITY-OFFLINE-V1.md
  - src/solana_alpha_lab/rc002_h11_park_from_priority.py
  - tests/test_rc002_h11_park_from_priority.py
  - scripts/run_rc002_h11_park_from_priority.py
  - docs/evidence/rc002_h11_park_from_priority/a1_h11_park_from_priority_acceptance_v1.json
  - docs/reports/rc002_h11_park_from_priority/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_park_from_priority/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_park_from_priority/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_park_from_priority/a1_delivery_factory_fit_v1.json
  - registries/decisions_negative_results.yaml
  - tests/test_lifecycle_registries.py
  - tests/test_catalog.py
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
  - HARNESS_REWRITE
  - RC001_FREEZE_MUTATED
  - HOLDOUT_CONSUMED
  - LIVE_PIT_OR_EXECUTION_CLAIM
  - UNBOUNDED_PUMP_PROGRAM_GTA
  - HISTORICAL_RECEIPT_REWRITE
  - PINNED_PUMP_DECODER_MUTATION
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - MERGE_GATE_OR_CONTROL_RUNTIME_CHANGE
  - TASK37_CLOCK_DEFINITION_REWRITE
  - TASK40_RECEIPT_REWRITE
  - TRIAL_LEDGER_REWRITE
  - H11_EFFECT_SCREEN_RERUN
  - MORE_CREATES_OPTION_C
  - COHORT_READY_INFERENCE_FROM_N1
  - PAID_CAPTURE_ON_FALSIFIED_ROUTES
  - H13_OR_H02_TRIAL_STARTED
  - HYPOTHESIS_NEGATIVE_OR_POSITIVE_INFERENCE
  - CREATE_AT_FROM_BLOCKTIME
  - MIGRATION_AT_FROM_BLOCKTIME
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-RC002-H11-PARK-FROM-PRIORITY-001
  l2_roles: [DELIVERY_EVIDENCE, LIFECYCLE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE:
      - registries/decisions_negative_results.yaml
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/a1_cohort_eligibility_after_task40_close_acceptance_v1.json
      - docs/evidence/rc002_h11_park_from_priority/a1_h11_park_from_priority_acceptance_v1.json
      - docs/evidence/rc002_h11_park_from_priority/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_park_from_priority/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_park_from_priority/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-PARK-FROM-PRIORITY-OFFLINE-V1

Owner phrase `H11 паркуем`. Park `HYP-RC002-H11-LIFECYCLE-CLOCK-V1` /
`RESEARCH-CYCLE-RC002-001` from factory priority. Keep science. Name when
to return and when not to. No provider calls. TASK-36/37/40 science
receipts, TASK-37 clock yaml, trial ledger and the pinned decoder stay
immutable. This is not a hypothesis verdict and not canonical DONE.

## Task Outcome Brief

- **Owner decision:** park H11 from priority after the exact phrase
  `H11 паркуем`, because further one-mint clock work and falsified-route
  capture cannot produce product-market fit.
- **Product outcome:** one terminal that H11 is parked from priority,
  science is retained, return requires a new exact contract, and
  forbidden follow-ons are named.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner, any later
  thread that would otherwise resume H11 by recency.
- **Cheapest falsifier:** cohort eligibility is no longer
  `H11_COHORT_NOT_READY_SCREEN_FORBIDDEN`; owner phrase drifted; science
  receipts were rewritten; park is read as hypothesis negative/positive
  or as DONE.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout stating what was parked, why,
  whether to return, the exact return trigger, and the forbidden
  follow-ons.
- **Non-goals:** no provider/network, no paid capture, no effect screen,
  no more Creates, no H13/H02 trial, no clock from transaction wall
  time, no TASK-36/37/40/ledger rewrite, no live PIT, no canonical DONE,
  no `H11_SCREEN_NEGATIVE` or `H11_SCREEN_POSITIVE`.
- **Evidence budget:** git receipts plus public cohort binder; no local
  full gate before PR.
- **Replan trigger:** prerequisite terminals or bytes drifted; owner later
  authorizes a sample-campaign brief under the named return trigger.

## Decision capsule

- `DECISION_DELTA`: H11 leaves the live priority queue. Park is not a
  screen verdict. Return is trigger-gated, not calendar-gated.
- `UNCERTAINTY_REMOVED`: whether the owner chose more H11 capture versus
  park-from-priority for PMF. They chose park.
- `CAPABILITY_OR_EVIDENCE`: fail-closed binder over the public cohort
  eligibility API plus an append-only lifecycle decision. No decode.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: after merge, do not auto-start H13, H02, paid capture, or a
  PMF price/execution atom. Those need a new exact contract.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: paid additional-pool/mint clock
  capture on already-falsified routes, or treating n=1 as screen-ready.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=WRAP_A27_PARK_ADOPT_COHORT_ELIGIBILITY_BINDER`

`OWNER_CAPTURE_PHRASE=H11 паркуем`

## Definition of Done

1. Binder reads the cohort eligibility acceptance for mint
   `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`. Drift is fail-closed.
2. Cohort terminal remains `H11_COHORT_NOT_READY_SCREEN_FORBIDDEN`.
   TASK-36 remains `HISTORICAL_ROUTE_INADEQUATE_REPLAN` / `n=0`.
   TASK-37 capture remains `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`.
3. Owner phrase is exactly `H11 паркуем`. Terminal is
   `H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED`, or
   `H11_PARK_PREREQUISITES_DRIFT` if git receipts drifted.
   `hypothesis_verdict` is `NOT_REFUTED_NOT_SUPPORTED`.
   `priority_disposition` is `PARKED_FROM_PRIORITY`.
4. Return trigger and forbidden follow-ons are bound in acceptance and
   the Russian readout. Calendar elapsed time is not a return trigger.
5. `registries/decisions_negative_results.yaml` records the park
   decision. TASK-36/37/40 science receipts, TASK-37 yaml, trial ledger
   and the pinned decoder are not in the write set.
6. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth and owner operability.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=PMF_PRICE_AND_EXECUTION_TRUTH`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-36/37/40 science receipts, the trial
ledger or the pinned decoder. Park is not `H11_SCREEN_NEGATIVE`.
