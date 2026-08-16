---
task_id: RC002-H11-CREATE-EARLY-SIX-FIELD-LAYOUT-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 656d0698852661f44c5812919dde9f12f6b78f45
  expected_upstream: origin/main
  expected_upstream_oid: 656d0698852661f44c5812919dde9f12f6b78f45
  expected_branch: cursor/rc002-h11-create-early-six-field-layout
  dirty_mode: ALLOW_REPORTED
objective: Test whether the retained Create 195 Program-data Borsh-consumes under a Create-only six-field candidate through user, knowing the pinned decoder still requires timestamp.
managed_write_set:
  - docs/tasks/RC002-H11-CREATE-EARLY-SIX-FIELD-LAYOUT-OFFLINE-V1.md
  - src/solana_alpha_lab/rc002_h11_create_early_six_field_layout.py
  - tests/test_rc002_h11_create_early_six_field_layout.py
  - scripts/run_rc002_h11_create_early_six_field_layout.py
  - docs/evidence/rc002_h11_create_early_six_field_layout/a1_create_early_six_field_layout_acceptance_v1.json
  - docs/reports/rc002_h11_create_early_six_field_layout/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_create_early_six_field_layout/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_create_early_six_field_layout/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_create_early_six_field_layout/a1_delivery_factory_fit_v1.json
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
      - docs/evidence/rc002_h11_bounded_gettransaction_create/a1_bounded_gettransaction_create_acceptance_v1.json
      - docs/evidence/rc002_h11_create_without_virtual_quote/a1_create_without_virtual_quote_acceptance_v1.json
      - docs/evidence/rc002_h11_older_idl_clock_body/a1_older_idl_clock_body_acceptance_v1.json
      - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_acceptance_v1.json
      - docs/evidence/rc002_h11_create_early_six_field_layout/a1_create_early_six_field_layout_acceptance_v1.json
      - docs/evidence/rc002_h11_create_early_six_field_layout/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_create_early_six_field_layout/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_create_early_six_field_layout/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-CREATE-EARLY-SIX-FIELD-LAYOUT-OFFLINE-V1

Offline Create-only layout trial on the emitted 195-byte Program-data.
No new GTA or getTransaction. Pinned TASK-08 decoder bytes stay immutable.
TASK-40/39 and previous H11 science receipts stay immutable.

## Task Outcome Brief

- **Owner decision:** layout work on Create 195 after public getTransaction
  confirmed the same length (`CREATE_GETTX_SAME_195_STILL_TRUNCATED`).
- **Product outcome:** one terminal that says whether Create 195 Borsh-consumes
  under candidate `DROP_CREATE_FIELDS_AFTER_USER`, including the pinned
  decoder's `timestamp` invariant.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** Create 195 truncated, trailing, other decode fail,
  or `decoded_event_missing_timestamp` after exact Borsh consume;
  Complete/Migration regress under `DROP_TRAILING_QUOTE_MINT`.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with one Create enum plus
  Complete/Migration regression.
- **Non-goals:** no provider/network, no Helius, no Pump-program GTA, no
  catalog/harness/registry rewrite, no pinned decoder mutation, no TASK-40/39
  or previous H11 receipt mutation, no live PIT, no exclusive XB/RPC-cut
  claim, no claim that six fields are the current on-chain IDL.
- **Evidence budget:** synthetic Borsh, git getTransaction fixture, optional
  local A4 pages; no local full gate before PR.
- **Replan trigger:** candidate cannot be expressed without mutating the
  pinned decoder; pinned Create prefix drifted; second provider/route pivot.

## Decision capsule

- `DECISION_DELTA`: quote-field masks still truncated; getTransaction did not
  lengthen Create. After Borsh strings, the 187-byte body has 96 bytes left
  (exactly three pubkeys). Candidate keeps
  `name, symbol, uri, mint, bonding_curve, user`. Pinned
  `decode_pump_program_data` always requires `timestamp`, so exact six-field
  Borsh consume surfaces as `decoded_event_missing_timestamp`, not a
  `DecodedPumpEvent`.
- `UNCERTAINTY_REMOVED`: whether Create 195 is six-field Borsh with no
  remainder, versus truncated/trailing/other fail.
- `CAPABILITY_OR_EVIDENCE`: Create-only candidate plan plus public decode
  fail-codes on the git fixture and optional retained A4.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: Borsh consume without timestamp does not authorize a decoder fork;
  `create_at` from `CreateEvent.timestamp` is unavailable on this body.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: drop only `token_program` and later
  trailing fields (still too long: remaining-after-strings is 96, not 194).
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_PINNED_PUMP_DECODER_PUBLIC_DECODE_WITH_CREATE_ONLY_CANDIDATE_PLAN`

## Definition of Done

1. Candidate layout `DROP_CREATE_FIELDS_AFTER_USER` is the pinned CreateEvent
   field list kept through `user` and dropped after it. CompleteEvent,
   CompletePumpAmmMigrationEvent and TradeEvent stay pinned.
   `src/solana_alpha_lab/pump_event_decoder.py` is not in the write set.
2. Synthetic Create encoded with those six fields →
   `decode_pump_program_data` on the candidate plan raises
   `decoded_event_missing_timestamp` (Borsh consumed; decoder invariant).
3. The same Create encoded with the current pinned layout → candidate decode
   fails (`event_payload_trailing_bytes` or `borsh_payload_truncated`).
4. Git fixture
   `tests/fixtures/rc002_h11/gettransaction_create_same_195_v1.json`
   Create Program-data length 195 is classified. Exact Borsh then timestamp
   invariant → `CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT`.
   Unexpected successful `DecodedPumpEvent` →
   `CREATE_EARLY_LAYOUT_CONSUMED_WITHOUT_REMAINDER`. Trailing →
   `CREATE_EARLY_LAYOUT_TRAILING_BYTES`. Truncated →
   `CREATE_EARLY_LAYOUT_STILL_TRUNCATED`. Other decode fail →
   `CREATE_EARLY_LAYOUT_DECODE_FAILED`. This is not an exclusive-cut claim
   and does not authorize mutating the pinned decoder.
5. Optional local A4 scan of the exact TASK-40 page set. Create 195 is tried
   on the same candidate. Missing pages → `RETAINED_A4_PAGES_NOT_IN_CHECKOUT`.
6. Complete 112 and Migration 168 still consume under previous candidate
   `DROP_TRAILING_QUOTE_MINT` (regression, not a new exclusive-cut claim).
7. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=PINNED_DECODER_FORK_ONLY_AFTER_MULTI_CREATE_CONFIRM`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-40/39 or previous H11 science receipts or
the pinned decoder.
