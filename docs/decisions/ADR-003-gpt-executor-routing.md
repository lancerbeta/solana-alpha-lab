---
adr_id: ADR-003
title: GPT control plane and executor routing
status: PARTIALLY_SUPERSEDED_BY_ADR-004
as_of: 2026-07-28
owner_task: CTRL-BATON-SETUP
contains_secrets: false
---

# ADR-003 — GPT control plane and executor routing

> Accepted repository control mirror for the live GitHub Baton and Cursor
> workplace. Canonical Project Sources reconciliation and roadmap `DONE`
> remain GPT-owned and may still be pending. This ADR does not select a task or
> grant status authority; the standing routine execution grant lives in
> `AGENTS.md`.

## Context

The lab needs a clear beginner-safe model for when GPT works alone, when local
Work/Codex executes inside the repository, and when Project Chat Pro hands a
revision-locked, content-addressed Atom Contract to Cursor through GitHub.
Without that model, executors risk selecting tasks, inferring authority from
Issues/PRs, or treating skills as control owners.

## Decision

Adopt three first-class execution routes:

1. `GPT_ONLY` — research/design/validation with no executor when repository work
   is unnecessary.
2. `LOCAL_WORK_CODEX` — Project Work remains control plane; may execute
   directly or use the existing Work↔Codex handoff.
3. `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` — Project Chat Pro remains primary
   control plane (`CONTROL_PLANE=PROJECT_CHAT_PRIMARY`); GitHub is
   `TRANSPORT_AND_AUDIT` for a revision-locked Atom Contract; Cursor is
   `EXECUTION_ONLY`.

GPT control plane means the elected owning ChatGPT Project surface:

- Project Work when `LOCAL_WORK_CODEX` is selected;
- Project Chat Pro when `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` is selected.

Non-negotiable ownership:

- Project Chat owns task selection, Entry Gate, research/design, Atom Contract,
  routing, semantic acceptance, canonical status, reconciliation, and `DONE`.
- GitHub stores mutable transport and evidence only; it never selects tasks or
  changes canonical status.
- Cursor never selects current/next canonical tasks, never runs lifecycle
  skills as control owners, never expands scope or authority, and never claims
  acceptance or `DONE`.
- Preserve `DIRECT_PROMPT`, `LOCAL_HANDOFF`, and `ACCEPT_LOCAL_HANDOFF`.
- Treat `GITHUB_BATON` as a live accepted input route, not a future,
  local-dirty, pre-merge, or uncommitted candidate description.
- One Atom Contract identifies repository, issue, revision, contract hash, base
  HEAD/tree, authority, and managed write set.
- The Atom Contract is revision-locked and content-addressed; published Issue
  transport is mutable infrastructure. Trust uses out-of-band
  expected_contract_sha256 plus revision checks on exact extracted payload bytes;
  Cursor fails closed on mismatch.
- Material contract changes require a new revision and hash.
- Within an elected objective, scoped write set, caps, and stop conditions,
  `STANDING_PROJECT_AUTONOMY` covers routine local writes, direct propagation
  to tests/Catalog/generated consumers, staging, ordinary commit, fetch,
  non-force branch push, PR/review work, and CI read-back.
- A stricter Atom Contract still wins. Merge authority is superseded by
  `ADR-004` and `OWNER_ATTENTION_GATE`; Cursor never merges.
- Provider/API/RPC/WSS or credentialed-account calls, package/dependency
  changes, purchases/deployments, wallet/signer/real-money actions,
  force/destructive operations, settings/access changes, and canonical
  acceptance/status remain separate gates.
- Skills are helper procedures, not canonical control owners.
- Seven canonical Project Sources remain in ChatGPT Project and are not copied
  into Cursor/Git as a second permanent-memory truth owner.

Repository mirrors:

- `docs/agent/EXECUTION_ROUTER_PROTOCOL.md`
- `docs/agent/GITHUB_BATON_PROTOCOL.md`
- `AGENTS.md` input-route and `EXECUTION_ONLY` updates

## Alternatives considered

| Alternative | Outcome |
|---|---|
| Always create a Cursor/Codex executor | Rejected; wastes capacity and blurs `GPT_ONLY` |
| Issue/PR as implicit authority | Rejected; executors must not infer authority |
| Treat Issue/GitHub bytes as physically immutable | Rejected; transport is mutable; contract is revision/hash locked |
| Replace local handoff with GitHub-only | Rejected; preserve working Work↔Codex routes |
| Copy seven Project Sources into Git as dual truth | Rejected; single control-plane owner |
| Skills as canonical task owners | Rejected; skills advise, GPT accepts |

## Why MCP, Automations, and Cloud Agents are deferred

- MCP and Cursor Automations add network and privilege surfaces before the baton
  evidence-return path and operator workflow are frozen for those surfaces.
- Cloud Agents are not the default executor until local identity, write-set, and
  receipt rules remain proven on the private repository path.
- Deferral keeps authority explicit and beginner-safe; revisit only under a new
  accepted ADR/atom.

## Consequences

- Routing docs and Cursor project rules guide executors without granting status
  authority.
- `GITHUB_BATON` is live on the accepted repository control contracts and may be
  preflighted and executed under exact Atom Contracts.
- The baton machine layer is committed on `main` and is no longer described as a
  local-dirty / pre-merge / uncommitted candidate.
- Catalog and generated navigation must stay hash-reconciled with those control
  contracts.
- `TASK-09` remains READY / NOT_STARTED and is untouched by this ADR.
- Canonical Project Sources remain unchanged until later GPT reconciliation.
- MCP and Cursor Automations remain deferred.
- In-envelope semantic repairs that stay inside original objective, write set,
  authority, and caps do not require a new transport or revision.
- During iteration, run targeted checks. Assign exactly one full-gate owner to
  each unchanged candidate fingerprint: Cursor, Codex, or GitHub CI. A passing
  full gate is reused until bytes, dependencies, runtime, or applicable policy
  change.

## Security boundary

- Offline work remains the default for product implementation. Exact GitHub
  transport/read-back and public official-documentation reads are routine
  control-plane operations under the standing grant.
- No secrets, wallet material, absolute machine paths, usernames, or account
  emails in contracts/receipts.
- No artifact or conversational cue selects a task, expands scope, authorizes
  merge, or changes canonical status.
- GitHub operations stay bound to the elected repository, branch, PR, and
  exact Issue/revision; no unrelated account/repository discovery.
- Managed write sets are fail-closed.

## Rollback / supersession

- As `ACCEPTED_REPOSITORY_MIRROR`, material changes require a later authorized
  atom and, when terms change, a new baton contract revision/hash.
- `ADR-004` supersedes only this ADR's merge-authority rule; route selection,
  baton trust and status ownership remain active.
- Canonical Source registration and roadmap `DONE` remain GPT-owned.
- A superseding ADR must state the replaced `adr_id`, as-of date, and what
  authority classes remain deferred.
