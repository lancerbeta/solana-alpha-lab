# TASK-30 A20 — Bitquery named partial PIT route capture contract v1

## Decision and consumer

The named consumer is `RC001-H07-H01-LIQUIDITY-RETENTION` and the next
TASK-30 data-admissibility decision. This atom reopens only the data-route
question closed by A19; it does not reopen provider churn or establish the
hypothesis.

The cheapest falsifier is one credentialed Bitquery V2 GraphQL query for the
already frozen PumpSwap pool over one fully closed UTC day. Every one of the 96
15-minute slots becomes exactly one `OBSERVATION` or one typed
`MISSING_UNKNOWN` gap.

## Exact route binding

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
| Named notionals | `10, 25, 50, 100 USD` |

The exact window is a fully closed UTC day with at least one day of archive
settling margin at Entry. It is a technical data-route subject only;
representativeness remains `NOT_ESTABLISHED`.

## External and security boundary

The owner created a one-day manual Bitquery token for this task, stored it in
the local Windows user environment and confirmed its presence without sharing
the value. The runtime may read `BITQUERY_ACCESS_TOKEN` once, only after a
credential-free DNS/TCP/TLS preflight passes.

The cap is one credentialed POST, 2,000,000 response bytes, 100 Bitquery
points, 30 seconds, zero retry, zero fallback and zero cash spend. HTTP,
GraphQL, identity, byte-cap or retention failure is terminal.

The token may never enter the URL, CLI arguments, Git, raw manifest, receipt,
report, exception or log. Raw response bytes are retained under ignored
`local/task30_bitquery_pit_capture/` and hash-bound by the tracked runtime
receipt. The tracked receipt stores the full normalized 96-slot projection;
this is the explicit local raw-loss waiver for a reproducible historical
query.

## Terminal outcomes and non-claims

- `COMPLETE_96_SLOT_MARKET_PANEL`: all 96 slots are observed.
- `PARTIAL_TYPED_GAP_PANEL`: at least one slot is observed and every absence is
  an explicit typed gap.
- `ROUTE_UNKNOWN_STOP`: transport, auth, GraphQL, schema, identity, retention
  or zero-observation evidence cannot support a market panel.

Historical OHLCV and observed volume do not establish fillability for the
named notionals, quotes, route feasibility, settlement, inventory, execution,
PnL, numeric NetReturn, alpha, H07/H01 evidence or canonical TASK-30
acceptance. Missing never means zero, flat, inactive, no-trade or settled.
