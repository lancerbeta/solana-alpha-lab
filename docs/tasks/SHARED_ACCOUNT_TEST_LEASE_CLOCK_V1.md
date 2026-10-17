---
task_id: SHARED_ACCOUNT_TEST_LEASE_CLOCK_V1
task_version: '1.0'
status: READY
as_of: '2026-10-17'
owner: GOAL_OWNER
allowed_routes: [DIRECT_CLAUDE_CODE_DELIVERY]
required_review_roles: [CODE_REVIEWER]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 15dbebd998697996a75cb07ed21fccde94832ff6
  expected_upstream: origin/main
  expected_upstream_oid: 15dbebd998697996a75cb07ed21fccde94832ff6
  expected_branch: claude/shared-account-test-lease-clock-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Remove a calendar time bomb in one test: the resolve lease was taken on the
  fixed test clock (2026-10-17T00:30Z, expiring 00:32Z) while
  resolve_restore_marker() fences against the wall clock, so main CI fails
  LEASE_FENCED on every run after that minute.
managed_write_set:
  - docs/tasks/SHARED_ACCOUNT_TEST_LEASE_CLOCK_V1.md
  - docs/evidence/shared_account_test_lease_clock_v1/**
  - tests/test_observation_shared_account_budget_v1.py
  - catalog/assets/**
  - catalog/catalog_manifest.yaml
  - catalog/generated/**
  - docs/generated/**
  - docs/PROJECT_MAP.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - STOP_EXACT_HEAD_CI_AND_MACHINE_READINESS_THEN_EXACT_OWNER_MERGE_PHRASE
  - STOP_ANY_PRODUCT_CODE_CHANGE
context_requirements:
  catalog_asset_ids: []
  l2_roles: [DELIVERY_EVIDENCE]
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/shared_account_test_lease_clock_v1/completion.json
      - docs/evidence/shared_account_test_lease_clock_v1/independent-review.json
      - docs/evidence/shared_account_test_lease_clock_v1/factory-fit.json
    HISTORICAL_CONTEXT: []
---

# SHARED_ACCOUNT_TEST_LEASE_CLOCK_V1

Owner EXECUTE 17.10.2026: nano test-only fix after post-merge CI of #412 failed
in shard 2 on `test_commissioning_includes_spend_after_prepare_and_refuses_stale_or_restore`
(`LEASE_FENCED`), unrelated to #412. SPEC_ROUTE: NONE. Factory Fit: FAST_PATH.

- DECISION_DELTA: main CI is no longer red by wall-clock date.
- UNCERTAINTY_REMOVED: failure is a fixed-clock lease versus wall-clock fence, not a store defect.
- CAPABILITY_OR_EVIDENCE: the original test fails now and passes with the resolve lease on the wall clock (19/19 in module).
- STOP: exact-head CI plus readiness; NEXT: post-merge readback of #412 and this PR.
- Rollback: revert the one test line. No product code changes.
