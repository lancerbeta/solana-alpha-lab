# FACTORY HOT90 commissioning contract (prepare only)

Status: `PREPARED_NOT_EXECUTED`
As of: `2026-09-05`
Predecessor: `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1` merged to `main`
This document is the next operational atom contract. It does **not** authorize
deploy, Drive write, retention APPLY, SQLite compaction, or live deletion.

Activation default in Git is `CURRENT_SAFE`. Commissioning mutates Factory
runtime only after a later exact owner atom.

## STOP

Do not execute this runbook from the IMPL PR. Do not start cleanup. Do not
start Telegram. Do not delete `BACKUP_*.zip`.

## Required activation boundary

`configs/factory_hot90_archive_activation_v1.yaml`

| Stage | Allowed | Forbidden |
|---|---|---|
| `CURRENT_SAFE` | live SNAPPY + per-publication members + full-RDP local backup | ZSTD HOT writes, SNAPSHOT_PLUS_DELTA, Drive, eviction, compaction |
| `WRITE_ONLY_SHADOW` | new layout/raw/archive generation beside current truth | eviction, SQLite compaction, live delete |
| `DURABILITY_CUTOVER` | immutable archive + mutable-only backup | eviction, compaction |
| `RETENTION_ACTIVE` | only after a separate destructive owner gate | size-only remote proof, mtime age, wildcard delete |

## Commissioning proof on the real VPS (later atom)

Prove, in order, then STOP:

1. deploy/readback exact merged `main`;
2. write-only new layout (`WRITE_ONLY_SHADOW`);
3. one closed UTC-day archive (`ARCHIVE_<sha256>.zip` + `ARCHIVE_MANIFEST.json`);
4. exact remote content SHA256 (`local SHA256 == remote content SHA256`);
5. isolated hydrate into a temporary `data_root` (never `factory_v1`);
6. exact members reconstruction for that day;
7. SQLite integrity;
8. collector/source-poll progression;
9. mutable-only backup restore;
10. no new full-RDP ZIP appears after cutover;
11. actual storage/day readback;
12. live Factory scientific state unchanged.

## Non-claims

Filename, listing, mtime, size, or successful upload never authorize deletion.
`canonical_panel_retention = IMMUTABLE` remains content immutability.
`hot_local_residency_days = 90` is local residency, not a rewrite of IMMUTABLE.
