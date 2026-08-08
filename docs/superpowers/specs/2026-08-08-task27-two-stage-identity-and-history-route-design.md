# T27-A1R1 — Two-stage identity and history-route design

## Decision

Design a small, staged alternative to the failed keyless GeckoTerminal pilot.
The proposed atom is
`T27-A1R1_TWO_STAGE_IDENTITY_AND_HISTORY_ROUTE_DESIGN_V1`.  It prepares a
future decision path only; it does not contact a provider, read a credential,
retain any new raw response, or change TASK-27 acceptance.

The design intentionally assigns different providers to different facts:

- DexScreener establishes the public identity of the owner-nominated Solana
  pool and its base-token mint; and
- Solana Tracker is tested as the source of historical, pool-specific 15-minute
  OHLCV bars.

This is a staged hand-off, not an automatic fallback.  One provider may not be
silently substituted for the other.

## Why this route

The earlier GeckoTerminal pilot exhausted its two authorised requests with an
access-denied response.  Retrying that route, switching browser signature, or
trying an unbounded alternate URL would add cost without new information.

Three alternatives were considered:

1. **Solana Tracker only.** Rejected as the first step because its pair-chart
   endpoint needs both a token mint and pool address; the current nominated
   URL never established the mint as a verified fact.
2. **DexScreener as the historical candle source.** Rejected because its
   documented public API exposes pair identity and current aggregates, but no
   historical OHLCV endpoint.
3. **Reconstruct candles from Helius transaction history.** Deferred. Helius
   is suitable for later on-chain provenance and transaction reconstruction,
   but it would turn this cheap source-feasibility check into an indexed-data
   engineering task.
4. **Two stages: DexScreener identity, then Solana Tracker pool OHLCV.**
   Selected. It resolves the unknown mint with one bounded public identity
   query, then tests the only candidate that documents the required pool-level
   bars.

## Stage A — exact public identity resolution

A later owner gate may authorise exactly one unauthenticated GET:

```text
https://api.dexscreener.com/latest/dex/pairs/solana/URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S
```

The response is acceptable as an identity snapshot only when it contains
exactly one matching Solana pair whose `pairAddress` equals the nominated pool
address and whose `baseToken.address`, `quoteToken.address`, and `dexId` are
explicit.  The selected base mint becomes a newly frozen input, with raw-body
hash, parsed-output hash, response time, and retention record outside Git.

Stage A establishes neither historical coverage nor price truth.  It does not
admit the pool to a watchlist, make a market-universe claim, or create an
execution path.

## Stage B — exact authenticated pool-history pilot

Only after Stage A is retained and content-bound may a new separate owner gate
authorise Solana Tracker.  The gate must name the frozen base mint and may
authorise at most these two GETs:

1. `https://data.solanatracker.io/tokens/{base_mint}` to prove that the
   provider itself maps the frozen mint to the nominated pool; and
2. `https://data.solanatracker.io/chart/{base_mint}/{pool}` with an exact
   24-hour UTC boundary and the explicit parameters:
   `type=15m`, `time_from`, `time_to`, `currency=usd`,
   `removeOutliers=false`, `fastCache=false`, and `timezone=UTC`.

The Solana Tracker API key is supplied only as an HTTP header by a local
process from its secret environment.  It must never appear in a URL, command
history, repository file, raw manifest, receipt, test fixture, or chat.  The
future approval must state the maximum request count and the owner's known
quota/credit boundary; this design makes no free-tier, cash-cost, or quota
claim.

The pool-specific endpoint is mandatory.  The token-only chart endpoint is
forbidden because it can dynamically select a main pool and would not prove
that the resulting bars belong to the nominated pool.

## Acceptance, failure and evidence

The Stage B pilot can emit exactly one of:

- `READY_FOR_BOUNDED_HISTORY_CAPTURE`;
- `REDESIGN_PUBLIC_HISTORY_ROUTE`; or
- `CLOSE_PUBLIC_HISTORY_ROUTE`.

The ready state requires the two provider identities to agree on the same
network, pool, base mint and declared DEX; exactly 96 unique, ascending,
900-second-aligned 15-minute bars for the frozen 24-hour window; positive and
internally consistent OHLC values; observed USD volume; and raw hashes that
reconcile to parsed output.  The response wire key is validated as actually
returned and retained; it is never silently corrected by a parser.

Any HTTP/authentication/quota failure, identity mismatch, absent raw manifest,
wrong wire shape, incomplete panel, duplicate, time-grid gap, missing volume,
or raw-hash mismatch stops the stage.  It cannot trigger a retry, a request to
Helius, a token-level chart substitute, imputation, or a widened request cap.
It yields a failure receipt and a new owner decision only.

Raw bodies remain outside Git.  Failed or unusable probe evidence follows the
existing 30-day A4 retention rule; decision-supporting data remains with its
dependent research.  Tracked artifacts may contain only request identity,
hashes, status, and a sanitized decision.

## Deterministic implementation and test scope

The eventual offline implementation will add a versioned route contract,
configuration, Catalog schema, synthetic fixture, focused test module, and
acceptance receipt.  Its tests must accept one valid synthetic two-stage
packet and reject at least:

- a DexScreener result that does not exactly match the nominated Solana pool;
- attempting Solana Tracker before a frozen Stage A identity;
- a token-only or dynamically-selected-pool chart request;
- a missing explicit 15-minute UTC window or any hidden smoothing/cache
  default;
- key material in a URL, fixture, receipt, or log field;
- an unbounded quota/call-cap claim;
- retry, automatic provider fallback, or Helius reconstruction after failure;
- an incomplete or altered 96-bar panel; and
- PIT, alpha, execution, PnL, NetReturn, cashflow, or TASK-27-completion
  claims.

No generic data platform, provider adapter framework, dependency, scheduler,
wallet, signer, transaction, or Project Source release is justified by this
atom.

## Authority and horizon

This design authorises only bounded repository documentation and deterministic
synthetic validation under the standing repository policy.  It authorises
zero provider/API/RPC/WSS calls, credentials, raw response retention, R2/R3
reads, wallet/signer/transaction actions, and cash spend.

`NOW`: freeze and test this two-stage route so the next real read is minimal,
verifiable, and cannot accidentally become a data-collection programme.

`WATCH`: the one-call DexScreener identity probe.  Activate only after the
design and its implementation pass delivery, and after the owner separately
approves that exact URL, one-call cap, raw retention, and the stated
non-claims.  Solana Tracker remains a later, separately authorised stage.
