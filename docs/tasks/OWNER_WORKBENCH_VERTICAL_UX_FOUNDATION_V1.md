---
task_id: OWNER_WORKBENCH_VERTICAL_UX_FOUNDATION_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-06"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: f08effba27125d6e23c0ee4de53c0d1ee2ae0cde
  expected_upstream: origin/main
  expected_upstream_oid: f08effba27125d6e23c0ee4de53c0d1ee2ae0cde
  expected_branch: cursor/owner-workbench-vertical-ux-foundation-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  One Pareto UI/UX foundation pass over the existing server-rendered Workbench
  so all five owner surfaces share a Russian-first Visual OS shell: meaning
  first, then known/unknown, then safe action, then inspectable machine truth.
  No frontend rewrite, no new truth source, no Move-3 start.
managed_write_set:
  - docs/tasks/OWNER_WORKBENCH_VERTICAL_UX_FOUNDATION_V1.md
  - docs/contracts/smial_visual_operating_system_v1.md
  - configs/smial_visual_operating_system_v1.yaml
  - src/solana_alpha_lab/factory/owner_language.py
  - src/solana_alpha_lab/factory/visual_os.py
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/research_workbench.py
  - src/solana_alpha_lab/factory/owner_surface.py
  - tests/test_owner_workbench_vertical_ux_foundation_v1.py
  - tests/test_factory_v1_owner_cockpit.py
  - tests/test_owner_operations_cockpit_v1.py
  - tests/test_research_lifecycle_workbench_v1.py
  - tests/test_experiment_evidence_decision_v1.py
  - tests/test_smial_visual_operating_system_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_factory_semantic_operability.py
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/assets/core.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/owner_workbench_vertical_ux_foundation/a1_delivery_completion_evidence_v1.json
  - docs/evidence/owner_workbench_vertical_ux_foundation/a1_delivery_independent_review_v1.json
  - docs/evidence/owner_workbench_vertical_ux_foundation/a1_delivery_factory_fit_v1.json
  - docs/reports/owner_workbench_vertical_ux_foundation/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - VISUAL_READBACK_UNAVAILABLE
  - PRESENTATION_REQUIRES_DOMAIN_REWRITE
  - NEW_FRONTEND_FRAMEWORK_REQUIRED
  - NEW_BACKEND_REQUIRED
  - NEW_DATABASE_REQUIRED
  - RUNTIME_TRANSLATION_REQUIRED
  - AUTHORITY_SEMANTICS_CHANGE_REQUIRED
  - SCIENTIFIC_TRUTH_CHANGE_REQUIRED
  - OPERATIONS_COMMAND_CHANGE_REQUIRED
  - LOCALIZATION_SCOPE_ESCAPE
  - GENERIC_DESIGN_SYSTEM_SCOPE_ESCAPE
  - PARALLEL_WORKTREE_ISOLATION_UNAVAILABLE
  - POST_PARALLEL_REVIEW_REQUIRED
  - REPEATED_MATERIAL_BLOCKER
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
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
    ARCHITECTURE_DECISIONS:
    - docs/contracts/smial_visual_operating_system_v1.md
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# OWNER_WORKBENCH_VERTICAL_UX_FOUNDATION_V1

## Isolation

```text
WORKTREE_PATH = C:\Users\lance\Projects\solana-alpha-lab-uiux
BRANCH = cursor/owner-workbench-vertical-ux-foundation-v1
INITIAL_BASE_SHA = f08effba27125d6e23c0ee4de53c0d1ee2ae0cde
PARALLEL_NON_DEPENDENCY = Telegram/VDS monitoring atom
MERGE_ORDER = SECOND after that atom lands on main
```

Final BASE is post-Telegram/VDS `origin/main`, not this INITIAL_BASE_SHA.

## Entry / Outcome

`SPEC_ROUTE=BOTH` — extend existing Visual OS + owner-language contracts;
do not create a parallel Visual OS.

- `DECISION_DELTA`: owner Workbench surfaces inherit one shell, Russian-first
  labels, summary-before-detail, and progressive disclosure of machine truth.
- `UNCERTAINTY_REMOVED`: whether current five routes can become scannable
  owner workstations without a frontend rewrite or domain-truth change.
- `CAPABILITY_OR_EVIDENCE`: live Web-view before/after at 1440×900 and
  1920×1080 plus focused regressions.
- `STOP`: merge-readiness after first atom is on main; never auto-start
  `SCIENCE_TO_STRATEGY_HANDOFF_V1`.
- `NEXT`: `SCIENCE_TO_STRATEGY_HANDOFF_V1`.
- `REPLAN_TRIGGER`: any stop condition above, or post-parallel Workbench
  conflict that cannot be resolved without domain rewrite.

## Named consumer

Petr, opening `/`, `/research`, `/operations`, `/economics`, `/system`.

## Cheapest falsifier

Live browser: owner cannot state the page question in ~10s, or UNKNOWN
becomes $0 / healthy, or command POST values change.

## Non-goals

No StrategyVersion, VPS, SSH, providers, wallet, i18n framework, SPA,
Playwright/Selenium, mobile-first, Move 3.
