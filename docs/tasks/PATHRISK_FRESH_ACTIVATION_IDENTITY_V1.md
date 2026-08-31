---
task_id: PATHRISK_FRESH_ACTIVATION_IDENTITY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-31'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 10db0324b02d1720bc5167b89f5991d4390c857d
  expected_upstream: origin/main
  expected_upstream_oid: 10db0324b02d1720bc5167b89f5991d4390c857d
  expected_branch: cursor/pathrisk-fresh-activation-identity-v1
  dirty_mode: ALLOW_REPORTED
objective: "Give a new explicitly-authorized prospective PathRisk window a fresh immutable identity after the pre-evidence operational death of ACT-PATHRISK-LIVE-001, without rewriting that predecessor or changing science. Zero provider calls and zero real credential reads in this PR."
managed_write_set:
- docs/tasks/PATHRISK_FRESH_ACTIVATION_IDENTITY_V1.md
- configs/early_quote_surface_pathrisk_calibration_v1.yaml
- src/solana_alpha_lab/factory/pathrisk_live.py
- src/solana_alpha_lab/factory/observation_panel_publisher.py
- tests/test_pathrisk_fresh_activation_identity.py
- tests/test_pathrisk_live_window.py
- tests/test_pathrisk_wallclock_live.py
- docs/evidence/pathrisk_fresh_activation_identity/a1_delivery_completion_evidence_v1.json
- docs/evidence/pathrisk_fresh_activation_identity/a1_delivery_independent_review_v1.json
- docs/evidence/pathrisk_fresh_activation_identity/a1_delivery_factory_fit_v1.json
- docs/reports/pathrisk_fresh_activation_identity/a1_owner_readout_v1.md
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
- REWRITE_OR_RESUME_ACT_PATHRISK_LIVE_001
- SECOND_REPLACEMENT_WINDOW
- SCIENCE_SEMANTICS_CHANGE
- ARBITRARY_CALLER_ACTIVATION_ID
- GENERAL_MULTI_WINDOW_FRAMEWORK
- RETRY_OR_FALLBACK
- NEW_PROVIDER_OR_ENDPOINT
- SECRET_REDACTION_NOT_PROVEN
- RDP_PUBLICATION_IN_THIS_PR
- EVIDENCE_EPOCH_MUTATION_IN_THIS_PR
- WALLET_SIGNER_TX
context_requirements:
  catalog_asset_ids:
  - CTRL-PATHRISK-FRESH-ACTIVATION-IDENTITY-001
  - CTRL-PATHRISK-REAL-WALLCLOCK-LIVE-EXECUTION-001
  - CTRL-JUPITER-READONLY-TRANSPORT-PARITY-001
  - MODULE-PATHRISK-LIVE-001
  - CONFIG-EARLY-QUOTE-SURFACE-PATHRISK-CALIBRATION-001
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
    - docs/evidence/pathrisk_fresh_activation_identity/a1_delivery_completion_evidence_v1.json
    - docs/evidence/pathrisk_fresh_activation_identity/a1_delivery_independent_review_v1.json
    - docs/evidence/pathrisk_fresh_activation_identity/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PATHRISK_FRESH_ACTIVATION_IDENTITY_V1

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=PRD_LITE`

`DELIVERY_MODE=VERTICAL_CAPABILITY_LOOP`

`ROUTE=DIRECT_CURSOR_DELIVERY`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## Decision capsule

- `DECISION_DELTA:` PathRisk live activation identity moves from a module-global singleton into the canonical live-window contract. This campaign binds `ACT-PATHRISK-LIVE-002` with predecessor `ACT-PATHRISK-LIVE-001` and `PRE_EVIDENCE_OPERATIONAL_FAILURE`. Runtime directories, journals, schedules, bindings, ObservationSchedule activation rows and call accounting are keyed by that contract identity. ACT-001 is not rewritten, resumed or scientifically reinterpreted.
- `UNCERTAINTY_REMOVED:` A dead pre-evidence window can be followed by one explicitly-authorized replacement window without identity collision and without a second science PR after a normal runtime outcome.
- `CAPABILITY_OR_EVIDENCE:` Zero-network T1–T24. New replacement owner phrase is printed, not executed.
- `STOP:` exact merge gate. No provider call, no live-run, no replacement window execution in this PR.
- `NEXT:` after merge, owner may authorize the printed ACT-002 phrase. Do not use the consumed ACT-001 calibration phrase.
- `CHEAPEST_FALSIFIER:` ACT-002 loads ACT-001 journal/state, or tests pass while ACT-001 is selected as current, or COMPLETE ACT-002 can run again.
- `REPLAN_TRIGGER:` need to rewrite ACT-001, science/sample/notional/horizon change, general multi-window framework, provider/credential/live-run in this PR.
