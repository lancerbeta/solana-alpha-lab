---
contract_id: CONTRACT-T13-PILOT-AUDIT-001
contract_version: "1.0"
task_id: TASK-13
atom_id: T13-A2_FROZEN_BOUNDED_AUDIT_CONTRACT_V1
status: FROZEN_BOUNDED_HISTORICAL_EVIDENCE_CONTRACT
as_of: 2026-07-28
provider_calls: 0
cash_spend_usd: 0
contains_secrets: false
---

# TASK-13 bounded pilot-evidence audit contract v1

## 1. Purpose and accepted claim

This contract freezes the smallest decision-valid audit of evidence that
already exists locally. It does not authorize collection and does not claim
that a sustained pilot occurred.

The Atom 2 accepted claim is only:

`BOUNDED_HISTORICAL_EVIDENCE_AUDIT_CONTRACT_FROZEN`

The later audit may determine whether the retained TASK-08 through TASK-11 raw
records are complete, internally reproducible and point-in-time safe within
their exact bounded runs. It may quantify identity duplicates, repeated
content, timestamp ordering, availability lag, typed failures and
raw-to-projection reconciliation.

It does **not** establish:

- 24–48 hour collection, lifecycle representativeness or source coverage;
- a provider purchase requirement or production service-level objective;
- Fillable, realized execution, RealizedVWAP, NetReturn, PathRisk or alpha;
- a strategy veto, promotion decision, wallet action or real-money result.

## 2. Frozen population

The audit population is
`POPULATION-T13-BOUNDED-HISTORICAL-EVIDENCE-001` version `1.0`.
It contains the accepted local raw evidence from TASK-08 through TASK-11:

| Slice | Raw rows | Raw files | Role |
|---|---:|---:|---|
| `T08_ACCEPTED` | 388 | 1 | Primary slice; Helius successes plus typed Solana Tracker access failures |
| `T09_ACCEPTED` | 258 | 1 | PumpSwap Touch transport and one retained schema-drift response |
| `T10_FAIL_CLOSED_V1` | 1 | 1 | Preserved Jupiter schema mismatch |
| `T10_ACCEPTED_V2` | 8 | 1 | Four buy and four exact reverse-sell quote observations |
| `T11_ACCEPTED` | 3 | 3 | Supply, largest-token-account and owner-resolution RPC responses |

The exact raw denominator is 658 rows in seven Parquet files and 1,738,772
bytes. Two TASK-10 DuckDB projections add 2,727,936 bytes. The complete
data-file read set is therefore nine files and 4,466,708 bytes.

TASK-12 contributes its tracked seven-vector offline supervisor acceptance as
control evidence only. Its vectors are not provider observations and are
excluded from the 658-row raw denominator.

Earlier TASK-08 exploratory runs, TASK-07 provider smoke data, synthetic
contract fixtures, receipts, summaries and future observations are excluded
from the raw denominator. Tracked fixtures and receipts are lineage and
reconciliation evidence, never replacement raw rows.

## 3. Primary estimand and decision consumer

The primary audit slice is `T08_ACCEPTED` because it is the largest retained
slice and the only selected slice containing two source labels plus typed
access failures. Its estimand is:

```text
within the exact retained TASK-08 run
-> can every raw identity and PIT timestamp be reconciled
-> are repeated contents distinguished from duplicate identities
-> are Helius successes and Solana Tracker HTTP failures retained as typed
   observations with their true denominators
```

The primary downstream consumer is TASK-14. TASK-14 may use measured gaps to
decide that a provider purchase is unsupported or that a later bounded
collection contract is required. It may not treat this short historical sample
as a rate, reliability or coverage estimate for sustained operation.

## 4. Identity, lineage and immutable bytes

The machine-readable fixture
`tests/fixtures/task13/pilot_audit_population_v1.json` owns the exact
repository-relative paths, SHA-256 values, byte counts, row counts and tracked
evidence fingerprints.

Rules:

- `raw_event_id` and `idempotency_key` are identity denominators;
- `content_sha256` repetition is measured separately and is not automatically
  an identity duplicate;
- raw provider bodies are read only from ignored local data and must never be
  copied to tracked reports, fixtures, tests or logs;
- no raw file, manifest, receipt, fixture or projection may be rewritten;
- a missing expected local raw file or mismatched SHA-256 is
  `AUDIT_INPUT_MISSING_OR_DRIFTED`, not an empty dataset;
- a missing Catalog record is `CATALOG_GAP`, not proof that bytes are absent.

## 5. Point-in-time boundary

The global eligibility cutoff is
`2026-07-28T10:25:42.035105Z`, the latest retained
`first_reliable_available_at` in the selected raw population.

Every non-null timestamp chain must satisfy:

```text
event_time
<= observed_at
<= first_reliable_available_at
<= available_to_strategy_at
<= ingested_at
```

`event_time` may be null where the source contract permits it. A null permitted
event time is not an ordering violation. Availability is never backfilled or
moved earlier. Metrics must be computed per slice first; cross-slice totals may
be reported only where units and denominators are identical.

## 6. Metrics and typed-state semantics

The later auditor is limited to:

| Metric | Numerator | Denominator |
|---|---|---|
| Identity completeness | Rows with non-null raw event, idempotency and content identities | All raw rows in the slice |
| Identity duplicate rate | Rows beyond the first occurrence of an identity | All raw rows in the slice |
| Content repetition rate | Rows beyond the first occurrence of a content hash | All raw rows in the slice |
| PIT ordering violation rate | Rows violating the frozen timestamp chain | Rows with the relevant timestamp pair |
| Availability lag | `available_to_strategy_at - first_reliable_available_at` | Rows with both timestamps |
| Typed failure rate | Rows with a non-success response status | All raw rows in the slice |
| Raw/projection reconciliation | Projection rows with exact raw lineage | TASK-10 projection rows |
| Source-status divergence | Typed status counts by source | Rows in the primary TASK-08 slice |

Typed states remain distinct:

- `SUCCESS` means a retained response accepted by its source contract;
- `HTTP_ERROR` is provider/access failure evidence, not empty, zero or
  `NO_ROUTE`;
- `INVALID_RESPONSE` preserves schema or response-contract drift;
- `NO_ROUTE` requires explicit quote evidence and is never inferred from HTTP
  failure, timeout, missing data or schema mismatch;
- missing input is `AUDIT_INPUT_MISSING_OR_DRIFTED`;
- unavailable or non-comparable metrics are `NOT_TESTABLE`, never zero.

TASK-10 quote projections contain nine raw and nine quote-attempt rows across
the two runs and zero execution-attempt rows. A quote row is not a fill.

## 7. Reuse and implementation boundary

TASK-13 applies `ADOPT -> WRAP -> FORK -> BUILD`:

- `ADOPT` TASK-05 PIT relation semantics and the existing local
  Python/DuckDB stack;
- `WRAP` TASK-06 raw envelope identity, manifest and immutable Parquet rules;
- `FORK` nothing;
- `BUILD` later, under separate authority, only one thin deterministic
  auditor for this frozen population.

No dependency, collector, scheduler, general data-quality framework, graph
database, dashboard or monitoring platform is added.

## 8. Caps, security and side effects

The future offline audit contract is bounded by:

- nine exact data files and 4,466,708 input bytes;
- 658 raw rows;
- 120 seconds local wall time per acceptance invocation;
- 1,048,576 bytes maximum sanitized report output;
- zero retries, network calls, provider calls, credential use, cash spend,
  provider credits and raw-data writes.

The cash cap remains USD 0.

Tracked outputs must contain zero provider bodies, credentials, secret values
or machine-specific absolute paths. Wallet, signer, transaction construction,
simulation, sending and real-money actions remain forbidden.

## 9. Atom 2 authority

Atom `T13-A2_FROZEN_BOUNDED_AUDIT_CONTRACT_V1` permits writes only to:

- `docs/contracts/pilot_audit_contract_v1.md`;
- `tests/fixtures/task13/pilot_audit_population_v1.json`;
- `tests/test_task13_pilot_audit_contract.py`.

It permits zero network/provider/API/RPC/WSS calls, collector executions,
credential reads, raw-data writes, dependency changes, commits, pushes, pull
requests, merges, UI changes, purchases, deployments or destructive actions.

Catalog registration is deferred to the TASK-13 Catalog finalization atom.
That deferral blocks TASK-13 completion but does not block this contract
freeze.

## 10. Validation and next boundary

Atom 2 passes only if targeted tests prove:

- the fixture has one exact stable identity and immutable fingerprint;
- all file counts, row counts, byte counts and hashes reconcile;
- slice denominators sum to 658 and projections reconcile to nine quote rows;
- PIT, missing, failure and `NO_ROUTE` meanings remain separate;
- the primary slice and TASK-14 consumer are explicit;
- tracked lineage evidence matches current repository bytes;
- authority and security caps remain zero-effect.

After PASS, stop before production implementation. The next candidate atom is
`T13-A3_THIN_DETERMINISTIC_AUDITOR_V1`, which requires a separate bounded
local-write authority and may not call a provider.
