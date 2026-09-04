# Owner readout — FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1

## Terminal

`STORAGE_ARCHITECTURE_BLOCKED`

VPS `factory-remote-ops` (`5.199.174.153`) стал unreachable (SSH banner timeout,
ICMP 100% loss) после read-only forensics-скрипта, который обошёл `/opt` в
поисках `BACKUP_*.zip`. Factory-данные не мутировались, Drive не писался,
секреты не читались. Live Phase A/C этого атома не закрыты. 40/50 GiB PASS/FAIL
не утверждается.

Последний успешный machine readback: `2026-09-04T14:17:55Z`
(`a1_storage_baseline_v1.json`).

## Entry / outcome

- `DECISION_DELTA`: какая стандартная архитектура держит 90 дней RAW+science на
  текущем ~100 GiB VPS без апгрейда диска.
- `UNCERTAINTY_REMOVED`: владельцы байт и backup-амплификация из Git-контрактов
  и baseline 14:17Z; semantic equality кодеков на schema-faithful корпусе;
  rclone/Drive SHA256; hydration без HOT/COLD в каждом reader.
- `CAPABILITY_OR_EVIDENCE`: PRD+SSD
  `docs/architecture/FACTORY_97D_STORAGE_ARCHITECTURE_PRD_SSD_V1.md`.
- `STOP`: нет implementation, deploy, retention APPLY, Drive write, delete.
- `NEXT`: bounded live forensics (без walk `/opt`) → заполнить 97d таблицу →
  один implementation atom только если PASS.

`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`
`NEXT_MODEL_EFFORT`: `SOL_XHIGH` на retry forensics / capacity; не
implementation.

Predecessor `NO_STORAGE_ARCHITECTURE_CHANGE_REQUIRED` не переписывается: это
было «менять topology/retention/resolution *сейчас*?» при 31d raw + immutable
local RDP. Здесь новое требование владельца: 90d residency всех material RAW +
science и бюджет 40/50 GiB.

## 16 ответов

1. **Что ест байты сейчас (14:17Z):** scientific RDP ~584 MiB; SQLite ~160 MiB;
   completed publication receipts ~480 KiB; local backup zip ~10.3 GiB
   (pre-reclaim leftover, не steady-state); FS used ~15.1 GiB / ~16%.
2. **Что дублируется:** текущий 12h ZIP_STORED full копирует весь
   `observation_rdp` на тот же диск; weekly off-host full снова шлёт те же
   immutable байты. Size-only remote verify. Member `members.parquet` пишется
   на каждую publication — live exact-dup ещё не измерен.
3. **Operational vs raw vs scientific:** SQLite = operational ledger + decoded
   JSON bodies (~56.5 MiB protected payloads, 2353 calls). RDP Parquet =
   scientific. `legacy_full` = 0.
4. **Backup amplify:** ZIP_STORED ⇒ ~1.0× сжатия, ~2× same-volume если sink на
   том же FS. `FACTORY_BACKUP_SINK` other-device **не** machine-proven —
   same-volume байты входят в 40/50.
5. **Lossless savings:** CI корпус доказал semantic equality для unspecified /
   none / zstd 1,3,7 / snappy и raw `canonical_json_bytes` roundtrip +
   `response_sha256` dedup. Live ratio не измерен (хост упал).
6. **Выбранная архитектура:** WRAP Parquet ZSTD + DuckDB + rclone Drive SHA256
   + существующий ZIP/manifest; split operational SQLite vs HOT raw Parquet;
   upload-once immutable; 90d residency / indefinite cold; mutable-only local
   snapshot. Имя: `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1`.
7. **REJECT:** current SQLite+RDP unchanged (2× backup + нельзя эвиктить);
   Iceberg/Delta/Hudi (каталог/сервис, сложность > задачи); MinIO/S3/GCS (новый
   провайдер); PostgreSQL/Kafka/Redis; 31→90 в SQLite как решение; CAS файлы
   пока Parquet сохраняет exact canonical bytes.
8. **97d footprint:** typical / conservative **UNKNOWN** без publication
   day-span. Contractual 1 GiB/day × 97d = 97 GiB — отдельно, не measured
   run-rate, и уже > HARD 50.
9. **PASS 40 GiB?** Не утверждается.
10. **PASS 50 GiB?** Не утверждается.
11. **RAW 90d без SQLite bloat:** HOT raw Parquet (canonical JSON bytes +
    occurrence metadata, dedup по `response_sha256`); COMPLETED body уходит из
    SQLite только после materialize+hash+нет unresolved due/call.
12. **Scientific identity после eviction:** content immutable; HOT tree
    shrinks; COLD ZIP_STORED exact source bytes; hydrate в isolated
    `data_root`; manifests/path/dataset id сохраняются; DuckDB projection
    rebuild from remaining HOT, не partial delete из глобально связанного
    индекса.
13. **Drive verify:** `rclone hashsum sha256`; fallback `--download`. Size-only
    недостаточно. Это атом Drive не вызывал.
14. **DR:** ~24h RPO за счёт mutable snapshot + unclosed tail. Isolated restore
    без записи в live `factory_v1`. Immutable не weekly full-reupload.
15. **Старый >90d experiment:** скачать archive unit → isolated temp data_root
    → существующие readers. Не поверх live.
16. **Новый consumer через месяц:** storage admission в
    `DATA_RESOLUTION_ECONOMY`: compressed bytes/day → 97d → total vs 40/50.
    >40 `DEGRADED`; >50 `ACTION_REQUIRED`. Не silent downsample. Если lossless
    не влезает в 50 — `STORAGE_TARGET_REQUIRES_CAPTURE_POLICY_CHANGE`.

## Content immutability vs local residency

Не переименовывать тихо `canonical_panel_retention=IMMUTABLE`.

- canonical content = immutable forever
- hot local residency = 90d
- cold durability = indefinite

## VPS / owner attention

Хост сейчас не отвечает. Это не micro-approval: нужен operator check
(Cherry console / reboot), затем **bounded** forensics:

- `df` / `findmnt` / `du` только `local/factory_v1` и известный backup sink
- SQLite read-only URI
- parquet **metadata** (не `rglob /opt`)
- не hashing всех файлов одним процессом без прогресса

Collector на момент 14:17Z был `ACTIVE`. Текущее здоровье неизвестно, пока нет
свежего doctor.

## Non-claims

Не alpha. Не NetReturn. Не canonical DONE. Не 40/50 PASS. Не implementation.
Не retention APPLY. Не Drive write. Не текущий runtime health.
