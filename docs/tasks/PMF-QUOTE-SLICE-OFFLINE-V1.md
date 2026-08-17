---
task_id: PMF-QUOTE-SLICE-OFFLINE-V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 72f6e5a7515a7bfd0cf1533f398d5e4db79ab332
  expected_upstream: origin/main
  expected_upstream_oid: 72f6e5a7515a7bfd0cf1533f398d5e4db79ab332
  expected_branch: cursor/pmf-quote-slice-offline
  dirty_mode: ALLOW_REPORTED
objective: Offline-bind the PMF quote-slice after owner start of OK PMF-QUOTE-SLICE, adopting Jupiter Swap V2 /order without taker as the quote-only surface, naming one Git identity and one notional, without provider calls, credentials, execute, H11 unpark or RC001 trials.
managed_write_set:
  - docs/tasks/PMF-QUOTE-SLICE-OFFLINE-V1.md
  - configs/pmf_quote_slice_v1.yaml
  - src/solana_alpha_lab/pmf_quote_slice.py
  - tests/test_pmf_quote_slice.py
  - scripts/run_pmf_quote_slice.py
  - docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_acceptance_v1.json
  - docs/reports/pmf_quote_slice/a1_owner_readout_v1.md
  - docs/evidence/pmf_quote_slice/a1_delivery_completion_evidence_v1.json
  - docs/evidence/pmf_quote_slice/a1_delivery_independent_review_v1.json
  - docs/evidence/pmf_quote_slice/a1_delivery_factory_fit_v1.json
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
  - CREDENTIAL_OR_API_KEY_READ
  - JUPITER_EXECUTE_OR_BUILD
  - TAKER_OR_SIGNER_SUPPLIED
  - FAKE_OBSERVED_REGISTRY_ROW
  - RC001_FREEZE_MUTATED
  - HOLDOUT_CONSUMED
  - LIVE_PIT_OR_EXECUTION_CLAIM
  - H11_UNPARK_OR_SAMPLE_CAMPAIGN
  - H13_OR_H02_TRIAL_STARTED
  - NOTIONAL_BUCKET_SET_V1_FROZEN
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - MERGE_GATE_OR_CONTROL_RUNTIME_CHANGE
  - TASK36_37_40_RECEIPT_REWRITE
  - TRIAL_LEDGER_REWRITE
  - PINNED_PUMP_DECODER_MUTATION
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-PMF-QUOTE-SLICE-001
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/provider_route_capability_registry_v6.yaml
      - configs/task30_a24_raw_to_pit_admissibility_owner_panel_v1.yaml
      - docs/evidence/task30/a26_h07_h01_owner_fork_packet_acceptance_v1.json
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_acceptance_v1.json
      - docs/evidence/pmf_quote_slice/a1_delivery_completion_evidence_v1.json
      - docs/evidence/pmf_quote_slice/a1_delivery_independent_review_v1.json
      - docs/evidence/pmf_quote_slice/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PMF-QUOTE-SLICE-OFFLINE-V1

Owner phrase `OK PMF-QUOTE-SLICE`. Rebase the live product object from
the next RC001 family onto one quote-only PMF slice. Adopt official
Jupiter Swap V2 `GET /swap/v2/order` **without** `taker` as the quote
surface. Do not wrap the TASK-10 Metis logger. Do not call the network.
Do not read a portal key. Do not execute. Live registry v6 stays
`REGISTRY_GAP` until a later observed one-shot. This is not alpha, PIT,
cashflow or canonical DONE.

## Task Outcome Brief

- **Owner decision:** start the PMF quote-slice after the exact phrase
  `OK PMF-QUOTE-SLICE`, because parked H11/H07 families do not produce
  a visible price, a touchable route or money after costs.
- **Product outcome:** one terminal that the slice is bound — named
  identity, one notional, ADOPT V2 `/order` without taker, live registry
  still gap, call not authorized.
- **Named consumers:** goal owner; any later one-shot that would
  otherwise wrap Metis, unpark H11, or start H13/H02.
- **Cheapest falsifier:** v6 already has a Jupiter quote route; A26
  no longer records `jupiter_or_quote_route_present=false`; identity
  drifted from the A24 PumpSwap base mint; notional became
  `NOTIONAL_BUCKET_SET_V1`; `/build` or tx persistence claimed.
- **Terminal outcome:** `PROCEED` only if targeted tests pass, isolated
  critics run, and exact-head CI is green.
- **User-visible result:** Russian readout stating what was bound, why
  the live registry stays a gap, whether a call is allowed, the exact
  next phrase, and the forbidden follow-ons.
- **Non-goals:** no provider/network, no credential read, no `/execute`
  or `/build`, no taker/signer, no fake v7 observation, no H11 unpark,
  no H13/H02 trial, no live PIT, no canonical DONE.
- **Evidence budget:** git receipts plus public v6 registry and A26
  binder; no local full gate before PR.
- **Replan trigger:** official `/order` without taker no longer returns
  quote fields; portal key policy changes; A24 identity is retired.

## Decision capsule

- `DECISION_DELTA`: live product object is a quote-only PMF slice, not
  the next RC001 family. Jupiter V2 `/order` without taker is ADOPT.
  Live capability registry is not rewritten without an observed receipt.
- `UNCERTAINTY_REMOVED`: which official surface, which Git identity,
  which one notional, and that a call still needs a separate phrase.
- `CAPABILITY_OR_EVIDENCE`: fail-closed binder over v6 `REGISTRY_GAP`
  plus A26 plus the slice config. No decode. No network.
- `STOP`: after green exact-head CI; do not merge until the owner phrase.
- `NEXT`: after merge, do not auto-start the one-shot, H13, H02, H11
  sample-campaign, or execute. One-shot needs
  `OK PMF-QUOTE-SLICE-ONE-SHOT`.
- `SPEC_ROUTE=PRD_LITE`
- `ROADMAP_VERDICT=REBASE`
- `strongest_rejected_alternative`: offline inventory of the already
  proven PIT/execution gap, or wrapping TASK-10 Metis `/swap/v1/quote`.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ENTRY_VERDICT=START_AS_WRITTEN`

`ADOPTION_ROUTE=ADOPT_JUPITER_SWAP_V2_ORDER_QUOTE_ONLY`

`OWNER_CAPTURE_PHRASE=OK PMF-QUOTE-SLICE`

## Definition of Done

1. Binder reads live registry v6. Resolving
   `JUPITER-SOLANA-SWAP-V2-ORDER-001` is `REGISTRY_GAP`. Drift is
   fail-closed.
2. A26 still records `jupiter_or_quote_route_present=false` and
   `route_feasibility_registry_status=REGISTRY_GAP`.
3. Owner phrase is exactly `OK PMF-QUOTE-SLICE`. Terminal is
   `PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED`, or
   `PMF_QUOTE_SLICE_PREREQUISITES_DRIFT` if git receipts drifted.
4. Identity is the A24 PumpSwap pool
   `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` with base mint
   `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` quoted from SOL.
   This is not the A18 Orca POPCAT mint. Notional is `10000000`
   lamports. Parameter id is `PMF_QUOTE_SLICE_NOTIONAL_V1`, not
   `NOTIONAL_BUCKET_SET_V1`.
5. Intended call omits `taker`, forbids `/execute` and `/build`, and
   does not persist transaction bytes. TASK-10 Metis logger is not the
   adopted client.
6. Targeted tests pass. Review evidence has no
   `SINGLE_AGENT_REVIEW_FALLBACK`. No unproven `skipTest`.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW`. Research-truth, provider abstraction
and owner operability.
`PRODUCT_HORIZON_NOW=NONE`.
`CAPABILITY_RADAR_NOW=NONE`.
`CAPABILITY_RADAR_WATCH=PMF_QUOTE_ONE_SHOT_AFTER_SEPARATE_PHRASE`.

## Authority and non-claims

No provider, credential, wallet, cash, deployment or settings change.
A named intended route is not an observed registry row and not call
authority. Passing tests, CI or merge is not semantic DONE, alpha or
cashflow. This atom does not rewrite TASK-36/37/40 science, the trial
ledger, RC001 freeze or the pinned decoder.
