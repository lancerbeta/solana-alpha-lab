# Operator navigation

Generated from the active Project Sources release and validated Catalog. Do not edit manually.
This is a short route map, not a second truth owner or a documentation portal.

## Current binding

- Active Project Sources release: `PSR-0003-T28-RC001-FREEZE`
- Owner-smoke receipt: `docs/evidence/task28/a3r2_project_sources_activation_and_task_close_acceptance_v1.json`
- Active task in that release: `TASK-28`
- Bound source roles: `7`
- A local Project Sources mirror is optional diagnostic input; it is never canonical.

## Safe first command

```powershell
uv run --locked --managed-python python -B scripts/show_task34a_context.py --format text
```

To inspect an optional local mirror without printing its path:

```powershell
uv run --locked --managed-python python -B scripts/show_task34a_context.py --format json --sources-dir <local-sources-directory>
```

## Read the result

- `MIRROR_MATCHES_ACTIVE_RELEASE`: the optional bytes agree with the active release.
- `STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED` or `MIRROR_UNAVAILABLE`: use the activated registry/receipt; no automatic repair is needed.
- `MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW`: stop selection and resolve the conflicting Source state before proceeding.
- A `TASK34A_CONTEXT: FAIL` is a release-binding failure, not permission to choose a replacement truth owner.

## Runbooks

- [Start or resume a task](runbooks/task_entry_and_resume.md)
- [Handle Source mirror drift](runbooks/source_mirror_drift.md)
- [Stop at external authority](runbooks/external_authority_stop.md)

## Catalog anchors

- `CATALOG-ROOT-001`
- `GENERATOR-CATALOG-NAVIGATION-001`
- `CTRL-AGENTS-001`

No provider, credential, wallet, transaction, cash, deployment, or Project Sources UI action is performed by these commands.
