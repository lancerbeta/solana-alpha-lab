---
handoff_status: WORKING_CHECKPOINT
task_id: TASK-03
atom_id: TASK03-ATOM-3A-R
canonical_status_owner: ChatGPT_Project_Work
accepted_base_commit: "399ef0365b017fcd9d7b81389218a63bf1e466c1"
candidate_commit: NONE
remote: NONE
---

# Latest handoff

## Atom

Catalog schemas, root resolver, and checkout/EOL repair are staged; no Catalog
commit or remote exists.

## Candidate state

- base commit: `399ef0365b017fcd9d7b81389218a63bf1e466c1`;
- repository state: `CATALOG_FOUNDATION_STAGED`;
- total repository files: 32;
- staged Atom 3A-R files: 21;
- untracked and unstaged files: 0;
- remote count: 0.

## Foundation outputs

- `catalog/catalog_manifest.yaml`;
- standalone JSON Schemas for manifest/assets/queries;
- core asset registry and read-only query registry;
- `scripts/validate_catalog.py`;
- `scripts/catalog_cli.py`;
- ADR-001 and deterministic evidence receipt.

## Checkout contract

- `*.ps1 text eol=lf`;
- working-tree and staged PowerShell bytes: LF-only;
- `git check-attr` working/cached results: `lf`;
- temporary `checkout-index` roundtrip: LF-only;
- global Git configuration: unchanged.

## Dependencies

- PyYAML `6.0.3` — exact lock, `safe_load` only;
- jsonschema `4.26.0` — exact lock, Draft 2020-12;
- no additional dependency or network action in Atom 3A-R.

## Deferred

Pre-Git import, generated map/edges, lifecycle registries, private remote,
CI, clean clone, and Codex pilot remain unimplemented.

## Proposed status

No canonical TASK-03 status change is claimed from this staged checkpoint.
