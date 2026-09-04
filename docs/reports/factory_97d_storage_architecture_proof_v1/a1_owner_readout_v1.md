# Owner readout — FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1

## Terminal

`STORAGE_ARCHITECTURE_BLOCKED`

Live probe: `HOST_UNREACHABLE`

VPS `factory-remote-ops` (`5.199.174.153`) не отвечал (SSH banner timeout,
ICMP 100% loss) после read-only forensics-скрипта, который обошёл `/opt` в
поисках `BACKUP_*.zip`. Причинность «скрипт уронил хост» не доказана, только
временная последовательность. Factory-данные не мутировались, Drive не
писался, секреты не читались. Live Phase A/C этого атома не закрыты. 40/50 GiB
PASS/FAIL не утверждается.

Последний успешный machine readback: `2026-09-04T14:17:55Z`
(`a1_storage_baseline_v1.json`).

## Entry / outcome

- `DECISION_DELTA`: какая стандартная архитектура держит 90 дней RAW+science на
  текущем ~100 GiB VPS без апгрейда диска.
- `UNCERTAINTY_REMOVED`: владельцы байт и backup-амплификация из Git-контрактов
  и baseline 14:17Z; semantic equality кодеков на schema-faithful корпусе.
  rclone/Drive SHA256 и isolated hydration — **выбранный контракт**, не live
  измерение в этом атоме (Drive hash calls = 0).
- `CAPABILITY_OR_EVIDENCE`: PRD+SSD
  `docs/architecture/FACTORY_97D_STORAGE_ARCHITECTURE_PRD_SSD_V1.md`.
- `STOP`: нет implementation, deploy, retention APPLY, Drive write, delete.
- `NEXT` — три разных слоя, не одна стрелка:

  1. **Owner recovery (сейчас):** Cherry portal reboot instance `973818`.
     Locator: `docs/operator/FACTORY_REMOTE_HOST.md`.
  2. **Research (после живого SSH):** bounded live forensics, suggested id
     `FACTORY_97D_BOUNDED_LIVE_FORENSICS_V1`. Не этот PR. Не walk `/opt`.
  3. **Implementation:** `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1` только
     после capacity terminal `STORAGE_97D_ARCHITECTURE_READY` или
     `STORAGE_97D_ARCHITECTURE_READY_WITH_TARGET_MARGIN`. Не следующий шаг.

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

Хост на момент этого readout не отвечает. Это не micro-approval и не
implementation. Слой 1 — только владелец в Cherry. Locator:
`docs/operator/FACTORY_REMOTE_HOST.md` и
`docs/operator/factory_remote_host_v1.yaml`. Instance: `973818`. Hostname:
`factory-remote-ops`. IPv4: `5.199.174.153`. User: `factory`.

```
https://portal.cherryservers.com/
```

Хост снова жив, когда SSH banner не timeout **и** doctor JSON читается
(вердикт `HEALTHY` у doctor запрещён; нужен parseable JSON, не ICMP-only).

Проверка SSH с ПК оператора:

```
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_factory" -o IdentitiesOnly=yes -o BatchMode=yes factory@5.199.174.153
```

Doctor после живого SSH:

```
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_factory" -o IdentitiesOnly=yes -o BatchMode=yes factory@5.199.174.153 "cd /opt/solana-alpha-lab && sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py"
```

Слой 2 (агент, только после живого SSH): `du` только
`/opt/solana-alpha-lab/local/factory_v1` и известный backup sink; SQLite
`file:?mode=ro`; parquet metadata; не `rglob /opt`; не hashing всего дерева
одним процессом без прогресса. Это не команды Cherry console.

Collector на момент 14:17Z был `ACTIVE`. Текущее здоровье неизвестно, пока нет
свежего doctor.

## Non-claims

Не alpha. Не NetReturn. Не canonical DONE. Не 40/50 PASS. Не implementation.
Не retention APPLY. Не Drive write. Не текущий runtime health.
