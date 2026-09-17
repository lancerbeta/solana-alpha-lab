---
task_id: HORIZON_SCOPED_SCIENTIFIC_ELIGIBILITY_V1
task_version: '1.0'
status: READY
as_of: '2026-09-18'
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
  expected_base: 6515e8b3a880065327a43448f592fe4101026dfb
  expected_upstream: origin/main
  expected_upstream_oid: 6515e8b3a880065327a43448f592fe4101026dfb
  expected_branch: cursor/horizon-scoped-scientific-eligibility-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Land one versioned ScientificEligibilityProjection so X300-valid X_ELIGIBLE
  is the scientific denominator, Y completeness cannot shrink N, ExperimentSpec
  1.3 carries explicit required_outcomes, and the historical selection receipt
  is a FULL_LIFECYCLE_COMPLETENESS caveat rather than a global Forge START veto.

managed_write_set:
  - docs/tasks/HORIZON_SCOPED_SCIENTIFIC_ELIGIBILITY_V1.md
  - configs/scientific_eligibility_projection_v1.yaml
  - catalog/schemas/experiment_spec_v1_3.schema.json
  - catalog/schemas/scientific_eligibility_projection_v1.schema.json
  - catalog/catalog_manifest.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - src/solana_alpha_lab/factory/scientific_eligibility_projection.py
  - src/solana_alpha_lab/factory/experiment_spec.py
  - src/solana_alpha_lab/factory/lane_classifier.py
  - src/solana_alpha_lab/factory/hfic_selection_robustness_gate.py
  - src/solana_alpha_lab/factory/hfic_preflight.py
  - src/solana_alpha_lab/factory/hfic_control_integrity.py
  - src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py
  - src/solana_alpha_lab/factory/live_cohort_to_forge.py
  - src/solana_alpha_lab/factory/hfic_representation_probe.py
  - src/solana_alpha_lab/factory/hfic_released_trajectory_projection.py
  - src/solana_alpha_lab/factory/hfic_session.py
  - .agents/skills/independent-hypothesis-critic/SKILL.md
  - docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
  - docs/contracts/normalized_trajectory_v1_capability_contract.md
  - docs/contracts/normalized_trajectory_representation_probe_v1.md
  - tests/test_scientific_eligibility_projection_v1.py
  - tests/test_hfic_selection_robustness_gate_v1.py
  - tests/test_hfic_representation_probe.py
  - tests/test_hfic_released_trajectory_projection_v1.py
  - tests/test_hfic_fresh_control_decision_integrity_closure_v1.py
  - tests/test_normalized_trajectory_probe_preregistration_v1.py
  - tests/test_lane_classifier.py
  - docs/reports/horizon_scoped_scientific_eligibility/a1_owner_readout_v1.md
  - docs/evidence/horizon_scoped_scientific_eligibility/a1_delivery_completion_evidence_v1.json
  - docs/evidence/horizon_scoped_scientific_eligibility/a1_delivery_independent_review_v1.json
  - docs/evidence/horizon_scoped_scientific_eligibility/a1_delivery_factory_fit_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - FORGE_EXECUTION
  - CRITIC_INPUT_PACKET_1_5
  - SCHEDULER_OR_CENSUS_MUTATION
  - HISTORICAL_RECEIPT_REWRITE
  - Y_TYPED_VALUE_READ
  - COMPLETE_CASE_POPULATION
  - M1_CALIBRATION_EDIT
  - GLOBAL_START_NEW_SESSION_SELECTION_VETO
  - PRIMARY_Y_PARSER
  - PROVIDER_CALL
  - REAL_MONEY_OR_PROMOTION

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
      - docs/evidence/horizon_scoped_scientific_eligibility/a1_delivery_completion_evidence_v1.json
      - docs/evidence/horizon_scoped_scientific_eligibility/a1_delivery_independent_review_v1.json
      - docs/evidence/horizon_scoped_scientific_eligibility/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HORIZON_SCOPED_SCIENTIFIC_ELIGIBILITY_V1

SEMANTIC_PREMISE_HIGH_RISK: true
SPEC_ROUTE=DESIGN_SPEC.

Owner START after DESIGN checkpoint `PATCH`. One PR. Stop at merge-readiness.

## Task Outcome Brief

- **Owner decision:** Base scientific population = X300-valid X_ELIGIBLE.
  Future Y completeness must never retroactively remove a member. Outcome
  missingness is coverage against that denominator and may only fail-close
  an experiment into the existing data/science-option route.
- **Product outcome:** one pure `ScientificEligibilityProjection` plus
  ExperimentSpec 1.3 `required_outcomes`, scoped selection-receipt
  interpretation, and CONTROL/NT floors bound to `base_x_population.n`.
- **Named consumer:** Forge preflight, Independent Critic B5, lane
  classifier / execute, NORMALIZED_TRAJECTORY probe.
- **Cheapest falsifier:** synthetic + C1-shape tests proving 475/148/327,
  no Y typed-value reads, no complete-case shrink, no global START veto,
  horizon-specific spec is not auto-vetoed, 1.3 required_outcomes, Critic
  packet stays 1.4.
- **Terminal:** reviews, exact-head CI, merge-readiness, owner phrase.
  Post-merge read-only C1 semantic acceptance is the next atom, not this one.
- **Non-goals:** Forge execution; packet 1.5; scheduler/census/parquet/
  latest.json mutation; M1 edits; IPW; collection redesign; primary_y parser.

## Frozen rules

1. `base_x` = `candidate_state == X_ELIGIBLE` AND X300
   `FIELD-LIQUIDITY-USD-001 == OBSERVED` AND PIT `<= due_at + allowed_lateness`.
   Do not require the entire X300 bundle.
2. `base_x.n` is always the scientific denominator.
   `outcome_readiness` = `COMPLETE | MISSINGNESS_UNRESOLVED | UNSPECIFIED`.
3. ExperimentSpec 1.3 adds `required_outcomes`. No Critic packet 1.5.
4. Historical selection receipt is byte-immutable
   `FULL_LIFECYCLE_COMPLETENESS` caveat. No global START STOP.
   Veto only when required Y point set equals the bound schedule Y set.
5. CONTROL/NT floor and equality use `base_x.n`. Keep NT M semantics.
6. M1 out of scope.
7. Historical corpus/receipts immutable.
8. C1-shape acceptance: 475 / 148 / 327 without Y typed values.

## Delivery notes

- `DECISION_DELTA`: scientific N is X300-valid X_ELIGIBLE; Y missingness
  cannot shrink it.
- `UNCERTAINTY_REMOVED`: Forge no longer treats full-ladder completeness
  as the base population or as a global START veto.
- `CAPABILITY_OR_EVIDENCE`: projection + 1.3 schema + consumer rewiring.
- `STOP`: merge-readiness / owner phrase.
- `NEXT`: post-merge read-only canonical C1 semantic acceptance. No Forge.
- `REPLAN_TRIGGER`: need to mutate scheduler rows; need packet 1.5;
  C1-shape predicates cannot reproduce 475/148/327.
- `SPEC_ROUTE=DESIGN_SPEC`
