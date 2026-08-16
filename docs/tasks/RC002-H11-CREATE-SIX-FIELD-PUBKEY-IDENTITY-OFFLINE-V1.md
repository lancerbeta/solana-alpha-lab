---
task_id: RC002-H11-CREATE-SIX-FIELD-PUBKEY-IDENTITY-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 124d2335096d8ae62d3d5417ce7cf057a52f3afa
  expected_upstream: origin/main
  expected_upstream_oid: 124d2335096d8ae62d3d5417ce7cf057a52f3afa
  expected_branch: cursor/rc002-h11-create-six-field-pubkey-identity
  dirty_mode: ALLOW_REPORTED
objective: Test whether the three pubkeys after name/symbol/uri in retained Create 195 match the TASK-40 named mint and bonding_curve, with no new provider calls and no pinned decoder mutation.
managed_write_set:
  - docs/tasks/RC002-H11-CREATE-SIX-FIELD-PUBKEY-IDENTITY-OFFLINE-V1.md
  - src/solana_alpha_lab/rc002_h11_create_six_field_pubkey_identity.py
  - tests/test_rc002_h11_create_six_field_pubkey_identity.py
  - scripts/run_rc002_h11_create_six_field_pubkey_identity.py
  - docs/evidence/rc002_h11_create_six_field_pubkey_identity/a1_create_six_field_pubkey_identity_acceptance_v1.json
  - docs/reports/rc002_h11_create_six_field_pubkey_identity/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_create_six_field_pubkey_identity/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_create_six_field_pubkey_identity/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_create_six_field_pubkey_identity/a1_delivery_factory_fit_v1.json
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
      - docs/evidence/rc002_h11_create_six_field_pubkey_identity/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_create_six_field_pubkey_identity/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_create_six_field_pubkey_identity/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-CREATE-SIX-FIELD-PUBKEY-IDENTITY-OFFLINE-V1

Offline identity trial on the emitted 195-byte Create Program-data.
No new GTA or getTransaction. Pinned TASK-08 decoder bytes stay immutable.
TASK-40/39 and previous H11 science receipts stay immutable.

## Task Outcome Brief

- **Owner decision:** after six-field Borsh plus timestamp invariant, check
  whether the three trailing pubkeys are the TASK-40 named mint and
  bonding_curve.
- **Product outcome:** one terminal that says match, mismatch, or not a
  six-field body.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** parsed mint/bonding_curve differ from TASK-40
  identity, or the body is not three strings plus three pubkeys with no
  remainder.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with one enum and observed
  mint/bonding_curve/user if parsed.
- **Non-goals:** no provider/network, no Helius, no decoder fork, no
  `create_at` from `blockTime` or event timestamp, no TASK-40/39 or previous
  H11 receipt mutation, no live PIT, no exclusive XB/RPC-cut, no current IDL
  claim.
- **Evidence budget:** git getTransaction fixture, optional local A4; no
  local full gate before PR.
- **Replan trigger:** TASK-40 identity drifted; body cannot be parsed
  without mutating the pinned decoder; second provider/route pivot.

## Decision capsule

- `DECISION_DELTA`: Create 195 Borsh-fits six fields but public decode has
  no timestamp. Identity of the three pubkeys is the next cheapest
  falsifier before any `create_at` source decision.
- `UNCERTAINTY_REMOVED`: whether those pubkeys equal TASK-40 `named_mint`
  and `bonding_curve`.
- `CAPABILITY_OR_EVIDENCE`: bounded string+pubkey reader on Create
  Program-data plus exact identity compare.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: match → `create_at` from `CreateEvent.timestamp` remains absent
  on this mint's Create (owner gap); mismatch → six-field layout is not
  this mint's identity.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: fork pinned decoder to return
  timestamp-less Create (mutates TASK-08 invariant; not needed for identity).
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_TASK40_NAMED_MINT_AND_BONDING_CURVE_PLUS_GIT_CREATE_FIXTURE`

## Definition of Done

1. Reader keeps Create discriminator from the pinned plan, then Borsh
   `string,string,string,pubkey,pubkey,pubkey` with no remainder. It does
   not call `decode_pump_program_data` and does not import `_`-prefixed
   decoder symbols. `src/solana_alpha_lab/pump_event_decoder.py` is not in
   the write set.
2. TASK-40 acceptance still names mint
   `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` and bonding_curve
   `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC`. Drift is fail-closed.
3. Git fixture
   `tests/fixtures/rc002_h11/gettransaction_create_same_195_v1.json`
   Create 195 is classified. Both pubkeys match →
   `CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE`. Parsed but either
   differs → `CREATE_PUBKEYS_MISMATCH`. Not three strings plus three
   pubkeys with no remainder → `CREATE_BODY_NOT_SIX_FIELD`. No Create
   Program-data → `CREATE_BODY_ABSENT`.
4. Optional local A4 scan of the exact TASK-40 page set. Missing pages →
   `RETAINED_A4_PAGES_NOT_IN_CHECKOUT`.
5. A match is not `create_at`, not `DecodedPumpEvent`, not current IDL.
6. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=CREATE_AT_SOURCE_OWNER_GAP_IF_PUBKEYS_MATCH`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-40/39 or previous H11 science receipts or
the pinned decoder.
