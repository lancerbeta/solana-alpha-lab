---
task_id: FACTORY_OFFHOST_TRAFFIC_BOUNDED_BACKUP_V1
task_version: '1.1'
status: READY
as_of: '2026-09-02'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: a1dcf6b5b2b457f375a37ffd41b97b24fc951264
  expected_upstream: origin/main
  expected_upstream_oid: a1dcf6b5b2b457f375a37ffd41b97b24fc951264
  expected_branch: cursor/factory-offhost-traffic-bounded-backup-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Replace the current high-amplification local/off-host backup topology with
  bounded-memory local full snapshots, daily manifest-differenced incremental
  Google Drive checkpoints and weekly standalone full coverage, preserving
  approximately 24h disaster RPO while targeting <=240 GB of measured
  application backup payload per rolling 30 days as an operating design margin
  under the owner's 300 GB backup-traffic target, with exact remote recovery
  discovery and non-empty RDP isolated restore proof.
managed_write_set:
- docs/tasks/FACTORY_OFFHOST_TRAFFIC_BOUNDED_BACKUP_V1.md
- configs/factory_remote_operations_v1_1.yaml
- catalog/schemas/factory_remote_operations_v1_1.schema.json
- configs/factory_remote_ops/factory-remote-backup.timer
- configs/factory_remote_ops/factory-remote-backup.service
- configs/factory_remote_ops/factory-remote-backup-gdrive.service
- configs/factory_remote_ops/factory-remote-backup-gdrive.timer
- configs/factory_remote_ops/factory-remote-backup-gdrive-delta.service
- configs/factory_remote_ops/factory-remote-backup-gdrive-delta.timer
- scripts/factory_offhost_backup_copy.py
- scripts/factory_remote_doctor.py
- src/solana_alpha_lab/factory/offhost_backup.py
- src/solana_alpha_lab/factory/remote_ops.py
- src/solana_alpha_lab/factory/collector_operational_packet.py
- src/solana_alpha_lab/factory/collector_owner_pulse.py
- src/solana_alpha_lab/factory/live_ops_hardening.py
- tests/test_factory_offhost_backup.py
- tests/test_factory_remote_operations.py
- tests/test_factory_v1_live_ops_hardening.py
- docs/operator/FACTORY_REMOTE_HOST.md
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/operator/factory_remote_host_v1.yaml
- catalog/assets/core.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
- docs/evidence/factory_offhost_traffic_bounded_backup/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_offhost_traffic_bounded_backup/a1_delivery_independent_review_v1.json
- docs/evidence/factory_offhost_traffic_bounded_backup/a1_delivery_factory_fit_v1.json
- docs/reports/factory_offhost_traffic_bounded_backup/a1_owner_readout_v1.md
external_caps:
  network: true
  credentials: true
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: true
stop_conditions:
- NEW_BACKUP_PROVIDER_REQUIRED
- NEW_BACKUP_PLATFORM_REQUIRED
- NEW_CREDENTIAL_REQUIRED
- CREDENTIAL_VALUE_EXPOSURE_REQUIRED
- REMOTE_DELETE_REQUIRED
- RCLONE_SYNC_REQUIRED
- SCIENTIFIC_RDP_RETENTION_CHANGE_REQUIRED
- PRODUCTION_RESTORE_OVER_LIVE_STATE_REQUIRED
- CASH_SPEND_REQUIRED
- WALLET_SIGNER_TRANSACTION_REQUIRED
- BACKUP_CORRECTNESS_REQUIRES_SECOND_PERSISTENCE_CONTROL_PLANE
- SAFE_LOCAL_DERIVED_BUNDLE_RETENTION_CANNOT_BE_PROVEN
context_requirements:
  catalog_asset_ids: []
  l2_roles:
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
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE:
    - docs/operator/factory_remote_host_v1.yaml
    - configs/factory_remote_operations_v1_1.yaml
    - docs/operator/FACTORY_REMOTE_HOST.md
    - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/factory_offhost_traffic_bounded_backup/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_offhost_traffic_bounded_backup/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_offhost_traffic_bounded_backup/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
    - docs/reports/factory_google_drive_offhost_durability_automation/a1_owner_readout_v1.md
    - docs/evidence/factory_google_drive_offhost_durability_automation/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_google_drive_offhost_durability_automation/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_google_drive_offhost_durability_automation/a1_delivery_factory_fit_v1.json
---

# FACTORY_OFFHOST_TRAFFIC_BOUNDED_BACKUP_V1

## SPEC_ROUTE

`NONE` — operational durability topology change of existing remote-ops backup.

## DECISION_DELTA

Hourly full local+Drive copy is replaced by 12h streaming local full (retain 1),
daily incremental Drive checkpoint, weekly standalone full, and an immutable
remote recovery checkpoint. Application payload is not Cherry billing truth.

## UNCERTAINTY_REMOVED

Whether ~24h disaster RPO can stay inside a 240 GB / 30d application-payload
planning budget without rclone sync/delete or a second backup platform.

## CAPABILITY_OR_EVIDENCE

Streaming `package_backup`, 12h timer, retain-1 prune, shared lock, weekly-before-delta,
recovery checkpoint discovery, planning fixture ~202 GB < 240 GB, nonempty isolated
incremental restore proof.

## STOP

Exact merge gate. No remote delete/sync. No restore over live Factory state.
No new backup provider. Live VPS unit enable is allowed after Git identity is
bound; not required to claim the Git proof.

## NEXT

Deploy/enable 12h local + daily delta + weekly full timers on Factory VPS;
confirm first remote checkpoint; locator SKU remains live `CLOUD_VPS_6_GEN2`.

## REPLAN_TRIGGER

Planning fixture or `5 × current_full + projected_deltas` cannot stay under 240 GB
without weakening RPO; rclone sync/delete appears required; second persistence
plane required for correctness.

## Managed write set

```text
docs/tasks/FACTORY_OFFHOST_TRAFFIC_BOUNDED_BACKUP_V1.md
configs/factory_remote_operations_v1_1.yaml
catalog/schemas/factory_remote_operations_v1_1.schema.json
configs/factory_remote_ops/factory-remote-backup.timer
configs/factory_remote_ops/factory-remote-backup.service
configs/factory_remote_ops/factory-remote-backup-gdrive.service
configs/factory_remote_ops/factory-remote-backup-gdrive.timer
configs/factory_remote_ops/factory-remote-backup-gdrive-delta.service
configs/factory_remote_ops/factory-remote-backup-gdrive-delta.timer
scripts/factory_offhost_backup_copy.py
scripts/factory_remote_doctor.py
src/solana_alpha_lab/factory/offhost_backup.py
src/solana_alpha_lab/factory/remote_ops.py
src/solana_alpha_lab/factory/collector_operational_packet.py
src/solana_alpha_lab/factory/collector_owner_pulse.py
src/solana_alpha_lab/factory/live_ops_hardening.py
tests/test_factory_offhost_backup.py
tests/test_factory_remote_operations.py
tests/test_factory_v1_live_ops_hardening.py
docs/operator/FACTORY_REMOTE_HOST.md
docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
docs/operator/factory_remote_host_v1.yaml
catalog/assets/core.yaml
catalog/catalog_manifest.yaml
catalog/generated/asset_edges.json
docs/PROJECT_MAP.md
docs/OPERATOR_NAVIGATION.md
docs/evidence/factory_offhost_traffic_bounded_backup/a1_delivery_completion_evidence_v1.json
docs/evidence/factory_offhost_traffic_bounded_backup/a1_delivery_independent_review_v1.json
docs/evidence/factory_offhost_traffic_bounded_backup/a1_delivery_factory_fit_v1.json
docs/reports/factory_offhost_traffic_bounded_backup/a1_owner_readout_v1.md
```

## Authoritative overrides

Owner V1.1 corrections C1–C10 are authoritative: 12h local full / retain 1 /
streaming package / weekly-before-delta / recovery checkpoint / no-change still
publishes checkpoint / payload bytes are not billing truth / 240 GB internal
budget / 300 GB owner target / nonempty isolated incremental restore.

Final terminal: `FACTORY_DAILY_DELTA_WEEKLY_FULL_OFFHOST_BACKUP_PASS`.
