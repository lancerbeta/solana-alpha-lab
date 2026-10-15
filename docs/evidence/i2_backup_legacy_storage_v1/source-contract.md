# SMIAL I2 — небольшие бэкапы, безопасное освобождение места, обслуживание без ручной рутины

**PRD + SSD + контракт исполнения · V1 · 15 октября 2026**
**Proposed task ID:** `I2_BACKUP_LEGACY_STORAGE_V1`
**Parent:** `SMIAL_MANAGED_COLLECTION_OPERABILITY_V1`, прежде всего §5, §7.1–7.2, §9–12.
**Mode этого документа:** DESIGN. Стартовая команда §15 выбирает EXECUTE; production-права она не расширяет.

> **Результат I2:** согласованный и восстановимый backup с разумными размером/временем; ненужные legacy bodies выведены из HOT и новых routine checkpoints; физический размер уменьшен; повторяемое обслуживание выполняется существующей системой по одной одобренной политике. Работающий collector, автоматическое продолжение I3, уже принятые наблюдения и история списаний сохраняются.
>
> **Не результат:** заменить `ZIP_STORED` на DEFLATE, получить зелёные тесты и оставить гигабайтный legacy в каждой новой копии. Сжатие — первый полезный этап, не закрытие I2.

## 0. Как исполнять и что считать завершением

Одна постановка, один coherent scope. По умолчанию — одна feature-ветка и один согласованный PR для необходимых изменений backup/restore/retention и прямых consumers. Применение staged: сначала безопасная упаковка, затем отдельно разрешённый retirement/reclaim и включение maintenance policy. Это не обязательные отдельные PR и не подтверждение владельцем каждого технического действия.

Исполнитель сам выбирает функции, SQL, размер chunks, способы mock/fault injection и повторное использование проверок. До material authority boundary работает самостоятельно. Не заменяет согласованный результат перечнем `not proven`: обязательный непокрытый сценарий остаётся BLOCKED/PARTIAL.

**Рекомендуемая последовательность:**

| Этап | Независимо проверяемый результат | Где остановиться |
|---|---|---|
| A. Реализация и rehearsal | Correct snapshot/chain/restore; измеренное сжатие; безопасный retirement/reclaim на копии; готовый штатный maintenance path | Exact-head merge gate или material blocker |
| B. Первая production-поставка | Новый packager/restore установлен; обычный backup восстановим; A/B/I3 не повреждены | Только перед отдельным destructive APPLY/maintenance-policy approval |
| C. Retirement + reclaim + maintenance | Exact legacy scope выведен из HOT, место реально освобождено, новая цепь не зависит от retired bodies, обслуживание не требует ежедневного агента | Итоговая отбивка; либо конкретный недостающий live cycle |

Если общий PR объективно задерживает безопасную первую поставку, допускается отделить готовый packaging/restore repair. Основание — измеренный риск или независимая возможность приёмки, не удобство написать ещё один маленький PR. Остаток I2 сохраняется в той же постановке с точным resume point.

**Первый STOP исполнителя:** готовый exact PR/CI/merge-readiness либо существенная конфликтующая предпосылка. До этого не спрашивать владельца про уровень DEFLATE, SQL-индекс или имена файлов.

## 1. Checkpoint и границы истины

### 1.1. Подтверждённый Git и предоставленный runtime

**Git anchor, прочитан при подготовке:** `b3fb9d8ecffbffda468dccabaa81ca3392da6f15` (`main`, merge #405). Прочитаны `AGENTS.md`, semantic map, backup/restore/retention owners и непосредственные consumers. Перед исполнением — current Git и relevant diff, не слепой checkout старого SHA. [G0]

**Runtime — из последней отбивки исполнителя, не новый SSH-readback Project Chat:**

| Объект | Известное состояние / protected binding |
|---|---|
| Producer | `b3fb9d8e…` установлен, ordinary SEARCH→publication работает |
| Managed profile | revision 1, desired `RUN`, `UNTIL_REVOKED`; grant/profile SHA `e561a280378bba681a8e45d924e41976227bd823971740964c010e0040cf8a37` |
| Режим | 100 admissions/UTC day, rolling 100, active cap 400; shared account 1200 calls / 1200 credits в сутки, cumulative 2 000 000 |
| Общий аккаунт | `JUPITER-MANAGED-ACCOUNT-1`, расход не сбрасывается при смене activation |
| A | `ACT-4744D4017AC4B196`, schedule `4744d4017ac4b19625c5ee11ce4e20fdd4b36c6744f8c0889467052e2a6ef23c`; authority `c2c937b4…`, storage `fa6450ba…` |
| B | `ACT-A26CF9B0815A36F2`, schedule `a26cf9b0815a36f2f67589b7c1db5da429d617ab048ff9676ad7df64ad2cc063`; зарегистрирована, авторизована, persistent timer взведён |
| B timing | Intake 17.10 00:15Z → 18.10 00:00Z; запуск 17.10 00:20:30Z, резервный 00:50:30Z; tail authority до 21.10 01:05Z |
| Managed takeover | Не раньше 18.10 00:00Z; новые окна автоматически; live acceptance переходов ещё впереди |
| C1/C2 | Принятый exact corpus: 47 episodes / 6533 episode-point pairs. Не переснимать и не переисследовать |
| Backup baseline | По отчёту 7932 ZIP entries, `ZIP_STORED`, archive ≈5.225 GB; SQLite ≈5.21 GB; daily upload 60–110 минут |
| Legacy decomposition | По benchmark около 94% DB приходится на крупные `call_ledger`, `poll_slots`, `candidate_members`; это не разрешение удалить 94% DB |
| Компрессия | Примерно 6× на исследованных данных — предварительный benchmark, не доказанный whole-checkpoint ratio |
| Freshness | Source `OFFHOST_VERIFIED`, profile max-age 30h; effective предел ограничен CURRENT 24h. После успешной delta FRESH/CURRENT; daily cycle создаёт интервал DEGRADED во время следующего upload |

Не использовать сокращённые SHA для execution. Полные protected receipts/path/root identities executor получает из существующего runtime/readback. State A/B может законно измениться к моменту исполнения; сравнивать допустимый переход, не требовать вечного `ACTIVE`.

### 1.2. Что непосредственно найдено в коде

| Seam | Подтверждённый факт | Следствие для I2 |
|---|---|---|
| Snapshot consistency | `BackupPayloadSnapshot` обслуживает publication-job files; `scan_backup_inventory` делает SQLite snapshot, а full/delta packager может снять SQLite повторно | Проверить concurrent-writer reproducer; на один checkpoint inventory и ZIP должны читать одни SQLite bytes [G1] |
| Compression | Packagers используют STORED; `_stream_zip_entry` самостоятельно создаёт `ZipInfo` без `compress_type` | Одной замены параметра `ZipFile` недостаточно; проверить реальные entries [G1] |
| Chain restore | `restore_incremental_chain_isolated` принимает `expected_inventory_sha256`, но в прочитанном owner только возвращает его, не сравнивает с реконструированным corpus | Встроить итоговую проверку и continuity каждого delta; ненулевое RDP и hash ZIP не являются oracle [G2] |
| Restore marker | Full restore добавляет marker в SQLite, затем deltas могут заменить весь SQLite-файл | Воспроизвести и гарантировать unresolved marker **после последнего** file replacement; raw-byte oracle выполнять до recovery-decoration [G2] |
| Retention | Native `evaluate_retention/apply_retention` есть; большие payload читаются через `fetchall()`, eligibility в основном legacy due-based | Ремонтировать owner, не строить второй compactor; добавить episode/pin-aware защиту [G3] |
| Retention freshness | Текущий apply сохраняет `call_ledger.updated_at` | Это полезный invariant, сохранить; cleanup не становится новым provider event [G3] |
| CLI read-only | Retention `status` открывает обычный writable store и повторяет evaluation | Исправить entry point: настоящий ro status/plan, одна bounded evaluation [G3] |
| Backup freshness | В receipt off-host `uploaded_at`/`verified_at` записываются из captured clock начала run; config CURRENT=86400s; I3 требует CURRENT и затем свой max-age | Сжатие сократит задержку, но само не исправит clock/cadence contract [G4, G5] |
| Source meaning | Retention работает с decoded/canonical provider JSON; episode ledger содержит `raw_body_rel` и `entities` | Архив JSON не называть исходным HTTP; ссылки и recovery-поля не выкидывать общим whitelist [G3, G6] |

Это кодовые факты и основания проверок, **не заявление о повреждении существующих production backups**. Достаточно проверить применимые real chains, не обследовать всю историю Drive.

## 2. PRD: owner outcome, критерии и non-goals

### 2.1. Требования к результату

1. Обычные local/full/delta paths используют согласованный captured state и сохраняют восстановимость при concurrent collector.
2. Объём новой routine копии кратно меньше baseline при сопоставимом snapshot. Размер, CPU/RSS, upload и filesystem peak измерены отдельно.
3. Удалённые из HOT **retired bodies отсутствуют в логическом payload новых routine checkpoints**, а не просто хорошо сжаты. Компактная lineage/provenance/accounting-истина сохраняется.
4. Физическое освобождение подтверждено размером DB/WAL и тома. Freelist reuse не выдаётся за уменьшение файла.
5. Обычная последующая maintenance работает по approved policy без ежедневных IDs, ручного агента, ручного `record-backup` и новых PR.
6. При отсутствии места, конфликте, failed upload или недоступном архиве механизм сохраняет last-good и нужные источники, откладывает необязательные действия, выдаёт один actionable incident через existing watch.
7. Restore работает без исходного VPS из exact сохранённых объектов; не требует переснять рынок, заново authorize старые episodes или сбросить расходы.
8. Право на будущий intake, `STOP_INTAKE`, old/tail authorities и protected B сохраняются. I2 не меняет смысл научной выборки.

**Product DoD:** выполнены packaging/restore proof, approved retirement/reclaim, новый recovery checkpoint, один обычный backup cycle и один обычный maintenance cycle при действующем collector. Пока последнего нет — конкретный `LIVE_PENDING_*`, но не завершённый I2.

### 2.2. Что исключено

Не внедрять новый backup service/БД/object-store, WAL shipping, собственный page-delta формат, новый шифровальный ключ или новый внешний сервис. Не включать LZMA только ради лучшего ratio. Не переустраивать scheduler/Forge. Не увеличивать admissions, provider budgets или период хранения без отдельного решения. Не удалять исходные научные данные или старые цепи по wildcard/возрасту папки. Не делать daily VACUUM.

Никакие secrets/raw payload не попадают в Git, чат или sanitized evidence. Использовать существующие credentials только в отдельно разрешённой операции; новых ключей нет.

### 2.3. Рекомендуемый вариант и альтернативы

**Выбрано:** существующие SQLite + `BackupPayloadSnapshot`/backup packagers + local/Drive owners + native retention, с небольшими изменениями по реальным seams.

Только DEFLATE — полезная первая поставка, но не итог I2. Новая deduplicating backup-платформа — WATCH лишь если после retirement и сжатия остаётся измеренный material bottleneck. До этого цена новой эксплуатации выше недоказанного выигрыша.

## 3. Владельцы, интерфейсы и footprint задачи

Entry: `AGENTS.md` → `SEM-REMOTE-OPS-RECOVERY`, `SEM-LIVE-COLLECTION`, `SEM-LIVE-EVIDENCE-TO-FORGE` → exact owners. Реальное executable задание материализуется по текущему delivery harness, не отдельной параллельной spec-системой.

| Existing owner | Изменение / ответственность |
|---|---|
| `src/solana_alpha_lab/factory/remote_ops.py` | Snapshot mapping, full/delta entries, local verification, restore, pruning ownership |
| `src/solana_alpha_lab/factory/offhost_backup.py` | Immutable retry, checkpoint publication/chain tip, last-good/attempt health, clock meanings, remote reference retention |
| `src/solana_alpha_lab/factory/observation_schedule_retention.py` | Scope/eligibility, exact plan, bounded compaction, policy/resume; при необходимости reclaim adapter |
| `scripts/observation_schedule_retention.py` | Одна публичная discoverable operational entry: ro plan/status, gated apply, continuation/status |
| `src/solana_alpha_lab/factory/observation_schedule_store.py` | Только необходимые narrow store/maintenance cursor primitives; existing writer fence |
| `managed_collection.py`, `collector_operational_packet.py`, `operability_watch.py` | Прямые consumers новых backup/capacity/maintenance semantics; без переписывания I3 |
| Existing archive/release owners | Проверка frozen source dependencies и cold pins; расширение только если без этого unsafe retirement |
| `configs/factory_remote_operations_v1_1.yaml`, relevant schemas и `configs/factory_remote_ops/*` | Только необходимая versioned configuration/installed-unit propagation; никаких скрытых новых timers |
| Existing tests/contracts/operator/Catalog | Дополнить по реально изменённой семантике, не создавать дубликаты |

На anchor используются Python `>=3.13,<3.14`, exact pin `3.13.14`; действующий lock не обновлять ради этой задачи. [G7]

Логические интерфейсы ниже — дизайн, не утверждение о существующих CLI names. Executor размещает их внутри перечисленных owners. Не требуется общий framework.

```text
CapturedSources(checkpoint_identity)
    logical_path → staged_path, SHA256, size, substrate, captured_at/bounds

CheckpointOperation
    captured inventory → immutable archive(s) → remote verified checkpoint
    → committed local chain pointer → owned staging release

RetentionPlan / Policy
    exact source identity + scope + cutoff/high-watermark + pins + archive refs
    → bounded revalidated apply → semantic compaction receipt → physical reclaim
```

## 4. SSD — единый captured state и честная ZIP-компрессия

### 4.1. Snapshot один раз, не «почти тот же»

Расширить существующую модель снимка так, чтобы **каждая SQLite в одном checkpoint снималась один раз**. Последующие inventory, diff, pack, manifest/result inventory и chain tip читают этот снимок. Standalone local full использует тот же путь. Разные самостоятельные checkpoints не обязаны разделять один snapshot.

Для SQL использовать existing SQLite backup API, не `cp` открытого `.sqlite` без WAL. API поддерживает online-копирование; это не гарантирует атомарность нескольких отдельных БД/файлов. [E2]

Нужна проверяемая совместимость OPS, operational/paper store и publication/research dependencies. Предпочтительно existing recovery/reconciliation boundary; краткий writer fence — только там, где без него нет согласованного recovery set. Нельзя удерживать collector lease всё время компрессии или upload.

**Важный consumer:** managed grant/children/counters и соответствующие authority/transition ResearchEvents. Определить минимальное recovery-required множество. Если текущий mutable-only backup его не покрывает, добавить нужную узкую dependency closure либо связать с уже verified archive. Не возвращать весь RDP в каждую daily delta. Непокрытая часть остаётся явным blocker полного restore claim.

Для каждого mutable path должен быть один captured источник. Пропавший после capture live-файл не перечитывать. Новый файл, появившийся позже, относится к следующему checkpoint; archive/provenance должны описывать именно captured membership.

**Cheap falsifier:** после inventory commit имитировать запись collector в исходную SQLite и переход publication-job. Старый путь проверяется на расхождение; исправленный checkpoint должен содержать ровно captured bytes и допустимые recovery dependencies. Не требовать «writer остановлен во время всего backup» ради прохождения теста.

### 4.2. Место, срок жизни и повторное использование снимка

Снимки размещаются на явно известном томе/staging root с учётом volume model. Не оставлять крупные файлы в неучтённом `/tmp`/tmpfs. На run — одна captured копия каждой DB и текущий ZIP; дальнейшая лишняя полная копия допустима только как измеренная необходимость existing consumer.

Snapshot освобождается **после последнего local consumer** — inventory/packing/local-byte verification — и не держится до конца сетевого upload, если он уже не нужен. Retry использует готовый immutable ZIP и сохранённый operation intent. При crash cleanup удаляет только принадлежащие этому run временные артефакты, не последний рабочий snapshot/ZIP другого процесса.

Не удерживать RAM пропорционально DB/archive. Начать с существующего streaming chunk; менять только при benchmark. Полный SQLite не читать в `bytes`/memory compression. Bound применим также к количеству source paths и manifest entries: при текущих ~8 тыс. entries существующий список может быть достаточен; payload stream и retention SQL не должны превращаться в multi-GB objects.

### 4.3. DEFLATE на конкретном entry

Первый кандидат — стандартный DEFLATE level 1; другой низкий уровень рассмотреть только если materially улучшает результат. Сначала одинаковый source snapshot: STORED → DEFLATE → независимое извлечение/сравнение. Не переносить ratio отдельных legacy-таблиц на весь checkpoint.

В `_stream_zip_entry` создан собственный `ZipInfo`, поэтому метод и уровень задаются именно ему. Python 3.13 предоставляет публичный `compress_level`. ZIP64 и исходные archive metadata conventions сохраняются. [E1]

Иллюстрация интеграции, не готовая замена всего packager:

```python
# source — captured immutable snapshot, НЕ live SQLite.
# Existing validation, canonical metadata, exception cleanup и fsync остаются у owner.
info = zipfile.ZipInfo(filename=relative, date_time=ZIP_TIMESTAMP)
info.external_attr = 0o100644 << 16
info.compress_type = zipfile.ZIP_DEFLATED
info.compress_level = 1
with source.open("rb") as src, archive.open(info, "w", force_zip64=True) as dst:
    # Existing bounded stream одновременно считает SHA256 распакованных bytes.
    digest, size = stream_copy_and_hash(src, dst)
assert digest == captured_entry.sha256
assert size == captured_entry.size
```

`stream_copy_and_hash`/`captured_entry` в примере — логические placeholders, не обещанные repository symbols. Переиспользовать существующий stream helper.

В acceptance проверять `ZipInfo.compress_type`, `file_size`, `compress_size` реальных больших entries. `ZipFile.testzip()` проверяет CRC/header, но не заменяет сравнение с независимым captured inventory. Маленький manifest может оставаться STORED; нельзя утверждать «всё сжато», если основной SQLite entry остался STORED.

## 5. SSD — checkpoint publication, retry и полноценное восстановление

### 5.1. Порядок commit без потери last-good

Рекомендуемый порядок в существующем owner:

```text
CAPTURED → PACKED_LOCAL_VERIFIED → PAYLOAD_REMOTE_VERIFIED
         → CHECKPOINT_REMOTE_VERIFIED → CHAIN_POINTER_COMMITTED → CLEANUP
```

Это conceptual phases одного existing operation/receipt, не новый workflow engine.

- До local verification не публиковать финальное content-addressed имя.
- До remote verification нужных payload не публиковать checkpoint, ссылающийся на них.
- До подтверждения checkpoint не заменять last-good pointer и не удалять его последние локальные dependencies.
- После remote checkpoint commit, но до local pointer commit — crash recovery находит тот же operation и заканчивает local bookkeeping; не переснимает рынок и не начинает другую chain.
- После timeout/UNKNOWN результата upload сначала remote reconciliation того же имени/hash, затем bounded повтор того же артефакта. Новые SQLite snapshots, filenames и full chains на каждом retry запрещены.
- Локальный prune учитывает pending upload/restore references и retained local points. Удалять «все BACKUP кроме последнего» до установления replacement recovery path нельзя.
- Повреждённый существующий chain-state файл — typed conflict, не пустая новая installation. First bootstrap и corruption различаются.

Сохранить один backup-plane lock и существующий OPS writer fence, но установить непротиворечивый порядок их захвата. Maintenance не ждёт network upload, удерживая writer lease. Weekly/full/daily/local contention даёт bounded DEFER, а не параллельные snapshots или принудительное снятие чужого lock.

### 5.2. Restore — это проверка состояния, а не наличия ZIP

`restore_from_recovery_checkpoint` → existing full + ordered deltas → isolated raw reconstruction:

1. Проверить checkpoint schema/name/content hash, безопасные относительные paths, exact base/delta identities и порядок ссылок.
2. Проверить entries и declared sizes/hashes; не допускать duplicate paths, traversal/symlink, неожиданный entry, omitted changed file, delete вне manifest или несоответствие base inventory.
3. Для каждого delta проверить `base_inventory_sha256` против реконструированного предыдущего состояния; после применения сравнить result inventory. Missing/reordered delta не даёт «частично успешный restore».
4. Итоговый reconstructed inventory должен совпасть с expected checkpoint inventory **по фактическим файлам**, не только по скопированному полю manifest. Read-only raw phase не меняет восстановленную SQLite до этого сравнения.
5. После всех file replacements — SQLite integrity и semantic checks; затем добавить unresolved restore marker в готовую operational copy. Marker не может быть стёрт последней SQLite-delta. Collector на восстановленной stale копии не имеет права сам восстановить RUN и тратить забытые debits.
6. Raw evidence и operationally decorated restored copy различаются: изменение SQLite из-за legitimate restore marker не объявлять ошибкой archived hash и не исключать весь SQLite из проверки.

Минимальный независимый oracle: отдельный scanner `path→size→SHA256` по изолированному root, не тот же shared dict из packager. Semantic oracle: material keys/ROWID/cursors, profile revision/revoke, shared counters, active/tail rows, unresolved attempts, publication recovery и relevant ResearchEvents.

Смешанная цепь old STORED full → new DEFLATE delta → следующий delta должна восстановиться. Старые архивы и их hashes не переписывать. Также проверить full-only, deleted path, changed SQLite, interrupted apply в disposable root.

**Если обнаружена старая неверная inventory binding:** изолировать exact affected scope, сохранить forensic evidence и последнее доказанное восстановление. Не подбирать хэш к получившимся bytes. При невозможности продолжать такую цепь подготовить **один** корректный rebase/full по отдельному operational gate; не массовую пересборку Drive.

### 5.3. Last-good и latest-attempt — разные факты

Не стирать успешную recovery pointer запись неуспешной попыткой. Existing health owner должен различать: last verified checkpoint, его data age/coverage, текущий run и последний failure. «Есть last-good» не означает fresh; «последняя попытка упала» не означает отсутствие всех backup.

Remote verification — через существующий доказанный транспорт/проверяемый checksum capability. Совпадение имени и размера отдельно не доказывает bytes. Для первоначальной приёмки нужен независимый remote content readback и restore выбранной цепи; **не требуется скачивать все исторические архивы ежедневно**. Уровень routine verification и границы доверия точно указать.

## 6. SSD — retirement: убрать ненужный body, не удалить историю

### 6.1. Доказанная принадлежность раньше возраста и размера

Использовать уже сделанное разложение как старт. На одной consistent копии уточнить крупные contributions до достаточного решения. Не повторять весь inventory Drive. По active runtime нужны только bounded metadata и consumer/pin readback.

**Таблица решения:**

| Класс | Действие / защита |
|---|---|
| Legacy decoded provider bodies и duplicate poll-cache | Кандидат на cold archive + provenance-preserving compaction при exact approved retirement |
| `candidate_members` | Сохранить denominator, membership/state/IDs; выносить только действительно дублирующий тяжёлый body, если все readers совместимы |
| Accounting/lifetime/member bindings | Сохранять для всех исторических activations, не только ACTIVE. Не копировать counters в новый «чистый» baseline |
| Profiles/grants/revocations/transitions | Сохранять immutable history и current control; I3 зависит от них |
| STARTED/UNKNOWN attempts; active/tail slots/rounds/outbox/jobs | Не удалять необходимые raw/decoded dependencies; no age-only cleanup |
| Frozen release/export/capture/member-prefix dependencies | Сохранять до verified independent closure и разрешённой retention; PC download не safety prerequisite |
| Retired PAUSED/PENDING legacy | Нужен explicit retirement/disallow-resume record; нельзя превратить в COMPLETE/OBSERVED ради eligibility |
| Orphan owned scratch, завершённые staging | Удалять только после проверки owner/consumer, published replacement и отсутствия текущего процесса |
| Unknown ownership | Named blocker для этого scope; не выбирать по размеру |

**Нельзя:** `DELETE FROM call_ledger`, очистить все PAUSED, удалить `candidate_members` как таблицу, сбросить `accounting_counters/lifetime_counters`, заменить большие JSON пустым success.

### 6.2. Архив один раз, а не в каждой daily copy

Для approved legacy set сохранить один **dependency-complete** cold artifact в существующий независимый sink/Drive, проверить remote bytes и изолированное восстановление. Для случая только SQLite decoded bodies это может быть exact исходный snapshot DB плюс компактный scope/removal manifest; если нужны отдельные raw файлы — включить именно их. Новая система object dedup не нужна.

Архивировать оригинальные сохранённые bytes до изменения. `DECODED_CANONICAL_PROVIDER_JSON_NOT_BYTE_IDENTICAL_HTTP` не переименовывать в raw HTTP. Metadata-compaction хранит исходные occurrence/request/response hashes и archive locator; отдельный hash новой compact projection не подменяет старый response hash.

Cold archive находится **вне routine source selection**. В противном случае мы снова пакуем тот же legacy под другим pathname. Один локальный rescue artifact до приёмки допустим и учитывается в capacity; две папки на одном VPS не являются независимыми копиями.

Конец retention для cold legacy и связанных научных pins выбирается по доказанным consumers и owner policy. Не удалять его через 7/30 дней «потому что новая база маленькая». Срок — один выбор политики, не бесконечная ежедневная ручная церемония.

### 6.3. Episode-aware eligibility и устойчивый resume

Начать с `observation_schedule_retention.py`, расширить применимость, не создавать второй compactor.

- Опираться на occurrence identity и точный scope, а не только совпадающий `request_sha256` или возраст. Shared request может соответствовать разным attempts; compacted body может иметь несколько consumers.
- Учитывать реальные episode `due_observations`/slot states, rounds, outbox, publication jobs, exports, raw/member-chain pins и frozen scientific dependencies. Отсутствие legacy due rows не означает «ничего не нужно».
- Сохранить поля, реально читаемые recovery/diagnostics: в том числе `raw_body_rel`, `entities`, clocks и typed missingness, если они ещё нужны. Универсальное «всё вне PROVENANCE_KEEP_KEYS удалить» здесь недостаточно.
- Не изменять provider state, occurrence IDs, scientific availability или source timestamps. Время compaction хранится отдельно.
- Результат для устранённого body — existing `COMPACTED_PROVENANCE_ONLY` с понятным архивным чтением/typed unavailable; не `[]` вместо реального response.

Plan фиксирует DB/schema identity, exact retired scopes, candidate cutoff/high-watermark, policy revision, archive proofs и exclusions. Чтение — keyset/chunk; summary не удерживает все IDs/payload в RAM. Candidate list может быть streamed artifact; каждый chunk перед mutation заново проверяет eligibility и payload identity под existing fence.

Изменения посторонних active rows не инвалидируют весь plan. Изменение самого candidate, его deps/protection/retirement либо policy — `PLAN_STALE/PROTECTED`, без принудительной записи. Cursor advancement коммитится вместе с effect, либо replay идемпотентен. Не использовать OFFSET на меняющейся таблице.

Начальная форма: стабильный `(original_time, occurrence_id)` keyset или existing row-identity key, с bound на rows **и bytes**. Не читать один очень большой JSON, не проверив размер; при выходе за измеренный memory budget — отдельно ограниченный путь либо typed refusal для этого scope. Размер chunks выбирает executor по копии; сначала existing index/EXPLAIN, новый индекс только для material scan-risk.

## 7. SSD — физический reclaim без потери текущего состояния

### 7.1. Выбор техники

До compaction свободных страниц почти нет по benchmark: сейчас один VACUUM бесполезен. После compaction pages могут стать reusable, но file size останется прежним. Физический reclaim — отдельная проверенная операция.

Предпочтение native SQLite-механизму, если копия доказывает совместимость. VACUUM может менять implicit ROWID и требует временного места; отсутствие проблем primary key не доказывает сохранность ROWID-cursors. [E3]

Если значимые implicit ROWIDs/sequence/lookup identities не сохраняются native operation, выбрать минимальный identity-preserving rebuild нужного store с явным сохранением этих полей и индексов. Не менять всю схему продукта и не строить универсальную миграционную платформу. Решение — executor, на основании реального consumer trace.

### 7.2. Live-порядок после отдельного exact approval

1. Rehearsal на recent копии: время, required disk/peak/RSS, preserved identities, recovery/readback и следующий writer. Получить допустимое maintenance window.
2. Проверить last-good independent recovery, свободный объём на каждом involved filesystem, backup/archive activity и время до due/rollover/B timer. Активный upload не убивать ради deploy/reclaim.
3. Bounded quiesce **всех реальных writers** этого DB и участвующих publication owners. Не использовать бизнес-команду `collection-stop-intake`, если нужна только техническая остановка процесса: она меняет persisted desired state. Исходный RUN и timer states сохраняются для восстановления.
4. Снять final current snapshot и повторно связать plan с actual counters/children/cursors. Старая rehearsal copy никогда не заменяет более свежий live state.
5. Reclaim/rebuild и verify, затем switch по поддержанному same-filesystem atomic path с минимальным recoverable intent. Не копировать открытые SQLite/WAL/SHM наборы вручную. WAL handling — через SQLite при закрытых writers. [E4]
6. Подтвердить schema/indices/integrity, material row identities и sequence high-watermarks, managed profile/revoke/control, authority/account totals, active/tail obligations и root binding.
7. Возобновить прежние services/timers, проверить обычный tick → SEARCH → publication, отсутствие лишних calls и новый корректный backup checkpoint.

Если maintenance не укладывается в безопасную щель между наблюдениями — назвать измеренное окно и честно ожидаемые gaps, получить решение. Не обещать нулевые пропуски или потом заполнять старые slots новыми provider calls.

**Root/inode seam:** DB inode может измениться; `data_root` и его device/inode, закреплённые в frozen envelopes, не должны незаметно смениться. Проверить все фактические lookup/cache/identity consumers. Не редактировать frozen A/B/child envelopes для легализации неожиданного cutover.

### 7.3. Rollback

До возобновления writers при неуспешном switch — возврат exact final pre-maintenance set, если это доказано и текущих новых writes ещё нет. После возобновления/new admissions — **никакого restore вчерашней DB поверх runtime**: forward reconciliation/repair.

Откат backup compression меняет новые записи/настройки, а не переписывает старые ZIP. Новый reader должен продолжать читать mixed chains. Откат maintenance policy не возвращает bodies автоматически в HOT; exact cold archive даёт восстановимость при реальной необходимости.

Запрет I3 на старый binary после первого managed child сохраняется. Даже до child нельзя вернуть несовместимый backup/retention reader после изменения state/schema. Подготовить exact minimum-compatible artifact; не использовать дату как критерий совместимости.

## 8. SSD — один maintenance profile, а не ручная уборка каждую неделю

### 8.1. Минимальная политика

Предпочтительно расширить existing maintenance/retention owner с одной versioned policy в operational plane. Новая таблица нужна только если подходящего owner нет. Не встраивать изменяемые daily limits в Git и не переписывать уже выданный managed grant.

Политика содержит: allowed collection/scopes/classes; retirement permissions; minimum age из применимых frozen contracts; required cold/source proofs; max rows/bytes/wall на run; trigger cadence; concurrency/pressure limits; retained restore points; pause/resume and incident behaviour. Предложение и approval связываются с exact hash/revision.

Для текущих episode raw/body срок не сокращается автоматически: применить действующий lower bound соответствующего schedule/source contract, а не удобные 14 дней из примера parent plan. Изменение HOT/COLD retention — отдельное материальное решение, не настройка компрессора.

**Named consumer:** existing backup/archive/maintenance entry, вызывающий короткий bounded maintenance step. Предпочтительно уже существующий hook/процесс; новый persistent service не нужен по умолчанию. Подключение к установленному unit — часть отдельно разрешённого OPERATE. Отсутствие автоматического caller означает `MAINTENANCE_NOT_COMMISSIONED`, а не DONE.

### 8.2. Поведение под нагрузкой

Maintenance yield при близких due deadlines, чужом writer, неблагоприятной RAM/IO, unresolved restore или active checkpoint. Collector не ждёт многоминутную SQL transaction. Плохой optional maintenance не должен отменять критический backup; backup failure не разрешает разрушительную очистку.

При заполнении диска не включать «агрессивную чистку всех старых файлов». Сначала разрешённые orphan/staging targets; protected dependencies остаются. Затем existing safe intake HOLD/stop и incident. Already accepted tails имеют приоритет; никаких частых произвольных retries provider.

После разового physical reclaim routine compaction освобождает страницы для reuse. Не делать ежедневный VACUUM. Новый physical maintenance trigger нужен только по измеренному reusable/file amplification и допустимому maintenance window.

**Scale acceptance:** при фиксированных incoming rate и retention hot working set не растёт от количества прожитых лет. Scientific history может расти в COLD. Keyset selection, bounded manifests/retained checkpoint graph и pruning предотвращают линейные большие scans в routine path. Не обещать O(1) всей системы.

### 8.3. Reachability перед удалением backup objects

Новая маленькая DB может сначала прийти как delta старой большой full chain. Это уменьшит новый upload, но не удалит зависимость восстановления от старой base. После retirement нужен **один новый проверенный компактный full baseline** в существующем checkpoint owner; не ежедневный full reset.

До pruning old full/deltas построить union references retained checkpoints + explicit scientific/recovery pins + pending operations. Выбранные restore points должны восстанавливаться после удаления остальных. Prune не удаляет новый last-good или независимый legacy retirement archive. Remote deletion — только отдельный exact plan/approved narrow policy, никаких `sync --delete`.

Первый cleanup старых remote generations можно отложить, если он не влияет на безопасный runway; новые routine copies уже не содержат legacy. Но capability/policy для ограниченного дальнейшего роста должна быть подготовлена, иначе backlog бесконечен.

Выключенный ПК не мешает durability: удаление HOT допускается по независимому source/recovery coverage, не по «Пётр скачал». Если source package ещё нельзя доказать, соответствующие rows/files остаются pinned; это точная зависимость от I4, не разрешение удалить их для красивой цифры.

## 9. Freshness: устранить ежедневную ложную тревогу, не скрыть старый backup

**Поправка к текущему framing:** DEFLATE сократит upload, но при запуске раз в 24 часа и hard CURRENT 24h интервал age>24h всё равно возможен при любой ненулевой/переменной длительности. Обещание «сжатие само устранит freshness-проблему» неверно. [G4, G5]

### 9.1. Разделить время данных и время выполнения

В existing receipt/health contract отличать:

- `snapshot_data_as_of` / conservative captured-state lower bound;
- `run_started_at`;
- `uploaded_at` — фактическое завершение upload;
- `verified_at` — фактическое завершение verification;
- last-good checkpoint identity/coverage;
- latest run state/progress/deadline.

Не переписывать старые receipts. Для старого формата — явный compatibility rule: прежний `verified_at`, записанный из start clock, не трактовать как новый completion timestamp. Для нового checkpoint data-age отсчитывается от snapshot, **не от только что завершённой переотправки старого ZIP**.

### 9.2. Рекомендуемая политика для commissioning

Сохранить daily checkpoint и no daily manual action. Подготовить согласованную **effective data-age границу 30h**, если измеренное `24h cadence + package/upload/verify + запас` укладывается в неё. Это рекомендация к одному initial policy decision, не скрытое расширение действующего 24h owner contract.

Новый profile/readiness должен показывать фактический предел: сейчас I3 max-age30h ограничен более строгим off-host CURRENT24h. Не «исправлять» это подменой `CURRENT`. Версионировать владельца политики/адаптацию consumers и отдельно одобрить effective изменение. Старые policies сохраняют старую семантику. Один точный OPERATE decision может охватить согласованные настройки; дальше daily approvals нет.

`IN_PROGRESS` не делает last-good моложе, не разрешает бесконечную grace и не скрывает stalled/failure. Если last-good data-age и coverage допустимы, collector продолжает в одобренном scope; если предел нарушен — новый intake блокируется, реальные tails не теряют полномочия. Last error, stale backup и missing integrity различаются. Не переключаться на LOCAL_BUNDLE ради PASS.

Если жёсткий 24h data-age нужно сохранить, executor предлагает **одну** более частую безопасную cadence после измеренного уменьшения backup, с расчётом дополнительного traffic/IO. Не увеличивать frequency на 5-GB baseline автоматически и не менять расписание до отдельного разрешения.

Acceptance: daily run с длительностью 20 и 110 минут, variable finish, failed/stalled run, skipped day, reboot/retry same artifact, weekly/full overlap и cutover в 00:00/после 00:45. Часы wall определяют actual timestamps; duration/timeouts — monotonic; будущее/невалидное время не объявляется fresh.

## 10. Метрики, budget и достаточная экономика

### 10.1. Пять разных чисел

| Метрика | Что измеряем |
|---|---|
| `resident_hot_bytes` | DB, WAL, RDP и другие принадлежащие Factory resident на конкретном томе; non-overlap |
| `new_useful_source_bytes_per_day` | Реально новые поддерживаемые данные, отдельно рост mandatory metadata |
| `backup_upload_bytes_per_day` | Actual attempted/verified payload, отдельно failed retries/повторное already-present; это не billing truth |
| `retained_remote_bytes` | Reachable retained generations + explicit cold pins, а не сумма всех исторических загрузок |
| `peak_transient_bytes_by_phase` | Одновременный snapshot/ZIP/reclaim/archive staging на каждом filesystem |

Снимать before/after в сопоставимом scope. GB=10^9, GiB=2^30; в machine data — bytes. Освобождение локального source после remote upload не добавляет свободное место на другом томе.

Формула peak:

```text
peak(t) = nonoverlapping_resident(t)
        + simultaneous_transient_of_allowed_jobs(t)
        + admitted_but_not_materialized_obligations(t)
        + explicit_error_margin
```

Не суммировать независимые maxima snapshot/upload/vacuum как одновременные и не прятать реальный overlap разных timers. Temporary SQLite outside RDP и weekly full+daily delta должны учитываться. Если current I3 footprint owner их не видит — minimal consumer repair входит в I2; ещё один независимый storage calculator не создавать.

### 10.2. Чего ожидать, не выдавая модель за факт

При **гипотетическом** whole-checkpoint ratio 6×: `5.225 / 6 ≈ 0.871 GB`. Только network часть прежних 60–110 минут при неизменном throughput стала бы примерно 10–18 минут; capture, compression, verify, competing I/O и rate variance добавляются. Ни 20 минут, ни освобождение 94% DB не являются SLA/DoD до замера.

Выбор DEFLATE принимается, когда restore invariants проходят, reduction кратная и нет material ухудшения due-slot coverage/ресурсного запаса. Не тратить время на подбор десяти уровней ради последних процентов. Если целый snapshot сжимается неожиданно плохо — один раз уточнить contribution; не сразу менять платформу.

**После retirement:** вклад exact retired bodies в uncompressed logical payload новых snapshots = 0. Mandatory historical metadata/counters остаются и честно считаются. Подтвердить новый уменьшенный DB-file и обычный backup; freelist/сжатый ZIP не подменяют это доказательство.

### 10.3. Горизонт месяцев

Дать модель 7/30/180 дней с измеренным ростом, HOT/COLD/backup retention, счётчиком файлов/inodes и разрешённым overlap. Недоказанные I4 lifecycle/архивные зависимости не считать устранёнными. 100-недельный time-advanced metadata сценарий — только если нужен для проверки bounded selection, без генерации сотен GB raw.

`MONTHS_RUNWAY_SUPPORTED` — модель при заданных assumptions и automation, не полгода runtime proof. Если raw/RDP/cold policy не ограничены и реально доминируют — назвать точное I4 действие; не заявлять бессрочность из маленькой SQLite.

## 11. Проверка: сценарии эксплуатации вместо TDD ради количества

Existing tests/CLI/fixtures — первый путь. Новые durable checks только на непокрытые material risks; можно расширять существующий suite. Реальные provider calls в тестах отсутствуют. Runtime контроль использует обычный collector, не искусственные дополнительные запросы.

| Риск | Дешёвый oracle / достаточное доказательство |
|---|---|
| Snapshot A/B расхождение | Concurrent writer между inventory и pack; extracted SQLite hash/semantic rows равны одному captured state |
| Entry остался STORED | Inspect central-directory большого entry, реально compressed bytes, независимое извлечение |
| Mixed chain / ложный restore PASS | STORED full + DEFLATE delta + changed/deleted paths; actual result inventory. Missing/reordered delta и wrong expected hash отказывают |
| Потерян restore marker | Последняя delta заменяет SQLite; после raw verification marker unresolved в final operational copy; tick не делает provider calls до reconciliation |
| Kill после upload, до pointer | Новый процесс завершает тот же checkpoint; last-good не потерян, повтор не создаёт другой snapshot/chain |
| Local/weekly/daily collision | Два callers, один admitted backup operation; остальные bounded defer, no lost artifact/no duplicate full |
| Неизвестный remote результат | Reconcile exact object/checkpoint; no blind recapture; failed run не омолаживает last-good |
| Unsafe retention | Active/tail/UNKNOWN/round/outbox/export/managed/account pins защищены; retired body удалён, provenance/denominator прежние |
| Partial compaction / crash chunk | Повторяет тот же plan/cursor, без потери/двойного effect; changed candidate отказывается |
| Physical reclaim ломает IDs | Independent key/ROWID/sequence/cursor fingerprints до/после, exact pending recovery, следующий native writer |
| Cleanup подделывает здоровье | Original source clocks/status неизменны; compaction timestamps отдельны; stale source не становится fresh |
| Неполная source backup closure | Restored A/managed-child authoritative state и required events читаются без VPS; непокрытый raw scope явно назван и не очищен |
| Storage вне RDP / temp leak | Real topology на disposable root, sibling DB/WAL/backup/temp и разрешённый overlap учтены, repeated failures не растят orphan staging |
| Cadence / freshness | Approved data-age semantics на 24h boundary и variable upload; stale/corrupt не допускаются, штатное окно не требует ежедневного repair |
| Автоматизация только «на бумаге» | Installed caller/policy readback + один ordinary maintenance cycle после restart; no ad-hoc agent step |

**Regression acceptance** переиспользует I1 release verification, I3 shared-account/standing-grant/rollover/stop semantics и affected backup/watch checks. Не запускать I1 production re-import, полную Forge-науку или полный disaster drill для каждого микроизменения.

**Targeted mutation** по необходимости: убрать comparison result inventory; reread live SQLite вместо snapshot; стереть archive pin; reset counter/marker; treat STARTED as eligible. Проверка должна действительно отличить broken behaviour, а не повторять формулу реализации.

## 12. Runtime rollout и authority без лишних остановок

### 12.1. До merge

EXECUTE разрешает task-local implementation, isolated copies, fixtures/benchmark, needed contracts/Catalog, обычную ветку/PR/CI по current harness. Разрешение не распространяется на SSH writes, deploy, uploads, новые timers, live compaction/reclaim, managed-profile changes или удаление remote chains.

Если для достоверного rehearsal нужна существующая backup-копия, executor сначала использует доступную approved local copy. При отсутствии — один narrow доступ/download нужного checkpoint closure через отдельный текущий read/external gate, не весь Drive. Работа на synthetic counterparts продолжается независимо от этого.

### 12.2. Первое внедрение

После exact merge/readiness/owner phrase и post-merge readback подготовить **один OPERATE packet** с этапами:

- exact deploy совместимого packager/reader, что default-off в destructive maintenance;
- существующий normal backup и независимый restore; после его PASS можно принимать упаковочный выигрыш;
- exact archive/retirement/reclaim plan: target scopes, bytes, protected exclusions, archive/restore proof, bounded writer window и rollback;
- один approval узкой recurring maintenance policy и необходимого existing caller/config;
- новый compact full baseline и reachability-safe local/remote pruning в пределах отдельно granted scope;
- actual readback collector/I3, ordinary backup/maintenance and Telegram incident/recovery delivery через existing TEST path, если direct consumer изменён.

Это перечисление разных прав, не требование шести отдельных фраз: совместимые действия можно включить в один exact packet по current policy. Не просить отдельный approval на generated JSON/локальный SQL-step. Destructive first APPLY и live scope остаются явными.

### 12.3. B/I3 и календарь

По последней отбивке B уже взведена, managed profile применён. **Не ждать 18 октября для начала I2.** Даты ниже — контроль фактических событий, не deadline для unsafe merge/reclaim.

- 17.10 около **03:20 МСК**: readback B и сохранности A-tail.
- 18.10 после **03:00 МСК**: первый managed child; 19.10 — следующий.
- Не проводить physical cutover или risky backup/deploy прямо на этих границах. Длинная операция требует measured window, а не «должно успеть».
- Если packaging готов раньше retirement/reclaim — применить независимый безопасный результат; тяжёлый reclaim не задерживает сбор и не превращает compression-only в DONE.
- Если работа возобновилась после указанных дат, сначала live state; никаких ручных C/D и действий задним числом.

## 13. Durable propagation и эксплуатационные ограничения

В том же атоме обновить только actual owners: backup manifest/receipt meanings, restore/version compatibility, retention eligibility/CLI/read-only behaviour, recurring policy/caller, status/alerts/capacity, нужные Catalog routes. Новый агент должен найти точный resume через AGENTS/semantic map, не через этот чат.

Не дублировать PRD, SSD, 200-step audit и отдельный shadow state. Этот документ — единый design input; task связывает exact executable scope. Runtime grants, IDs/часы, private backup files и current measurements не коммитятся как механизм управления VPS.

Unknown не снимается декларацией. Например, `LOCAL_BUNDLE` не равен независимому off-host restore; исправный checksum одного payload не равен всему checkpoint; silent cleanup не равен успешному maintenance; «нет новых ошибок» не равно сохранению source denominator.

## 14. Handback для одного тактического решения

Один `OWNER_READOUT` + existing hash-bound receipts. Достаточно следующего:

```text
I2_BACKUP_LEGACY_STORAGE_V1 / stage / exact scope
OUTCOME: CODE_READY_RUNTIME_PENDING | PACKAGING_LIVE_PROVEN |
         STORAGE_AND_MAINTENANCE_LIVE_PROVEN | PARTIAL | BLOCKED

FACT: exact head/deployed, source checkpoint, policy rev, observed time.
BEFORE→AFTER:
  DB/WAL, logical legacy/current/provenance bytes,
  compressed archive, upload/retained remote bytes,
  phase peak, wall/RSS, collector delay/gaps.
CORRECTNESS:
  single snapshot + inventory identity; mixed chain reconstruction;
  restore marker after final delta; preserved keys/counters/profile;
  cold retirement archive; exact compacted scope; next native writer.
AUTOMATION:
  installed caller; approved scope; resume/idempotence;
  next routine run; no daily owner/agent step.
RECOVERY: last-good/new checkpoint, rollback boundary and residuals.
AUTHORITY: performed / not performed; exact next gate if any.
RUNWAY: 7/30/180d estimate, assumptions, retention pins, I4 dependency.
NEXT: one recommended action + exact resume; what NOT to repeat.
```

Не принимать I2 целиком, если только compression ratio PASS. Финальный результат требует исчезновения retired body из новых routine copies, физического эффекта и commissioned maintenance. Ждать очередного обычного run можно со статусом `AWAITING_ROUTINE_BACKUP`; независимая следующая работа не простаивает.

## 15. Стартовая команда исполнителю — передать сейчас

```text
SMIAL — EXECUTE I2_BACKUP_LEGACY_STORAGE_V1.

Прими приложенный I2_BACKUP_LEGACY_STORAGE_V1_PRD_SSD.md как единый
PRD+SSD и продолжение §5 исходной программы. Current AGENTS.md,
semantic routes, Git policy и exact machine evidence сохраняются.
NEXT_MODEL_EFFORT: SOL_XHIGH.

Outcome — не только DEFLATE: один consistent snapshot на checkpoint,
правильный full/delta restore, устранение routine legacy amplification,
episode-safe retirement и physical reclaim, затем автоматическая
maintenance по узкой policy. Existing owners; никакой новой платформы.

Уже работающие A, авторизованная/взведённая B и APPLIED managed profile
защищены. Не сбрасывать shared accounting, не переписывать grants,
C1/C2/denominator и не менять provider/scientific workload.

Переиспользуй известный benchmark. Сначала точные falsifiers из §1.2
и §11; затем coherent implementation и rehearsal на isolated snapshot.
До runtime можно автономно реализовать все необходимые seams,
контракты/CLI/caller и подготовить один staged OPERATE packet.

Доведи до reviewed exact-head CI и machine merge-readiness.
Первый STOP — exact merge phrase либо material blocker.
Deploy, uploads, destructive APPLY, recurring-policy enable и
изменение effective freshness/retention требуют своих exact gates;
никаких live mutations по одному этому EXECUTE.

Handback — §14. Непройденные обязательные части не переименовывать
в non-goals. Можно заранее отдать готовый independent packaging
результат, если это materially защищает runtime, но I2 остаётся
незавершённой до legacy/reclaim/maintenance outcome.
```

## 16. Источники и проверяемость

**[P] Parent, предоставлен владельцем:** `SMIAL_Managed_Collection_Operability_PRD_SSD_V1_2026-10-13 (1)(1).md`, §5; совместимость §3, §6–7, §9–12. Отсюда outcome полного I2, запрет косметической delta, сохранение science/debt, source pins и staged authority.

**[R] Последние переданные runtime handbacks, 15.10.2026:** PROFILE APPLIED rev1, A/B/managed timings, FRESH off-host, STORED archive 7932 entries/≈5.225 GB, длительности upload и preliminary table/compression benchmark. Нового SSH/readback и нового compression benchmark Project Chat не выполнял.

**Git anchor всех G-ссылок:** `b3fb9d8ecffbffda468dccabaa81ca3392da6f15`, прочитан 15.10.2026.

- **[G0]** [AGENTS](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/AGENTS.md), [semantic map](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/docs/FACTORY_SEMANTIC_MAP.md). Authority/entry; не live health.
- **[G1]** [remote_ops.py](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/src/solana_alpha_lab/factory/remote_ops.py): `_stream_zip_entry`, `BackupPayloadSnapshot`, `scan_backup_inventory`, full/delta packagers, pruning; прочитаны relevant ranges 100–280, 650–1120, 1140–1575.
- **[G2]** Тот же `remote_ops.py`: `restore_backup_isolated`, `apply_delta_bundle`, `restore_incremental_chain_isolated`; [offhost_backup.py](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/src/solana_alpha_lab/factory/offhost_backup.py): `restore_from_recovery_checkpoint`, `run_offhost_checkpoint`, chain publication; relevant ranges 980–1485.
- **[G3]** [retention owner](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/src/solana_alpha_lab/factory/observation_schedule_retention.py) и [CLI](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/scripts/observation_schedule_retention.py), прочитаны целиком relevant retention path.
- **[G4]** [offhost_backup.py](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/src/solana_alpha_lab/factory/offhost_backup.py), включая receipt из captured run clock; [remote config](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/configs/factory_remote_operations_v1_1.yaml), 24h/48h freshness и source/channel definitions.
- **[G5]** [managed_collection.py](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/src/solana_alpha_lab/factory/managed_collection.py#L566-L660): footprint и `read_verified_backup`. Current backup adapter требует owner CURRENT; profile max-age сам по себе его не отменяет.
- **[G6]** [opportunity_episode_tick.py](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/src/solana_alpha_lab/factory/opportunity_episode_tick.py#L324-L347): `_load_raw_body`, `_ledger_payload`.
- **[G7]** [pyproject.toml](https://github.com/lancerbeta/solana-alpha-lab/blob/b3fb9d8ecffbffda468dccabaa81ca3392da6f15/pyproject.toml): Python/uv constraints.

**Внешние primary references, проверены 15.10.2026; только технические свойства, не SMIAL runtime proof:**

- **[E1]** [Python 3.13 zipfile](https://docs.python.org/3.13/library/zipfile.html): per-entry compression/`compress_level`, ZIP64, `testzip` limitations. Это не рекомендация обновить pinned Python.
- **[E2]** [SQLite Online Backup API](https://www.sqlite.org/backup.html): consistent online snapshot, stepping; не атомарный multi-store checkpoint.
- **[E3]** [SQLite VACUUM](https://www.sqlite.org/lang_vacuum.html): physical rewrite, space и ROWID caveats; решение о live reclaim требует actual copy proof.
- **[E4]** [SQLite WAL](https://www.sqlite.org/wal.html): WAL — часть состояния БД; его нельзя произвольно отделять при замене DB.

**Truth boundary:** документ спроектирован; product code, backups, compression benchmark, live profile, retention/reclaim и внешние записи в этой работе не изменялись. Proposed interfaces/policies должны получить canonical implementation и exact runtime evidence. I3 APPLIED не равен `MANAGED_CONTINUITY_LIVE_PROVEN`, а I2-storage PASS не является научным или торговым результатом.
