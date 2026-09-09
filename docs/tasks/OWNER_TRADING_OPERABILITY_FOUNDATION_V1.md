---
task_id: OWNER_TRADING_OPERABILITY_FOUNDATION_V1
task_version: "1.0"
status: IN_PROGRESS
as_of: "2026-09-09"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 62527018dca6f8a98a5722b71ce09c21f6aedd74
  expected_upstream: origin/main
  expected_upstream_oid: 62527018dca6f8a98a5722b71ce09c21f6aedd74
  expected_branch: cursor/owner-trading-operability-foundation-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Give Petr a gitless PAPER/SHADOW operating envelope: versioned
  TradingRuntimePolicyV1 in the existing PaperPlane store, one serialized
  admission boundary, and a workstation Workbench that shows current
  requested/runtime/effective risk without a new service, LIVE, or policy UI.
managed_write_set:
  - docs/tasks/OWNER_TRADING_OPERABILITY_FOUNDATION_V1.md
  - docs/contracts/trading_runtime_policy_v1.md
  - docs/contracts/trading_operations_workbench_v2.md
  - docs/contracts/risk_and_economics_v1.md
  - docs/contracts/science_to_strategy_handoff_v1.md
  - docs/contracts/smial_visual_operating_system_v1.md
  - catalog/schemas/trading_runtime_policy_v1.schema.json
  - catalog/schemas/strategy_version_v1_1.schema.json
  - configs/trading_runtime_policy_v1.yaml
  - configs/execution_domain_v1.json
  - src/solana_alpha_lab/factory/trading_runtime_policy.py
  - src/solana_alpha_lab/factory/paper_plane.py
  - src/solana_alpha_lab/factory/paper_shadow_operations.py
  - src/solana_alpha_lab/factory/trading_operations.py
  - src/solana_alpha_lab/factory/risk_economics.py
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/visual_os.py
  - src/solana_alpha_lab/factory/owner_language.py
  - src/solana_alpha_lab/factory/owner_surface.py
  - src/solana_alpha_lab/factory/research_workbench.py
  - scripts/trading_runtime_policy.py
  - tests/test_trading_runtime_policy_v1.py
  - tests/test_trading_runtime_admission_concurrency_v1.py
  - tests/test_owner_trading_operability_workbench_v1.py
  - tests/test_trading_runtime_policy_backup_restore_v1.py
  - tests/test_research_lifecycle_workbench_v1.py
  - tests/test_owner_workbench_vertical_ux_foundation_v1.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - tests/test_factory_semantic_operability.py
  - configs/factory_semantic_operability_v1.yaml
  - catalog/fixtures/semantic_route_gold_queries_v1.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/owner_trading_operability_foundation/a1_delivery_completion_evidence_v1.json
  - docs/evidence/owner_trading_operability_foundation/a1_delivery_independent_review_v1.json
  - docs/evidence/owner_trading_operability_foundation/a1_delivery_factory_fit_v1.json
  - docs/reports/owner_trading_operability_foundation/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - DUE_ACTIVE_TIME_GATE_PREEMPTS
  - OVERLAPPING_CANONICAL_RUNTIME_POLICY_EXISTS
  - SECOND_TRUTH_DATABASE_OR_SERVICE_REQUIRED
  - ATOMIC_ADMISSION_NEEDS_PARALLEL_RISK_ENGINE
  - CURRENT_RUNTIME_VALUES_MUST_LIVE_IN_GIT
  - UNKNOWN_EXPOSURE_MUST_BE_ZERO
  - PAPER_SHADOW_ISOLATION_IMPOSSIBLE
  - CRASH_RETRY_CANNOT_RETAIN_ADMISSION
  - WORKBENCH_REQUIRES_FRONTEND_REWRITE
  - SEMANTIC_ROUTE_BUDGET_CONFLICT
  - SCIENTIFIC_ESTIMAND_MUST_CHANGE
  - REQUESTED_VS_EFFECTIVE_NOTIONAL_CANNOT_BE_DISTINCT
  - PROVIDER_WALLET_LIVE_OR_DEPLOY_REQUIRED
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
      - docs/contracts/trading_runtime_policy_v1.md
      - docs/contracts/trading_operations_workbench_v2.md
      - catalog/schemas/strategy_version_v1_1.schema.json
    DELIVERY_EVIDENCE:
      - docs/evidence/owner_trading_operability_foundation/a1_delivery_completion_evidence_v1.json
      - docs/evidence/owner_trading_operability_foundation/a1_delivery_independent_review_v1.json
      - docs/evidence/owner_trading_operability_foundation/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OWNER_TRADING_OPERABILITY_FOUNDATION_V1

## SPEC_ROUTE

`BOTH` — this file is the exact Git task contract;
`docs/contracts/trading_runtime_policy_v1.md` is the durable product
contract. No new semantic route: reuse `SEM-OWNER-LIFECYCLE` and
`SEM-VISUAL-OPERATING-SYSTEM`.

## ENTRY VERDICT

```text
START_WITH_PATCH
ROUTE=DIRECT_CURSOR_DELIVERY
BASE=9044db6b1b65614f55c074c481fb0dfd323ca2e1
DESIGN_BASELINE=19ad057614f0fd4aa4313b409606d205ff9cb290 (ancestor)
TIME_GATES=none due
SEMANTIC=SEM-OWNER-LIFECYCLE reuse
```

Fresh Git has StrategyVersion v1.1, PaperPlane admission, operator
commands, TRADING_OPERATIONS_WORKBENCH_V2, RISK_AND_ECONOMICS_V1,
Visual OS tokens, and `paper_plane_state.sqlite` in the mutable backup
set. It does **not** contain a canonical overlapping runtime
capital/risk policy. ADOPT PaperPlane + operator_commands +
OPEN_RISK_STATES + PRE_TRADE_RISK_SNAPSHOT + HFIC-style append-only
hash chain (WRAP into PaperPlane, not ResearchStore).

## ARCHITECTURE FREEZE

Storage owner is **PaperPlaneStore** (`local/factory_v1/paper_plane_state.sqlite`),
not `operational_state.sqlite`. Admission and policy APPLY serialize
through one SQLite `BEGIN IMMEDIATE` boundary. A second database would
be a STOP.

PAPER and SHADOW have independent revision chains. LIVE cannot resolve
TradingRuntimePolicyV1 as authority.

Absent table/row = `NOT_CONFIGURED_STRATEGY_ONLY` (strategy-only
admission). Schema creation ≠ enablement. Invalid stored policy =
`RUNTIME_POLICY_INVALID` fail-closed for NEW admissions; EXIT continues.

GET Workbench remains readonly and creates neither table, row, nor file.

## DECISION_DELTA

Routine PAPER/SHADOW operating envelope moves from Git StrategyVersion
edits to an append-only runtime policy consumed atomically at ENTER.

## UNCERTAINTY_REMOVED

Whether concurrent ENTERs can oversubscribe; whether runtime caps can
silently enlarge StrategyVersion; whether Workbench can show current
risk without Git archaeology.

## CAPABILITY_OR_EVIDENCE

TradingRuntimePolicyV1 + serialized admission + gitless SHOW/CHECK/APPLY
+ workstation Workbench projection.

## STOP

Exact merge gate after critics, Factory Fit, exact-head CI.

## NEXT

Separate owner-authorized PAPER/SHADOW policy initialization after merge
and deploy/smoke. No VPS apply in this atom.
