---
task_id: COLLECTOR_ORACLE_P99_SCIENTIFIC_DEADLINE_CLOSURE_V1
task_version: '1.0'
status: READY
as_of: '2026-09-02'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 78082974966c3b876403c7001d156cb5febc2ef6
  expected_upstream: origin/main
  expected_upstream_oid: 78082974966c3b876403c7001d156cb5febc2ef6
  expected_branch: cursor/collector-oracle-p99-scientific-deadline-closure-v1
  dirty_mode: ALLOW_REPORTED
objective: Make ObservationSchedule schedulability oracle admit recommended envelopes only when modeled p99_due_lateness fits allowed X lateness; expose x_deadline_headroom_seconds; no VPS/provider/authorize.
managed_write_set:
- docs/tasks/COLLECTOR_ORACLE_P99_SCIENTIFIC_DEADLINE_CLOSURE_V1.md
- src/solana_alpha_lab/factory/collector_schedulability_oracle.py
- tests/test_collector_oracle_p99_scientific_deadline_closure.py
- tests/test_collector_sampling_oracle_applied_probability_repair.py
- docs/reports/collector_oracle_p99_scientific_deadline_closure_v1/a1_owner_readout_v1.md
- docs/evidence/collector_oracle_p99_scientific_deadline_closure_v1/a1_delivery_completion_evidence_v1.json
- docs/evidence/collector_oracle_p99_scientific_deadline_closure_v1/a1_delivery_independent_review_v1.json
- docs/evidence/collector_oracle_p99_scientific_deadline_closure_v1/a1_delivery_factory_fit_v1.json
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
- HARDCODED_ENVELOPE_BYPASS_OF_ORACLE
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
    - docs/evidence/collector_oracle_p99_scientific_deadline_closure_v1/a1_delivery_completion_evidence_v1.json
    - docs/evidence/collector_oracle_p99_scientific_deadline_closure_v1/a1_delivery_independent_review_v1.json
    - docs/evidence/collector_oracle_p99_scientific_deadline_closure_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# COLLECTOR_ORACLE_P99_SCIENTIFIC_DEADLINE_CLOSURE_V1

Generic ObservationSchedule scientific-deadline invariant: recommended live
envelope requires `p99_due_lateness_seconds <= allowed_x_lateness_seconds`.

No VPS mutation. No provider calls. No register/authorize/activate.
Proposal `50b2d070…` must not be authorized.
