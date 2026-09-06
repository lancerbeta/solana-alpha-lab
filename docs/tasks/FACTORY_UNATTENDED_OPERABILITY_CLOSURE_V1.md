---
task_id: FACTORY_UNATTENDED_OPERABILITY_CLOSURE_V1
task_version: "1.0"
status: READY
as_of: "2026-09-06"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: f08effba27125d6e23c0ee4de53c0d1ee2ae0cde
  expected_upstream: origin/main
  expected_upstream_oid: f08effba27125d6e23c0ee4de53c0d1ee2ae0cde
  expected_branch: cursor/factory-unattended-operability-closure-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Close unattended Factory operability as one Git capability: recurring
  closed-day archive→Drive→exact SHA, one daily/incident/recovery pulse,
  local watchdog, provider-neutral heartbeat hook, and semantic discovery.
  No live deploy, Drive write, Telegram send, retention, or scientific delete.

managed_write_set:
  - docs/tasks/FACTORY_UNATTENDED_OPERABILITY_CLOSURE_V1.md
  - src/solana_alpha_lab/factory/hot90_archive.py
  - src/solana_alpha_lab/factory/hot90_remote_verify.py
  - src/solana_alpha_lab/factory/hot90_closed_day_loop.py
  - src/solana_alpha_lab/factory/operability_watch.py
  - src/solana_alpha_lab/factory/external_heartbeat.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/collector_owner_pulse.py
  - scripts/hot90_closed_day_durability.py
  - scripts/factory_operability_watch.py
  - scripts/factory_external_heartbeat.py
  - scripts/collector_owner_pulse.py
  - configs/factory_remote_operations_v1_1.yaml
  - catalog/schemas/factory_remote_operations_v1_1.schema.json
  - configs/factory_remote_ops/factory-collector-owner-pulse.timer
  - configs/factory_remote_ops/factory-collector-owner-pulse.service
  - configs/factory_remote_ops/factory-hot90-closed-day-archive.service
  - configs/factory_remote_ops/factory-hot90-closed-day-archive.timer
  - configs/factory_remote_ops/factory-operability-watch.service
  - configs/factory_remote_ops/factory-operability-watch.timer
  - configs/factory_remote_ops/factory-external-heartbeat.service
  - configs/factory_remote_ops/factory-external-heartbeat.timer
  - configs/factory_remote_ops/secrets.env.example
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/assets/core.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
  - docs/operator/FACTORY_HOT90_COMMISSIONING_V1.md
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - README.md
  - configs/ci_test_shards_v1.json
  - tests/test_factory_unattended_operability_closure_v1.py
  - tests/test_factory_hot90_immutable_drive_archive_impl_v1.py
  - tests/test_collector_operability_retention_and_owner_pulse.py
  - tests/test_factory_semantic_operability.py
  - docs/reports/factory_unattended_operability_closure_v1/a1_owner_readout_v1.md
  - docs/evidence/factory_unattended_operability_closure_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_unattended_operability_closure_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_unattended_operability_closure_v1/a1_delivery_factory_fit_v1.json
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
  - CREDENTIAL_VALUE_READ
  - NEW_MONITORING_PLATFORM_OR_QUEUE
  - PROVIDER_PURCHASE_OR_EXTERNAL_WATCHER_ACTIVATION
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
      - delivery-harness/policies/solana-alpha-lab.md
      - configs/factory_remote_operations_v1_1.yaml
      - configs/factory_hot90_archive_activation_v1.yaml
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_unattended_operability_closure_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_unattended_operability_closure_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_unattended_operability_closure_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_UNATTENDED_OPERABILITY_CLOSURE_V1

## Task Outcome Brief

- Owner decision: close unattended operability as four vertical loops, not a
  monitoring platform or another runtime state machine in Git.
- Named consumer: GOAL_OWNER daily/incident Telegram + later OPERATE
  commissioning of new systemd units.
- Cheapest falsifier: vertical tests that a closed fixture day archives once,
  Drive copy without SHA is not durable, 7-day backlog catch-up converges,
  incidents fire once, UTC bytes match, unconfigured heartbeat is silent.
- Non-goals: live deploy, Drive/Telegram, RETENTION_ACTIVE, scientific delete,
  external watcher purchase.
- SPEC_ROUTE: NONE (loop contracts live in this task; no second PRD).

## Decision delta

Git gains recurring consumers over existing HOT90 archive/verify primitives,
one operability watch, UTC-correct daily pulse, and a heartbeat URL hook.
Git still does not own live HOT90 stage or current health.

## ENTRY

`START_WITH_PATCH`: `package_closed_day_archive` / `verify_remote_content_sha256`
exist with tests and no production recurring caller.
