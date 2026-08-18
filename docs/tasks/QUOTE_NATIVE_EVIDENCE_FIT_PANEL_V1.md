---
task_id: QUOTE_NATIVE_EVIDENCE_FIT_PANEL_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-18'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 57fd8b4c915d0149825a5d64f8f9942999cf5bfa
  expected_upstream: origin/main
  expected_upstream_oid: 57fd8b4c915d0149825a5d64f8f9942999cf5bfa
  expected_branch: cursor/quote-native-evidence-fit-panel
  dirty_mode: ALLOW_REPORTED
objective: Run one authorized quote-only Jupiter Swap V2 /order measurement panel on four Git-named independent mints, two frozen notionals, buy plus reverse at t0, with +15m/+60m/+240m sells scheduled, no taker, no execute, cash cap $0, call cap 40, registry v7 bound.
managed_write_set:
  - docs/tasks/QUOTE_NATIVE_EVIDENCE_FIT_PANEL_V1.md
  - configs/quote_native_evidence_fit_panel_v1.yaml
  - src/solana_alpha_lab/quote_native_evidence_fit_panel.py
  - tests/test_quote_native_evidence_fit_panel.py
  - scripts/run_quote_native_evidence_fit_panel.py
  - docs/evidence/quote_native_evidence_fit_panel/a1_quote_native_evidence_fit_panel_runtime_receipt_v1.json
  - docs/evidence/quote_native_evidence_fit_panel/a1_quote_native_evidence_fit_panel_acceptance_v1.json
  - docs/reports/quote_native_evidence_fit_panel/a1_owner_readout_v1.md
  - docs/evidence/quote_native_evidence_fit_panel/a1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_native_evidence_fit_panel/a1_delivery_independent_review_v1.json
  - docs/evidence/quote_native_evidence_fit_panel/a1_delivery_factory_fit_v1.json
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
  - WRAP_TASK10_METIS_LOGGER
  - LIVE_MARKET_DISCOVERY
  - H13_OR_H02_TRIAL_STARTED
  - H11_UNPARK_OR_H07_UNPARK
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - RC001_FREEZE_MUTATED
  - TRIAL_LEDGER_REWRITE
  - NUMERIC_NETRETURN_OR_ALPHA_CLAIM
  - CONTINUOUS_OHLC_RECONSTRUCTION
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-PMF-QUOTE-SLICE-ONE-SHOT-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-007
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/quote_native_evidence_fit_panel_v1.yaml
      - configs/provider_route_capability_registry_v7.yaml
      - configs/pmf_quote_slice_v1.yaml
      - configs/task21_final_cohort_freeze_v1.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_runtime_receipt_v1.json
      - docs/evidence/quote_native_evidence_fit_panel/a1_quote_native_evidence_fit_panel_acceptance_v1.json
      - docs/evidence/quote_native_evidence_fit_panel/a1_delivery_completion_evidence_v1.json
      - docs/evidence/quote_native_evidence_fit_panel/a1_delivery_independent_review_v1.json
      - docs/evidence/quote_native_evidence_fit_panel/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_NATIVE_EVIDENCE_FIT_PANEL_V1

Owner phrase `OK QUOTE_NATIVE_EVIDENCE_FIT_PANEL_V1: Jupiter /swap/v2/order quote-only, taker omitted, execute forbidden, wallet/signer/transaction forbidden, cash cap $0, no retry/fallback, call cap 40, bind registry v7 route JUPITER-SOLANA-SWAP-V2-ORDER-001`.

Measurement panel, not a hypothesis trial. Identities are selected from already-frozen Git names. No live market discovery. Keyless GET only. Credential/.env read is forbidden. Raw bodies stay A4 outside git.

## Task Outcome Brief

- **Owner decision:** replace the next market-truth route with a quote-native prospective panel because one prior `/order` proved route existence, not serial PIT quote/exit/fee measurement.
- **Product outcome:** a frozen protocol plus t0 buy/reverse observations on Git-named independent mints until a typed stop; delayed sells at +15m/+60m/+240m remain scheduled in the same receipt.
- **Named consumers:** goal owner; later quote-native falsifier design. Not H13/H02/H11/H07.
- **Cheapest falsifier:** the same protocol cannot produce a comparable quote-or-typed-failure on the second independent identity; a base measurement requires taker, execute, wallet, or a new provider.
- **Terminal outcomes:** `T0_PANEL_OBSERVED`, `SECOND_IDENTITY_PROTOCOL_FAIL`, `CREDENTIAL_REQUIRED_NOT_AUTHORIZED`, `PANEL_PROTOCOL_FAIL`.
- **User-visible result:** Russian readout of identity sources, t0 quote/typed-failure counts, fee-field presence, remaining horizon due times, and that this is not DONE/alpha/NetReturn.
- **Non-goals:** OHLC warehouse; H13 repair; H02 trial; taker `/order`; `/execute`; wallet; NetReturn; canonical DONE.
- **Evidence budget:** at most 40 provider GET `/swap/v2/order`; this atom executes due t0 cells until the cheapest falsifier, a typed stop, or the t0 cap. Horizons remain same-contract continuation.
- **Replan trigger:** second identity incomparable; credential required; second provider/route pivot; another preparatory-only atom.

## Decision capsule

- `DECISION_DELTA`: next market byte comes from a serial quote-native panel, not attempt-prep or OHLC reconstruction.
- `UNCERTAINTY_REMOVED`: whether one frozen `/order` protocol yields comparable PIT quote/reverse/typed-failure states on more than one Git-named identity.
- `CAPABILITY_OR_EVIDENCE`: t0 panel receipt with raw A4 retention, quote-level fee/route projection, and frozen remaining sells.
- `STOP`: after exact-head CI; do not merge until the owner phrase bound to this PR/head.
- `NEXT`: owner chooses horizons-only for already quoted buys (`wave=due`) or a new t0 clock for leftover identities. Do not start MOVE 2, taker, H13, or H02.
- `SPEC_ROUTE=PRD_LITE`
- `ROADMAP_VERDICT=KEEP`
- `strongest_rejected_alternative`: continue `PMF-QUOTE-ATTEMPT-PREP` to taker `/order`, or reconstruct continuous OHLC.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`
- `ADOPTION_ROUTE=ADOPT_JUPITER_SWAP_V2_ORDER_QUOTE_ONLY`

`ENTRY_VERDICT=START_AS_WRITTEN`

`OWNER_CAPTURE_PHRASE=OK QUOTE_NATIVE_EVIDENCE_FIT_PANEL_V1: Jupiter /swap/v2/order quote-only, taker omitted, execute forbidden, wallet/signer/transaction forbidden, cash cap $0, no retry/fallback, call cap 40, bind registry v7 route JUPITER-SOLANA-SWAP-V2-ORDER-001`

## Definition of Done

1. Four identities are frozen from Git: A24 mint plus three TASK-21 R2 freeze mints. No DexScreener/live discovery.
2. Two notionals are frozen: `10000000` and `1000000` lamports. Slippage 100 bps.
3. A t0 cell is SOL→mint buy then, iff buy quoted, mint→SOL reverse using exact `outAmount`. Missing buy ⇒ reverse/sells are `SKIPPED_NO_ENTRY` and consume no extra calls. Unreached t0 cells after a typed stop stay `NOT_REACHED`.
4. Keyless GET `https://api.jup.ag/swap/v2/order` without `taker`. No `/execute`, `/build`, wallet, signer, or transaction bytes in git.
5. No credential or `.env` read. HTTP 401/403 is `CREDENTIAL_REQUIRED_NOT_AUTHORIZED` and stops the panel.
6. Quote projection keeps fee/route/price-impact fields as observed or typed ABSENT/NULL; missing is never zero.
7. Provider requests ≤ 40, retries 0, fallbacks 0. This atom executes t0 cells until a second-identity protocol fail, credential stop, call cap, or typed rate-limit stop. Remaining t0 cells are `NOT_REACHED`; horizon sells stay `SCHEDULED` unless their parent buy already failed. A 429 is not retried and is not a second-identity protocol fail if that identity already produced `QUOTE_OBSERVED`. Continuation `wave=due` loads the Git t0 receipt as the only schedule, selects only due horizon sells, and must not rebuild `due_at` from now, re-call consumed cells, or fire leftover t0 buys. `T0_PANEL_OBSERVED` requires a protocol-comparable observation (`QUOTE_OBSERVED`, `NO_ROUTE`, or `PROVIDER_TYPED_FAILURE`) on the second independent identity; transport-unknown and 429 are not comparable.
8. Russian readout names sources, t0 outcomes, and that MOVE 2/taker/H13/H02 do not auto-start.
