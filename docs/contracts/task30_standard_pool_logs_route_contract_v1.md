# TASK-30 standard pool logs route contract v1

## Consumer and decision

The sole consumer is `RC001-H07-H01-LIQUIDITY-RETENTION`. The offline
decision `OFFLINE_ROUTE_READY_FOR_OWNER_GATE` means only that one exact
pool-filtered Helius Standard WSS request and its fail-closed classifier are
specified. It does not authorize or perform an external connection.

## Frozen route

The route uses Solana `logsSubscribe` with exactly one `mentions` filter equal
to pool `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` and commitment
`confirmed`. The target is the frozen PumpSwap pair whose base and quote mints
are recorded in the policy. The existing pinned PumpSwap IDL decoder is the
only admitted event decoder.

One future foreground capture is bounded to one connection, one subscription,
600 seconds, 128 notifications, 1,000,000 stream bytes and an estimated cap of
21 credits. RPC follow-ups, retry, reconnect, fallback and scheduler are
forbidden.

## Truth boundary

An exact-pool decoded `BuyEvent` or `SellEvent` is a technical trade
observation. It is not interval coverage, PIT-admissible research evidence,
TASK-30 acceptance, execution evidence or NetReturn.

No notification remains `NO_OBSERVATION_UNKNOWN`; transport loss remains
`TRANSPORT_LOST_UNKNOWN`; truncation or schema drift remains
`TRUNCATED_OR_SCHEMA_DRIFT_UNKNOWN`. Missing is never projected to zero, flat,
empty or complete. Duplicate signatures, subscription drift and pool mismatch
fail closed.

## Authority and recovery

This atom permits tracked offline artifacts, synthetic fixtures, tests,
Catalog propagation and ordinary repository delivery. It permits no provider,
API, RPC or WSS call; no credential read; no raw external write; no R2/R3,
wallet, signer, transaction or cash action; and no TASK-30 trial or acceptance.

A real foreground capture requires the exact separately approved owner phrase
stored in the policy. Any loss of monitoring stops the run. Reconciliation and
RPC enrichment remain outside this route until an actual retained pool log
proves a named field gap.
