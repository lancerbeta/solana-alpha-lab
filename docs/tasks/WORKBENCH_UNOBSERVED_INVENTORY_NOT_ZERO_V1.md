---
task_id: WORKBENCH_UNOBSERVED_INVENTORY_NOT_ZERO_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-26"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: ac5b761e4746cebc81b416a843a8a23080d71649
  expected_upstream: origin/main
  expected_upstream_oid: 0e0b4793b1f511c589d51bb53c5bb2ea7c048faa
  expected_branch: cursor/workbench-unobserved-inventory-not-zero-v1
  dirty_mode: FORBIDDEN
objective: >-
  Stop the owner Workbench from printing a measured zero when Operations
  has no runtime source or Research projection is UNAVAILABLE, and keep
  English WHY_NOW out of the closed attention scan line.
managed_write_set:
  - docs/tasks/WORKBENCH_UNOBSERVED_INVENTORY_NOT_ZERO_V1.md
  - docs/evidence/workbench_unobserved_inventory_not_zero/a1_delivery_completion_evidence_v1.json
  - docs/evidence/workbench_unobserved_inventory_not_zero/a1_delivery_independent_review_v1.json
  - docs/evidence/workbench_unobserved_inventory_not_zero/a1_delivery_factory_fit_v1.json
  - src/solana_alpha_lab/factory/workbench.py
  - tests/test_owner_trading_operability_workbench_v1.py
  - tests/test_owner_workbench_predeploy_experience_qa_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - catalog/assets/core.yaml
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - DOMAIN_TRUTH_CHANGE_REQUIRED
  - COMMAND_POST_VALUE_CHANGE_REQUIRED
  - SHADOW_ENVELOPE_ROW_CHANGE_REQUIRED
  - REHOST_ALLOWLIST_CHANGE_REQUIRED
  - NEW_FRONTEND_FRAMEWORK_REQUIRED
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - OWNER_UX_CRITIC
context_requirements:
  catalog_asset_ids: []
  l2_roles: []
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
      - docs/evidence/workbench_unobserved_inventory_not_zero/a1_delivery_completion_evidence_v1.json
      - docs/evidence/workbench_unobserved_inventory_not_zero/a1_delivery_independent_review_v1.json
      - docs/evidence/workbench_unobserved_inventory_not_zero/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# WORKBENCH_UNOBSERVED_INVENTORY_NOT_ZERO_V1

## Entry / Outcome

- `DECISION_DELTA`: one presentation repair. Absent Operations inventory and an unavailable Research projection are not numeric zeros. The closed attention line is the Russian next action.
- `UNCERTAINTY_REMOVED`: whether `NOT_PRESENT` / `UNAVAILABLE` can be read as an empty counted book, and whether the first attention line is English prose.
- `CAPABILITY_OR_EVIDENCE`: focused HTML tests. A present source with no active rows still shows `ACTIVE POSITIONS = 0`.
- `STOP`: merge-readiness, then one guarded merge. No deploy.
- `NEXT`: none from this PR. SHADOW envelope row and rehost yaml stay out.
- `REPLAN_TRIGGER`: a fix that needs domain truth, command POST values, the SHADOW row, or the rehost allowlist.

## Non-goals

No SHADOW row change. No `configs/owner_lifecycle_projection_v1.yaml` allowlist edit. No new frontend. No command semantics change. No deploy.
