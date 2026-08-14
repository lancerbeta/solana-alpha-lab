# TASK-30 A22 Helius `getTransactionsForAddress` one-shot contract v1

## Decision

Test one existing Helius route against the frozen A20 PumpSwap pool and closed
UTC day. The decision is binary: a complete raw full-transaction batch is
observed in one response, or this route stops with a typed reason.

## Frozen request

- Route: `HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001`.
- Address: `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`.
- Block time: `[1786492800, 1786579200)`.
- Full JSON transactions, ascending order, finalized, succeeded-only,
  `tokenAccounts=none`, version 0 supported, limit 1,000.
- One credential-free DNS/TCP/TLS preflight, then at most one POST.
- `HELIUS_API_KEY` is local-only. It may appear only in the in-memory request
  URL and never in arguments, output, logs, receipts, raw manifests or Git.

## Completeness and retention

`count < 1000` plus `paginationToken=null` is a complete response under this
bounded request. `count=1000` or any pagination token is a terminal incomplete
batch. No pagination, retry, fallback or second provider is allowed.

Exact response bytes are retained create-only under ignored
`local/task30_a22_helius_get_transactions_for_address/`. Git stores only the
byte count, SHA-256, safe transport facts and the validated projection.

Every returned row must be successful, inside the exact half-open window,
chronologically ordered, contain full transaction plus metadata, and bind the
queried pool address. Any drift fails closed; missingness is never converted to
zero activity.

## Claims boundary

A complete batch establishes only technical route fit for raw transactions.
It does not establish OHLCV, PIT admissibility, H07/H01 evidence, fillability,
route feasibility, execution, settlement, PnL, NetReturn, alpha, strategy or
TASK-30 acceptance. TASK-30 remains `BLOCKED_DATA` until a separately
authorized data-admissibility decision consumes the batch.

The exact owner authority is
`OK T30-A22 HELIUS_GET_TRANSACTIONS_FOR_ADDRESS_ONE_SHOT`. It authorizes one
provider POST, zero cash and no other external action.
