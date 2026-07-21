# AGENTS.md — Solana Alpha Lab repository contract

## MISSION

Implement only the active bounded task that advances the Solana Memecoin
Intraday Alpha Lab toward executable, net-of-cost evidence and eventual
owner cashflow.

## STATUS_OWNERSHIP

ChatGPT Project / Work owns mission, roadmap, task status, acceptance, and
canonical state. Repository agents and Codex may propose status changes in
handoff evidence but must not claim acceptance.

## CURRENT_TASK

TASK-03 — Private repository, controls & Project Asset Catalog.

Current atom: commit-ready patch without commit. The exact baseline is
staged, but commit creation, remote actions, connector permission, and Codex
writes remain prohibited.

## WORKSPACE_ONLY

Operate only inside this repository workspace. Do not read or write
unrelated folders. Machine-specific absolute paths must not enter tracked
files or Catalog metadata.

## NO_SECRETS

Never create, request, display, store, or commit:

- `.env` values;
- API keys, access tokens, passwords, cookies, or private endpoints;
- seed phrases, private keys, wallet recovery data, or signer material;
- credentials in URLs, logs, fixtures, screenshots, or exception traces.

`.env.example` remains placeholder-only. Secret tests construct synthetic
rejection fixtures in memory and contain no usable secret.

## EXTERNAL_ACTIONS

Network access is off by default. No provider/API/RPC call, account
creation, payment, remote creation, push, pull request, connector
permission, VPS action, wallet action, or package adoption without an
explicit Work-approved atom.

## PYTHON_AND_DEPENDENCIES

- Project runtime: uv-managed CPython 3.13.14.
- Runtime range: Python 3.13 only.
- Project environment: `.venv`, never global site-packages.
- Dependency truth: `pyproject.toml` plus `uv.lock`.
- Validation must not update the lockfile.

## LOCAL_QUALITY_GATE

- PowerShell runtime: 7.6.3 Core x64.
- Canonical command:
  `pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1`
- Local Git hook path: `.githooks`.
- `pre-commit` invokes the canonical command.
- Hook bypass is not authorized.

## REPOSITORY_STATES

The quality gate accepts only:

- `COMMIT_READY_STAGED`: unborn `main`, exact approved staged tree, zero
  untracked/unstaged files, zero remotes;
- `COMMITTED_BASELINE`: exactly one root commit, exact approved HEAD tree,
  clean index/worktree, zero remotes.

Any partial staging, additional commit, extra file, unstaged drift, remote,
or non-root first commit fails.

## COMMIT_PROTOCOL

- Atom 2F prepares and fingerprints the commit-ready tree only.
- Atom 2G separately confirms author identity policy and creates the commit.
- The tracked receipt records payload fingerprints, not the future commit
  hash, avoiding a self-referential commit.
- After commit, the same quality gate must report `COMMITTED_BASELINE`.
- The resulting commit hash is external acceptance evidence until the
  transactional TASK-03 living-state handoff.

## DATA_BOUNDARY

Raw and canonical data bytes do not belong in Git. Track only approved
schemas, contracts, sanitized fixtures, manifests, fingerprints, and
evidence.

## CHANGE_PROTOCOL

Before editing:

1. read this file and `docs/tasks/TASK-03.md`;
2. confirm the named atom and allowed files;
3. stop on secrets, unexpected files, broader access, payment, or scope
   expansion.

After editing:

1. run the canonical validation command;
2. inspect staged or committed tree evidence;
3. update `docs/handoffs/latest.md`;
4. do not commit, push, or change canonical status unless explicitly
   authorized.
