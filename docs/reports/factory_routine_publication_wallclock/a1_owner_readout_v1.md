# FACTORY_ROUTINE_PUBLICATION_WALLCLOCK_V1 — owner readout

## Result

Routine SNAPSHOT_PLUS_DELTA publication hot path optimized for ~205k members.

- Baseline hot substages: **20.416s** (diff alone ~13.1s via per-row SELECT)
- Candidate warm append: **4.968s** (~**4.11×**), both ≤45s and ≥2× envelope PASS
- Mechanisms: sorted-merge diff; non-canonical operational latest cache; folded prev fingerprint; stage telemetry (`SMIAL_PUBLICATION_STAGE_TIMING`)

## Non-claims

No merge/deploy/VPS/tick/C1 in this atom. Cache is not scientific truth.

## Next

Exact merge-readiness → owner phrase → guarded merge → separate OPERATE commissioning.
