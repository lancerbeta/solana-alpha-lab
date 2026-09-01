---
task_id: COLLECTOR_SAMPLING_ORACLE_APPLIED_PROBABILITY_REPAIR_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-02'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 5c0efd1619f048c61e6f056b83449571e0abfdae
  expected_upstream: origin/main
  expected_upstream_oid: 5c0efd1619f048c61e6f056b83449571e0abfdae
  expected_branch: collector/sampling-oracle-applied-probability-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: Align recommended_inclusion_probability with the applied member cap
  (min(requested, max_supported)), not the capacity ceiling alone. Restore frozen
  commissioning envelope p=0.057 at 114 members/day.
managed_write_set:
- docs/tasks/COLLECTOR_SAMPLING_ORACLE_APPLIED_PROBABILITY_REPAIR_V1.md
- src/solana_alpha_lab/factory/collector_schedulability_oracle.py
- tests/test_collector_sampling_oracle_applied_probability_repair.py
- tests/test_harness_sync_bindings.py
- scripts/harness_sync.py
- scripts/owner_attention_gate.py
- docs/reports/collector_sampling_oracle_applied_probability_repair/a1_owner_readout_v1.md
- catalog/assets/core.yaml
- docs/evidence/collector_sampling_oracle_applied_probability_repair/a1_delivery_completion_evidence_v1.json
- docs/evidence/collector_sampling_oracle_applied_probability_repair/a1_delivery_independent_review_v1.json
- docs/evidence/collector_sampling_oracle_applied_probability_repair/a1_delivery_factory_fit_v1.json
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
    - docs/evidence/collector_sampling_oracle_applied_probability_repair/a1_delivery_completion_evidence_v1.json
    - docs/evidence/collector_sampling_oracle_applied_probability_repair/a1_delivery_independent_review_v1.json
    - docs/evidence/collector_sampling_oracle_applied_probability_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# COLLECTOR_SAMPLING_ORACLE_APPLIED_PROBABILITY_REPAIR_V1

Repair oracle inclusion probability semantics. Proposal `02152e3136ad…` MUST NOT
be authorized. Zero network, zero VPS mutation.
