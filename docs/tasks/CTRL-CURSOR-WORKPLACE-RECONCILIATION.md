---
task_id: CTRL-CURSOR-WORKPLACE-RECONCILIATION
task_version: "1.0"
title: Live GitHub Baton and Cursor workplace control reconciliation
phase: control_infrastructure
canonical_status: REPOSITORY_MIRROR_IN_PROGRESS
canonical_status_owner: ChatGPT_Project_GPT_Control_Plane
current_owning_surface: Project_Chat_Pro
repository_evidence_status: PUBLISHED_DRAFT_PR_EVIDENCE
atom_id: CWR-A3_PRE_MERGE_TASK_MIRROR_REPAIR
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

`CWR-A3_PRE_MERGE_TASK_MIRROR_REPAIR` continues the live-route chain started by
`CWR-A1_LIVE_ROUTE_CONTRACT_REPAIR` on published branch
`ctrl/live-baton-reconciliation`.

Publication evidence:

- Branch pushed to `origin/ctrl/live-baton-reconciliation`
- Draft PR `#6` open into `main`
- Prior CI on the published head: PASS
- Current atom repairs published staged lifecycle plus this living mirror

Authority: bounded four-file local repair, one normal commit, non-force push to
the existing upstream, and UTF-8 body-only update of Draft PR `#6`.
Stop before Ready or merge.

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
- Generic ctrl staged repair accepts modified tracked files only, including on
  a published linear branch with matching upstream and remote OID.

## Non-goals

- Ready transition, merge, settings mutation, branch deletion, Issue comment,
  or canonical status change
- TASK-09 implementation
- Dependency, provider, wallet, signer, or real-money action
