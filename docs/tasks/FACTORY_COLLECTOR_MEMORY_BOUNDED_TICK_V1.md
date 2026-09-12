---
task_id: FACTORY_COLLECTOR_MEMORY_BOUNDED_TICK_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-12'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 73b604d3aa24cf4ebe241c660a71872c22dee784
  expected_upstream: origin/main
  expected_upstream_oid: 73b604d3aa24cf4ebe241c660a71872c22dee784
  expected_branch: cursor/factory-collector-memory-bounded-tick-v1
  dirty_mode: ALLOW_REPORTED
objective: Repair the ordinary Factory ObservationSchedule collector tick so
  working memory stays bounded on the 5.8 GiB no-swap host and cannot take down
  SSH/Workbench as the live activation universe grows, without changing scientific
  semantics or mutating production.
managed_write_set:
- docs/tasks/FACTORY_COLLECTOR_MEMORY_BOUNDED_TICK_V1.md
- src/solana_alpha_lab/factory/observation_schedule.py
- src/solana_alpha_lab/factory/observation_schedule_store.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
- src/solana_alpha_lab/factory/observation_panel_coverage.py
- src/solana_alpha_lab/factory/observation_panel_publisher.py
- src/solana_alpha_lab/factory/observation_publication_jobs.py
- src/solana_alpha_lab/factory/members_snapshot_delta.py
- configs/factory_remote_ops/factory-observation-schedule.service
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- tests/test_factory_collector_memory_bounded_tick_v1.py
- tests/test_factory_snapshot_delta_economy_and_signal_repair_v1.py
- tests/test_observation_schedule_remote_ops.py
- tests/test_observation_schedule_commissioning.py
- tests/test_live_cohort_memory_bounded_publication_v1.py
- docs/evidence/factory_collector_memory_bounded_tick/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_collector_memory_bounded_tick/a1_delivery_independent_review_v1.json
- docs/evidence/factory_collector_memory_bounded_tick/a1_delivery_factory_fit_v1.json
- docs/reports/factory_collector_memory_bounded_tick/a1_owner_readout_v1.md
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
- STOP_VPS_WRITE_DEPLOY_PAUSE_KILL
- STOP_C1_RESUME_SEAL_IMPORT
- STOP_HYPOTHESIS_FORGE_SLASH
- STOP_RDP_REWRITE_OR_SQLITE_MUTATION
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- STOP_IDENTITY_PARITY_IMPOSSIBLE
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
    - docs/evidence/factory_collector_memory_bounded_tick/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_collector_memory_bounded_tick/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_collector_memory_bounded_tick/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_COLLECTOR_MEMORY_BOUNDED_TICK_V1

## SPEC_ROUTE

`NONE` — repair existing SEM-LIVE-COLLECTION ordinary tick memory lifetime.

## Decision capsule

- **DECISION_DELTA:** Production `tick --once` must not materialize the full
  activation/due/census as Python/Arrow copies; scoped SQLite, batched
  projection, streaming hashes, bounded SNAPSHOT_PLUS_DELTA writes, compact
  open jobs, and a canonical systemd memory fence.
- **UNCERTAINTY_REMOVED:** The live Factory outage root cause is the ordinary
  collector hot path, not the already-fenced C1 publication worker.
- **CAPABILITY_OR_EVIDENCE:** Ordinary collector tick stays ≤1 GiB MaxRSS at
  ≥150k members with identity/PIT/sampling parity.
- **STOP:** Exact merge gate. No live VPS pause/deploy/C1 resume.
- **NEXT:** Post-merge OPERATE: exact-SHA deploy, unit sync, paused first tick
  with MemoryPeak, then timer, then C1.

SEMANTIC_PREMISE_HIGH_RISK: true

## Runtime safety precondition

`RUNTIME_SAFETY_PRECONDITION=COLLECTOR_SAFETY_PAUSED`

Separate OPERATE atom paused the live collector (`ACT-619AE64E885E995E`,
timer inactive, no tick child) on 2026-09-12. This software atom still does
not pause, resume, deploy, or otherwise mutate the VPS.

## Non-goals

No production deploy/pause/kill, no C1 build/seal/import, no `/hypothesis-forge`,
no swap/resize, no historical RDP rewrite, no timer-cadence workaround.
