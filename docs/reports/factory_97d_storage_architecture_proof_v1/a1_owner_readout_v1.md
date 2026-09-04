# Owner readout — FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1

## Terminal

`STORAGE_97D_ARCHITECTURE_READY`

Typical `TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D` = 4.97 GiB ≤ TARGET 40.
Combined conservative stress (SNAPSHOT_PLUS_DELTA members + freq-scaled
raw/meta/backup + tail + staging) = 7.02 GiB ≤ HARD 50 (margin 42.98 GiB)
and ≤ TARGET 40. Architecture `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1` with
HOT members `SNAPSHOT_PLUS_DELTA`. Capture/sampling unchanged.

`STORAGE_TARGET_REQUIRES_CAPTURE_POLICY_CHANGE` не выбран (HARD recovered
losslessly). `STORAGE_ARCHITECTURE_BLOCKED` снят после post-reboot coherence.

Historical incident remains recorded: first probe `HOST_UNREACHABLE`
(`NOT_OBSERVED_AFTER_HOST_UNREACHABLE` for post-hang host mutation/secrets).
Power cycle is not itself recovery proof; machine readback is.

## Entry / outcome

- `DECISION_DELTA`: какая стандартная архитектура держит 90 дней RAW+science на
  текущем ~100 GiB VPS без апгрейда диска — SNAPSHOT_PLUS_DELTA закрывает HARD 50
  lossless.
- `UNCERTAINTY_REMOVED`: live byte attribution, `st_dev` backup sink, exact
  `poll_slots` payload-hash overlap, members reconstruction 258/258 and 121/121,
  97d typical 4.97 GiB / combined stress 7.02 GiB vs 40/50.
- `CAPABILITY_OR_EVIDENCE`: PRD+SSD
  `docs/architecture/FACTORY_97D_STORAGE_ARCHITECTURE_PRD_SSD_V1.md`.
- `STOP`: нет implementation, deploy, retention APPLY, Drive write, delete,
  capture change, merge. Этот PR — research/design handoff.
- `NEXT`: merge gate этого PR. Не стартовать
  `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1` из этого хендоффа.
  Destructive eviction — отдельный поздний gate.

`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`
`NEXT_MODEL_EFFORT`: `LUNA_MAX` на bounded IMPL после merge этого research PR;
`SOL_XHIGH` если IMPL трогает schema/PIT/availability clocks.

Predecessor `NO_STORAGE_ARCHITECTURE_CHANGE_REQUIRED` не переписывается.

## Post-reboot health

SSH `SSH_OK`. Hostname `factory-remote-ops`. New boot proven:
`boot_id=e3645da3-2e1b-4d22-bcaf-20b9648f22d4`, `uptime -s` `2026-09-04 22:12:07`
(EEST), uptime 355 s at 19:18:03Z. Deploy SHA still
`af1ad23ac4a97d4f63108abd8446ad3dc6b1960c` (PR #262 not deployed).

FS used 16.46 GiB / 17%. Collector timer enabled/active; ticks `TICK_COMPLETE`;
activation `ACT-619AE64E885E995E` `ACTIVE`. Source-poll success
`19:18:41.288308Z` → `19:19:41.374963Z` (progress after boot). SQLite
`integrity_check=ok` on observation/operational/paper. publication_jobs:
open 0 / completed 530 / `legacy_full` 0 / unmigrated 0. Backup timers
enabled/waiting; no stuck writer; no backup locks. Off-host `CURRENT`
(`DAILY_DELTA_VERIFIED` 13:17Z). RDP excl. jobs 612 857 483 → 842 194 811
(рост, не rollback). `restore_marker_unresolved=false`.

Doctor JSON `DOCTOR_PROVIDER_FAILED` из `TRANSPORT_ERROR_24h=1` —
остаток 24h-окна, не текущий poll fail. Это не `STOP_WITH_REPLAN`.

Root cause HOST_UNREACHABLE: не доказан без speculative repair. Только
временная последовательность после `/opt` walk. Этот атом Drive не писал и
секреты не читал (`credential_values_read: false`).

## 16 ответов

1. **Что ест байты сейчас (19:23Z):** scientific RDP excl. jobs 842.2 MiB
   (members 786.2 MiB SNAPPY); SQLite 183.2 MiB; completed receipts 545 KiB;
   leftover local ZIP 10.35 GiB (pre-reclaim, не selected 97d term); factory_v1
   0.97 GiB; current data-related incl. leftover ZIP 11.32 GiB; FS ~17%.
2. **Что дублируется:** `poll_slots` overlap probe 20:05Z: 1286/1286 exact
   `sha256(payload_json)` in `call_ledger`; `poll_nonoverlap_payload_bytes=0`;
   duplicate payload bytes 67 874 291. `response_sha256` miss = 1 row / 2
   rows-json bytes. Decision `DEDUPE_KEEP` — не добавлять poll как extra unique
   HOT raw. Same JSON shape не было доказательством. Exact `members.parquet`
   SHA dups = 0; доминирует повтор overlapping 7d member snapshot на каждую
   publication. Same-volume ZIP_STORED full RDP: `st_dev=64769` совпадает с
   `factory_v1`. Leftover sink 10.35 GiB (не selected 97d term).
3. **Operational vs raw vs scientific:** SQLite = ledger + decoded JSON
   (`$.rows` 58.1 MiB unique-ish; body field 0). RDP Parquet = scientific.
   `legacy_full` = 0. DuckDB projection ABSENT.
4. **Backup amplify:** git-side sink same `st_dev=64769`. Other-device
   `FACTORY_BACKUP_SINK` не доказан — исключать нельзя. Selected architecture
   keeps 12h retain-1 **mutable** ZIP_STORED snapshot on the same volume.
   Typical `MUTABLE_LOCAL_BACKUP_PEAK` = 1 912 711 645 bytes (1.78 GiB) — не
   ноль. Не full RDP copy. Leftover ZIP 10.35 GiB — текущий диск, не 97d term.
5. **Lossless savings:** live members SNAPPY→ZSTD3 ≈ 0.74× per file; daily
   batched Parquet ≈ 0.993×/0.999× vs per-file ZSTD3 (**no material gain**).
   SNAPSHOT_PLUS_DELTA: 70.0 MiB → 4.7 MiB (02) and 201.7 MiB → 6.8 MiB (03).
   Reconstruction 258/258 and 121/121. CAS larger than delta — not selected.
6. **Выбранная архитектура:** `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1` + HOT
   members `SNAPSHOT_PLUS_DELTA`.
7. **REJECT:** current SQLite+RDP unchanged (full same-volume RDP ZIP + нельзя
   эвиктить science); Iceberg/Delta/Hudi; MinIO/S3/GCS; PG/Kafka/Redis; 31→90
   в SQLite; daily batched members as HOT; CAS member reuse.
8. **97d footprint (SNAPSHOT_PLUS_DELTA):** typical PRIMARY 3 370 594 606 +
   mutable backup 1 912 711 645 + unarchived tail 15 030 737 + staging
   34 748 398 = `TOTAL` 5 333 085 386 (4.97 GiB). Combined stress TOTAL =
   7 539 689 255 (7.02 GiB). Contractual 1 GiB/day × 97 = 97 GiB — отдельно,
   не run-rate и не publication rate.
9. **PASS 40 GiB?** Typical **yes**. Combined conservative stress **yes**.
10. **PASS 50 GiB?** Typical **yes**. Combined conservative stress **yes**
    (margin 42.98 GiB).
11. **RAW 90d без SQLite bloat:** HOT raw Parquet canonical JSON + occurrence
    metadata; `response_sha256` unique-body. COMPLETED body leaves SQLite only
    after materialize+hash+no unresolved due/call.
12. **Scientific identity после eviction:** content immutable; HOT shrinks;
    COLD ZIP_STORED; hydrate isolated `data_root`. Пока нет поля
    `hot_local_residency_days`:
    `SCIENTIFIC_RDP_LOCAL_EVICTION_FORBIDDEN_UNDER_CURRENT_IMMUTABLE_CONST`.
13. **Drive verify:** `rclone hashsum sha256`; fallback `--download`. Этот атом
    Drive hash не вызывал.
14. **DR:** ~24h RPO на mutable tail (`UNARCHIVED_TAIL_DURABILITY_BYTES` в
    бюджете). Isolated restore. Immutable не weekly full-reupload.
15. **Старый >90d experiment:** archive unit → isolated temp data_root →
    существующие readers.
16. **Новый consumer:** `DATA_RESOLUTION_ECONOMY` admission: compressed
    bytes/day → 97d → vs 40/50. >40 `DEGRADED`; >50 `ACTION_REQUIRED`. Не
    silent downsample. Этот атом capture не меняет.

## Publication-rate stress basis

Typical pubs/day = 530 / 2.9636151684 = 178.83563481898935.
Completed jobs by UTC day: 2026-09-02 **258**, 2026-09-03 **121**,
2026-09-04 **151** (exclude: HOST_UNREACHABLE/reboot, не healthy throughput).
Stress pubs/day = 258. Frequency multiplier vs typical = 1.4426654970701887.
`n_clean_full_utc_days=2`; variance 121 vs 258 ⇒ dimension `BOUNDED`, not
90d-stable. Do not use the 14:17Z–19:23Z catch-up window. Do not use the
1 GiB/day provider cap as publication rate.

Members HOT stress = max SNAPSHOT_PLUS_DELTA day (2026-09-03 = 7 119 972 bytes),
not 258 × p95 per-file. Frequency multiplier 1.4427 still scales raw, other
science, metadata, and mutable backup. Combined conservative = 7.02 GiB ≤ HARD.

## Content immutability vs local residency

Не переименовывать тихо `canonical_panel_retention=IMMUTABLE`.

- canonical content = immutable forever
- hot local residency = 90d
- cold durability = indefinite

## Implementation atom (not this PR)

`FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1` after this research PR merges.
HOT members layout = `SNAPSHOT_PLUS_DELTA`. Write set остаётся в PRD §16.
Eviction remains a later destructive gate.
Deployment sequence: write-only ZSTD + raw plane + members snapshot+delta →
archive without eviction → mutable-only backup cutover → isolated hydrate
proof → STOP.

## VPS locator (unchanged)

```
https://portal.cherryservers.com/
```

```
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_factory" -o IdentitiesOnly=yes -o BatchMode=yes factory@5.199.174.153
```

Default doctor emits health alerts. This atom used `doctor_packet` without
Telegram. Locator one-liner remains:

```
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_factory" -o IdentitiesOnly=yes -o BatchMode=yes factory@5.199.174.153 "cd /opt/solana-alpha-lab && sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py"
```

## Non-claims

Не alpha. Не NetReturn. Не canonical DONE. Не merge. Не implementation.
Не retention APPLY. Не Drive write. Не capture change в этом атоме.
Contractual 1 GiB/day saturation is not a measured run-rate.
