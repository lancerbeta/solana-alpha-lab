---
task_id: RC002-H11-TRUNCATION-VS-ABSENCE-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-16'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: edfe3a9c51de106277793b8e5ca8e2ee820f1343
  expected_upstream: origin/main
  expected_upstream_oid: edfe3a9c51de106277793b8e5ca8e2ee820f1343
  expected_branch: cursor/rc002-h11-truncation-vs-absence
  dirty_mode: ALLOW_REPORTED
objective: Classify whether TASK-40/39 borsh_payload_truncated hid H11 clock events or only non-clock TradeEvent payloads, using retained bytes and synthetic logs, with no new provider calls.
managed_write_set:
  - docs/tasks/RC002-H11-TRUNCATION-VS-ABSENCE-OFFLINE-V1.md
  - src/solana_alpha_lab/rc002_h11_truncation_vs_absence.py
  - tests/test_rc002_h11_truncation_vs_absence.py
  - scripts/run_rc002_h11_truncation_vs_absence.py
  - docs/evidence/rc002_h11_truncation_vs_absence/a1_truncation_vs_absence_acceptance_v1.json
  - docs/reports/rc002_h11_truncation_vs_absence/a1_owner_readout_v1.md
  - docs/evidence/rc002_h11_truncation_vs_absence/a1_delivery_completion_evidence_v1.json
  - docs/evidence/rc002_h11_truncation_vs_absence/a1_delivery_independent_review_v1.json
  - docs/evidence/rc002_h11_truncation_vs_absence/a1_delivery_factory_fit_v1.json
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
      - docs/evidence/task40/a1_h11_bonding_curve_pda_gta_acceptance_v1.json
      - docs/evidence/rc002_h11_truncation_vs_absence/a1_truncation_vs_absence_acceptance_v1.json
      - docs/evidence/rc002_h11_truncation_vs_absence/a1_delivery_completion_evidence_v1.json
      - docs/evidence/rc002_h11_truncation_vs_absence/a1_delivery_independent_review_v1.json
      - docs/evidence/rc002_h11_truncation_vs_absence/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RC002-H11-TRUNCATION-VS-ABSENCE-OFFLINE-V1

Offline discriminator. No new GTA. TASK-40/39 historical receipts stay immutable.

## Task Outcome Brief

- **Owner decision:** do not treat `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`
  as closed while `borsh_payload_truncated` can hide Create/Complete or abort
  the rest of a transaction.
- **Product outcome:** one terminal that says whether pinned clock
  discriminators are present but their body is not consumed by the pinned
  layout, skipped after a non-clock truncate, or truly absent from
  addressed Pump `Program data` lines.
- **Named consumers:** `RC002-H11-LIFECYCLE-CLOCK`, goal owner.
- **Cheapest falsifier:** a truncated Create discriminator classified as
  non-clock, or a Create after a truncated Trade classified as absent.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout with one enum and the truncation
  split by event name.
- **Non-goals:** no provider/network, no Pump-program GTA, no catalog/harness
  rewrite, no TASK-40/39 receipt mutation, no live PIT, no exclusive-write
  wrap of TASK-40.
- **Evidence budget:** offline repository plus optional local A4 pages if
  present; no local full gate before PR.
- **Replan trigger:** classifier cannot name the truncated event; live pages
  required but unreadable; second provider/route pivot.

## Decision capsule

- `DECISION_DELTA`: classify truncated Pump events by matched discriminator
  and keep scanning the same transaction after a non-clock truncate.
- `UNCERTAINTY_REMOVED`: whether 1245 `borsh_payload_truncated` counts can
  still hide H11 clocks.
- `CAPABILITY_OR_EVIDENCE`: per-event truncation histogram plus terminal enum.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: act only on the terminal; no new GTA in this atom.
- `SPEC_ROUTE=NONE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: wrap TASK-40 with exclusive writes
  (does not change the clock verdict).
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_PINNED_PUMP_DECODER_AND_EXISTING_LOG_ATTRIBUTION`

## Definition of Done

1. Create/Complete/Migration discriminator whose pinned body does not
   decode (truncate or other Borsh error) →
   `CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT`. This uncloses TASK-40 wrong-address;
   it is not an exclusive XB/RPC-cut claim.
2. Create decoded after truncated Trade in the same tx →
   `CLOCK_EVENTS_PRESENT_AFTER_NON_CLOCK_TRUNCATION`.
3. Truncated Trade only, no clock discriminator →
   `CLOCK_EVENTS_ABSENT_TRUNCATION_IS_NON_CLOCK`.
4. No clock discriminator and no pinned truncate →
   `CLOCK_EVENTS_ABSENT_NO_CLOCK_DISCRIMINATOR`.
5. Optional local A4 scan if `local/task40_rc002_h11_bonding_curve_pda_gta`
   exists with the exact TASK-40 page set, sizes and sha256; otherwise
   explicit `RETAINED_A4_PAGES_NOT_IN_CHECKOUT`.
6. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth only.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
Passing tests, CI or merge is not semantic DONE, alpha or cashflow.
This atom does not rewrite TASK-40/39 science receipts.
