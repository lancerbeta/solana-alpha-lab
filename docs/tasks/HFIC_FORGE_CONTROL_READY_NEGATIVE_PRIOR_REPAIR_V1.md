---
task_id: HFIC_FORGE_CONTROL_READY_NEGATIVE_PRIOR_REPAIR_V1
task_version: '1.0'
status: READY
as_of: '2026-09-19'
owner: GOAL_OWNER

allowed_routes:
  - DIRECT_CURSOR_DELIVERY

required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC

expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: "f0425162af393b790d6f6fb4c3006c7669778d29"
  expected_upstream: origin/main
  expected_upstream_oid: "f0425162af393b790d6f6fb4c3006c7669778d29"
  expected_branch: cursor/hfic-forge-control-ready-negative-prior-repair-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Stop forge_control_ready from treating eligible scientific HARD_CLOSE/PARK
  prior-memory states as operational search-memory quarantine. Keep real
  quarantine membership fail-closed, leave memory-policy and CONTROL packet
  bound unchanged, and leave CURRENT_REPRESENTATION_CONTROL-first routing
  unchanged.

managed_write_set:
  - docs/tasks/HFIC_FORGE_CONTROL_READY_NEGATIVE_PRIOR_REPAIR_V1.md
  - src/solana_alpha_lab/factory/live_cohort_to_forge.py
  - tests/test_live_cohort_to_forge_operational_closure_v1.py
  - docs/reports/hfic_forge_control_ready_negative_prior_repair/a1_owner_readout_v1.md
  - docs/evidence/hfic_forge_control_ready_negative_prior_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/hfic_forge_control_ready_negative_prior_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/hfic_forge_control_ready_negative_prior_repair/a1_delivery_factory_fit_v1.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - MEMORY_POLICY_MUTATION
  - EVIDENCE_EPOCH_MUTATION
  - CONTROL_PACKET_BOUND_CHANGE
  - HARD_CLOSE_OR_PARK_DROP
  - SESSION_QUARANTINE_OR_RESTORE
  - HYPOTHESIS_FORGE_SLASH
  - RESEARCHSTORE_WRITE_ON_ACCEPTANCE
  - PROVIDER_OR_VPS

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
      - docs/evidence/hfic_forge_control_ready_negative_prior_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_forge_control_ready_negative_prior_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_forge_control_ready_negative_prior_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_FORGE_CONTROL_READY_NEGATIVE_PRIOR_REPAIR_V1

SEMANTIC_PREMISE_HIGH_RISK: true

SPEC_ROUTE=NONE. Exact owner atom: remove the forge_control_ready disposition
deny-list that conflates eligible HARD_CLOSE/PARK with quarantine.

SCIENCE_CRITIC is outside `required_review_roles` schema enum and is launched
isolated; answers are bound in the owner readout and architecture findings.

## Task Outcome Brief

- **Owner decision:** Eligible scientific HARD_CLOSE/PARK must remain
  search-memory priors. Operational quarantine stays membership-only.
- **Product outcome:** C2 `forge-control-ready` can PASS while CONTROL packet
  capacity remains a separate fail-closed gate at 16384.
- **Named consumer:** `scripts/discovery_evidence_release.py forge-control-ready`
  after LIVE CORPUS import, before `/hypothesis-forge CURRENT_REPRESENTATION_CONTROL`.
- **Cheapest falsifier:** production-shaped unit in
  `tests/test_live_cohort_to_forge_operational_closure_v1.py` plus read-only
  real C2 `forge-control-ready`.
- **Terminal:** `DONE_FOR_MERGE` after reviews, exact-head CI and merge-readiness.
  Stop before owner merge phrase.
- **Non-goals:** raising CONTROL bound, dropping HARD_CLOSE/PARK, quarantining
  60FB, changing memory-policy identity, running `/hypothesis-forge`.
- **Evidence budget:** disposable fixtures + one read-only local data_plane
  acceptance. No ResearchStore writes on acceptance.
- **SPEC_ROUTE=NONE**

## Decision capsule

- `DECISION_DELTA`: forge_control_ready keeps session-id quarantine integrity
  (CHECK_A) and stops denying eligible HARD_CLOSE/PARK (CHECK_B).
- `UNCERTAINTY_REMOVED`: C2 forge-control-ready FAIL was a contract bug, not
  a real 60FB quarantine.
- `CAPABILITY_OR_EVIDENCE`: FORGE_CONTROL_READY on imported C2; CONTROL packet
  may still typed-STOP on `MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND`.
- `STOP`: merge-readiness; owner phrase gate.
- `NEXT`: separate CONTROL packet capacity atom.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FAST_PATH`. Restores already-designed prior-memory
semantics on one gate. `PRODUCT_HORIZON_NOW=NONE`. `CAPABILITY_RADAR_NOW=NONE`.
