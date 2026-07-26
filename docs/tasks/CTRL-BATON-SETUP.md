---
task_id: CTRL-BATON-SETUP
task_version: "0.9"
title: GPT executor routing and GitHub baton machine layer
phase: control_infrastructure
canonical_status: CANDIDATE_NOT_REGISTERED
canonical_status_owner: ChatGPT_Project_GPT_Control_Plane
current_owning_surface: Project_Chat_Pro
repository_evidence_status: PRE_MERGE_LOCAL_MAIN_REPAIR_CANDIDATE
atom_id: A6.18_PRE_MERGE_LOCAL_MAIN_STATE_REPAIR
provider_api_rpc_calls: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# CTRL-BATON-SETUP — candidate control-infrastructure task mirror

Temporary ID: `CTRL-BATON-SETUP` (non-canonical).

Owner: ChatGPT Project GPT control plane.
Current owning surface: Project Chat Pro.
Cursor: `EXECUTION_ONLY`.

This file is a repository candidate, not roadmap truth. Canonical registration,
ordering, acceptance and DONE remain owned by the GPT control plane.
No repository file may claim canonical DONE.
`TASK-09` remains READY / NOT_STARTED and is not started or changed by this
candidate.

## Atom authority split

- `A6.1` / `A6.1R` — protocol foundation (AGENTS, router, baton protocol, ADR,
  Cursor rules/command, `.cursorignore`).
- `A6.2` — machine layer (schemas, scripts, fixtures, templates, CI, Catalog
  registration) as a local dirty candidate only.
- `A6.2R_BATON_SECURITY_AUTHORITY_REPAIR` — material scope/security/authority
  repair on the existing local candidate (`LOCAL_WRITE` +
  `MATERIAL_SCOPE_PATCH`).
- `A6.2R2_BATON_PORTABILITY_AND_FAIL_CLOSED_REPAIR` — portability and
  fail-closed receipt/path/repository-policy repair on the same local dirty
  candidate.
- `A6.2R3_BATON_REPOSITORY_IDENTITY_AND_URI_REPAIR` — local repository identity
  and URI-vs-UNC string-scan repair on the same local dirty candidate.
- `A6.2R4_BATON_ORIGIN_REDACTION_REPAIR` — origin mismatch evidence redaction
  so raw `origin_url` / userinfo never enters codes, receipts, or summaries.
- `A6.4_COMPOSITIONAL_REPOSITORY_STATE_MACHINE_PATCH` — exact lifecycle
  composition for local staged/committed/published feature states, GitHub PR
  merge checkout, and merge-commit-only main push checkout.
- `A6.5` / `A6.6` / `A6.7` — exact restage, one local commit, and publication
  of `ctrl/baton-setup`.
- `A6.8` — Draft PR #1 plus GitHub Actions read-back. Run `30177151609`, job
  `89727671250`, failed before repository-policy classification.
- `A6.8R1` — read-only root cause: fixture and Catalog integrity used raw
  platform-dependent Windows worktree bytes instead of canonical Git blob
  content.
- `A6.9_PR_CI_CANONICAL_BLOB_HASH_REPAIR` — local-only canonical Git-content
  resolver, fixture/Catalog hash repair, and two transient lifecycle states.
- `A6.10` — completed exact 15-path repair stage and full local gate.
- `A6.11` — completed one amend preserving the single-commit feature shape.
- `A6.12` — completed exact force-with-lease publication and successful PR CI
  read-back.
- `A6.13_FINAL_RECONCILIATION_PATCH` — local-only pre-merge evidence,
  Catalog, and lifecycle reconciliation candidate.
- `A6.14` / `A6.15` / `A6.16` — exact reconciliation stage, one amend, and
  force-with-lease publication with successful PR CI.
- `A6.17` — PR body reconciled to the published F3 checkpoint and PR #1 moved
  from Draft to Ready.
- `A6.18_PRE_MERGE_LOCAL_MAIN_STATE_REPAIR` — exact fail-closed staged repair
  plus local post-merge main topology with both feature refs preserved.

The accepted A6.17 checkpoint is feature commit
`57ea966c1afe00d16836f2067e8a2c985289116b`, tree
`12eb2852fd7b733572464a085fa0cd5091b4ab22`, parent/base
`bd152b3199a9ba5c75374bd798b1e81756cd4d9b`, with exactly 84 changed paths
and one commit. PR #1 is OPEN, Ready and mergeable. Local validation passed
601 tests with zero skipped; PR CI run `30190666920`, job `89763237448`,
passed on synthetic merge
`1b97ff72cfe03786cee8e4dbae234c3a470d46fc`. That checkpoint used Catalog
0.8.3. No merge or canonical state change occurred.

A6.18 is a separate exact 12-path pre-merge repair candidate with Catalog
0.8.4. It closes the discovered local-main gate gap without broadening the
GitHub checkout policy: local main is accepted only after an exact two-parent
merge, ff-only synchronization, clean content, and preservation of matching
local and remote feature refs. Its amended commit SHA, tree SHA, workflow
run/job and post-push synthetic merge are `PENDING_EXTERNAL_READBACK` until
the authorized publication completes. Final merge SHA is also pending because
merge is not authorized here. Canonical status change remains `NONE`.

## Objective

Establish a beginner-safe protocol foundation for:

- `GPT_ONLY`
- `LOCAL_WORK_CODEX`
- `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR`

so executors cannot silently become task owners, and so GitHub baton transport
can be added later without replacing local handoff routes.

## Current atoms

Candidate outputs under
`A6.1`+`A6.2`+`A6.2R`+`A6.2R2`+`A6.2R3`+`A6.2R4`+`A6.4`+`A6.9`+`A6.13`+`A6.18`:

- patch `AGENTS.md` for `GITHUB_BATON` and Cursor `EXECUTION_ONLY`;
- execution-router and GitHub-baton protocol docs with out-of-band hash trust;
- ADR-003 as `PROPOSED_LOCAL_CANDIDATE`;
- Cursor rules/command and `.cursorignore`;
- Atom Contract / execution / acceptance JSON Schemas;
- offline baton scripts, fixtures, fixture manifest, tests, Issue form and PR
  template;
- fail-closed managed-write/path/receipt/repository-policy repairs;
- A6.2R2 portability and fail-closed repair;
- A6.2R3 local repository identity + URI-vs-UNC scan repair;
- A6.2R4 origin mismatch redaction (`origin_not_allowed` / no raw URL leak);
- compositional repository-state/topology policy with eleven exact allowed
  combinations and no permissive feature-branch allowlist;
- canonical repository-content hashing from index blobs or side-effect-free,
  Git-proved candidate clean bytes;
- 37-entry fixture manifest using canonical Git-content SHA-256 and a
  platform-neutral synthetic CR rejection regression;
- Catalog 0.8.4 candidate with canonical-integrity sweep across all 190 assets;
- merge-commit-only validation: exact `(H0,F)` parent order,
  `F^=H0`, `tree(M)=tree(F)`, and exact 84-path `diff(H0,M)`;
- CI pull_request+main trigger and Catalog registration;
- fail-closed local-main post-merge validation with exact retained feature
  refs, main upstream, merge parent order, tree equality and inventory;
- stop before merge, settings writes, branch deletion or canonical
  reconciliation.

The failed A6.8 CI run remains immutable evidence alongside the successful
A6.12 and A6.17 checkpoints. A6.18 starts from the published F3 branch with
matching local/remote feature refs and unchanged `main` / `origin/main`.
GitHub private-repository branch protection is
`DEFERRED_BY_OWNER_COST_NOT_JUSTIFIED_FOR_MVP`; compensating exact read-back,
merge-commit-only and post-merge CI/local validation controls apply. Merge and
canonical reconciliation are not complete. `TASK-09` remains READY /
NOT_STARTED.

## A6.18 compositional lifecycle

Only these repository-state/topology combinations are accepted:

1. `CTRL_BATON_A62R_CANDIDATE_DIRTY` / `PUBLISHED_LOCAL`;
2. `CTRL_BATON_A62R_CANDIDATE_STAGED` / `BATON_FEATURE_LOCAL`;
3. `CTRL_BATON_A62_FEATURE_COMMITTED` / `BATON_FEATURE_LOCAL`;
4. `CTRL_BATON_A62_FEATURE_COMMITTED` / `BATON_FEATURE_PUBLISHED`;
5. `CTRL_BATON_A62_PR_MERGE_CHECKOUT` /
   `GITHUB_PR_MERGE_CHECKOUT`;
6. `CTRL_BATON_A62_MAIN_MERGE_COMMITTED` /
   `GITHUB_MAIN_PUSH_CHECKOUT`.
7. `CTRL_BATON_A69_PR_CI_REPAIR_STAGED` /
   `BATON_FEATURE_PUBLISHED_REPAIR_STAGED`.
8. `CTRL_BATON_A62_FEATURE_COMMITTED` /
   `BATON_FEATURE_AHEAD_OF_PUBLISHED`.
9. `CTRL_BATON_A613_FINAL_RECONCILIATION_STAGED` /
   `BATON_FEATURE_PUBLISHED_RECONCILIATION_STAGED`.
10. `CTRL_BATON_A618_LOCAL_MAIN_REPAIR_STAGED` /
    `BATON_FEATURE_PUBLISHED_LOCAL_MAIN_REPAIR_STAGED`.
11. `CTRL_BATON_A62_MAIN_MERGE_COMMITTED` /
    `BATON_MAIN_LOCAL_POST_MERGE`.

The main transition accepts only a two-parent merge commit with parents
`(H0,F)` in that order. Direct, squash, fast-forward, swapped-parent, partial,
extra-inventory, and merge-content-drift forms fail closed. Pull-request
checkout derives base/head identity from GitHub event context and locally
available commit objects; it does not claim canonical GPT acceptance or prove
the later main merge belongs to a GitHub PR. The local post-merge combination
additionally requires `main=origin/main=M`, `F^=H0`, `tree(M)=tree(F)`,
`upstream=origin/main`, and exact matching local/remote feature refs.

## Next material boundary

After the authorized A6.18 stage/amend/force-with-lease/CI/body reconciliation
passes, the next material boundary is explicit merge-commit-only PR #1 plus
post-merge GitHub/local validation. Remote settings hardening remains deferred
by owner and is not part of this MVP workflow.

## Definition of Done (candidate)

Repository DoD for this candidate is technical only:

- managed write set contains the protocol foundation and machine-layer files;
- repository state and topology are accepted only as one of the eleven exact
  lifecycle combinations;
- repository-policy tests reject direct/squash/fast-forward main updates,
  swapped parents, tree drift, inventory drift, stale refs, and mixed states;
- preflight and authority boundaries are documented;
- validation findings are reported honestly, including Catalog-pending states;
- A6.18 publication uses one amend, one exact force-with-lease update and one
  PR body reconciliation only;
- no merge, settings change, branch deletion, purchase or canonical write is
  performed under A6.18.

Canonical DoD and `DONE` remain GPT-owned after semantic acceptance and
roadmap registration.

## Authority boundaries

Allowed under authorized `PRE_MERGE_LOCAL_MAIN_STATE_REPAIR`:

- `LOCAL_WRITE` inside the exact 12-path managed write set;
- exact-path staging, one `--no-edit` amend, one exact force-with-lease update
  from accepted F3, bounded PR/CI read-back and PR #1 body reconciliation.

Forbidden here:

- merge, squash, rebase, auto-merge, direct-main push, branch deletion,
  comments, labels, GitHub settings, purchase or deployment;
- TASK-09 implementation;
- Project Sources / roadmap / current-state canonical edits;
- skill, plugin, MCP, or Automation changes;
- provider/API/RPC calls;
- start-solana-task / finish-solana-task modifications.

The association between a real main merge commit and PR #1 remains
`NOT_TESTABLE` until the separately authorized merge/read-back. Merge-commit
availability is checked immediately before that boundary. GitHub Pro and
private-repository protection remain explicitly deferred by owner; no settings
write is attempted.

## Non-goals

- Changing PR #1 title, Ready state, comments, labels, settings, or merging it.
- Declaring CTRL-BATON-SETUP a registered roadmap task.
- Moving seven Project Sources into Git as a second permanent-memory owner.
