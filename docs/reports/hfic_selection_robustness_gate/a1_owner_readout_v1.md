# HFIC_SELECTION_ROBUSTNESS_GATE_V1 — Owner readout

Date: 2026-09-17 · Route: DIRECT_CURSOR_DELIVERY

## What landed

Capability `CAP-HFIC-SELECTION-ROBUSTNESS-GATE-001` exists. It reuses frozen
Stage 1 `CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001` and, only when Stage 1
is `CENSORING_OBSERVED_X_SHIFT_NOT_DETECTED`, runs one L2-logistic
out-of-sample AUC check on the same Block A X300 surface.

The owner-facing field is `router_decision`. Project Chat does not need to
combine Stage-1 and Stage-2 statistics by hand.

This atom does **not** run the canonical LIVE CORPUS OPERATE. Until that later
OPERATE writes `latest.json` on the LIVE CORPUS `--data-root`, ordinary
`/hypothesis-forge` preflight stays as it was. DETECTED / NOT_DETECTED /
INCONCLUSIVE after OPERATE is already a decision, not a reason for another
implementation PR.

## How to score this atom

- **This atom complete** after merge-readiness + owner phrase + guarded merge.
  Task YAML `status: READY` is the contract, not scientific DONE.
- **Canonical OPERATE is out of this atom.** Do not treat synthetic tests as
  the 148/327/475 result.

## Router

| Input | `router_decision` |
| --- | --- |
| Stage 1 DETECTED | `BLOCK_FORGE_SELECTION_RISK` (skip Stage 2) |
| Stage 1 INCONCLUSIVE or invalid | `BLOCK_FORGE_EVIDENCE_GAP` (skip Stage 2) |
| Stage 2 DETECTED | `BLOCK_FORGE_SELECTION_RISK` |
| Stage 2 INCONCLUSIVE | `BLOCK_FORGE_EVIDENCE_GAP` |
| Stage 2 NOT_DETECTED | `FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT` |

`FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT` allows ordinary Forge while residual
unmeasured-selection uncertainty stays a limitation. It does not prove
identification, MAR, ignorability, or MNAR.

## Forge consumption (after OPERATE)

No `latest.json` → ordinary preflight unchanged, including
`SEARCH_BUDGET_EXHAUSTED`. The selection seam does not rewrite that STOP.

Present but unusable `latest.json` (symlink, directory/non-file, unreadable
UTF-8, JSON/hash/schema invalid) → new-session preflight STOPs as
`BLOCK_FORGE_EVIDENCE_GAP`.

Applicable BLOCK → new-session preflight STOPs. Primary fields are
`action=STOP`, `terminal=<router_decision>`, `router_decision`, and
`next=DO_NOT_START_FORGE_UNTIL_SELECTION_GATE_ALLOWS`. This includes
`preflight --control-current-representation`. Resume paths stay unchanged.

Applicable caveat → new-session preflight continues, but the receipt still
shows top-level `router_decision=FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT`. That
is a limitation, not a cleared identification result. Existing HFIC sessions
are not quarantined.

## Operator command (after merge; not this atom)

Canonical OPERATE uses parent `--data-root` on the imported LIVE CORPUS, never
Observation RDP. Bind FAIL does not fall back to parquet. Empty invocation
fails as `CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED`. Mixing
`--data-root` with `--census`/`--observations` fails as
`CANONICAL_MODE_EXPLICIT_PATH_CONFLICT`.

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <LIVE_CORPUS_data_root> selection-robustness-gate
```

Read `router_decision` first. Then `stage1_terminal`, `stage2_status`,
`stage2_terminal`, `oof_roc_auc`, and `permutation_p`.

Explicit parquet:

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py selection-robustness-gate --census <census.parquet> --observations <observations.parquet>
```

That path stays noncanonical and does **not** write `latest.json`, so Forge
preflight will not consume it.

Forge consumption needs the same `--data-root` as OPERATE. Do not auto-run
Forge from the gate command.

## Non-claims

- NO_MAR
- NO_IGNORABILITY
- NO_IDENTIFIABILITY
- NO_RANDOM_SAMPLE_CERTIFICATION
- NO_MNAR
- NO_ALPHA
- NO_CAUSAL_MECHANISM
- NO_MARKET_HYPOTHESIS_VALIDITY
- NO_Y_POINT_READ
- NO_CANONICAL_ACTIVE_RDP_RUN_THIS_ATOM
- NO_LIVE_CORPUS_GATE_THIS_ATOM
