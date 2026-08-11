# TASK-30 A12 — Forward raw trade route design

## Decision in one sentence

Do not build another 15-minute candle poller.  Prepare one narrow, future
provider-entry route that can capture raw Solana transaction observations for
the frozen `RC001-H07-H01-LIQUIDITY-RETENTION` consumer, classify every
coverage gap honestly, and derive 15-minute research panels only after those
raw observations are proven sufficient.

This is a design-only atom.  It selects neither a provider nor an external
action, and it creates no collector, scheduler, API/RPC/WSS connection,
credential use, raw-data write, trial, wallet action, cash action, or Project
Sources change.

## Durable process hook

This is not a one-off A12 ritual.  The project `start-solana-task` skill now
contains the conditional `REUSE_RESEARCH_GATE`: it runs only before a material
reusable capability might be built, duplicated, adopted or extended.  It
requires a small evidence-saturated scan of repository assets, official
documentation and comparable maintained work, then records one of
`ADOPT | WRAP | FORK | BUILD | NO_FIT_FOUND` in the task map.  It never turns a
routine repair into research theatre and never authorises a dependency,
provider call or external action.

## Why the route changes

The earlier provider-owned candle paths failed different truth requirements:

- the retained GeckoTerminal path has a boundary conflict and its live
  shakedown did not publish the expected closed 15-minute interval within the
  authorised observation offsets;
- the named Solana Tracker sample retained only 33 of the 96 requested
  intervals;
- the Birdeye history route is `HOLD_NO_AUTORETRY` after its observed quota or
  rate limit.

Those outcomes close their *tested routes*, not their providers or the
hypothesis.  Repeating a closed route does not improve the data.  The consumer
instead needs a future-forward, provenance-preserving record from which a
15-minute interval can be derived without turning a missing observation into a
zero-volume candle or a no-trade assertion.

## Research-first result

This design intentionally reuses the problem decomposition already established
by Solana infrastructure rather than presenting a custom stream as novel.

| Reference class | Reuse finding | A12 decision |
| --- | --- | --- |
| Official Helius `transactionSubscribe` documentation | A filtered transaction stream can deliver transaction updates with commitment and detail controls. | Candidate transport only; no route selection or connection. |
| Official Helius indexing guidance | Enhanced WebSockets can have gaps after disconnect and require application-level gap detection and backfill. | This becomes a hard admission requirement, not a later reliability improvement. |
| Official `helius-labs/helius-sdk` | The maintained SDK exposes typed subscription and unsubscribe semantics. | `WRAP_CANDIDATE`; inspect language/runtime fit before adding any dependency. |
| `rpcpool/yellowstone-grpc` / Helius LaserStream SDK | Mature streaming references provide a higher-capability option for later scale or replay needs. | `WATCH_ONLY`; they are disproportionate for a first named pool and may require paid or new infrastructure. |
| Public bot/indexer repositories | They show familiar ingredients—subscription, swap decoding, buckets and reconnect—but do not establish our PIT, coverage, consumer or cashflow contract. | Pattern reference only; no code copy or dependency adoption. |

The reusable unit is therefore not a bot.  It is a small **forward raw-observation
spine** with provider adapter, immutable observation envelope, coverage ledger,
and a downstream 15-minute projection.  Strategy logic, token selection,
signals, execution, dashboards and a generic platform are out of scope.

Before any future build atom, its entry receipt must contain:

1. current official provider documentation and commercial limits as-of the
   decision date;
2. at least two independently maintained open-source or provider examples;
3. an `ADOPT | WRAP | FORK | BUILD` verdict for each reusable candidate;
4. an explicit reason why the remaining local code is factory-specific; and
5. license, maintenance, secret-handling and exit-path checks.

Stars, marketing claims and an example compiling are discovery signals only;
they never substitute for these checks or for a deterministic local harness.

## Candidate approaches

### A. Provider-owned candles

Continue polling a provider's 15-minute OHLCV endpoint and retain returned
candles.  It is cheap to implement, but the three observed routes have already
failed the relevant completeness or freshness tests.  **Rejected for this
consumer now.**

### B. Filtered transaction stream plus explicit coverage ledger

Observe a single named pool or program through a future Helius-compatible
transaction stream, retain raw envelopes outside Git, and project only verified
raw observations into 15-minute intervals.  A transport discontinuity makes the
affected span `UNKNOWN`; it cannot be projected or retried silently.  A
separately specified reconciliation path must resolve or retain that gap before
the interval is eligible.  **Recommended candidate, pending a separate owner
external-read gate.**

### C. High-capability streaming with managed replay

Use a Yellowstone/gRPC or managed replay product.  This may reduce recovery
uncertainty, but adds transport, quota, dependency and operating complexity
before one pool has proved useful.  **Watch, not adopt.**

## Minimal future architecture

```text
one named pool/program
        |
provider adapter (future, one transport)
        |
raw observation envelope + content hash (outside Git)
        |
coverage ledger: CONNECTED | GAP_SUSPECTED | UNKNOWN | RECONCILED | STOPPED
        |
DEX-specific decoder (only for the named route)
        |
15-minute projection with explicit empty / unknown / invalid states
        |
H07/H01 research admission gate
```

The adapter must record at least a stable transaction signature, source route,
connection epoch, observed/available/ingested times, slot or block context,
raw content hash, parse disposition and pool-identity binding.  A decoded swap
also needs the factual token and quote deltas, fee or balance context when
available, and a decoder version.  It must not infer price, fillability,
execution, settlement or NetReturn from an incomplete record.

`UNKNOWN` is the crucial state: it means a transport/coverage gap exists and
the factory does not yet know whether observations are absent or merely missed.
A silent reconnect, an empty candle, a zero value, or a replacement provider
response cannot erase it.  Recovery is a distinct authorised action with its
own source, interval, reconciliation result and residual uncertainty.

## Future owner boundary

Only a later exact owner packet may name a provider, endpoint, credential
transport, pool/program filter, duration, raw-retention location, budget and
recovery source.  It must also prove that the process can stop before a second
run when monitoring, local storage, identity binding or reconciliation health
fails.

The first external pilot, if approved later, is a technical capture test—not a
TASK-30 trial.  It cannot claim panel completeness, PIT admissibility, H07/H01
evidence, alpha, strategy, execution, settlement, PnL or numeric NetReturn.

## Acceptance criteria for the next implementation plan

The plan must create a deterministic offline contract and synthetic tests that
reject at least:

- duplicate transaction signatures inside a connection epoch;
- a reconnect that lacks a declared coverage outcome;
- a raw record with the wrong pool/program identity;
- a decoder result without required token-delta provenance;
- an `UNKNOWN` interval projected as empty, zero, flat or complete;
- a retry or fallback before reconciliation;
- a provider, credential, scheduler or raw-write action attempted by offline
  code; and
- a promotion from technical capture readiness to hypothesis evidence or a
  trial.

`FACTORY_FIT_REVIEW` will be `FULL_REVIEW`: it must show that the smallest
reusable component advances the named consumer faster than one more historical
candle experiment, while keeping provider replacement and later hypotheses
possible.

## Boundaries and next decision

The only output of A12 is a reviewed implementation plan for the offline
contract.  It neither selects Helius nor authorises contacting it.  The next
material decision is whether the resulting owner packet justifies a minimal
credentialed forward-stream pilot under a measured free-tier budget.
