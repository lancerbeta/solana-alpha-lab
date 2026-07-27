# AGENTS.md — Solana Alpha Lab repository contract

## MISSION

Implement only the active bounded task that advances the Solana Memecoin Intraday Alpha Lab toward executable, net-of-cost evidence and eventual owner cashflow.

## STATUS_OWNERSHIP

The GPT control plane owns canonical mission, roadmap, task status, acceptance, and
canonical state. The elected owning ChatGPT Project GPT control plane surface is:

- Project Work when `LOCAL_WORK_CODEX` is selected;
- Project Chat Pro when `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` is selected.

Repository agents and Codex may propose status changes in handoff evidence but
must not claim acceptance. Cursor is always `EXECUTION_ONLY`: it never selects
the current or next canonical task, never declares DONE, and never infers
authority from an Issue, PR, commit, tests, or files alone.

## STANDING_PROJECT_AUTONOMY

The goal owner granted a durable project-local autonomy envelope on 2026-07-28.
Within the active objective and this repository, Codex and Cursor may proceed
without a new approval for:

- read-only inspection, official-document verification, calculations, and
  validation;
- bounded local writes, refactoring, Catalog maintenance, generated consumers,
  routine repair, tests, and exact staging;
- exact Atom Contract Issue creation/update/read-back by the GPT control plane,
  exact named-Issue receipt comments by an executor, task branches, ordinary
  commits, Git fetch/read-back, non-force push to a task branch, and creation
  or update of a pull request;
- routine implementation choices whose alternatives do not materially change
  the estimand, scope, cost, data contract, or safety boundary.

This is an explicit standing grant across the listed authority classes, not
authority inferred from a file, commit, Issue, PR, or passing test. A stricter
active-task contract, exact write set, offline requirement, cap, or stop
condition still wins. Cursor receives the objective and bounded scope from the
active direct prompt, handoff, or baton; the standing grant supplies routine
execution classes and necessary direct test, Catalog, hash, and generated
consumers. It does not let Cursor select a task, widen product semantics, or
claim canonical acceptance or `DONE`.

Codex performs a final pull-request merge only after the goal owner gives an
explicit confirmation for that exact PR immediately before the merge. The
confirmation is the gate; it is not an instruction for the user to click the
merge button. Without that per-PR confirmation, stop before merge.

The standing grant does not authorize force push, history rewrite, destructive
cleanup, branch deletion, repository or account settings, credentials or
secrets, provider/API/RPC/WSS execution, purchases, deployment,
wallet/signer/transaction actions, real money, or any action that only the user
can complete. Those remain explicit user gates. If an ordinary step exposes one
of these boundaries, stop only at that boundary and return the smallest
concrete user action.

## LANGUAGE_AND_REPORTING

User-facing communication defaults to Russian. Keep code, paths, schema keys,
protocol labels, enums, product names, and machine-readable JSON/YAML in their
canonical form; explain exact English errors in Russian. This is a
project-scoped reporting rule only—it grants no task authority or action
permission.

## INPUT_ROUTING

Default: `INPUT=DIRECT_PROMPT`.

- The active task and atom come from the current GPT-control-plane-approved
  direct prompt or an explicitly named local handoff.
- Read local input only when the current prompt contains
  `LOCAL_HANDOFF: <repository-relative path>`.
- Read Work acceptance output only when the current prompt contains
  `ACCEPT_LOCAL_HANDOFF: <repository-relative path>`.
- Read a GitHub-transported Atom Contract only when the current prompt contains
  `GITHUB_BATON: <exact contract locator>` and the contract is validated under
  `docs/agent/GITHUB_BATON_PROTOCOL.md`. `GITHUB_BATON` is a live accepted
  input route for `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR`; it grants no implicit
  Issue/PR write, commit, push, or status authority. Those routine actions are
  authorized only by the explicit standing grant above or a stricter direct
  user instruction.
- Local handoff validation and path rules are defined by
  `docs/agent/HANDOFF_PROTOCOL.md`.
- Execution-route selection among `GPT_ONLY`, `LOCAL_WORK_CODEX`, and
  `PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR` is defined by
  `docs/agent/EXECUTION_ROUTER_PROTOCOL.md`.
- Never search for the newest, latest, or most recently modified handoff.
- A direct prompt, handoff, baton, or standing grant defines the applicable
  authority envelope. Never infer a broader envelope from an Issue, PR,
  commit, tests, or files alone.

## WORKSPACE_ONLY

Operate only inside this repository workspace. Do not read or write unrelated folders. Machine-specific absolute paths must not enter tracked files or Catalog metadata.

## NO_SECRETS

Never create, request, display, store, or commit `.env` values, API keys, access tokens, passwords, cookies, private endpoints, seed phrases, private keys, wallet recovery data, or signer material. `.env.example` remains placeholder-only.

## EXTERNAL_ACTIONS

GitHub transport covered by `STANDING_PROJECT_AUTONOMY` may be used for exact
Atom Contract Issue creation/update/read-back, exact named-Issue receipt
comments, ordinary fetch, non-force task-branch push, pull-request work, CI
read-back, and routine review interaction. It does not authorize unrelated
Issue discovery or account/repository-wide mutation. Public official
documentation may be read when it changes a decision. Provider/API/RPC/WSS
execution, account or repository settings, payment, remote creation, connector
permission changes, VPS actions, package adoption, deployment,
wallet/signer/transaction actions, and any other external side effect remain
separately gated.

## PRE_GIT_PROVENANCE

- Exact imported bytes live under `docs/evidence/pre_git/`.
- Source completion bundles stay outside Git and are registered by exact SHA-256.
- Every imported record preserves origin task, source path, legacy ID where available, creation date, `first_reliable_available_at`, retention, and named consumers.
- Import/backfill never creates past availability.
- Exact imported evidence is content-addressed and exempt from style normalization; repository-authored files remain subject to whitespace diff checks.
- Bundle-only superseded code must not become active code.
- `ARCH-INTENT-001` is current user-owned direction from 2026-07-21, not historical TASK-01/02 evidence.

## ARCHITECTURE_INTENT_BOUNDARY

External context such as AOT/ALBS is advisory only. It must carry as-of, first-reliable-availability, TTL, revision, hash, confidence/calibration, lineage, evidence, and allowed-consumer fields. It cannot directly command a bot and cannot bypass risk, execution, inventory, holdout, or economics gates.

## VALIDATION_COMMAND

Platform-neutral gate:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py
```

Windows compatibility wrapper:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1
```

## VALIDATION_ECONOMY

- During implementation, run the smallest targeted checks for the changed
  behavior and direct consumers.
- Use one full-gate owner per exact candidate fingerprint: Cursor locally,
  Codex validation, or GitHub CI. Do not repeat the full gate after staging,
  commit, or publication when the candidate and environment are unchanged.
- When the route guarantees full validation on the same pushed head, Cursor may
  return targeted evidence plus `FULL_VALIDATION=DELEGATED_TO_CI`, then read
  back CI when transport is available. Delegation is not a blocker.
- Re-run a failed check only after its root cause changed; re-run a passed full
  gate only when the candidate fingerprint, dependencies, relevant runtime, or
  validation policy changed.
- Catalog, generated-view, security, and topology checks apply when their owner
  or consumer changed; read-only work does not trigger repository validation.

## CHANGE_PROTOCOL

Read this file and the task/handoff explicitly named by the current prompt,
confirm the bounded objective, apply `VALIDATION_ECONOMY`, inspect the exact
staged or committed inventory, and use the standing autonomy envelope without
pausing for routine microsteps. Cursor stops before merge; Codex merges only
after exact per-PR confirmation. Do not cross a stricter task cap, perform an
excluded authority class, or change canonical status. The GPT control plane
owns canonical status and acceptance.
