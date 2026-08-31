---
task_id: CI_SHARD_REBALANCE_AND_ANTI_DRIFT_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-31'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 4cf01ec95637d8b7fe4b359cf73ac7f9d269a990
  expected_upstream: origin/main
  expected_upstream_oid: 4cf01ec95637d8b7fe4b359cf73ac7f9d269a990
  expected_branch: cursor/ci-shard-rebalance-and-anti-drift-v1
  dirty_mode: ALLOW_REPORTED
objective: Refresh the four CI test-shard partitions from one fresh module profile
  and add a small load-aware unplanned-module assignment so new tests do not pile
  onto one shard before the next occasional reprofile.
managed_write_set:
- docs/tasks/CI_SHARD_REBALANCE_AND_ANTI_DRIFT_V1.md
- configs/ci_test_shards_v1.json
- scripts/ci_test_partition.py
- scripts/run_ci_test_shard.py
- tests/test_ci_test_partition.py
- tests/test_run_ci_test_shard.py
- tests/test_profile_test_wall_clock.py
- docs/evidence/ci_shard_rebalance_and_anti_drift/a1_delivery_completion_evidence_v1.json
- docs/evidence/ci_shard_rebalance_and_anti_drift/a1_delivery_independent_review_v1.json
- docs/evidence/ci_shard_rebalance_and_anti_drift/a1_delivery_factory_fit_v1.json
- catalog/assets/core.yaml
- catalog/assets/lifecycle.yaml
- catalog/catalog_manifest.yaml
- catalog/generated/asset_edges.json
- docs/PROJECT_MAP.md
- docs/OPERATOR_NAVIGATION.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STOP_NO_MATERIAL_GAIN
- STOP_REBALANCE_NOT_MATERIALLY_VALIDATED
- TEST_DELETION_SKIP_XFAIL_OR_WEAKENING
- CI_REDESIGN_OR_WORKFLOW_ARCHITECTURE_CHANGE
- NEW_DEPENDENCY_OR_UNPINNED_ACTION
- PAID_OR_LARGER_RUNNER
- PROVIDER_API_RPC_WSS
- PRODUCT_OR_BRIDGE_BEHAVIOR_CHANGE
- BRANCH_PROTECTION_OR_RULESET_MUTATION
- AUTOMATIC_MERGE_OR_BRANCH_DELETION
- WALLET_BUILD_EXECUTE_TRANSACTION
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
    - docs/evidence/ci_shard_rebalance_and_anti_drift/a1_delivery_completion_evidence_v1.json
    - docs/evidence/ci_shard_rebalance_and_anti_drift/a1_delivery_independent_review_v1.json
    - docs/evidence/ci_shard_rebalance_and_anti_drift/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# CI_SHARD_REBALANCE_AND_ANTI_DRIFT_V1

## SPEC_ROUTE

`NONE` — this file is the exact task contract. Owner prompt is the attached
authority source for thresholds and routes.

## Task Outcome Brief

- **Owner decision:** refresh the existing 4-shard CI plan from one fresh
  module profile and add a small load-aware assignment for modules absent
  from the committed plan. Do not redesign CI. Owner later authorized one
  local sequential profile of about one hour after
  `STOP_FAST_REBALANCE_TOO_EXPENSIVE` on the same workstation.
- **Product outcome:** future exact-head CI critical path is materially
  shorter (prefer all four test shards ~5–6.5 minutes) and newly added test
  modules distribute until the next occasional reprofile.
- **Named consumer:** Delivery Harness exact-head `validate-tests` matrix.
- **Cheapest falsifier:** one fresh profile plus `plan_shards()` projection
  fails the materiality gate (`projected_max` improvement vs observed ~580s
  max <20%), or exact-head CI max shard improvement vs observed ~9m40s is
  <20%.
- **Terminal outcomes:**
  - `CI_SHARD_REBALANCE_AND_ANTI_DRIFT_PASS_READY_FOR_MERGE_GATE`
  - `STOP_NO_MATERIAL_GAIN`
  - `STOP_REBALANCE_NOT_MATERIALLY_VALIDATED`
- **User-visible result:** committed `configs/ci_test_shards_v1.json` is a
  fresh balanced 4-shard plan; unplanned modules use load-aware estimated
  assignment; stale-profile hint is informational only.
- **Non-goals:** CI redesign, workflow architecture change, runner size,
  paid services, dependencies, test weakening, product/Factory/science/
  provider paths, Settings, branch protection, automatic profile/PR.
- **Evidence budget:** exactly one fresh full sequential module profile.
  Owner-authorized wall-clock is about one hour on this workstation.
  Anti-drift remains a small additive change; skip anti-drift rather than
  block rebalance. No repeated profiling or CI optimization loops. No
  local full gate before PR.
- **Replan trigger:** projected improvement <20%; exact-head CI green but
  critical-path improvement not material; tests fail during profiling.

## Architecture preserved

Module-level profiling, deterministic longest-processing-time planner,
max 4 shards, fail-closed inventory equivalence, fail-closed test-case
count equivalence, current exact-head CI validation semantics.

## Rebalance acceptance

- current test-module inventory covered exactly once
- zero duplicate / missing current modules
- same canonical discovered test-case count
- no test file changed except the proportional anti-drift tests in the
  write set; no skip / xfail / weakening
- shard_count remains canonical unless the existing planner selects otherwise
- projected max/min <= 1.30 where reasonably achievable
- prefer `projected_max_seconds <= 390`
- materiality: projected improvement vs recent ~580s max >= 20%

## Anti-drift

Change only assignment of modules absent from the committed plan.
Planned modules stay on their committed shard. No runtime profiling.
Deterministic least-loaded shard with lowest-index tie-break, using
`sum(projected_seconds) / number_of_planned_modules` as equal estimated
weight. Informational `CI_SHARD_PROFILE_STALE_REBALANCE_RECOMMENDED`
when unplanned count >= 8 or unplanned fraction >= 0.05; exit code
unaffected.
