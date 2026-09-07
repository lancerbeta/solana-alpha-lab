---
task_id: SYSTEM_OPERABILITY_SURFACE_V2
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-07"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 2df9fbcfb657d69d4f29d4dbef515552708b384c
  expected_upstream: origin/main
  expected_upstream_oid: 2df9fbcfb657d69d4f29d4dbef515552708b384c
  expected_branch: cursor/system-operability-surface-v2
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make /system one owner operability composition over existing collector,
  systemd, durability and deploy-marker sources so Petr can decide whether
  Factory may run unattended, without a monitoring platform or Workbench
  mutation buttons.
managed_write_set:
  - docs/tasks/SYSTEM_OPERABILITY_SURFACE_V2.md
  - docs/contracts/system_operability_surface_v2.md
  - src/solana_alpha_lab/factory/system_operability.py
  - src/solana_alpha_lab/factory/observation_schedule_store.py
  - src/solana_alpha_lab/factory/operability_watch.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/owner_language.py
  - src/solana_alpha_lab/factory/owner_surface.py
  - src/solana_alpha_lab/factory/owner_daily_attention.py
  - scripts/show_system_operability.py
  - scripts/factory_operability_watch.py
  - tests/test_system_operability_surface_v2.py
  - tests/test_observation_schedule_store.py
  - tests/test_owner_workbench_vertical_ux_foundation_v1.py
  - tests/test_factory_v1_owner_cockpit.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_factory_semantic_operability.py
  - tests/test_catalog_canonical_binding_discovery.py
  - tests/test_owner_attention_and_change_feed_v1.py
  - tests/test_factory_unattended_operability_closure_v1.py
  - catalog/schemas/factory_semantic_operability.schema.json
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/system_operability_surface/a1_delivery_completion_evidence_v1.json
  - docs/evidence/system_operability_surface/a1_delivery_independent_review_v1.json
  - docs/evidence/system_operability_surface/a1_delivery_factory_fit_v1.json
  - docs/reports/system_operability_surface/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PREDECESSOR_NOT_CANONICALLY_INTEGRATED
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - SECOND_MONITORING_STORE_OR_SERVICE_REQUIRED
  - SEM_SYSTEM_ROUTE_REQUIRED
  - GET_SYSTEM_MUTATES_RUNTIME_STATE
  - PROCESS_ALIVE_INFERRED_FROM_GIT_CONFIG
  - WORKBENCH_SYSTEM_MUTATION_BUTTONS
  - PROVIDER_CREDENTIAL_WALLET_OR_SPEND_REQUIRED
  - LIVE_HOST_MUTATION_REQUIRED
context_requirements:
  catalog_asset_ids: []
  l2_roles:
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
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - delivery-harness/policies/solana-alpha-lab.md
      - docs/contracts/system_operability_surface_v2.md
      - docs/contracts/owner_attention_and_change_feed_v1.md
      - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
    DELIVERY_EVIDENCE:
      - docs/evidence/system_operability_surface/a1_delivery_completion_evidence_v1.json
      - docs/evidence/system_operability_surface/a1_delivery_independent_review_v1.json
      - docs/evidence/system_operability_surface/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# SYSTEM_OPERABILITY_SURFACE_V2

## SPEC_ROUTE

`BOTH` — this file is the exact Git task contract;
`docs/contracts/system_operability_surface_v2.md` is the durable
product contract. Semantic route reused: `SEM-REMOTE-OPS-RECOVERY`.

## ENTRY VERDICT

`START_WITH_PATCH`

Fresh Git:

- live `origin/main` = `2df9fbcfb657d69d4f29d4dbef515552708b384c`
  (PR #277 OWNER_ATTENTION_AND_CHANGE_FEED_V1 is canonical on main)
- no due unresolved active-time gate
- collector packet, ObservationSchedule, operability watch, remote-ops
  and unattended runbook already exist
- `/system` currently infers `process_alive=True` from runtime.yaml +
  OperationalStore, and ObservationSchedule GET opens writable SQLite

## DECISION_DELTA

`/system` becomes the owner current-health surface. Production-lite
runtime remains capability inventory, not current health owner.

## UNCERTAINTY_REMOVED

Whether Petr can leave Factory technically running without him, and
which recovery route to follow when he cannot.

## CAPABILITY_OR_EVIDENCE

`SystemOperabilityProjectionV2` + readonly ObservationSchedule wrap +
System-local attention for Move 5.

## STOP

Merge-readiness owner phrase. Do not start `RISK_AND_ECONOMICS_V1`.
Do not deploy or mutate the live VPS.

## NEXT

WATCH = `RISK_AND_ECONOMICS_V1` after owner use, not automatically.

## DoD

Owner EXECUTE packet sections 32–35 and 47. PASS only when vertical
A/B/C/D, read-safety, semantic Git and isolated CODE/GOAL/ARCHITECTURE
plus Factory Fit FULL_REVIEW reach the merge gate.
