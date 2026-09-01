---
task_id: OBSERVATION_RUNTIME_DEPLOY_SHA_REPAIR_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-01'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 96f32177e9f01b7865647923f5da9a36b3a5bfe1
  expected_upstream: origin/main
  expected_upstream_oid: 96f32177e9f01b7865647923f5da9a36b3a5bfe1
  expected_branch: cursor/observation-runtime-deploy-sha-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair ObservationSchedule producer SHA resolution for sanctioned
  exact-SHA no-.git Factory deploy roots via .factory_deploy_sha fallback, and
  leave canonical collector operator navigation so a future agent can operate
  without reconstructing context from chat.
managed_write_set:
- docs/tasks/OBSERVATION_RUNTIME_DEPLOY_SHA_REPAIR_V1.md
- src/solana_alpha_lab/factory/observation_schedule_runtime.py
- tests/test_observation_runtime_deploy_sha_repair.py
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/operator/FACTORY_REMOTE_HOST.md
- .cursor/rules/50-factory-remote-host.mdc
- docs/evidence/observation_runtime_deploy_sha_repair/a1_delivery_completion_evidence_v1.json
- docs/evidence/observation_runtime_deploy_sha_repair/a1_delivery_independent_review_v1.json
- docs/evidence/observation_runtime_deploy_sha_repair/a1_delivery_factory_fit_v1.json
- docs/reports/observation_runtime_deploy_sha_repair/a1_owner_readout_v1.md
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
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- STOP_VPS_OR_DEPLOY_REQUIRED
- STOP_AUTHORIZE_OR_ACTIVATE
- STOP_SECOND_OPERATOR_TRUTH_PLANE
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- WALLET_BUILD_EXECUTE_TRANSACTION
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/observation_runtime_deploy_sha_repair/a1_delivery_completion_evidence_v1.json
    - docs/evidence/observation_runtime_deploy_sha_repair/a1_delivery_independent_review_v1.json
    - docs/evidence/observation_runtime_deploy_sha_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OBSERVATION_RUNTIME_DEPLOY_SHA_REPAIR_V1

## SPEC_ROUTE

`NONE` — defect already proven on live no-.git deploy; this atom is a bounded
runtime repair plus operator navigation.

## Decision capsule

- **DECISION_DELTA:** Producer identity on exact-SHA Factory roots is
  `.factory_deploy_sha` after explicit config and Git HEAD.
- **UNCERTAINTY_REMOVED:** `PRODUCER_GIT_SHA_UNAVAILABLE` on sanctioned VPS
  layout is a code gap, not an ops mystery.
- **CAPABILITY_OR_EVIDENCE:** Zero-network tests reproduce no-.git + deploy pin;
  collector runbook is Catalog-registered.
- **STOP:** Merge gate. No VPS deploy/activate in this atom.
- **NEXT:** Deploy repaired main → no-live tick smoke → timer enable → campaign
  readiness reclassification.
