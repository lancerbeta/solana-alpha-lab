---
task_id: LIVE_COHORT_TO_FORGE_OPERATIONAL_CLOSURE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-10'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 7ce0b87c9518914af7636a9860d068b6517b0943
  expected_upstream: origin/main
  expected_upstream_oid: 7ce0b87c9518914af7636a9860d068b6517b0943
  expected_branch: cursor/live-cohort-to-forge-operational-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: Operationalize the recurring mature-cohort publication path from
  Observation RDP through verified seal/transport/import to Forge CONTROL
  readiness without Git/PR on normal rolling-deploy and next-cohort-active states.
managed_write_set:
- docs/tasks/LIVE_COHORT_TO_FORGE_OPERATIONAL_CLOSURE_V1.md
- src/solana_alpha_lab/factory/live_cohort_discovery_release.py
- src/solana_alpha_lab/factory/live_cohort_to_forge.py
- scripts/discovery_evidence_release.py
- tests/test_live_cohort_to_forge_operational_closure_v1.py
- tests/test_live_cohort_discovery_release_series.py
- tests/test_live_evidence_consumer_truth_closure.py
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- configs/factory_semantic_operability_v1.yaml
- docs/evidence/live_cohort_to_forge_operational_closure/a1_delivery_completion_evidence_v1.json
- docs/evidence/live_cohort_to_forge_operational_closure/a1_delivery_independent_review_v1.json
- docs/evidence/live_cohort_to_forge_operational_closure/a1_delivery_factory_fit_v1.json
- docs/reports/live_cohort_to_forge_operational_closure/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/FACTORY_SEMANTIC_MAP.md
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
- STOP_VPS_OR_DEPLOY_OR_LIVE_SEAL_IMPORT
- STOP_HYPOTHESIS_FORGE_SLASH
- STOP_RDP_REWRITE_OR_BACKFILL
- STOP_COLLECTOR_PAUSE_RESUME
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
    - docs/evidence/live_cohort_to_forge_operational_closure/a1_delivery_completion_evidence_v1.json
    - docs/evidence/live_cohort_to_forge_operational_closure/a1_delivery_independent_review_v1.json
    - docs/evidence/live_cohort_to_forge_operational_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# LIVE_COHORT_TO_FORGE_OPERATIONAL_CLOSURE_V1

## SPEC_ROUTE

`NONE` — operationalize existing SEM-LIVE-EVIDENCE-TO-FORGE primitives.

## Decision capsule

- **DECISION_DELTA:** Recurring weekly cohort publication is a cohort-scoped
  verified path (source + closure receipt + producer set + transport +
  import + Forge CONTROL readback), not a Git atom and not a singular
  producer SHA.
- **UNCERTAINTY_REMOVED:** Register-time `run_id=null`, rolling deploy, and
  a live next cohort no longer silently fail or false-READY the mature cohort.
- **CAPABILITY_OR_EVIDENCE:** Production-shaped zero-network matrix plus one
  owner command `publish-live-cohort` / `forge-control-ready`.
- **STOP:** Exact merge gate. No VPS deploy, no live seal/import, no
  `/hypothesis-forge`.
- **NEXT:** Post-merge live acceptance of cohort 1 on Factory using the
  new operator path.

## Source identity

Cohort-scoped snapshot path
`live_observation_rebuild/cohort={cohort_id}/source_snapshot.json`.

Bind: `schedule_sha256` + `activation_id` + `cohort_id` + exact window.
Producer: `schedule_producer_git_sha` + sorted
`contributing_producer_git_shas`. Singular `producer_git_sha` only when
the contributing set has exactly one SHA.

## Closure

SQLite/runtime is evidence, not scientific rows. No receipt or open
cohort-1 due/publication → fail closed. Cohort-2 future PENDING is not a
cohort-1 blocker.
