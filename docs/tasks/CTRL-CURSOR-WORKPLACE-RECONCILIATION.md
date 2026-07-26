---
task_id: CTRL-CURSOR-WORKPLACE-RECONCILIATION
task_version: "1.0"
title: Live GitHub Baton and Cursor workplace control reconciliation
phase: control_infrastructure
canonical_status: REPOSITORY_MIRROR_IN_PROGRESS
canonical_status_owner: ChatGPT_Project_GPT_Control_Plane
current_owning_surface: LOCAL_WORK_PRIMARY
repository_evidence_status: LOCAL_STAGED_REPAIR_CANDIDATE
atom_id: CWR-A4_WORK_REELECTION_FAIL_CLOSED_REPAIR
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

- Current `CTRL-CURSOR-WORKPLACE-RECONCILIATION` control plane =
  `LOCAL_WORK_PRIMARY`.
- For the generic live `GITHUB_BATON` route, when selected:
  `CONTROL_PLANE` = `PROJECT_CHAT_PRIMARY`, GitHub = `TRANSPORT_AND_AUDIT`,
  and Cursor = `EXECUTION_ONLY`.
- `GITHUB_BATON` remains a live accepted route; it is not the selected control
  surface for the current local Work atom.

## Active atom

`CWR-A4_WORK_REELECTION_FAIL_CLOSED_REPAIR` continues the live-route chain started by
`CWR-A1_LIVE_ROUTE_CONTRACT_REPAIR` on published branch
`ctrl/live-baton-reconciliation`.

Publication evidence:

- Branch pushed to `origin/ctrl/live-baton-reconciliation`
- Draft PR `#6` open into `main`
- Prior CI on the published head: PASS
- Current local atom reconciles Work ownership, fails closed on unreadable Git
  upstream state, registers this mirror in Catalog, and refreshes navigation

Authority: local write and exact stage only for the explicitly approved nineteen-file
managed set. Offline, no dependency changes, and USD 0.
Stop before commit, PR mutation, Ready, or merge.

## Invariants

- This Local Work owns the current CWR atom, reconciliation, validation, and
  semantic acceptance checkpoint.
- The GPT control plane remains owner of canonical Project Sources, roadmap
  status, architecture, and project-level `DONE`.
- GitHub never selects tasks or changes canonical status.
- Cursor executes only an exact approved atom and never runs lifecycle skills
  as control owners, expands scope/authority, or claims acceptance/`DONE`.
- Authority classes remain separate; `LOCAL_WRITE` does not grant commit, push,
  PR, settings, merge, provider, or destructive authority.
- `TASK-09` remains READY / NOT_STARTED.
- Canonical Sources remain unchanged and require later reconciliation.
- A branch with no configured upstream is represented as deterministic `NONE`
  only after successful Git reads; unreadable Git state blocks preflight.
- Generic ctrl repository file count binds the actual committed tree inventory
  fail-closed, not the historical fixed Baton 225-file checkpoint.
- Generic ctrl staged repair accepts modified tracked files only, including on
  a published linear branch with matching upstream and remote OID.
- The current atom independently requires the staged path set to equal the
  approved nineteen-file managed set exactly.

## Non-goals

- Commit, push, PR mutation, Ready transition, merge, settings mutation, branch
  deletion, Issue comment, or canonical status change
- TASK-09 implementation
- Dependency, provider, wallet, signer, or real-money action
