---
task_id: TASK-05
task_version: "1.0"
title: Canonical schema v1
phase: P1
canonical_status: IN_PROGRESS
canonical_status_owner: ChatGPT_Project_Work
repository_evidence_status: IMPLEMENTED_UNVERIFIED
atom_id: T05-A7A
accepted_implementation_commit: b7aff0117b1fc6ca4c4229b4c2eb4b9c202e3625
accepted_implementation_tree: 27d41a8307efdec19faabb82e7be9b5553d3cbdf
provider_api_rpc_calls: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# TASK-05 — Canonical schema v1

TASK-05 defines the first executable, versioned data contract for the Solana
Memecoin Intraday Alpha Lab. The repository implementation is published and
validated, but only Work/control plane may accept the finalization candidate,
reconcile canonical Project Sources, or declare TASK-05 `DONE`.

## Objective

Provide a bounded schema/model/migration/query contract that lets later tasks
store and read point-in-time evidence without overwriting revisions, collapsing
missing states, backdating availability, or confusing quote economics with
realized cashflow.

TASK-05 does not create collectors, provider connections, strategies, bots,
wallets, signers, transactions, production datasets, or live trading behavior.

## Invariants

- raw payload and provider revisions are append-only;
- business identity is separate from storage primary keys;
- provider disagreement and revision history may coexist;
- missing is not zero;
- no-route, failed exit, unknown transaction state and unresolved inventory are
  explicit states;
- `available_to_strategy_at` controls decision eligibility;
- `first_reliable_available_at` prevents historical backdating;
- monetary and token quantities use integer atomic amounts with explicit mint
  and decimals provenance;
- quote fees and realized cashflow remain reconcilable without double counting;
- execution has exactly one terminal state;
- unresolved inventory retains ordered recovery bounds.

## Implemented boundaries

The implementation contains:

- executable DuckDB DDL for 15 bounded relations;
- strict Pydantic v2 models for the same relation contracts;
- an ordered content-addressed migration ledger and immutable initial migration;
- synthetic revision, disagreement, no-route and round-trip fixtures;
- two bounded read-only PIT/as-of query recipes;
- Catalog registrations for schemas, models, migrations, fixtures, tests,
  relation boundaries and query consumers;
- deterministic generated navigation and fail-closed repository-state policy.

Durable truth is immutable Parquet plus content-addressed manifests. DuckDB is a
rebuildable single-writer analytical projection, not the raw truth store.

## Required repository artifacts

| Artifact | Role |
|---|---|
| `schemas/schema_v1.sql` | DuckDB DDL and decision-safe PIT macro |
| `docs/contracts/data_contract_v1.md` | Field, ownership, revision, availability and missing-state contract |
| `src/solana_alpha_lab/contracts/` | Strict boundary models and migration-ledger validation |
| `migrations/` | Immutable ordered migration declaration |
| `tests/fixtures/task05/` | Synthetic valid and adversarial evidence |
| `scripts/query_task05.py` | Bounded read-only query runner |
| `catalog/` | Stable IDs, relations, query recipes and generated navigation |
| `docs/tasks/TASK-05.md` | This repository task mirror |
| `docs/handoffs/latest.md` | Published implementation evidence and TASK-06 entry gate |

## Published implementation evidence

- implementation commit:
  `b7aff0117b1fc6ca4c4229b4c2eb4b9c202e3625`;
- tree: `27d41a8307efdec19faabb82e7be9b5553d3cbdf`;
- parent: `644bda35429ab74b9488d11e78827234d5d438f3`;
- commit subject: `feat: add TASK-05 canonical data contract`;
- committed changed-file count: 26;
- committed diff SHA-256:
  `0e73bcca596a9542c849ad8803580c563241a3be55883273d3be9c674d9868e7`;
- targeted TASK-05 tests: 57/57 PASS;
- full unit suite: 235/235 PASS;
- GitHub Actions run `30042685509`: PASS;
- clean clone: exact HEAD/tree, 57/57 targeted and 235/235 full PASS;
- Catalog at implementation commit: 0.4.0 / 110 assets / 4 shards /
  4 schemas / 7 queries;
- repository state: `TASK05_ATOM5B_CANDIDATE_COMMITTED`.

The first clean-clone aggregate launch reached 235/235 tests but stopped because
the new clone had not yet applied the repository-required local
`core.hooksPath=.githooks` bootstrap. After applying the same clone-local setup
used by CI, the complete gate passed. Remote CI was not rerun.

## Finalization candidate

Atom T05-A7A repairs two completion gaps:

1. this required repository task mirror did not exist;
2. `docs/handoffs/latest.md` still described the pre-commit TASK-04 candidate.

The atom also separates the task-control document from the data-contract
document in Catalog, regenerates navigation, and adds fail-closed recognition
for the exact staged and future committed finalization states. It does not
change schema, model, migration, query or dependency semantics.

Finalization commit and push require separate explicit authority. Project
Sources replacement and UI activation are later control-plane actions.

## TASK-06 handoff boundary

TASK-06 may begin only after TASK-05 acceptance. Its first atom is read-only and
must consume:

- `raw_api_events` as the redacted append-only envelope relation;
- `raw_event_id`, `idempotency_key`, `request_hash`, `content_sha256`,
  `revision_number` and `revision_of` as raw identity and revision controls;
- `dataset_manifests.dataset_manifest_id`, `(dataset_id, dataset_version)`,
  `schema_sha256`, `dataset_fingerprint`, `generation_run_id` and
  `validation_receipt_sha256` as dataset identity;
- `partition_manifests.partition_manifest_id`,
  `(dataset_manifest_id, partition_id)`, `logical_location`, `file_sha256`,
  `content_sha256`, row count and event/availability bounds as partition
  integrity;
- all four operational timestamps where applicable plus
  `first_reliable_available_at`;
- redaction-before-storage, append-only revisions, immutable Parquet truth,
  manifest-bound fingerprints, retained failed responses and zero secrets.

TASK-06 must not silently choose a provider, create an account, call an API/RPC,
collect data, add dependencies, or expand storage without its own Entry Gate and
authority.

## Definition of Done checkpoint

Repository implementation, Catalog/query registration, targeted/full/hook/CI
and clean-clone evidence are complete. TASK-05 remains `IN_PROGRESS` until:

- Work accepts the exact staged finalization candidate;
- an ordinary finalization commit and normal push pass their separate gates;
- CI and exact clean clone pass for that finalization commit;
- canonical state/roadmap/manifest replacement candidates are validated;
- the TASK-06 handoff is accepted;
- UI activation is either verified or explicitly recorded as pending under the
  canonical completion rule.
