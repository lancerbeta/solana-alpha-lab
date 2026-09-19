---
task_id: IMPLEMENT_BOUNDED_COHORT_MATERIALIZATION_V1
task_version: "1.0"
status: READY
as_of: "2026-09-19"
owner: GOAL_OWNER
allowed_routes: [DIRECT_CURSOR_DELIVERY]
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 7ef87028c933fd5335b75ad234fb830f7031eeb5
  expected_upstream: origin/main
  expected_upstream_oid: 7ef87028c933fd5335b75ad234fb830f7031eeb5
  expected_branch: cursor/bounded-cohort-materialization-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Repair mature LIVE cohort materialization so normal C3/C20/C50/C100 work is
  bounded by the current cohort window plus maturity tail, not by cumulative
  campaign history. One prefix walk per SNAPSHOT_PLUS_DELTA unit, keyed
  observation routing, plan-only unbounded gate, atomic build lock, 90-minute
  wall, owned scratch, and exact scientific parity.
managed_write_set:
  - docs/tasks/IMPLEMENT_BOUNDED_COHORT_MATERIALIZATION_V1.md
  - src/solana_alpha_lab/factory/bounded_cohort_materialization.py
  - src/solana_alpha_lab/factory/research_store.py
  - src/solana_alpha_lab/factory/members_snapshot_delta.py
  - src/solana_alpha_lab/factory/live_cohort_to_forge.py
  - src/solana_alpha_lab/factory/live_cohort_discovery_release.py
  - src/solana_alpha_lab/factory/live_cohort_source_bundle.py
  - scripts/discovery_evidence_release.py
  - scripts/bench_bounded_cohort_materialization_v1.py
  - tests/test_bounded_cohort_materialization_v1.py
  - tests/test_local_cohort_incremental_materialization_v1.py
  - tests/test_live_cohort_memory_bounded_publication_v1.py
  - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
  - docs/reports/bounded_cohort_materialization/a1_owner_readout_v1.md
  - docs/evidence/bounded_cohort_materialization/a1_delivery_completion_evidence_v1.json
  - docs/evidence/bounded_cohort_materialization/a1_delivery_independent_review_v1.json
  - docs/evidence/bounded_cohort_materialization/a1_delivery_factory_fit_v1.json
  - docs/evidence/bounded_cohort_materialization/c2_plan_bounded_v1.json
  - docs/evidence/bounded_cohort_materialization/c2_build_receipt_v1.json
  - docs/evidence/bounded_cohort_materialization/c100_payload_work_v1.json
  - docs/evidence/bounded_cohort_materialization/old_residual_cleanup_candidates_v1.json
  - catalog/assets/core.yaml
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
context_requirements:
  catalog_asset_ids: []
  l2_roles: [LIFECYCLE, ARCHITECTURE_DECISIONS]
  l3_roles: [HISTORICAL_CONTEXT]
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE:
      - docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - src/solana_alpha_lab/factory/bounded_cohort_materialization.py
      - src/solana_alpha_lab/factory/members_snapshot_delta.py
      - src/solana_alpha_lab/factory/research_store.py
    DELIVERY_EVIDENCE:
      - docs/evidence/bounded_cohort_materialization/a1_delivery_completion_evidence_v1.json
      - docs/evidence/bounded_cohort_materialization/a1_delivery_independent_review_v1.json
      - docs/evidence/bounded_cohort_materialization/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT:
      - docs/tasks/LOCAL_COHORT_INCREMENTAL_MATERIALIZATION_V1.md
stop_conditions:
  - Canonical implementation/contracts drifted from 7ef87028. STOP IMPLEMENTATION_BASE_DRIFT.
  - Real frozen C2 exceeds 90 minutes. STOP REAL_C2_REPAIR_SLO_FAIL. No retry, no extension.
  - C100 payload work exceeds ~1.5x C3 class or ResearchStore payload decode grows with ordinal. STOP C100_SCALING_FAIL.
  - Any scientific parity invariant cannot be preserved exactly. STOP, no threshold weakening.
  - Slow fallback reported as BOUNDED_COHORT_WINDOW or FAST. STOP.
  - Owner merge phrase, VPS, provider, seal/import, C3 execution, or historical artifact deletion.
---

# IMPLEMENT_BOUNDED_COHORT_MATERIALIZATION_V1

## DECISION_DELTA

Normal mature-cohort `build-live-source` is bounded by
`[window_start, closure_cutoff]` plus exactly one `PREDECESSOR_BOUNDARY`
MEMBER_BATCH. Historical PIT replay, full ResearchStore payload scans, and
global observation globs are not the operator path.

## UNCERTAINTY_REMOVED

Whether C2/C3/C100 materialization cost is a function of campaign history or
of the current window + maturity tail.

## CAPABILITY_OR_EVIDENCE

`--plan-only` with `BOUNDED_COHORT_WINDOW` or fail-closed
`UNBOUNDED_MATERIALIZATION_PLAN`; one prefix walk per unit; keyed
OBSERVATION_BATCH routing; lock; 90-minute wall; owned scratch; tests A–P;
real C2 ≤90 min; C100 payload bound.

## STOP

Owner merge gate. No VPS, no seal/import, no C3, no old-artifact deletion.

## NEXT

Owner phrase after exact-head CI + merge-readiness. Then authorized C3 unpack.

## Additional isolated reviews (not contract-enum)

SCIENCE_CRITIC and FACTORY_FIT run as isolated critics. SCIENCE_CRITIC is
outside `required_review_roles` schema enum and is bound in review evidence.

## Non-goals

VPS mutation, provider calls, collector/schedule/sampling/estimand change,
canonical data_plane rewrite, C1 rewrite, seal/import/Forge, destructive
historical cleanup, persistent indexes, daemons, event ledgers, GiB
checkpoints.
