---
task_id: EARLY_QUOTE_SURFACE_PATHRISK_CALIBRATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-30'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b5ae41ee7d0507035c8604d4ac8f6856767199d3
  expected_upstream: origin/main
  expected_upstream_oid: b5ae41ee7d0507035c8604d4ac8f6856767199d3
  expected_branch: cursor/early-quote-surface-pathrisk-calibration-v1
  dirty_mode: ALLOW_REPORTED
objective: "Reusable enriched quote observation plus T0 reverse/H900 dual-notional PathRisk calibration capability. Zero provider calls in this PR. Not an alpha hypothesis."
managed_write_set:
- docs/tasks/EARLY_QUOTE_SURFACE_PATHRISK_CALIBRATION_V1.md
- configs/early_quote_surface_pathrisk_calibration_v1.yaml
- configs/observation_primitive_registry_v1.yaml
- src/solana_alpha_lab/factory/quote_surface_projection.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/pathrisk_calibration.py
- scripts/early_quote_surface_pathrisk_calibration.py
- tests/fixtures/observation_schedule/pathrisk_calibration.yaml
- tests/test_quote_surface_projection.py
- tests/test_pathrisk_calibration.py
- tests/test_observation_primitive_registry.py
- docs/evidence/early_quote_surface_pathrisk_calibration/a1_delivery_completion_evidence_v1.json
- docs/evidence/early_quote_surface_pathrisk_calibration/a1_delivery_independent_review_v1.json
- docs/evidence/early_quote_surface_pathrisk_calibration/a1_delivery_factory_fit_v1.json
- docs/reports/early_quote_surface_pathrisk_calibration/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/assets/lifecycle.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_PROVIDER_CALL_IN_THIS_PR
- NEW_PROVIDER_OR_ENDPOINT
- NEW_SCHEDULER_ARCHITECTURE
- NEW_ESTIMAND_BEYOND_PATHRISK_CALIBRATION
- TAKER_BUILD_EXECUTE_WALLET_SIGNER_TRANSACTION
- THIRD_NOTIONAL
- SECOND_LIVE_WINDOW
- NEW_POPULATION
- HOLDER_CONCENTRATION_REOPEN
- HYPOTHESIS_FORGE
- PAPER_STRATEGY_SHADOW
- REALIZED_VWAP_OR_NETRETURN_CLAIM
- H3600_OR_H14400
- NEW_COLLECTOR_PLATFORM_DB_OR_UI
context_requirements:
  catalog_asset_ids:
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  - MODULE-OBSERVATION-PRIMITIVES-001
  - CTRL-DECLARATIVE-OBSERVATION-SCHEDULE-BRIDGE-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - EXTERNAL_ROUTE_KNOWLEDGE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - configs/provider_route_capability_registry_v10.yaml
    ARCHITECTURE_DECISIONS:
    - docs/decisions/ADR-007-declarative-observation-schedule-bridge.md
    DELIVERY_EVIDENCE:
    - docs/evidence/early_quote_surface_pathrisk_calibration/a1_delivery_completion_evidence_v1.json
    - docs/evidence/early_quote_surface_pathrisk_calibration/a1_delivery_independent_review_v1.json
    - docs/evidence/early_quote_surface_pathrisk_calibration/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# EARLY_QUOTE_SURFACE_PATHRISK_CALIBRATION_V1

## Entry Gate

`ENTRY_VERDICT=START_WITH_PATCH`

Reason: `MEASUREMENT_ADEQUACY_PROBE` already returned
`CURRENT_Y_DEGENERATE_NEW_MEASUREMENT_REQUIRED`. Current accepted quote
observation primitives materialize only quote `outAmount` and do not give
enough typed quote-surface information to distinguish static round-trip
friction from H900 path change.

`SPEC_ROUTE=PRD_LITE`

`DELIVERY_MODE=VERTICAL_CAPABILITY_LOOP`

`ROUTE=DIRECT_CURSOR_DELIVERY`

## Product outcome

After merge, one reusable capability can, for a runtime-selected mint and
notional, without a new provider/endpoint or scheduler architecture:

1. T0 BUY SOL → token
2. Immediate dependent T0 reverse token → SOL using the BUY `outAmount`
3. H900 dependent SELL of the same T0 BUY token amount → SOL

Each quote observation stores a typed projection of at least:

`in_amount`, `out_amount`, `price_impact_pct`, `fee_bps`, `platform_fee`,
`router`, `mode`, `route_hop_count`, `route_fee_amounts_present`,
raw-response immutable pointer/hash.

Missing remains typed `ABSENT | NULL | UNKNOWN`, never zero. Full raw
provider response stays in the accepted raw/data zone, never Git.

## Measurement semantics (implemented, not live-run)

### A. Quote-only economic proxy

`QUOTE_NET_PROXY_N = H900_sell_out_SOL / original_SOL_notional - 1`

Continuity with the current Y. Quote-only; not fill, not RealizedVWAP,
not NetReturn.

### B. PathRisk proxy

`QUOTE_PATH_CHANGE_N = H900_sell_out_SOL / T0_reverse_out_SOL - 1`

Change in quote-surface exit value between T0 and H900 after removing the
static T0 round-trip baseline. Not a profitability metric.

### C. Scale response

Keep `QUOTE_PATH_CHANGE_1M` and `QUOTE_PATH_CHANGE_10M` jointly. No score
or threshold search.

## Future live calibration contract (do not run in this PR)

- Population: `ICP-EARLY-PUMPFUN-V1`
- One prospective R0 snapshot
- First 4 fresh eligible mints, deterministic current population order
- Eligible `<4` → `CALIBRATION_ELIGIBLE_BELOW_FLOOR`, quote calls = 0
- Notionals: `10_000_000` and `1_000_000` lamports only
- Terminals: `PATHRISK_SURFACE_INFORMATIVE` |
  `PATHRISK_SURFACE_STILL_DEGENERATE` |
  `CALIBRATION_PARTIAL_INSUFFICIENT_COVERAGE` |
  `CALIBRATION_PROVIDER_OR_SCHEMA_INVALID`
- `PATHRISK_SURFACE_INFORMATIVE` requires at least `3/4` mints with
  complete T0 BUY + T0 reverse + H900 SELL on **both** notionals, exact
  integer recomputation, and non-constant `QUOTE_PATH_CHANGE` among
  complete cells. Surface fee/impact/route fields are diagnostic and do
  not enter this terminal.
- Pre-quote eligible `<4` is `CALIBRATION_ELIGIBLE_BELOW_FLOOR` (quote
  calls = 0), not one of the four post-quote terminals.
- Live window injects one R0 discovery snapshot and does not enable
  source_poll or per-member search; `max_calls: 25` = 1 bulk search + 24
  quotes.

## Pre-merge success

`EARLY_QUOTE_SURFACE_PATHRISK_CALIBRATION_CAPABILITY_READY` with
provider/API calls = 0 and credential reads = 0.

This does **not** mean the measurement surface is informative. That is
decided only by one separately authorized post-merge calibration window.

## Non-goals

Holder-concentration reopen, taker-mix/friction/quote-stay families,
`/hypothesis-forge`, Paper/Strategy/Shadow, fill/taker/`/build`/`/execute`,
wallet/signer/transaction, RealizedVWAP, NetReturn claim, 5+ notional
ladder, H3600/H14400, second provider, new collector/platform/DB/UI.

## Replan triggers

New provider/endpoint, new scheduler architecture, new estimand beyond
declared PathRisk calibration, execution/taker/fill semantics, third
notional, second live window, new population, repair-loop budget breach,
repeated architecture blocker.

## STOP

After exact-head CI, owner merge phrase, guarded merge, exact main
read-back and post-merge CI success: **STOP before live calibration** and
return the exact proposed capture packet to the owner.
