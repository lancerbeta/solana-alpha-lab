---
task_id: FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1
task_version: "1.0"
status: READY
as_of: "2026-09-05"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 8149f0649a633a334cc1fab532027ba483e4f4da
  expected_upstream: origin/main
  expected_upstream_oid: 8149f0649a633a334cc1fab532027ba483e4f4da
  expected_branch: cursor/factory-hot90-immutable-drive-archive-impl-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Implement FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1 with SNAPSHOT_PLUS_DELTA
  behind a fail-closed CURRENT_SAFE default so a future checkout/deploy cannot
  silently change live Factory semantics. No production deploy, Drive write,
  retention APPLY, local Factory delete, or SQLite live compaction.

managed_write_set:
  - docs/tasks/FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1.md
  - configs/factory_hot90_archive_activation_v1.yaml
  - catalog/schemas/observation_schedule_v1.schema.json
  - catalog/schemas/experiment_spec_v1_2.schema.json
  - catalog/schemas/factory_remote_operations_v1_1.schema.json
  - configs/factory_remote_operations_v1_1.yaml
  - configs/ci_test_shards_v1.json
  - delivery-harness/policies/solana-alpha-lab.md
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - docs/operator/FACTORY_HOT90_COMMISSIONING_V1.md
  - docs/operator/FACTORY_HOT90_CLEANUP_PRECONDITIONS_V1.md
  - docs/reports/factory_hot90_immutable_drive_archive_impl_v1/a1_owner_readout_v1.md
  - docs/evidence/factory_hot90_immutable_drive_archive_impl_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_hot90_immutable_drive_archive_impl_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_hot90_immutable_drive_archive_impl_v1/a1_delivery_factory_fit_v1.json
  - src/solana_alpha_lab/factory/hot90_activation.py
  - src/solana_alpha_lab/factory/members_snapshot_delta.py
  - src/solana_alpha_lab/factory/raw_evidence_plane.py
  - src/solana_alpha_lab/factory/hot90_archive.py
  - src/solana_alpha_lab/factory/hot90_remote_verify.py
  - src/solana_alpha_lab/factory/hot90_eviction.py
  - src/solana_alpha_lab/factory/hot90_storage_admission.py
  - src/solana_alpha_lab/factory/hot90_sqlite_eligibility.py
  - src/solana_alpha_lab/factory/hot90_mutable_backup.py
  - src/solana_alpha_lab/factory/observation_panel_publisher.py
  - src/solana_alpha_lab/factory/research_store.py
  - src/solana_alpha_lab/factory/remote_ops.py
  - src/solana_alpha_lab/factory/offhost_backup.py
  - tests/test_factory_hot90_immutable_drive_archive_impl_v1.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/control/delivery_harness_acceptance_v1.json
  - docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json

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
  - EXISTING_FULL_RDP_BACKUP_ZIP_DELETE
  - CREDENTIAL_VALUE_READ
  - CAPTURE_OR_SAMPLING_CHANGE
  - TELEGRAM_OR_PROVIDER_CALL
  - NEW_CLOUD_PROVIDER_OR_TABLE_PLATFORM
  - SILENT_CURRENT_SAFE_SEMANTIC_CHANGE
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
    - LIFECYCLE
    - EXTERNAL_ROUTE_KNOWLEDGE
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
      - docs/architecture/FACTORY_97D_STORAGE_ARCHITECTURE_PRD_SSD_V1.md
      - delivery-harness/policies/solana-alpha-lab.md
      - configs/factory_remote_operations_v1_1.yaml
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_hot90_immutable_drive_archive_impl_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_hot90_immutable_drive_archive_impl_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_hot90_immutable_drive_archive_impl_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1

## Decision delta

Repository contains the complete HOT90 capability (SNAPSHOT_PLUS_DELTA,
ZSTD new writes, raw plane, archive/verify/hydrate/evict/admission) while
production remains `CURRENT_SAFE` until a later commissioning atom.

## Binding

- Base: `8149f0649a633a334cc1fab532027ba483e4f4da`
- Route: `DIRECT_CURSOR_DELIVERY`
- SPEC_ROUTE: `NONE` (PRD already merged)
- Entry: `START_AS_WRITTEN`
- `MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`

Predecessor `FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1` / PR #262 terminal
`STORAGE_97D_ARCHITECTURE_READY` is the architecture owner. Do not redo
closed storage benchmarks unless implementation evidence shows a semantic
discrepancy.

## Named consumer

Later commissioning on the VPS after this research-IMPL PR merges. Not this
atom. Destructive eviction and old ZIP cleanup remain later owner gates.

## STOP / NEXT

STOP after PR + exact-head CI + merge-readiness. No merge without the exact
owner phrase. NEXT is owner merge phrase if `ready_for_owner_phrase=true`,
then commissioning as a separate atom.
