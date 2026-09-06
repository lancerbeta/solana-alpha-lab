# FACTORY HOT90 commissioning contract

Status: `ACTIVE_BOUNDARY_CONTRACT`.
Runtime truth: `RUNTIME_STATE_EXTERNAL_READBACK_REQUIRED`.
As of: `2026-09-06`
Predecessor: `HOT90_RUNTIME_ACTIVATION_BOUNDARY_REPAIR_V1`

This document is the Git commissioning **boundary**, not live host status.
It does **not** encode the current VPS activation stage, Drive liveness, or
Telegram liveness. Those require a fresh machine readback.

Retention APPLY, SQLite compaction, and live scientific deletion still need
an exact owner OPERATE gate. Unattended closed-day archive / daily pulse /
incident watch capability lives in
`docs/operator/FACTORY_UNATTENDED_OPERABILITY.md` and is not auto-enabled by
this Git change.

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

Do not treat this Git file as current live stage, current Telegram health, or
current Drive health. Do not start scientific cleanup or `BACKUP_*.zip`
deletion from this document. Do not treat tracked YAML as live Factory stage.
Telegram and closed-day archive **capability** exist in Git; install/enable
and live send remain a later OPERATE gate. Historical commissioning sequence
below is contextual, not a claim that the VPS is in any named stage now.

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

Operator readback on the Factory host (deploy root `/opt/solana-alpha-lab`):

```
uv run --locked --managed-python python -B scripts/hot90_activation.py --root /opt/solana-alpha-lab show
```

After this SHA is live, `activation_source=GIT_DEFAULT` plus `CURRENT_SAFE` is
continuity **FAIL**: missing runtime, new writes would drop to SNAPPY/legacy.
Success is `activation_source=RUNTIME` plus `WRITE_ONLY_SHADOW`.

SET is an operational mutation on the host named by `--root`. The CLI grants
no authority. Continuity SET below preserves already-live `WRITE_ONLY_SHADOW`;
it is still an OPERATE mutation and needs the exact owner gate first. It is
not a stage move. Do not run it against a workstation checkout.

```
uv run --locked --managed-python python -B scripts/hot90_activation.py --root /opt/solana-alpha-lab set --stage WRITE_ONLY_SHADOW --drive-writes false --compaction false --eviction false
```

## Continuity migration (OPERATE, not this Git PR)

Owner-reported live host before this repair is `WRITE_ONLY_SHADOW`. This Git
PR does not re-prove that host fact. Sequence:

1. **Before** deploying the repair SHA, on the Factory host write validated
   runtime state with the current live semantics: `WRITE_ONLY_SHADOW`, Drive
   false, compaction false, eviction false. The pre-repair SHA ignores this
   file (`local/` preserved).
2. Deploy the exact merged repair SHA (`restart=False` exact-SHA, preserve `local/`).
3. New loader reads the preserved runtime file.
4. Host `show` must prove no behavior transition:
   `WRITE_ONLY_SHADOW` + `activation_source=RUNTIME` before deploy equals
   the same pair after deploy.

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

## Compact SNAPSHOT_PLUS_DELTA commissioning (later OPERATE, not this Git PR)

Write-only procedure after the economy/signal repair SHA is merged. Do **not**
execute it from the Git PR. Do not rewrite historical fat deltas, verified
`20260905` archive, or live scientific members. Success is material collapse of
tick wall-time and new-delta bytes versus the fat-`unchanged[]` regime, plus
exact reconstruction. Do not require arbitrary exact performance numbers before
a real live result. If the dominant cost remains, STOP and report it instead of
tuning thresholds.

1. Fresh live SHA / collector / HOT90 readback.
2. Exact merged-SHA deploy (`restart=False` exact-SHA).
3. Preserve local runtime/data (`local/` including HOT90 runtime and RDP).
4. Observe several consecutive real ticks.
5. Prove new delta representation appears (`schema_version=2.0`, no `unchanged[]`).
6. Prove mixed old→new current-UTC-day reconstruction.
7. Prove collector source poll continues.
8. Measure tick wall-time.
9. Verify lease does not expire during a normal tick (`LEASE_SECONDS` stays 120 unless a later evidence-backed renewal is required).
10. Verify archive/backup unaffected (no historical rewrite).
11. Verify watch stops generating false `DATA_STALE` / duplicate `COLLECTOR_STALLED`.
12. Wait for automatic `RECOVERED` rather than clearing incident state manually.
13. Record a new storage-growth baseline without deleting old data.

## Non-claims

Filename, listing, mtime, size, or successful upload never authorize deletion.
`canonical_panel_retention = IMMUTABLE` remains content immutability.
`hot_local_residency_days = 90` is local residency, not a rewrite of IMMUTABLE.
Tracked Git YAML is the safe default when no valid runtime file exists, not a
log of the last operator SET. After this SHA, missing runtime means
`CURRENT_SAFE` / SNAPPY, which is a live downgrade if the host was already
`WRITE_ONLY_SHADOW`.
