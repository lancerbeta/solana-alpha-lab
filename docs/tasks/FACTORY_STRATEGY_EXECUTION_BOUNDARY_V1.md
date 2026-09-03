---
task_id: FACTORY_STRATEGY_EXECUTION_BOUNDARY_V1
task_version: "1.0"
status: READY
as_of: "2026-09-03"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: df1fd8ae4a2f45bbe304a394caa1266872cbfd5f
  expected_upstream: origin/main
  expected_upstream_oid: df1fd8ae4a2f45bbe304a394caa1266872cbfd5f
  expected_branch: cursor/factory-strategy-execution-boundary-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Separate scientific signal/exit logic from the generic PAPER/SHADOW execution
  boundary via StrategyVersion v1.1 + SignalDecision/ExitDecision contracts,
  activation_epoch binding, signal-id position identity, and SQLite-compatible
  migration, while preserving legacy StrategyVersion v1.0 commissioning behavior.

managed_write_set:
  - docs/tasks/FACTORY_STRATEGY_EXECUTION_BOUNDARY_V1.md
  - catalog/schemas/strategy_version_v1_1.schema.json
  - catalog/schemas/signal_decision_v1.schema.json
  - catalog/schemas/exit_decision_v1.schema.json
  - src/solana_alpha_lab/factory/strategy_runtime.py
  - src/solana_alpha_lab/factory/paper_plane.py
  - tests/test_factory_strategy_execution_boundary_v1.py
  - tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml
  - tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_b.yaml
  - tests/fixtures/factory_strategy_execution_boundary/signal_decision_enter_a.json
  - tests/fixtures/factory_strategy_execution_boundary/signal_decision_enter_b_same_mint.json
  - tests/fixtures/factory_strategy_execution_boundary/signal_decision_no_enter.json
  - tests/fixtures/factory_strategy_execution_boundary/signal_decision_unknown.json
  - tests/fixtures/factory_strategy_execution_boundary/signal_decision_blocked.json
  - tests/fixtures/factory_strategy_execution_boundary/signal_decision_future_available.json
  - tests/fixtures/factory_strategy_execution_boundary/exit_decision_exit.json
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/factory_strategy_execution_boundary/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_strategy_execution_boundary/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_strategy_execution_boundary/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_strategy_execution_boundary/a1_owner_readout_v1.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - PROVIDER_API_RPC_WSS_REQUIRED
  - CREDENTIAL_VALUE_REQUIRED
  - VPS_OR_DEPLOY_MUTATION_REQUIRED
  - PACKAGE_ADOPTION_REQUIRED
  - WALLET_SIGNER_TRANSACTION_REQUIRED
  - CASH_SPEND_REQUIRED
  - OBSERVATION_RDP_OR_C4_MUTATION
  - FORGE_OR_HOLDOUT_CONSUMPTION
  - SECOND_POSITION_MODEL
  - REAL_FILL_OR_NETRETURN_CLAIM
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - REPEATED_MATERIAL_BLOCKER
  - UNIVERSAL_FEATURE_EXPRESSION_DSL
  - V1_0_COMPATIBILITY_REWRITE

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
      - docs/evidence/factory_strategy_execution_boundary/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_strategy_execution_boundary/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_strategy_execution_boundary/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_STRATEGY_EXECUTION_BOUNDARY_V1

Owner pack: `PAPER_SHADOW_OPERATOR_VERTICAL_EXECUTION_PACK_V2` Atom 1.

## Decision delta

Future promoted hypotheses hand frozen `SignalDecision` / `ExitDecision` into one
PAPER/SHADOW runtime without the engine knowing scientific feature names.

## Named consumer

First future hypothesis that passes confirmatory promotion after live corpus/Forge.

## Cheapest falsifier

Two synthetic v1.1 candidates with structurally different producers emitting the same
`SignalDecision` interface, plus one legacy v1.0 commissioning strategy.

## Terminal

`STRATEGY_EXECUTION_BOUNDARY_PASS`

## SPEC_ROUTE

`BOTH`
