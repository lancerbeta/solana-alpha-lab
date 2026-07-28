# TASK-10 Jupiter buy/reverse-sell quote panel summary v2

Status: **PASS_BOUNDED_BUY_REVERSE_SELL_QUOTE_PANEL**

## Decision

The authorized T10-A6 public keyless Jupiter run returned `QUOTE_AVAILABLE`
for all four exact USDC buy notionals and all four dependent reverse sells.
Every sell input equals the preceding buy `outAmount` exactly. The legacy
`/swap/v1/quote` surface therefore passed this bounded compatibility panel.

This is quote evidence, not a fill. It does not establish landed execution,
realized VWAP, settled cashflow, NetReturn, PathRisk or alpha.

## Panel result

| USD input | Buy output token atomic | Reverse-sell USDC atomic | Quote recovery | Quote-only delta |
|---:|---:|---:|---:|---:|
| 10 | 3,464,827,961,969 | 9,657,834 | 96.578340% | -342.1660 bps |
| 25 | 8,599,892,480,161 | 23,798,667 | 95.194668% | -480.5332 bps |
| 50 | 16,997,033,489,660 | 46,475,368 | 92.950736% | -704.9264 bps |
| 100 | 33,201,195,353,176 | 88,811,179 | 88.811179% | -1118.8821 bps |

The quote-only round-trip deterioration increased monotonically with size in
this one bounded observation. It is a material capacity warning for future
research, not a causal fee/slippage decomposition and not realized PnL.

All eight responses omitted route `feeAmount` and `feeMint`. Consequently
`provider_fee_atomic`, `platform_fee_atomic`, `fee_mint` and
`included_in_output_amount` remain null. Provider `outAmount` was not reduced
a second time; the slippage limit was not counted as a realized cost.

## Live run and observability

| Run | Calls | Buy | Sell | Received | Durable | Elapsed | Terminal |
|---|---:|---:|---:|---:|---:|---:|---|
| `t10a6-20260728T015829Z` | 8 | 4 | 4 | 13,282 B | 1,406,298 B | 15.657190 s | 8 `QUOTE_AVAILABLE` |

Provider latency ranged from 225 to 348 ms, mean 284.625 ms and median
277.5 ms. The seven inter-request gaps ranged from 2.200042 to 2.200456
seconds, satisfying the 2.2-second sequential pacing floor. Context slots
were strictly increasing from `435653684` to `435653721` in observed order.
All PIT timestamp invariants passed and all projected quote ages were zero
milliseconds at strategy availability.

The DuckDB projection contains eight raw events, eight quote attempts and zero
execution attempts. The raw partition has eight unique raw event IDs and
eight unique idempotency keys. All raw bodies use one accepted typed schema;
no transaction or instruction payload key occurred.

## Immutable evidence

The ignored local raw root is
`task10_jupiter_quote_pilot_v2/run=t10a6-20260728T015829Z`.

| Logical file | Bytes | SHA-256 |
|---|---:|---|
| `partitions/quotes.parquet` | 31,635 | `0648390ba3af49bacf804aafb7cc4788fbbb7040508cfef79f88c3d1ed188d1b` |
| `projections/quotes.duckdb` | 1,372,160 | `c1664a1180a525477d9beba5b5d13662cf9b5ae8721506363ce34d65af50ceda` |
| `receipts/quotes.manifest.json` | 742 | `84cf3cf6103cbf7e81e3ff05c76e363514b60a033149085a5e375e8b65e86ca4` |
| `receipts/run.receipt.json` | 1,761 | `ac64469d0e0dd214aba775f625a90aec0006a3685921ab2234f49df89531f0a4` |

The logical raw content SHA-256 is
`12f0bb76938c518933e47ef0a73ea901e640948aee408b419a1cc2f74f645cce`.
The frozen A6 plan SHA-256 is
`b76c11f19f8244d6b2dfa5c4bb6c8594a5e790f22eef5010117d21b475243833`.

Tracked evidence:

- fixture:
  `tests/fixtures/task10/jupiter_quote_logger_live_evidence_v2.json`
  (`242e76b2295ce37b47ac851b29cd44e8b8d457a0ac7669a9b71013f0deb4d7d5`);
- machine receipt:
  `docs/evidence/task10/jupiter_quote_logger_execution_receipt_v2.json`
  (`01c6392d38ab4fd8c67bead42a9a5013d2c82206a706cb50e9aac523560490ec`).

The tracked fixture contains public identifiers, hashes and sanitized metrics,
not provider bodies, headers, credentials, secret material or absolute machine
paths.

## Authority and costs

The exact authority was
`T10-A6_BOUNDED_EXTERNAL_QUOTE_PILOT_V2`: one selected mint, four buys, at
most four dependent sells, eight GET calls maximum, concurrency one, retries
zero, 20-second request timeout, 600-second wall cap, 1,048,576 received bytes
and 5,242,880 durable bytes.

Actual use: eight public keyless provider calls, zero retries, zero accounts,
zero API keys, zero provider credits, zero cash spend and zero wallet, signer
or transaction actions. Acceptance and evidence production used no network
and did not rewrite the ignored run.

## Validation

The final local acceptance passed 64 targeted quote/logger tests, 12 v2
evidence tests and the full 834-test repository suite. Catalog validation
passed with 228 assets, and generated navigation, secret scanning and file
hygiene checks passed.

## Boundaries

- No `NO_ROUTE`, provider error, invalid response or timeout occurred in this
  bounded live panel.
- Quote availability is not Fillable, realized execution or NetReturn.
- The observed monotonic size deterioration is one point-in-time sample for
  one selected mint, not a population estimate.
- The legacy Jupiter surface is mutable compatibility evidence; future
  consumers must preserve provider version and repeat bounded validation when
  the surface changes.
- TASK-10 canonical status changes only after repository/Catalog/finalization
  evidence is accepted by the control plane.
