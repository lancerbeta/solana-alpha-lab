---
task_id: FACTORY_GOOGLE_DRIVE_OFFHOST_DURABILITY_AUTOMATION_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-01'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: a8a9b9931c06646fc0164d1ad29bea5a0f7a0b47
  expected_upstream: origin/main
  expected_upstream_oid: a8a9b9931c06646fc0164d1ad29bea5a0f7a0b47
  expected_branch: cursor/factory-gdrive-offhost-durability-automation-v1
  dirty_mode: ALLOW_REPORTED
objective: Turn the proven Google Drive copy/readback/restore route into the
  smallest canonical unattended OFF_HOST durability capability after local
  hourly backup, with machine freshness visibility and fresh-agent recovery,
  without changing FACTORY_BACKUP_SINK or claiming non-empty live RDP restore.
managed_write_set:
- docs/tasks/FACTORY_GOOGLE_DRIVE_OFFHOST_DURABILITY_AUTOMATION_V1.md
- catalog/assets/core.yaml
- catalog/schemas/factory_remote_operations_v1_1.schema.json
- configs/factory_remote_operations_v1_1.yaml
- configs/factory_remote_ops/factory-remote-backup-gdrive.service
- configs/factory_remote_ops/factory-remote-backup.service
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/operator/FACTORY_REMOTE_HOST.md
- docs/operator/factory_remote_host_v1.yaml
- scripts/factory_offhost_backup_copy.py
- scripts/factory_remote_doctor.py
- src/solana_alpha_lab/factory/collector_operational_packet.py
- src/solana_alpha_lab/factory/collector_owner_pulse.py
- src/solana_alpha_lab/factory/live_ops_hardening.py
- src/solana_alpha_lab/factory/offhost_backup.py
- src/solana_alpha_lab/factory/remote_ops.py
- tests/test_factory_offhost_backup.py
- tests/test_factory_remote_operations.py
- docs/evidence/factory_google_drive_offhost_durability_automation/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_google_drive_offhost_durability_automation/a1_delivery_independent_review_v1.json
- docs/evidence/factory_google_drive_offhost_durability_automation/a1_delivery_factory_fit_v1.json
- docs/reports/factory_google_drive_offhost_durability_automation/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_PROVIDER_OR_CREDENTIAL_REQUIRED
- STOP_VPS_OR_DEPLOY_REQUIRED
- STOP_AUTHORIZE_OR_ACTIVATE
- STOP_NONEMPTY_RDP_OFFHOST_RESTORE_PROOF
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
    - docs/evidence/factory_google_drive_offhost_durability_automation/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_google_drive_offhost_durability_automation/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_google_drive_offhost_durability_automation/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_GOOGLE_DRIVE_OFFHOST_DURABILITY_AUTOMATION_V1

## SPEC_ROUTE

`NONE` — operational durability extension of existing remote-ops backup.

## DECISION_DELTA

Google Drive becomes `PROVEN_OFFHOST_DURABILITY` (copy-only stage 2) after local
hourly backup, with machine RPO visibility and fresh-agent recovery; prior role
`OPTIONAL_COLD_COPY_NOT_DOD` preserved in provenance.

## UNCERTAINTY_REMOVED

Whether the already-proven Drive copy/readback/restore route can become
unattended hourly durability without a second backup platform.

## CAPABILITY_OR_EVIDENCE

Stage-2 `OnSuccess` copy, receipt, doctor `--offhost-status`, pulse/doctor
health classes, zero-secret tests, recovery runbook.

## STOP

Exact merge gate. No VPS deploy/enable of gdrive unit in this atom.
`NONEMPTY_RDP_OFFHOST_RESTORE_PROOF` remains mandatory after live RDP exists.

## NEXT

Deploy + enable gdrive chain on VPS, then Jupiter credential gate.
