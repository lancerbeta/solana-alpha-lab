---
task_id: OBSERVATION_RUNTIME_COMPOSITION_PARITY_V1
task_version: "1.0"
status: READY
as_of: "2026-09-04"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 1de19ef378d9c08d3f4ebb4d3b81c9d0e99ab836
  expected_upstream: origin/main
  expected_upstream_oid: 1de19ef378d9c08d3f4ebb4d3b81c9d0e99ab836
  expected_branch: cursor/observation-runtime-composition-parity-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Earn a deterministic zero-network P0–P2 production-composition parity proof
  for the ObservationSchedule tick path by reusing real CLI/runtime-config/
  authority/store/scheduler/read-model code and replacing only physical
  nondeterminism through process-local test overrides; preserve production
  authority and scientific semantics; no platformization.

managed_write_set:
  - docs/tasks/OBSERVATION_RUNTIME_COMPOSITION_PARITY_V1.md
  - src/solana_alpha_lab/factory/observation_schedule_composition.py
  - scripts/observation_schedule.py
  - scripts/observation_runtime_composition_parity.py
  - tests/test_observation_runtime_composition_parity_v1.py
  - tests/test_factory_production_clock_pacing_adapter_parity_repair.py
  - tests/fixtures/observation_schedule/composition_parity_provider_v1.json
  - configs/ci_test_shards_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/reports/observation_runtime_composition_parity_v1/a1_owner_readout_v1.md
  - docs/evidence/observation_runtime_composition_parity_v1/a1_delivery_completion_evidence_v1.json
  - docs/evidence/observation_runtime_composition_parity_v1/a1_delivery_independent_review_v1.json
  - docs/evidence/observation_runtime_composition_parity_v1/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - A4_NOT_MERGED_OR_READBACK
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - EQUIVALENT_CAPABILITY_ALREADY_EXISTS
  - PRODUCTION_CONFIG_OR_SCHEMA_WIDENING_REQUIRED
  - SCHEDULER_SEMANTICS_CHANGE_REQUIRED_FOR_TEST
  - STORE_OR_PUBLISHER_SEMANTICS_CHANGE_REQUIRED_FOR_TEST
  - SCIENTIFIC_ORACLE_OR_POPULATION_DECISION_CHANGE_REQUIRED
  - EXTERNAL_PROVIDER_SEMANTICS_UNRESOLVED
  - NETWORK_OR_CREDENTIAL_ACCESS_REQUIRED
  - PACKAGE_ADOPTION_REQUIRED
  - DEPLOYMENT_OR_VPS_ACTION_REQUIRED
  - SECOND_ARCHITECTURE_PIVOT
  - REPEATED_MATERIAL_BLOCKER
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - SIMULATOR_FRAMEWORK_EMERGING
  - REPLAN_REQUIRED_COMPOSITION_BOUNDARY_NOT_NARROW
  - REPLAN_REQUIRED_REAL_RUNTIME_DEFECT

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
      - docs/evidence/observation_runtime_composition_parity_v1/a1_delivery_completion_evidence_v1.json
      - docs/evidence/observation_runtime_composition_parity_v1/a1_delivery_independent_review_v1.json
      - docs/evidence/observation_runtime_composition_parity_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OBSERVATION_RUNTIME_COMPOSITION_PARITY_V1

Owner pack: `OBSERVATION_RUNTIME_COMPOSITION_PARITY_V1_PRD_SSD_V2`.

## Decision delta

Can the actual production ObservationSchedule tick composition preserve
historical composition invariants (#238/#240/#242) under process-local
physical overrides without a production fake-mode switch?

## Binding

- Post-A4 main: `1de19ef378d9c08d3f4ebb4d3b81c9d0e99ab836` (PR #254 merge)
- Post-merge CI: run `33806506235` SUCCESS
- Route: `DIRECT_CURSOR_DELIVERY`
- SPEC_ROUTE: `BOTH`

## Terminal

`OBSERVATION_RUNTIME_COMPOSITION_PARITY_PASS`

## Non-claims

P3 live commissioning, long-run reliability, provider forever-compat, alpha,
cashflow, OS/systemd supervision.
