---
task_id: RC002-H11-COMPLETE-MIGRATION-FROM-RETAINED-CREATE-HISTORY-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: d6b88812c14fd787e9a7bed756fa5b70a2566b10
  expected_upstream: origin/main
  expected_upstream_oid: d6b88812c14fd787e9a7bed756fa5b70a2566b10
  expected_branch: cursor/rc002-h11-complete-migration-from-retained-create-history
  dirty_mode: ALLOW_REPORTED
objective: Offline-scan the git-retained Create 195 getTransaction history for CompleteEvent and CompletePumpAmmMigrationEvent, bind TASK-40 mint/curve identity if those bodies decode under the already-consumed DROP_TRAILING_QUOTE_MINT candidate, and leave migration_at unbound when they are absent from that Create history, without provider calls or pinned-decoder mutation.
managed_write_set:
  - docs/tasks/RC002-H11-COMPLETE-MIGRATION-FROM-RETAINED-CREATE-HISTORY-OFFLINE-V1.md
  - src/solana_alpha_lab/rc002_h11_complete_migration_from_retained_create_history.py
  - tests/test_rc002_h11_complete_migration_from_retained_create_history.py
  - scripts/run_rc002_h11_complete_migration_from_retained_create_history.py
  - docs/evidence/rc002_h11_complete_migration_from_retained_create_history/a1_complete_migration_from_retained_create_history_acceptance_v1.json
  - docs/reports/rc002_h11_complete_migration_from_retained_create_history/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_complete_migration_from_retained_create_history/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_complete_migration_from_retained_create_history/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_complete_migration_from_retained_create_history/a1_delivery_factory_fit_v1.json
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
      - docs/evidence/rc002_h11_older_idl_clock_body/a1_older_idl_clock_body_acceptance_v1.json
      - docs/evidence/rc002_h11_complete_migration_from_retained_create_history/a1_complete_migration_from_retained_create_history_acceptance_v1.json
      - docs/evidence/rc002_h11_complete_migration_from_retained_create_history/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_complete_migration_from_retained_create_history/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_complete_migration_from_retained_create_history/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-COMPLETE-MIGRATION-FROM-RETAINED-CREATE-HISTORY-OFFLINE-V1

Mint-scoped offline scan of the git Create 195 getTransaction for Complete and
CompletePumpAmmMigration. Owner authorized this write set after
`create_at = MISSING_UNKNOWN`. No provider calls. Pinned decoder stays
immutable. TASK-37/39/40 and previous H11 science receipts stay immutable.
TASK-37 frozen `migration_at := CompletePumpAmmMigrationEvent.timestamp` is
not rewritten. `CompleteEvent.timestamp` stays `MIGRATION_STARTED`, not
`migration_at`.

## Task Outcome Brief

- **Owner decision:** scan Complete / CompletePumpAmmMigration in the retained
  Create 195 git history; bind identity and `migration_at` only from those
  event bodies; do not use `blockTime`.
- **Product outcome:** one terminal that says whether those events are in the
  Create getTransaction (and optional local A4 pages), or fail-closed if
  prerequisite receipts drifted.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** Complete/Migration discriminators appear in the
  Create getTransaction; decoded mint/curve mismatch TASK-40; older-IDL
  receipt no longer shows A4 Complete+Migration consumed; a numeric clock is
  copied from fixture `blockTime`.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with the fixture terminal and
  `migration_at: null` unless identity-matched Migration timestamp is bound.
- **Non-goals:** no provider/network, no Helius, no decoder fork, no
  `create_at`/`migration_at` from `blockTime`, no CompleteEvent as
  `migration_at`, no TASK-37 yaml rewrite, no TASK-40/39 or previous H11
  receipt mutation, no live PIT, no exclusive XB/RPC-cut, no current-IDL
  claim, no more Creates.
- **Evidence budget:** git receipts plus optional local A4; no local full
  gate before PR.
- **Replan trigger:** prerequisite terminals drifted; Create getTransaction
  unexpectedly contains Complete/Migration; owner later authorizes A4 body
  extraction or a bounded getTransaction of those signatures.

## Decision capsule

- `DECISION_DELTA`: remaining H11 clocks are now tested against the same git
  Create history that bound `create_at = MISSING_UNKNOWN`, instead of another
  layout probe on Create 195.
- `UNCERTAINTY_REMOVED`: whether Create 195 getTransaction also carries
  Complete / CompletePumpAmmMigration for this mint.
- `CAPABILITY_OR_EVIDENCE`: mint-scoped binder over git Create fixture,
  older-IDL A4 consumption receipt, and optional local A4 decode under
  `DROP_TRAILING_QUOTE_MINT`.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: `create_at` stays `MISSING_UNKNOWN`; this mint now has event-timestamp
  `migration_at` from A4, not from the Create getTransaction. TASK-40 still
  not closed; more Creates stay WATCH; H11 effect screen is not this atom.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=KEEP`
- `strongest_rejected_alternative`: copy fixture `blockTime` or
  `CompleteEvent.timestamp` as `migration_at` (violates TASK-37).
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_DROP_TRAILING_QUOTE_MINT_AND_CREATE_GETTX_FIXTURE`

## Definition of Done

1. Binder reads TASK-40 named mint
   `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` and bonding_curve
   `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC`. Drift is fail-closed.
2. `create_at` receipt terminal remains `CREATE_AT_MISSING_UNKNOWN`. Older-IDL
   A4 receipt still records CompleteEvent and CompletePumpAmmMigrationEvent
   consumed under `DROP_TRAILING_QUOTE_MINT` with payload lengths 112 and 168.
   Drift → `COMPLETE_MIGRATION_PREREQUISITES_DRIFT`.
3. Git getTransaction Create 195 is classified under the in-memory
   `DROP_TRAILING_QUOTE_MINT` candidate. No Complete/Migration discriminator →
   `COMPLETE_MIGRATION_ABSENT_FROM_CREATE_GETTX`. `migration_at` is JSON
   `null`. Fixture `blockTime` is not copied. `CompleteEvent.timestamp` is
   never stored as `migration_at`.
4. Optional local A4 scan of the exact TASK-40 page set. Consumed
   Complete/Migration bodies whose mint and bonding_curve match TASK-40 →
   `COMPLETE_MIGRATION_IDENTITY_MATCH` and `migration_at` from
   `CompletePumpAmmMigrationEvent.timestamp`. Matching Complete without
   Migration → `COMPLETE_MIGRATION_STARTED_NOT_MIGRATED` and `migration_at`
   stays JSON `null`. Mismatch →
   `COMPLETE_MIGRATION_IDENTITY_MISMATCH`. Decode fail without consume →
   `COMPLETE_MIGRATION_LAYOUT_FAIL`. Missing A4 is an explicit checkout gap,
   not a clock.
5. `src/solana_alpha_lab/pump_event_decoder.py`, TASK-37/39/40 configs and
   science receipts are not in the write set. Decode may run against the
   in-memory older-IDL candidate only. No pinned-file mutation.
6. A bound gap is not current IDL, not TASK-40 close, not a cohort rewrite of
   TASK-37 `migration_at := CompletePumpAmmMigrationEvent.timestamp`.
7. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=TASK40_CLOSE_OR_H11_EFFECT_SCREEN_AFTER_MINT_CLOCKS`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-37/39/40 or previous H11 science receipts or
the pinned decoder.
