# FACTORY HOT90 commissioning contract

Status: `PREPARED_NOT_EXECUTED` for Drive archive / durability cutover / cleanup.
As of: `2026-09-05`
Predecessor: `HOT90_RUNTIME_ACTIVATION_BOUNDARY_REPAIR_V1`

This document is the operational commissioning contract. It does **not**
authorize Drive write, retention APPLY, SQLite compaction, or live deletion
by itself. Those still need an exact owner OPERATE gate.

Git YAML is **policy / safe default / validation**, not current host stage.
Current activation on a Factory host is preserved local runtime state.

## Ownership

| Plane | Path | Owns |
|---|---|---|
| Git policy | `configs/factory_hot90_archive_activation_v1.yaml` | allowed stages, fail-closed validation, `CURRENT_SAFE` when no valid runtime file exists |
| Host runtime | `local/factory_v1/hot90_activation_runtime.yaml` | current `activation_stage` and Drive/compaction/eviction flags |
| Machine readback | `scripts/hot90_activation.py show` | actual loader result (`activation_source=RUNTIME` or `GIT_DEFAULT`) |

Ordinary transitions
`CURRENT_SAFE → WRITE_ONLY_SHADOW → DURABILITY_CUTOVER → RETENTION_ACTIVE`
are operational `SET`s. They do **not** require a Git PR unless policy or
implementation changes. The CLI grants no authority. Production stage, Drive
writes and destructive flags still need an exact owner gate before `SET`.

## STOP

Do not start cleanup. Do not start Telegram. Do not delete `BACKUP_*.zip`.
Do not treat tracked YAML as live Factory stage.

## Required activation boundary

Tracked Git default:

```
activation_stage: CURRENT_SAFE
production_compaction_enabled: false
production_eviction_enabled: false
drive_writes_enabled: false
```

Meaning: **SAFE DEFAULT WHEN NO VALID RUNTIME STATE EXISTS.**

| Stage | Allowed | Forbidden |
|---|---|---|
| `CURRENT_SAFE` | live SNAPPY + per-publication members + full-RDP local backup | ZSTD HOT writes, SNAPSHOT_PLUS_DELTA, Drive, eviction, compaction |
| `WRITE_ONLY_SHADOW` | publisher ZSTD + SNAPSHOT_PLUS_DELTA; raw/archive/verify/hydrate/runway remain explicit primitives (no collector auto-run) | eviction, SQLite compaction, live delete, Drive |
| `DURABILITY_CUTOVER` | immutable archive + mutable-only backup | eviction, compaction |
| `RETENTION_ACTIVE` | only after a separate destructive owner gate | size-only remote proof, mtime age, wildcard delete |

`RETENTION_ACTIVE` does not imply eviction. `production_eviction_enabled` must
be explicit `true`.

Loader: valid runtime → use it; runtime absent → Git safe default; runtime
present but invalid, malformed, unsafe or symlink → fail closed, no silent
fallback.

Operator readback:

```
uv run --locked --managed-python python -B scripts/hot90_activation.py show
```

SET is an operational mutation and requires the exact owner gate first. Example continuity file (not a grant):

```
uv run --locked --managed-python python -B scripts/hot90_activation.py set --stage WRITE_ONLY_SHADOW --drive-writes false --compaction false --eviction false
```

## Continuity migration (OPERATE, not this Git PR)

Live host at repair merge is already `WRITE_ONLY_SHADOW`. Sequence:

1. **Before** deploying the repair SHA, write validated runtime state with the
   current live semantics: `WRITE_ONLY_SHADOW`, Drive false, compaction false,
   eviction false. The pre-repair SHA ignores this file (`local/` preserved).
2. Deploy the exact merged repair SHA (`restart=False` exact-SHA, preserve `local/`).
3. New loader reads the preserved runtime file.
4. Readback must prove no behavior transition:
   `WRITE_ONLY_SHADOW` before == `WRITE_ONLY_SHADOW` after.

Do **not** perform that VPS migration from the Git PR.

## Rollback

- Rollback to a pre-repair SHA: runtime file is ignored; old SHA uses its
  tracked config.
- Rollback to repair-or-newer SHA: preserved runtime state remains authoritative.
- Deleting or corrupting the runtime file is not a casual rollback. Corrupt
  runtime fails closed.

## Commissioning proof on the real VPS (later OPERATE atom)

Prove, in order, then STOP:

1. continuity migration readback (`WRITE_ONLY_SHADOW` unchanged);
2. owner-gated runtime `SET` only when moving stage or Drive;
3. one closed UTC-day archive (`ARCHIVE_<sha256>.zip` + `ARCHIVE_MANIFEST.json`);
4. exact remote content SHA256 (`local SHA256 == remote content SHA256`);
5. isolated hydrate into a temporary `data_root` (never `factory_v1`);
6. exact members reconstruction for that day;
7. SQLite integrity;
8. collector/source-poll progression;
9. mutable-only backup restore after `DURABILITY_CUTOVER`;
10. no new full-RDP ZIP appears after cutover;
11. actual storage/day readback;
12. live Factory scientific state unchanged.

Closed-day archive waits until the UTC day is actually closed.

## Non-claims

Filename, listing, mtime, size, or successful upload never authorize deletion.
`canonical_panel_retention = IMMUTABLE` remains content immutability.
`hot_local_residency_days = 90` is local residency, not a rewrite of IMMUTABLE.
Tracked Git YAML is never current production stage.
