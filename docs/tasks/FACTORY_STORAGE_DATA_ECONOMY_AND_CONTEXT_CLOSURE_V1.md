---
task_id: FACTORY_STORAGE_DATA_ECONOMY_AND_CONTEXT_CLOSURE_V1
task_version: "1.0"
status: READY
as_of: "2026-09-04"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: af1ad23ac4a97d4f63108abd8446ad3dc6b1960c
  expected_upstream: origin/main
  expected_upstream_oid: af1ad23ac4a97d4f63108abd8446ad3dc6b1960c
  expected_branch: cursor/factory-storage-data-economy-and-context-closure-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Close the current Collector/storage operational chain with a durable
  post-reclaim economics baseline, DATA_RESOLUTION_ECONOMY in the existing
  domain-policy owner, and a corrected agent-facing Collector runbook.
  No production-code, Telegram, topology, or retention APPLY in this atom.

managed_write_set:
  - docs/tasks/FACTORY_STORAGE_DATA_ECONOMY_AND_CONTEXT_CLOSURE_V1.md
  - delivery-harness/policies/solana-alpha-lab.md
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - docs/reports/factory_storage_data_economy_and_context_closure_v1/a1_owner_readout_v1.md
  - docs/evidence/factory_storage_data_economy_and_context_closure_v1/a1_storage_baseline_v1.json
  - docs/evidence/factory_storage_data_economy_and_context_closure_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_storage_data_economy_and_context_closure_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_storage_data_economy_and_context_closure_v1/a1_delivery_factory_fit_v1.json
  - tests/test_factory_storage_data_economy_and_context_closure_v1.py
  - configs/ci_test_shards_v1.json
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
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - PRODUCTION_CODE_CHANGE_REQUIRED
  - RETENTION_APPLY_OR_VACUUM
  - TELEGRAM_OR_PULSE_TIMER_INSTALL
  - REPEAT_RECLAIM_OR_RESTORE
  - NEW_STORAGE_SERVICE_SCHEMA_OR_ARCHIVE_TIER
  - HARD_GLOBAL_CANDLE_GRANULARITY
  - PACKAGE_ADOPTION_REQUIRED
  - SECOND_ARCHITECTURE_PIVOT
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING

context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
    - ARCHITECTURE_DECISIONS
    - LIFECYCLE
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
    ARCHITECTURE_DECISIONS:
      - delivery-harness/policies/solana-alpha-lab.md
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_storage_data_economy_and_context_closure_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_storage_data_economy_and_context_closure_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_storage_data_economy_and_context_closure_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_STORAGE_DATA_ECONOMY_AND_CONTEXT_CLOSURE_V1

## Decision delta

After live publication operability, nonempty off-host restore proof, and
`legacy_full` reclaim, does current Factory storage require a topology,
retention, or capture-resolution change — or only a durable economics
baseline plus agent-facing context correction?

## Binding

- Base: `af1ad23ac4a97d4f63108abd8446ad3dc6b1960c`
- Route: `DIRECT_CURSOR_DELIVERY`
- SPEC_ROUTE: `PRD_LITE`
- Entry: `START_WITH_PATCH`

## Reclaim disposition (literal, not rewritten)

Machine terminal of the reclaim operation remains:

`LEGACY_FULL_RECLAIM_FAIL`

Project-level interpretation: `RECLAIM_EFFECTIVE` /
`ACCEPTANCE_FALSE_NEGATIVE_CONCURRENT_PUBLICATION`.

Acceptance required exact pre/post scientific fingerprint equality while the
collector stayed `ACTIVE`. The collector legally appended publications.
Pre-existing scientific path+hash subset cannot be reconstructed: exact
pre-file inventory was not persisted. Do not repeat reclaim. Do not delete
more files.

Concurrent append-only invariant: preserve the pre-existing scientific
path+hash set as a subset of post-state. Full fingerprint equality is valid only
when the writer is frozen.

## Named consumer

Future Factory agents and the owner, deciding whether to change storage
topology/retention/resolution, and how to operate the collector without
repeating restore/reclaim or credential-less ticks.

## Cheapest falsifier

- Domain policy lacks `DATA_RESOLUTION_ECONOMY`, or introduces a hard global
  candle/tick ban.
- Collector runbook still routes a future agent to restore/reclaim as NEXT.
- Manual production tick still documents bare `uv … tick` without the
  sanctioned `EnvironmentFile`.
- Evidence claims empirical 30d/90d growth while `collector_storage_history.jsonl`
  is absent.

## Non-goals

No production-code change, retention APPLY, VACUUM, archive tier, new DB,
Telegram/pulse timer install, deploy, provider calls, or next atom.

## Terminals

- `NO_STORAGE_ARCHITECTURE_CHANGE_REQUIRED`
- `RETENTION_NO_ACTION_YET`
- Delivery software close is this atom's PR; live pulse timer install is
  Product Horizon `NOW` after merge, not this write set.

## STOP / NEXT

STOP at exact merge gate. NEXT (not this atom): commission existing
`DAILY_COLLECTOR_OWNER_PULSE` on the VPS. Telegram incident alerts stay WATCH.
