---
task_id: TRADING_OPERATIONS_WORKBENCH_V2
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-07"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: dbe007f374f6ce1520c33094c5733e2d774a15c5
  expected_upstream: origin/main
  expected_upstream_oid: dbe007f374f6ce1520c33094c5733e2d774a15c5
  expected_branch: cursor/trading-operations-workbench-v2
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make /operations one owner-operable OBSERVE → DIAGNOSE → ACT&VERIFY
  vertical over existing PaperPlane, commands and LifecycleProjection,
  without a parallel V2 runtime, activation workflow, or Git snapshots.
managed_write_set:
  - docs/tasks/TRADING_OPERATIONS_WORKBENCH_V2.md
  - docs/contracts/trading_operations_workbench_v2.md
  - src/solana_alpha_lab/factory/trading_operations.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/read_model.py
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/owner_language.py
  - src/solana_alpha_lab/factory/paper_plane.py
  - src/solana_alpha_lab/factory/paper_shadow_operations.py
  - tests/test_trading_operations_workbench_v2.py
  - tests/test_owner_operations_cockpit_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_factory_semantic_operability.py
  - tests/test_owner_workbench_vertical_ux_foundation_v1.py
  - tests/test_factory_v1_owner_cockpit.py
  - configs/execution_domain_v1.json
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/schemas/factory_semantic_operability.schema.json
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/trading_operations_workbench/a1_delivery_completion_evidence_v1.json
  - docs/evidence/trading_operations_workbench/a1_delivery_independent_review_v1.json
  - docs/evidence/trading_operations_workbench/a1_delivery_factory_fit_v1.json
  - docs/reports/trading_operations_workbench/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - PREDECESSOR_NOT_CANONICALLY_INTEGRATED
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - OPERATIONS_TRUTH_OWNER_AMBIGUOUS
  - NEW_INCOMPATIBLE_POSITION_LIFECYCLE_REQUIRED
  - LINEAGE_REQUIRES_MINT_TIME_OR_FILENAME_INFERENCE
  - WORKBENCH_DIRECT_SQLITE
  - ACTIVATION_WORKFLOW_MUST_BE_DESIGNED
  - PROVIDER_CREDENTIAL_WALLET_OR_SPEND_REQUIRED
  - SECOND_DATABASE_OR_SERVICE_REQUIRED
  - MOVE_5_6_7_REQUIRED_FOR_VALUE
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
      - delivery-harness/policies/solana-alpha-lab.md
      - docs/contracts/trading_operations_workbench_v2.md
      - catalog/schemas/strategy_version_v1_1.schema.json
    DELIVERY_EVIDENCE:
      - docs/evidence/trading_operations_workbench/a1_delivery_completion_evidence_v1.json
      - docs/evidence/trading_operations_workbench/a1_delivery_independent_review_v1.json
      - docs/evidence/trading_operations_workbench/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# TRADING_OPERATIONS_WORKBENCH_V2

## SPEC_ROUTE

`BOTH` — this file is the exact Git task contract;
`docs/contracts/trading_operations_workbench_v2.md` is the durable
product contract. No new semantic route unless gold-query tests prove
`SEM-OWNER-LIFECYCLE` / `SEM-AUTHORITY-BOUNDARIES` cannot disambiguate.

## ENTRY VERDICT

`START_WITH_PATCH`

Fresh Git:

- live `origin/main` = `dbe007f374f6ce1520c33094c5733e2d774a15c5`
- design baseline `6a8522aa` (PR #274 SCIENCE_TO_STRATEGY_HANDOFF_V1) is an
  ancestor; PR #275 landed after it
- no due unresolved active-time gate
- `OWNER_OPERATIONS_COCKPIT_V1`, PaperPlane, PAPER/SHADOW commands and
  LifecycleProjection already exist

PATCH reason: cockpit surfaces exist but GET `/operations` and `/economics`
bootstrap PaperPlane, Git StrategyVersion can be read as a running bot,
and the owner cannot follow Signal→Risk→Execution→readback as one vertical.

## DECISION_DELTA

Derived `TradingOperationsProjectionV2` is rebuilt from Git StrategyVersion
plus existing PaperPlane/events/commands. GET never creates runtime bytes.
Activation stays inspectable, not createable. V1 cockpit remains the
lower-level PAPER/SHADOW projection consumed by V2.

## UNCERTAINTY_REMOVED

Petr can answer what is actually executing, where the path stopped, what
is safe now, and what changed after a command — without SQLite, SSH or
Git archaeology.

## CAPABILITY_OR_EVIDENCE

Vertical scenarios A–K on contract-real PaperPlane fixtures plus GET
non-mutation on `/`, `/research`, `/operations`, `/economics`, `/system`.

## NON-GOALS

No new activation workflow; no LIVE; no provider; no deploy/VPS; no
wallet; no global Attention Feed; no new DB/service; no watchlist
platform; no owner FCF.

## MODEL_EFFORT_RECOMMENDATION

`SOL_XHIGH` for contracts/boundaries; `LUNA_MAX` for bounded UI/projection
work.
