---
task_id: QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1
task_version: '1.1'
status: DONE
as_of: '2026-08-18'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 91b7e7144e9a94b47e626178d521cc2f89c817dc
  expected_upstream: origin/main
  expected_upstream_oid: 91b7e7144e9a94b47e626178d521cc2f89c817dc
  expected_branch: cursor/quote-native-live-variation-campaign
  dirty_mode: ALLOW_REPORTED
objective: Run one live outcome-blind quote-native campaign that first discovers a fresh Tokens V2 sample, then measures whether quoted round-trip amounts move over +15m and +60m on that sample plus a traded control stratum.
managed_write_set:
  - docs/tasks/QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1.md
  - configs/quote_native_live_variation_campaign_v1.yaml
  - src/solana_alpha_lab/quote_native_live_variation_campaign.py
  - tests/test_quote_native_live_variation_campaign.py
  - scripts/run_quote_native_live_variation_campaign.py
  - configs/provider_route_capability_registry_v8.yaml
  - catalog/schemas/provider_route_capability_registry_v8.schema.json
  - src/solana_alpha_lab/provider_route_capability_registry_v8.py
  - tests/test_provider_route_capability_registry_v8.py
  - docs/evidence/quote_native_live_variation_campaign/a1_quote_native_live_variation_campaign_runtime_receipt_v1.json
  - docs/evidence/quote_native_live_variation_campaign/a1_quote_native_live_variation_campaign_acceptance_v1.json
  - docs/reports/quote_native_live_variation_campaign/a1_owner_readout_v1.md
  - docs/evidence/quote_native_live_variation_campaign/a1_delivery_completion_evidence_v1.json
  - docs/evidence/quote_native_live_variation_campaign/a1_delivery_independent_review_v1.json
  - docs/evidence/quote_native_live_variation_campaign/a1_delivery_factory_fit_v1.json
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
  - PACE_BELOW_TWO_SECONDS
  - A24_OR_T21_FREEZE_SELECTED
  - T21_FREEZE_REUSED_AS_SAMPLE
  - THRESHOLD_FIT_ON_THIS_SAMPLE
  - H13_OR_H02_TRIAL_STARTED
  - H11_UNPARK_OR_H07_UNPARK
  - WALLET_SIGNER_TX_OR_DEPLOYMENT
  - RC001_FREEZE_MUTATED
  - TRIAL_LEDGER_REWRITE
  - NUMERIC_NETRETURN_OR_ALPHA_CLAIM
  - BACKGROUND_SCHEDULER
  - SECOND_PROVIDER_FORBIDDEN
  - BACKFILL_H14400
context_requirements:
  catalog_asset_ids:
    - EVIDENCE-QUOTE-NATIVE-FRICTION-H900-FALSIFIER-ACCEPTANCE-001
    - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-007
  l2_roles: [DELIVERY_EVIDENCE, EXTERNAL_ROUTE_KNOWLEDGE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
      - configs/quote_native_live_variation_campaign_v1.yaml
      - configs/provider_route_capability_registry_v7.yaml
      - configs/provider_route_capability_registry_v8.yaml
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/quote_native_friction_h900_falsifier/a1_quote_native_friction_h900_falsifier_acceptance_v1.json
      - docs/evidence/quote_native_live_variation_campaign/a1_quote_native_live_variation_campaign_acceptance_v1.json
      - docs/evidence/quote_native_live_variation_campaign/a1_delivery_completion_evidence_v1.json
      - docs/evidence/quote_native_live_variation_campaign/a1_delivery_independent_review_v1.json
      - docs/evidence/quote_native_live_variation_campaign/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1

Owner phrase `OK QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1: Jupiter Tokens V2 /recent plus /toptraded/1h control keyless, quote-only /swap/v2/order, taker omitted, execute forbidden, wallet/signer/transaction forbidden, cash cap $0, no retry/fallback, pace >=2s, call cap 60, bind order route JUPITER-SOLANA-SWAP-V2-ORDER-001, registry v8 additive after first observation, live outcome-blind sample, no T21 freeze reuse, no A24, +15m and +60m sells, +240m explicit gap`.

One campaign, one contract, three waves. First byte is discovery. Quotes run only after a frozen live cohort exists. Not a friction-prediction trial and not Factory v1.

## Task Outcome Brief

- **Owner decision:** stop using the stale T21 freeze as the quote-native sample; learn whether quoted round-trip amounts move over 900s and 3600s on a live outcome-blind sample plus a traded control.
- **Product outcome:** one appended campaign receipt with a frozen live cohort, paced t0 buy/reverse, honest +15m/+60m sells, and a typed variation verdict. Registry v8 is additive after the first Tokens V2 observation.
- **Named consumers:** goal owner choosing whether quote-native family continues (MOVE 2) or closes.
- **Cheapest falsifier:** `GET /tokens/v2/recent` returns 401/403 before any quote; or the traded control has ≥6 complete X/Y cells and fewer than half are time-separated (`Y≠X`).
- **Terminal outcomes:** `DISCOVERY_CREDENTIAL_REQUIRED_NOT_AUTHORIZED` | `CONTROL_STRATUM_CREDENTIAL_REQUIRED_NOT_AUTHORIZED` | `SAMPLE_INVALID_INSUFFICIENT_DISCOVERY` | `DISCOVERY_COHORT_FROZEN` | `T0_VARIATION_CLOCK_ARMED` | `VARIATION_PRESENT_NOT_MECHANISM` | `VARIATION_ABSENT_ON_TRADED_CONTROL` | `SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY` | `PANEL_RATE_LIMITED` | `CREDENTIAL_REQUIRED_NOT_AUTHORIZED`.
- **User-visible result:** Russian readout of strata, complete vs time-separated counts, kill vs continue, and that this is not NetReturn, alpha, or MOVE 2.
- **Non-goals:** DexScreener; T21 freeze reuse; A24 leftover; +240m backfill; threshold fit; taker/`/execute`; wallet; H07/H11/H13/H02 unpark; Factory cockpit; trial-ledger rewrite.
- **Evidence budget:** at most 60 keyless GET; discovery at most 2; quotes paced ≥2s; retries 0.
- **Replan trigger:** discovery requires a credential; paced 2s still 429s before 20 comparable quotes; second provider; another preparatory-only atom before the first market byte.

## Decision capsule

- `DECISION_DELTA`: quote-native contour becomes a live-sample variation test, not another freeze-cohort falsifier.
- `UNCERTAINTY_REMOVED`: whether quote-layer round-trip amounts move over 15m/60m on tokens that currently trade, or `Y=X` was a property of the channel.
- `CAPABILITY_OR_EVIDENCE`: Tokens V2 discovery adapter + wrap of existing `/order` helpers and `score_mechanism`; additive registry v8.
- `STOP`: after exact-head CI; merge only with the repository phrase bound to this PR/head.
- `NEXT`: variation present → MOVE 2 on a fresh window. Variation absent on traded control → close quote-native as alpha source. Discovery 401 → owner decides free API key versus class-C stop.
- `SPEC_ROUTE=PRD_LITE`
- `ROADMAP_VERDICT=REORDER`
- `strongest_rejected_alternative`: another unused-T21 falsifier, or Touch/Fillable/execute before variation exists.
- `MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`
- `ADOPTION_ROUTE=ADOPT_JUPITER_TOKENS_V2_RECENT_AND_WRAP_EXISTING_ORDER_HELPERS`

`ENTRY_VERDICT=START_AS_WRITTEN`

`OWNER_CAPTURE_PHRASE=OK QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1: Jupiter Tokens V2 /recent plus /toptraded/1h control keyless, quote-only /swap/v2/order, taker omitted, execute forbidden, wallet/signer/transaction forbidden, cash cap $0, no retry/fallback, pace >=2s, call cap 60, bind order route JUPITER-SOLANA-SWAP-V2-ORDER-001, registry v8 additive after first observation, live outcome-blind sample, no T21 freeze reuse, no A24, +15m and +60m sells, +240m explicit gap`

## Estimand (variation existence, not NetReturn)

X = t0 reverse `outAmount` / t0 buy input − 1, only if buy and reverse are `QUOTE_OBSERVED`.

Y = H900 sell `outAmount` / t0 buy input − 1, only if buy and H900 sell are `QUOTE_OBSERVED`. Complete cells with `Y=X` are not time-separated.

Control kill, frozen before quotes: if the TRADED stratum has ≥6 complete X/Y cells and time-separated share `< 0.5`, the channel is uninformative.

Primary success: ≥10 complete X/Y cells and ≥6 time-separated, with both strata represented.

H3600 is a secondary observable, not the kill criterion. H14400 is an explicit gap.

## Definition of Done

1. Discovery is exactly two keyless GET: `https://api.jup.ag/tokens/v2/recent` then `https://api.jup.ag/tokens/v2/toptraded/1h`. No DexScreener. HTTP 401/403 on `/recent` stops before any `/order`.
2. Cohort freeze is 6 RECENT + 6 TRADED cells at `10000000` lamports after a predeclared liquidity floor of 1000. Ranking does not use `usdPrice`. A24 and all TASK-21 freeze mints are forbidden.
3. t0 is SOL→mint buy then, iff quoted, mint→SOL reverse using exact `outAmount`. Observable delayed sells are `SELL_H900` and `SELL_H3600`. `wave=due` is repeatable and consumes only horizons that are due and inside slack. `SELL_H14400` is `EXPLICIT_GAP`.
4. Keyless GET `https://api.jup.ag/swap/v2/order` without `taker`. No `/execute`, `/build`, wallet, `.env`, or transaction bytes in git.
5. Provider requests ≤ 60, retries 0, fallbacks 0. Minimum 2 seconds between provider calls. HTTP 429 is not retried.
6. Missing is never zero. `Y=X` is not a directional hint. Family is not closed on `SAMPLE_INVALID_*`.
7. Registry v8 is append-only after the first Tokens V2 observation and preserves v7 route semantics.
8. Russian readout names strata, variation, and limitations.

## Canonical closure

`FINISH_GATE=DONE_CONFIRMED`: the owner accepted
`SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY` as the terminal result of this
keyless campaign. The result is neither alpha nor MOVE 2, and it does not close
the quote-native family by itself. Historical A1 receipt bytes remain bound to
task version 1.0; the owner-approved replan is recorded separately in
`docs/evidence/quote_native_live_variation_campaign/a2_replan_closure_v1.json`.
