---
task_id: FACTORY_ROUTINE_PUBLICATION_WALLCLOCK_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-12'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 90c1c181d4461b7c81e7a79f6e1eb2cd4b1619f0
  expected_upstream: origin/main
  expected_upstream_oid: 90c1c181d4461b7c81e7a79f6e1eb2cd4b1619f0
  expected_branch: cursor/factory-routine-publication-wallclock-v1
  dirty_mode: ALLOW_REPORTED
objective: Profile and optimize the routine SNAPSHOT_PLUS_DELTA publication hot
  path for ~205k-member populations so post-provider wall time fits a commissioning
  envelope without weakening scientific identity, lossless reconstruction,
  crash/retry, memory bounds, or routine fail-closed behavior; add minimal stage
  timing telemetry.
managed_write_set:
- docs/tasks/FACTORY_ROUTINE_PUBLICATION_WALLCLOCK_V1.md
- src/solana_alpha_lab/factory/members_snapshot_delta.py
- src/solana_alpha_lab/factory/hot90_archive.py
- src/solana_alpha_lab/factory/hot90_closed_day_loop.py
- tests/test_factory_routine_publication_wallclock_v1.py
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/evidence/factory_routine_publication_wallclock/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_routine_publication_wallclock/a1_delivery_independent_review_v1.json
- docs/evidence/factory_routine_publication_wallclock/a1_delivery_factory_fit_v1.json
- docs/evidence/factory_routine_publication_wallclock/baseline_stage_profile_v1.json
- docs/evidence/factory_routine_publication_wallclock/candidate_stage_profile_v1.json
- docs/evidence/factory_routine_publication_wallclock/full_path_benchmark_v1.json
- scripts/bench_routine_publication_full_path.py
- docs/reports/factory_routine_publication_wallclock/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
external_caps:
  network: true
  credentials: false
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_CURRENT_GIT_INVALIDATES_TASK
- STOP_ROOT_CAUSE_NOT_CONFIRMED
- STOP_SCHEMA_OR_TRUTH_BOUNDARY_CHANGE_REQUIRED
- STOP_PERFORMANCE_ENVELOPE_NOT_SOLVED
- STOP_CPU_MEMORY_TRADEOFF_REQUIRES_OWNER_DECISION
- STOP_VPS_DEPLOY_TICK_C1
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- WALLET_BUILD_EXECUTE_TRANSACTION
- OWNER_DECISION_REQUIRED
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
    - docs/evidence/factory_routine_publication_wallclock/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_routine_publication_wallclock/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_routine_publication_wallclock/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_ROUTINE_PUBLICATION_WALLCLOCK_V1

## SPEC_ROUTE

`BOTH` — runtime hot-path change plus scientific lineage / crash-recovery
contracts for SNAPSHOT_PLUS_DELTA routine publication.

## Decision capsule

- **DECISION_DELTA:** From opaque >90s post-provider CPU to a measured,
  history-bounded routine publication path with stage telemetry, or a typed
  stop proving an owner-level envelope decision is required.
- **UNCERTAINTY_REMOVED:** Which full-population / history-depth operations
  dominate publish wall time and whether they can be removed/reused without
  changing scientific identity.
- **CAPABILITY_OR_EVIDENCE:** Optimized routine publish path + offline 205k
  stage profile + history-depth proof + independent reviews.
- **STOP:** Exact merge-readiness only. No merge, deploy, VPS, tick, or C1.
- **NEXT:** Separate OPERATE commissioning atom after merge.

SEMANTIC_PREMISE_HIGH_RISK: true

## Runtime safety precondition

`RUNTIME_SAFETY_PRECONDITION=NO_VPS_NO_TICK`

## Non-goals

No merge/deploy/VPS/timer/tick/C1/STARTED cleanup/memory-fence increase/swap/
new dependencies/public schema expansion/unrelated refactor.
