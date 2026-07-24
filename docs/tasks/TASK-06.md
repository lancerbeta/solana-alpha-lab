---
task_id: TASK-06
task_version: "1.0"
title: Raw event envelope and immutable storage boundary
phase: P1
canonical_status: IN_PROGRESS
canonical_status_owner: ChatGPT_Project_Work
repository_evidence_status: IMPLEMENTED_UNVERIFIED
atom_id: T06-A6
repository_base_commit: 1db62c7abc06bcb4ab209b3db7f4eb858f64330a
repository_base_tree: 6ec5e7a10b7c547b02c37436a1f37d0729a6f657
provider_api_rpc_calls: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# TASK-06 — Raw event envelope and immutable storage boundary

TASK-06 provides the first bounded write boundary for replayable raw provider
evidence. It converts already available response bytes and explicit request
metadata into redacted, immutable, content-addressed records and Parquet
pieces. It does not select or call a provider.

Only Work/control plane may accept this local candidate, authorize staging,
commit or publication, reconcile canonical Project Sources, or declare
TASK-06 `DONE`.

## Objective

Provide a reusable raw-event envelope and storage port that:

- retains success, error, timeout, no-route and empty-body outcomes;
- redacts secrets before durable bytes are created;
- preserves revisions instead of overwriting prior observations;
- separates event, observation, strategy-availability, ingestion and
  first-reliable-availability time;
- binds every immutable Parquet piece and dataset root to deterministic
  manifests and fingerprints;
- publishes without clobbering accepted evidence;
- fails before uncontrolled disk growth.

## Invariants

- raw identity and content identity are deterministic and independently
  verifiable;
- missing and failed responses remain evidence and are never converted to
  successful zero-valued observations;
- revision history is append-only;
- `available_to_strategy_at` controls decision eligibility;
- `first_reliable_available_at` prevents backdated availability claims;
- only redacted response bytes cross the storage boundary;
- immutable logical locations never overwrite different bytes;
- physical paths and secrets do not enter manifests or receipts;
- runtime ingestion must use an explicit storage-budget policy;
- no concrete production storage cap is invented by the repository.

## Implemented boundaries

The local candidate contains:

- a deterministic redaction and raw-envelope builder;
- strict raw-event integrity verification;
- partition and dataset manifest identity plus dataset fingerprints;
- a pinned PyArrow adapter with deterministic logical content hashes;
- same-filesystem atomic no-clobber publication and full read-back;
- explicit partition, dataset and filesystem-reserve budgets;
- disk-growth warning forecasts and pre/post-publication checks;
- sanitized synthetic fixtures and adversarial tests.

DuckDB remains a rebuildable analytical consumer. Immutable Parquet pieces and
content-addressed manifests are durable truth. No real raw provider data is
stored in Git.

## Required repository artifacts

| Artifact | Role |
|---|---|
| `docs/contracts/raw_storage_contract_v1.md` | Redaction, identity and raw-event contract |
| `docs/contracts/dataset_manifest_contract_v1.md` | Partition/dataset identity and fingerprint contract |
| `docs/contracts/raw_parquet_store_contract_v1.md` | Deterministic immutable Parquet publication contract |
| `docs/contracts/storage_budget_contract_v1.md` | Logical/physical capacity and growth-alert contract |
| `src/solana_alpha_lab/storage/` | Bounded implementation ports |
| `tests/fixtures/task06/` | Sanitized deterministic evidence |
| `tests/test_task06_*.py` | Contract, integrity, failure and Catalog tests |
| `catalog/` | Stable IDs, relations and generated navigation |

## Accepted local atom evidence

Work accepted the following local-write atoms before this Catalog transaction:

- `T06-A2`: redaction and raw-event envelope;
- `T06-A3`: manifest identity and dataset fingerprint;
- `T06-A4`: immutable Parquet adapter and atomic publication;
- `T06-A5`: storage budget, free-space reserve and growth warnings.

The accepted implementation remains an unstaged local candidate. Atom 6
registers every mandatory output and named consumer, updates deterministic
navigation and adds fail-closed Catalog checkpoint tests. It does not change
provider, raw-event, manifest, Parquet or budget semantics.

## Downstream boundary

TASK-07 may consume these contracts only after the TASK-06 candidate is
committed, published and validated. TASK-07 still requires separate authority
for provider/account/API actions and exact request caps.

TASK-12 may later bind the budget snapshot to runtime metrics and a
single-writer coordinator. TASK-15 may choose deployment-specific storage and
free-space limits. Neither task may reinterpret the Atom 5 forecast as a disk
reservation or a retention policy.

## Definition of Done checkpoint

Local implementation and Catalog registration are not task completion.
TASK-06 remains `IN_PROGRESS` until:

- Work accepts the complete unstaged candidate;
- the exact candidate is staged under separate authority;
- an ordinary commit and normal push pass separate gates;
- CI and an exact clean clone pass;
- repository task/handoff/finalization evidence is reconciled;
- canonical state, roadmap, archive and manifest candidates are validated;
- Project Sources activation is verified or explicitly recorded under the
  canonical completion rule.
