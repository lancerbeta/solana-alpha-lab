# IMPLEMENT_BOUNDED_COHORT_MATERIALIZATION_V1

Normal mature LIVE `build-live-source` is bounded by the current cohort window
plus maturity tail, not by cumulative campaign history.

`DECISION_DELTA`: C3/C20/C50/C100 materialization work follows
`BOUNDED_COHORT_WINDOW` (predecessor MEMBER_BATCH + window/cutoff, one prefix
walk per SNAPSHOT_PLUS_DELTA unit, keyed OBSERVATION_BATCH routing). The old
full-history meat-grinder is not the operator path.

`UNCERTAINTY_REMOVED`: C2 wall cost is a function of the current window plus
one predecessor and one prefix walk, not of all historical PIT depth.

`CAPABILITY_OR_EVIDENCE`: `--plan-only` fail-closes on
`UNBOUNDED_MATERIALIZATION_PLAN`; real frozen C2 rebuilt in 83.5 min with a
canonical bundle; C100 payload work equals C3 class on the synthetic harness.

`STOP`: merge-readiness / owner phrase. No merge, VPS, seal/import, C3, or
old-artifact deletion in this atom.

`NEXT`: owner phrase after exact-head CI. Then authorized C3 unpack via
`list-live-cohorts` → `--plan-only` require `BOUNDED_COHORT_WINDOW` →
`build-live-source` → verify.

## Operator route

Identify the next mature unimported cohort, acquire only missing incremental
evidence, plan, require `BOUNDED_COHORT_WINDOW`, then build. Do not copy the
entire historical RDP, replay all historical PIT, start a duplicate build,
bypass the plan gate, prewarm caches, or delete random temp files.

## C2 acceptance (frozen local RDP, no VPS/provider)

- Cohort `REL-20260909T111900Z-20260916T111900Z`
- Plan: `BOUNDED_COHORT_WINDOW`, 739 MEMBER_BATCH (1 predecessor), 7 units,
  864 predicted delta applications, 738 observations, ~8.68 MiB observation
  payload, 0 independent reconstruct, 0 global observation glob, 0 Sep02-Sep05
  legacy locations
- Wall: 5011683 ms (83.5 min), ceiling 90 min
- Bundle: members 113107, observations 39008, schedule artifact exact,
  `source_sha256=041fc0924ef77a5b68f785a5f48fd97edcb345b6ed6e4b711af24b29e1733e89`
- CLI `assert_source_matches_receipt` PASS; admissions all inside window;
  observation mints subset of members
- Owned `.build-c5b494aea895afaf` removed after commit; old incident dirs kept
- Last live progress before cleanup: 6/7 units, 841/864 deltas, 721877740
  member payload bytes; scratch class ~0.88 GiB replay SQLite

## C100 harness

C3/C20/C50/C100 plan-only: member and observation payload ratios = 1.0;
ResearchStore payload ratio = 1.0; partitions opened = 4. Manifest headers
scale with history (9→203) and stay cheap (C100 plan 0.06 s).
`C100_PAYLOAD_WORK_BOUNDED`.

## Residuals (no deletion)

See `docs/evidence/bounded_cohort_materialization/old_residual_cleanup_candidates_v1.json`.
Reclaimable ~3.29 GiB. Separate owner cleanup authorization required.

## Non-claims

`NO_VPS` · `NO_PROVIDER` · `NO_SEAL_IMPORT` · `NO_C3_EXECUTION` ·
`NO_OLD_ARTIFACT_DELETION` · `NO_ALPHA` · `NO_CANONICAL_DONE`
