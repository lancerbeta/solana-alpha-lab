---
task_id: RISK_AND_ECONOMICS_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-07"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: b403c4df836615a68c79453e4c7ba785e5f2e33b
  expected_upstream: origin/main
  expected_upstream_oid: b403c4df836615a68c79453e4c7ba785e5f2e33b
  expected_branch: cursor/risk-and-economics-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make /economics one evidence-safe owner composition over existing
  PaperPlane accounting so Petr can see what PAPER/SHADOW actually measured,
  which costs are in the number, where the result is UNKNOWN, and what
  declared entry-admission risk is proven — without mixing planes or
  claiming NetReturn, owner FCF, LIVE PnL or promotion.
managed_write_set:
  - docs/tasks/RISK_AND_ECONOMICS_V1.md
  - docs/contracts/risk_and_economics_v1.md
  - docs/contracts/trading_operations_workbench_v2.md
  - src/solana_alpha_lab/factory/risk_economics.py
  - src/solana_alpha_lab/factory/paper_plane.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/trading_operations.py
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/owner_language.py
  - tests/test_risk_and_economics_v1.py
  - tests/test_owner_workbench_vertical_ux_foundation_v1.py
  - tests/test_owner_operations_cockpit_v1.py
  - tests/test_factory_v1_owner_cockpit.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_factory_semantic_operability.py
  - configs/execution_domain_v1.json
  - configs/owner_lifecycle_projection_v1.yaml
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/risk_and_economics/a1_delivery_completion_evidence_v1.json
  - docs/evidence/risk_and_economics/a1_delivery_independent_review_v1.json
  - docs/evidence/risk_and_economics/a1_delivery_factory_fit_v1.json
  - docs/reports/risk_and_economics/a1_owner_readout_v1.md
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
  - ACCOUNTING_TRUTH_OWNER_AMBIGUOUS
  - FUZZY_ECONOMIC_SCOPE_IDENTITY
  - STRATEGY_VERSION_CANNOT_BIND_DECLARED_POLICY
  - HISTORICAL_PAPERPLANE_REWRITE_REQUIRED
  - SECOND_ACCOUNTING_OR_RISK_STORE_REQUIRED
  - SECOND_PNL_FORMULA_TREE_REQUIRED
  - NEW_RISK_POLICY_REQUIRED_TO_FINISH
  - GET_ECONOMICS_MUTATES_RUNTIME
  - SEMANTIC_ROUTE_BUDGET_GAP
  - PROVIDER_OR_LIVE_MARKET_READ_REQUIRED
  - MOVE_8_REQUIRED_TO_FINISH_MOVE_7
  - PAPER_SHADOW_CARRIES_PROMOTION_AUTHORITY
  - OWNER_FCF_PROXY_CREATED
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
      - docs/contracts/risk_and_economics_v1.md
      - docs/contracts/trading_operations_workbench_v2.md
    DELIVERY_EVIDENCE:
      - docs/evidence/risk_and_economics/a1_delivery_completion_evidence_v1.json
      - docs/evidence/risk_and_economics/a1_delivery_independent_review_v1.json
      - docs/evidence/risk_and_economics/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# RISK_AND_ECONOMICS_V1

## ENTRY

```text
START_WITH_PATCH
SPEC_ROUTE=BOTH
ROUTE=DIRECT_CURSOR_DELIVERY
PREDECESSOR=SYSTEM_OPERABILITY_SURFACE_V2 canonical on origin/main
BASE=b403c4df836615a68c79453e4c7ba785e5f2e33b
TIME_GATES=none due
```

PAPER/SHADOW accounting and `/economics` already exist. Missing capability is
evidence-safe composition, accounting/mark/path semantic repair, declared-risk
interpretation, owner boundaries, and Catalog/semantic ownership.

## FALSIFIERS (fresh bytes)

```text
A EVIDENCE MIXING          YES — one reconciled_net_pnl_usd across classes
B OPEN MARK NET = GROSS    YES — record_position_mark copies gross to net
C UNKNOWN PATH METRICS     YES — drawdown skips UNKNOWN; streak can stay KNOWN
D /economics OWNERSHIP     YES — thin render of paper_shadow_operations
```

## DECISION_DELTA

Owner economics is a derived `RiskEconomicsProjectionV1` over PaperPlane
source rows. Reconciled and open-mark stay separate planes. PAPER and SHADOW
stay separate scopes. Mixed evidence is not summed. Declared
`max_open_positions` is an entry-admission readback of the same
`OPEN_RISK_STATES` set execution already uses.

## UNCERTAINTY_REMOVED

Whether `/economics` can be read as total profit, LIVE cash, NetReturn,
owner FCF, or portfolio risk.

## CAPABILITY_OR_EVIDENCE

Petr on GET `/economics` in ≤30s sees scoped PAPER/SHADOW model evidence,
modeled-fee coverage, UNKNOWN/conflict, declared entry-admission status,
and explicit non-claims.

## STOP

Exact-head CI + merge-readiness. No deploy. No Move 8.

## NEXT

Owner merge phrase after readiness. Then guarded merge. Do not start
`MARKET_DATA_AWARENESS_V1`.

## REPLAN_TRIGGER

Repeated mixed-PnL leak, GET mutation, second formula tree, semantic route
budget breach, or any promotion/FCF proxy.
