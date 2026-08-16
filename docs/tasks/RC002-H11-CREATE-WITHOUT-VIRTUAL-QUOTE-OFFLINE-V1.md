---
task_id: RC002-H11-CREATE-WITHOUT-VIRTUAL-QUOTE-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: c35a69f6473f10973cb5a94f8c32dc21e8809d9b
  expected_upstream: origin/main
  expected_upstream_oid: c35a69f6473f10973cb5a94f8c32dc21e8809d9b
  expected_branch: cursor/rc002-h11-create-without-virtual-quote
  dirty_mode: ALLOW_REPORTED
objective: Test whether the retained Create 195 Program-data body consumes completely after dropping both quote_mint and virtual_quote_reserves from CreateEvent only, with no new provider calls.
managed_write_set:
  - docs/tasks/RC002-H11-CREATE-WITHOUT-VIRTUAL-QUOTE-OFFLINE-V1.md
  - src/solana_alpha_lab/rc002_h11_create_without_virtual_quote.py
  - tests/test_rc002_h11_create_without_virtual_quote.py
  - scripts/run_rc002_h11_create_without_virtual_quote.py
  - docs/evidence/rc002_h11_create_without_virtual_quote/a1_create_without_virtual_quote_acceptance_v1.json
  - docs/reports/rc002_h11_create_without_virtual_quote/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_create_without_virtual_quote/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_create_without_virtual_quote/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_create_without_virtual_quote/a1_delivery_factory_fit_v1.json
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
      - docs/evidence/rc002_h11_truncation_vs_absence/a1_truncation_vs_absence_acceptance_v1.json
      - docs/evidence/rc002_h11_older_idl_clock_body/a1_older_idl_clock_body_acceptance_v1.json
      - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_acceptance_v1.json
      - docs/evidence/rc002_h11_create_without_virtual_quote/a1_create_without_virtual_quote_acceptance_v1.json
      - docs/evidence/rc002_h11_create_without_virtual_quote/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_create_without_virtual_quote/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_create_without_virtual_quote/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-CREATE-WITHOUT-VIRTUAL-QUOTE-OFFLINE-V1

Offline Create-only layout trial. No new GTA. Pinned TASK-08 decoder bytes stay
immutable. TASK-40/39 historical receipts stay immutable. Previous atom
`RC002-H11-OLDER-IDL-CLOCK-BODY-OFFLINE-V1` science receipts stay immutable.

## Task Outcome Brief

- **Owner decision:** do not open `getTransaction` while the retained Create
  195 body can still be a complete older Create layout (trailing `quote_mint`
  and `virtual_quote_reserves` both absent).
- **Product outcome:** one terminal that says whether Create 195 consumes with
  no remainder under candidate `DROP_QUOTE_MINT_AND_VIRTUAL_QUOTE_RESERVES`.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** Create 195 still fails after dropping both quote
  fields, or Complete/Migration regress under `DROP_TRAILING_QUOTE_MINT`.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with one Create enum plus
  Complete/Migration regression.
- **Non-goals:** no provider/network, no Pump-program GTA, no catalog/harness
  rewrite, no pinned decoder mutation, no TASK-40/39 receipt mutation, no
  live PIT, no extra field drop on Complete/Migration, no exclusive XB/RPC-cut
  claim from a consume or a fail.
- **Evidence budget:** synthetic Borsh plus optional local A4 pages if
  present; no local full gate before PR.
- **Replan trigger:** candidate cannot be expressed without mutating the
  pinned decoder; live pages required but unreadable; second provider/route
  pivot.

## Decision capsule

- `DECISION_DELTA`: previous candidate dropped only `quote_mint`; live Create
  195 still failed `borsh_payload_truncated`. Next cheapest offline mask is
  Create-only drop of both trailing quote fields.
- `UNCERTAINTY_REMOVED`: whether Create 195 consumes under
  `DROP_QUOTE_MINT_AND_VIRTUAL_QUOTE_RESERVES`.
- `CAPABILITY_OR_EVIDENCE`: Create-only candidate plan plus consume/fail.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: if Create consumes, schema-skew still not exclusive-cut; if not,
  bounded `getTransaction` needs a new owner OK.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: `getTransaction` now (external gate;
  more expensive than retained bytes).
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_PINNED_PUMP_DECODER_PUBLIC_DECODE_WITH_CREATE_ONLY_CANDIDATE_PLAN`

## Definition of Done

1. Candidate layout `DROP_QUOTE_MINT_AND_VIRTUAL_QUOTE_RESERVES` is the pinned
   CreateEvent field list with `quote_mint` and `virtual_quote_reserves`
   removed. CompleteEvent, CompletePumpAmmMigrationEvent and TradeEvent stay
   pinned. `src/solana_alpha_lab/pump_event_decoder.py` is not in the write set.
2. Synthetic Create encoded without those two fields →
   `decode_pump_program_data` on the candidate plan succeeds (no remainder).
3. The same Create encoded with the current pinned layout → candidate decode
   fails (`event_payload_trailing_bytes` or `borsh_payload_truncated`).
4. Optional local A4 scan of the exact TASK-40 page set. Create Program-data
   full length 195 is tried on the candidate. Consume with no remainder →
   `CREATE_CONSUMED_WITHOUT_REMAINDER`. Still truncated/trailing →
   `CREATE_STILL_TRUNCATED_NEED_GETTRANSACTION`. Missing pages →
   `RETAINED_A4_PAGES_NOT_IN_CHECKOUT`. A consume is compatible with exact
   truncation of a longer layout; it is not an exclusive-cut claim.
5. Complete 112 and Migration 168 still consume under previous candidate
   `DROP_TRAILING_QUOTE_MINT` (regression, not a new exclusive-cut claim).
6. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=BOUNDED_GETTRANSACTION_IF_CREATE_STILL_TRUNCATED`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-40/39 science receipts, the previous older-IDL
receipts, or the pinned decoder.
