---
task_id: EXACT_HEAD_CI_WALL_CLOCK_HEADROOM_V1
task_version: '1.0'
status: VALIDATED
as_of: '2026-08-30'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 7c04306ae3169df557a4a589e1a8eb4d07890ac2
  expected_upstream: origin/main
  expected_upstream_oid: 7c04306ae3169df557a4a589e1a8eb4d07890ac2
  expected_branch: cursor/exact-head-ci-wall-clock-headroom-v1
  dirty_mode: ALLOW_REPORTED
objective: Restore at least 30 percent real exact-head CI wall-clock headroom against
  the fixed 900-second reference budget without deleting, skipping, weakening, or
  duplicating validation coverage, and without product, provider, or Settings changes.
managed_write_set:
- docs/tasks/EXACT_HEAD_CI_WALL_CLOCK_HEADROOM_V1.md
- .github/workflows/ci.yml
- delivery-harness/harness.yaml
- delivery-harness/templates/portable-core/delivery-harness/harness.yaml
- scripts/validate_ci.py
- scripts/validate_baseline.py
- scripts/profile_test_wall_clock.py
- scripts/ci_test_partition.py
- scripts/run_ci_test_shard.py
- scripts/render_ci_workflow.py
- configs/ci_test_shards_v1.json
- tests/test_profile_test_wall_clock.py
- tests/test_ci_test_partition.py
- tests/test_run_ci_test_shard.py
- tests/test_ci.py
- tests/test_baseline.py
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/evidence/exact_head_ci_wall_clock_headroom/a1_delivery_completion_evidence_v1.json
- docs/evidence/exact_head_ci_wall_clock_headroom/a1_delivery_independent_review_v1.json
- docs/evidence/exact_head_ci_wall_clock_headroom/a1_delivery_factory_fit_v1.json
- docs/evidence/exact_head_ci_wall_clock_headroom/a1_baseline_receipt_v1.json
- docs/evidence/exact_head_ci_wall_clock_headroom/a1_coverage_equivalence_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- BRANCH_PROTECTION_OR_RULESET_MUTATION
- NEW_DEPENDENCY_OR_UNPINNED_ACTION
- PAID_OR_LARGER_RUNNER
- PROVIDER_API_RPC_WSS
- PRODUCT_OR_BRIDGE_BEHAVIOR_CHANGE
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- SHARED_MUTABLE_TEST_STATE
- CACHE_AS_CLAIMED_PERFORMANCE_FIX
- WALLET_BUILD_EXECUTE_TRANSACTION
- AUTOMATIC_MERGE_OR_BRANCH_DELETION
context_requirements:
  catalog_asset_ids: []
  l2_roles: []
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
    - docs/evidence/exact_head_ci_wall_clock_headroom/a1_delivery_completion_evidence_v1.json
    - docs/evidence/exact_head_ci_wall_clock_headroom/a1_delivery_independent_review_v1.json
    - docs/evidence/exact_head_ci_wall_clock_headroom/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# EXACT_HEAD_CI_WALL_CLOCK_HEADROOM_V1

## SPEC_ROUTE

`NONE` — this file is the exact task contract. Owner PRD+SSD is the attached
authority source for thresholds and routes.

## PRD-lite

- Owner decision: restore real exact-head headroom `>=30%` vs fixed `900s`
  (`critical_path_seconds <=630`, target `<=600`) without coverage loss.
- Named consumer: Delivery Harness exact-head `validate` gate.
- Cheapest falsifier: exact-head GitHub CI critical-path timing plus
  module/test/skip and core-command equivalence receipt.
- Non-goals: branch protection, Harness redesign, product/provider/runtime,
  paid runners, cache-as-fix, test weakening.
- Replan trigger: safe hotspot plus at most four shards cannot reach `630s`,
  or coverage equivalence cannot be proved.

## Frozen baseline (post-Bridge authoritative main)

- `base_commit_sha`: `7c04306ae3169df557a4a589e1a8eb4d07890ac2`
- `base_tree_sha`: `48f8c8bbde330a16892b17edd6fc91beae2a5995`
- Bridge merge: `0e733c5a4434f936d51b27f3bdc49735c78be3a5` (PR #212)
- Ancestor floor: `c795952e166a2c5f0f5c967b84ee6457c3b0dc80`
- Workflow blob: `2d3e7ce33c9ffd4ea8614abe3894495ecd304a22`
- `validate_ci.py` blob: `43f64edc7eeedbac8ef320822d1c2bc23a57976c`
- `validate_baseline.py` blob: `749e960e6d7f7db70adf99b90d5621f356dd02a5`
- Current workflow timeout already `25` minutes (temporary measurement guard
  already on main; not a success claim)
- Post-Bridge Bridge-merge CI: job ~789s; `Ran 3662 tests in 735.725s`
- Authoritative current-main CI run `33284120701`: job critical path `1178s`;
  validate step `1171s`; `Ran 3720 tests in 1116.100s`; `OK (skipped=75)`
- Module inventory at base: `329` `tests/test_*.py` files

## Decision delta

`DECISION_DELTA`: real exact-head wall-clock reserve restored without omitting
or duplicating validation work.

`UNCERTAINTY_REMOVED`: whether post-Bridge/current main already had headroom,
and which frozen router route (hotspot vs shard) applies.

`CAPABILITY_OR_EVIDENCE`: exact-head critical path `<=630s` with coverage
equivalence receipt; final required check remains named `validate`.

`STOP`: merge gate with exact owner phrase; no automatic merge.

`NEXT`: owner merge phrase only after success terminal; branch protection
remains deferred outside this atom.

## Success terminal

`EXACT_HEAD_CI_HEADROOM_RESTORED`
