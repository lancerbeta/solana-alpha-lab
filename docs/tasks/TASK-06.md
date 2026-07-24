---
task_id: TASK-06
task_version: "1.0"
title: Raw event envelope and immutable storage boundary
phase: P1
canonical_status: IN_PROGRESS
canonical_status_owner: ChatGPT_Project_Work
repository_evidence_status: IMPLEMENTED_UNVERIFIED
atom_id: T06-A8A
accepted_implementation_commit: 23ead28bfb9fe9c60fd143b7e69267b61bc8512c
accepted_implementation_tree: dead22b1d8bae02fead79d3aa7ef27c13f6c840a
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

## Accepted implementation atoms

Work accepted the following bounded local-write atoms:

- `T06-A2`: redaction and raw-event envelope;
- `T06-A3`: manifest identity and dataset fingerprint;
- `T06-A4`: immutable Parquet adapter and atomic publication;
- `T06-A5`: storage budget, free-space reserve and growth warnings;
- `T06-A6`: complete Catalog registration and consumer links;
- `T06-A7A/B/C`: exact staging, ordinary commit, normal publication, CI and
  clean-clone validation.

## Published implementation evidence

- implementation commit:
  `23ead28bfb9fe9c60fd143b7e69267b61bc8512c`;
- tree: `dead22b1d8bae02fead79d3aa7ef27c13f6c840a`;
- parent: `1db62c7abc06bcb4ab209b3db7f4eb858f64330a`;
- commit subject: `feat: add TASK-06 raw storage boundary`;
- committed changed-file count: 28;
- committed diff SHA-256:
  `ccf22d511b7e32bfd758aaa79534e8a1f8b2764a9b598e6a2dc89a571429ba60`;
- targeted TASK-06 tests: 64/64 PASS;
- full unit suite: 310/310 PASS;
- GitHub Actions run/job: `30057909197` / `89373386559`, PASS;
- exact clean clone: HEAD/tree, `main -> origin/main`, single-branch refspec,
  no tags, clean index/worktree, 64/64 targeted and 310/310 full PASS;
- Catalog at implementation commit: 0.5.0 / 128 assets / 4 shards /
  4 schemas / 7 queries;
- repository state: `TASK06_ATOM7B_CANDIDATE_COMMITTED`;
- provider/API/RPC calls: 0; cash spend: USD 0;
- wallet, signer and transaction actions: 0.

## Finalization candidate

Atom `T06-A8A` repairs the remaining repository completion gap:

1. this task mirror did not yet contain the published commit, CI and
   clean-clone evidence;
2. `docs/handoffs/latest.md` still described TASK-05;
3. repository policy did not recognize exact TASK-06 finalization staged and
   future committed states.

The atom advances Catalog to 0.5.1 with the same 128 assets and 7 queries,
reconciles task/handoff hashes and ownership, and regenerates only deterministic
navigation. It does not change raw-envelope, manifest, Parquet, budget,
dependency or provider semantics.

Finalization commit and push require separate explicit authority. Canonical
Project Sources replacement and UI activation are later control-plane actions.

## TASK-07 handoff boundary

TASK-07 starts with a read-only Entry Gate over the published TASK-06 contracts
and an exact provider smoke specification. No provider is silently selected and
no account, API or RPC action is implied.

The smoke specification must bind:

- provider and official endpoint/version evidence with an `as_of` date;
- exact request inventory, maximum request count, credit and cash caps;
- timeout, retry, 429 and stop behavior;
- raw-envelope identity, redaction version and retained failure outcomes;
- dataset/partition manifest identity and first-reliable availability;
- sanitized output, receipt and rollback requirements.

Any provider/account/API/RPC call, credential use, purchase or storage
allocation requires its own Work-approved authority after the read-only gate.

TASK-12 may later bind the budget snapshot to runtime metrics and a
single-writer coordinator. TASK-15 may choose deployment-specific storage and
free-space limits. Neither task may reinterpret the Atom 5 forecast as a disk
reservation or a retention policy.

## Definition of Done checkpoint

Implementation, Catalog registration, commit, publication, CI and exact clean
clone are complete. TASK-06 remains `IN_PROGRESS` until:

- Work accepts this exact staged finalization candidate;
- an ordinary finalization commit and normal push pass separate gates;
- CI and an exact clean clone pass for that finalization commit;
- canonical state, roadmap, archive and manifest candidates are validated;
- the TASK-07 read-only handoff is accepted;
- Project Sources activation is verified or explicitly recorded under the
  canonical completion rule.
