# Owner readout — FACTORY_HOT90_WRITE_ONLY_SHADOW_ACTIVATION_V1

## Terminal

Git-canonical HOT90 stage is `WRITE_ONLY_SHADOW`. New publisher writes use ZSTD
and `SNAPSHOT_PLUS_DELTA`. Drive writes, SQLite compaction, eviction, and backup
durability cutover remain disabled. This PR does not deploy the VPS.

## Entry / outcome

- `DECISION_DELTA`: tracked `configs/factory_hot90_archive_activation_v1.yaml`
  changes `CURRENT_SAFE` → `WRITE_ONLY_SHADOW` with all destructive/Drive flags
  false.
- `UNCERTAINTY_REMOVED`: live publisher will pick up the Git-owned stage after
  a later exact-SHA deploy; no runtime override and no exact-SHA tree edit.
- `CAPABILITY_OR_EVIDENCE`: loader + production-gated refuse tests for
  eviction, compaction, and Drive; CURRENT_SAFE fail-closed retained; legacy
  SNAPPY/per-publication remaining readable.
- `STOP`: merge gate of this activation PR. No deploy from this handoff.
- `NEXT`: after merge, deploy the exact merged SHA and observe real
  `WRITE_ONLY_SHADOW` publications before any durability cutover.

`SPEC_ROUTE`: `NONE`
`MODEL_EFFORT_RECOMMENDATION`: `LUNA_MAX`
`NEXT_MODEL_EFFORT`: `ROUTINE_NO_SWITCH`

## Confirm

- Drive enabled = false
- compaction enabled = false
- eviction enabled = false
