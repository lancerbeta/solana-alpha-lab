# FACTORY_OPERABILITY_SIGNAL_CALIBRATION_V1 — owner readout

## What changed

Collector operability health is now **recovery-aware**.

- 24h provider counters stay diagnostics.
- Current `PROVIDER_FAILED` / `PROVIDER_AUTH_FAILED` / `PROVIDER_RATE_LIMITED` follow the **latest outcome per primitive**, by timestamp.
- Proven recovery is a later same-primitive `HTTP_OK` only. A later `STARTED` or unclassified call cannot clear an unresolved failure.
- A later success on a **different** primitive cannot hide an unresolved failure.
- 97d runway uses `resident_rdp_bytes = observation_rdp_bytes - publication_jobs_open_bytes` from one filesystem walk.
- OPEN job bytes count **once** as `staging_peak_bytes`.
- Daily storage-history sample is skipped while an OPEN publication job exists; the pulse still succeeds.

## What did not change

- Collector / scheduler / provider / publication execution
- `operability_watch.py` grace/dedupe/recovery
- TARGET40 / HARD50
- Physical disk warning/critical
- `SOURCE_DATA_STALE` (still `age > period * 3`)
- No deploy, no live VPS mutation

## Residual watch

`SOURCE_DATA_STALE_LONG_TICK_FALSE_POSITIVE_WATCH` — healthy ticks may last ~5 minutes while period is 60s. Out of scope here.

## Next owner gate

Exact merge phrase after exact-head CI and merge-readiness. **NO DEPLOY.**
