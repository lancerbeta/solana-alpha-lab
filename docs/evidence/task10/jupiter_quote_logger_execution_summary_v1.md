# TASK-10 Jupiter quote pilot execution summary v1

Status: **STOPPED_FAIL_CLOSED_OFFLINE_REPLAY_CANDIDATE**

## Decision

The one authorized T10-A4 keyless Jupiter quote run stopped correctly after
the first provider call. The HTTP response used an additive schema outside
the frozen parser, so the durable live record remains
`INVALID_RESPONSE/SCHEMA_MISMATCH` and the run remains
`STOPPED/UNCLASSIFIABLE_SCHEMA_DRIFT`. No retry or second call was made.

T10-A4R adds a narrow offline adapter for exactly the observed typed
extensions. It accepts eight additive top-level telemetry fields,
`swapInfo.updateContextSlot`, nullable route `bps` when positive `percent`
is present, and the absence of the `feeAmount`/`feeMint` pair. Any other
unknown key, changed extension type, or transaction/instruction payload
still fails closed.

Offline replay of the preserved response produces one
`QUOTE_AVAILABLE_CANDIDATE_AFTER_TYPED_EXTENSION`: USD 10 USDC input,
`3452264667206` token atomic units output, two route legs, context slot
`435648803`, and route ID
`bc40c87af5d35349ae28d1dd45ab4dcd1f3df9f57f31e83bec1791fcd50ae5ce`.
This candidate does not rewrite the raw event or the DuckDB quote row.

## Source and frozen selection

The selected mint is
`4vXNhA6ncbx8usZ14CfxkYeQKdaQYgrLfJXNyWcVpump`, decimals `6`. It was
frozen before the network call as the sole non-WSOL mint in the accepted
TASK-09 `getTransaction` token balances. No price or route observation
participated in selection.

The source TASK-09 partition is
`577e614c0b2f41b7a1e3ae92b6cfd965e87e4d4bca76070925873df1ef5b4466`;
the T10-A4 plan is
`ec22bfa5e183a2787d5c1e4e07fb6e6e25996fbacc8b356d089588da1ff6d21b`.

## Live run

| Run | Provider calls | Buy | Sell | Received bytes | Stored bytes | Terminal |
|---|---:|---:|---:|---:|---:|---|
| `t10a4-20260728T011304Z` | 1 | 1 | 0 | 1,434 | 1,373,108 | `UNCLASSIFIABLE_SCHEMA_DRIFT` |

The ignored local raw run is
`task10_jupiter_quote_pilot_v1/run=t10a4-20260728T011304Z`.
Its exact files are:

| Logical file | Bytes | SHA-256 |
|---|---:|---|
| `partitions/quotes.parquet` | 14,811 | `eed05d3c5f65f5adf4e77c07e0fbbccd94856ecabfcb7c5b963e3c0611c8cb67` |
| `projections/quotes.duckdb` | 1,355,776 | `557692a5a37a6d30e8e7ed9e293e5ee24cb6315c9c8714b09e2d561a75d18f5b` |
| `receipts/quotes.manifest.json` | 742 | `40d836d273f90623b1cdc702f28e777e2699b6c6d44acd9db48a8e601e86e520` |
| `receipts/run.receipt.json` | 1,779 | `6a25a37114de65c378b9de3ba4d8a130cd6553b9c908fc91e0dd68d7729b8059` |

The Parquet content hash is
`715c4b436e3f6ffc9926764287cdaca722504ac1edc066c52a7f7e8eb5e03c83`.
The DuckDB projection contains one invalid quote row and zero execution rows.
Hashes were identical before and after offline replay.

Tracked evidence:

- fixture:
  `tests/fixtures/task10/jupiter_quote_logger_live_evidence_v1.json`
  (`8d02ae7e5f32c65c97de2a725d9ed64220c99e09942d3efae356b273ef1d2409`);
- machine receipt:
  `docs/evidence/task10/jupiter_quote_logger_execution_receipt_v1.json`
  (`024f6f4bf81f28dbfa431296fca8373482546debe6acfee9ac90835acfc00ad9`).

The tracked fixture contains hashes, typed schema observations, public
identifiers and sanitized quote metrics. It contains no provider body,
request/response headers, credentials, secret material or absolute machine
path.

## Authority and costs

The approved authority was
`T10-A4_BOUNDED_EXTERNAL_QUOTE_PILOT`: one selected mint, at most four buys
and four dependent sells, eight HTTP calls maximum, concurrency one, retries
zero, 20-second request timeout, 600-second wall cap, 1,048,576 received
bytes and 5,242,880 durable bytes.

Actual use was one public keyless provider call, one buy attempt, zero sell
attempts, zero retries, zero accounts, zero API keys, zero provider credits,
zero cash spend and zero wallet/signer/transaction actions. The frozen stop
condition terminated the remaining call allowance. Repair, replay and
evidence production used no network and did not modify the ignored raw run.

## Boundaries and next gate

- USD 25, USD 50 and USD 100 buy panels are unobserved.
- Every dependent reverse sell is unobserved.
- `NO_ROUTE`, Fillable, execution, realized VWAP, inventory bounds, alpha
  and NetReturn are not established.
- Missing provider route fee fields remain raw-only uncertainty; normalized
  fee fields stay null.
- TASK-10 remains `IN_PROGRESS`; this evidence implies no canonical status
  change.
- Any continuation requires a new explicit external-call authorization and
  a fresh run ID. The stopped run must never be resumed or rewritten.

Validation passed: TASK-10 quote suite 52/52, tracked evidence 11/11 and full
repository 821/821. Catalog `0.12.0` validates with 221 assets, four shards,
four schemas and seven queries; generated navigation, secret scan and file
hygiene also pass.
