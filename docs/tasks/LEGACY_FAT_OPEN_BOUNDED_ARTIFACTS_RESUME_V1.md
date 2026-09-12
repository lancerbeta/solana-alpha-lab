---
task_id: LEGACY_FAT_OPEN_BOUNDED_ARTIFACTS_RESUME_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-12'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: f47755aa4a49cc7981396606e405369d8e02f24f
  expected_upstream: origin/main
  expected_upstream_oid: f47755aa4a49cc7981396606e405369d8e02f24f
  expected_branch: cursor/legacy-fat-open-bounded-artifacts-resume-v1
  dirty_mode: ALLOW_REPORTED
objective: Add a paused-only bounded ARTIFACTS resume for oversized legacy open
  publication jobs that reuses the canonical publisher continuation without
  materializing members[] or weakening routine fail-closed tick behavior.
managed_write_set:
- docs/tasks/LEGACY_FAT_OPEN_BOUNDED_ARTIFACTS_RESUME_V1.md
- src/solana_alpha_lab/factory/observation_publication_jobs.py
- src/solana_alpha_lab/factory/observation_panel_publisher.py
- scripts/observation_publication_jobs.py
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/PROJECT_MAP.md
- docs/FACTORY_SEMANTIC_MAP.md
- tests/test_legacy_fat_open_bounded_artifacts_resume_v1.py
- tests/test_observation_publication_job_lifecycle_v1.py
- docs/evidence/legacy_fat_open_bounded_artifacts_resume/a1_delivery_completion_evidence_v1.json
- docs/evidence/legacy_fat_open_bounded_artifacts_resume/a1_delivery_independent_review_v1.json
- docs/evidence/legacy_fat_open_bounded_artifacts_resume/a1_delivery_factory_fit_v1.json
- docs/reports/legacy_fat_open_bounded_artifacts_resume/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
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
- STOP_VPS_WRITE_DEPLOY_PAUSE_KILL
- STOP_C1_RESUME_SEAL_IMPORT
- STOP_LIVE_COLLECTOR_TICK
- STOP_HYPOTHESIS_FORGE_SLASH
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- STOP_WEAKEN_ROUTINE_FAT_FAIL_CLOSED
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
    - docs/evidence/legacy_fat_open_bounded_artifacts_resume/a1_delivery_completion_evidence_v1.json
    - docs/evidence/legacy_fat_open_bounded_artifacts_resume/a1_delivery_independent_review_v1.json
    - docs/evidence/legacy_fat_open_bounded_artifacts_resume/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# LEGACY_FAT_OPEN_BOUNDED_ARTIFACTS_RESUME_V1

## SPEC_ROUTE

`NONE` — extend the existing publication-job journal and publisher continuation.
No new publication subsystem.

## Decision capsule

- **DECISION_DELTA:** Oversized `open/` jobs at exactly `stage=ARTIFACTS` get
  an explicit paused-only inspect/resume that streams scalars and the small
  observation payload, skips `members[]`, and continues through the same
  canonical `ARTIFACTS → RDP → MANIFEST → MARKER → compact completed` path.
- **UNCERTAINTY_REMOVED:** Class-B crash residue can finish without a members
  census or a 616 MB JSON parse; routine tick stays fail-closed.
- **CAPABILITY_OR_EVIDENCE:** Operator `inspect-fat-open` then
  `resume-fat-artifacts` for one content identity; tests prove parity, retry,
  hash/stage/pause refusals, MaxRSS, and routine-path regression.
- **STOP:** Exact merge-readiness. No merge, deploy, VPS, tick, or C1.
- **NEXT:** Post-merge OPERATE may recover the live fat `open/` job under a
  separate owner-authorized atom.

SEMANTIC_PREMISE_HIGH_RISK: true

## Runtime safety precondition

`RUNTIME_SAFETY_PRECONDITION=NO_VPS_NO_TICK`

This software atom must not access or mutate Factory. Collector remains frozen
from the prior OPERATE atom. Recovery of the live job is out of scope.

## Non-goals

No merge, deploy, VPS, live tick, C1, STARTED=547 cleanup, activation change,
provider/estimand/timer/swap changes, generalized arbitrary-stage migration,
or weakening of PR #298 memory protections.
