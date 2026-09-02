---
task_id: FACTORY_PRODUCTION_CLOCK_PACING_ADAPTER_PARITY_REPAIR_V1
task_version: '1.0'
status: READY
as_of: '2026-09-02'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: f6dd1175a578103ed3df463219b8040c23fb535e
  expected_upstream: origin/main
  expected_upstream_oid: f6dd1175a578103ed3df463219b8040c23fb535e
  expected_branch: cursor/factory-production-clock-pacing-adapter-parity-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: Pause contaminated commissioning #3; repair ObservationSchedule production clock/pacing adapter so RECENT+SEARCH progress under real >=3s pacing; PR+CI; stop at merge gate; no VPS deploy of repair.
managed_write_set:
- docs/tasks/FACTORY_PRODUCTION_CLOCK_PACING_ADAPTER_PARITY_REPAIR_V1.md
- src/solana_alpha_lab/factory/observation_provider_pacing.py
- src/solana_alpha_lab/factory/observation_scheduler.py
- scripts/observation_schedule.py
- tests/test_factory_production_clock_pacing_adapter_parity_repair.py
- docs/reports/factory_production_clock_pacing_adapter_parity_repair_v1/a1_owner_readout_v1.md
- docs/evidence/factory_production_clock_pacing_adapter_parity_repair_v1/a1_commissioning3_pause_record_v1.json
- docs/evidence/factory_production_clock_pacing_adapter_parity_repair_v1/a1_delivery_completion_evidence_v1.json
- docs/evidence/factory_production_clock_pacing_adapter_parity_repair_v1/a1_delivery_independent_review_v1.json
- docs/evidence/factory_production_clock_pacing_adapter_parity_repair_v1/a1_delivery_factory_fit_v1.json
- catalog/assets/core.yaml
external_caps:
  network: false
  credentials: false
  external_system: true
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- MATERIAL_BUDGET_DRIFT
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- LIVE_PAUSE_SAFETY_FAILED
- RUNTIME_ORACLE_REPLAN_REQUIRED
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
    - docs/evidence/factory_production_clock_pacing_adapter_parity_repair_v1/a1_delivery_completion_evidence_v1.json
    - docs/evidence/factory_production_clock_pacing_adapter_parity_repair_v1/a1_delivery_independent_review_v1.json
    - docs/evidence/factory_production_clock_pacing_adapter_parity_repair_v1/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_PRODUCTION_CLOCK_PACING_ADAPTER_PARITY_REPAIR_V1

Owner pause authority:
`OK FACTORY_PAUSE_COMMISSIONING_3_PRODUCTION_CLOCK_PACING_BUG_V1`
schedule=`1ac23901907ecc8a481ec8ce595f751b774c53221244407cbdee634cdadc5893`
activation=`ACT-1AC23901907ECC8A`
reason=`SEARCH_STARVED_BY_PRODUCTION_CLOCK_PACING_ADAPTER`

No resume. No abort on VPS in this atom. No repaired-code VPS deploy.
No new campaign. No oracle/scientific retune. No Forge.
