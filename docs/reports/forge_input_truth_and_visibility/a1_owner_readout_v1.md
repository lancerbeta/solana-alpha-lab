# FORGE_INPUT_TRUTH_AND_VISIBILITY_V1 — Owner readout

Date: 2026-09-20 · Route: DIRECT_CURSOR_DELIVERY

Program: third atom of owner-path convergence. A4–A5 and the provenance
addendum are not this atom.

## What changed

One canonical `build_forge_input_receipt` builder now owns scientific
input/visibility. Actual HFIC preflight attaches that receipt. CONTROL
`forge-control-ready` is an adapter over the same builder plus operational
extras. Historical C1 selection calibration stays a scoped caveat against
its own frozen inputs; a later C2 cumulative `dataset_manifest_id` does not
make that receipt `integrity_invalid`. Ordinary packet selection keeps a
protected LIVE CORPUS slot.

Owner classes are `FORGE_INPUT_READY`, `INPUT_NOT_READY`, and
`OBSERVABILITY_BLOCKED`. There is no `NO_WORTHY` on this surface.
`forge-input --no-write` never starts a session.

## Real C1/C2 no-write acceptance

persist=False against this machine's LIVE CORPUS instance.

- `forge_runnable=true`
- corpus_version **2**
- visible cohorts: `REL-20260902T111900Z-20260909T111900Z`,
  `REL-20260909T111900Z-20260916T111900Z`
- historical C1 `FULL_LIFECYCLE_COMPLETENESS` integrity **PASS**
  (`BLOCK_FORGE_SELECTION_RISK` remains a caveat, not a rewrite)
- `pit_semantics` / `missingness_visible` / `feature_grounding` are
  **NOT_EVALUATED** (packet membership is not a PIT probe)
- owner `next` when runnable: `STOP_BEFORE_SYNTHESIS` (not slash)
- writes: research_store 0, forge_context 0, session 0
- receipt_sha256 `6749ca0347cb5745c0759e8f354725ca9a713c1682aefd38c0c99349fb9ad675`

Do not commit current runtime outputs or absolute machine paths.

## What did not change

No `/hypothesis-forge`, Prompt A/B/C, Independent Critic, statistical
diagnostic, V1 scientific probe, commissioning, historical receipt rewrite,
or new trial.

## Residual

Named consumer after merge/readback: A4 `FORGE_REPRESENTATION_LADDER_V1`.
`CAPABILITY_RADAR_NOW=NONE`. STOP before owner merge phrase.
