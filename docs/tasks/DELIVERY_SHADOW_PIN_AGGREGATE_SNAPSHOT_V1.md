---
task_id: DELIVERY_SHADOW_PIN_AGGREGATE_SNAPSHOT_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-10-03'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER, ARCHITECTURE_CRITIC]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 72330ae1727631cb5c0dacc0ab6bc6f65fee2b80
  expected_upstream: origin/main
  expected_upstream_oid: 72330ae1727631cb5c0dacc0ab6bc6f65fee2b80
  expected_branch: codex/delivery-shadow-pin-aggregate-snapshot-v1
  dirty_mode: FORBIDDEN
objective: >-
  Make historical evidence pins to harness-owned aggregate/derived paths
  (Catalog manifest, asset registries, generated navigation outputs)
  snapshot-only in preflight-push so an ordinary Catalog change no longer
  forces a rewrite of docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json.
  Pins to every other path keep today's SHADOW_PIN_DRIFT DENY. Add the
  forward-only evidence policy to the protocol and skill. No product change.
managed_write_set:
  - docs/tasks/DELIVERY_SHADOW_PIN_AGGREGATE_SNAPSHOT_V1.md
  - scripts/delivery_harness.py
  - tests/test_preflight_shadow_pin_drift.py
  - docs/agent/DELIVERY_HARNESS_PROTOCOL.md
  - .agents/skills/delivery-harness/SKILL.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/**
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/control/delivery_shadow_pin_aggregate_snapshot_v1/**
  - docs/evidence/control/delivery_harness_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - ANOTHER_GATE_FORCES_OWNER_PULSE_REWRITE_WITH_DIFFERENT_ROOT_CAUSE
  - HISTORICAL_EVIDENCE_REWRITE_OR_DELETION
  - HARNESS_CONTROL_WRITE_PREFIX_WIDENING
  - MERGE_READINESS_BIND_EVIDENCE_OR_GUARDED_MERGE_CHANGE
  - PRODUCT_FORGE_RESEARCHSTORE_PROVIDER_OR_C5_ACTION
  - MERGE_BEFORE_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: []
  l2_roles: [DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/control/delivery_shadow_pin_aggregate_snapshot_v1/completion.json
      - docs/evidence/control/delivery_shadow_pin_aggregate_snapshot_v1/independent_review.json
      - docs/evidence/control/delivery_shadow_pin_aggregate_snapshot_v1/factory_fit.json
    HISTORICAL_CONTEXT: []
---

SPEC_ROUTE: NONE (owner contract is the spec).
DECISION_DELTA: aggregate pins in historical evidence stop taxing every Catalog PR.
UNCERTAINTY_REMOVED: whether an aggregate-only exemption loses any real drift guard.
CAPABILITY_OR_EVIDENCE: one shared exempt set read from `harness_sync` constants, 4 unit tests, real-tree dry run.
STOP: exact-head CI and merge-readiness PASS; await exact owner phrase.
NEXT: separately authorized guarded merge.

TASK_OUTCOME_BRIEF:
- OWNER_DECISION: none new; removes a recurring rewrite tax.
- NAMED_CONSUMER: every Catalog-touching PR through preflight-push.
- CHEAPEST_FALSIFIER: real-tree dry run, core.yaml before/after the fix.
- NON_GOALS: no merge-readiness/bind-evidence/guarded-merge change, no prefix widening,
  no evidence deletion/rewrite, no FROZEN_SEMANTICS_EVIDENCE_FILES change.
- REPLAN_TRIGGER: another gate forces the owner_pulse rewrite for a different root cause.

FACTORY_ALIGNMENT_PREFLIGHT: START_AS_WRITTEN.
PRODUCT_HORIZON: NOW=this control atom.
CAPABILITY_RADAR_NOW: NONE.

## Policy

Aggregate set = `harness_sync.MANIFEST_RELATIVE` + `ASSET_REGISTRIES` + `NAV_OUTPUTS`
(`harness_owned_aggregate_paths()`), the guard that remains is `harness_sync.check_drift`.
Evidence policy (forward-only) is recorded in `docs/agent/DELIVERY_HARNESS_PROTOCOL.md`.
