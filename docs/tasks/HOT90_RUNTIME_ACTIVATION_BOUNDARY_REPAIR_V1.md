---
task_id: HOT90_RUNTIME_ACTIVATION_BOUNDARY_REPAIR_V1
task_version: "1.0"
status: READY
as_of: "2026-09-05"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: a946e866370464d7980212118f8535ae963fdb1c
  expected_upstream: origin/main
  expected_upstream_oid: a946e866370464d7980212118f8535ae963fdb1c
  expected_branch: cursor/hot90-runtime-activation-boundary-repair-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Patch HOT90 activation ownership once: Git YAML is policy/safe default
  CURRENT_SAFE; current host stage lives in preserved local runtime state.
  Ordinary stage transitions must not require another Git PR. No VPS mutation.

managed_write_set:
  - docs/tasks/HOT90_RUNTIME_ACTIVATION_BOUNDARY_REPAIR_V1.md
  - configs/factory_hot90_archive_activation_v1.yaml
  - src/solana_alpha_lab/factory/hot90_activation.py
  - scripts/hot90_activation.py
  - tests/test_factory_hot90_immutable_drive_archive_impl_v1.py
  - docs/operator/FACTORY_HOT90_COMMISSIONING_V1.md
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/hot90_runtime_activation_boundary_repair_v1/a1_owner_readout_v1.md
  - docs/evidence/hot90_runtime_activation_boundary_repair_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hot90_runtime_activation_boundary_repair_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/hot90_runtime_activation_boundary_repair_v1/a1_delivery_factory_fit_v1.json

external_caps:
  network: true
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - PRODUCTION_DEPLOY_OR_SYSTEMD_MUTATION
  - GOOGLE_DRIVE_WRITE
  - LOCAL_FACTORY_DATA_DELETE
  - RETENTION_APPLY_ON_LIVE_FACTORY
  - SQLITE_LIVE_COMPACTION
  - PRODUCTION_EVICTION_ENABLED
  - BACKUP_DURABILITY_CUTOVER
  - EXISTING_FULL_RDP_BACKUP_ZIP_DELETE
  - CREDENTIAL_VALUE_READ
  - CAPTURE_OR_SAMPLING_CHANGE
  - TELEGRAM_OR_PROVIDER_CALL
  - NEW_CLOUD_PROVIDER_OR_TABLE_PLATFORM
  - GENERIC_RUNTIME_CONFIG_SUBSYSTEM
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING

context_requirements:
  catalog_asset_ids:
    - CONFIG-FACTORY-HOT90-ARCHIVE-ACTIVATION-001
    - CTRL-FACTORY-HOT90-IMMUTABLE-DRIVE-ARCHIVE-IMPL-001
    - TEST-FACTORY-HOT90-IMMUTABLE-DRIVE-ARCHIVE-IMPL-001
    - DOC-FACTORY-HOT90-COMMISSIONING-001
  l2_roles:
    - LIFECYCLE
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
      - docs/operator/FACTORY_HOT90_COMMISSIONING_V1.md
      - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - configs/factory_hot90_archive_activation_v1.yaml
      - src/solana_alpha_lab/factory/hot90_activation.py
    DELIVERY_EVIDENCE:
      - docs/evidence/hot90_runtime_activation_boundary_repair_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hot90_runtime_activation_boundary_repair_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/hot90_runtime_activation_boundary_repair_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HOT90_RUNTIME_ACTIVATION_BOUNDARY_REPAIR_V1

## Decision delta

Git owns HOT90 policy, allowed stages, validation and the safe default
`CURRENT_SAFE`. Current host activation is preserved local runtime state at
`local/factory_v1/hot90_activation_runtime.yaml`. Ordinary
`CURRENT_SAFE → WRITE_ONLY_SHADOW → DURABILITY_CUTOVER → RETENTION_ACTIVE`
transitions do not require a Git diff. Owner gate still required for production
stage, Drive and destructive flags. This PR does not deploy or change VPS state.

## Binding

- Base: `a946e866370464d7980212118f8535ae963fdb1c`
- Route: `DIRECT_CURSOR_DELIVERY`
- `SPEC_ROUTE`: `NONE`
- Entry: `START_AS_WRITTEN`
- `MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`

## Named consumer

Later OPERATE: write validated runtime state matching live WRITE_ONLY_SHADOW
before deploying this SHA, then exact-SHA deploy and prove no stage transition.

## Cheapest falsifier

Loader with no runtime file returns Git `CURRENT_SAFE`. Valid runtime
`WRITE_ONLY_SHADOW` returns ZSTD + SNAPSHOT_PLUS_DELTA with Drive/compaction/
eviction false. Malformed or symlink runtime fails closed. Mutable backup
excludes full RDP only when runtime stage is `DURABILITY_CUTOVER`.

## STOP / NEXT

STOP after one PR, exact-head CI and merge-readiness. No merge without the
exact owner phrase. No VPS mutation from this PR.

NEXT after merge: OPERATE continuity migration (runtime file then deploy), not
another Git stage-transition PR.
