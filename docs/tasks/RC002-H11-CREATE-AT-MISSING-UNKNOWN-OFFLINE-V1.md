---
task_id: RC002-H11-CREATE-AT-MISSING-UNKNOWN-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 38df23922b31733bdaa5e4c425b70cfb15757c63
  expected_upstream: origin/main
  expected_upstream_oid: 38df23922b31733bdaa5e4c425b70cfb15757c63
  expected_branch: cursor/rc002-h11-create-at-missing-unknown
  dirty_mode: ALLOW_REPORTED
objective: Bind owner decision A that this TASK-40 mint's create_at is MISSING_UNKNOWN because Create 195 is identity-matched and has no CreateEvent.timestamp, without filling create_at from blockTime or mutating the pinned decoder.
managed_write_set:
  - docs/tasks/RC002-H11-CREATE-AT-MISSING-UNKNOWN-OFFLINE-V1.md
  - src/solana_alpha_lab/rc002_h11_create_at_missing_unknown.py
  - tests/test_rc002_h11_create_at_missing_unknown.py
  - scripts/run_rc002_h11_create_at_missing_unknown.py
  - docs/evidence/rc002_h11_create_at_missing_unknown/a1_create_at_missing_unknown_acceptance_v1.json
  - docs/reports/rc002_h11_create_at_missing_unknown/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_create_at_missing_unknown/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_create_at_missing_unknown/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_create_at_missing_unknown/a1_delivery_factory_fit_v1.json
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
      - docs/evidence/rc002_h11_create_early_six_field_layout/a1_create_early_six_field_layout_acceptance_v1.json
      - docs/evidence/rc002_h11_create_six_field_pubkey_identity/a1_create_six_field_pubkey_identity_acceptance_v1.json
      - docs/evidence/rc002_h11_create_at_missing_unknown/a1_create_at_missing_unknown_acceptance_v1.json
      - docs/evidence/rc002_h11_create_at_missing_unknown/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_create_at_missing_unknown/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_create_at_missing_unknown/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-CREATE-AT-MISSING-UNKNOWN-OFFLINE-V1

Mint-scoped typed gap for `create_at`. Owner chose A after Create pubkey identity
matched TASK-40 and the six-field body had no timestamp.
No provider calls. Pinned decoder stays immutable. TASK-37/39/40 and previous
H11 science receipts stay immutable. TASK-37 frozen definition
`create_at := CreateEvent.timestamp` is not rewritten.

## Task Outcome Brief

- **Owner decision:** A. For this mint, `create_at = MISSING_UNKNOWN`.
- **Product outcome:** one terminal that binds the gap, or fail-closed if
  prerequisite receipts drifted.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** identity is no longer MATCH, layout is no longer
  timestamp-invariant, TASK-40 mint/curve drifted, or a numeric `create_at`
  / fixture `blockTime` is bound as the clock.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with `CREATE_AT_MISSING_UNKNOWN`
  and `create_at: null`.
- **Non-goals:** no provider/network, no Helius, no decoder fork, no
  `create_at` from `blockTime`, no TASK-37 yaml rewrite, no TASK-40/39 or
  previous H11 receipt mutation, no live PIT, no exclusive XB/RPC-cut, no
  current-IDL claim, no cohort-wide clock policy change.
- **Evidence budget:** git receipts only; no local full gate before PR.
- **Replan trigger:** prerequisite terminals drifted; owner later chooses
  another time label or more Creates (option C).

## Decision capsule

- `DECISION_DELTA`: identity MATCH plus missing timestamp is now an explicit
  typed gap, not an implied next layout probe.
- `UNCERTAINTY_REMOVED`: whether this mint may pretend to have
  `create_at` from CreateEvent.timestamp or blockTime. It may not.
- `CAPABILITY_OR_EVIDENCE`: mint-scoped binder over git identity + layout
  receipts.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: Complete/Migration clocks for this mint remain available under
  prior candidates; TASK-40 still not closed; more Creates stay WATCH.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: bind fixture `blockTime` as `create_at`
  (violates TASK-37 forbidden block-time heuristic spirit and owner A).
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_GIT_IDENTITY_AND_LAYOUT_RECEIPTS_NO_NEW_DECODE`

## Definition of Done

1. Binder reads TASK-40 named mint
   `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` and bonding_curve
   `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC`. Drift is fail-closed.
2. Identity receipt terminal remains
   `CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE`. Layout receipt
   terminal remains
   `CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT`. Drift →
   `CREATE_AT_PREREQUISITES_DRIFT`.
3. Both git getTransaction terminals MATCH/invariant →
   `CREATE_AT_MISSING_UNKNOWN`. `create_at` is JSON `null`.
   `create_at_status` is `MISSING_UNKNOWN`. Fixture `blockTime` is not
   copied. No i64 clock is emitted.
4. `src/solana_alpha_lab/pump_event_decoder.py`, TASK-37/39/40 configs and
   science receipts are not in the write set. No `decode_pump_program_data`.
5. A bound gap is not `DecodedPumpEvent`, not current IDL, not TASK-40 close,
   not a cohort rewrite of TASK-37 `create_at := CreateEvent.timestamp`.
6. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=COMPLETE_MIGRATION_CLOCKS_FOR_THIS_MINT_OR_MORE_CREATES`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-37/39/40 or previous H11 science receipts or
the pinned decoder.
