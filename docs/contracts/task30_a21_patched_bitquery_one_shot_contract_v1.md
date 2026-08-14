# TASK-30 A21 — Patched Bitquery one-shot contract v1

## Decision and consumer

The named consumer remains `RC001-H07-H01-LIQUIDITY-RETENTION`. A20 consumed
its one authorized request and stopped as `ROUTE_UNKNOWN_STOP` because the
pre-patch runner collapsed `HTTPError` into `TRANSPORT_ERROR` and did not
retain HTTP status or response bytes. This atom binds a later same-route
one-shot on the patched client already merged at
`3b532d6ad4a875837bee061ff2e7832e86344fdb`. It is not a retry inside A20 and
does not reopen provider churn.

## Exact route binding

Reuse the A20 identity and window without drift:

| Field | Value |
| --- | --- |
| Route ID | `BITQUERY-SOLANA-PUMPSWAP-OHLCV-001` |
| Endpoint | `https://streaming.bitquery.io/graphql` |
| Dataset/cube | `Solana(dataset: archive)` / `DEXTradeByTokens` |
| Pool | `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S` |
| Base mint | `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK` |
| Quote mint | `So11111111111111111111111111111111111111112` |
| PumpSwap program | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` |
| UTC window | `[2026-08-12T00:00:00Z, 2026-08-13T00:00:00Z)` |
| Interval | 15 minutes, 96 closed slots |

## Evidence retention

The patched `perform_http_post_once` must retain `HTTPError.code` and any
safe response body. Collapsing HTTP into `TRANSPORT_ERROR` is forbidden.
True transport failure may still leave `http_status` null. A20 receipts,
script paths and negative-result row stay immutable. A21 writes only
`local/task30_a21_bitquery_one_shot/` and
`docs/evidence/task30/a21p_patched_bitquery_one_shot_runtime_receipt_v1.json`.

## Authority gate

The owner authorized exactly one patched Bitquery POST after confirming the
local `BITQUERY_ACCESS_TOKEN` is present. Capture may proceed only through
`scripts/run_task30_a21_patched_bitquery_one_shot.py` after a credential-free
preflight. Zero retry, zero fallback, zero second provider. The token value
never enters Git, chat, CLI arguments, URL, receipts or logs.

## Terminal outcomes and non-claims

This capture may return only `COMPLETE_96_SLOT_MARKET_PANEL`,
`PARTIAL_TYPED_GAP_PANEL` or `ROUTE_UNKNOWN_STOP`. Historical OHLCV does not
establish fillability, execution, PnL, NetReturn, alpha, H07/H01 evidence or
TASK-30 acceptance. Missing is never zero, flat, inactive or no-trade.
