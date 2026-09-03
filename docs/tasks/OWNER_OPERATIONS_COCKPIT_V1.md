---
task_id: OWNER_OPERATIONS_COCKPIT_V1
task_version: "1.0"
status: READY
as_of: "2026-09-03"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: 3f0a671083f57ce4ef8a38c0471766310f89b206
  expected_upstream: origin/main
  expected_upstream_oid: 3f0a671083f57ce4ef8a38c0471766310f89b206
  expected_branch: cursor/owner-operations-cockpit-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Earn Workbench OPERATIONS and bounded PAPER/SHADOW ECONOMICS surfaces that
  answer ordinary owner questions and execute Atom-2 operator commands through
  FactoryApplication only, without Workbench opening SQLite or adopting a new UI
  package; MARKET stays hidden.

managed_write_set:
  - docs/tasks/OWNER_OPERATIONS_COCKPIT_V1.md
  - src/solana_alpha_lab/factory/application.py
  - src/solana_alpha_lab/factory/workbench.py
  - src/solana_alpha_lab/factory/cockpit.py
  - src/solana_alpha_lab/factory/paper_shadow_operations.py
  - configs/factory_v1_owner_cockpit_v1.yaml
  - catalog/schemas/factory_v1_owner_cockpit.schema.json
  - tests/test_owner_operations_cockpit_v1.py
  - tests/test_factory_v1_owner_cockpit.py
  - tests/test_factory_ordinary_market_hypothesis.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/owner_operations_cockpit/a1_delivery_completion_evidence_v1.json
  - docs/evidence/owner_operations_cockpit/a1_delivery_independent_review_v1.json
  - docs/evidence/owner_operations_cockpit/a1_delivery_factory_fit_v1.json
  - docs/reports/owner_operations_cockpit/a1_owner_readout_v1.md

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
  - NEW_UI_FRAMEWORK
  - WORKBENCH_DIRECT_SQLITE
  - MARKET_NAV_UNHIDE
  - LIVE_CAPITAL_OR_FCF_SURFACE
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
      - docs/evidence/owner_operations_cockpit/a1_delivery_completion_evidence_v1.json
      - docs/evidence/owner_operations_cockpit/a1_delivery_independent_review_v1.json
      - docs/evidence/owner_operations_cockpit/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# OWNER_OPERATIONS_COCKPIT_V1

Owner pack: `PAPER_SHADOW_OPERATOR_VERTICAL_EXECUTION_PACK_V2` Atom 3.

## Decision delta

Can the owner understand and safely operate PAPER/SHADOW without Git/SQLite
archaeology?

## Terminal

`OWNER_OPERATIONS_COCKPIT_PASS`

## SPEC_ROUTE

`BOTH`
