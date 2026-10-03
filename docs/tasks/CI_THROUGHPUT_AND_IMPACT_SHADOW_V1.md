---
task_id: CI_THROUGHPUT_AND_IMPACT_SHADOW_V1
task_version: '1.1'
status: IN_PROGRESS
as_of: '2026-10-03'
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CLAUDE_CODE_DELIVERY
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 3d2f75dc442cf3010d84f306404fc7a107eb88a4
  expected_upstream: origin/main
  expected_upstream_oid: 3d2f75dc442cf3010d84f306404fc7a107eb88a4
  expected_branch: claude/ci-throughput-and-impact-shadow-v1
  dirty_mode: FORBIDDEN
objective: >-
  Full-suite throughput repair only: replace the stale shard timing profile
  with fresh exact-head module_done telemetry, plan a deterministic 4-6 shard
  partition (currently 6) with unchanged coverage semantics, and prove the
  wall-clock gain on a full exact-head GitHub run. The shadow impact selector
  (Part B) is stopped with NO_MATERIAL_SELECTION_VALUE and is not implemented.
managed_write_set:
  - docs/tasks/CI_THROUGHPUT_AND_IMPACT_SHADOW_V1.md
  - configs/ci_test_shards_v1.json
  - scripts/ci_test_partition.py
  - tests/test_ci_test_partition.py
  - scripts/validate_ci.py
  - tests/test_ci.py
  - scripts/render_ci_workflow.py
  - .github/workflows/ci.yml
  - tests/test_execution_domain_modularity_and_fast_ci_v1.py
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/PROJECT_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
  - docs/reports/ci_throughput_and_impact_shadow/a1_owner_readout_v1.md
  - docs/evidence/ci_throughput_and_impact_shadow/a1_delivery_completion_evidence_v1.json
  - docs/evidence/ci_throughput_and_impact_shadow/a1_delivery_independent_review_v1.json
  - docs/evidence/ci_throughput_and_impact_shadow/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - BASE_DRIFT_REQUIRES_REPLAN
  - FULL_SUITE_COVERAGE_EQUIVALENCE_FAILED
  - ADDITIONAL_SHARDS_NO_USER_VISIBLE_GAIN
  - ACCOUNT_CONCURRENCY_SERIALIZES_PLAN
  - NEW_DEPENDENCY_REQUIRED
  - CACHE_OR_EXTERNAL_SERVICE_REQUIRED
  - PRODUCT_SEMANTICS_CHANGE_REQUIRED
  - TEST_WEAKENING_REQUIRED
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
      - docs/evidence/ci_throughput_and_impact_shadow/a1_delivery_completion_evidence_v1.json
      - docs/evidence/ci_throughput_and_impact_shadow/a1_delivery_independent_review_v1.json
      - docs/evidence/ci_throughput_and_impact_shadow/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---
# CI_THROUGHPUT_AND_IMPACT_SHADOW_V1

`SPEC_ROUTE=NONE`: this file is the exact task contract. Model effort: `SOL_XHIGH`.
Version 1.1 narrows the atom after the owner accepted the Part B stop.

## Entry / Outcome

- `DECISION_DELTA`: exact-head PR CI stops paying ~20 min for the full suite:
  fresh timing profile and 6 general shards instead of 4, coverage unchanged.
- `UNCERTAINTY_REMOVED`: whether more shards give a user-visible wall-clock gain
  on real runners without queueing; which minimal count is justified.
- `CAPABILITY_OR_EVIDENCE`: plan embeds its profile provenance and per-module
  seconds so it is reproducible; exact-head FULL timings before/after.
- `STOP`: merge-readiness readback; no merge.
- `NEXT`: decide from the real after-state whether any further CI atom exists.
- `REPLAN_TRIGGER`: 6 shards give no material gain (queue/concurrency): choose
  the minimal 5/4 plan or stop `ADDITIONAL_SHARDS_NO_USER_VISIBLE_GAIN`.
  Never raise a timeout or tune the model to pass.

## Invariants

- Canonical `unittest discover` stays the owner of the full inventory; each
  module runs exactly once across the execution lane and the general shards;
  loaded cases equal canonical discovery; reserved execution modules never enter
  general shards; no test deleted, skipped or weakened; no timeout inflation.
- No new dependency, service, cache, recurring profiler or per-test change.
- Slow modules are residual/WATCH only (see readout), not optimised here.

## Part B terminal: `NO_MATERIAL_SELECTION_VALUE` (durable negative evidence)

A fail-closed impact selector (groups EXECUTION, FACTORY_OPERABILITY,
FORGE_HFIC; AST import closure plus literal path mentions and directory scans;
Catalog propagation proven through `harness_sync`) was prototyped and replayed
over the last 45 first-parent merges of `main` at base `72330ae1`. It is not
implemented in this PR. Result:

- 9/45 merges hard-FULL (CI, validation, harness, global); eligible
  denominator 36.
- Only 6/36 formed a group-bounded candidate, all FORGE_HFIC. 0/6 stayed under
  the 70 % time cap: median selected time about 83 % (range 80-87 %), modules
  about 40 %, cases 53-60 %, spread over all 6 shards.
- Floor of any sound FORGE_HFIC selection is about 53.5 % of suite time: its 54
  owned tests are the slowest modules, and about 40 % of suite time sits in tests
  that scan directories, spawn subprocesses or mention files, so a sound
  selector must keep them. Typical saving at 6 shards is about 2 minutes, far
  from the ~7 minute activation bar.
- EXECUTION is a clean boundary (4 source modules, 15 tests, ~0 s in the general
  profile) but was never the only group touched in 45 merges. FACTORY_OPERABILITY
  is blocked by the shared hub `research_store.py` (closure about 75 % of time).
- Main FULL reasons among the 36 eligible: unclassified test 18, unknown source
  path 7, unproven Catalog propagation 4, group not admitted 1.

Do not rebuild an affected-test selector without new material evidence, for
example the slow HFIC tests becoming fast or a new group with a real boundary.
Prototype only in local branch `wip/ci-impact-planner-prototype`; not pushed.

## Rollback

Revert the merge commit; restoring the previous `configs/ci_test_shards_v1.json`
and `ci.yml` render returns the 4-shard plan. No persisted state.

## Definition of Done

Exact base/head recorded; fresh profile with provenance; deterministic 6-shard
plan reproducible from the plan file; coverage and disjointness proven;
renderer equals workflow; focused suite green with no expected failures; full
exact-head GitHub CI green with per-shard elapsed, wall clock, queue skew and
setup overhead compared against two fresh pre-change runs; reviewers PASS;
merge-readiness read back; merge not performed.
