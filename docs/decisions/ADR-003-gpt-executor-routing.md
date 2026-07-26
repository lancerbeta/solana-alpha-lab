---
adr_id: ADR-003
title: GPT control plane and executor routing
status: PROPOSED_LOCAL_CANDIDATE
as_of: 2026-07-25
owner_task: CTRL-BATON-SETUP
contains_secrets: false
---

# ADR-003 — GPT control plane and executor routing

> Local decision candidate only. Not accepted canonical truth. The GPT control
> plane retains semantic acceptance, roadmap registration, and `DONE`.
> This ADR grants no commit, push, GitHub write, provider, signer, or spend
> authority.

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
3. `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` — Project Chat Pro remains control
   plane; GitHub transports a revision-locked Atom Contract; Cursor is
   `EXECUTION_ONLY`.

GPT control plane means the elected owning ChatGPT Project surface:

- Project Work when `LOCAL_WORK_CODEX` is selected;
- Project Chat Pro when `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` is selected.

Non-negotiable ownership:

- GPT owns task selection, research/design, routing, semantic acceptance,
  canonical status, and `DONE`.
- Cursor never selects current/next canonical tasks and never infers authority
  from Issue, PR, commit, tests, or files alone.
- Preserve `DIRECT_PROMPT`, `LOCAL_HANDOFF`, and `ACCEPT_LOCAL_HANDOFF`.
- Add `GITHUB_BATON` only as a documented future input route.
- One Atom Contract identifies repository, issue, revision, contract hash, base
  HEAD/tree, authority, and managed write set.
- The Atom Contract is revision-locked and content-addressed; published Issue
  transport is mutable infrastructure. Trust uses out-of-band
  expected_contract_sha256 plus revision checks on exact extracted payload bytes;
  Cursor fails closed on mismatch.
- Material contract changes require a new revision and hash.
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
  contract, preflight, and evidence return path are frozen.
- Cloud Agents are not the default executor until local identity, write-set, and
  receipt rules are proven on the private repository path.
- Deferral keeps authority explicit and beginner-safe; revisit only under a new
  accepted ADR/atom.

## Consequences

- Routing docs and Cursor project rules can guide executors without granting
  status authority.
- `GITHUB_BATON` may be documented and preflighted before any Issue/PR machine
  layer exists.
- The A6.2 machine layer currently exists only as a local dirty candidate: not
  committed, not pushed, not live-piloted, and not canonical `DONE`.
- Catalog registration of new protocol assets remains part of that local
  candidate until GPT semantic acceptance and a later commit authority.
- TASK-09 and roadmap status remain untouched by this candidate.
- MCP and Cursor Automations remain deferred.
- In-envelope semantic repairs that stay inside original objective, write set,
  authority, and caps do not require a new transport or revision.

## Security boundary

- Network off by default.
- No secrets, wallet material, absolute machine paths, usernames, or account
  emails in contracts/receipts.
- No implicit GitHub write, commit, push, merge, or canonical status change.
- Bounded GitHub reads require already-explicit authority for the exact
  repository and Issue/revision; no discovery reads.
- Managed write sets are fail-closed.

## Rollback / supersession

- As `PROPOSED_LOCAL_CANDIDATE`, this file may be revised or removed by a later
  authorized atom before acceptance.
- Acceptance requires GPT control-plane semantic acceptance and canonical
  registration.
- A superseding ADR must state the replaced `adr_id`, as-of date, and what
  authority classes remain deferred.
