---
task_id: CTRL_DETERMINISTIC_FINISH_POSTMERGE_TESTS_V1
task_version: '1.0'
status: IN_PROGRESS
as_of: '2026-09-15'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: a39a14581054d185592da593e163fdf5cbec5325
  expected_upstream: origin/main
  expected_upstream_oid: a39a14581054d185592da593e163fdf5cbec5325
  expected_branch: cursor/ctrl-deterministic-finish-postmerge-tests-v1
  dirty_mode: ALLOW_REPORTED
objective: "Repair two branch-state-dependent acceptance tests that failed in post-merge CI on main after PR #304: the tests must tolerate the deterministic context-rebuild degradation that legitimately occurs on a checkout whose merge-base with origin/main no longer equals the task contract frozen base - no merge authority, no product change, no new capability."
managed_write_set:
- docs/tasks/CTRL_DETERMINISTIC_FINISH_POSTMERGE_TESTS_V1.md
- tests/test_delivery_harness_deterministic_finish.py
- docs/evidence/control/a1_ctrl_deterministic_finish_postmerge_tests_completion_v1.json
- docs/evidence/control/a1_ctrl_deterministic_finish_postmerge_tests_review_v1.json
- docs/evidence/control/a1_ctrl_deterministic_finish_postmerge_tests_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- NO_MERGE_AUTHORITY_STOP_BEFORE_MERGE
- PRECHECK_NEEDS_GITHUB_OR_NETWORK
- SCOPE_WIDENING_REQUIRED
context_requirements:
  catalog_asset_ids: []
  l2_roles: []
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
    - docs/evidence/control/a1_ctrl_deterministic_finish_postmerge_tests_completion_v1.json
    - docs/evidence/control/a1_ctrl_deterministic_finish_postmerge_tests_review_v1.json
    - docs/evidence/control/a1_ctrl_deterministic_finish_postmerge_tests_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# CTRL-DETERMINISTIC-FINISH-POSTMERGE-TESTS-V1

Post-merge CI on main (run 34908165528) failed on two acceptance tests of the
just-merged DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1 atom:

- `test_output_shape_is_stable_and_non_claiming` asserted the full 8-key
  `checks` form unconditionally;
- `test_write_set_violation_denies_on_real_wiring` asserted the
  `write_set_pass` key unconditionally.

Root cause: on merged main the preflight context rebuild legitimately cannot
rebuild the task receipt (merge-base != frozen expected_base), so `checks`
carries only the five state-independent keys and `CONTEXT_REBUILD_FAILED` is
recorded. Both tests passed on the task branch where the base was frozen and
failed on the merged checkout. This is exactly the "CI as a linter for
locally knowable failures" class the parent atom closes.

Fix: the shape test accepts the branch form (8 keys, rebuild deterministic)
and the merged/other-state form (5 keys + recorded rebuild failure) as the
two stable outputs; the write-set test derives its expectation from the
actual rebuild outcome. Both remain deterministic on any checkout state,
which is verified on this branch (main-based) before push.

## Managed write set

Derived consumers: none expected; `catalog/assets/core.yaml` re-application
is not required because the changed test file is not a record-hash target of
the catalog (verified via preflight `derived_state_current=true` without
sync on this branch).
