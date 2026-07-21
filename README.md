# Solana Memecoin Intraday Alpha Lab

A bounded, evidence-first research system for executable Solana memecoin
alpha on a 15-minute to 4-hour horizon.

## Current control state

- Phase: P0 — Project Control & Source Foundation
- Active task: TASK-03 — Private repository, controls & Project Asset Catalog
- Local branch: `main`
- First commit: not created
- Remote repository: absent
- Provider/API/RPC calls: zero
- Real-money execution: prohibited
- TASK-03 cash cap: USD 0

## Business objective

Build a low-cost, repeatable Alpha Factory whose eventual success criterion
is owner cashflow after trading and infrastructure cash costs. Backtest PnL,
code volume, dataset size, and bot count are not business outcomes.

## Current repository stage

The repository contains a reviewed commit-ready baseline:

- uv-managed CPython 3.13.14 and deterministic `uv.lock`;
- PowerShell 7.6.3 one-command quality gate;
- repository and staged-content secret rejection;
- versioned `.githooks/pre-commit`;
- deterministic payload fingerprints;
- support for validation both immediately before and immediately after the
  first local commit.

The commit itself, remote, CI, Asset Catalog, registry import, and Codex
pilot are not accepted yet.

## One-command validation

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1
```

Supported actual states:

- `COMMIT_READY_STAGED`: no commit exists and the exact approved tree is
  staged;
- `COMMITTED_BASELINE`: exactly one root commit exists and the working tree
  is clean.

The pre-commit hook validates `COMMIT_READY_STAGED`. The same command must
validate `COMMITTED_BASELINE` after the separately authorized commit.

## Commit boundary

Recommended first commit message:

```text
chore: establish local repository baseline
```

Author identity and commit creation remain separate Atom 2G decisions.
The tracked receipt does not contain a commit hash, avoiding self-reference;
acceptance records the resulting hash externally and later in living state.

## Security boundary

Do not place `.env`, credentials, tokens, seed phrases, private keys, raw
data, wallet mappings, or machine-specific absolute paths in this
repository.
