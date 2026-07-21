---
task_id: TASK-03
task_version: "1.0"
implementation_status: IN_PROGRESS
canonical_status_owner: ChatGPT_Project_Work
phase: P0
cash_cap: USD_0
repository_commit: NONE
remote: NONE
provider_calls: 0
contains_secrets: false
---

# TASK-03 — Private repository, controls & Project Asset Catalog

## Accepted checkpoints

- TASK-02: DONE.
- Local repository/security baseline: validated.
- uv-managed CPython 3.13.14 and `uv.lock`: validated.
- PowerShell 7.6.3 local quality gate: validated.
- Host execution policy requires process-scoped `-ExecutionPolicy Bypass` for repository-owned unsigned validation scripts; no persistent policy change.
- Secret rejection and versioned pre-commit hook: validated.
- First-commit candidate staging evidence: validated.
- Commits: 0.
- Remotes: 0.
- Provider/API/RPC calls: 0.
- Project Asset Catalog: not implemented.
- Codex workspace/write access: not granted.

## Current atom

Prepare the exact repository tree for a separately authorized first commit:

- replace pre-commit-only assertions with a two-state validator;
- preserve strict staged-tree validation before commit;
- support exactly one clean root commit after commit;
- create a commit-ready receipt with deterministic payload fingerprints;
- avoid embedding the unknown future commit hash in the commit itself;
- leave author identity and commit execution to Atom 2G.

## Not allowed

- creating the first commit;
- remote or GitHub repository creation;
- connector permission;
- Codex workspace/write action;
- provider account/key/API/RPC call;
- trading/data dependencies;
- raw/canonical data;
- database, VPS, wallet, signer, or real money.

## Acceptance

- repository state is `COMMIT_READY_STAGED`;
- exactly 21 approved files are staged;
- no untracked or unstaged file remains;
- `.githooks/pre-commit` has mode `100755`;
- staged secret scan and whitespace check pass;
- payload manifest/content fingerprints match the Atom 2F receipt;
- real pre-commit hook and canonical quality gate pass;
- validator is statically proven to accept exactly one clean root commit
  with the same payload fingerprints;
- commit count and remote count remain zero.

## Next atom after acceptance

Atom 2G confirms the repository-local author identity policy, creates one
local root commit with the approved message, and validates the resulting
`COMMITTED_BASELINE`. Remote creation remains a later separate action.
