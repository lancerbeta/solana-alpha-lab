# AGENTS.md — Solana Alpha Lab repository contract

## MISSION

Implement only the active bounded task that advances the Solana Memecoin Intraday Alpha Lab toward executable, net-of-cost evidence and eventual owner cashflow.

## STATUS_OWNERSHIP

ChatGPT Project / Work owns mission, roadmap, task status, acceptance, and canonical state. Repository agents and Codex may propose status changes in handoff evidence but must not claim acceptance.

## INPUT_ROUTING

Default: `INPUT=DIRECT_PROMPT`.

- The active task and atom come from the current Work-approved direct prompt or
  an explicitly named local handoff.
- Read local input only when the current prompt contains
  `LOCAL_HANDOFF: <repository-relative path>`.
- Read Work acceptance output only when the current prompt contains
  `ACCEPT_LOCAL_HANDOFF: <repository-relative path>`.
- The validation and path rules for both triggers are defined by
  `docs/agent/HANDOFF_PROTOCOL.md`.
- Never search for the newest, latest, or most recently modified handoff.
- A direct prompt or handoff grants only the authority class it states. It never
  implies commit, push, external action, or canonical status authority.

## WORKSPACE_ONLY

Operate only inside this repository workspace. Do not read or write unrelated folders. Machine-specific absolute paths must not enter tracked files or Catalog metadata.

## NO_SECRETS

Never create, request, display, store, or commit `.env` values, API keys, access tokens, passwords, cookies, private endpoints, seed phrases, private keys, wallet recovery data, or signer material. `.env.example` remains placeholder-only.

## EXTERNAL_ACTIONS

Network access is off by default. No provider/API/RPC call, account creation, payment, remote creation, push, pull request, connector permission, VPS action, wallet action, or package adoption without an explicit Work-approved atom.

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

## CHANGE_PROTOCOL

Read this file and the task/handoff explicitly named by the current prompt,
confirm the bounded atom, run the quality gate, inspect the exact staged or
committed inventory, and do not commit, push, perform another authority class,
or change canonical status unless explicitly authorized. Work owns canonical
status and acceptance.
