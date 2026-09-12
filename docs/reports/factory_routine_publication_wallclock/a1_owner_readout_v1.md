# FACTORY_ROUTINE_PUBLICATION_WALLCLOCK_V1 — owner readout

## Result

Routine SNAPSHOT_PLUS_DELTA publication hot path optimized for ~205k members,
verified on the full production-shaped post-provider path.

- Baseline hot substages: **20.416s** (diff alone ~13.1s via per-row SELECT)
- Candidate warm append (`append_delta_publication`, 205,847 members): **4.968s**
  (~**4.11×**), ≤45s and ≥2× envelope PASS
- **Full post-provider path** (`publish_observation_batch` with a small
  realistic observation batch on an open day: member spill, canonical content
  hashing, SNAPSHOT_PLUS_DELTA append, artifact hash verification, manifests,
  RDP events, marker, receipt finalization): **5.818s** measured wall
  (target ≤45s PASS; fence 60s not approached), **peak RSS 208.4 MiB**
  (target ≤512 MiB PASS; fence 768 MiB), **provider calls = 0**
- Full-population passes in the measured publish: **1** (canonical census hash
  over the spilled 205,847 members); operational cache hit = 1, misses = 0
- Cache bytes measured (205,847-member fixture): **65,053,113 bytes total**
  (sqlite 65,052,672 + meta 441); explicitly non-canonical
- Depth proof: warm append at **history depth 100** stays flat (hot-path ops:
  1 full-population pass, 0 reconstruct calls; wall < 2s for a 200-row
  fixture) — hot path does not scale with history depth
- Cache-miss/corrupt fallback at **depth 60**: full replay publishes
  scientifically correct state (exact tags verified at depth and tail); cold
  fallback is correct, not required fast. Companion cold-path proof at the
  same **depth 100** as the warm proof: cold replay of 100 deltas measured
  0.796s on the 200-row fixture (loose correctness bound <30s), so warm-cache
  speed is the optimization, not a correctness dependency
- Mechanisms: sorted-merge diff; non-canonical operational latest cache;
  folded prev fingerprint; stage telemetry (`SMIAL_PUBLICATION_STAGE_TIMING`)

## Archive boundary (review closure 1)

Operational latest cache files (`datasets/members_snapshot_plus_delta/<utc_day>/
.operational_latest_members.*`) are excluded from
`list_closed_day_relative_paths()`: cache bytes NEVER enter closed-day
scientific inventory/archive. Regression test proves identical archive
inventory with cache present/absent/stale/corrupt, and reconstruction stays
exact in all four states. Retention is bounded by
`prune_stale_operational_caches()` (run at closed-day durability loop): only
verified days within the 1-closed-day retention window keep a cache; the open
day always keeps its working cache; older days are pruned, so day-over-day
retention cannot grow unbounded. Canonical unit/delta archive content is not
weakened.

## Non-claims

No merge/deploy/VPS/tick/C1 in this atom. Cache is not scientific truth.
Benchmarks are offline deterministic synthetic members, not live host truth.

## Next

Exact merge-readiness → owner phrase → guarded merge → separate OPERATE commissioning.
