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

Current atom: Catalog schemas, root resolver, and checkout/EOL repair. Remote
creation, pre-Git import, lifecycle registries, generated project map, and
Codex writes are outside this atom.

## WORKSPACE_ONLY

Operate only inside this repository workspace. Do not read or write
unrelated folders. Machine-specific absolute paths must not enter tracked
files or Catalog metadata.

## NO_SECRETS

Never create, request, display, store, or commit `.env` values, API keys,
access tokens, passwords, cookies, seed phrases, private keys, signer
material, credential URLs, or private endpoints.

## EXTERNAL_ACTIONS

No provider/API/RPC call, account creation, payment, remote creation, push,
connector permission, VPS action, wallet action, or package adoption beyond
the exact Atom 3A dependencies without explicit Work approval.

## PYTHON_AND_DEPENDENCIES

- uv-managed CPython 3.13.14;
- PowerShell 7.6.3 Core x64;
- dependency truth: `pyproject.toml` plus `uv.lock`;
- Atom 3A adopts exact `PyYAML==6.0.3` and `jsonschema==4.26.0` only;
- YAML is loaded only with `yaml.safe_load`;
- JSON Schema references are local; network schema resolution is forbidden.

## PROJECT_ASSET_CATALOG

- root resolver: `catalog/catalog_manifest.yaml`;
- Catalog owns discovery, location, relations, access recipes, and evidence;
- Git/data/runtime/specialized registries own bytes and domain truth;
- stable IDs are immutable once committed;
- raw/canonical bytes never enter Catalog metadata;
- secrets and absolute paths fail validation;
- missing mandatory output is `CATALOG_GAP`;
- self-referential Catalog files are bound by accepted commit/tree evidence,
  not by embedding their own hash;
- generated views are regenerated later, never hand-edited;
- graph database remains deferred until measured need.

## TEXT_AND_CHECKOUT_CONTRACT

- tracked text uses LF;
- `*.ps1` is explicitly `text eol=lf`;
- `*.bat` and `*.cmd` remain `text eol=crlf`;
- do not change global `core.autocrlf` for this project;
- the quality gate must verify `.gitattributes`, working-tree bytes,
  staged/committed blobs, cached and working-tree attributes, and a temporary
  checkout roundtrip before commit or clean-clone acceptance.

## LOCAL_QUALITY_GATE

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1
```

Atom 3A-R accepts exactly:

- `CATALOG_FOUNDATION_STAGED`: baseline commit remains HEAD and the exact
  Catalog plus EOL-repair candidate is staged;
- `CATALOG_FOUNDATION_COMMITTED`: a later exact second commit contains the
  same payload and a clean working tree.

## CHANGE_PROTOCOL

1. Read this file and `docs/tasks/TASK-03.md`.
2. Resolve relevant assets through the Catalog, not filename guessing.
3. Run the canonical quality gate.
4. Do not commit, push, connect GitHub, import pre-Git bundles, or give Codex
   write access unless the active atom explicitly authorizes it.
