# TASK-30 A15 — Standard WSS pool trade route

## Objective

Prepare an offline, fail-closed route for one future Helius Standard WSS
`logsSubscribe` capture filtered by the exact frozen PumpSwap pool. Reuse the
existing pinned TASK-09 PumpSwap event decoder and do not build a second generic
streaming platform.

## Consumer and cheapest falsifier

The consumer is `RC001-H07-H01-LIQUIDITY-RETENTION`. The cheapest falsifier is
a deterministic exact-pool `BuyEvent` or `SellEvent` encoded through the pinned
IDL and classified without any provider access. Wrong target, duplicate
signature, subscription drift, truncation and type confusion must fail closed.

## Managed write set

The durable product assets are the versioned contract, YAML policy, JSON
Schema, synthetic fixture, pure route module, deterministic test, local renderer,
owner readout and two evidence receipts. This task note and the accepted design
and implementation plan are process documents and are intentionally outside
the product Catalog.

## Definition of done

- the request contains exactly one pool `mentions` filter and no RPC follow-up;
- policy and wire widening fail closed, including bool/int type confusion;
- synthetic exact-pool buy and sell events reuse the pinned PumpSwap decoder;
- missing, transport loss and truncation remain UNKNOWN;
- the Russian readout states the limits and no-authority boundary;
- acceptance hashes bind all eight implementation artifacts;
- FULL Factory Fit is `PASS_WITH_LIMITATIONS`;
- all ten product/evidence assets are Catalog-discoverable;
- targeted tests and the repository delivery gate pass;
- no provider, credential, raw external, transaction, cash or Project Sources
  action occurs.

## Stop boundary

Stop before any Helius connection, credential read or raw external write. A
future foreground capture requires a new exact owner phrase. It remains
technical evidence only and cannot become interval coverage, TASK-30 trial or
NetReturn without a later gate.
