---
task_id: FACTORY_PRODUCTION_LINE_CONVERGENCE_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-25'
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
required_review_roles:
  - CODE_REVIEWER
  - ARCHITECTURE_CRITIC
  - GOAL_DOD_CRITIC
  - OWNER_UX_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 971e0a09e600ae3210b07094dd071824708d6bbd
  expected_upstream: origin/main
  expected_upstream_oid: 971e0a09e600ae3210b07094dd071824708d6bbd
  expected_branch: cursor/factory-production-line-convergence-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Reconcile live Factory runtime semantics onto canonical main and make
  normal exact-SHA release refuse a side lineage, race a scheduled tick,
  or rehearse rollback on every success.
managed_write_set:
  - docs/tasks/FACTORY_PRODUCTION_LINE_CONVERGENCE_V1.md
  - docs/tasks/FACTORY_LIVE_MAIN_PARITY_CONVERGENCE_V1.md
  - docs/operator/FACTORY_REMOTE_HOST.md
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/evidence/factory_production_line_convergence_v1/live_delta_disposition_v1.json
  - scripts/factory_live_release.py
  - scripts/observation_schedule.py
  - src/solana_alpha_lab/factory/production_lineage.py
  - src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
  - src/solana_alpha_lab/factory/observation_schedule_store.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - tests/test_factory_production_line_convergence_v1.py
  - tests/test_collector_continuity_boundaries_v1.py
  - docs/evidence/factory_production_line_convergence_v1/delivery_completion_evidence_v1.json
  - docs/evidence/factory_production_line_convergence_v1/delivery_independent_review_v1.json
  - docs/evidence/factory_production_line_convergence_v1/delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - LIVE_DELTA_UNKNOWN
  - SCHEMA_MIGRATION
  - VPS_MUTATION
  - C3_MATERIALIZATION
context_requirements:
  catalog_asset_ids: []
  l2_roles: []
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_production_line_convergence_v1/delivery_completion_evidence_v1.json
      - docs/evidence/factory_production_line_convergence_v1/delivery_independent_review_v1.json
      - docs/evidence/factory_production_line_convergence_v1/delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_PRODUCTION_LINE_CONVERGENCE_V1

Production software must sit on canonical `main` first-parent history.
`FACTORY_LIVE_MAIN_PARITY_CONVERGENCE_V1` is superseded: its merge did not
carry `activation_transition_research_event_proven`.

This atom ports that continuity proof, keeps C3 `--plan-only`, and changes
`scripts/factory_live_release.py` to one forward release with timer quiesce.
Deploy of the merged SHA is a later owner gate. C3 plan-only stays unrun.
