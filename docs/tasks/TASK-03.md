---
task_id: TASK-03
task_version: "1.0"
implementation_status: IN_PROGRESS
canonical_status_owner: ChatGPT_Project_Work
phase: P0
cash_cap: USD_0
repository_commit: ee6119ae0b7750710c7f822c50137ed95b4977e9
remote: NONE
provider_calls: 0
contains_secrets: false
---

# TASK-03 — Private repository, controls & Project Asset Catalog

## Accepted checkpoints

- Repository baseline commit: accepted.
- Catalog foundation commit: `ee6119ae0b7750710c7f822c50137ed95b4977e9`, accepted.
- Catalog foundation: 17 assets, 3 queries, 3 schemas, stable-ID resolver PASS.
- Remote/push: absent.
- Provider/API/RPC calls: 0.

## Current atom

Stage exact import of TASK-01 and TASK-02 historical evidence plus registration of `ARCH-INTENT-001`:

- 12 exact TASK-01 files;
- 8 exact TASK-02 files;
- 2 external immutable bundle records;
- 1 bundle-only superseded TASK-01 validator record;
- provenance-aware Catalog schema evolution;
- `first_reliable_available_at` preservation and no-backfill rule;
- architecture intent registration as current direction, not historical evidence;
- deterministic import validator and query recipe;
- no commit and no remote.

## Not allowed

- commit, remote, push, connector permission, Codex write;
- provider account/key/API/RPC call;
- raw/canonical market data;
- database, collector, VPS, wallet, signer, or real money;
- claiming that `ARCH-INTENT-001`, `ORCH-001`, or `CTX-AOT-ALBS-001` is implemented.

## Acceptance

- repository state is `PRE_GIT_IMPORT_STAGED`;
- HEAD remains `ee6119ae0b7750710c7f822c50137ed95b4977e9` and commit count remains 2;
- repository file count is 58; staged change count is 40; no untracked or unstaged drift;
- 20 imported files match exact SHA-256 and source-bundle paths;
- exact imported files are exempt from repository style normalization; all repository-authored staged files still pass `git diff --check`;
- source ZIP audits and checksum ledgers pass;
- Catalog has 44 assets, 4 query recipes, 3 schemas, and 3 asset registries;
- external bundles remain outside Git;
- A028 stays bundle-only and superseded;
- provenance and first reliable availability validate;
- `ARCH-INTENT-001` is current direction only;
- pre-commit hook, quality gate, secret/path/EOL checks, and tests pass.

## Next atom after acceptance

Create a separate import commit only after staged hashes, Catalog resolution, provenance, availability, and rollback evidence are accepted. Remote remains later.
