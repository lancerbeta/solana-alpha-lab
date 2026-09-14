# CTRL-DETERMINISTIC-FINISH-POSTMERGE-TESTS-V1

task_id: CTRL_DETERMINISTIC_FINISH_POSTMERGE_TESTS_V1
owner_intent: "Repair two branch-state-dependent acceptance tests that fail on merged main after PR #304; tests must be deterministic on any checkout state."
status: IN_PROGRESS
created: 2026-09-15
route: DIRECT_CURSOR_DELIVERY
git_binding:
  expected_base: a39a14581054d185592da593e163fdf5cbec5325
  expected_upstream: origin/main
  expected_branch: cursor/ctrl-deterministic-finish-postmerge-tests-v1
  dirty_mode: ALLOW_REPORTED
objective: "Make the two DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1 acceptance tests (test_output_shape_is_stable_and_non_claiming, test_write_set_violation_denies_on_real_wiring) branch-state tolerant: on a checkout whose merge-base with origin/main no longer equals the task contract's frozen expected_base (merged main, fresh clone), the preflight context rebuild deterministically omits task-scoped checks (task_base_frozen, candidate_non_empty, write_set_pass) and records CONTEXT_REBUILD_FAILED. The tests must assert the stable schema and non-claims on any state, and assert the full 8-check branch form only when the receipt rebuild succeeds on a matching frozen base - no merge authority, no product change."
managed_write_set:
- docs/tasks/CTRL_DETERMINISTIC_FINISH_POSTMERGE_TESTS_V1.md
- tests/test_delivery_harness_deterministic_finish.py
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

## Task Outcome Brief

Post-merge CI on main (run 34908165528) failed on two acceptance tests of the just-merged
DELIVERY_HARNESS_DETERMINISTIC_FINISH_V1 atom. Root cause: the tests assume the working
branch state (merge-base == frozen expected_base). On merged main the context rebuild
legitimately cannot rebuild the task receipt (base moved), so `checks` carries only the
five state-independent keys and `CONTEXT_REBUILD_FAILED` is recorded. This is the same
"CI as a linter for locally knowable failures" class the atom was created to close.

Fix approach: (1) the shape test accepts either the full 8-key branch form or the
reduced 5-key merged/other-state form, requiring the schema, non-claims, and
state-independent keys unconditionally; (2) the write-set test derives expectations
from the actual rebuild outcome: when rebuild fails on this state it asserts the
recorded CONTEXT_REBUILD_FAILED reason and the reduced key set; when rebuild succeeds
it asserts the WRITE_SET_VIOLATION DENY via the injected violating reader exactly as
before. Both tests remain fully deterministic on branch and main checkouts.

## Managed write set

Derived consumers: none expected; `catalog/assets/core.yaml` may require harness_sync
re-application if the changed test file is a tracked record hash target; use the
sanctioned sync tool if drift is reported by preflight.

## Next

Finish content, run the two tests on main-state and branch-state, preflight-push PASS,
PR, exact-head CI, merge-readiness, stop for owner phrase.
