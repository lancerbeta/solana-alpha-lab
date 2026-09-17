# HFIC_SELECTION_ROBUSTNESS_GATE_V1 — Owner readout

Date: 2026-09-17 · Route: DIRECT_CURSOR_DELIVERY

## What landed

Ordinary Forge now has one durable post-`NO_WORTHY` selection gate:

`CAP-HFIC-SELECTION-ROBUSTNESS-GATE-001`

It reuses frozen Stage 1 `CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001`
and, only when Stage 1 is `CENSORING_OBSERVED_X_SHIFT_NOT_DETECTED`, runs one
L2-logistic out-of-sample AUC check on the same Block A X300 surface.

The owner-facing field is `router_decision`. Project Chat does not need to
combine Stage-1 and Stage-2 statistics by hand.

This atom does **not** run the canonical LIVE CORPUS OPERATE. A later bounded
OPERATE command is the scientific result. DETECTED / NOT_DETECTED /
INCONCLUSIVE after that run is already a decision, not a reason for another
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

If no gate receipt is in the data root, ordinary Forge preflight is unchanged.
An applicable BLOCK stops **new-session** preflight with the typed decision.
Resume paths stay unchanged. Existing HFIC sessions are not quarantined.

## Operator command (after merge; not this atom)

Canonical OPERATE uses parent `--data-root` on the imported LIVE CORPUS, never
Observation RDP. Explicit parquet paths stay noncanonical.

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <LIVE_CORPUS_data_root> selection-robustness-gate
```

Read `router_decision` first. Then `stage1_terminal`, `stage2_status`,
`stage2_terminal`, `oof_roc_auc`, and `permutation_p`.

Forge consumption: the same `--data-root` must hold
`research/artifacts/hfic_selection_robustness_gate/latest.json`. Do not auto-run
Forge from this command.

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
