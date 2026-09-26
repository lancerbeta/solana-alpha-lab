# FORGE_GROUNDED_DISCOVERY_REPAIR_V1 — Owner readout

Date: 2026-09-26 · Route: DIRECT_CURSOR_DELIVERY · MODEL_EFFORT: `SOL_XHIGH`

Ordinary `/hypothesis-forge` is no longer a silent CONTROL run.
The ordinary route can compute BASE_X price and liquidity from
production-shaped census and observation rows, store the look, and require
those refs at freeze. Explicit `--control-current-representation` stays
trajectory-blind. V1 triggers are unchanged. AUTO was not released.
Market Prompt A, market Critic, and experiments were not run.

## What the ordinary path does

`discovery-execute` admits role and holdout from the binding document before
it reads row values. It does not default to the live store. BASE_X is
`X_ELIGIBLE` plus PIT X300 liquidity. The target is not an eligibility
filter. Traders completeness is not required. A missing explanatory flag
stays missing. Empty cohorts stay in the table with a zero usable count.
Overlapping collection windows are not independent replication. The result
carries `engine_emits_alpha=false`.

The look is a `RESEARCH_ARTIFACT` of kind `DISCOVERY_QUERY_LOOK`. The same
spec, data binding, and calculation version resume the previous bytes and
do not add a look. A changed binding counts. Freeze rejects a missing ref
and a tampered summary. `NO_WORTHY` keeps the scope record and is not a
raw-corpus negative.

A valid close still blocks the same content on the same surface, including
a renamed `question_id`. A CONTROL negative does not close an unseen richer
ordinary scope. Missing scope axes are unresolved.

Predictive sketches are 0–6 and do not require an actor story. Causal
claims keep the identification bar.

## Synthetic acceptance

Public entry, temporary store, no handwritten summary:

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py discovery-execute --store <explicit-store> --census <census.parquet> --observations <observations.parquet> --binding <binding.json> --spec <spec.json> --candidate-scope <scope.json> --journal-scope <scope> --format json
```

On the synthetic panel the pooled mean is 0 while liquidity-high and
liquidity-low means are +1 and -1. Two calendar blocks are present. One
cohort has denominator 0. A late target is leakage. An ineligible mint
stays out of BASE_X. Live scientific writes and the live focus slot were
not spent.

State-only coverage, still without `typed_value`:

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py discovery-coverage --format json
```

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

Rollback: revert this PR. Historical ResearchStore rows and the occupied
AUTO slot stay.
