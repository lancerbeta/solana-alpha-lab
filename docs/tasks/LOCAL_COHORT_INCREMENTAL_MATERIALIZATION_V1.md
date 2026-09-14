---
task_id: LOCAL_COHORT_INCREMENTAL_MATERIALIZATION_V1
task_version: "1.0"
status: IMPLEMENTED_UNVERIFIED
as_of: "2026-09-14"
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: e79adc0b7b8d765ef14e1560ba81f08efcdcf61a
  expected_upstream: origin/main
  expected_upstream_oid: e79adc0b7b8d765ef14e1560ba81f08efcdcf61a
  expected_branch: local-cohort-incremental-materialization-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Make local mature-cohort source materialization incremental in steady
  state: after the initial cold bootstrap, the cost of C2/C3/... must depend
  primarily on new/changed material since a validated local checkpoint, NOT
  on total historical delta depth or cohort ordinal. Full canonical replay
  remains available as cold bootstrap, cache-miss fallback, corruption or
  staleness fallback, and explicit audit or recovery path.
managed_write_set:
  - docs/tasks/LOCAL_COHORT_INCREMENTAL_MATERIALIZATION_V1.md
  - src/solana_alpha_lab/factory/members_snapshot_delta.py
  - src/solana_alpha_lab/factory/live_cohort_discovery_release.py
  - src/solana_alpha_lab/factory/live_cohort_source_bundle.py
  - scripts/bench_local_materialization_v1.py
  - tests/test_local_cohort_incremental_materialization_v1.py
  - tests/test_live_cohort_memory_bounded_publication_v1.py
  - catalog/assets/core.yaml
  - docs/reports/local_cohort_incremental_materialization/a1_owner_readout_v1.md
  - docs/evidence/local_cohort_incremental_materialization/a1_benchmark_v1.json
  - docs/evidence/local_cohort_incremental_materialization/a1_delivery_completion_evidence_v1.json
  - docs/evidence/local_cohort_incremental_materialization/a1_delivery_independent_review_v1.json
  - docs/evidence/local_cohort_incremental_materialization/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
context_requirements:
  catalog_asset_ids: []
  l2_roles: [DELIVERY_EVIDENCE]
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
      - docs/evidence/local_cohort_incremental_materialization/a1_benchmark_v1.json
      - docs/evidence/local_cohort_incremental_materialization/a1_delivery_completion_evidence_v1.json
      - docs/evidence/local_cohort_incremental_materialization/a1_delivery_independent_review_v1.json
      - docs/evidence/local_cohort_incremental_materialization/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
stop_conditions:
  - >-
    Warm production-shape benchmark remains >90 min by design or work counters
    show monotonic growth with cohort ordinal. Replan instead of cosmetic PASS.
  - >-
    Any scientific parity invariant cannot be preserved exactly. STOP, no
    threshold weakening, no GAP semantics change.
  - >-
    Checkpoint or cache identity mismatch cannot be fail-closed ignored. STOP.
  - >-
    Owner attention gate material boundary (merge, VPS, provider, deployment)
    requires exact owner decision.
---

# LOCAL_COHORT_INCREMENTAL_MATERIALIZATION_V1

## Objective
Owner-path throughput/I/O optimization of the measured local C1 materialization
bottleneck (~3h25m wall, ~807 GB reads / ~201 GB writes, RSS 237-297 MB,
FORGE_CONTROL_READY). Steady-state incremental materialization for C2/C3/...

## Design order
ADOPT -> WRAP -> BUILD. First assess reuse/generalization of existing
.operational_latest_members.sqlite validation/cache primitives. No second
checkpoint schema unless latest-only semantics cannot satisfy exact
historical/PIT materialization. Any separate local checkpoint is: local-only,
rebuildable, explicitly NOT scientific truth, identity-bound (unit/publication
identity, dataset_manifest_id, seq, snapshot_fingerprint, row_count,
checkpoint file sha), atomically replaced, ignored/discarded on any mismatch.
A later checkpoint must NEVER satisfy an earlier PIT target.

## Hard invariants
Scientific parity (identity/sampling/missingness/survival/typed values/
provenance/lineage/fingerprints/v1-v2 read compatibility/publication identity/
PIT clocks/closure-coverage/seal-verify-import/FORGE_CONTROL_READY behavior).
No historical RDP rewrite. No threshold weakening. No GAP semantics change.

## Required telemetry
Compact materialization stage evidence (build wall, member reconstruction wall,
cohort selection wall, observation extraction wall, parquet/hash wall,
seal/verify/import wall, anchor_loads, checkpoint_hit/miss, reconstruct_calls,
delta_files_applied, repeated exact-publication reconstruction count, scratch
bytes). No metrics subsystem.

## Complexity acceptance (deterministic production-shape regressions)
A. cold path canonical replay with no cache.
B. warm unchanged: exact-unchanged state does NOT replay anchor -> full chain.
C. one-step incremental: work proportional to new state, not all history.
D. deep history (10-cohort-equivalent): warm materialization work must NOT
   grow with total chain depth; C10-like same complexity class as C2-like for
   comparable new-data volume. Assert work counters/complexity, not only wall.

## SLO targets (owner targets, not scientific claims)
C2 warm ~20-45 min; C10 ~20-60 min and <= ~1.5x C2 normalized; if warm
production-shape benchmark >90 min by design or monotonic growth: replan,
do not cosmetically PASS. Do NOT rerun real C1 3.5h as pre-merge gate; use
deterministic benchmark/equivalence evidence.

## Scratch/cleanup
Repo-local owned scratch conceptually local/factory_mirror/.materialization/
(checkpoint/, tmp/run=<run-id>/). SUCCESS: remove run-scoped temp sqlite,
journals, temp parquet/hash material, unneeded completed .build-* staging,
superseded checkpoint generations. Handled failure: keep compact diagnostics
only. Hard crash: conservative age/active-run prune of owned stale scratch
only; never arbitrary %TEMP%; never canonical data. Persistent cache bounded,
rebuildable, atomic replacement, no unbounded generations. Cleanup regression:
no giant scratch remains after warm materialization.

## Reviews
CODE_REVIEWER, ARCHITECTURE_CRITIC, SCIENCE_CRITIC, GOAL_DOD_CRITIC,
FACTORY_FIT_REVIEW, PRODUCT_HORIZON_RADAR.
Science critic: can any checkpoint/cache/reuse return a member state not
exactly available at the requested publication/PIT boundary?
Architecture critic: does warm cost stay bounded as depth/cohort count grows,
or did the patch merely make C1/C2 fixtures fast?

## Rollback
Delete/disable rebuildable acceleration cache; fall back to canonical full
replay. No scientific rollback/history rewrite.

## Delivery
One bounded PR. CHECK -> CONTEXT -> ENTRY/OUTCOME -> IMPLEMENT ->
proportional tests/benchmark -> isolated reviews -> FACTORY_FIT /
PRODUCT_HORIZON -> FINISH -> PR -> exact-head CI -> merge-readiness.
STOP before merge; no merge authority granted.
