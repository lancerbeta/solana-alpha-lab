---
task_id: RC002-H11-TASK40-CLOSE-CREATE-AT-GAP-MIGRATION-AT-BOUND-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5800e2c7183df335fcddd10253e1e11bd3aa8089
  expected_upstream: origin/main
  expected_upstream_oid: 5800e2c7183df335fcddd10253e1e11bd3aa8089
  expected_branch: cursor/rc002-h11-task40-close-create-at-gap-migration-at-bound
  dirty_mode: ALLOW_REPORTED
objective: Offline successor-close TASK-40 for this mint by binding create_at MISSING_UNKNOWN plus event-timestamp migration_at from git H11 receipts, without rewriting the TASK-40 capture receipt, registries, or TASK-37 clock yaml, and without provider calls.
managed_write_set:
  - docs/tasks/RC002-H11-TASK40-CLOSE-CREATE-AT-GAP-MIGRATION-AT-BOUND-V1.md
  - src/solana_alpha_lab/rc002_h11_task40_close_create_at_gap_migration_at_bound.py
  - tests/test_rc002_h11_task40_close_create_at_gap_migration_at_bound.py
  - scripts/run_rc002_h11_task40_close_create_at_gap_migration_at_bound.py
  - docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_task40_close_create_at_gap_migration_at_bound_acceptance_v1.json
  - docs/reports/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_delivery_factory_fit_v1.json
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
      - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_acceptance_v1.json
      - docs/evidence/rc002_h11_create_at_missing_unknown/a1_create_at_missing_unknown_acceptance_v1.json
      - docs/evidence/rc002_h11_complete_migration_from_retained_create_history/a1_complete_migration_from_retained_create_history_acceptance_v1.json
      - docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_task40_close_create_at_gap_migration_at_bound_acceptance_v1.json
      - docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_task40_close_create_at_gap_migration_at_bound/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-TASK40-CLOSE-CREATE-AT-GAP-MIGRATION-AT-BOUND-V1

Mint-scoped successor close of TASK-40. Owner authorized this write set after
`migration_at` bound and `create_at = MISSING_UNKNOWN`. No provider calls.
Pinned decoder stays immutable. TASK-37/39/40 science receipts, trial ledger
and previous H11 receipts stay immutable. H11 effect screen and more Creates
(option C) stay out of this atom.

## Task Outcome Brief

- **Owner decision:** close TASK-40 for this mint with the typed `create_at`
  gap and bound event-timestamp `migration_at`; do not rewrite the capture
  receipt.
- **Product outcome:** one successor terminal that the capture campaign is
  closed with those clocks, or fail-closed if prerequisite receipts drifted.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** TASK-40 capture terminal is no longer
  `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`; `create_at` is no longer null;
  `migration_at` is unbound or copied from `CompleteEvent` / `blockTime`;
  prerequisite file bytes changed.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with
  `TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND`, `create_at: null`, and
  bound `migration_at`.
- **Non-goals:** no provider/network, no Helius, no decoder fork, no
  `create_at`/`migration_at` from `blockTime`, no CompleteEvent as
  `migration_at`, no TASK-37 yaml rewrite, no TASK-40/39/ledger rewrite, no
  live PIT, no exclusive XB/RPC-cut, no current-IDL claim, no more Creates,
  no H11 effect screen, no canonical DONE.
- **Evidence budget:** git receipts only; no local full gate before PR.
- **Replan trigger:** prerequisite terminals or bytes drifted; owner later
  authorizes more Creates or an H11 effect screen.

## Decision capsule

- `DECISION_DELTA`: TASK-40 now has a successor close record instead of an
  open INCONCLUSIVE capture plus later H11 clocks with no close.
- `UNCERTAINTY_REMOVED`: whether this mint may close TASK-40 while
  `create_at` stays a typed gap and `migration_at` is already bound.
- `CAPABILITY_OR_EVIDENCE`: mint-scoped binder over git TASK-40, create_at
  and Complete/Migration acceptance receipts. No decode, no A4 rescan.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: H11 effect screen stays WATCH; more Creates stay WATCH; this close
  is not PIT, alpha or canonical DONE.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=KEEP`
- `strongest_rejected_alternative`: rewrite TASK-40 acceptance or trial
  ledger to PASS / rewrite `create_at` from `blockTime` / run effect screen
  now.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_GIT_TASK40_CREATE_AT_AND_MIGRATION_RECEIPTS_NO_DECODE`

## Definition of Done

1. Binder reads TASK-40 named mint
   `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` and bonding_curve
   `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC`. Drift is fail-closed.
2. TASK-40 acceptance terminal remains
   `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT` and `trial_outcome` remains
   `INCONCLUSIVE`. File bytes stay the frozen git hash. Drift →
   `TASK40_CLOSE_PREREQUISITES_DRIFT` or a typed load error.
3. create_at receipt terminal remains `CREATE_AT_MISSING_UNKNOWN`.
   `create_at` is JSON `null`. Status `MISSING_UNKNOWN`.
4. Complete/Migration receipt terminal remains
   `COMPLETE_MIGRATION_IDENTITY_MATCH`. `migration_at` is copied from that
   receipt as `CompletePumpAmmMigrationEvent.timestamp`.
   `CompleteEvent.timestamp` stays `MIGRATION_STARTED`, not `migration_at`.
5. All three match → `TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND`.
   TASK-40/39 science receipts, trial ledger, TASK-37 yaml and the pinned
   decoder are not in the write set.
6. A bound close is not canonical DONE, not live PIT, not an H11 effect
   screen, not option C / more Creates, and not a ledger PASS rewrite.
7. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=H11_EFFECT_SCREEN_WITH_PARTIAL_CREATE_AT_GAP`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-37/39/40 science receipts, the trial ledger
or the pinned decoder.
