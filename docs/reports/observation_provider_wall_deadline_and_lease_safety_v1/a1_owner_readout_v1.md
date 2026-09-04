# Owner readout — OBSERVATION_PROVIDER_WALL_DEADLINE_AND_LEASE_SAFETY_V1

## Outcome

Hard wall-clock provider-call deadline is owned by ObservationSchedule runtime:
a stalled Jupiter read-only opener cannot outlive the lease envelope and
self-fence via `LEASE_FENCED`. Socket `timeout_seconds` alone remains insufficient;
this atom adds an end-to-end wall around the logical provider operation.

## What changed

- `observation_provider_wall_deadline.py`: stdlib daemon-thread wall + optional lease heartbeat
- `tick_once` wraps the opener with `provider_call_wall_seconds` (default **60**, must be `< LEASE_SECONDS=120`)
- Heartbeat calls `renew_held_lease` during bounded waits; wall still forces the
  waiter to return typed TIMEOUT so the tick can release the lease (daemon worker
  is not joined; oneshot ticks exit with the process)
- Hard deadline → existing `TimeoutError` → typed `TIMEOUT` missingness (no fabricate / no auto-retry)
- Config/schema: `provider_call_wall_seconds`
- Deterministic tests: stall > lease-equivalent cannot `LEASE_FENCED`; STARTED restart stays fail-closed

## Non-claims

- No VPS deploy / live commissioning in this atom
- No provider route/credential change
- No retry/fallback widening
- No estimand/sampling change
- No `LEASE_SECONDS` increase as sole fix
- No systemd timer retune as primary repair

## After merge (separate owner gate)

Deploy SHA = merge commit on `main`. Minimal commissioning: timer tick readback —
`call_ledger` must not stick at `STARTED` for wall-budget stalls; no `LEASE_FENCED`
from single-tick provider I/O; RDP/scientific deadlines resume advancing.
