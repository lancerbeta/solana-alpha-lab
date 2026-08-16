---
task_id: RC002-H11-COHORT-ELIGIBILITY-AFTER-TASK40-CLOSE-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 17df0e57cc0db29dc34b0f6c68d5fb3b179ea598
  expected_upstream: origin/main
  expected_upstream_oid: 17df0e57cc0db29dc34b0f6c68d5fb3b179ea598
  expected_branch: cursor/rc002-h11-cohort-eligibility-after-task40-close
  dirty_mode: ALLOW_REPORTED
objective: Offline-bind H11 cohort eligibility after the TASK-40 successor close against frozen TASK-37 minima and the TASK-36 screen receipt, showing the cohort is not ready and the effect screen stays forbidden, without provider calls or rewriting TASK-36/37/40 science receipts.
managed_write_set:
  - docs/tasks/RC002-H11-COHORT-ELIGIBILITY-AFTER-TASK40-CLOSE-OFFLINE-V1.md
  - src/solana_alpha_lab/rc002_h11_cohort_eligibility_after_task40_close.py
  - tests/test_rc002_h11_cohort_eligibility_after_task40_close.py
  - scripts/run_rc002_h11_cohort_eligibility_after_task40_close.py
  - docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/a1_cohort_eligibility_after_task40_close_acceptance_v1.json
  - docs/reports/rc002_h11_cohort_eligibility_after_task40_close/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/a1_delivery_factory_fit_v1.json
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
  - CATALOG_OR_HARNESS_REWRITE
  - REGISTRY_REWRITE
  - RC001_FREEZE_MUTATED
  - HOLDOUT_CONSUMED
  - LIVE_PIT_OR_EXECUTION_CLAIM
  - UNBOUNDED_PUMP_PROGRAM_GTA
  - HISTORICAL_RECEIPT_REWRITE
  - PINNED_PUMP_DECODER_MUTATION
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - MERGE_GATE_OR_CONTROL_RUNTIME_CHANGE
  - CREATE_AT_FROM_BLOCKTIME
  - MIGRATION_AT_FROM_BLOCKTIME
  - COMPLETE_EVENT_AS_MIGRATION_AT
  - TASK37_CLOCK_DEFINITION_REWRITE
  - TASK40_RECEIPT_REWRITE
  - H11_EFFECT_SCREEN_RERUN
  - MORE_CREATES_OPTION_C
  - COHORT_READY_INFERENCE_FROM_N1
context_requirements:
  catalog_asset_ids: []
  l2_roles: [DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_task40_close_create_at_gap_migration_at_bound_acceptance_v1.json
      - docs/evidence/task36/a1_h11_lifecycle_clock_screen_runtime_receipt_v1.json
      - docs/evidence/task37/a1_h11_migration_clock_capture_acceptance_v1.json
      - docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/a1_cohort_eligibility_after_task40_close_acceptance_v1.json
      - docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_cohort_eligibility_after_task40_close/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-COHORT-ELIGIBILITY-AFTER-TASK40-CLOSE-OFFLINE-V1

Mint-scoped offline eligibility after TASK-40 successor close. Owner authorized
this write set so closing one mint cannot be read as H11 screen-ready.
No provider calls. TASK-36/37/40 science receipts, TASK-37 clock yaml, trial
ledger and the pinned decoder stay immutable. Effect screen and more Creates
stay out of this atom.

## Task Outcome Brief

- **Owner decision:** bind whether the H11 cohort is eligible after the
  TASK-40 close, against frozen TASK-37 minima and the TASK-36 screen
  receipt.
- **Product outcome:** one terminal that the cohort is not ready and the
  effect screen stays forbidden, or fail-closed if prerequisites drifted.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** TASK-40 close is no longer
  `TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND`; TASK-36 is no longer
  `n=0` / `HISTORICAL_ROUTE_INADEQUATE_REPLAN`; TASK-37 minima or
  `h11_effect_screen: false` drifted; n=1 is treated as cohort-ready.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with
  `H11_COHORT_NOT_READY_SCREEN_FORBIDDEN`, reconstructed 1 pool vs 8/2/2,
  and `create_at` still a typed gap.
- **Non-goals:** no provider/network, no Helius, no decoder fork, no clock
  from `blockTime`, no CompleteEvent as `migration_at`, no TASK-37 yaml
  rewrite, no TASK-36/37/40/ledger rewrite, no live PIT, no effect screen
  rerun, no more Creates, no canonical DONE, no `CLOCKS_RECONSTRUCTED_COHORT_READY`.
- **Evidence budget:** git receipts plus frozen TASK-37 policy load; no
  local full gate before PR.
- **Replan trigger:** prerequisite terminals or bytes drifted; owner later
  authorizes paid/cohort capture or an effect screen.

## Decision capsule

- `DECISION_DELTA`: TASK-40 close is now scored against H11 cohort minima
  instead of being readable as screen-ready.
- `UNCERTAINTY_REMOVED`: whether this mint's successor close satisfies
  TASK-37 8/2/2 or TASK-36 screen eligibility. It does not.
- `CAPABILITY_OR_EVIDENCE`: mint-scoped binder over git TASK-40 close,
  TASK-36 runtime, TASK-37 acceptance, and `load_policy` of frozen TASK-37
  yaml. No decode, no A4, no live pages.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: paid or additional-pool clock capture stays WATCH; effect screen
  stays forbidden until minima and policy allow it.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=KEEP`
- `strongest_rejected_alternative`: rerun H11 effect screen now, or infer
  `CLOCKS_RECONSTRUCTED_COHORT_READY` from n=1.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_TASK40_CLOSE_BINDER_AND_TASK37_LOAD_POLICY`

## Definition of Done

1. Binder reads the TASK-40 close receipt for mint
   `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` and bonding_curve
   `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC`. Drift is fail-closed.
2. Close terminal remains `TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND`.
   `create_at` stays JSON `null` / `MISSING_UNKNOWN`. `migration_at` stays
   bound from the close receipt. Destination pool is one reconstructed
   pool unit, not a cohort.
3. TASK-36 runtime terminal remains `HISTORICAL_ROUTE_INADEQUATE_REPLAN`
   and `cohort.n` remains 0.
4. TASK-37 acceptance terminal remains
   `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`. Frozen policy still has
   `h11_effect_screen: false` and minima 8 pools / 2 days / 2 deployers.
5. Counts below minima or screen policy false →
   `H11_COHORT_NOT_READY_SCREEN_FORBIDDEN`. `effect_screen_eligible` is
   false. Prerequisite drift → `H11_COHORT_ELIGIBILITY_PREREQUISITES_DRIFT`.
6. TASK-36/37/40 science receipts, TASK-37 yaml, trial ledger and the
   pinned decoder are not in the write set. No live-page load.
7. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=PAID_OR_ADDITIONAL_POOL_CLOCK_CAPTURE`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-36/37/40 science receipts, the trial ledger
or the pinned decoder.
