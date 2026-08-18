---
task_id: QUOTE_NATIVE_FRICTION_H900_FALSIFIER_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-18'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 497a3056d79bb0328c3dfc56f68e4dbb2694d0cb
  expected_upstream: origin/main
  expected_upstream_oid: 497a3056d79bb0328c3dfc56f68e4dbb2694d0cb
  expected_branch: cursor/quote-native-friction-h900-falsifier
  dirty_mode: ALLOW_REPORTED
objective: Run one quote-native t0-friction to +15m quoted-liquidation mechanism look on four unused TASK-21 freeze mints, one 0.01 SOL notional, admission frozen before any Jupiter call, no live discovery, no A24/T21 A, no +60m/+240m backfill.
managed_write_set:
  - docs/tasks/QUOTE_NATIVE_FRICTION_H900_FALSIFIER_V1.md
  - configs/quote_native_friction_h900_falsifier_v1.yaml
  - src/solana_alpha_lab/quote_native_friction_h900_falsifier.py
  - tests/test_quote_native_friction_h900_falsifier.py
  - scripts/run_quote_native_friction_h900_falsifier.py
  - docs/evidence/quote_native_friction_h900_falsifier/a1_quote_native_friction_h900_falsifier_runtime_receipt_v1.json
  - docs/evidence/quote_native_friction_h900_falsifier/a1_quote_native_friction_h900_falsifier_acceptance_v1.json
  - docs/reports/quote_native_friction_h900_falsifier/a1_owner_readout_v1.md
  - docs/evidence/quote_native_friction_h900_falsifier/a1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_native_friction_h900_falsifier/a1_delivery_independent_review_v1.json
  - docs/evidence/quote_native_friction_h900_falsifier/a1_delivery_factory_fit_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
external_caps:
  network: true
  credentials: false
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - AUTHORITY_WIDENING
  - JUPITER_EXECUTE_OR_BUILD
  - TAKER_OR_SIGNER_SUPPLIED
  - PERSIST_TRANSACTION_BYTES
  - CREDENTIAL_READ_OR_DOTENV
  - RETRY_OR_FALLBACK
  - CALL_CAP_EXCEEDED
  - LIVE_MARKET_DISCOVERY
  - A24_OR_T21A_SELECTED
  - CONSUMED_H900_OUTCOME_REUSED
  - THRESHOLD_FIT_ON_THIS_SAMPLE
  - H13_OR_H02_TRIAL_STARTED
  - H11_UNPARK_OR_H07_UNPARK
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - RC001_FREEZE_MUTATED
  - TRIAL_LEDGER_REWRITE
  - NUMERIC_NETRETURN_OR_ALPHA_CLAIM
  - BACKGROUND_SCHEDULER
  - SECOND_PROVIDER_FORBIDDEN
  - BACKFILL_H3600_OR_H14400
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-QUOTE-NATIVE-QUOTED-BUY-H900-CLOCK-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-007
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/quote_native_friction_h900_falsifier_v1.yaml
      - configs/quote_native_quoted_buy_h900_clock_v1.yaml
      - configs/provider_route_capability_registry_v7.yaml
      - configs/task21_final_cohort_freeze_v1.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/quote_native_quoted_buy_h900_clock/a1_quote_native_quoted_buy_h900_clock_acceptance_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_NATIVE_FRICTION_H900_FALSIFIER_V1

Owner phrase `OK QUOTE_NATIVE_FRICTION_H900_FALSIFIER_V1: Jupiter /swap/v2/order quote-only, taker omitted, execute forbidden, wallet/signer/transaction forbidden, cash cap $0, no retry/fallback, call cap 16, bind registry v7 route JUPITER-SOLANA-SWAP-V2-ORDER-001, unused T21 B/C plus R3 two mints only, one notional 0.01 SOL, t0 buy/reverse plus +15m sell, A24 and T21 A forbidden, +60m/+240m explicit gap no backfill, no live discovery`.

First hypothesis-bearing use of the quote-native `/order` primitive. Not another measurement-only panel. Not H07/H11 unpark. Sample is the four unused TASK-21 freeze mints that do not yet have a quoted-buy H900 outcome. That cohort is outcome-blind for this estimand and age-stale relative to a live 15m memecoin universe.

## Task Outcome Brief

- **Owner decision:** stop measuring quote capability in isolation; test whether t0 quoted round-trip friction ranks +15m quoted liquidation on already-admitted unused names.
- **Product outcome:** one frozen X→Y look: `QuotedRoundTripFriction(t0)` → `QuotedLiquidationRecovery(+15m)` plus sell-route survival, or an explicit `SAMPLE_INVALID_*` if the stale cohort cannot support the comparison.
- **Named consumers:** goal owner; later live-window confirmation only if a directional hint appears. Not H13/H02/H11/H07.
- **Cheapest falsifier:** on cells with both X and Y observed, worse t0 friction does not rank with worse H900 quoted recovery; or the sample is route-dominated so the mechanism cannot be scored.
- **Terminal outcomes:** `T0_FRICTION_CLOCK_ARMED` | `H900_MECHANISM_SCORED` | `DIRECTIONAL_HINT_NOT_CONFIRMATION` | `MECHANISM_NOT_SUPPORTED_ON_THIS_SAMPLE` | `SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY` | `SAMPLE_INVALID_ROUTE_DOMINATED` | `H900_MISSED_OFFSET` | `SECOND_IDENTITY_PROTOCOL_FAIL` | `PANEL_RATE_LIMITED` | `CREDENTIAL_REQUIRED_NOT_AUTHORIZED`.
- **User-visible result:** Russian readout of X/Y cells, concordance, sample-invalid vs mechanism-not-supported, and that this is not NetReturn, alpha, live-universe confirmation, or family close.
- **Non-goals:** DexScreener/live discovery; 8–12 names; second nomination window; leftover measurement of A24/T21 A; +60m/+240m; threshold fitting; taker/simulation; real money; H07/H13/H11 unpark; Factory cockpit.
- **Evidence budget:** at most 16 provider GET `/swap/v2/order`; t0 at most 8; +15m at most remaining cap; retries 0.
- **Replan trigger:** second provider/route pivot; live discovery required to get any complete X/Y; 429/protocol stop before two identities; threshold search on this sample.

## Decision capsule

- `DECISION_DELTA`: quote-native contour becomes an instrument for a new sparse friction→liquidation look, not a longer measurement ladder.
- `UNCERTAINTY_REMOVED`: whether unused TASK-21 names, already admitted outcome-blind, show any predeclared X→Y direction at +15m, or the stale sample is invalid.
- `CAPABILITY_OR_EVIDENCE`: wrap existing `/order` helpers; frozen four-mint sample; mechanism score with missing≠zero.
- `STOP`: after exact-head CI; live capture only with the owner phrase; merge only with the repository phrase bound to this PR/head.
- `NEXT`: `SAMPLE_INVALID_*` → do not close the family; a later live-window nomination is a separate atom. `DIRECTIONAL_HINT_NOT_CONFIRMATION` → MOVE 2 on a fresh window. `MECHANISM_NOT_SUPPORTED_ON_THIS_SAMPLE` → close this exact estimand/family, not H07.
- `SPEC_ROUTE=PRD_LITE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: 8–12 live DexScreener names and a second window in this atom, or leftover A24/T21 A / +60m/+240m measurement.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`
- `ADOPTION_ROUTE=WRAP_EXISTING_QUOTE_NATIVE_ORDER_HELPERS`

`ENTRY_VERDICT=START_WITH_PATCH`

`OWNER_CAPTURE_PHRASE=OK QUOTE_NATIVE_FRICTION_H900_FALSIFIER_V1: Jupiter /swap/v2/order quote-only, taker omitted, execute forbidden, wallet/signer/transaction forbidden, cash cap $0, no retry/fallback, call cap 16, bind registry v7 route JUPITER-SOLANA-SWAP-V2-ORDER-001, unused T21 B/C plus R3 two mints only, one notional 0.01 SOL, t0 buy/reverse plus +15m sell, A24 and T21 A forbidden, +60m/+240m explicit gap no backfill, no live discovery`

## Estimand (screening, not NetReturn)

X = `QuotedRoundTripFriction` = t0 reverse `outAmount` / t0 buy input − 1, only if buy and reverse are `QUOTE_OBSERVED`. Missing stays missing.

Y = `QuotedLiquidationRecovery` = H900 sell `outAmount` / t0 buy input − 1, only if buy and H900 sell are `QUOTE_OBSERVED`. Typed `NO_ROUTE` / failure is a survival tail, not a numeric Y.

Predeclared direction: more negative X ranks with more negative Y. Concordance is a hint. No threshold is chosen on this sample.

Consumed H900 outcomes on A24 and T21 A are development evidence only and are not this trial's sample.

## Definition of Done

1. Cells are exactly four Git-frozen pairs at `10000000`: `T21_R2_MINT_B`, `T21_R2_MINT_C`, `T21_R3_MINT_1`, `T21_R3_MINT_2`. A24 and T21 A are forbidden.
2. Admission is the TASK-21 freeze; no live market discovery; no DexScreener call.
3. t0 is SOL→mint buy then, iff quoted, mint→SOL reverse using exact `outAmount`.
4. Observable delayed sell is only `SELL_H900` inside `due_at` plus slack. `SELL_H3600` and `SELL_H14400` are `EXPLICIT_GAP`.
5. Keyless GET `https://api.jup.ag/swap/v2/order` without `taker`. No `/execute`, `/build`, wallet, `.env`, or transaction bytes in git.
6. Provider requests ≤ 16, retries 0, fallbacks 0. HTTP 429 is not retried.
7. Mechanism score treats missing as missing. Family is not closed on `SAMPLE_INVALID_*`.
8. Russian readout names X/Y, concordance, and limitations.
