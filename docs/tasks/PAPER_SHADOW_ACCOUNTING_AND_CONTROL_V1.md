---
task_id: PAPER_SHADOW_ACCOUNTING_AND_CONTROL_V1
task_version: "1.0"
status: READY
as_of: "2026-09-03"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 2038abf80500b9a52e9f95657c998d0db9af8eab
  expected_upstream: origin/main
  expected_upstream_oid: 2038abf80500b9a52e9f95657c998d0db9af8eab
  expected_branch: cursor/paper-shadow-accounting-and-control-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Make the single SQLite PAPER/SHADOW plane a durable operator runtime:
  Decimal accounting with explicit evidence classes, execution event lineage,
  derived operations metrics (loss streak/drawdown/UNKNOWN preserved), and
  idempotent operator commands (pause/resume/close-one/close-all/stop-drain)
  with stale close-all snapshot protection and restart readback.

managed_write_set:
  - docs/tasks/PAPER_SHADOW_ACCOUNTING_AND_CONTROL_V1.md
  - src/solana_alpha_lab/factory/paper_plane.py
  - src/solana_alpha_lab/factory/paper_shadow_operations.py
  - src/solana_alpha_lab/factory/paper_shadow_commands.py
  - scripts/factory_paper_shadow_operator_smoke.py
  - tests/test_paper_shadow_accounting_and_control_v1.py
  - tests/fixtures/paper_shadow_accounting_control/strategy_v1_1_accounting.yaml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/evidence/paper_shadow_accounting_and_control/a1_delivery_completion_evidence_v1.json
  - docs/evidence/paper_shadow_accounting_and_control/a1_delivery_independent_review_v1.json
  - docs/evidence/paper_shadow_accounting_and_control/a1_delivery_factory_fit_v1.json
  - docs/reports/paper_shadow_accounting_and_control/a1_owner_readout_v1.md

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
  - SECOND_RUNTIME_STORE
  - REAL_FILL_OR_NETRETURN_CLAIM
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - REPEATED_MATERIAL_BLOCKER

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
      - docs/evidence/paper_shadow_accounting_and_control/a1_delivery_completion_evidence_v1.json
      - docs/evidence/paper_shadow_accounting_and_control/a1_delivery_independent_review_v1.json
      - docs/evidence/paper_shadow_accounting_and_control/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# PAPER_SHADOW_ACCOUNTING_AND_CONTROL_V1

Owner pack: `PAPER_SHADOW_OPERATOR_VERTICAL_EXECUTION_PACK_V2` Atom 2.

## Decision delta

Is the single SQLite PAPER/SHADOW plane durable under ordinary position
management, UNKNOWN marks, pause/close-all, and restart?

## Terminal

`PAPER_SHADOW_ACCOUNTING_CONTROL_PASS`

## SPEC_ROUTE

`BOTH`
