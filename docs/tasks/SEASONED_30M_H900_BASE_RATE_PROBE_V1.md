---
task_id: SEASONED_30M_H900_BASE_RATE_PROBE_V1
task_version: '1.0'
status: READY
as_of: '2026-08-24'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: a818ac7cf59bc4c193657ecc4cd393c9897dad5b
  expected_upstream: origin/main
  expected_upstream_oid: a818ac7cf59bc4c193657ecc4cd393c9897dad5b
  expected_branch: cursor/seasoned-30m-h900-base-rate-probe
  dirty_mode: ALLOW_REPORTED
objective: "Answer whether one fresh ~30-minute seasoned pump.fun decision surface contains enough positive executable H900 mass to justify a later positive-selector search; implement only the minimum reusable seasoning seam plus this immediate consumer."
managed_write_set:
- docs/tasks/SEASONED_30M_H900_BASE_RATE_PROBE_V1.md
- configs/seasoned_30m_h900_base_rate_probe_v1.yaml
- src/solana_alpha_lab/ordinary_recent_organic_pressure_h900_audition.py
- src/solana_alpha_lab/seasoned_30m_h900_base_rate_probe.py
- scripts/run_seasoned_30m_h900_base_rate_probe.py
- tests/test_seasoned_30m_h900_base_rate_probe.py
- tests/test_early_holder_concentration_h900_confirmatory_oos.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- docs/PROJECT_MAP.md
- docs/evidence/seasoned_30m_h900_base_rate_probe/a1_runtime_receipt_v1.json
- docs/evidence/seasoned_30m_h900_base_rate_probe/a1_delivery_completion_evidence_v1.json
- docs/evidence/seasoned_30m_h900_base_rate_probe/a1_delivery_independent_review_v1.json
- docs/evidence/seasoned_30m_h900_base_rate_probe/a1_delivery_factory_fit_v1.json
- docs/reports/seasoned_30m_h900_base_rate_probe/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_JUPITER_BEFORE_PRE_LIVE_HEAD_AND_EXACT_OWNER_PHRASE
- NEW_CAMPAIGN_RUNTIME_OR_GENERIC_SCHEDULER
- FACTORY_RUNNER_CHANGE
- HYPOTHESIS_X_OR_FEATURE_SPLIT
- ICP_EARLY_IDENTITY_MUTATION
- AGE_BAND_OR_LIQUIDITY_RESCUE
- SECOND_WINDOW_OR_ALTERNATE_AGE
- HORIZON_GRID_OR_H300_H600_H1800
- Y_HURDLE_SUBTRACTION_OR_MEU_IMPUTATION
- SECOND_PROVIDER_OR_PAID_PLAN
- STRATEGY_BOT_SHADOW_ALPHA_OR_NETRETURN
- PREPARATORY_ONLY_READY_FOR_LIVE_PR
- AUTOMATIC_NEXT_ATOM
context_requirements:
  catalog_asset_ids:
  - MODULE-ORDINARY-RECENT-ORGANIC-PRESSURE-H900-AUDITION-001
  - CTRL-EARLY-HOLDER-CONCENTRATION-H900-FALSIFIER-001
  - CTRL-EARLY-HOLDER-CONCENTRATION-H900-CONFIRMATORY-OOS-001
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/architecture/intents/ARCH-INTENT-005-factory-v1-operational-readiness-and-owner-experience.md
    DELIVERY_EVIDENCE:
    - docs/evidence/seasoned_30m_h900_base_rate_probe/a1_delivery_completion_evidence_v1.json
    - docs/evidence/seasoned_30m_h900_base_rate_probe/a1_delivery_independent_review_v1.json
    - docs/evidence/seasoned_30m_h900_base_rate_probe/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# SEASONED_30M_H900_BASE_RATE_PROBE_V1

## Entry Gate

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=PRD_LITE`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH` — PIT/statistical base-rate plus a
timing-contract seam. `NEXT_MODEL_EFFORT=ROUTINE_NO_SWITCH` at the exact
owner Jupiter phrase checkpoint.

`ROADMAP_VERDICT=KEEP`

Owner-selected after DESIGN_ONLY reframe. This contract supersedes the
rejected draft `EARLY_SEASONED_POOL_H900_BASE_RATE_PROBE_V1`. Do not start
that draft AS_WRITTEN. Canonical EARLY `300 <= age_seconds < 900` is not
mutated.

## Atom identity

```text
DECISION_DELTA: freeze a task-local ~30m seasoned decision surface and
  ask whether it contains positive executable H900 mass
UNCERTAINTY_REMOVED: whether positive-selector search has a plausible
  opportunity surface on this one fresh ~30m window
CAPABILITY_OR_EVIDENCE: minimum reusable seasoning seam plus one typed
  base-rate terminal from one fresh window
STOP: no Jupiter until PRE_LIVE_HEAD + exact owner phrase; no X search
NEXT: SEASONED_30M_SURFACE_NO_POSITIVE_MASS |
  SEASONED_30M_SURFACE_SHOWS_POSITIVE_MASS |
  SEASONED_30M_SURFACE_INCONCLUSIVE |
  INVALID_EVIDENCE_REPLAN
REPLAN_TRIGGER: seasoning change requires campaign rewrite;
  duplicated /recent-search-sleep-quote-H900 orchestration;
  age/liquidity rescue; second window; preparatory-only PR
```

Named Factory gap: `EARLY_CAMPAIGN_CONFIGURABLE_SEASONING_SEAM`.

Task-local population identity: `SEASONED_PUMPFUN_30M_PROBE_V1`.
Not `ICP-EARLY-PUMPFUN-V1`. Not a new global ICP taxonomy.

## Estimand

Base-rate probe, not ranking and not a causal wait-treatment test.

`POSITIVE_EXECUTABLE_H900` =
H900 terminal `QUOTE_OBSERVED` AND numeric `Y > 0`.

`Y = sell_out_lamports / 10_000_000 - 1` with notional 0.01 SOL,
slippage 100 bps, quote-only BUY at decision, quote-only SELL at H900.
No fill. No NetReturn. `MARKET_EXECUTION_UNAVAILABLE` gets no numeric Y
and is not a success.

Primary metrics: decision_time_eligible, positive_executable_count,
positive_executable_rate, rankable_h900, median_Y among rankable,
MEU count/rate, pre-decision attrition.

Diagnostics cannot rescue the terminal.

## Flow / PIT

`/tokens/v2/recent` → freeze 24 fresh project-eligible pump.fun mints →
exclude all prior consumed research mints → wait until every frozen
candidate can reach >=1800s → one bulk `/tokens/v2/search` → decision-time
eligibility → quote-only BUY → H900=900s after actual BUY → quote-only
SELL → offline base-rate scorer → typed terminal.

Do not source 30m tokens from `/recent` at decision time.

Admissible age envelope: `1800 <= pool_age_at_decision < 3600`.
Owner-facing: "~30-minute seasoned decision surface", not a representative
30–60m market population.

## Factory reuse

Reuse `ordinary_recent_organic_pressure_h900_audition.run_campaign`.
Allowed new production logic only:

1. minimum configurable-seasoning seam (`expected_seasoning_seconds=300`
   by default);
2. tiny neutral seasoned eligibility projector;
3. tiny pure/offline base-rate scorer.

Default behaviour remains 300 seconds. Existing organic-pressure, holder,
and structural-backing consumers stay valid without config changes.

If the seam becomes a broad campaign rewrite: `FACTORY_LEVERAGE_REPLAN`.

## Evidence floors

frozen=24; decision_time_eligible >= 18; rankable_h900 >= 14.
Otherwise `INVALID_EVIDENCE_REPLAN` with class DATA | PROVIDER | RUNTIME |
TRUTH_SEMANTICS. Do not alter age band or liquidity to rescue N.

## Decision rule

Valid evidence and `positive_executable_count == 0` →
`SEASONED_30M_SURFACE_NO_POSITIVE_MASS`.

Valid evidence and (`positive_executable_count >= 3` OR `median_Y > 0`) →
`SEASONED_30M_SURFACE_SHOWS_POSITIVE_MASS`.

Other valid outcomes, including count in {1,2} with median_Y <= 0 →
`SEASONED_30M_SURFACE_INCONCLUSIVE`.

Floors / PIT / provider / truth failure → `INVALID_EVIDENCE_REPLAN`.
No automatic retry.

`PRE_LIVE_READY`, `CONFIGURABLE_SEASONING_IMPLEMENTED`, and
`BASE_RATE_SCORER_READY` are not DONE.

## Delivery order

CHECK → CONTEXT → exact combined contract → narrow implementation →
compatibility / scientific tests → risk-routed reviews → PRE_LIVE_HEAD →
OWNER PROVIDER GATE → one fresh window → typed terminal → FINISH →
complete hash-bound delivery packet → PR / exact-head CI → exact merge
gate → post-merge read-back → STOP.

Do not start Jupiter without the exact frozen owner phrase.
The final PR head presented for merge must already contain the complete
machine-required delivery packet. No preparatory PR.
