---
task_id: PATHRISK_SUCCESSOR_WINDOW_IDENTITY_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-08-31'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: af8bc7d41ec43055dc4cdb3ac464ef7fdd28e4e0
  expected_upstream: origin/main
  expected_upstream_oid: af8bc7d41ec43055dc4cdb3ac464ef7fdd28e4e0
  expected_branch: cursor/pathrisk-successor-window-identity-v1
  dirty_mode: ALLOW_REPORTED
objective: "Replace per-window Git PathRisk identity with a stable successor policy so a BELOW_FLOOR window can be followed by ACT-(N+1) via exact owner phrase and existing runtime, without a Git identity PR. Zero provider calls and zero real credential reads in this PR."
managed_write_set:
- docs/tasks/PATHRISK_SUCCESSOR_WINDOW_IDENTITY_V1.md
- configs/early_quote_surface_pathrisk_calibration_v1.yaml
- src/solana_alpha_lab/factory/pathrisk_live.py
- src/solana_alpha_lab/factory/pathrisk_calibration.py
- scripts/early_quote_surface_pathrisk_calibration.py
- tests/test_pathrisk_successor_window_identity.py
- tests/pathrisk_live_testkit.py
- tests/test_pathrisk_fresh_activation_identity.py
- tests/test_pathrisk_live_window.py
- tests/test_pathrisk_wallclock_live.py
- tests/test_pathrisk_recent_http_class.py
- tests/test_pathrisk_calibration.py
- docs/evidence/pathrisk_successor_window_identity/a1_delivery_completion_evidence_v1.json
- docs/evidence/pathrisk_successor_window_identity/a1_delivery_independent_review_v1.json
- docs/evidence/pathrisk_successor_window_identity/a1_delivery_factory_fit_v1.json
- docs/reports/pathrisk_successor_window_identity/a1_owner_readout_v1.md
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
- REWRITE_ACT_PATHRISK_LIVE_001_OR_002
- SUCCESSOR_AFTER_INFORMATIVE_OR_COMPLETE
- YAML_IDENTITY_REQUIRED_FOR_ACT_004
- SCIENCE_SEMANTICS_CHANGE
- GENERAL_MULTI_WINDOW_FRAMEWORK
- SUPPLY_WATCHER_OR_SCHEDULER
- RETRY_OR_FALLBACK
- NEW_PROVIDER_OR_ENDPOINT
- SECRET_REDACTION_NOT_PROVEN
- RDP_PUBLICATION_IN_THIS_PR
- EVIDENCE_EPOCH_MUTATION_IN_THIS_PR
- WALLET_SIGNER_TX
context_requirements:
  catalog_asset_ids:
  - CTRL-PATHRISK-SUCCESSOR-WINDOW-IDENTITY-001
  - CTRL-PATHRISK-FRESH-ACTIVATION-IDENTITY-001
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
    - docs/evidence/pathrisk_successor_window_identity/a1_delivery_completion_evidence_v1.json
    - docs/evidence/pathrisk_successor_window_identity/a1_delivery_independent_review_v1.json
    - docs/evidence/pathrisk_successor_window_identity/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PATHRISK_SUCCESSOR_WINDOW_IDENTITY_V1

`ENTRY_VERDICT=START_AS_WRITTEN`

`SPEC_ROUTE=PRD_LITE`

`DELIVERY_MODE=VERTICAL_CAPABILITY_LOOP`

`ROUTE=DIRECT_CURSOR_DELIVERY`

`MODEL_EFFORT_RECOMMENDATION=SOL_XHIGH`

## Decision capsule

- `DECISION_DELTA:` Git PathRisk identity becomes a stable successor policy. Runtime binds `ACT-PATHRISK-LIVE-(N+1)` from explicit CLI identity plus a deterministically rendered owner phrase after a `CALIBRATION_ELIGIBLE_BELOW_FLOOR` predecessor. ACT-001 and ACT-002 stay immutable historical state.
- `UNCERTAINTY_REMOVED:` A normal lack-of-market-supply terminal no longer requires a Git/config PR before the next scientifically clean PathRisk window.
- `CAPABILITY_OR_EVIDENCE:` Zero-network T1–T35 plus ACT-003 then ACT-004 without Git/config byte changes.
- `STOP:` exact merge gate. No provider call, no live ACT-003, no Forge.
- `NEXT:` after merge, zero-network `successor-preflight` then owner phrase for ACT-003.
- `CHEAPEST_FALSIFIER:` ACT-004 still requires YAML identity, or INFORMATIVE/COMPLETE predecessor grants ordinary successor, or ACT-003 phrase authorizes ACT-004.
- `REPLAN_TRIGGER:` need successor-after-COMPLETE, supply watcher, science change, general multi-window platform.

## Named consumer

Owner/executor after merge, against the already-authorized local ACT-002 `CALIBRATION_ELIGIBLE_BELOW_FLOOR` journal (gitignored Factory `data_root`, not Git):

1. zero-network `successor-preflight --data-root <factory data_root>`
2. exact rendered owner phrase for `ACT-PATHRISK-LIVE-003`
3. one ACT-003 live window
4. Git changes = 0, PRs = 0, core code changes = 0

If ACT-003 is also BELOW_FLOOR, the same runtime emits ACT-004 without a Git identity edit.

ACT-001 and ACT-002 remain historical immutable local state. This PR does not rewrite their bytes and does not run live ACT-003.
