---
task_id: RC002-H11-OLDER-IDL-CLOCK-BODY-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 4a2f4a90bbddf5f0f349590eb76b097a51e8080b
  expected_upstream: origin/main
  expected_upstream_oid: 4a2f4a90bbddf5f0f349590eb76b097a51e8080b
  expected_branch: cursor/rc002-h11-older-idl-clock-body
  dirty_mode: ALLOW_REPORTED
objective: Test whether the three retained H11 clock Program-data bodies consume completely under the pinned TASK-08 layout with trailing quote_mint removed, with no new provider calls.
managed_write_set:
  - docs/tasks/RC002-H11-OLDER-IDL-CLOCK-BODY-OFFLINE-V1.md
  - src/solana_alpha_lab/rc002_h11_older_idl_clock_body.py
  - tests/test_rc002_h11_older_idl_clock_body.py
  - scripts/run_rc002_h11_older_idl_clock_body.py
  - docs/evidence/rc002_h11_older_idl_clock_body/a1_older_idl_clock_body_acceptance_v1.json
  - docs/reports/rc002_h11_older_idl_clock_body/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_older_idl_clock_body/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_older_idl_clock_body/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_older_idl_clock_body/a1_delivery_factory_fit_v1.json
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
      - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_acceptance_v1.json
      - docs/evidence/rc002_h11_older_idl_clock_body/a1_older_idl_clock_body_acceptance_v1.json
      - docs/evidence/rc002_h11_older_idl_clock_body/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_older_idl_clock_body/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_older_idl_clock_body/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-OLDER-IDL-CLOCK-BODY-OFFLINE-V1

Offline layout trial. No new GTA. Pinned TASK-08 decoder bytes stay immutable.
TASK-40/39 historical receipts stay immutable.

## Task Outcome Brief

- **Owner decision:** do not open `getTransaction` while the three retained
  clock bodies can still be a complete older layout (trailing `quote_mint`
  absent).
- **Product outcome:** one terminal that says whether Create, Complete and
  CompletePumpAmmMigration bodies consume with no remainder under candidate
  `DROP_TRAILING_QUOTE_MINT`.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** Complete or Migration body that still fails after
  dropping `quote_mint`, or Create that fails while the other two consume.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with one enum and per-event
  consume/fail.
- **Non-goals:** no provider/network, no Pump-program GTA, no catalog/harness
  rewrite, no pinned decoder mutation, no TASK-40/39 receipt mutation, no
  live PIT, no open IDL search, no exclusive XB/RPC-cut claim from a fail.
- **Evidence budget:** synthetic Borsh plus optional local A4 pages if
  present; no local full gate before PR.
- **Replan trigger:** candidate cannot be expressed without mutating the
  pinned decoder; live pages required but unreadable; second provider/route
  pivot.

## Decision capsule

- `DECISION_DELTA`: payload lengths 112 and 168 include the 8-byte
  discriminator, so Complete body 104 and Migration body 160 equal the
  pinned layouts minus trailing `quote_mint` (32), not minus 24.
- `UNCERTAINTY_REMOVED`: whether those three clock bodies are complete
  under `DROP_TRAILING_QUOTE_MINT`.
- `CAPABILITY_OR_EVIDENCE`: candidate plan plus consume/fail per clock event.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: if consumed, schema-skew not exclusive-cut; if not, bounded
  `getTransaction` needs a new owner OK.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: `getTransaction` now (external gate;
  more expensive than retained bytes).
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_PINNED_PUMP_DECODER_PUBLIC_DECODE_WITH_CANDIDATE_PLAN`

## Definition of Done

1. Candidate layout `DROP_TRAILING_QUOTE_MINT` is the pinned clock field
   list with the `quote_mint` field removed. TradeEvent is unchanged.
   `src/solana_alpha_lab/pump_event_decoder.py` is not in the write set.
2. Synthetic Create/Complete/Migration encoded without `quote_mint` →
   `decode_pump_program_data` on the candidate plan succeeds (no remainder).
3. The same events encoded with the current pinned layout → candidate
   decode fails (`event_payload_trailing_bytes` or `borsh_payload_truncated`).
4. Optional local A4 scan of the exact TASK-40 page set; the three clock
   Program-data payloads (full lengths 195 / 112 / 168) are tried on the
   candidate. All three consume →
   `LAYOUT_CONSUMED_WITHOUT_REMAINDER`. None consume →
   `NO_CANDIDATE_LAYOUT_CONSUMES`. Mixed →
   `MIXED_CLOCK_BODIES_NOT_UNIFORM`. Missing pages →
   `RETAINED_A4_PAGES_NOT_IN_CHECKOUT`.
5. A fail is not an exclusive XB/RPC-cut claim.
6. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=BOUNDED_GETTRANSACTION_IF_CANDIDATE_FAILS`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-40/39 science receipts or the pinned decoder.
