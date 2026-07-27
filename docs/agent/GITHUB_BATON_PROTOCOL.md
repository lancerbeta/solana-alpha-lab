# GitHub Baton Protocol

Live execution flow for route
`PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR`.

This document defines the live control-transport protocol. Exact contract read,
task branch, ordinary commit, non-force push, PR/review, and CI interaction are
routine transport under `STANDING_PROJECT_AUTONOMY`. Settings, provider calls,
credentials, spend, destructive actions, and merge remain separately bounded.

Related:

- `AGENTS.md` — input routes and `EXECUTION_ONLY` boundary
- `docs/agent/EXECUTION_ROUTER_PROTOCOL.md` — route selection
- `docs/agent/HANDOFF_PROTOCOL.md` — preserved local Work↔Codex routes

## Roles

| Role | Owns |
|---|---|
| Project Chat Pro / GPT control plane (`PROJECT_CHAT_PRIMARY`) | Task selection, Entry Gate, research/design, Atom Contract authoring, routing, semantic acceptance, canonical status, reconciliation, `DONE` |
| GitHub (`TRANSPORT_AND_AUDIT`) | Mutable transport and evidence surfaces for a revision-locked Atom Contract; never selects tasks or changes canonical status |
| Cursor (`EXECUTION_ONLY`) | Bounded local execution of the exact named atom only |

Cursor never selects the current or next canonical task and never infers
authority from an Issue, PR, commit, tests, or files alone. Cursor never runs
lifecycle skills as control owners, never expands scope or authority, and never
claims acceptance or `DONE`.

## Contract mutability model

- The Atom Contract payload is exact UTF-8 JSON bytes.
- Exact canonical contract bytes have a SHA-256 computed over those exact bytes.
- Published Issue transport is mutable infrastructure, not physically immutable.
- GPT control plane supplies out-of-band launch parameters: repository full
  name, Issue number, contract revision, and `expected_contract_sha256`.
- `expected_contract_sha256` must not be derived only from the fetched Issue
  body or from a hash embedded inside that same body.
- Cursor extracts payload bytes between
  `<!-- SMIAL-BATON-CONTRACT-BEGIN -->` and
  `<!-- SMIAL-BATON-CONTRACT-END -->`, hashes those exact bytes, and compares
  them to the out-of-band expected hash while verifying the out-of-band
  revision against the parsed payload.
- Editing both Issue text and any embedded informational hash cannot establish
  trust.
- The Atom Contract schema must not require a self-referential
  `contract_sha256` field inside its own payload.
- Cursor must fail closed on hash or revision mismatch
  (`BLOCKED_CONTRACT_MISMATCH`).

Material contract changes require a new `revision` and a new hash.

## End-to-end flow

1. Project Chat Pro authors an exact GitHub Atom Contract.
2. Cursor runs preflight against the named contract (local checks plus one
   exact GitHub read under the standing grant).
3. Cursor performs bounded local execution inside the managed write set.
4. Cursor runs targeted validation while iterating and produces a sanitized
   receipt.
5. Cursor may stage, commit, non-force push, create/update the PR, and read CI
   under standing routine authority unless the contract has a stricter stop.
6. One full-gate owner validates the exact candidate: Cursor, Codex, or GitHub
   CI. Delegation uses `FULL_VALIDATION=DELEGATED_TO_CI` plus commit/tree
   identity and is not a blocker.
7. GPT performs semantic acceptance after evidence read-back.
8. Optional bounded repair may continue inside the same atom/envelope when it
   stays within the original objective, managed write set, dependency set,
   authority class, network/cost caps, and rollback boundary; otherwise a new
   contract revision/hash and explicit approval are required.
9. Cursor stops before merge. Codex obtains exact per-PR user confirmation and
   performs merge/read-back.
10. GPT control plane performs canonical reconciliation.

The standing grant supplies routine local write→stage→commit→push→PR/CI
delivery as one envelope. The Atom Contract scopes objective, base, managed
write set, dependencies, caps, rollback, and stricter stops; it does not need
to re-grant each routine step. Provider/API/RPC/WSS, credentials, spend,
package adoption, deploy, wallet/signer/transaction, settings,
force/destructive/history actions, material scope change, and merge remain
excluded or conditional gates.

## Atom Contract minimum fields

One Atom Contract must identify:

- exact repository (`owner/name`);
- exact Issue locator when GitHub-tracked;
- contract `revision`;
- contract content hash (SHA-256 of canonical contract bytes);
- expected base `HEAD` and `tree`;
- authority class or stricter exclusions;
- managed write set;
- stop-before boundaries;
- validation command;
- evidence return channel (Issue comment and/or PR).

## Input route

Read a GitHub-transported Atom Contract only when the current prompt contains:

```text
GITHUB_BATON: <exact contract locator>
```

Rules:

- Reject discovery by newest/last-modified Issue or PR.
- Reject absolute machine paths and parent traversal.
- A trigger scopes the contract; standing project autonomy supplies routine
  delivery unless the contract is stricter.
- `GITHUB_BATON` never implies merge, settings, provider action, material scope
  expansion, or canonical status authority.
- Existing routes `DIRECT_PROMPT`, `LOCAL_HANDOFF`, and
  `ACCEPT_LOCAL_HANDOFF` remain valid and unchanged.
- `GITHUB_BATON` is a live accepted route, not a future, local-dirty,
  pre-merge, or uncommitted candidate description.

## Cursor preflight

Before any mutation, verify:

- repository identity matches the contract;
- branch, `HEAD`, `tree`, and upstream match the expected base;
- worktree dirty state matches the contract requirement (usually clean);
- contract revision and hash match;
- authority/exclusions are valid and compatible with the standing envelope;
- managed write set is non-empty only when local writes are authorized.

### Bounded GitHub read

Standing project autonomy covers one bounded read of the exact repository and
Issue/revision named by `GITHUB_BATON`.

When authorized:

- allow only the minimum `gh issue view`/equivalent read needed to fetch the
  exact contract;
- forbid issue search, issue listing, newest/latest discovery, other repo
  reads, comments, edits, labels, PR writes, push, merge, or settings;
- count and report exact GitHub reads;
- make zero GitHub writes.

If the active contract forbids that read or the standing grant is unavailable,
return `BLOCKED_AUTHORITY`.
On revision/hash mismatch, return `BLOCKED_CONTRACT_MISMATCH`.

No GitHub writes or unbounded/discovery reads. Local preflight makes zero local
writes. Return a sanitized structured result and stop before mutation on any
mismatch.

## Local execution and receipt

When `LOCAL_WRITE` is authorized:

- edit only paths inside the managed write set;
- run targeted checks under `VALIDATION_ECONOMY`;
- produce a sanitized receipt (no secrets, usernames, emails, absolute
  machine paths, tokens, or wallet material);
- continue through routine commit/push/PR/CI delivery unless a stricter stop is
  explicit.

## Internal repair policy

- Repairs that remain inside the original objective, managed write set,
  dependency set, authority class, network/cost caps, and rollback boundary may
  execute within the same atom/envelope.
- No new user transport or contract revision is required for those repairs.
- Material scope change, new authority class, new dependency, new external
  system, changed architecture, or destructive action requires a new contract
  revision/hash and explicit approval.

## Excluded and conditional boundaries

- Cursor never merges; Codex merges only after exact per-PR confirmation.
- Provider/API/RPC/WSS, credentials, spend, deploy, wallet/signer/transaction,
  settings, force/destructive/history operations, material scope change, and
  user-only actions require an exact gate.
- Canonical status changes and `DONE` remain GPT control-plane decisions.

## Deferred surfaces

- MCP
- Cursor Automations
- Cloud Agents as default executors
- Google Drive as primary code/task transport

## Failure and stop conditions

Stop and return `BLOCKED`, `BLOCKED_AUTHORITY`, or
`BLOCKED_CONTRACT_MISMATCH` when identity, revision, hash, base, scope,
write-set, cleanliness, caps, or stricter-stop checks fail; when secrets or
absolute paths appear; or when a step crosses an excluded boundary.
