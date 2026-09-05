---
task_id: FACTORY_HOT90_WRITE_ONLY_SHADOW_ACTIVATION_V1
task_version: "1.0"
status: READY
as_of: "2026-09-05"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: fc69b4d5fa88d07ff177fda4c731c1792b1ae8cd
  expected_upstream: origin/main
  expected_upstream_oid: fc69b4d5fa88d07ff177fda4c731c1792b1ae8cd
  expected_branch: cursor/factory-hot90-write-only-shadow-activation-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Git-owned config-only HOT90 activation CURRENT_SAFE -> WRITE_ONLY_SHADOW
  with production_compaction_enabled, production_eviction_enabled, and
  drive_writes_enabled remaining false. No VPS deploy, Drive write,
  compaction, eviction, backup cutover, or implementation redesign.

managed_write_set:
  - docs/tasks/FACTORY_HOT90_WRITE_ONLY_SHADOW_ACTIVATION_V1.md
  - configs/factory_hot90_archive_activation_v1.yaml
  - tests/test_factory_hot90_immutable_drive_archive_impl_v1.py
  - tests/test_observation_scheduler.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/factory_hot90_write_only_shadow_activation_v1/a1_owner_readout_v1.md
  - docs/evidence/factory_hot90_write_only_shadow_activation_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_hot90_write_only_shadow_activation_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_hot90_write_only_shadow_activation_v1/a1_delivery_factory_fit_v1.json

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
  - IMPLEMENTATION_REDESIGN_OR_RUNTIME_OVERRIDE
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING

context_requirements:
  catalog_asset_ids:
    - CONFIG-FACTORY-HOT90-ARCHIVE-ACTIVATION-001
    - CTRL-FACTORY-HOT90-IMMUTABLE-DRIVE-ARCHIVE-IMPL-001
    - TEST-FACTORY-HOT90-IMMUTABLE-DRIVE-ARCHIVE-IMPL-001
  l2_roles:
    - LIFECYCLE
    - EXTERNAL_ROUTE_KNOWLEDGE
    - ARCHITECTURE_DECISIONS
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
    LIFECYCLE:
      - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
    EXTERNAL_ROUTE_KNOWLEDGE:
      - docs/operator/FACTORY_REMOTE_HOST.md
      - docs/operator/factory_remote_host_v1.yaml
    ARCHITECTURE_DECISIONS:
      - configs/factory_hot90_archive_activation_v1.yaml
      - src/solana_alpha_lab/factory/hot90_activation.py
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_hot90_write_only_shadow_activation_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_hot90_write_only_shadow_activation_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_hot90_write_only_shadow_activation_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_HOT90_WRITE_ONLY_SHADOW_ACTIVATION_V1

## Decision delta

Canonical tracked HOT90 stage becomes `WRITE_ONLY_SHADOW`. New publisher
writes use ZSTD and `SNAPSHOT_PLUS_DELTA`. Drive writes, SQLite compaction,
eviction, and backup durability cutover stay disabled. Live VPS still runs
`CURRENT_SAFE` until a later exact-SHA deploy.

## Binding

- Base: `fc69b4d5fa88d07ff177fda4c731c1792b1ae8cd`
- Route: `DIRECT_CURSOR_DELIVERY`
- `SPEC_ROUTE`: `NONE`
- Entry: `START_AS_WRITTEN`
- `MODEL_EFFORT_RECOMMENDATION`: `LUNA_MAX`

## Named consumer

Later OPERATE atom: deploy the exact merged SHA and observe real
`WRITE_ONLY_SHADOW` publications before any durability cutover. Not this atom.

## Cheapest falsifier

Loader from the tracked YAML returns `activation_stage=WRITE_ONLY_SHADOW`,
`members_layout=SNAPSHOT_PLUS_DELTA`, `new_write_zstd=true`, and all three
destructive/Drive flags false. `CURRENT_SAFE` fail-closed tests still pass.
Production-gated eviction, compaction, and Drive writes remain refused.

## STOP / NEXT

STOP after one tiny PR, exact-head CI, and merge-readiness. No merge without
the exact owner phrase. No production deploy from this PR.

NEXT after merge: deploy exact merged SHA and observe real WRITE_ONLY_SHADOW
publications before any durability cutover.
