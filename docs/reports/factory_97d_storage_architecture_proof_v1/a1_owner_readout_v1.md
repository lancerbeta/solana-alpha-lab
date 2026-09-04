# Owner readout — FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1

## Terminal

`STORAGE_TARGET_REQUIRES_CAPTURE_POLICY_CHANGE`

Typical `TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D` = 23.45 GiB ≤ TARGET 40.
Combined conservative stress (publication-frequency × members p95 after
lossless layout + mutable backup + unarchived tail + staging) = 62.33 GiB
**> HARD 50**. Architecture direction `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1`
accepted and unchanged. This atom does **not** change capture/sampling.

`STORAGE_97D_ARCHITECTURE_READY` не выбран (combined stress fails HARD).
`STORAGE_97D_ARCHITECTURE_READY_WITH_TARGET_MARGIN` не выбран.
`STORAGE_ARCHITECTURE_BLOCKED` снят после post-reboot coherence + bounded
live forensics.

Historical incident remains recorded: first probe `HOST_UNREACHABLE`
(`NOT_OBSERVED_AFTER_HOST_UNREACHABLE` for post-hang host mutation/secrets).
Power cycle is not itself recovery proof; machine readback is.

## Entry / outcome

- `DECISION_DELTA`: какая стандартная архитектура держит 90 дней RAW+science на
  текущем ~100 GiB VPS без апгрейда диска — и проходит ли она 40/50 после
  additive same-volume mutable backup и publication-rate stress.
- `UNCERTAINTY_REMOVED`: live byte attribution, `st_dev` backup sink, exact
  `poll_slots` payload-hash overlap, healthy UTC publication counts (n=2),
  SNAPPY footer, ZSTD3 live ratios, 97d typical 23.45 GiB / combined stress
  62.33 GiB vs 40/50.
- `CAPABILITY_OR_EVIDENCE`: PRD+SSD
  `docs/architecture/FACTORY_97D_STORAGE_ARCHITECTURE_PRD_SSD_V1.md`.
- `STOP`: нет implementation, deploy, retention APPLY, Drive write, delete,
  capture change, merge. Этот PR — research/design handoff.
- `NEXT`: owner capture/sampling (или другой HARD-budget) decision. Не
  стартовать `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1` как будто 50 GiB
  proven. Destructive eviction — отдельный поздний gate.

`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`
`NEXT_MODEL_EFFORT`: `SOL_XHIGH` на owner capture-policy / budget decision;
`LUNA_MAX` только на bounded IMPL после того, как HARD 50 снова доказуем.

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
5. **Lossless savings:** live members SNAPPY→ZSTD3 ≈ 0.74×; 80 raw JSON rows →
   ZSTD3 parquet ≈ 0.15×. CI semantic equality без изменений.
6. **Выбранная архитектура:** `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1`
   (не пересобиралась; live numbers её подтверждают как направление).
7. **REJECT:** current SQLite+RDP unchanged (full same-volume RDP ZIP + нельзя
   эвиктить science); Iceberg/Delta/Hudi; MinIO/S3/GCS; PG/Kafka/Redis; 31→90
   в SQLite; CAS files.
8. **97d footprint (additive, A=0.725):** typical PRIMARY 22 813 412 249 +
   mutable backup 1 912 711 645 + unarchived tail 215 472 156 + staging
   235 189 817 = `TOTAL` 25 176 785 867 (23.45 GiB). Combined stress TOTAL =
   66 929 230 243 (62.33 GiB). Contractual 1 GiB/day × 97 = 97 GiB — отдельно,
   не run-rate и не publication rate.
9. **PASS 40 GiB?** Typical **yes**. Combined conservative stress **no**.
10. **PASS 50 GiB?** Typical **yes**. Combined conservative stress **no**.
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
    silent downsample. Этот атом capture не меняет; terminal требует owner
    decision.

## Publication-rate stress basis

Typical pubs/day = 530 / 2.9636151684 = 178.83563481898935.
Completed jobs by UTC day: 2026-09-02 **258**, 2026-09-03 **121**,
2026-09-04 **151** (exclude: HOST_UNREACHABLE/reboot, не healthy throughput).
Stress pubs/day = 258. Frequency multiplier vs typical = 1.4426654970701887.
`n_clean_full_utc_days=2`; variance 121 vs 258 ⇒ dimension `BOUNDED`, not
90d-stable. Do not use the 14:17Z–19:23Z catch-up window. Do not use the
1 GiB/day provider cap as publication rate.

Combined stress = 258 pubs/day × p95 members after ZSTD3 + freq-scaled raw +
operational metadata + same-volume mutable backup + unarchived tail + staging.
Size-only p95 or frequency-only without p95 is **not** the HARD-50 claim.
Do not massage: combined 62.33 GiB exceeds HARD.

## Content immutability vs local residency

Не переименовывать тихо `canonical_panel_retention=IMMUTABLE`.

- canonical content = immutable forever
- hot local residency = 90d
- cold durability = indefinite

## Implementation atom (not this PR)

`FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1` только после owner
capture/budget decision и повторного доказательства HARD 50. Write set
остаётся в PRD §16. Eviction remains a later destructive gate.
Deployment sequence: write-only ZSTD + raw plane → archive without eviction →
mutable-only backup cutover → isolated hydrate proof → STOP.

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
Не retention APPLY. Не Drive write. Не capture change в этом атоме
(terminal — owner gate на capture/budget). Не WITH_TARGET_MARGIN. Не READY.
Contractual 1 GiB/day saturation is not a measured run-rate.
