---
task_id: OWNER_WORKBENCH_PREDEPLOY_EXPERIENCE_QA_V1
task_version: "1.1"
status: IN_PROGRESS
as_of: "2026-09-08"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 52808d613d02f8e96a85aea2668e98d80aec0d51
  expected_upstream: origin/main
  expected_upstream_oid: 52808d613d02f8e96a85aea2668e98d80aec0d51
  expected_branch: cursor/owner-workbench-predeploy-experience-qa-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  One browser-first owner-experience QA pass over the six already-shipped
  Workbench surfaces on current main/live SHA: screenshots, independent
  critiques, one severity-ranked backlog, one presentation-only repair
  batch, and same-path AFTER review. Historical atom name says predeploy;
  review baseline is the already-deployed Workbench. No new VPS mutation.
managed_write_set:
  - docs/tasks/OWNER_WORKBENCH_PREDEPLOY_EXPERIENCE_QA_V1.md
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/visual_os.py
  - src/solana_alpha_lab/factory/owner_surface.py
  - src/solana_alpha_lab/factory/owner_language.py
  - tests/test_owner_workbench_predeploy_experience_qa_v1.py
  - tests/test_owner_workbench_vertical_ux_foundation_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_market_data_awareness_v1.py
  - tests/test_factory_semantic_operability.py
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - configs/factory_semantic_operability_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/owner_workbench_predeploy_experience_qa/a1_delivery_completion_evidence_v1.json
  - docs/evidence/owner_workbench_predeploy_experience_qa/a1_delivery_independent_review_v1.json
  - docs/evidence/owner_workbench_predeploy_experience_qa/a1_delivery_factory_fit_v1.json
  - docs/evidence/owner_workbench_predeploy_experience_qa/a1_before_after_inventory_v1.json
  - docs/evidence/owner_workbench_predeploy_experience_qa/a1_severity_ranked_backlog_v1.json
  - docs/reports/owner_workbench_predeploy_experience_qa/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - DOMAIN_TRUTH_CHANGE_REQUIRED
  - AUTHORITY_SEMANTICS_CHANGE_REQUIRED
  - COMMAND_POST_VALUE_CHANGE_REQUIRED
  - NEW_FRONTEND_FRAMEWORK_REQUIRED
  - NEW_BACKEND_OR_DATABASE_REQUIRED
  - VPS_OR_DEPLOY_MUTATION_REQUIRED
  - PROVIDER_CALL_REQUIRED
  - WALLET_SIGNER_TX_OR_CASH
  - UNKNOWN_PRESENTED_AS_ZERO_OR_HEALTHY
  - REPEATED_MATERIAL_BLOCKER
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
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
    ARCHITECTURE_DECISIONS:
      - docs/contracts/smial_visual_operating_system_v1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/owner_workbench_predeploy_experience_qa/a1_delivery_completion_evidence_v1.json
      - docs/evidence/owner_workbench_predeploy_experience_qa/a1_delivery_independent_review_v1.json
      - docs/evidence/owner_workbench_predeploy_experience_qa/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OWNER_WORKBENCH_PREDEPLOY_EXPERIENCE_QA_V1

## PATCH (Git reality)

```text
ENTRY=START_WITH_PATCH
SPEC_ROUTE=PRD_LITE
ROUTE=DIRECT_CURSOR_DELIVERY
NAME_KEPT=OWNER_WORKBENCH_PREDEPLOY_EXPERIENCE_QA_V1
NAME_SEMANTICS=HISTORICAL_ATOM_ID_NOT_PREDEPLOY_GATE
REVIEW_BASELINE_SHA=52808d613d02f8e96a85aea2668e98d80aec0d51
LIVE_READBACK=FACTORY_WORKBENCH_GET_ONLY
VPS_MUTATION=FORBIDDEN
```

The atom id still says `predeploy`. That is not a blocker. Workbench is
already on Factory at the same SHA as `origin/main`. Live GET is readback
baseline only. Repair lands in Git and is verified on the same six routes
locally; this atom does not deploy.

## Surfaces

```text
HOME        /
RESEARCH    /research
MARKET      /market
OPERATIONS  /operations
ECONOMICS   /economics
SYSTEM      /system
```

Plus two or three representative second-level drilldowns already linked
from those pages (research kind/detail, technical disclosure). No new
surface and no new product meaning.

## Entry / Outcome

- `DECISION_DELTA`: one bounded presentation repair batch after a
  severity-ranked owner-experience review of the six live surfaces.
- `UNCERTAINTY_REMOVED`: whether Petr can scan each surface in ~10s without
  UNKNOWN becoming $0/healthy, without command POST values changing, and
  without a frontend rewrite.
- `CAPABILITY_OR_EVIDENCE`: BEFORE/AFTER screenshots at 1440×900 for six
  surfaces plus representative drilldowns; independent owner-UX + code
  critiques; ranked backlog; focused tests.
- `STOP`: merge-readiness. No deploy. No provider. No VPS mutation.
- `NEXT`: owner merge phrase after readiness. Do not start Hypothesis Forge
  or a new deploy atom from this PR.
- `REPLAN_TRIGGER`: any stop condition, or a finding that only a domain or
  authority change can fix.

## Named consumer

Petr, using the six Workbench routes as daily instruments.

## Cheapest falsifier

Browser: page question not visible in ~10s; UNKNOWN shown as $0 or
«исправна»; command `name="command" value=` tokens change; GET mutates
store; repair requires a new framework.

## Non-goals

No new Visual OS, no SPA, no i18n framework, no Playwright/Selenium as a
product dependency, no mobile-first, no domain/estimand/PIT change, no
command semantics change, no OperationalStore schema change, no
collector/RDP/HOT90/deploy/systemd change, no Hypothesis Generator.

## Visual proof

Operator-local PNG inventory under
`local/owner_workbench_predeploy_experience_qa/` (gitignored). Canonical
Git record is `a1_before_after_inventory_v1.json` with path, viewport,
surface, and sha256. Screenshots are not Catalog truth.

## MODEL_EFFORT

`LUNA_MAX` for the review+repair chain. `ROUTINE_NO_SWITCH` at
merge-readiness.
