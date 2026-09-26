# FORGE_GROUNDED_DISCOVERY_REPAIR_V1 — Owner readout

Date: 2026-09-26 · Route: DIRECT_CURSOR_DELIVERY · MODEL_EFFORT: `SOL_XHIGH`

Ordinary `/hypothesis-forge` no longer turns a fresh focus into CONTROL.
Explicit `--control-current-representation` stays trajectory-blind.
`NORMALIZED_TRAJECTORY_V1` triggers are unchanged. AUTO was not released.
Market Prompt A, Critic, and experiments were not run.

## What changed

- Fresh ordinary `forge-run` returns `START_BASE` with
  `ORDINARY_DISCOVERY_READY` and
  `evidence_surface_mode=ORDINARY_GROUNDED_DISCOVERY_V1`.
- `CONTROL_SURFACE_REQUIRED` remains only for explicit CONTROL when no CONTROL
  session matches.
- A CONTROL `SEARCH_EXHAUSTED` readout says
  `scope_exhausted: CURRENT_REPRESENTATION_CONTROL_V1` and
  `raw ordinary discovery NOT_RUN`.
- Discovery contract `FORGE_GROUNDED_DISCOVERY_V1` admits only
  `EXPLORATORY_REUSE` on `DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001`,
  population `BASE_X`, fields price and liquidity. Ambiguous role stops before
  a value read. Cohort id is not a feature. Target point must be after the
  decision points. Missing outcomes are not zeros. The engine does not emit
  alpha.
- Look budget: 6 main query specs, 2 adaptive refinements. Identical spec
  bytes are a retry.
- Draft minimum is 0 candidates, maximum 6. Critic packets may carry
  `grounded_evidence`. A scoped CONTROL negative does not block a different
  raw question. An exact scope match still does.

## No-write live coverage

`scientific_writes=0`. `typed_value` was not selected.

| Cohort | base_x-like | joint X300 price+liquidity | prefix through Y1800 |
|---|---:|---:|---:|
| `REL-20260902T111900Z-20260909T111900Z` | 475 | 475 | 332 |
| `REL-20260909T111900Z-20260916T111900Z` | 249 | 249 | 128 |
| `REL-20260914T173510Z-20260921T173510Z` | 425 | 425 | 342 |

First supported scope: `X300_PRICE_LIQUIDITY_BASELINE` and
`PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800`.
Excluded: `TRADERS_COMPLETE_PREFIX`.
No-write ordinary focus `COHORT_STRATIFIED_LIFECYCLE_PATHS`:
`next_action=START_BASE`, stage `ORDINARY_DISCOVERY_READY`,
`control_session_id=NONE`, writes 0. It would consume one remaining
distinct-focus slot only if a later slash persists a session.

## After merge

```text
/hypothesis-forge
```

with focus:

```text
OWNER_FOCUS=COHORT_STRATIFIED_LIFECYCLE_PATHS
```

Expected scope: `ORDINARY_GROUNDED_DISCOVERY_V1`, not CONTROL, not V1.
That slash is a separate owner authorization. This PR does not run it.

Rollback: ordinary revert of this PR. Historical ResearchStore rows stay.
The occupied AUTO slot stays occupied.
