# TASK-21 observation-horizon correction contract v1

`T21-A6S_T1_HORIZON_GATE_CORRECTION_V1` removes the seven-day duration
from its accidental role as the exclusive start gate for all useful TASK-21
observations.

## Why the correction is required

The accepted T1 replay contains three outcome-blind nominations, zero
admissions and zero panels. No scheduler, collector or database writes occur
during the original P7D wait. Elapsed time alone therefore adds no evidence.
P7D remains useful as one observation horizon, but it is not evidence-based as
the only horizon or as a prerequisite for the first panel.

## Preserved truth

- The original source receipt and replay partition remain byte-for-byte
  unchanged.
- The original anchor and P7D timestamp remain historical facts.
- No observation is backfilled before it became reliably available.
- No quote, route, price, terminal outcome or hypothesis result was inspected
  to choose this correction.
- The three nominations remain unadmitted until a separate explicit authority.

## Forward-only replacement

The first real panel becomes eligible immediately after a separately
authorized admission and capture action. That first capture is `H0`; the
remaining frozen offsets are `+1h`, `+6h`, `+24h`, `+72h` and `+7d`.

These offsets are a bounded pilot measurement grid, not a universal market
law. Future hypothesis versions own their observation horizons. A missed
window is recorded as an explicit gap and is never silently backfilled or
rescheduled after seeing outcomes.

## Authority boundary

This correction is local-write-only. It authorizes zero provider/API/RPC/WSS
or Jupiter calls, zero candidate admissions, zero raw or dataset writes, zero
Drive operations, zero scheduler/background execution, zero cash spend and
zero wallet, signer or transaction actions.

The next boundary is
`T21-A6S_BOUNDED_ADMISSION_AND_MULTI_HORIZON_CAPTURE_V1` under a separate exact
authority. TASK-21 Catalog finalization remains deferred to `T21-A7`.
