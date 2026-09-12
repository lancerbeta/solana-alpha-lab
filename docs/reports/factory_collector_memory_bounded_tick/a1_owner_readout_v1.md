# Owner readout — FACTORY_COLLECTOR_MEMORY_BOUNDED_TICK_V1

## Result

Ordinary ObservationSchedule collector tick no longer materializes the full
activation/due/member census as concurrent Python/Arrow copies. Pending prove
stays schedule-wide (base parity) without loading due row dicts; SNAPSHOT_PLUS_DELTA
V2 writes stream ops; recovered CLAIMED stays uncapped; systemd template adds
MemoryHigh=768M / MemoryMax=1G (live sync is post-merge OPERATE only).

## Measured

- Stress worker @ 150k members: MaxRSS ≈ 164 MiB (<< 1 GiB ceiling).
- Independent reviews: ARCHITECTURE_CRITIC / CODE_REVIEWER / GOAL_DOD_CRITIC = PASS
  at head `3c7be45b…` with packet `fb6349d4…`.

## Non-claims

No alpha, no canonical DONE, no live VPS mutate/deploy/resume in this atom,
no C1, no provider calls, no RDP rewrite.

## Next (post-merge OPERATE)

Exact-SHA deploy + unit sync, paused first tick with MemoryPeak, then timer, then C1.
