# TASK-30 A13 — Forward stream owner-packet readiness

## Objective

Create the smallest deterministic offline packet that lets the owner review a
future one-shot, read-only transaction-stream technical pilot for the frozen
H07/H01 consumer.  The packet makes scope, caps, stop conditions and
non-claims machine-checkable before any provider connection exists.

## Consumer and frozen identity

- Consumer: `FUTURE_EXACT_OWNER_EXTERNAL_READ_GATE`
- Frozen group: `RC001-H07-H01-LIQUIDITY-RETENTION`
- Network: `solana`
- Pool: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`
- Base mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`

## Scope

The only deliverable is an offline contract, evaluator, Russian owner readout,
synthetic fixtures/tests, acceptance evidence and Catalog bindings.  The
proposal names a candidate `HELIUS_TRANSACTION_SUBSCRIBE` wire profile for a
possible later pilot; it does not select a provider or assert an entitlement.

## Hard boundaries

- Provider/API/RPC/WSS calls, credential reads, raw writes, scheduler,
  dependency changes, R2/R3, wallet/signer/transaction actions, cash spend,
  trial and Project Sources change are zero.
- One future pilot may only be authorised by the exact owner phrase in the
  versioned config.  It is one foreground connection, one subscription, at
  most 1,200 seconds and 500 notifications; retry/reconnect/fallback are false.
- `UNKNOWN` requires separately authorised reconciliation.  It is never an
  empty interval, zero volume, complete coverage or hypothesis evidence.
- The future technical pilot cannot claim PIT admissibility, H07/H01 evidence,
  alpha, strategy, execution, settlement, PnL, NetReturn or TASK-30 acceptance.

## Reuse decision

`WRAP_CANDIDATE`: a future implementation may inspect the bounded WSS capture
and receipt safety pattern in `lifecycle_discovery_transport.py`.  Its Pump
`logsSubscribe` binding and parser are explicitly not a direct fit for this
`transactionSubscribe` candidate.

## Done condition

The pure evaluator rejects every authority or truth promotion listed in the
contract, the rendered packet remains non-technical and secret-free, all
artifacts are hash-bound, and all durable contract/runtime/report/evidence
outputs are Catalog-discoverable.  The accepted design and implementation plan
and this task note remain hash-bound process documents rather than Catalog
product assets.  The delivery stops before a provider or owner-external-read
action.
