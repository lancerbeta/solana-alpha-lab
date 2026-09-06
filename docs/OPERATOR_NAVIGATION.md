# Operator navigation

Generated from the validated Catalog, semantic operability projection, canonical bindings and Delivery Harness. Do not edit manually.
This is a short route map, not a second truth owner or a documentation portal.

## Active Git discovery

Project Sources release and owner-smoke receipts are not the active discovery path.

1. Product or capability question → semantic routes (`docs/FACTORY_SEMANTIC_MAP.md`):

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py search-routes --text "<NEED>" --limit 5 --explain --json
```

2. Known semantic route → resolve route:

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-route <SEMANTIC_ROUTE_ID> --json
```

3. Exact known Catalog ID:

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-asset <ASSET_ID> --json
```

4. Current root (`resolve-binding`):

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-binding <BINDING_ID> --json
```

Canonical bindings at this commit:

- `ACTIVE-EXPERIMENT-CAPABILITY-REGISTRY` → `CONFIG-EXPERIMENT-CAPABILITY-REGISTRY-V2-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-FACTORY-MARKET-FEATURE-SURFACE` → `CONFIG-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-FACTORY-OPERATIONAL-READINESS` → `CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-FACTORY-REMOTE-OPERATIONS` → `CONFIG-FACTORY-REMOTE-OPERATIONS-V1-1-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-FACTORY-SEMANTIC-OPERABILITY` → `CONFIG-FACTORY-SEMANTIC-OPERABILITY-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-HYPOTHESIS-FORGE` → `CONFIG-HYPOTHESIS-FORGE-INDEPENDENT-CRITIC-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-LIFECYCLE-COLLECTOR` → `DOC-FACTORY-LIFECYCLE-COLLECTOR-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-LIVE-LIFECYCLE-EVIDENCE` → `MODULE-LIVE-COHORT-DISCOVERY-RELEASE-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-OWNER-LIFECYCLE-PROJECTION` → `CONFIG-OWNER-LIFECYCLE-PROJECTION-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY` → `CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010` (`CURRENT_AT_COMMIT`)
- `ACTIVE-RESEARCH-LIFECYCLE-WORKBENCH` → `DOC-RESEARCH-LIFECYCLE-WORKBENCH-001` (`CURRENT_AT_COMMIT`)
- `ACTIVE-SMIAL-VISUAL-OPERATING-SYSTEM` → `CONFIG-SMIAL-VISUAL-OPERATING-SYSTEM-001` (`CURRENT_AT_COMMIT`)

5. Concept search:

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py search-assets --text <QUERY> --match all --limit 20 --explain --json
```

6. Declared Catalog relations (`related-assets`, depth at most 2, `authority_inferred: false`):

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py related-assets <ASSET_ID> --depth 2 --direction both --json
```

7. Prior work — current registered query recipes (historical T16 remains valid):

- `QUERY-HFIC-EXACT-RELATED-PRIOR-001` — Find exact definition matches and component-overlap related HFIC prior work without scanning the repository.
- `QUERY-HYPOTHESIS-FAST-LANE-SEARCH-PRIOR-WORK-001` — Search bounded prior Fast Lane work from the DuckDB research projection at an explicit as-of cutoff.
- `QUERY-HFIC-SESSION-BY-SEARCH-KEY-001` — Look up an HFIC session by evidence epoch, focus and prompt search key.
- `QUERY-HFIC-PENDING-SESSION-001` — Find a resumable pending HFIC session for the current evidence epoch and focus.
- `QUERY-T16-PRIOR-WORK-001` — Search the exact offline TASK-16 fixture or TASK-17 production hypothesis research memory at an explicit point-in-time cutoff for reusable prior work without automatic rejection or promotion.

```powershell
uv run --locked --managed-python python -B scripts/catalog_cli.py resolve-query <RECIPE_ID> --json
```

8. Exact task execution context:

```powershell
uv run --locked --managed-python python -B scripts/delivery_harness.py check
```

```powershell
uv run --locked --managed-python python -B scripts/delivery_harness.py context --route DIRECT_CURSOR_DELIVERY --task-id <TASK_ID> --contract <CONTRACT_PATH> --json
```

9. Exhaustive browsing fallback only: generated [`PROJECT_MAP.md`](PROJECT_MAP.md).

10. Historical / optional Project Sources diagnostics (not the discovery path).

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
- `CONFIG-FACTORY-SEMANTIC-OPERABILITY-001`
- `QUERY-CATALOG-SEARCH-ASSETS-001`
- `QUERY-HFIC-EXACT-RELATED-PRIOR-001`
- `QUERY-T16-PRIOR-WORK-001`

No provider, credential, wallet, transaction, cash, deployment, or Project Sources UI action is performed by these commands.
Semantic routing never grants authority (`authority_granted = false`).
