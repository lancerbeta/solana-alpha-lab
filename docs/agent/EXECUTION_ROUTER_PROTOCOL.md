# Execution Router Protocol

Beginner-safe routing among three execution routes. Canonical control remains
with the GPT control plane. Skills are helper procedures, not control owners.

## GPT control plane

The GPT control plane is the elected owning ChatGPT Project surface:

- Project Work when `LOCAL_WORK_CODEX` is selected;
- Project Chat Pro when `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` is selected.

For `GPT_ONLY`, the active Project surface that authored the iteration remains
the control plane. Cursor is always `EXECUTION_ONLY`.

Related:

- `AGENTS.md` — repository contract and input routes
- `docs/agent/HANDOFF_PROTOCOL.md` — local Work↔Codex handoff
- `docs/agent/GITHUB_BATON_PROTOCOL.md` — live GitHub Atom Contract baton
- `docs/decisions/ADR-003-gpt-executor-routing.md` — accepted repository routing ADR

## Control-plane ownership

The GPT control plane owns:

- task selection and roadmap order;
- research, analysis, architecture, and strategy design;
- route selection among the three routes below;
- semantic acceptance and repair decisions;
- canonical status and `DONE`.

Cursor, when used, is always `EXECUTION_ONLY`. It executes only an explicitly
scoped bounded objective. `AGENTS.md` standing project autonomy supplies routine
execution classes, including an exact named-Issue receipt comment; the active
prompt, handoff, or baton supplies scope and any stricter stops. Cursor never
selects the current or next canonical task, never declares `DONE`, never
creates or discovers unrelated Issues, and never infers scope from an Issue,
PR, commit, tests, or files alone.

## Three routes

### 1. `GPT_ONLY`

GPT performs research, analysis, architecture, strategy, and validation.
No execution agent is created when repository mutation is unnecessary.

Use when the iteration is design/review only, or when the answer does not
require local file changes, Git evidence, or executor tooling.

### 2. `LOCAL_WORK_CODEX`

Project Work with the local repository remains the control plane.
Work may execute directly or use the existing bounded Work↔Codex handoff under
`docs/agent/HANDOFF_PROTOCOL.md`.

Preserved input routes:

- `DIRECT_PROMPT`
- `LOCAL_HANDOFF`
- `ACCEPT_LOCAL_HANDOFF`

### 3. `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR`

Project Chat Pro remains the primary control plane
(`CONTROL_PLANE=PROJECT_CHAT_PRIMARY`). GitHub is `TRANSPORT_AND_AUDIT` for a
revision-locked, content-addressed Atom Contract. Cursor is `EXECUTION_ONLY`
and executes only that exact atom, returning evidence through an Issue comment
or PR under standing routine authority unless the contract is stricter. The GPT
control plane may create/update/read back the exact Atom Contract Issue under
the same standing grant.

Live accepted input route:

- `GITHUB_BATON`

`GITHUB_BATON` is a live accepted route for this repository control contract. It
is not a future-only, local-dirty, pre-merge, or uncommitted candidate description.
The baton machine layer is committed on `main` and used through exact Issue
transport with out-of-band hash trust. Canonical Project Sources reconciliation
and roadmap `DONE` remain GPT-owned and may still be pending. MCP and Cursor
Automations remain deferred.

## Routing criteria

| Situation | Route |
|---|---|
| No repository mutation needed | `GPT_ONLY` |
| Local Work/Codex can complete a bounded atom safely | `LOCAL_WORK_CODEX` |
| Revision-locked GitHub-transported atom + Cursor execution needed | `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` |

Prefer `GPT_ONLY` whenever an executor adds no evidence value. Not every
project iteration creates an executor.

## When no executor is created

Do not create Cursor, Codex, Cloud Agent, Automation, or MCP executor when:

- the work is research/design/acceptance only;
- the managed write set would be empty;
- authority class is read-only and no local evidence package is required;
- route switching has not been explicitly authorized by the control plane.

## Authority boundaries

Every authorized atom must state:

- exact repository identity;
- bounded objective and initial managed write set;
- expected base revision when mutation is allowed;
- network/cost/dependency caps and stop-before boundaries.

The prompt, handoff, or baton scopes the objective. `STANDING_PROJECT_AUTONOMY`
supplies routine local write, direct propagation, test, stage, commit,
exact Atom Contract Issue creation/update/read-back by the GPT control plane,
exact named-Issue receipt comments by the executor, fetch/read-back, non-force
task-branch push, PR/review, and CI classes. A stricter contract wins. Cursor
may add only direct tests, Catalog/hash records, and generated consumers
necessary to keep the scoped change valid, and must report the final exact
inventory.

Provider/API/RPC/WSS, credentials, spend, package adoption, deploy, wallet,
signer, transaction, real money, settings, force/history rewrite, destructive
cleanup, branch deletion, material product/architecture scope, and user-only
actions remain owner-attention gates. Evaluate `OWNER_ATTENTION_GATE` from
`control/owner_attention_gate_v1.yaml` before asking the user or merging.
`LOCAL_WORK_CODEX` allows Codex ordinary merge only after all exact-head
machine preconditions pass. Cursor never merges; the
`PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` route has no Codex auto-merge grant.

Cursor never:

- chooses TASK-XX or CTRL-XX as “next”;
- activates canonical Project Sources in the cloud UI or represents a
  repository candidate as activated truth;
- widens product semantics or adds unrelated truth owners;
- performs network/provider/RPC calls without an explicit
  GPT-control-plane-approved atom.

## Project Sources release control

At Entry Gate, read `docs/project_sources/release_registry_v1.yaml` before
relying on a repository-authored Source release. At Finish Gate, a changed
acceptance receipt must declare exactly one project-Sources disposition:
`NO_CHANGE`, `RELEASE_CANDIDATE` or `ACTIVATION_RECEIPT`.

Only a registered candidate under `docs/project_sources/releases/` may be
prepared by the repository route. The owner separately replaces cloud UI
roles and returns the manifest-first seven-role smoke. A PR, merge or CI run
does not activate cloud Project Sources.

## Validation ownership

Use targeted checks while iterating. Elect one full-gate owner for the exact
candidate fingerprint: Cursor, Codex, or GitHub CI. When CI is guaranteed on
the same pushed head, Cursor may report targeted evidence and
`FULL_VALIDATION=DELEGATED_TO_CI`; do not duplicate the full gate merely because
the same bytes were staged, committed, pushed, or placed in a PR.

## Route switching rules

- Route changes require an explicit control-plane decision in the active prompt
  or named handoff/baton.
- Silent mid-task ownership transfer is forbidden.
- Switching from `GPT_ONLY` to an executor requires a bounded objective and
  scope; routine classes come from standing project autonomy.
- Switching into `GITHUB_BATON` requires a new Atom Contract revision and hash
  when material terms change.
- Skills such as start/finish helpers may advise; they do not own routing or
  canonical status.

## Beginner-safe startup model

1. Read `AGENTS.md`.
2. Identify the active input route from the current prompt only.
3. Confirm the route, objective, scope, caps, and stricter stops.
4. If `GPT_ONLY`, stop after analysis; create no executor.
5. If local handoff, follow `HANDOFF_PROTOCOL.md` path rules exactly.
6. If GitHub baton, follow `GITHUB_BATON_PROTOCOL.md` preflight before any write.
7. Execute the named atom through routine delivery; stop only at a stated or
   excluded boundary.

## Failure and stop conditions

Stop without mutation when:

- repository identity, branch, HEAD/tree, or upstream mismatch expected base;
- worktree is dirty before a mutation atom that requires clean state;
- contract hash, revision, objective, caps, or scope is missing/invalid;
- managed write set is absent or would be exceeded;
- secrets, absolute machine paths, or out-of-workspace paths appear;
- GitHub action is outside standing routine transport or violates a stricter
  contract; provider/credentialed network action lacks an exact gate;
- acceptance or `DONE` is requested from an execution-only agent.

On stop, return `BLOCKED` with exact observed versus expected facts. Do not
guess the next task.
