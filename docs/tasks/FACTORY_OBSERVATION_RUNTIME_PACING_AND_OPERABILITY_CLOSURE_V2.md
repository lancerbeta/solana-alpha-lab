---
task_id: FACTORY_OBSERVATION_RUNTIME_PACING_AND_OPERABILITY_CLOSURE_V2
task_version: '1.0'
status: READY
as_of: '2026-09-02'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 2a54438deef22ee1a325cf1c43a16d002d66cae3
  expected_upstream: origin/main
  expected_upstream_oid: 2a54438deef22ee1a325cf1c43a16d002d66cae3
  expected_branch: cursor/factory-observation-runtime-pacing-closure-v2
  dirty_mode: ALLOW_REPORTED
objective: Close ObservationSchedule runtime pacing/oracle/due-pressure commissioning defect after SEARCH starvation; no replacement live campaign in this atom.
managed_write_set:
- docs/tasks/FACTORY_OBSERVATION_RUNTIME_PACING_AND_OPERABILITY_CLOSURE_V2.md
- src/solana_alpha_lab/factory/observation_provider_pacing.py
- src/solana_alpha_lab/factory/due_pressure.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- src/solana_alpha_lab/factory/collector_schedulability_oracle.py
- src/solana_alpha_lab/factory/collector_read_model.py
- src/solana_alpha_lab/factory/collector_operational_packet.py
- src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
- scripts/observation_schedule.py
- tests/test_observation_runtime_pacing_closure_v2.py
- tests/test_collector_sampling_oracle_applied_probability_repair.py
- tests/test_observation_schedule_commissioning.py
- tests/test_observation_scheduler.py
- catalog/assets/core.yaml
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- MATERIAL_BUDGET_DRIFT
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- REPLAN_REQUIRED_NO_VIABLE_FREE_TIER_ENVELOPE
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
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# FACTORY_OBSERVATION_RUNTIME_PACING_AND_OPERABILITY_CLOSURE_V2

Owner authority granted to pause schedule `7db1c77a…` / `ACT-7DB1C77A6F7AF4F3` only.
No resume, no replacement campaign, no VPS ABORTED_SAFETY mutation in this atom.
