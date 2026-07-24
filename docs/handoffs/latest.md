---
handoff_status: LOCAL_FINALIZATION_CANDIDATE
task_id: TASK-06
atom_id: T06-A8A
canonical_status: IN_PROGRESS
canonical_status_owner: ChatGPT_Project_Work
repository_candidate_state: IMPLEMENTED_UNVERIFIED
accepted_implementation_commit: 23ead28bfb9fe9c60fd143b7e69267b61bc8512c
accepted_implementation_tree: dead22b1d8bae02fead79d3aa7ef27c13f6c840a
finalization_commit: FORBIDDEN_NOT_CREATED
next_action: WORK_ACCEPTANCE_BEFORE_SEPARATE_COMMIT_AUTHORIZATION
provider_api_rpc_calls: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# Latest handoff — TASK-06 finalization candidate

TASK-06 implementation is published at exact commit
`23ead28bfb9fe9c60fd143b7e69267b61bc8512c`, but Work/control plane still owns
acceptance, canonical reconciliation and `DONE`. Atom `T06-A8A` is a staged
repository completion candidate, not a commit and not automatic task
completion.

## Published implementation

- tree: `dead22b1d8bae02fead79d3aa7ef27c13f6c840a`;
- parent: `1db62c7abc06bcb4ab209b3db7f4eb858f64330a`;
- subject: `feat: add TASK-06 raw storage boundary`;
- exact changed set: 28 files;
- diff SHA-256:
  `ccf22d511b7e32bfd758aaa79534e8a1f8b2764a9b598e6a2dc89a571429ba60`;
- targeted TASK-06 tests: 64/64 PASS;
- full unit suite: 310/310 PASS;
- GitHub Actions run/job: `30057909197` / `89373386559`, PASS;
- clean clone: exact HEAD/tree, `main -> origin/main`, single-branch refspec,
  no tags, clean index/worktree, 64/64 targeted and 310/310 full PASS;
- implementation repository state:
  `TASK06_ATOM7B_CANDIDATE_COMMITTED`;
- provider/API/RPC calls: 0; cash spend: USD 0;
- wallet, signer and transaction actions: 0.

## T06-A8A exact purpose

The staged candidate:

- reconciles `docs/tasks/TASK-06.md` with the published implementation,
  CI and clean-clone evidence;
- replaces the stale TASK-05 handoff in this file;
- transfers the handoff Catalog record to TASK-06 and the TASK-07 consumer;
- advances Catalog to 0.5.1 with 128 assets and 7 queries;
- regenerates only `docs/PROJECT_MAP.md` and
  `catalog/generated/asset_edges.json`;
- recognizes exact `TASK06_FINALIZATION_STAGED` and future
  `TASK06_FINALIZATION_COMMITTED` states without pinning an impossible
  self-referential commit OID.

Raw-envelope, manifest, Parquet, storage-budget, dependency and provider
semantics are unchanged. Finalization validation counts and the exact staged
diff are bound by the Work acceptance receipt produced after staging.

## TASK-07 entry gate

TASK-07 is not started. Its first action is a read-only Entry Gate over the
published TASK-06 contracts and the canonical provider decision evidence.

The gate must freeze before any external call:

- provider and official endpoint/version evidence with an `as_of` date;
- exact request inventory and maximum request count;
- credit, cash, timeout, retry, 429 and stop caps;
- redaction-before-storage and retained success/failure outcomes;
- raw-event, request, content, revision and idempotency identities;
- dataset/partition identities, availability bounds and fingerprints;
- sanitized report, receipt, validation and rollback requirements.

TASK-07 requires separate authority before repository writes, provider/account
actions, API/RPC calls, credential use, purchases, storage allocation or data
collection.

## Stop boundary

Work must inspect the exact staged diff, hashes, Catalog/generated outputs and
validation receipt. Only a later explicit authorization may create one ordinary
finalization commit. Push, remote changes, Project Sources/UI actions, provider
calls, purchases, secrets, wallet/signer actions and real money remain
forbidden.
