# TASK-30 Forward raw trade route contract v1

## Consumer and decision

The sole consumer is
`RC001-H07-H01-LIQUIDITY-RETENTION_FORWARD_DATA_ENTRY_GATE`.

The only offline decision is `OFFLINE_FORWARD_ROUTE_CONTRACT_VALIDATED`.
It says that synthetic coverage semantics are specified. It does not select a
provider or authorise an external pilot.

## Forward envelope

A future observed record needs one stable `connection_epoch`, `signature`,
pool identity, source-route label, observed/available/ingested times, slot,
interval start and raw content hash. Its decoder and market values are outside
this contract.

`OBSERVED` is a retained synthetic observation shape. `TRANSPORT_LOST` is not a
market observation. It creates `UNKNOWN` until a separately authorised
reconciliation record closes the exact coverage interval.

## Coverage and projection

The policy states are `COMPLETE`, `GAP_SUSPECTED`, `UNKNOWN`, `RECONCILED`,
`INVALID` and `STOPPED`.

`COMPLETE` in an offline test means only that the synthetic record sequence has
no unresolved transport loss. It does not make an interval projectable into
price or volume data. `UNKNOWN` is not empty, zero, flat, no-trade or complete.

Duplicate signatures inside one connection epoch, a wrong pool identity, a
missing raw hash, retry, fallback, or reconnect before reconciliation fail
closed. An unresolved transport loss returns `UNKNOWN` and `STOP_RUN`.

## Reuse-first boundary

The retained A12 research result records
`HELIUS_TRANSACTION_SUBSCRIBE=WRAP_CANDIDATE`. It provides a documented
filtered transaction stream, but its own indexing documentation requires gap
detection and backfill after disconnect. `YELLOWSTONE_OR_MANAGED_REPLAY` is
`WATCH_ONLY` until a future named consumer proves that its additional cost and
complexity are justified.

Before a future build or external owner packet, the reusable candidates require
a current official-document check, at least two maintained examples where
available, license/maintenance/security/exit review and an
`ADOPT | WRAP | FORK | BUILD | NO_FIT_FOUND` decision.

## Authority

This contract permits local tracked documentation, synthetic fixtures, pure
evaluation, tests, Catalog maintenance and ordinary Git delivery only. It
permits no provider/API/RPC/WSS action, credential use, raw retention write,
scheduler, dependency change, R2/R3, wallet/signer/transaction, cash, trial or
Project Sources change.

A later packet must name one provider, transport, identity binding, duration,
budget, raw-retention location, monitoring owner, reconciliation source and
stop/recovery conditions. It remains a separate owner decision.
