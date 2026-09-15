---
task_id: CTRL_CI_VALIDATE_TIMEOUT_25M_V1
task_version: '1.0'
status: READY
as_of: '2026-09-15'
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: e85b291ff4c5a22a43f3c51438a970fd881c0d21
  expected_upstream: origin/main
  expected_upstream_oid: e85b291ff4c5a22a43f3c51438a970fd881c0d21
  expected_branch: cursor/ctrl-ci-validate-timeout-25m-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Raise GitHub validate job timeout-minutes from 15 to 25 so exact-head and
  main push CI stop losing green runs to shard wall-clock cancel. No shard
  rebalance, no coverage change, no product change.
managed_write_set:
  - docs/tasks/CTRL_CI_VALIDATE_TIMEOUT_25M_V1.md
  - scripts/validate_ci.py
  - .github/workflows/ci.yml
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/control/a1_ci_validate_timeout_25m_completion_v1.json
  - docs/evidence/control/a1_ci_validate_timeout_25m_review_v1.json
  - docs/evidence/control/a1_ci_validate_timeout_25m_factory_fit_v1.json
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - SHARD_REBALANCE_OR_COVERAGE_CHANGE
  - PRODUCT_RUNTIME_CHANGE
  - NEW_RUNNER_OR_PAID_CAPACITY
  - BRANCH_PROTECTION_OR_SETTINGS_CHANGE
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
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
      - docs/evidence/control/a1_ci_validate_timeout_25m_completion_v1.json
      - docs/evidence/control/a1_ci_validate_timeout_25m_review_v1.json
      - docs/evidence/control/a1_ci_validate_timeout_25m_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL_CI_VALIDATE_TIMEOUT_25M_V1

## Objective

One constant: `GITHUB_VALIDATE_TIMEOUT_MINUTES = 25`. Re-render
`.github/workflows/ci.yml`. Leave shard plan, coverage, and product bytes
untouched.

## DoD

- `scripts/validate_ci.py` and rendered `ci.yml` agree on 25 for
  validate-core / validate-execution / validate-tests.
- Aggregator stays at 5 minutes.
- `uv run ... python -B -m unittest tests.test_ci` PASS.
- No runner/settings/product change.

## STOP

Exact owner merge gate after CI. No shard rebalance in this atom.
