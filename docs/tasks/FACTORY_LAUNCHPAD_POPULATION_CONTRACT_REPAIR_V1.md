---
task_id: FACTORY_LAUNCHPAD_POPULATION_CONTRACT_REPAIR_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-01'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 1acad20db6af363df98b71da7e0a0d8d9ef8c5f6
  expected_upstream: origin/main
  expected_upstream_oid: 1acad20db6af363df98b71da7e0a0d8d9ef8c5f6
  expected_branch: factory/launchpad-population-contract-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: Pause the invalid live activation whose source predicate never matched
  Jupiter live Tokens V2 shape; add FIELD-LAUNCHPAD-001; repair campaign preflight
  and registry semantics without aliasing first-pool source; leave broken schedule
  as immutable audit evidence.
managed_write_set:
- docs/tasks/FACTORY_LAUNCHPAD_POPULATION_CONTRACT_REPAIR_V1.md
- src/solana_alpha_lab/factory/tokens_v2_typed_projection.py
- src/solana_alpha_lab/factory/collector_campaign_preflight.py
- src/solana_alpha_lab/factory/discovery_evidence_release.py
- configs/observation_primitive_registry_v1.yaml
- catalog/schemas/observation_primitive_registry_v1.schema.json
- catalog/assets/core.yaml
- docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
- tests/test_launchpad_population_contract_repair.py
- tests/test_tokens_v2_typed_projection.py
- docs/evidence/factory_launchpad_population_contract_repair/a1_commissioning_pause_evidence_v1.json
- docs/evidence/factory_launchpad_population_contract_repair/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_launchpad_population_contract_repair/a1_delivery_independent_review_v1.json
- docs/evidence/factory_launchpad_population_contract_repair/a1_delivery_factory_fit_v1.json
- docs/reports/factory_launchpad_population_contract_repair/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- LIVE_PAUSE_SAFETY_FAILED
- MATERIAL_BUDGET_DRIFT
- RESUME_BROKEN_SCHEDULE
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
    - docs/evidence/factory_launchpad_population_contract_repair/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_launchpad_population_contract_repair/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_launchpad_population_contract_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_LAUNCHPAD_POPULATION_CONTRACT_REPAIR_V1

Pause `490c21b6…` / `ACT-490C21B69A1F8F8F`; prove provider calls stop; deliver
`FIELD-LAUNCHPAD-001` contract repair. Do not start replacement live campaign in
this atom.
