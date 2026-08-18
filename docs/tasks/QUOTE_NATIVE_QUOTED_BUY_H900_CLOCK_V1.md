---
task_id: QUOTE_NATIVE_QUOTED_BUY_H900_CLOCK_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-18'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 67c58dec8ce274c102f65ad7dbb82a5e801d4db9
  expected_upstream: origin/main
  expected_upstream_oid: 67c58dec8ce274c102f65ad7dbb82a5e801d4db9
  expected_branch: cursor/quote-native-quoted-buy-h900-clock
  dirty_mode: ALLOW_REPORTED
objective: Run one new-clock quote-only Jupiter V2 /order panel on already-quoted buys only, t0 buy/reverse plus one honest +15m sell in this session, with +60m/+240m explicit gap and no backfill.
managed_write_set:
  - docs/tasks/QUOTE_NATIVE_QUOTED_BUY_H900_CLOCK_V1.md
  - configs/quote_native_quoted_buy_h900_clock_v1.yaml
  - src/solana_alpha_lab/quote_native_quoted_buy_h900_clock.py
  - tests/test_quote_native_quoted_buy_h900_clock.py
  - scripts/run_quote_native_quoted_buy_h900_clock.py
  - docs/evidence/quote_native_quoted_buy_h900_clock/a1_quote_native_quoted_buy_h900_clock_runtime_receipt_v1.json
  - docs/evidence/quote_native_quoted_buy_h900_clock/a1_quote_native_quoted_buy_h900_clock_acceptance_v1.json
  - docs/reports/quote_native_quoted_buy_h900_clock/a1_owner_readout_v1.md
  - docs/evidence/quote_native_quoted_buy_h900_clock/a1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_native_quoted_buy_h900_clock/a1_delivery_independent_review_v1.json
  - docs/evidence/quote_native_quoted_buy_h900_clock/a1_delivery_factory_fit_v1.json
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
  - LEFTOVER_B_C_OR_T21A_001
  - OLD_DUE_AT_REBUILT_OR_OLD_RECEIPT_MUTATED
  - BACKFILL_H3600_OR_H14400
  - WRAP_TASK10_METIS_LOGGER
  - LIVE_MARKET_DISCOVERY
  - H13_OR_H02_TRIAL_STARTED
  - H11_UNPARK_OR_H07_UNPARK
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - RC001_FREEZE_MUTATED
  - TRIAL_LEDGER_REWRITE
  - NUMERIC_NETRETURN_OR_ALPHA_CLAIM
  - BACKGROUND_SCHEDULER
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-007
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/quote_native_quoted_buy_h900_clock_v1.yaml
      - configs/quote_native_evidence_fit_panel_v1.yaml
      - configs/provider_route_capability_registry_v7.yaml
      - configs/pmf_quote_slice_v1.yaml
      - configs/task21_final_cohort_freeze_v1.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/quote_native_evidence_fit_panel/a1_quote_native_evidence_fit_panel_runtime_receipt_v1.json
      - docs/evidence/quote_native_quoted_buy_h900_clock/a1_quote_native_quoted_buy_h900_clock_acceptance_v1.json
      - docs/evidence/quote_native_quoted_buy_h900_clock/a1_delivery_completion_evidence_v1.json
      - docs/evidence/quote_native_quoted_buy_h900_clock/a1_delivery_independent_review_v1.json
      - docs/evidence/quote_native_quoted_buy_h900_clock/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_NATIVE_QUOTED_BUY_H900_CLOCK_V1

Owner phrase `OK QUOTE_NATIVE_QUOTED_BUY_H900_CLOCK_V1: Jupiter /swap/v2/order quote-only, taker omitted, execute forbidden, wallet/signer/transaction forbidden, cash cap $0, no retry/fallback, call cap 16, bind registry v7 route JUPITER-SOLANA-SWAP-V2-ORDER-001, new clock A24 both notionals plus T21_R2_MINT_A 0.01 SOL only, t0 plus +15m only in this session, +60m and +240m explicit gap no backfill, leftover B/C and 0.001 forbidden, old due_at not rebuilt`.

Measurement panel on a **new** clock. Reuses the keyless `/order` helpers. Does not mutate the prior t0 receipt. No leftover B/C. No T21 A 0.001 SOL. No owner alarm for +60m/+240m.

## Task Outcome Brief

- **Owner decision:** do not fire overdue original-clock horizons or leftover t0; start a new clock only for already-quoted buys and take one honest +15m delayed sell in this session.
- **Product outcome:** t0 buy/reverse plus +15m sell quotes (or typed stop) on A24 both notionals and T21_R2_MINT_A 0.01 SOL; +60m/+240m recorded as `EXPLICIT_GAP` with no backfill.
- **Named consumers:** goal owner; later quote-native falsifier design. Not H13/H02/H11/H07.
- **Cheapest falsifier:** a quoted buy cannot produce a protocol-comparable delayed sell at the frozen +15m offset (`NO_ROUTE` or `PROVIDER_TYPED_FAILURE`), or t0 cannot re-quote a previously quoted cell.
- **Terminal outcomes:** `T0_QUOTED_BUY_CLOCK_ARMED`, `H900_PANEL_OBSERVED`, `H900_MISSED_OFFSET`, `SECOND_CELL_PROTOCOL_FAIL`, `CREDENTIAL_REQUIRED_NOT_AUTHORIZED`, `PANEL_PROTOCOL_FAIL`, `PANEL_RATE_LIMITED`.
- **User-visible result:** Russian readout of new clock, t0/+15m terminals, explicit +60m/+240m gaps, and that this is not DONE/alpha/MOVE 1 complete.
- **Non-goals:** leftover B/C; T21 A 0.001; original due_at rebuild; +60m/+240m observation; taker; `/execute`; H13/H02; NetReturn; canonical DONE; background scheduler.
- **Evidence budget:** at most 16 provider GET `/swap/v2/order`; t0 at most 6; +15m at most remaining cap; retries 0.
- **Replan trigger:** second cell incomparable; credential required; 429 stop; lateness beyond slack; second provider/route pivot.

## Decision capsule

- `DECISION_DELTA`: honest +15m delayed sell on already-quoted buys, not leftover breadth and not late original-clock H900/H3600/H14400.
- `UNCERTAINTY_REMOVED`: whether the same frozen `/order` protocol still quotes those buys at a new t0 and yields a comparable mint→SOL sell ~900s later.
- `CAPABILITY_OR_EVIDENCE`: new-clock runtime receipt; H3600/H14400 `EXPLICIT_GAP`; prior panel receipt immutable.
- `STOP`: after exact-head CI; merge only with the owner phrase bound to this PR/head.
- `NEXT`: owner reads +15m result; do not auto-start leftover t0, +60m/+240m backfill, MOVE 2, taker, or H02.
- `SPEC_ROUTE=PRD_LITE`
- `ROADMAP_VERDICT=PATCH`
- `strongest_rejected_alternative`: `wave=due` on the original clock, or leftover B/C t0, or owner-alarm +60m/+240m.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`
- `ADOPTION_ROUTE=WRAP_EXISTING_QUOTE_NATIVE_ORDER_HELPERS`

`ENTRY_VERDICT=START_AS_WRITTEN`

`OWNER_CAPTURE_PHRASE=OK QUOTE_NATIVE_QUOTED_BUY_H900_CLOCK_V1: Jupiter /swap/v2/order quote-only, taker omitted, execute forbidden, wallet/signer/transaction forbidden, cash cap $0, no retry/fallback, call cap 16, bind registry v7 route JUPITER-SOLANA-SWAP-V2-ORDER-001, new clock A24 both notionals plus T21_R2_MINT_A 0.01 SOL only, t0 plus +15m only in this session, +60m and +240m explicit gap no backfill, leftover B/C and 0.001 forbidden, old due_at not rebuilt`

## Definition of Done

1. Cells are exactly three Git-frozen pairs: A24 `10000000`, A24 `1000000`, T21_R2_MINT_A `10000000`. B, C, and T21 A `1000000` are forbidden.
2. New `panel_started_at`. Prior `quote_native_evidence_fit_panel` runtime receipt is not overwritten and is not a due-wave prior.
3. t0 is SOL→mint buy then, iff quoted, mint→SOL reverse using exact `outAmount`.
4. Observable delayed sell is only `SELL_H900` when `due_at <= now <= due_at + lateness_slack`. Early stays `SCHEDULED`. Late is `MISSED_OFFSET` with no call. No backfill.
5. `SELL_H3600` and `SELL_H14400` are `EXPLICIT_GAP` at t0 and never selected.
6. Keyless GET `https://api.jup.ag/swap/v2/order` without `taker`. No `/execute`, `/build`, wallet, `.env`, or transaction bytes in git.
7. Provider requests ≤ 16, retries 0, fallbacks 0. HTTP 429 is not retried.
8. Reuses public one-shot `/order` helpers; does not wrap TASK-10 Metis logger.
9. Russian readout names the new clock, t0/+15m, and explicit gaps.
