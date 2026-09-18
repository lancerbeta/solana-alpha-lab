# HORIZON_SCOPED_SCIENTIFIC_ELIGIBILITY_V1

Scientific N is X300-valid `X_ELIGIBLE` (`base_x_population.n`). Outcome
missingness is coverage against that denominator. It does not shrink N and
can only fail-close an experiment into the existing data/science-option
route (`PASS_DATA_OPTION_REQUIRED`).

`COMPLETE` iff every declared required `(point_id, field_id)` is `OBSERVED`
for every member of `base_x`. Censored, typed-missing, absent, or unknown
required outcomes are `MISSINGNESS_UNRESOLVED`. They are not a second
population.

Historical selection receipts stay byte-immutable
`FULL_LIFECYCLE_COMPLETENESS` caveats. A valid receipt does not globally
STOP `START_NEW_SESSION` and does not auto-veto ExperimentSpec 1.3 from
Y-point-set equality. An unusable/mismatched receipt is
`SELECTION_RECEIPT_INTEGRITY_INVALID`, not a selection veto.

CONTROL / NT consume-time floors use `base_x.n` only after the release-bound
X300 300+300 `FIELD-LIQUIDITY-USD-001` geometry is proven. Bound identity
with unproven or incompatible schedule is
`CANONICAL_SCHEDULE_UNBOUND` / `CANONICAL_X300_SCHEDULE_INCOMPATIBLE` /
`CONTROL_CORPUS_UNRESOLVABLE`. It does not stamp a yield or complete-case N.
Unbound identity (this data-root is not expected C1) may still omit
projection. NT motif `M` is unchanged. A NORMALIZED_TRAJECTORY release
that carries `candidate_state` also fail-closes instead of silent 300+300.

This patch does not run Forge.

## In-task sealed C1 read-only acceptance

Identity bind on LIVE CORPUS parent data-root:

- corpus_id = `DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001`
- cohort_id = `REL-20260902T111900Z-20260909T111900Z`
- release_id = `633a57088a5eb16dcc75a56aa2eb2521bbc76d1874aeb75aceb1ecc795bf1154`
- dataset_manifest_id = `dataset-663effb830a45ca5117742ac6a29e0763b9378f3905dcb37c7c2deba41f62756`
- census_sha256 = `cfa7d8404dc5400c4e223c4d5303193ad2209f92cac3af2d61862e384ebfd5bf`
- observations_sha256 = `7b26425c69cc95baf8a9e0b9ea506de1042b98b83d48a2dae07f5a33a7d66d7d`
- census `source_schedule_sha256` = `619ae64e885e995ee09d562f7b11d93f2ff7aca8b642abbb1f81c390c7d7896d`

Consume-time `try_project_scientific_eligibility_from_data_root` =
`CANONICAL_SCHEDULE_UNBOUND`. LIVE CORPUS has no `OBSERVATION_SCHEDULE`
document for that SHA, and the sibling ops `registered_schedules` row is
absent. Product CONTROL/classifier/live_cohort therefore fail-close. They
do not apply silent 300+300 and do not stamp `yield_eligible`.

5A/5B counts below are identity-bound parquet projection after the lineage
bind, using factory X300 300+300 `FIELD-LIQUIDITY-USD-001` and required
Y86400 / `FIELD-USD-PRICE-001` state metadata only. Loaded observation
columns contain zero `typed_value` fields.

### 5A. Base population

- `base_x_population.n` = 475
- rule_id = `BASE_X_X300_VALID_X_ELIGIBLE_V1`
- X point = X300; X field = `FIELD-LIQUIDITY-USD-001`; due = 300; lateness = 300
- lifecycle n_observed = 148
- lifecycle n_censored_late = 327
- lifecycle n_typed_missing = 0
- lifecycle n_other = 0
- lifecycle denominator_n = 475
- 148 + 327 + 0 + 0 = 475

### 5B. Required-outcome missingness

Resolved canonical pair: Y86400 / `FIELD-USD-PRICE-001`.

- n_observed = 383
- n_censored_late = 92
- n_typed_missing = 0
- n_absent = 0
- n_other = 0
- denominator_n = 475
- 383 + 92 + 0 + 0 + 0 = 475
- outcome_readiness = `MISSINGNESS_UNRESOLVED`
- `base_x_population.n` remains 475

### 5C. Safety

- Y typed-value reads = 0
- provider requests = 0
- credential reads = 0
- Forge runs = 0
- data-plane mutations = 0
- `latest.json` sha256 = `7a9435aefa2a0d7b897a931a49d469b71ed3bf0e2f0de44967aa2ba1a7ad187b` (unchanged)
- historical selection receipt bytes not rewritten

Hermetic vertical Case A (required Y900 observed, unrelated Y86400
censored): `COMPLETE`, caveat-only historical receipt, no shrink.
Case B (required Y86400 censored): `MISSINGNESS_UNRESOLVED` →
`PASS_DATA_OPTION_REQUIRED` / `REPORT_OUTCOME_COVERAGE_KEEP_BASE_X`.

Terminal of this atom: reviews + exact-head CI + merge-readiness / owner
phrase. Not canonical DONE, not alpha.
