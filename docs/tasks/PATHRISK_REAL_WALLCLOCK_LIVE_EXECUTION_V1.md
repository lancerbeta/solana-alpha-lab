---
task_id: PATHRISK_REAL_WALLCLOCK_LIVE_EXECUTION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-31'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5ccfc2b1dc95f94d6b95a0a2d74925d93482af7b
  expected_upstream: origin/main
  expected_upstream_oid: 5ccfc2b1dc95f94d6b95a0a2d74925d93482af7b
  expected_branch: cursor/pathrisk-real-wallclock-live-execution-v1
  dirty_mode: ALLOW_REPORTED
objective: "Make the accepted one-window PathRisk calibration executable against real Jupiter under wall-clock time. Zero provider calls and zero real credential reads in this PR."
managed_write_set:
- docs/tasks/PATHRISK_REAL_WALLCLOCK_LIVE_EXECUTION_V1.md
- configs/early_quote_surface_pathrisk_calibration_v1.yaml
- src/solana_alpha_lab/factory/pathrisk_live.py
- src/solana_alpha_lab/factory/pathrisk_calibration.py
- scripts/early_quote_surface_pathrisk_calibration.py
- tests/test_pathrisk_live_window.py
- tests/test_pathrisk_wallclock_live.py
- tests/test_pathrisk_calibration.py
- docs/evidence/pathrisk_real_wallclock_live_execution/a1_delivery_completion_evidence_v1.json
- docs/evidence/pathrisk_real_wallclock_live_execution/a1_delivery_independent_review_v1.json
- docs/evidence/pathrisk_real_wallclock_live_execution/a1_delivery_factory_fit_v1.json
- docs/reports/pathrisk_real_wallclock_live_execution/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
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
- REAL_CREDENTIAL_VALUE_READ
- NEW_PROVIDER_OR_ENDPOINT
- NEW_HTTP_ARCHITECTURE
- NEW_ESTIMAND
- NEW_POPULATION
- THIRD_NOTIONAL
- SECOND_LIVE_WINDOW
- FROZEN_CLOCK_IN_PRODUCTION
- WALLET_SIGNER_TX
context_requirements:
  catalog_asset_ids:
  - CTRL-EARLY-QUOTE-SURFACE-PATHRISK-CALIBRATION-001
  - CTRL-PATHRISK-REAL-WALLCLOCK-LIVE-EXECUTION-001
  - MODULE-PATHRISK-LIVE-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  l2_roles:
  - ARCHITECTURE_DECISIONS
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: configs/factory_v1_operational_readiness_v1.yaml
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - configs/provider_route_capability_registry_v10.yaml
    ARCHITECTURE_DECISIONS:
    - docs/decisions/ADR-007-declarative-observation-schedule-bridge.md
    DELIVERY_EVIDENCE:
    - docs/evidence/pathrisk_real_wallclock_live_execution/a1_delivery_completion_evidence_v1.json
    - docs/evidence/pathrisk_real_wallclock_live_execution/a1_delivery_independent_review_v1.json
    - docs/evidence/pathrisk_real_wallclock_live_execution/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PATHRISK_REAL_WALLCLOCK_LIVE_EXECUTION_V1

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=PRD_LITE`

`DELIVERY_MODE=VERTICAL_CAPABILITY_LOOP`

`ROUTE=DIRECT_CURSOR_DELIVERY`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## Decision capsule

- `DECISION_DELTA:` Production PathRisk live uses SystemClock, adopted Jupiter GET opener, `JUPITER_API_KEY` process-env after gates, and a runtime-materialized one-window activation. FrozenClock time-jump is test-only.
- `UNCERTAINTY_REMOVED:` H900 cannot fire before `firstPool.createdAt + 900s`. Git fixture dates 2026-09-01/02 are not live authority.
- `CAPABILITY_OR_EVIDENCE:` Zero-network wall-clock E2E plus production CLI that cannot be confused with fixture mode.
- `STOP:` exact merge gate. No provider call in this PR.
- `NEXT:` post-merge owner live phrase on exact main.
- `CHEAPEST_FALSIFIER:` H900 URL recorded before anchor+900, or production CLI accepting `--fake-provider-fixture`.
- `REPLAN_TRIGGER:` new HTTP stack, new endpoint, prospective band cannot be derived from current schedule, new scheduler architecture.
