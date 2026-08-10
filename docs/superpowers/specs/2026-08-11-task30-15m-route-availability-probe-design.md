# TASK-30 A11A — 15m route-availability probe design

## Decision

Keep the frozen `RC001-H07-H01-LIQUIDITY-RETENTION` candidate on its declared
15-minute observation grid.  The factory remains cadence-neutral for later
hypotheses, but changing this frozen candidate to one-minute or seconds after
seeing a data inconvenience would create a new hypothesis, not a better test
of this one.

Before a 24-hour technical capture, run one smaller future availability probe.
It answers a single question: after a 15-minute interval closes, does a named
market-data route expose a start-labelled candle by one bounded, repeatable
delay?  It does not test alpha, a research trial, fillability, execution,
settlement, or NetReturn.

## Why this is the smallest useful step

`T30-A10` established that the observed GeckoTerminal timestamp is
start-labelled.  It did not establish how soon a newly closed candle is
published, whether its final value remains stable, or whether a 24-hour route
would record every slot as an observation or an explicit gap.  Starting a
96-slot run without that answer could create a day of ambiguous data.

Continuous 15-second polling is rejected.  It would create 5,760 requests per
day for repeated reads of the same 15-minute interval.  Short 15-second
spacing is retained only inside the future diagnostic probe, where it measures
publication lag rather than pretending to create seconds-resolution data.

## Reuse boundary

Reuse only the proven concepts from existing project components:

- `T30-A10`: start-label evaluator, raw manifest conventions and explicit
  non-claims;
- TASK-21: immutable slot identity, idempotency, typed gaps, capacity caps and
  recovery vocabulary.

Do not directly reuse the TASK-21 collector runtime: its population, quote
adapter and accepted consumer are TASK-21-specific.  Do not add an SDK,
generic provider abstraction, generic collector, scheduler, dependency or
database.

## Future external probe shape — not authority

The later owner packet may propose, but this document does not select or call,
one named provider and one named pool.  A candidate using the already observed
GeckoTerminal pool route would have these maximum bounds:

| Field | Proposed bound |
| --- | --- |
| Closed 15m boundaries | 3 |
| Reads per boundary | 4 at offsets `+0s`, `+15s`, `+30s`, `+60s` |
| OHLCV reads | 12 maximum |
| Identity read | 1 maximum, only if separately bound |
| Retries / fallback | 0 / forbidden |
| Credentials, spend, wallet, R2/R3 | 0 |

Each response must retain request time, response time, response hash, expected
interval start and a classification.  Missing, malformed or inconsistent
responses become explicit typed gaps or failures; they never become zero
volume, flat price, no trade or a successful slot.

The probe can return only:

- `READY_FOR_FIXED_DELAY_24H_TECHNICAL_CAPTURE` — all three boundaries expose
  the expected closed interval by the same bounded delay and the retained
  observations are stable;
- `ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE` — the route misses, revises or
  contradicts the expected interval;
- `INCONCLUSIVE` — insufficient or semantically ambiguous evidence.

Only the first result can justify asking for a later 24-hour technical capture
of at most 96 slots.  That capture would still be route feasibility evidence,
not H07/H01 evidence or a trial.

## Anti-one-shot activation ladder

A 24-hour run must never be the first execution of a future capture mechanism.
The later external work is deliberately staged so that a scheduler, clock,
raw-write or monitoring defect appears within minutes rather than at the end
of a day.

1. **Offline acceptance.** Deterministic fixtures exercise every classifier,
   idempotent slot identity, raw-manifest binding, capacity limit, typed-gap
   path and stop path with no provider call.
2. **Two-slot live shakedown.** Under its own smaller owner packet, make two
   planned closed-slot observations in two independent short process starts.
   The starts must use the same scheduling mechanism intended for the later
   run.  Read back both receipts immediately.
3. **Sustained capture.** Only a passing two-slot shakedown can be followed by
   a separately authorised 96-slot run.  Each slot writes one health/receipt
   update, so its state is observable before the next slot.

The sustained run distinguishes two classes of absence:

- an invoked process receives no valid candle: retain the result as the
  provider/market typed gap and continue only if monitoring remains healthy;
- a process did not start, cannot write its receipt, cannot read the prior
  manifest, or loses monitoring: stop the run immediately.  Do not silently
  restart, backfill or wait until the final report to disclose it.

The later implementation may use a short independent invocation per slot with
shared idempotent state.  It must not rely on an unattended long-lived process
to survive for 24 hours, and it must not add a general scheduler platform.

## Required future owner gate

No network action follows from this design.  Before any probe the owner packet
must bind provider and endpoint, current pool identity, exact UTC boundaries,
request/quota cap, raw-retention location and hash plan, backup or tracked
waiver, monitoring owner, recovery path and the non-claims above.  Scheduler
activation and any 24-hour capture require a separate authority after the
probe result.

## Offline implementation follow-up

If the owner approves this design, the next bounded implementation atom may
create only a deterministic policy evaluator, synthetic fixture and tests for
the classifications above.  It must reject duplicate slot identities,
untyped gaps, retry/fallback, mixed offsets, unstable selected values and any
attempt to promote a technical result into research, execution or cashflow
truth.

## Acceptance for this design artifact

- The frozen 15-minute H07/H01 boundary remains unchanged.
- Minute/seconds strategies remain valid only as separately versioned future
  hypotheses with their own data and execution contracts.
- The future probe has a bounded purpose, a maximum of 12 OHLCV reads and no
  implicit external authority.
- Direct reuse of the TASK-21 runtime and creation of a generic capture
  platform are explicitly rejected.
- A real capture has an offline gate, two-slot live shakedown and immediate
  health stop before any 24-hour run.
