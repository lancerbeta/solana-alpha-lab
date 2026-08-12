# TASK-30 A15 Standard WSS Pool Trade Route Design

## Decision

Use a thin Helius Standard WebSocket wrapper around Solana
`logsSubscribe`, filtered by the one frozen pool address, and reuse the
project-owned PumpSwap log decoder offline.  This is `WRAP`, not a new
collector and not a provider migration.

The atom proves only that the free-plan wire route, parser boundary and
truth classification are ready for one later owner-authorized foreground
pilot.  It performs no provider, RPC or WSS call itself.

## Why this route

The rejected A14P route used Helius-specific `transactionSubscribe`, which
the provider explicitly denied on the current free plan.  Current Helius
documentation includes standard Solana WebSockets on Free, and the Solana
RPC contract allows `logsSubscribe` to filter by exactly one mentioned
address.  That fits the frozen single-pool target without a new provider.

Repository evidence is stronger than a paper-only candidate:

- TASK-08 retained a bounded Helius standard-WSS capture;
- TASK-09 retained 257 `logsSubscribe` notifications and exercised the
  project PumpSwap decoder;
- the frozen pool is independently bound to `dex_id=pumpswap`;
- the decoder already preserves buy/sell atomic amounts, raw pool reserves,
  virtual quote reserves and fee fields.

External facts were checked on 2026-08-12 against:

- Helius plans: <https://www.helius.dev/docs/billing/plans>;
- Helius WebSocket methods: <https://www.helius.dev/docs/api-reference/rpc/websocket-methods>;
- Solana `logsSubscribe`: <https://solana.com/docs/rpc/websocket/logssubscribe>.

## Alternatives considered

1. **Recommended — Helius Standard WSS `logsSubscribe` by pool.**
   Reuses the current credential transport, existing WSS safety boundary and
   PumpSwap decoder.  It is available on the current free plan and keeps one
   provider/account surface.
2. **Public Solana RPC `logsSubscribe`.**
   Avoids credentials and uses the same standard wire contract, but changes
   provider reliability and quota semantics.  Keep as a separately gated
   fallback only if the Helius standard method is rejected.
3. **Paid `transactionSubscribe`, Yellowstone/gRPC or another provider.**
   Richer notifications can reduce follow-up work, but current evidence does
   not justify recurring cost, a new dependency or a new operational surface.
   Keep behind a measured completeness or capacity trigger.

## Frozen identity and wire contract

- network: `solana`
- pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`
- base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`
- quote mint: `So11111111111111111111111111111111111111112`
- DEX: `pumpswap`
- provider candidate: `HELIUS_STANDARD_WSS`
- method: `logsSubscribe`
- params: `[{"mentions":[pool]}, {"commitment":"confirmed"}]`
- one connection, one subscription, foreground only;
- no retry, reconnect, fallback, scheduler or automatic continuation.

The exact request body is deterministic and hashable.  A credential may be
accepted only as an in-memory argument by a later execution adapter; it is
never returned by `repr`, safe receipts, logs, fixtures or tracked evidence.

## Architecture

Create one narrow pure module for the route-specific contract.  It may reuse:

- `BoundProbeRequest` for endpoint and safe-receipt enforcement;
- TASK-09 `parse_logs_notification` for strict Solana notification parsing;
- the pinned PumpSwap IDL subset and decoder for attributed event decoding.

It must not import or copy the TASK-09 live runner.  TASK-09 monitors the
PumpSwap program universe; A15 monitors one frozen pool.  Sharing the parser
is correct, sharing the program-wide request binder is not.

The module exposes four responsibilities only:

1. validate the closed route policy;
2. build the exact pool-targeted subscription request;
3. classify synthetic acknowledgement/notification captures;
4. project only exact-pool decoded trade events into a sanitized readiness
   result.

No storage writer, scheduler, HTTP follow-up or live socket is added in A15.
The existing A14P raw-first attempt/reconciliation boundary remains the reuse
candidate for a later execution adapter, but its `transactionSubscribe`
classifier is not reused as if the wire formats were equal.

## Truth states

The classifier is fail-closed and returns one terminal state:

- `ROUTE_READY_OFFLINE` — the closed policy and synthetic happy path pass;
- `SUBSCRIPTION_REJECTED` — acknowledgement is a typed provider error;
- `TRANSPORT_LOST_UNKNOWN` — the connection state is not terminally known;
- `NO_OBSERVATION_UNKNOWN` — bounded time elapsed with no notification;
- `OBSERVED_POOL_TRADE` — at least one valid, exact-pool PumpSwap buy/sell
  event was decoded;
- `OBSERVED_NON_TRADE_OR_UNSUPPORTED` — a valid notification was observed but
  no admissible exact-pool trade was decoded;
- `TRUNCATED_OR_SCHEMA_DRIFT_UNKNOWN` — logs were truncated or the closed wire
  contract drifted.

`NO_OBSERVATION_UNKNOWN` is never an empty interval, zero volume or complete
coverage.  A failed transaction is retained but does not become a trade.
Decoded events whose embedded pool differs from the frozen pool are rejected,
not silently filtered.

## Why no `getTransaction` in the first pilot

The pinned PumpSwap event payload already contains the atomic user amounts,
pool reserves, virtual quote reserves and fee fields needed to test raw
price/volume feasibility.  Adding one HTTP read per signature would increase
cost and failure surface before a missing field is demonstrated.

`getTransaction` becomes a later bounded option only if a successful
exact-pool log observation lacks a field required by the named H07/H01
consumer.  A null result remains `UNKNOWN` and never becomes zero.

## Artifacts

- versioned contract and strict YAML policy;
- closed JSON Schema;
- pure route module;
- deterministic synthetic fixture and adversarial tests;
- Russian owner readout;
- hash-bound acceptance and FULL Factory Fit evidence;
- Catalog records and generated navigation.

The task/design/implementation-plan notes are process documents outside the
Catalog.  Product contract, config, schema, module, fixture, test, report and
acceptance evidence are Catalog-discoverable.

## Validation

Tests must prove:

- exact pool binding and exactly one `mentions` address;
- Standard WSS method and `confirmed` commitment;
- safe receipt and `repr` never disclose a credential;
- typed subscription rejection;
- no-notification, transport-loss and truncated-log states remain unknown;
- failed transaction retention without trade promotion;
- valid PumpSwap buy and sell decode for the frozen pool;
- pool mismatch, duplicate signature, malformed acknowledgement,
  notification schema drift and forbidden retry/reconnect/fallback fail;
- no output claims interval completeness, PIT admissibility, hypothesis
  evidence, alpha, execution, PnL or NetReturn.

Run the smallest targeted tests during implementation.  The exact committed
candidate uses the repository delivery route and CI as the full-suite owner
when eligible; otherwise use tracked-only delivery preflight.

## Boundaries and next gate

A15 has zero provider/API/RPC/WSS calls, credential reads, raw external writes,
dependency changes, R2/R3 access, wallet/signer/transaction actions, cash
spend, strategy promotion or TASK-30 acceptance.

After offline acceptance and delivery, stop before one exact owner external
gate.  That future gate may authorize only one foreground Helius Standard WSS
capture with fixed caps.  A successful transport result still does not accept
TASK-30; it only decides whether the observed raw events can support a later
15-minute projection.
