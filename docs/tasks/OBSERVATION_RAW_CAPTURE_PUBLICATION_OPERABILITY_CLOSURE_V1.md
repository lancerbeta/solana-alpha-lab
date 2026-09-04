---
task_id: OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_CLOSURE_V1
task_version: "1.0"
status: READY
as_of: "2026-09-04"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 55206cc414fb2499df54221f475a84fd4cb849de
  expected_upstream: origin/main
  expected_upstream_oid: 55206cc414fb2499df54221f475a84fd4cb849de
  expected_branch: cursor/observation-raw-capture-publication-operability-closure-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Close the ObservationSchedule publication-job tick hotspot as one vertical
  owner-path: bounded raw capture stays unchanged, scientific RDP stays
  immutable, recovery journal no longer re-parses historical completed payloads
  on every tick, crash/replay stays identity-preserving, and live deploy/
  migration/smoke remain a separate owner gate.

managed_write_set:
  - docs/tasks/OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_CLOSURE_V1.md
  - src/solana_alpha_lab/factory/observation_publication_jobs.py
  - src/solana_alpha_lab/factory/observation_panel_publisher.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - scripts/observation_publication_jobs.py
  - tests/test_observation_publication_job_lifecycle_v1.py
  - tests/test_observation_panel_publisher.py
  - tests/test_collector_operability_retention_and_owner_pulse.py
  - configs/ci_test_shards_v1.json
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/observation_raw_capture_publication_operability_closure_v1/a1_owner_readout_v1.md
  - docs/evidence/observation_raw_capture_publication_operability_closure_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/observation_raw_capture_publication_operability_closure_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/observation_raw_capture_publication_operability_closure_v1/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - EQUIVALENT_CAPABILITY_ALREADY_EXISTS
  - PROVIDER_ROUTE_OR_CREDENTIAL_CHANGE_REQUIRED
  - RETRY_OR_FALLBACK_AUTHORITY_WIDENING
  - SCIENTIFIC_ESTIMAND_OR_SAMPLING_CHANGE_REQUIRED
  - PACKAGE_ADOPTION_REQUIRED
  - DEPLOYMENT_OR_VPS_ACTION_REQUIRED
  - LEGACY_FULL_DELETION_IN_THIS_ATOM
  - STARTED_CLEANUP_OR_BACKFILL
  - NEW_SERVICE_DAEMON_OR_PLATFORM
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - SECOND_ARCHITECTURE_PIVOT
  - REPEATED_MATERIAL_BLOCKER

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
    - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE:
      - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/observation_panel_publisher.py
      - src/solana_alpha_lab/factory/observation_scheduler.py
    DELIVERY_EVIDENCE:
      - docs/evidence/observation_raw_capture_publication_operability_closure_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/observation_raw_capture_publication_operability_closure_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/observation_raw_capture_publication_operability_closure_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_CLOSURE_V1

## Decision delta

Can ObservationSchedule keep writing scientific RDP while stopping the
proven tick hotspot of `repair_open_publication_jobs` `json.loads` over
historical publication job payloads (~10.56 GiB), without deleting scientific
history or mixing irreversible `legacy_full` compaction into this atom?

## Binding

- Base: `55206cc414fb2499df54221f475a84fd4cb849de`
- Route: `DIRECT_CURSOR_DELIVERY`
- SPEC_ROUTE: `BOTH`
- Live VPS deploy, migration APPLY, and live smoke remain a separate owner gate

## Owner decision

Separate `open/`, `completed/`, and `legacy_full/` job journals; compact
proven terminals; keep Forge/history on immutable RDP; close the
marker→completion crash window with idempotent COMPLETE semantics.

## Named consumer

Factory ObservationSchedule tick / owner pulse: routine repair cost is
`O(open jobs)`, not `O(historical completed bytes)`.

## Cheapest falsifier

Deterministic fixture: hundreds of completed receipts plus a huge sentinel
completed body must not be opened by routine repair; one genuine open job
crash-repairs; D+1 replay keeps dataset identity; Forge/RDP consumer matches
after compacting the job.

## Terminal (this repository atom)

`OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_SOFTWARE_PASS`

Live terminal `OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_LIVE_PASS` is
out of this atom.

## Non-claims

No VPS deploy, no live provider calls, no Jupiter redesign, no HTTP timeout
work, no retry/fallback, no STARTED cleanup, no `legacy_full` deletion, no
byte-identical HTTP archive, no new campaign.

## Replan trigger

Repeated blocker, preparatory-only output, cheapest falsifier impossible,
second storage-platform pivot, or evidence/time budget breach.
