---
task_id: CTRL-CURSOR-WORKPLACE-RECONCILIATION
task_version: "1.0"
title: Live GitHub Baton and Cursor workplace control reconciliation
phase: control_infrastructure
canonical_status: REPOSITORY_MIRROR_IN_PROGRESS
canonical_status_owner: ChatGPT_Project_GPT_Control_Plane
current_owning_surface: Project_Chat_Pro
repository_evidence_status: LOCAL_WRITE_STOP_BEFORE_COMMIT
atom_id: CWR-A1_LIVE_ROUTE_CONTRACT_REPAIR
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

`CWR-A1_LIVE_ROUTE_CONTRACT_REPAIR` on local branch
`ctrl/live-baton-reconciliation` from accepted base
`308a062f3c5cb28c1ac9ba1c1fc5fc368f74bd8a` /
`6e2aaea5c94f00d7d2c6e4c71668f4bb75885b53`.

Authority: `LOCAL_WRITE` only. Stop before staging or commit.

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

## Non-goals

- Commit, push, Draft PR, Issue comment, merge, or canonical status change
- TASK-09 implementation
- Dependency, provider, wallet, signer, or real-money action
