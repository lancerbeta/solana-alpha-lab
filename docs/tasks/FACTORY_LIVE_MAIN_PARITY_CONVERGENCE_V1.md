---
task_id: FACTORY_LIVE_MAIN_PARITY_CONVERGENCE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-24'
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
required_review_roles:
  - CODE_REVIEWER
  - ARCHITECTURE_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 11bdb4349071f1309ca3cd48760d707bbdd06a56
  expected_upstream: origin/main
  expected_upstream_oid: 11bdb4349071f1309ca3cd48760d707bbdd06a56
  expected_branch: cursor/factory-live-main-parity-convergence-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Put the proven live backup snapshot and post-PR330 collector continuity
  invariants onto current main without merging the live backport branch or
  PR 331, and without new product or runtime semantics.
managed_write_set:
  - docs/tasks/FACTORY_LIVE_MAIN_PARITY_CONVERGENCE_V1.md
  - src/solana_alpha_lab/factory/remote_ops.py
  - src/solana_alpha_lab/factory/offhost_backup.py
  - tests/test_factory_remote_operations.py
  - tests/test_factory_offhost_backup.py
  - src/solana_alpha_lab/factory/observation_scheduler.py
  - src/solana_alpha_lab/factory/collector_read_model.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
  - tests/test_collector_continuity_boundaries_v1.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - catalog/assets/core.yaml
  - catalog/generated/asset_edges.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - NEW_SEMANTIC_DECISION
  - SCHEMA_MIGRATION
  - VPS_OR_DRIVE_MUTATION
  - PR_331_MERGE
context_requirements:
  catalog_asset_ids: []
  l2_roles: []
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# FACTORY_LIVE_MAIN_PARITY_CONVERGENCE_V1

Git-only parity. Live `aaf7f89c` stays the running host. This branch copies
the proven invariants onto `11bdb434` main.

Backup commits reused from the main-based line: `c286695c`, `a4d27c04`.
Continuity is a minimal port of `51ca014e`, `0b00b610`, `9b199472`,
`22a86893`, and `1fe894da`. PR #331 is not merged.
