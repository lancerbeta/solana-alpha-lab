# TASK-30 Gecko interval-semantics contract v1

## Bound external operation

Exactly two public keyless HTTPS `GET` requests are allowed, once each, through
`https://api.geckoterminal.com/api/v2` for the frozen Solana pool
`URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`:

1. `ohlcv/minute` with `aggregate=15`, `currency=usd`, `token=base`,
   `limit=96`, `include_empty_intervals=false`, and a runtime-calculated closed
   `before_timestamp` divisible by 900;
2. `trades` with `token=base`.

The runner must reject a different method, scheme, host, path, pool, request
count, credential, redirect, retry, fallback, scheduler, or output root before
network I/O.  Its dry run has zero network I/O.

## Decision algorithm

For a direct trade, derive `slot_start=floor(block_timestamp/900)*900`.  Test
the trade's base-token USD price against the OHLCV low/high range at
`slot_start` for `START_LABELED` and `slot_start+900` for `END_LABELED`.
Select a model only if it has at least two usable trades from at least two
slots, no range contradiction, and the other model has at least one range
contradiction.  Any other outcome is inconclusive.

## Evidence and retention

Exact raw response bytes, a raw manifest, and sanitized local runtime receipt
are written only below ignored `local/task30_gecko_interval_semantics/` with
exclusive file creation.  A tracked receipt may contain only relative logical
locations, SHA-256, byte count, timestamps, HTTP/transport class, the limited
decision, and non-secret request metadata.

## Non-claims

The result cannot claim a complete or PIT-admissible panel, empty/no-trade
semantics, provider selection, H07/H01 research evidence, a trial, fill,
execution, settlement, PnL, or numeric NetReturn.  `STATE_CHANGE=NONE` and
Project Sources disposition is `NO_CHANGE`.
