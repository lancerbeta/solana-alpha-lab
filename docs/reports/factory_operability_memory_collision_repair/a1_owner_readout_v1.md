# FACTORY_OPERABILITY_MEMORY_COLLISION_REPAIR_V1 — owner readout

## What changed

Operational monitoring is now **resource-safe**.

- `build_collector_operational_packet` streams RDP byte facts in one `os.walk`.
  It does not retain a list of every path.
- Ordinary watch / daily pulse no longer import
  `live_cohort_discovery_release` or load
  `live_observation_rebuild/source_snapshot.json`. Lifecycle fields without
  bounded manifest truth stay `UNKNOWN`.
  Residual: HOT90 closed-day helpers on the same packet path still import
  PyArrow; that is not this atom's scientific-snapshot bug.
- Daily owner pulse moves to `*-*-* 06:20:00 UTC`. The 15-minute watch stays
  `*-*-* *:0/15:00 UTC`. Observation-schedule cadence is unchanged.

PR #293 storage formula is unchanged: `resident = total - open`; OPEN
(including `*.json.tmp`) counts once as staging; completed/legacy stay resident.

The 2026-09-06 unattended-operability owner readout still mentions `06:15 UTC`
as the pulse time from that historical atom. That document is **historical**.
Current operator truth is `*-*-* 06:20:00 UTC` in
`docs/operator/FACTORY_UNATTENDED_OPERABILITY.md` and the timer template.

## What did not change

- Collector / scheduler / provider / publication execution
- TARGET40 / HARD50 and physical disk warning/critical
- `SOURCE_DATA_STALE` (`age > period * 3`, watch grace 1800s)
- The 18 SEARCH `CENSORED_LATE` rows from 2026-09-11
- No swap, no cgroup MemoryMax, **no deploy**

## Live commissioning (later deploy, not this atom)

After a separate live→target cumulative review and deploy, measure:

- MemoryPeak / MaxRSS for watch and pulse
- collector MemoryPeak on an ordinary tick
- packet wall time
- source-poll continuity
- OOM journal
- Workbench continuity

Do not claim a production RSS number from unit tests.

## Residuals

- `REMOTE_DOCTOR_SINGLE_SAMPLE_FALSE_DOWN_WATCH`
- 18 SEARCH `CENSORED_LATE` remain typed missingness
- live MemoryPeak unknown until post-deploy

## Next exact atom

`FACTORY_SOURCE_DATA_STALE_EXPECTATION_AWARE_V1`

## Next owner gate

Exact merge phrase after exact-head CI and merge-readiness. **NO DEPLOY.**
