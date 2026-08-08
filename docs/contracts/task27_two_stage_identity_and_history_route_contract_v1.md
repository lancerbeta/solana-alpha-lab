# TASK-27 two-stage identity and history-route contract v1

## Purpose

`T27-A1R1_TWO_STAGE_IDENTITY_AND_HISTORY_ROUTE_DESIGN_V1` freezes the
smallest offline decision contract for replacing the failed keyless
GeckoTerminal historical-price route. It separates pool identity from
historical OHLCV evidence. It makes no provider/API/RPC/WSS call, does not
read a credential, retains no new raw provider response, and does not change
TASK-27 acceptance.

The contract prepares two future, separately owner-gated stages:

1. DexScreener may establish the exact identity of the owner-nominated Solana
   pool and its base-token mint with one public pair lookup.
2. Only after that identity is retained and hash-bound may Solana Tracker be
   proposed for one provider-identity lookup and one pool-specific 15-minute
   OHLCV lookup.

This is a staged evidence hand-off, not a fallback chain. A failure in either
stage stops the route and requires a new owner decision.

## Stage A: public pair identity only

The sole future Stage A candidate is
`DEXSCREENER_PUBLIC_PAIR_IDENTITY`. A later exact owner approval may permit
one unauthenticated `GET` for the nominated Solana pool address. Its response
is an identity snapshot only when it explicitly matches:

- `network=solana`;
- the nominated pool address;
- one explicit base-token mint;
- one explicit quote-token mint; and
- one explicit DEX identifier.

Stage A must retain raw response bytes outside Git with request identity,
response/parsed hashes and the inherited A4 retention class. A tracked
receipt may carry only sanitized identifiers, hashes and decision state. It
does not establish a historical panel, price truth, market universe, watchlist,
alpha, execution route or permission to trade.

## Stage B: pool-specific historical OHLCV only

The sole Stage B candidate is `SOLANA_TRACKER_POOL_OHLCV`. It remains
unauthorised until Stage A has produced a retained, hash-bound base-token mint
and a new exact owner instruction names that mint, a frozen 24-hour UTC window,
request IDs, raw-manifest identities and the request cap.

The future instruction may permit at most two GETs:

1. a token-information request that must map the frozen base mint to the
   nominated pool; and
2. a pool-specific chart request for the same base mint and nominated pool.

The chart request must explicitly use 15-minute UTC bars, `time_from`,
`time_to`, `currency=usd`, `removeOutliers=false` and `fastCache=false`.
It must not use a token-only chart endpoint, a dynamically-selected main pool,
provider smoothing, cache substitution, a floating latest window or an
unbounded quota/cost assumption. The future key is header-only from a local
secret environment and must never appear in an URL, repository artifact,
fixture, raw manifest, receipt, log or chat.

## Acceptance and failure

The future Stage B pilot may emit exactly one outcome:

- `READY_FOR_BOUNDED_HISTORY_CAPTURE`;
- `REDESIGN_PUBLIC_HISTORY_ROUTE`; or
- `CLOSE_PUBLIC_HISTORY_ROUTE`.

The ready outcome requires provider identity agreement on network, pool and
base mint; an exact retained raw manifest; and 96 unique, ascending,
900-second-aligned, natural 15-minute bars covering the frozen 24-hour window.
OHLC values must be positive and internally consistent, and USD volume must be
observed. Missing data is `UNKNOWN`; it cannot become zero, carried-forward
or flat.

Any authentication, quota, provider, raw-manifest, identity, wire-shape,
alignment, duplicate, gap, volume or hash-reconciliation failure stops the
stage. It cannot retry, invoke Helius reconstruction, use a token-level chart,
switch provider automatically, relax the 96-bar rule or create a broader
capture authority.

Helius is deliberately deferred. Its transaction history may later support a
separate provenance/reconstruction decision, but it is forbidden as recovery
or fallback in this contract.

## Authority and non-claims

This atom performs only tracked documentation, configuration, schema, fixture,
test and receipt writes plus deterministic local validation. It makes zero
provider/API/RPC/WSS calls, uses zero credentials, retains zero provider bodies,
opens zero R2/R3 values or paths, creates no wallet/signer/transaction and
spends no cash. It changes no Project Source, release registry, dependency,
scheduler, runtime collector or generated Catalog file.

It establishes no descriptive sample, PIT admissibility, alpha, strategy,
quote, route, fill, inventory, PnL, NetReturn, cashflow or TASK-27 completion.
`READY_FOR_BOUNDED_HISTORY_CAPTURE` would be a future bounded data-route
decision only; it never grants provider or execution authority.
