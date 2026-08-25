# Operator navigation

Generated from the validated Catalog, canonical bindings and Delivery Harness. Do not edit manually.
This is a short route map, not a second truth owner or a documentation portal.

## Active Git discovery

Project Sources release and owner-smoke receipts are not the active discovery path.

1. Exact known Catalog ID:

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-asset <ASSET_ID> --json
```

2. Current semantic root (`resolve-binding`):

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-binding ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY --json
```

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-binding ACTIVE-FACTORY-MARKET-FEATURE-SURFACE --json
```

Canonical bindings at this commit:

- `ACTIVE-FACTORY-MARKET-FEATURE-SURFACE` → `CONFIG-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY` → `CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010` (`CURRENT_AT_COMMIT`)

3. Concept search:

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py search-assets --text <QUERY> --match all --limit 20 --explain --json
```

4. Declared Catalog relations (`related-assets`, depth at most 2, `authority_inferred: false`):

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py related-assets <ASSET_ID> --depth 2 --direction both --json
```

5. Prior work is `PARTIAL_COVERAGE` in this atom. Use recipe `QUERY-T16-PRIOR-WORK-001` only after substituting its documented parameters. The `prior-work-references` command is not implemented.

6. Task execution context:

```powershell
uv run --locked --managed-python python -B scripts/delivery_harness.py check
```

```powershell
uv run --locked --managed-python python -B scripts/delivery_harness.py context --route DIRECT_CURSOR_DELIVERY --task-id <TASK_ID> --contract <CONTRACT_PATH> --json
```

7. Exhaustive browsing: generated [`PROJECT_MAP.md`](PROJECT_MAP.md).

## Historical / optional Project Sources

The following is optional owner-managed export diagnostics. It is not the Git discovery path.

- Historical Project Sources release: `PSR-0003-T28-RC001-FREEZE`
- Owner-smoke receipt: `docs/evidence/task28/a3r2_project_sources_activation_and_task_close_acceptance_v1.json`
- Historical task in that release: `TASK-28`
- Bound source roles: `7`
- A local Project Sources mirror is optional diagnostic input; it is never canonical.

```powershell
uv run --locked --managed-python python -B scripts/show_task34a_context.py --format text
```

To inspect an optional local mirror without printing its path:

```powershell
uv run --locked --managed-python python -B scripts/show_task34a_context.py --format json --sources-dir <local-sources-directory>
```

- `MIRROR_MATCHES_ACTIVE_RELEASE`: the optional bytes agree with the historical release.
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
- `QUERY-CATALOG-SEARCH-ASSETS-001`
- `QUERY-T16-PRIOR-WORK-001`

No provider, credential, wallet, transaction, cash, deployment, or Project Sources UI action is performed by these commands.
