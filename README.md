# Solana Memecoin Intraday Alpha Lab

A bounded, evidence-first research system for executable Solana memecoin
alpha on a 15-minute to 4-hour horizon.

## Current repository stage

TASK-03 is building the private implementation truth layer. The local root
commit is accepted. Atom 3A adds the staged Project Asset Catalog foundation:

- `catalog/catalog_manifest.yaml` as the stable root resolver;
- versioned asset and query registries;
- standalone JSON Schema Draft 2020-12 files;
- deterministic Catalog validator and read-only resolver CLI;
- exact locked dependencies for safe YAML and JSON Schema validation.

Atom 3A-R also repairs the checkout contract before the Catalog commit:

- tracked text is LF;
- PowerShell `.ps1` files are explicitly materialized as LF;
- `.bat` and `.cmd` remain CRLF;
- the quality gate checks working-tree bytes, staged/committed blobs,
  `git check-attr`, and a temporary `checkout-index` roundtrip.

The Catalog foundation is staged but not committed. Pre-Git TASK-01/02 import,
generated project map/edges, lifecycle registries, private remote, CI, clean
clone, and Codex pilot remain unimplemented.

## One-command validation

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1
```

Expected additions:

```text
CATALOG_VALIDATION: PASS
CATALOG_RESOLUTION: PASS
ps1_eol_attribute_worktree: PASS
ps1_eol_attribute_index: PASS
ps1_checkout_roundtrip_lf: PASS
REPOSITORY_STATE: CATALOG_FOUNDATION_STAGED
RESULT: PASS
```

## Catalog usage

```powershell
uv run --locked --managed-python python -B .\scripts\catalog_cli.py list-assets
uv run --locked --managed-python python -B .\scripts\catalog_cli.py resolve-asset CATALOG-ROOT-001 --json
uv run --locked --managed-python python -B .\scripts\catalog_cli.py resolve-query QUERY-CATALOG-VALIDATE-001 --json
```

All commands are local and read-only. Catalog metadata contains no secrets,
raw data bytes, provider credentials, wallet material, or machine-specific
absolute paths.
