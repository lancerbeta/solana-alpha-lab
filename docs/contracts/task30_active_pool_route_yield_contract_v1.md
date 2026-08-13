# TASK-30 A17 — Active-pool route-yield discriminator contract v1

## Purpose

This contract prepares one future, owner-gated same-window discriminator for
the `RC001-H07-H01-LIQUIDITY-RETENTION` consumer. It asks one narrow question:
does a standard Helius pool-filtered stream yield a notification while the
selected Orca POPCAT/SOL pool has direct address activity?

The tracked implementation is offline and has zero provider authority.

## Task outcome

- Owner decision: extend the route only after technical yield; otherwise choose
  `PIVOT`, `ACCEPT_UNKNOWN`, `DEFER`, or `CLOSE` at TASK-30 level.
- Product outcome: remove one route-yield uncertainty before any panel or trial.
- Cheapest falsifier: one current active-pool selection, one first-notification
  stream, then one conditional same-window signature page.
- User-visible result: one of the five terminal outcomes below.
- Evidence budget: one keyless GET, one Helius WSS and one conditional RPC;
  180 seconds; no retries; zero cash; A4 outside Git.
- Replan trigger: A17 is terminal for this route branch. A repeated blocker,
  another provider pivot or a widened evidence budget cannot mint A17R1.

## Frozen sequence

1. Resolve and use the verified
   `DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001` route for POPCAT.
2. Select an Orca POPCAT/WSOL row with at least one m5 transaction. Rank by m5
   transaction count descending, USD liquidity descending and address
   ascending.
3. If no row qualifies, stop before Helius credential read with
   `NO_ACTIVE_TARGET_STOP`.
4. After DNS/TCP preflight, read `HELIUS_API_KEY` only in memory. Open one
   standard `logsSubscribe` connection bound to the selected pool, commitment
   `confirmed`, and stop after the first notification or 180 seconds.
5. A valid notification ends the sequence without RPC as
   `ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY`.
6. Only a valid acknowledgement plus a clean elapsed bound and zero
   notifications permits one `getSignaturesForAddress` request for the same
   pool, commitment `confirmed`, limit 1,000.
7. The page brackets the window only when its newest non-null `blockTime` is at
   or after the terminal second and its oldest non-null `blockTime` is at or
   before the acknowledgement second. Strictly interior signatures mean
   `ACTIVE_BUT_NO_WSS_YIELD`; none mean `NO_ACTIVITY_DURING_WINDOW`.
8. Transport, acknowledgement, schema, ordering, target or coverage ambiguity
   means `TRANSPORT_OR_COVERAGE_UNKNOWN`.

## Exact runtime caps

- public DexScreener GETs: 1;
- Helius WSS connections/subscriptions: 1/1;
- WSS open time: 180 seconds;
- notifications/stream/frame: 1 / 300,000 / 100,000 bytes;
- conditional Helius RPC requests: 1;
- RPC limit/response: 1,000 / 2,000,000 bytes;
- estimated Helius credit cap: 8, not a billing claim;
- retention: A4 exact raw bytes outside Git;
- retry/reconnect/fallback/scheduler/transaction follow-up: 0;
- cash, wallet, signer, transaction, TASK-30 trial/acceptance: 0.

Future execution requires exact equality with
`owner_authority.future_runtime_phrase` in
`configs/task30_active_pool_route_yield_v1.yaml`. The phrase grants only this
one runtime sequence and does not grant TASK-30 acceptance.

## Terminal outcomes

- `ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY`
- `ACTIVE_BUT_NO_WSS_YIELD`
- `NO_ACTIVITY_DURING_WINDOW`
- `NO_ACTIVE_TARGET_STOP`
- `TRANSPORT_OR_COVERAGE_UNKNOWN`

Every terminal preserves `price=false`, `volume=false`, `zero_volume=false`,
`empty_interval=false`, `interval_complete=false`, `pit_admissible=false`,
`task30_trial=false`, `task30_acceptance=false` and
`numeric_netreturn=false`.

Every provider route resolves through append-only
`PROVIDER-ROUTE-CAPABILITY-REGISTRY-002`. The successor preserves the two v1
route semantics by hash and adds only the A15P-observed Helius Standard WSS
`logsSubscribe` route. The immutable v1 snapshot and its acceptance receipt are
not rewritten.

Once `intent.json` exists, discovery, preflight, credential, WSS, RPC and
classification adapter failures terminate as
`TRANSPORT_OR_COVERAGE_UNKNOWN` with a fixed safe stage code. Exception text is
never retained. Every terminal receipt carries the false price/volume claims
and the task-level replan policy; a non-yield result cannot create an automatic
A17 suffix atom.

## Reuse and non-goals

`REUSE_DECISION=WRAP`: provider route registry, repository request/capture
types, Solana RPC semantics and A4 retention are reused. This atom does not add
a dependency, decode an Orca swap, build candles, choose a production provider,
schedule collection, run an experiment, trade, reconcile money or calculate
PnL/NetReturn.

## Validation and status

Deterministic tests cover the closed policy/schema, target selection, request
binding, all terminal branches, false-zero boundaries, invalid acknowledgement,
conditional RPC ordering, secret-free retention, wrong authority and Catalog
discovery. `FACTORY_FIT_REVIEW=FULL_REVIEW`.

`PROJECT_SOURCES_DISPOSITION=NO_CHANGE`; `STATE_CHANGE=NONE` until a separately
authorized runtime result and task-level owner decision exist.
