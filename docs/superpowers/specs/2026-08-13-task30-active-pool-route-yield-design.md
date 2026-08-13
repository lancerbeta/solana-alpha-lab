# TASK-30 A17 — Active-pool route-yield discriminator design

**Date:** 2026-08-13
**Status:** `A17_DESIGN_APPROVED`
**Entry Gate:** `START_WITH_PATCH`
**Specification route:** `DESIGN_SPEC`

## Task Outcome Brief

- `OWNER_DECISION`: decide whether the standard Helius pool-targeted route is
  worth extending into one named forward-panel capability, must be pivoted, or
  should be closed with `UNKNOWN` instead of another suffix attempt.
- `PRODUCT_OUTCOME`: remove the route-yield uncertainty blocking the
  `RC001-H07-H01-LIQUIDITY-RETENTION` data lane.
- `NAMED_CONSUMER`: `RC001-H07-H01-LIQUIDITY-RETENTION`.
- `CHEAPEST_FALSIFIER`: in one bounded window, select a currently active Orca
  POPCAT/SOL pool, listen for its first standard `logsSubscribe` notification,
  and only after an acknowledged zero-notification window reconcile the same
  interval with one `getSignaturesForAddress` page.
- `TERMINAL_OUTCOMES`: `ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY`,
  `ACTIVE_BUT_NO_WSS_YIELD`, `NO_ACTIVITY_DURING_WINDOW`,
  `NO_ACTIVE_TARGET_STOP`, `TRANSPORT_OR_COVERAGE_UNKNOWN`.
- `USER_VISIBLE_RESULT`: one plain route decision explaining whether a live
  active-pool transaction reached the standard stream, failed to reach it, was
  absent in the observed window, or remained unknown.
- `NON_GOALS`: no trade decoding, candle construction, price/volume panel, PIT
  admission, hypothesis trial, provider selection, scheduler, wallet,
  transaction, execution, PnL or NetReturn.
- `EVIDENCE_BUDGET`: at most one keyless DexScreener GET, one Helius WSS
  connection/subscription for 180 seconds and one conditional Helius RPC;
  no retry/reconnect/fallback, zero cash, A4 raw retention outside Git.
- `REPLAN_TRIGGER`: any repeated route blocker, second post-A17 provider/route
  pivot, inability to bracket the WSS window, or budget widening forces an
  explicit `PIVOT | ACCEPT_UNKNOWN | DEFER | CLOSE`; it must not create A17R1.

## Evidence and problem

A15P proved that standard Helius `logsSubscribe` accepted the frozen PumpSwap
pool subscription but returned no notification in ten minutes. A16P then
returned a valid 1,000-signature page whose time coverage bracketed that window
and contained no direct pool-address activity. Therefore A15P did not test WSS
yield on an active target.

A16R1 retained the verified public transport route and observed an active Orca
POPCAT/SOL pool through DexScreener. Its following Helius activity request ended
before an HTTP/RPC response, so the active-target route itself remains untested.
Repeating the old PumpSwap pool or separating activity and stream into distant
windows would not answer the owner decision.

## Reuse decision

`WRAP`:

- resolve all three external routes through append-only successor
  `PROVIDER-ROUTE-CAPABILITY-REGISTRY-002`, which preserves both v1 route
  semantics and adds only the A15P-observed Helius Standard WSS
  `logsSubscribe` route without rewriting the hash-bound v1 snapshot;
- reuse the existing secret-safe `BoundProbeRequest`, `WssCapture` and
  `HttpCapture` boundaries;
- reuse the standard Solana `logsSubscribe` and
  `getSignaturesForAddress` semantics;
- retain exact raw bytes under A4 outside Git.

No new dependency, generic collector, scheduler, decoder or provider layer is
introduced. Official protocol facts are frozen from Solana's
`logsSubscribe`/`getSignaturesForAddress` documentation; the provider route is
evidence-bound to the repository registry rather than rediscovered at runtime.

## Frozen target selection

The keyless discovery request is exactly the DexScreener Solana token-pairs
route for POPCAT mint `7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr`.
Eligible rows must bind:

- `chainId=solana`;
- `dexId=orca`;
- base mint = POPCAT;
- quote mint = wrapped SOL
  `So11111111111111111111111111111111111111112`;
- integer `txns.m5.buys + txns.m5.sells >= 1`;
- a valid Solana `pairAddress`.

Selection is deterministic: highest m5 transaction count, then highest finite
non-negative USD liquidity, then lexicographically smallest pool address.
No eligible row stops before credential read or Helius transport.

## Same-window state machine

1. Execute the one keyless discovery GET and retain exact bytes.
2. Select one active pool using the frozen rule. If none exists, return
   `NO_ACTIVE_TARGET_STOP`; Helius key reads and calls remain zero.
3. Run keyless DNS/TCP preflight. A failed preflight returns
   `TRANSPORT_OR_COVERAGE_UNKNOWN` before credential read.
4. Read `HELIUS_API_KEY` only in memory and open one standard WSS connection.
   Send one `logsSubscribe` with `mentions=[selected_pool]`, commitment
   `confirmed`, stop after the first valid notification or 180 seconds.
5. A valid target-bound notification returns
   `ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY`; no RPC follows.
6. Only an acknowledged, clean, zero-notification bounded window allows one
   `getSignaturesForAddress` request for the same pool.
7. A valid newest-first page brackets the window only when its newest non-null
   `blockTime` is at or after the terminal second and its oldest non-null
   `blockTime` is at or before the acknowledgement second. Strictly interior
   signatures produce `ACTIVE_BUT_NO_WSS_YIELD`; zero interior signatures
   produce `NO_ACTIVITY_DURING_WINDOW`. Any transport, schema, ordering,
   target or bracketing uncertainty stays `TRANSPORT_OR_COVERAGE_UNKNOWN`.

## Research-truth boundary

A WSS notification only proves technical route yield for a transaction that
mentions the selected pool. It is not necessarily a swap and contains no
accepted price or volume. An RPC signature only proves direct address activity.
Missing/unknown never becomes zero volume, an empty interval or PIT evidence.

## Offline authority and future gate

Tracked A17 bytes have zero provider authority. Future execution requires the
exact phrase emitted by the validated contract, and remains capped at:

- one public keyless GET;
- one Helius credential read and WSS connection/subscription;
- 180 seconds, one notification, 300,000 stream bytes;
- one conditional RPC with limit 1,000;
- estimated Helius credit cap 8, zero cash;
- no retry, reconnect, fallback, scheduler or transaction follow-up.

## Terminal task-level rule

A17 is the last route-yield discriminator in this branch. A technical-yield
result may enable a separately named Orca decoding/capture capability only for
a named consumer. Every other terminal result returns to the TASK-30 owner
decision (`PIVOT`, `ACCEPT_UNKNOWN`, `DEFER`, or `CLOSE`). It cannot silently
authorize another route probe.
