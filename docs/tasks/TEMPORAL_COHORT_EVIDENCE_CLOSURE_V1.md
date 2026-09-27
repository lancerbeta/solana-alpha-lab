---
task_id: TEMPORAL_COHORT_EVIDENCE_CLOSURE_V1
task_version: '1.0'
status: READY
as_of: '2026-09-28'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 662b3d654a995699b681be57addda358737556f0
  expected_upstream: origin/main
  expected_upstream_oid: 662b3d654a995699b681be57addda358737556f0
  expected_branch: cursor/temporal-cohort-evidence-closure-v1
  dirty_mode: FORBIDDEN

objective: >-
  One temporal question keeps pooled, cohort and calendar slices in the same
  journaled result, frozen critic packet and fixed-time consumer. Calculation
  moves to HFIC_TEMPORAL_DISCOVERY_CALC_V2 without a new scientific look,
  without changing grounded CALCULATION_VERSION, and without rewriting V1 bytes.

managed_write_set:
  - docs/tasks/TEMPORAL_COHORT_EVIDENCE_CLOSURE_V1.md
  - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
  - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
  - tests/test_hfic_temporal_discovery_v1.py
  - tests/test_hfic_temporal_production_runner_v1.py
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - catalog/assets/core.yaml
  - docs/reports/temporal_cohort_evidence_closure/a1_owner_readout_v1.md
  - docs/evidence/temporal_cohort_evidence_closure/a1_delivery_completion_evidence_v1.json
  - docs/evidence/temporal_cohort_evidence_closure/a1_delivery_independent_review_v1.json
  - docs/evidence/temporal_cohort_evidence_closure/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - MARKET_HYPOTHESIS_FORGE
  - LIVE_RESEARCH_STORE_MUTATION
  - LIVE_MEMORY_POLICY_CHANGE
  - NEW_CAPABILITY_OR_CLI
  - GROUNDED_CALCULATION_VERSION_CHANGE
  - NORMALIZED_TRAJECTORY_V1_CHANGE
  - MERGE_IN_THIS_ATOM

context_requirements:
  catalog_asset_ids:
    - MODULE-HFIC-TEMPORAL-DISCOVERY-001
    - DOC-HYPOTHESIS-FORGE-OPERATOR-001
  l2_roles:
    - LIFECYCLE
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE:
      - MODULE-HFIC-TEMPORAL-DISCOVERY-001
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE:
      - src/solana_alpha_lab/factory/hfic_temporal_discovery.py
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/hfic_grounded_discovery.py
    DELIVERY_EVIDENCE:
      - docs/evidence/temporal_cohort_evidence_closure/a1_delivery_completion_evidence_v1.json
      - docs/evidence/temporal_cohort_evidence_closure/a1_delivery_independent_review_v1.json
      - docs/evidence/temporal_cohort_evidence_closure/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

## Decision

DECISION_DELTA: temporal results now carry a descriptive by_cohort slice beside pooled and calendar blocks.
UNCERTAINTY_REMOVED: a cohort with several dates, overlapping cohorts, and a missing target are visible without a second look.
CAPABILITY_OR_EVIDENCE: same journal result, V2 calculation revision, freeze packet and DocumentRunner summary.
STOP: no market Forge, no live store or memory writes, no merge.
NEXT: owner phrase only after machine merge-readiness; S3 is a later decision.
REPLAN_TRIGGER: a second repair of this same evidence boundary.
