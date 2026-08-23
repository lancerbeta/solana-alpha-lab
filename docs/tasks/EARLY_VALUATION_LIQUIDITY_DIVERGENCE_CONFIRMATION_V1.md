---
task_id: EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-24'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3ba94251a4fbc7c2bd4093b1109947dedae10166
  expected_upstream: origin/main
  expected_upstream_oid: 3ba94251a4fbc7c2bd4093b1109947dedae10166
  expected_branch: cursor/early-valuation-liquidity-divergence-confirmation
  dirty_mode: ALLOW_REPORTED
objective: Fresh-mint PIT falsifier of early valuation-liquidity divergence, X =
  ln(R1/R0) across two prospective FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO snapshots
  300s apart, H900 after the second snapshot, Factory runner unchanged, no Discovery/A7.
managed_write_set:
- docs/tasks/EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1.md
- configs/early_valuation_liquidity_divergence_confirmation_v1.yaml
- src/solana_alpha_lab/early_valuation_liquidity_divergence_confirmation.py
- scripts/run_early_valuation_liquidity_divergence_confirmation.py
- tests/test_early_valuation_liquidity_divergence_confirmation.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_acceptance_v1.json
- docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_delivery_completion_evidence_v1.json
- docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_delivery_independent_review_v1.json
- docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_delivery_factory_fit_v1.json
- docs/reports/early_valuation_liquidity_divergence_confirmation/a1_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_JUPITER_OR_CREDENTIAL_READ_WITHOUT_EXACT_OWNER_PHRASE
- CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION
- CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT
- DOTENV_READ
- API_KEY_IN_URL_LOG_RECEIPT_OR_GIT
- RAW_BODY_CONTAINS_CREDENTIAL
- JUPITER_EXECUTE_OR_BUILD
- TAKER_OR_SIGNER_SUPPLIED
- WALLET_SIGNER_TRANSACTION_OR_DEPLOYMENT
- RETRY_OR_FALLBACK
- CALL_CAP_EXCEEDED
- PACE_BELOW_THREE_SECONDS
- SECOND_PROVIDER_OR_PAID_PLAN
- PRIOR_MINT_REUSED
- UNKNOWN_AS_ZERO
- FDV_AS_MCAP_SUBSTITUTE
- FACTORY_RUNNER_CHANGE
- CLOSED_FAMILY_THRESHOLD_WINDOW_OR_BUCKET_REOPEN
- SECOND_CAPTURE_WINDOW
- RUN_CAMPAIGN_BLACK_BOX_REUSE
- DISCOVERY_OR_A7_ACTIVATION
- VPS_OR_SHADOW_OR_MICRO_LIVE
- ALPHA_OR_NETRETURN
context_requirements:
  catalog_asset_ids:
  - CTRL-EARLY-ICP-FREEZE-AND-MATURITY-BRANCH-CLOSE-001
  - MODULE-ORDINARY-MARKET-PIT-PRIMARY-X-001
  - MODULE-ORDINARY-RECENT-ORGANIC-PRESSURE-H900-AUDITION-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  - EVIDENCE-EARLY-STRUCTURAL-BACKING-PIT-ACCEPTANCE-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - configs/provider_route_capability_registry_v10.yaml
    - configs/early_icp_freeze_and_maturity_branch_close_v1.yaml
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_delivery_completion_evidence_v1.json
    - docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_delivery_independent_review_v1.json
    - docs/evidence/early_valuation_liquidity_divergence_confirmation/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
    - docs/evidence/early_structural_backing_pit_commissioning/a1_acceptance_v1.json
---

# EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=BOTH`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

`ROADMAP_VERDICT=KEEP`

`NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at PR/CI/merge after scientific terminal
or after the exact owner phrase gate.

Owner nomination resolves prior `PAUSE_NO_CANDIDATE`. It does **not** activate
`ARCH-INTENT-006` or A7.

`strongest_rejected_alternative`: call existing `run_campaign` and score with
`tau_b_floor=0.20` / quartile / LOO. Rejected because that reopens the closed
EARLY_STRUCTURAL_BACKING buckets and cannot represent two PIT snapshots.

`ADOPTION_ROUTE=ADOPT_BIND_PRIMARY_X_AND_SEARCH_QUOTE_HELPERS_WRAP_TWO_SNAPSHOT_LN_BUILD_NO_FACTORY_RUNNER`

### Distinctness challenge

Closed family X = absolute `liquidity/mcap` at one decision snapshot.
This candidate X = `ln(R1/R0)` from two prospective snapshots 300s apart.
A high-level mint with no change has X=0 here and would have ranked high in
the closed family. Fresh mints only. No Window B. No 0.20 / quartile / LOO.

### Mechanical composition probe

`bind_primary_x` twice plus `ln(R1/R0)` works with UNKNOWN≠0.
`factory/runner.py` has no temporal primitive and stays hash-pinned.
`run_campaign` performs one search and pins closed-family score rules.
Therefore WRAP helpers; do not reuse `run_campaign` as a black box.
Factory core delta target 0. Not `FACTORY_LEVERAGE_REPLAN`.

## Owner authorization boundary

Implementation, zero-network tests, commit and PR may proceed under
`DIRECT_CURSOR_DELIVERY`. Provider calls require this exact phrase after
offline preflight is green:

```
OK EARLY_VALUATION_LIQUIDITY_DIVERGENCE_CONFIRMATION_V1: one bounded Jupiter Free-key read-only PIT campaign using a local process-environment key only; Tokens V2 /recent plus two bulk /tokens/v2/search snapshots 300s apart plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; ICP-EARLY-PUMPFUN-V1 fresh mints only excluding all prior consumed mints; X = ln(R1/R0) from FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO at two prospective search snapshots (mcap != fdv; UNKNOWN never zero); no closed-family threshold, window or quartile reopen; quote-only BUY after the second snapshot and quote-only SELL at H900; one window only; Factory runner unchanged; Discovery, A7, Strategy, Bot, Shadow, alpha, NetReturn and micro-live forbidden.
```

## PRD-lite

- **Owner decision:** `CLOSE_VALUATION_LIQUIDITY_DIVERGENCE_FAMILY`,
  `INVALID_EVIDENCE_REPLAN`, or `EARN_ONE_CONFIRMATORY_FRESH_OOS`.
- **Product outcome:** one cheapest fresh PIT kill/earn of the named
  temporal-change mechanism through existing capture helpers.
- **Named consumer:** GOAL_OWNER promote/close. Positive first sample does
  not authorize SHADOW.
- **Current gap:** closed family tested level, not confirmation change.
- **Success / cheapest falsifier:** sign-only Kendall tau_b of X vs H900 Y
  after the second snapshot; CLOSE if tau_b ≤ 0; INVALID if coverage fails;
  EARN only if tau_b > 0 with frozen coverage.
- **Non-goals:** Discovery, A7, SHADOW, alpha, threshold search, second
  interval, Window B, provider pivot, new platform, wallet/signer/tx,
  micro-live.
- **Evidence budget:** one window; call cap 60; cash $0.
- **Replan trigger:** Factory runner change required; closed-family rule
  reopen; second window; live read without the exact phrase.

## SSD-lite

- **Baseline truth:** `origin/main` `3ba94251a4fbc7c2bd4093b1109947dedae10166`.
- **Design:** ADOPT `bind_primary_x`, Tokens V2 recent/search, quote-only
  H900 helpers, ICP-EARLY-PUMPFUN-V1. WRAP two-snapshot wait + `ln(R1/R0)`
  + sign-only score. FORK nothing in Factory Python. BUILD only the
  experiment projector + CLI.
- **Invariants:** R0 age ∈ [300, 600); R1 must remain < 900; confirmation
  wait 300s; fdv forbidden; UNKNOWN ≠ 0; `factory/runner.py` hash unchanged;
  no `run_campaign` black-box reuse.
- **Y:** quoted sell-out / notional − 1 after BUY at the second snapshot.
- **Validation:** zero-network tests before any credential read; mocked
  two-search campaign; runner SHA pin; isolated critics after delivery.
- **Rollback:** revert branch; consumed market observations stay historical.

## Decision capsule

- `DECISION_DELTA`: test temporal liquidity/mcap change, not absolute level.
- `UNCERTAINTY_REMOVED`: whether ln(R1/R0) over 300s has directional H900
  signal on fresh EARLY ICP mints.
- `CAPABILITY_OR_EVIDENCE`: WRAP composition plus one scientific terminal,
  or offline-ready stop at the exact phrase gate.
- `STOP`: exact owner phrase before live capture; PR + exact-head CI before
  merge phrase.
- `NEXT`: if EARN, owner decides whether a later confirmatory OOS is worth
  a new contract. Not SHADOW.
- `REPLAN_TRIGGER`: runner change; closed-family reopen; second window.

## Definition of Done

1. Exact contract + policy + projector + CLI + tests landed.
2. Zero-network tests prove: ln(R1/R0); level-stable mint X=0; UNKNOWN≠0;
   fdv rejected; R0 age gate; wrong phrase → 0 credential reads; runner SHA
   pin; `run_campaign` not invoked.
3. Live capture only after the exact owner phrase. Same atom, no prep atom.
4. Scientific terminal is one of the three named terminals, or delivery
   stops at the phrase gate with offline composition PASS.
5. No `factory/runner.py` diff. No Discovery/A7. No wallet/signer/execute.
6. Delivery trio + owner readout bound before merge context.
