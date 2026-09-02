# FACTORY_PRODUCTION_CLOCK_PACING_ADAPTER_PARITY_REPAIR_V1 — owner readout

## Decision delta

Production ObservationSchedule ticks used `clock = lambda: datetime.now(UTC)`
(callable, **no `sleep`**). `tick_once` had a no-op adapter that still injected
that bare callable into `ProviderTickContext`. Pace waits bumped ignored
`_logical_offset` without sleeping, burned `MAX_INTRA_TICK_PACE_WAITS`, returned
`PACE_WAIT` after RECENT, and never issued SEARCH — commissioning #3 starvation.

## Repair

- Added explicit `WallClock` (`now`/`__call__` + real `time.sleep`).
- Production CLI supplies `WallClock()`.
- Bare callables without sleep fail closed (`CLOCK_SLEEP_REQUIRED`).
- Tests use `AdvancingClock` (no real 3s sleeps).
- Oracle/science envelope unchanged (85 / 0.0425 / 17 due slots / X300 / retry=false).

## Live pause (ops)

- `ACT-1AC23901907ECC8A` → `PAUSED_OPERATOR`
- `ACTIVE_COUNT=0`; timer remains enabled/active
- call_ledger baseline 108 frozen across 3 timer cycles
- `MUST_NOT_RESUME=true`; `SCIENTIFIC_USE=COMMISSIONING_ONLY`
- No VPS abort; no repair deploy; no replacement campaign

## Product Horizon (report only)

- Measure real SEARCH latency before revisiting zero-headroom p99 envelope.
- Global Jupiter pacing across >1 simultaneous live schedule.
- Legitimate end-of-tick `PACE_WAIT` still maps to systemd exit 2 — operational
  semantics radar only; not expanded in this atom.

## Stop

Merge gate after exact-head CI. No VPS deploy of this repair in this atom.
