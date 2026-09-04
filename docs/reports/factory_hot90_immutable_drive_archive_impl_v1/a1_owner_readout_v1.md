# Owner readout — FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1

## Terminal

Repository capability `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1` with HOT
members `SNAPSHOT_PLUS_DELTA`. Production activation remains `CURRENT_SAFE`.
No VPS deploy, Drive write, live delete, retention APPLY, or SQLite compaction
in this atom.

## Entry / outcome

- `DECISION_DELTA`: implement the already-merged #262 architecture behind an
  explicit fail-closed activation boundary.
- `UNCERTAINTY_REMOVED`: reconstruction, ZSTD new-write, raw-plane eligibility,
  archive/hydrate, remote SHA256 primitive, mutable-only backup topology,
  90d residency distinct from IMMUTABLE, fail-closed eviction, 97d runway.
- `CAPABILITY_OR_EVIDENCE`: code + targeted fixture tests + commissioning and
  cleanup contracts prepared, not executed.
- `STOP`: merge gate of this IMPL PR. No commissioning from this handoff.
- `NEXT`: owner merge phrase if merge-readiness `ready_for_owner_phrase=true`.

`SPEC_ROUTE`: `NONE` (PRD already merged)
`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`

## Scientific semantics preserved

- `canonical_panel_retention = IMMUTABLE` keeps content-immutability meaning.
- `hot_local_residency_days = 90` is optional on existing schedules; eviction
  refuses if the field is absent.
- no historical RDP rewrite; no PIT clock regression; no sampling/cadence change.
- SNAPSHOT_PLUS_DELTA reconstructs exact logical member snapshots.
- legacy per-publication `members.parquet` remains readable.

## Production mutations

`PRODUCTION MUTATIONS = 0`
`DRIVE WRITES = 0`
`DELETIONS = 0`
Old ~11.1 GiB `BACKUP_*.zip` is identified for a later cleanup gate and is not
deleted here.

## Next exact step

Owner merge phrase only. Do not start commissioning, cleanup, or Telegram.
