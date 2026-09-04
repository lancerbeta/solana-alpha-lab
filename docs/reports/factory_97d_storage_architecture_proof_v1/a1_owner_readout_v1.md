# Owner readout — FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1

## Terminal

`STORAGE_97D_ARCHITECTURE_READY`

Typical `TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D` = 21.47 GiB ≤ TARGET 40.
Conservative measured stress = 42.84 GiB: TARGET miss, HARD 50 pass.
`STORAGE_97D_ARCHITECTURE_READY_WITH_TARGET_MARGIN` не выбран (stress > 40).
`STORAGE_TARGET_REQUIRES_CAPTURE_POLICY_CHANGE` не выбран (lossless layout
держит HARD). `STORAGE_ARCHITECTURE_BLOCKED` снят после post-reboot
coherence + bounded live forensics.

Historical incident remains recorded: first probe `HOST_UNREACHABLE`
(`NOT_OBSERVED_AFTER_HOST_UNREACHABLE` for post-hang host mutation/secrets).
Power cycle is not itself recovery proof; machine readback is.

## Entry / outcome

- `DECISION_DELTA`: какая стандартная архитектура держит 90 дней RAW+science на
  текущем ~100 GiB VPS без апгрейда диска.
- `UNCERTAINTY_REMOVED`: live byte attribution, `st_dev` backup sink, publication
  span ~2.96 d, SNAPPY footer, ZSTD3 live ratios, 97d typical/stress vs 40/50.
- `CAPABILITY_OR_EVIDENCE`: PRD+SSD
  `docs/architecture/FACTORY_97D_STORAGE_ARCHITECTURE_PRD_SSD_V1.md`.
- `STOP`: нет implementation, deploy, retention APPLY, Drive write, delete,
  merge. Этот PR — research/design handoff.
- `NEXT`: merge gate этого PR после CI; затем
  `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1`. Destructive eviction —
  отдельный поздний gate. Не менять capture/sampling.

`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`
`NEXT_MODEL_EFFORT`: `LUNA_MAX` на bounded implementation после merge; `SOL_XHIGH`
если IMPL трогает schema/PIT/availability clocks.

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
   leftover local ZIP 10.35 GiB (pre-reclaim, не 97d selected term); factory_v1
   0.97 GiB; current data-related incl. leftover ZIP 11.32 GiB; FS ~17%.
2. **Что дублируется:** `poll_slots` ≈ тот же JSON, что `call_ledger` (второй
   сырой слой в SQLite). `response_sha256` extra occurrences 178 / ~387 KiB —
   почти ничего. Exact `members.parquet` SHA dups = 0; доминирует повтор
   overlapping 7d member snapshot на каждую publication. Same-volume
   ZIP_STORED full RDP: `st_dev=64769` совпадает с `factory_v1` ⇒ `B_same_vol=2.0`
   сейчас. Leftover sink 10.35 GiB (не selected 97d term).
3. **Operational vs raw vs scientific:** SQLite = ledger + decoded JSON
   (`$.rows` 58.1 MiB unique-ish; body field 0). RDP Parquet = scientific.
   `legacy_full` = 0. DuckDB projection ABSENT.
4. **Backup amplify:** git-side sink same `st_dev`. Selected architecture
   `B_same_vol=1.0` (mutable-only snapshot). Текущий leftover ZIP 10.35 GiB,
   не steady 97d.
5. **Lossless savings:** live members SNAPPY→ZSTD3 ≈ 0.74×; 80 raw JSON rows →
   ZSTD3 parquet ≈ 0.15×. CI semantic equality без изменений.
6. **Выбранная архитектура:** `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1`
   (не пересобиралась; live numbers её подтверждают).
7. **REJECT:** current SQLite+RDP unchanged (B=2 + нельзя эвиктить science);
   Iceberg/Delta/Hudi; MinIO/S3/GCS; PG/Kafka/Redis; 31→90 в SQLite; CAS files.
8. **97d footprint (selected, B=1, A=0.725):** typical
   `TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D` = 23 048 602 003 bytes
   (21.47 GiB). Conservative stress (members p95/mean) = 46 000 455 406
   (42.84 GiB). Contractual 1 GiB/day × 97 = 97 GiB — отдельно, не run-rate.
9. **PASS 40 GiB?** Typical **yes**. Conservative stress **no**.
10. **PASS 50 GiB?** Typical **yes**. Conservative stress **yes**.
11. **RAW 90d без SQLite bloat:** HOT raw Parquet canonical JSON + occurrence
    metadata; `response_sha256` unique-body. COMPLETED body leaves SQLite only
    after materialize+hash+no unresolved due/call.
12. **Scientific identity после eviction:** content immutable; HOT shrinks;
    COLD ZIP_STORED; hydrate isolated `data_root`. Пока нет поля
    `hot_local_residency_days`:
    `SCIENTIFIC_RDP_LOCAL_EVICTION_FORBIDDEN_UNDER_CURRENT_IMMUTABLE_CONST`.
13. **Drive verify:** `rclone hashsum sha256`; fallback `--download`. Этот атом
    Drive hash не вызывал.
14. **DR:** ~24h RPO на mutable tail. Isolated restore. Immutable не weekly
    full-reupload.
15. **Старый >90d experiment:** archive unit → isolated temp data_root →
    существующие readers.
16. **Новый consumer:** `DATA_RESOLUTION_ECONOMY` admission: compressed
    bytes/day → 97d → vs 40/50. >40 `DEGRADED`; >50 `ACTION_REQUIRED`. Не
    silent downsample.

## Content immutability vs local residency

Не переименовывать тихо `canonical_panel_retention=IMMUTABLE`.

- canonical content = immutable forever
- hot local residency = 90d
- cold durability = indefinite

## Implementation atom (not this PR)

`FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1` after this research PR merges.
Write set stays in PRD §16. Eviction remains a later destructive gate.
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
Не retention APPLY. Не Drive write. Не capture change. Не WITH_TARGET_MARGIN.
Contractual 1 GiB/day saturation is not a measured run-rate.
