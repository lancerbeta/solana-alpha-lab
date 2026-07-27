# TASK-09 PumpSwap Touch probe execution summary v1

Status: **PASS_WITH_FAIL_CLOSED_SCHEMA_EXTENSION_REPAIR**

## Decision

The one authorized T09-A4 public Solana capture establishes bounded
post-migration PumpSwap **Touch** transport and field coverage. It does not
establish Fillable, `NO_ROUTE`, migration, launch-universe representativeness,
alpha or NetReturn.

The live runner stopped fail-closed when the official public
`getTransaction` response contained one additive top-level result field,
`transactionIndex`. The raw record remains
`INVALID_RESPONSE/get_transaction_result_keys_drift`. T09-A4R accepts only
that optional field when it is a nonnegative integer, rejects every other
unknown key, and replays the preserved response offline as
`FIELD_COVERAGE_CANDIDATE`. No historical evidence was rewritten and no
second network call was made.

The official `getTransaction` documentation did not list `transactionIndex`
among result fields as of 2026-07-27. The observed public-RPC response is
therefore retained as an implementation extension with explicit provenance,
not promoted into an undocumented protocol guarantee.

## Evidence root

| Source run | Records | Canonical redacted-body bytes | Stored file bytes | Live terminal |
|---|---:|---:|---:|---|
| `t09a4-20260727T184740Z` | 258 | 694,186 | 843,801 | `STOPPED_SCHEMA_DRIFT` |

The ignored raw run remains local and immutable. Its exact files are:

| Logical file | Bytes | SHA-256 |
|---|---:|---|
| `partitions/probe.parquet` | 842,679 | `577e614c0b2f41b7a1e3ae92b6cfd965e87e4d4bca76070925873df1ef5b4466` |
| `receipts/probe.manifest.json` | 742 | `2070c0d36aeb963be8e3e39628c2d7a032679dad34d4d6f9131951190bba6493` |
| `receipts/probe.receipt.json` | 380 | `6191f4b2434351dbfda4b8e4d0b57fd879bc62cdf1604460a52a7d5cf76b31be` |

Tracked evidence:

- fixture:
  `tests/fixtures/task09/pumpswap_touch_probe_live_evidence_v1.json`
  (`20d5fc95e92b2837eee1f64c139f97ad5f98354eb2826c4771d7fb7969c9b735`);
- machine receipt:
  `docs/evidence/task09/pumpswap_touch_probe_execution_receipt_v1.json`
  (`8e9c066671ec8a0334d7cf41cf2cb5a725a836ad0c7c3f473b0e35902a16f0ee`).

The tracked fixture contains aggregate counts, typed classifications, logical
locations and hashes only. It contains no provider body, signature, address,
request value, header, credential or absolute machine path.

## Accepted result

The WSS subscription reached its exact 256-notification cap. It observed 124
successful and 132 failed transactions with no truncated log sets. The pinned
official PumpSwap IDL subset decoded 75 events: 41 `BuyEvent` and 34
`SellEvent`. Six PumpSwap program-data records remained explicitly
unsupported.

The decoded evidence covers pool identity, raw base and quote reserves,
virtual quote reserves, buy/sell atomic amounts, protocol/creator/LP fees and
event time. Raw, virtual and derived effective reserve meanings stay separate.
One `getTransaction` follow-up preserved token-balance and account-key
coverage and passes the repaired offline validator.

There are 258 unique raw event IDs and 258 unique idempotency keys: zero
duplicates, zero retries and zero restarts. Parquet row order is not treated
as source order; consumers must sort by `observed_at`, then `raw_event_id`.
Observed, available, ingested and first-reliable timestamps remain distinct
fields and satisfy their ordering invariants.

All frozen caps held: one WSS connection, one subscription, one HTTP
follow-up, concurrency 1, retries 0, provider credits 0, cash spend USD 0 and
no wallet, signer or transaction action. Exact canonical redacted-body and
stored-file sizes reconcile. Original wire-byte length was not persisted
separately on the stopped path and remains an explicit non-decision-changing
instrumentation gap.

## Boundaries and residuals

- This is bounded post-migration Touch evidence, not a representative launch
  or lifecycle sample.
- Failed transactions remain evidence and were not filtered away.
- The TASK-08 lifecycle coverage blocker remains unchanged.
- Fillable, executable quotes, route identity/count, `NO_ROUTE`, inventory,
  slippage and NetReturn begin in TASK-10.
- No provider/API/RPC/WSS call occurred during repair, replay or tracked
  evidence production.
- No retry or additional external call is authorized or required for this
  bounded acceptance.
- Catalog registration and canonical `DONE` still require their own finish
  reconciliation; this file alone does not change status.

Validation target: probe tests 8/8, evidence tests 11/11, complete TASK-09
suite 44/44 and full repository suite 753/753, plus Catalog, secret and
file-hygiene gates.
