---
task_id: CTRL-CURSOR-WORKPLACE-RECONCILIATION
task_version: "1.0"
title: Live GitHub Baton and Cursor workplace control reconciliation
phase: control_infrastructure
canonical_status: REPOSITORY_MIRROR_IN_PROGRESS
canonical_status_owner: ChatGPT_Project_GPT_Control_Plane
current_owning_surface: Project_Chat_Pro
repository_evidence_status: LOCAL_COMMIT_STOP_BEFORE_PUSH
atom_id: CWR-A1D_REPOSITORY_GATE_REPAIR
provider_api_rpc_calls: 0
cash_spend_usd: 0
wallet_signer_transaction_actions: 0
contains_secrets: false
---

# CTRL-CURSOR-WORKPLACE-RECONCILIATION

Repository mirror for reconciling control contracts to the accepted live
GitHub Baton and Cursor workplace. Canonical Project Sources and roadmap
`DONE` remain GPT-owned.

## Control posture

- `CONTROL_PLANE` = `PROJECT_CHAT_PRIMARY`
- GitHub = `TRANSPORT_AND_AUDIT`
- Cursor = `EXECUTION_ONLY`
- `GITHUB_BATON` = live accepted route

## Active atom

`CWR-A1D_REPOSITORY_GATE_REPAIR` continues the live-route chain started by
`CWR-A1_LIVE_ROUTE_CONTRACT_REPAIR` on local branch
`ctrl/live-baton-reconciliation` from accepted base
`ad98f5d762fe590cc5c82c7e3bc9b5047e9b4a69` /
`d8a1acb72fb8a66917a4f99169616666d8898e89`.

Authority: bounded six-file local repair plus exactly one second local
commit with the normal pre-commit hook. Stop before push.

## Invariants

- Project Chat owns task selection, Entry Gate, architecture, Atom Contract,
  semantic acceptance, canonical status, reconciliation, and `DONE`.
- GitHub never selects tasks or changes canonical status.
- Cursor executes only an exact approved atom and never runs lifecycle skills
  as control owners, expands scope/authority, or claims acceptance/`DONE`.
- Authority classes remain separate; `LOCAL_WRITE` does not grant commit, push,
  PR, settings, merge, provider, or destructive authority.
- `TASK-09` remains READY / NOT_STARTED.
- Canonical Sources remain unchanged and require later reconciliation.
- Missing `@{upstream}` is represented as deterministic `NONE` in baton
  preflight structured output.
- Generic ctrl repository file count binds the actual committed tree inventory
  fail-closed, not the historical fixed Baton 225-file checkpoint.
- Generic ctrl staged repair accepts modified tracked files only.

## Non-goals

- Push, Draft PR, Issue comment, merge, or canonical status change
- TASK-09 implementation
- Dependency, provider, wallet, signer, or real-money action
