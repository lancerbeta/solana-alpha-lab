# TASK-13 deterministic offline pilot-evidence audit acceptance v1

## Result

`T13-A4_DETERMINISTIC_OFFLINE_ACCEPTANCE_V1` accepts the bounded claim:

`BOUNDED_HISTORICAL_EVIDENCE_QUALITY_ACCEPTANCE`

The deterministic auditor reproduced the frozen TASK-08 through TASK-11
population from exact local bytes. All 658 raw rows have complete and unique
raw-event and idempotency identities. No point-in-time ordering violation and
no row after the global cutoff were observed. Both TASK-10 DuckDB projections
reconcile exactly to their nine raw and quote-attempt rows and contain zero
execution-attempt rows.

This accepts integrity and reproducibility of the retained bounded evidence.
It does not turn runs lasting seconds into a sustained pilot.

## Measured audit

| Slice | Rows | Identity duplicates | Repeated content | Typed failures | PIT violations |
|---|---:|---:|---:|---:|---:|
| TASK-08 accepted | 388 | 0 | 1 | 2 | 0 |
| TASK-09 accepted | 258 | 0 | 0 | 1 | 0 |
| TASK-10 fail-closed v1 | 1 | 0 | 0 | 1 | 0 |
| TASK-10 accepted v2 | 8 | 0 | 0 | 0 | 0 |
| TASK-11 accepted | 3 | 0 | 0 | 0 | 0 |
| **Total** | **658** | **0** | **1** | **4** | **0** |

The repeated TASK-08 content hash belongs to distinct immutable identities and
is not an identity duplicate.

Typed failures remain separate:

- two Solana Tracker `HTTP_ERROR/http_status_not_success:401` rows are access
  failures, not reliability-rate or empty-data observations;
- one TASK-09 `INVALID_RESPONSE/get_transaction_result_keys_drift` row
  preserves additive response drift;
- one TASK-10 `INVALID_RESPONSE/SCHEMA_MISMATCH` row preserves the original
  fail-closed quote observation;
- none of these states is `NO_ROUTE`.

Availability lag is zero for TASK-08, TASK-09 and TASK-11. The TASK-10 retained
lags range from 0.002 to 0.003 milliseconds. These values describe local
normalization timestamps in the exact runs; they are not provider latency
estimates.

## Decision impact

The evidence is decision-valid for:

- bounded raw-evidence integrity;
- typed-failure preservation;
- TASK-10 raw-to-projection reconciliation.

It is not decision-valid for sustained 24–48 hour operation, provider
reliability rates, lifecycle representativeness, provider purchase,
fill/realized execution, NetReturn, PathRisk or alpha.

TASK-14 therefore receives one bounded implication:
`PROVIDER_PURCHASE_REQUIREMENT_NOT_ESTABLISHED`. Any reliability, coverage or
purchase claim needs sustained measurement under separate authority.

## Evidence

- Frozen acceptance fixture:
  `tests/fixtures/task13/pilot_audit_offline_acceptance_v1.json`
- Fixture SHA-256:
  `97885ea7b782c68a65ac27744bce6703300acfe76cfe20a7f4141767fdee77c5`
- Machine-readable receipt:
  `docs/evidence/task13/pilot_audit_offline_acceptance_receipt_v1.json`
- Receipt SHA-256:
  `d932512f861736944cbca3d184528dae0366afbfdb45e185f44ba245c85f752d`
- Source audit result SHA-256:
  `688740fce2f4cd4b8181f2d7724ccca6281d6d0d09db4093a10cd3f7bfde1dc6`
- Frozen input-manifest SHA-256:
  `f74b22ecdb939f645c9304c6b20dba32ea0e842af9c35213b4fef6ac0acdf7f0`

Validation:

- Atom-4 acceptance suite: `9/9 PASS`;
- Atom-5 Catalog finalization check: `1/1 PASS`;
- TASK-13 contract, implementation and acceptance suite: `31/31 PASS`;
- full repository unit suite: `PASS`;
- real local population: `9/9 files`, `4,466,708` bytes and `658/658`
  raw rows PASS;
- source fingerprints: `6/6 PASS`;
- tracked evidence read-back: `12/12 PASS`;
- sanitized evidence and file hygiene: `PASS`.

Catalog transaction:
`0.16.0 / 262 assets / 4 shards / 4 schemas / 7 queries PASS`.
Generated navigation, secret scan and file hygiene are `PASS`. The aggregate
repository gate remains deferred to delivery because A5 is a local-write-only
candidate on the preceding task branch.

## Authority and status

One offline auditor run read nine local files. Network, provider/API/RPC/WSS
calls, credentials, collector executions, raw-data writes, retries, cash,
credits, dependency changes and wallet/signer/transaction actions are zero.
No raw provider body or machine-specific absolute path is retained.

TASK-13 remains `IN_PROGRESS`. All ten mandatory outputs are registered in
Catalog `0.16.0`; generated navigation and exact count consumers agree on
`262` assets.

`T13-A5` is a technical publication candidate, not canonical `DONE`. The next
boundary is `T13-A6_REPOSITORY_DELIVERY_V1`: exact task branch and commit,
non-force push, draft PR and CI read-back. Merge remains separately gated.
