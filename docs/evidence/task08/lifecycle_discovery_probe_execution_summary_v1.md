# TASK-08 lifecycle discovery probe execution summary v1

Status: **PASS_WITH_EXPLICIT_COVERAGE_BLOCKER_EVIDENCE**

## Decision

The one authorized T08-A5U live capture passes its transport, durability,
redaction and budget boundary. It does not pass lifecycle coverage. The
accepted classification is `NOT_TESTABLE_IN_WINDOW`, and the run is retained
as an explicit coverage-blocker candidate for control-plane acceptance.

No retry or 24-hour pilot is authorized by this evidence.

## Evidence root

| Source run | Records | Raw-body bytes | Stored file bytes | Result |
|---|---:|---:|---:|---|
| `t08a5-20260725T084127Z` | 388 | 600,292 | 799,765 | `NOT_TESTABLE_IN_WINDOW` |

The ignored raw run remains local and immutable. Its exact files are:

| Logical file | Bytes | SHA-256 |
|---|---:|---|
| `partitions/probe.parquet` | 798,206 | `079dc1401b4da3cf0e1d63d2b20210e017252f26d93c4dd2afd8af7d950fcb6a` |
| `receipts/probe.manifest.json` | 742 | `8872648a10ca39b6b9cdf3f10dba75dc51bef8083ddd768dca221720dab6ea98` |
| `receipts/probe.receipt.json` | 817 | `d1fb206fceb9a0277e65ae36f99ed245f1d82200d1b3d7fc0ce7d4b906d42598` |

Tracked evidence:

- fixture:
  `tests/fixtures/task08/lifecycle_discovery_probe_live_evidence_v1.json`
  (`e439e6a3f80560a1ea8c4475fc0278f8971784c31a7a20f1b633c37c2b0d21bd`);
- machine receipt:
  `docs/evidence/task08/lifecycle_discovery_probe_execution_receipt_v1.json`
  (`33a3f0b90de36c1543ee605eccc07685798f1b2e08ee6a5f494345d5cb19df40`).

The tracked fixture contains aggregate counts, typed failures, logical
locations and hashes only. It contains no provider bodies, request values,
headers, credentials or absolute machine paths.

## Accepted result

The Helius stream produced 385 notifications in seven seconds. Of these, 102
were successful transactions and 283 were failed transactions; 101 pinned Pump
events decoded, 15 Pump program-data records remained unsupported, and no
accepted `CreateEvent` occurred. The stream stopped at the frozen
`STREAM_GUARD`, so no follow-up candidate or RPC follow-up was created.

The two Solana Tracker observations both remain
`HTTP_ERROR/http_status_not_success:401`. This is access-failure evidence, not
an empty result, zero, `NO_ROUTE` or lifecycle evidence.

All frozen caps held: concurrency 1, retries 0, 15 modeled Helius credits,
2 Tracker requests, 600,292 received bytes, 1,400,057 combined received and
stored bytes, cash spend USD 0 and no wallet, signer or transaction action.

## Boundaries and residuals

- Transport feasibility and durable evidence are accepted for this run.
- An unbiased lifecycle sample, inactive/non-migrated coverage, a production
  collector, SLA, fillability, alpha and NetReturn remain unproven.
- No provider/API/RPC/WSS call occurred while producing these tracked files.
- No raw file, dependency, Catalog record, Git index, commit, remote or
  canonical Source was changed.
- Catalog registration remains `CATALOG_GAP_PENDING_SEPARATE_ATOM`.
- Canonical status remains unchanged; the coverage-blocker disposition still
  requires its own control-plane reconciliation.

Validation passed: evidence tests 10/10, the complete TASK-08 suite 73/73 and
the full repository suite 459/459, plus secret and file-hygiene checks.

The next safe checkpoint is a separate local-write atom for Catalog and
repository integration of the accepted TASK-08 candidate. It does not include
another external probe.
