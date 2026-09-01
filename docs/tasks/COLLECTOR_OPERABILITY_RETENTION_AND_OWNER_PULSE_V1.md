---
task_id: COLLECTOR_OPERABILITY_RETENTION_AND_OWNER_PULSE_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-01'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 23bb5b8d4bb861a33c27d711479af4ccdfffe9b9
  expected_upstream: origin/main
  expected_upstream_oid: 23bb5b8d4bb861a33c27d711479af4ccdfffe9b9
  expected_branch: cursor/collector-operability-retention-and-owner-pulse-v1
  dirty_mode: ALLOW_REPORTED
objective: Finish the software baseline for unattended multi-week Factory lifecycle
  collection before final VPS deploy — one collector operational read model, health
  semantics, daily owner Telegram pulse, and safe operational SQLite retention —
  without VPS mutation, providers, Forge, or scientific deletion.
managed_write_set:
- docs/tasks/COLLECTOR_OPERABILITY_RETENTION_AND_OWNER_PULSE_V1.md
- src/solana_alpha_lab/factory/collector_operational_packet.py
- src/solana_alpha_lab/factory/collector_owner_pulse.py
- src/solana_alpha_lab/factory/observation_schedule_retention.py
- scripts/collector_owner_pulse.py
- scripts/observation_schedule_retention.py
- configs/factory_remote_ops/factory-collector-owner-pulse.service
- configs/factory_remote_ops/factory-collector-owner-pulse.timer
- configs/factory_remote_operations_v1_1.yaml
- catalog/schemas/factory_remote_operations_v1_1.schema.json
- tests/test_collector_operability_retention_and_owner_pulse.py
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- docs/evidence/collector_operability_retention_and_owner_pulse/a1_delivery_completion_evidence_v1.json
- docs/evidence/collector_operability_retention_and_owner_pulse/a1_delivery_independent_review_v1.json
- docs/evidence/collector_operability_retention_and_owner_pulse/a1_delivery_factory_fit_v1.json
- docs/reports/collector_operability_retention_and_owner_pulse/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
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
- STOP_FORGE_OR_EXPERIMENT
- STOP_SCIENTIFIC_RDP_OR_RELEASE_DELETION
- RAW_RETENTION_REQUIRES_REPLAN
- STOP_SECOND_MONITORING_OR_DATA_PLATFORM
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
    LIFECYCLE:
    - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/collector_operability_retention_and_owner_pulse/a1_delivery_completion_evidence_v1.json
    - docs/evidence/collector_operability_retention_and_owner_pulse/a1_delivery_independent_review_v1.json
    - docs/evidence/collector_operability_retention_and_owner_pulse/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# COLLECTOR_OPERABILITY_RETENTION_AND_OWNER_PULSE_V1

## SPEC_ROUTE

`NONE` — ADOPT/WRAP existing collector_read_model, remote_ops health/backup/Telegram,
live cohort release readiness, ObservationSchedule store, and systemd unit patterns.

## DECISION_DELTA

Unattended multi-week collection needs one owner-visible operational packet, a daily
Telegram pulse (no Jupiter credentials), and safe compaction of aged COMPLETED
operational provider payloads — without a second monitoring platform and without
deleting scientific RDP/releases/corpus.

## UNCERTAINTY_REMOVED

Whether `raw_retention_days=31` is enforceable on operational SQLite without a new
raw archive; whether daily pulse can render with zero network/credential reads;
whether disk early-warning can coexist with the existing 85% hard boundary.

## CAPABILITY_OR_EVIDENCE

Machine-readable collector operational packet; health incident classes; dry-run and
emit daily pulse + systemd templates (not installed); retention status/dry-run and
optional apply compaction; zero-network vertical fixture; runbook/Catalog update.

## STOP

Exact merge gate. No VPS deploy/enable, no live activation, no provider calls,
no Forge/experiment, no scientific deletion.

## NEXT

Final VPS deploy of repaired main after this software baseline lands (separate atom).

## REPLAN_TRIGGER

`RAW_RETENTION_REQUIRES_REPLAN` if safe compaction cannot be proven without a new
raw archive or scientific storage rewrite.
