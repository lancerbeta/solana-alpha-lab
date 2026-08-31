---
task_id: PATHRISK_LIVE_WINDOW_EXECUTION_GLUE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-31'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 98c323887af2a8f2fe9a5511abe62c52970a81f0
  expected_upstream: origin/main
  expected_upstream_oid: 98c323887af2a8f2fe9a5511abe62c52970a81f0
  expected_branch: cursor/pathrisk-live-window-execution-glue-v1
  dirty_mode: ALLOW_REPORTED
objective: "Repair the accepted PathRisk live execution path: one /recent, one bulk R0 search, consumed-mint exclusion, floor-before-quotes, hard cap 26, live readout. Zero provider calls in this PR."
managed_write_set:
- docs/tasks/PATHRISK_LIVE_WINDOW_EXECUTION_GLUE_V1.md
- configs/early_quote_surface_pathrisk_calibration_v1.yaml
- catalog/schemas/observation_schedule_v1.schema.json
- src/solana_alpha_lab/factory/pathrisk_calibration.py
- src/solana_alpha_lab/factory/pathrisk_live.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/observation_schedule_compiler.py
- scripts/early_quote_surface_pathrisk_calibration.py
- tests/fixtures/observation_schedule/pathrisk_live_window.yaml
- tests/test_pathrisk_live_window.py
- tests/test_pathrisk_calibration.py
- docs/evidence/pathrisk_live_window_execution_glue/a1_delivery_completion_evidence_v1.json
- docs/evidence/pathrisk_live_window_execution_glue/a1_delivery_independent_review_v1.json
- docs/evidence/pathrisk_live_window_execution_glue/a1_delivery_factory_fit_v1.json
- docs/reports/pathrisk_live_window_execution_glue/a1_owner_readout_v1.md
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
- NEW_PROVIDER_OR_ENDPOINT
- NEW_SCHEDULER_ARCHITECTURE
- NEW_ESTIMAND
- THIRD_NOTIONAL
- SECOND_LIVE_WINDOW
- HOLDER_TAKER_FAMILY_REOPEN
- ALPHA_OR_NETRETURN_CLAIM
- CREDENTIAL_VALUE_READ
- WALLET_SIGNER_TX
context_requirements:
  catalog_asset_ids:
  - CTRL-EARLY-QUOTE-SURFACE-PATHRISK-CALIBRATION-001
  - CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010
  - MODULE-PATHRISK-CALIBRATION-001
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
    - docs/evidence/pathrisk_live_window_execution_glue/a1_delivery_completion_evidence_v1.json
    - docs/evidence/pathrisk_live_window_execution_glue/a1_delivery_independent_review_v1.json
    - docs/evidence/pathrisk_live_window_execution_glue/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PATHRISK_LIVE_WINDOW_EXECUTION_GLUE_V1

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=PRD_LITE`

`DELIVERY_MODE=VERTICAL_CAPABILITY_LOOP`

`ROUTE=DIRECT_CURSOR_DELIVERY`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## Decision capsule

- `DECISION_DELTA:` One bounded live PathRisk window uses exactly one `/recent` plus one bulk R0 `/search`, disables recurring source_poll, excludes consumed mints, floors before quotes, and hard-caps 26 calls. Readout is live-wired.
- `UNCERTAINTY_REMOVED:` The C-gap (policy inject vs executable `/recent` poll) is closed with one R0 snapshot identity.
- `CAPABILITY_OR_EVIDENCE:` Zero-network fixture E2E of the live operator. No provider calls in this PR.
- `STOP:` exact merge gate. No live capture.
- `NEXT:` post-merge read-only PATHRISK_LIVE_PREEXECUTION_GATE_V1, then owner phrase.
- `CHEAPEST_FALSIFIER:` a second `/search` in X300, recurring `/recent`, or a consumed mint in the selected four.
- `REPLAN_TRIGGER:` new scheduler architecture, new provider/endpoint, new estimand, exclusion not provable.

## Non-goals

New estimand, provider, endpoint, population, third notional, second window, alpha/NetReturn, Hypothesis Forge during capture, `.env` reads.
