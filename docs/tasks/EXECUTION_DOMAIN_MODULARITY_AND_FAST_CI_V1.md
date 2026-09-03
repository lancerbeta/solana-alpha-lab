---
task_id: EXECUTION_DOMAIN_MODULARITY_AND_FAST_CI_V1
task_version: "1.0"
status: READY
as_of: "2026-09-03"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab

git_binding:
  expected_base: b442a763e62e8d4ed8dcfebbdf2c67514d4d1d82
  expected_upstream: origin/main
  expected_upstream_oid: b442a763e62e8d4ed8dcfebbdf2c67514d4d1d82
  expected_branch: cursor/execution-domain-modularity-fast-ci-v1
  dirty_mode: ALLOW_REPORTED

objective: >-
  Enforce the existing PAPER/SHADOW execution domain as a machine-checked
  dependency boundary and move its required tests into one dedicated fast
  exact-head CI lane, while preserving one monorepo, one final validate gate,
  exactly-once canonical test coverage, existing runtime semantics and zero
  live/external authority.

managed_write_set:
  - docs/tasks/EXECUTION_DOMAIN_MODULARITY_AND_FAST_CI_V1.md
  - configs/execution_domain_v1.json
  - configs/ci_test_shards_v1.json
  - scripts/validate_execution_domain.py
  - scripts/run_ci_execution_domain.py
  - scripts/ci_test_partition.py
  - scripts/run_ci_test_shard.py
  - scripts/validate_ci.py
  - scripts/render_ci_workflow.py
  - scripts/owner_attention_gate.py
  - .github/workflows/ci.yml
  - tests/test_execution_domain_modularity_and_fast_ci_v1.py
  - tests/test_ci_test_partition.py
  - tests/test_run_ci_test_shard.py
  - tests/test_ci.py
  - tests/test_baseline.py
  - tests/test_delivery_harness_merge_guard.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/execution_domain_modularity_fast_ci/a1_entry_baseline_v1.json
  - docs/evidence/execution_domain_modularity_fast_ci/a1_coverage_timing_v1.json
  - docs/evidence/execution_domain_modularity_fast_ci/a1_delivery_completion_evidence_v1.json
  - docs/evidence/execution_domain_modularity_fast_ci/a1_delivery_independent_review_v1.json
  - docs/evidence/execution_domain_modularity_fast_ci/a1_delivery_factory_fit_v1.json
  - docs/reports/execution_domain_modularity_fast_ci/a1_owner_readout_v1.md

external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false

stop_conditions:
  - ACTIVE_TIME_GATE_PREEMPTS
  - CONTROL_PLANE_FREEZE_ACTIVE
  - BASE_DRIFT_CHANGES_EXECUTION_OR_CI_PREMISE
  - PRODUCT_RUNTIME_SOURCE_EDIT_REQUIRED
  - EXECUTION_SEMANTICS_CHANGE_REQUIRED
  - SECOND_POSITION_OR_ACCOUNTING_TRUTH_STORE
  - REPLAN_REQUIRED_EXISTING_BOUNDARY_VIOLATION
  - REPLAN_REQUIRED_FAST_LANE_TOO_SLOW
  - REPLAN_REQUIRED_COVERAGE_PARTITION_INVALID
  - REPEATED_MATERIAL_BLOCKER
  - SECOND_CI_ARCHITECTURE_PIVOT
  - NEW_DEPENDENCY_OR_UNPINNED_ACTION
  - TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
  - PATH_BASED_FULL_SUITE_SKIPPING
  - DUPLICATE_TEST_EXECUTION_AS_DESIGN
  - PAID_OR_LARGER_RUNNER
  - CACHE_AS_CLAIMED_FIX
  - BRANCH_PROTECTION_OR_RULESET_MUTATION
  - PROVIDER_API_RPC_WSS
  - CREDENTIAL_VALUE_REQUIRED
  - VPS_OR_DEPLOY_MUTATION_REQUIRED
  - WALLET_SIGNER_TRANSACTION_REQUIRED
  - REAL_FILL_OR_LIVE_CAPITAL_CLAIM
  - CASH_SPEND_REQUIRED
  - AUTOMATIC_MERGE_OR_BRANCH_DELETION

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
      - docs/evidence/execution_domain_modularity_fast_ci/a1_delivery_completion_evidence_v1.json
      - docs/evidence/execution_domain_modularity_fast_ci/a1_delivery_independent_review_v1.json
      - docs/evidence/execution_domain_modularity_fast_ci/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# EXECUTION_DOMAIN_MODULARITY_AND_FAST_CI_V1

Owner pack: `EXECUTION_DOMAIN_MODULARITY_AND_FAST_CI_V1_PRD_SSD` Atom 4.

## Decision delta

Can PAPER/SHADOW execution change and diagnose as one coherent unit with a fast
CI lane while full repository compatibility stays fail-closed?

## Terminal

`EXECUTION_DOMAIN_MODULARITY_FAST_CI_PASS`

## SPEC_ROUTE

`BOTH`

## Acceptance / cheapest falsifiers

1. `scripts/validate_execution_domain.py` prints `EXECUTION_DOMAIN_BOUNDARY: PASS`
   (absolute and relative factory imports checked).
2. `scripts/run_ci_execution_domain.py` prints `EXECUTION_DOMAIN_FAST_TESTS: PASS`.
3. Ordinary shards with `--reserved-manifest` prove
   `EXECUTION ∩ GENERAL = ∅` and union equals canonical discovery
   at module and loaded-case level.
4. Workflow has `validate-execution` needing `validate-core`; final `validate`
   denies non-success including skipped execution.
5. No `src/solana_alpha_lab/factory/` product-runtime edits in the atom diff.

## Non-claims

No live authority, no second repository/service, no path-based full-suite skip,
no alpha/cashflow, no product PAPER/SHADOW semantic change.
