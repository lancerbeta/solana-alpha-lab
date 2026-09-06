---
task_id: FACTORY_SNAPSHOT_DELTA_ECONOMY_AND_SIGNAL_REPAIR_V1
task_version: "1.0"
status: READY
as_of: "2026-09-06"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 7b7f96d191b12fb37a90565241b0ce0c447eaf30
  expected_upstream: origin/main
  expected_upstream_oid: 7b7f96d191b12fb37a90565241b0ce0c447eaf30
  expected_branch: cursor/factory-snapshot-delta-economy-and-signal-repair-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Repair SNAPSHOT_PLUS_DELTA so new deltas persist only material member
  changes and reconstruct without O(universe×chain) hashing; keep old fat
  deltas readable; stop duplicate DATA_STALE incidents; 24h-normalize live
  storage growth. No HOT90 redesign, retention, eviction, or VPS deploy.

managed_write_set:
  - docs/tasks/FACTORY_SNAPSHOT_DELTA_ECONOMY_AND_SIGNAL_REPAIR_V1.md
  - src/solana_alpha_lab/factory/members_snapshot_delta.py
  - src/solana_alpha_lab/factory/operability_watch.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - tests/test_factory_snapshot_delta_economy_and_signal_repair_v1.py
  - configs/ci_test_shards_v1.json
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/operator/FACTORY_HOT90_COMMISSIONING_V1.md
  - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - docs/reports/factory_snapshot_delta_economy_and_signal_repair_v1/a1_owner_readout_v1.md
  - docs/evidence/factory_snapshot_delta_economy_and_signal_repair_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_snapshot_delta_economy_and_signal_repair_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_snapshot_delta_economy_and_signal_repair_v1/a1_delivery_factory_fit_v1.json
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
  - PRODUCTION_DEPLOY_OR_SYSTEMD_HOST_MUTATION
  - GOOGLE_DRIVE_WRITE
  - LIVE_TELEGRAM_SEND
  - RETENTION_APPLY_ON_LIVE_FACTORY
  - SCIENTIFIC_RDP_DELETE
  - DRIVE_PRUNE
  - HISTORICAL_FAT_DELTA_REWRITE
  - LEASE_TTL_INFLATION_WITHOUT_EVIDENCE
  - WATCH_CADENCE_CHANGE_AS_PRIMARY_FIX
  - CREDENTIAL_VALUE_READ
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
      - configs/factory_hot90_archive_activation_v1.yaml
      - configs/factory_remote_operations_v1_1.yaml
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_snapshot_delta_economy_and_signal_repair_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_snapshot_delta_economy_and_signal_repair_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_snapshot_delta_economy_and_signal_repair_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_SNAPSHOT_DELTA_ECONOMY_AND_SIGNAL_REPAIR_V1

## Task Outcome Brief

- Owner decision: compact SNAPSHOT_PLUS_DELTA persistence and replay is the
  common cause of 4–5 MiB/publication, 12-minute ticks, false DATA_STALE, and
  HARD50 projection inflation. Repair write+replay+signals in one PR.
- Named consumer: live ObservationPanel publisher / reconstruct / archive
  hydrate, plus operability watch freshness incidents.
- Cheapest falsifier: large-universe tiny-change delta size ratio; 80-delta
  replay snapshot-hash count; mixed v1→v2 reconstruct; fail-closed corruption;
  one SOURCE_DATA_STALE incident; 31h growth scaled to 24h.
- Non-goals: HOT90 redesign, watch cadence change, SQLite compaction,
  retention/eviction, historical rewrite, VPS deploy.
- SPEC_ROUTE: NONE.

## Decision delta

New deltas are schema 2.0 without `unchanged[]`. Replay verifies chain identity
and hashes the target snapshot once. Watch maps DATA_STALE only to
SOURCE_DATA_STALE. Live growth is span-normalized. Lease stays 120s.

## ENTRY

`START_WITH_PATCH`: SNAPSHOT_PLUS_DELTA reconstructs exactly but persists the
full unchanged set; reconstruction re-hashes the universe per delta.
