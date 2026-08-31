---
task_id: PATHRISK_LIVE_RECENT_HTTP_CLASS_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-31'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ec76045ab487f7408ee876a3dbe0db0fc791a19f
  expected_upstream: origin/main
  expected_upstream_oid: ec76045ab487f7408ee876a3dbe0db0fc791a19f
  expected_branch: cursor/pathrisk-live-recent-http-class-v1
  dirty_mode: ALLOW_REPORTED
objective: "Persist exact Jupiter HTTP status/class through opener, primitive, call store and PathRisk operational terminals. Zero provider calls and zero real credential reads in this PR. Not a second PathRisk window."
managed_write_set:
- docs/tasks/PATHRISK_LIVE_RECENT_HTTP_CLASS_V1.md
- configs/early_quote_surface_pathrisk_calibration_v1.yaml
- src/solana_alpha_lab/factory/observation_primitives.py
- configs/observation_primitive_registry_v1.yaml
- src/solana_alpha_lab/factory/observation_schedule_runtime.py
- src/solana_alpha_lab/factory/pathrisk_live.py
- scripts/early_quote_surface_pathrisk_calibration.py
- tests/test_observation_primitives.py
- tests/test_pathrisk_recent_http_class.py
- docs/evidence/pathrisk_live_recent_http_class/a1_delivery_completion_evidence_v1.json
- docs/evidence/pathrisk_live_recent_http_class/a1_delivery_independent_review_v1.json
- docs/evidence/pathrisk_live_recent_http_class/a1_delivery_factory_fit_v1.json
- docs/reports/pathrisk_live_recent_http_class/a1_owner_readout_v1.md
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
- SECOND_LIVE_WINDOW
- REOPEN_ACT_PATHRISK_LIVE_001
- RETRY_OR_FALLBACK
- NEW_PROVIDER_OR_ENDPOINT
- NEW_HTTP_ARCHITECTURE
- HTTP_CLASS_REQUIRES_BREAKING_STORE_MIGRATION
- SECRET_REDACTION_NOT_PROVEN
- EXISTING_CALL_IDEMPOTENCY_WOULD_BREAK
- NEW_ESTIMAND
- WALLET_SIGNER_TX
context_requirements:
  catalog_asset_ids:
  - CTRL-PATHRISK-LIVE-RECENT-HTTP-CLASS-001
  - CTRL-PATHRISK-REAL-WALLCLOCK-LIVE-EXECUTION-001
  - MODULE-PATHRISK-LIVE-001
  - SCRIPT-EARLY-QUOTE-SURFACE-PATHRISK-CALIBRATION-001
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
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# PATHRISK_LIVE_RECENT_HTTP_CLASS_V1

`ENTRY_VERDICT=START_WITH_PATCH`

`SPEC_ROUTE=PRD_LITE`

`DELIVERY_MODE=VERTICAL_CAPABILITY_LOOP`

`ROUTE=DIRECT_CURSOR_DELIVERY`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## Decision capsule

- `DECISION_DELTA:` Exact HTTP status and canonical `http_class` survive opener → `execute_primitive` → `_oneshot` store payload → COMPLETED reuse → PathRisk operational terminals. Transport probe is a one-GET diagnostic with its own phrase, not a PathRisk window.
- `UNCERTAINTY_REMOVED:` `R0_SINGLE_SNAPSHOT_BINDING_NOT_PROVEN` no longer masks 401/403/429/5xx/timeout/transport on `/recent`. Historical ACT-PATHRISK-LIVE-001 stays `HTTP_ERROR` / `UNKNOWN_NOT_RECORDED_AT_TIME`.
- `CAPABILITY_OR_EVIDENCE:` Zero-network T1–T18 plus `transport-probe-recent`. Production probe phrase is printed, not executed.
- `STOP:` exact merge gate. No provider call in this PR.
- `NEXT:` owner may authorize the probe phrase after merge; replacement scientific window is a later contract.
- `CHEAPEST_FALSIFIER:` 401 recent still surfaces as `R0_SINGLE_SNAPSHOT_BINDING_NOT_PROVEN`, or COMPLETED reuse opens the network again.
- `REPLAN_TRIGGER:` store schema migration, new HTTP stack/provider, secret leak, idempotency break.
