---
task_id: TASK-03
task_version: "1.0"
implementation_status: IN_PROGRESS
canonical_status_owner: ChatGPT_Project_Work
phase: P0
cash_cap: USD_0
repository_commit: "399ef0365b017fcd9d7b81389218a63bf1e466c1"
remote: NONE
provider_calls: 0
contains_secrets: false
---

# TASK-03 — Private repository, controls & Project Asset Catalog

## Accepted checkpoints

- TASK-02 and Source activation: accepted.
- Local root commit `399ef0365b017fcd9d7b81389218a63bf1e466c1`:
  `COMMITTED_BASELINE`, clean, no remote.
- uv-managed CPython 3.13.14 and PowerShell 7.6.3: validated.
- Local secret rejection and versioned pre-commit hook: validated.

## Current atom — 3A-R

Implement and stage the Catalog foundation, with the pre-commit EOL repair:

- root resolver;
- manifest, asset-registry, and query-recipe schemas;
- one core asset registry with current repository/control assets;
- bounded read-only query registry;
- deterministic Catalog validator and resolver CLI;
- dependency adoption ADR;
- unit and negative tests;
- exact staged candidate receipt;
- `*.ps1 text eol=lf` checkout policy and roundtrip validation.

## Explicitly excluded

- pre-Git TASK-01/02 import;
- lifecycle registry skeletons;
- generated project map and edge projection;
- private remote, CI, clean clone;
- GitHub connector permissions;
- Codex workspace/write actions;
- provider/API/RPC calls;
- raw/canonical data, DB, VPS, wallet, signer, or real money.

## Atom 3A-R acceptance

- exact dependencies are locked: `PyYAML==6.0.3`, `jsonschema==4.26.0`;
- root manifest and three standalone schemas validate;
- stable asset/query IDs are unique and mandatory IDs resolve;
- all relations and query targets resolve;
- repository paths are relative, present, and inside the repository;
- declared SHA-256 values match non-self-referential files;
- self-referential Catalog roots use accepted-commit evidence policy;
- query recipes are bounded, read-only, and no-write;
- duplicate, broken-reference, absolute-path, hash-drift, and write-effect
  negative tests fail as designed;
- resolver CLI returns the expected root asset and validation recipe;
- `.gitattributes` declares `*.ps1 text eol=lf` and forbids the old CRLF rule;
- working-tree, staged/committed, cached-attribute, and temporary checkout
  checks all prove LF-only PowerShell bytes;
- exact 21-file Atom 3A-R changed set is staged; no unstaged/untracked drift;
- no commit or remote is created.

## Next atom

Review and separately authorize the Catalog-foundation commit. Pre-Git import
remains a later atom after the committed foundation is accepted.
