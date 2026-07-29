# TASK-17A execution-capacity quote panel summary v1

## Decision

`PASS_BOUNDED_QUOTE_ONLY_TEMPORAL_REPLICATION`.

The accepted matched set contains one versioned watchlist member and three
foreground windows: `T17A-WINDOW-01`, `T17A-WINDOW-03` and
`T17A-WINDOW-04-REPAIR-01`. Each window contains four USDC buy quotes at
USD 10, 25, 50 and 100 followed by an exact reverse-sell quote using the
preceding buy output. All 24 accepted calls returned `QUOTE_AVAILABLE`.

The median accepted-window increase in quote-only round-trip cost from
USD 10 to USD 100 is `832.5706 bps`. All three accepted windows have strictly
increasing costs across each adjacent notional step. This supports the frozen
hypothesis only within one member and three matched point-in-time quote
windows. It does not establish cross-token generality, data quality,
fillability, RealizedVWAP, NetReturn, a signal, a strategy or alpha.

The hypothesis remains `PAUSED`. The evidence is eligible only for the
conditional TASK-18 data-quality gate; promotion or trading is not authorized.

## Accepted costs

| Window | USD 10 | USD 25 | USD 50 | USD 100 | USD 100 − USD 10 |
|---|---:|---:|---:|---:|---:|
| `T17A-WINDOW-01` | 345.2850 bps | 495.1112 bps | 734.1092 bps | 1174.2551 bps | 828.9701 bps |
| `T17A-WINDOW-03` | 348.2840 bps | 497.1640 bps | 735.6348 bps | 1181.6128 bps | 833.3288 bps |
| `T17A-WINDOW-04-REPAIR-01` | 348.8440 bps | 497.5428 bps | 737.8010 bps | 1181.4146 bps | 832.5706 bps |

These are quote-only round-trip costs:

```text
10,000 × (1 − reverse_sell_USDC_atomic / buy_USDC_atomic)
```

They are not executed or realized costs.

## Timing repair

The original `T17A-WINDOW-02` is retained as immutable audit evidence but
excluded from the estimand. Its persisted trigger began `1799.992146` seconds
after window 01, a shortfall of `0.007854` seconds against the frozen
1800-second minimum. No post-hoc tolerance was introduced.

The root cause was exact monotonic pacing without a wall-clock safety margin.
The runner now adds a one-second margin. The replacement began
`1818.792805` seconds after window 03. Accepted-window separations are
`3599.993664` and `1818.792805` seconds.

## Usage and effects

- original A3 calls: `24`;
- timing-repair calls: `8`;
- total provider calls: `32`;
- modeled generic credits: `32`;
- billed credits: unavailable in keyless mode;
- retries: `0`;
- concurrency: `1`;
- API keys/accounts: `0`;
- cash spend: `USD 0`;
- wallet/signer/transaction actions: `0`;
- accepted raw bytes stored outside Git: `134,489`;
- excluded raw bytes remain outside Git and are retained by their exact hashes.

The deterministic machine receipt is
`docs/evidence/task17a/execution_capacity_quote_panel_audit_v1.json`.
