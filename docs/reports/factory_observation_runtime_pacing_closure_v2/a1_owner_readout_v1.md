# Factory observation runtime pacing closure — owner readout

## Verdict

`FACTORY_OBSERVATION_RUNTIME_PACING_AND_OPERABILITY_CLOSURE_READY_FOR_MERGE`

## Root cause closed

ObservationSchedule intra-tick pacing reused a fresh `/recent` call as `last_provider_call_at`, so every 60s tick saw `PACE_WAIT` on the same frozen clock, SEARCH never advanced, and due rows starved into `CENSORED_LATE`.

## Repair summary

- Unified intra-tick pacing via `ProviderTickContext` and deferred RECENT until due work is schedulable.
- Oracle/read-model due pressure is activation-scoped; recommended envelope is **102 members / p=0.051** (capacity ceiling 456), not the stale 114 / 0.057 pair.
- Panel reuse is fail-closed when live due rows exist: parquet point ids alone cannot satisfy a consumer; temporal due proof and stale snapshot rejection at materialize time block long-horizon reuse from Y900 snapshots.
- `abort_schedule()` exposes `ABORTED_SAFETY` without resuming starved campaign `7db1c77a…`.

## VPS constraints preserved

- Campaign `7db1c77a…` / `ACT-7DB1C77A6F7AF4F3`: **PAUSED_OPERATOR**, MUST_NOT_RESUME.
- No replacement live campaign, no provider calls after pause, no VPS ABORT in this atom.

## Non-claims

- No canonical DONE, alpha, or cashflow.
- No resume/abort of live starved campaign on VPS without separate owner gate.
