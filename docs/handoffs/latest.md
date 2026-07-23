---
handoff_status: LOCAL_FINALIZATION_CANDIDATE
task_id: TASK-05
atom_id: T05-A7A
canonical_status: IN_PROGRESS
canonical_status_owner: ChatGPT_Project_Work
repository_candidate_state: IMPLEMENTED_UNVERIFIED
accepted_implementation_commit: b7aff0117b1fc6ca4c4229b4c2eb4b9c202e3625
accepted_implementation_tree: 27d41a8307efdec19faabb82e7be9b5553d3cbdf
finalization_commit: FORBIDDEN_NOT_CREATED
next_action: WORK_ACCEPTANCE_BEFORE_SEPARATE_COMMIT_AUTHORIZATION
provider_api_rpc_calls: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# Latest handoff — TASK-05 finalization candidate

TASK-05 implementation is published at exact commit
`b7aff0117b1fc6ca4c4229b4c2eb4b9c202e3625`, but Work/control plane still owns
acceptance, canonical reconciliation and `DONE`. Atom T05-A7A is a staged
repository completion repair, not a commit and not automatic task completion.

## Published implementation

- tree: `27d41a8307efdec19faabb82e7be9b5553d3cbdf`;
- parent: `644bda35429ab74b9488d11e78827234d5d438f3`;
- subject: `feat: add TASK-05 canonical data contract`;
- exact changed set: 26 files;
- diff SHA-256:
  `0e73bcca596a9542c849ad8803580c563241a3be55883273d3be9c674d9868e7`;
- targeted TASK-05 tests: 57/57 PASS;
- full unit suite: 235/235 PASS;
- GitHub Actions run/job: `30042685509` / `89326215858`, PASS;
- clean clone: exact HEAD/tree, `main -> origin/main`, single-branch refspec,
  no tags, 57/57 targeted and 235/235 full PASS;
- implementation repository state:
  `TASK05_ATOM5B_CANDIDATE_COMMITTED`;
- provider/API/RPC calls: 0; cash spend: USD 0;
- wallet, signer and transaction actions: 0.

The initial local clean-clone aggregate attempt stopped only because the
repository-required clone-local hooks path had not yet been configured. Applying
the same `core.hooksPath=.githooks` setup used by CI produced a complete PASS.
Remote CI was not rerun.

## T05-A7A exact purpose

The staged candidate:

- adds the required `docs/tasks/TASK-05.md` repository mirror;
- replaces the stale TASK-04 handoff in this file;
- separates the TASK-05 task mirror from its data contract in Catalog;
- advances Catalog to 0.4.1 with 111 assets and 7 queries;
- regenerates only `docs/PROJECT_MAP.md` and
  `catalog/generated/asset_edges.json`;
- recognizes exact `TASK05_FINALIZATION_STAGED` and future
  `TASK05_FINALIZATION_COMMITTED` states without pinning an impossible
  self-referential commit OID.

Schema, Pydantic, migration, query and dependency semantics are unchanged.
Finalization validation counts and the exact staged diff are bound by the Work
acceptance receipt produced after this file is staged.

## TASK-06 entry gate

TASK-06 is not started. Its first action is a read-only Entry Gate over the
published TASK-05 contracts.

Required raw-envelope identity:

- relation: `raw_api_events`;
- primary identity: `raw_event_id`;
- replay identity: `idempotency_key`;
- request/content identities: `request_hash`, `content_sha256`;
- append-only revision chain: `revision_number`, `revision_of`;
- retained outcomes: `SUCCESS`, `HTTP_ERROR`, `PROVIDER_ERROR`, `TIMEOUT`,
  `INVALID_RESPONSE`;
- stored body: redacted bytes only, bound to `redaction_version`.

Required storage-manifest identity:

- dataset: `dataset_manifest_id`, `(dataset_id, dataset_version)`,
  `schema_id`, `schema_sha256`, `dataset_fingerprint`, `generation_task_id`,
  `generation_run_id`, `validation_receipt_sha256`;
- partition: `partition_manifest_id`,
  `(dataset_manifest_id, partition_id)`, `logical_location`, `file_sha256`,
  `content_sha256`, `row_count`, event-time bounds and strategy-availability
  bounds;
- truth boundary: immutable Parquet plus content-addressed dataset/partition
  manifests; DuckDB remains a rebuildable single-writer projection;
- availability: no consumer may read a row before both
  `available_to_strategy_at` and `first_reliable_available_at`;
- failures, missing values, provider disagreement and revisions remain
  explicit and are never overwritten or converted to zero.

TASK-06 requires its own authority before repository writes, dependency changes,
provider/API/RPC calls, account actions, storage allocation or data collection.

## Stop boundary

Work must inspect the exact staged diff, hashes, Catalog/generated outputs and
validation receipt. Only a later explicit authorization may create one ordinary
finalization commit. Push, remote changes, Project Sources/UI actions, provider
calls, purchases, secrets, wallet/signer actions and real money remain
forbidden.
