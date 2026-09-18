# SELF_CONTAINED_LIVE_COHORT_RELEASE_V1

Sealed LIVE releases now carry the exact ObservationSchedule document across
source → seal → verify → transport → import. Ordinary publication needs no
bind-schedule step. C2 is not operated in this atom.

`DECISION_DELTA`: a 1.1 sealed tree is scientifically self-contained for
schedule truth.

`UNCERTAINTY_REMOVED`: `CANONICAL_SCHEDULE_UNBOUND` is no longer caused by
dropping the document at the publication boundary.

`CAPABILITY_OR_EVIDENCE`: schema `1.1` `observation_schedule.json` plus
ResearchStore persist after typed import gates.

`STOP`: merge-readiness / owner phrase. Do not merge.

`NEXT`: owner-paced C2 `list-live-cohorts` → `build-live-source` →
`seal-live-cohort` → `verify-live` → transport → `import-live` →
`forge-control-ready`. `C2_OPERATION_PENDING`.

## Architecture

- **Source owner:** validated ObservationSchedule at `build-live-source`
  (source bundle `observation_schedule.json`). RDP vs ops disagreement is a
  typed STOP. Ops sqlite is source-time only.
- **Sealed artifact:** `observation_schedule.json` (complete document).
  Semantic identity = `schedule_sha256(document)`. Transport identity =
  SHA-256 of artifact bytes.
- **Verify:** parser PASS + semantic SHA + artifact byte SHA + census SHA.
- **Transport:** versioned release tree; 1.1 copies and byte-hashes the
  schedule artifact with the existing files.
- **Imported owner:** existing ResearchStore `OBSERVATION_SCHEDULE`, keyed by
  semantic SHA. Persist runs after `IMPORT_BEFORE_SEAL` and identity/conflict
  gates. Rejected import does not bind. Orphan exact SHA after a later
  publication crash is retryable and does not make an unverified cohort
  visible.
- **Downstream resolver:** unchanged `resolve_canonical_release_schedule` on
  local `data_root`. No VPS after import. PR #319 eligibility semantics
  unchanged.

## Operator flow

Unchanged:

`list-live-cohorts` → `build-live-source` → `seal-live-cohort` →
`verify-live` → transport/copy → `import-live` → `forge-control-ready`

Same-host `publish-live-cohort` inherits the same carriage. No
`--schedule-document`, `bind-schedule`, or `attach-schedule`.

## Tests

Hermetic A–I in `tests/test_self_contained_live_cohort_release_v1.py`:
forward 1.1 vertical, tamper, semantic mismatch, missing 1.1 artifact,
idempotent import, shared-SHA multi-cohort without parquet rewrite,
different SHA does not bind the other cohort, legacy 1.0 stays unbound,
rejected `IMPORT_BEFORE_SEAL` does not bind, no extra operator command.

## Non-claims

`NO_C2_OPERATION` · `NO_FORGE` · `NO_PROVIDER` · `NO_RUNTIME_MUTATION` ·
`NO_ALPHA` · `NO_CANONICAL_DONE`

Factory Fit: PASS / FULL_REVIEW. Product Horizon: NOW=NONE;
WATCH=C2_OPERATION_PENDING after merge.
