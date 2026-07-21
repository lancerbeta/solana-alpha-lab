# Solana Memecoin Intraday Alpha Lab

A bounded, evidence-first research system for executable Solana memecoin alpha on a 15-minute to 4-hour horizon.

## Current repository stage

The accepted local history contains the repository baseline and Project Asset Catalog foundation. The current staged candidate imports exact TASK-01 and TASK-02 pre-Git evidence and registers `ARCH-INTENT-001` without creating a new commit or remote.

```text
HEAD: ee6119ae0b7750710c7f822c50137ed95b4977e9
state: PRE_GIT_IMPORT_STAGED
repository files after import: 58
Catalog assets: 44
Catalog query recipes: 4
Catalog schemas: 3
imported exact bytes: 20
external immutable bundles: 2
bundle-only superseded records: 1
architecture intents: 1
```

## One-command validation

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1
```

The gate validates runtime/lock, repository secrets, Catalog schema and semantics, stable-ID resolution, exact import hashes, provenance and availability, architecture intent boundaries, Git state, EOL policy, receipts, and tests.

## Pre-Git provenance policy

- imported bytes remain historical references with `origin=PRE_GIT`;
- source bundles stay outside Git and are registered by exact SHA-256;
- `first_reliable_available_at` is preserved;
- backfill/import does not create earlier availability;
- exact imported evidence preserves source bytes even when historical formatting includes an extra final blank line; hashes and provenance, not style normalization, govern those files;
- superseded validators remain bundle-only and are not activated;
- current architecture intent is dated 2026-07-21 and is not attributed to earlier tasks.

## Security boundary

Do not place `.env`, credentials, tokens, seed phrases, private keys, raw data, wallet mappings, or machine-specific absolute paths in this repository. No provider call, remote, push, Codex write, or real-money action is authorized by this staged import.
