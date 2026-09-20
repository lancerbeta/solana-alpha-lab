# COHORT_DATA_ROOT_AND_IMPORT_READBACK_V1 — Owner readout

Date: 2026-09-20 · Route: DIRECT_CURSOR_DELIVERY

Program: second atom of owner-path convergence. A3–A5 and the provenance
addendum are not this atom.

## What changed

Publish/import from a linked worktree now lands in the Git principal
checkout `local/factory_v1/data_plane`. After `publish-live-cohort` or
`import-live` the CLI prints one operational `smial.cohort-import-readback`.
An exact already-imported lineage is `PASS_ALREADY_PRESENT_EXACT`.
`forge-control-ready` stays an expert diagnostic.

## Real C1/C2 readback

persist=False against this machine's LIVE CORPUS instance (not a family-global
canonical dataset).

- fingerprint `db5b0dede6936e17c3e35efa25105273a6b85d0305fde24bb7a932dbb3aff572`
- corpus_version **2**
- C1 `REL-20260902T111900Z-20260909T111900Z` count **1**
- C2 `REL-20260909T111900Z-20260916T111900Z` count **1**
- `duplicate_cohort_count=0`, `lineage_integrity=PASS`
- next owner action `STOP_BEFORE_HYPOTHESIS_FORGE`
- `source_sha256` is null: lineage does not carry that field, and
  `content_sha256` is not reused as a substitute

Do not commit current runtime outputs or absolute machine paths.

## What did not change

No Forge run, no A3 visibility receipt, no collector/VPS mutation, no
destructive rollback of imported bytes, no addendum model/reasoning
provenance.

## Residual

Named consumer after merge/readback: A3 `FORGE_INPUT_TRUTH_AND_VISIBILITY_V1`.
`CAPABILITY_RADAR_NOW=NONE`. STOP before owner merge phrase.
