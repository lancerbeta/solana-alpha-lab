---
task_id: LIVE_COHORT_MEMORY_BOUNDED_PUBLICATION_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-11'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 77de3bacb09ee32c97cca95582cda760642b5c1b
  expected_upstream: origin/main
  expected_upstream_oid: 77de3bacb09ee32c97cca95582cda760642b5c1b
  expected_branch: cursor/live-cohort-memory-bounded-publication-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair SEM-LIVE-EVIDENCE-TO-FORGE so recurring mature-cohort
  build-source, readiness, seal, and verify is memory-bounded and can coexist
  with the always-on Factory collector on the current host class, without
  changing scientific semantics or running live publication.
managed_write_set:
- docs/tasks/LIVE_COHORT_MEMORY_BOUNDED_PUBLICATION_V1.md
- src/solana_alpha_lab/factory/live_cohort_source_bundle.py
- src/solana_alpha_lab/factory/live_cohort_discovery_release.py
- src/solana_alpha_lab/factory/live_cohort_to_forge.py
- src/solana_alpha_lab/factory/members_snapshot_delta.py
- scripts/discovery_evidence_release.py
- tests/test_live_cohort_memory_bounded_publication_v1.py
- tests/test_live_cohort_to_forge_operational_closure_v1.py
- tests/test_live_evidence_consumer_truth_closure.py
- tests/test_live_cohort_discovery_release_series.py
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/evidence/live_cohort_memory_bounded_publication/a1_delivery_completion_evidence_v1.json
- docs/evidence/live_cohort_memory_bounded_publication/a1_delivery_independent_review_v1.json
- docs/evidence/live_cohort_memory_bounded_publication/a1_delivery_factory_fit_v1.json
- docs/reports/live_cohort_memory_bounded_publication/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/FACTORY_SEMANTIC_MAP.md
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
external_caps:
  network: true
  credentials: false
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_VPS_WRITE_DEPLOY_SEAL_IMPORT
- STOP_HYPOTHESIS_FORGE_SLASH
- STOP_RDP_REWRITE_OR_SQLITE_MUTATION
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- OWNER_DECISION_REQUIRED
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
    - docs/evidence/live_cohort_memory_bounded_publication/a1_delivery_completion_evidence_v1.json
    - docs/evidence/live_cohort_memory_bounded_publication/a1_delivery_independent_review_v1.json
    - docs/evidence/live_cohort_memory_bounded_publication/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# LIVE_COHORT_MEMORY_BOUNDED_PUBLICATION_V1

## SPEC_ROUTE

`NONE` — repair existing SEM-LIVE-EVIDENCE-TO-FORGE publication memory lifetime.

## Decision capsule

- **DECISION_DELTA:** Production live source is a small manifest plus parquet
  partitions; extraction/readiness/seal/verify stream or spill; CLI isolates
  `build-live-source` so resource exhaustion cannot take down Factory.
- **UNCERTAINTY_REMOVED:** The proven C1 OOM is a resource-safety failure of
  monolithic JSON and N×census MEMBER_BATCH loads, not a RAM-increase permit.
- **CAPABILITY_OR_EVIDENCE:** Recurring mature cohort → build → readiness →
  seal → verify stays memory-bounded on the current 5.8 GiB host class.
- **STOP:** Exact merge gate. No live VPS source/seal/import, no deploy.
- **NEXT:** Post-merge deploy of merged SHA, then bounded C1 publication.

SEMANTIC_PREMISE_HIGH_RISK: true

## Non-goals

No live VPS write, no provider calls, no collector pause, no RDP rewrite,
no swap/cgroup/host mutation, no `/hypothesis-forge`, no NORMALIZED_TRAJECTORY.
