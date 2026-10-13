# SMIAL — управляемая эксплуатация Opportunity Episodes

**PRD + SSD + итерационный контракт исполнения · V1 · 13 октября 2026**  
**Program ID:** `SMIAL_MANAGED_COLLECTION_OPERABILITY_V1`  
**Режим документа:** DESIGN. Реализация и эксплуатационные действия выполняются по отдельно выбранной итерации и действующей Git authority.

> **Результат:** работающий Jupiter collector не требует ручной регистрации когорт и постоянных разрешений на технические микрошаги. Пётр задаёт режим и допустимый ресурсный риск. Система измеряет, применяет, автоматически продолжает разрешённый сбор, защищает уже принятые обязательства, восстанавливается после обычных сбоев и сообщает о проблемах. По одной просьбе данные догружаются до честного Forge readiness. Старое содержимое SQLite не размножается ежедневно в нескольких гигабайтных копиях.

## Как пользоваться

Документ предназначен для Петра, Project Chat и coding executor. Он самодостаточен для постановки программы; current Git и machine readback остаются владельцами реализации и live state. Исполнитель не должен перечитывать старые чаты или просить Петра выбирать JSON, SHA, SQL либо внутренний путь.

Начать с §0–3, затем выполнить **только выбранную итерацию** из §4–8. Прочие итерации задают совместимость и следующую цель, а не дают разрешение на все будущие записи. Общие verification, authority и handback — §9–12. Готовая стартовая команда — §13.

Это **пять проверяемых результатов, не пять обязательных PR**. Внутри итерации локальные проектирование, код, проверки и подготовка применения идут без искусственных остановок. Exact merge, production deploy, новые provider/grant scopes и destructive APPLY сохраняют реальные границы разрешения. После результата итерации — одна отбивка для Chat/Петра и выбор следующего шага.

---

## 0. Решение и изменения относительно тактического runbook V2

### 0.1. Что сохраняем

Исходный план от 11.10 остаётся смысловой основой: закончить доставку canary, использовать новый поток, экономить storage/backup, снижать ручную нагрузку, довести данные до Forge и провести один отдельно разрешённый контролируемый научный проход. Сохраняем разделение operational fit, research fit и economic fit. Ни импорт, ни удобство управления, ни CI не являются alpha. [S1 §§0, 6, 10]

### 0.2. Что меняется по новым решениям владельца

| Раньше / обнаруженная проблема | Решение этой программы |
|---|---|
| Подготовка нового окна 14 → 7 → 5 → 4 дня ради TARGET | Разделить рекомендованный TARGET, действующий HARD, физический резерв и решение об активации. TARGET допускает точное ограниченное принятие риска владельцем; ложный PASS запрещён |
| Число 100 в коде как универсальный потолок | Для нового managed path численные лимиты — runtime policy плюс измеренная допустимость, а не PR на каждое число. Историческая семантика V1 сохраняется |
| Каждое окончание intake требует нового ручного commissioning | Один ограниченный standing grant на режим/период; система сама готовит и исполняет разрешённые successor schedules. Не выдаёт себе новые полномочия |
| Повторная доставка ломается на растущем `unit.json` | Frozen capture получает воспроизводимое представление источников; следующий capture не разрушает предыдущий |
| Ежедневная DELTA переносит целую ~5 GB SQLite | Сначала исправить упаковку и её snapshot consistency, затем вывести ненужный legacy из HOT и из новых backup chains. Не ограничиваться косметическим сжатием |
| «Retention APPLY отсутствует» | Уточнение: найден отдельный native `observation_schedule_retention.py` с `status/dry-run/apply`. Его нужно переиспользовать/исправить, а не создавать второй compactor |
| Все ошибки требуют ручной реакции | Развести ожидаемый idle, безопасный retry, деградацию, stop-intake/drain и настоящий integrity incident; оповещения через существующий Telegram-контур |
| ПК должен вовремя скачать raw | Source durability и retention не зависят от включённого ПК. Отложенный catch-up поддерживается в явно заданном cold retention window |

**Это новые требования к продукту.** Они не означают, что соответствующие возможности уже реализованы или что текущую activation разрешено переписать.

### 0.3. Основной выбор архитектуры

Рекомендуется **ремонт существующих owners с одним небольшим runtime-контуром управления collection**. Не новая платформа, не отдельный orchestration framework, не перевод runtime в Git.

Альтернативы рассмотрены:

- Оставить всё как есть и писать подробные команды агенту: самый дешёвый сегодняшний обход, но он сохраняет зависимость от чата и следующие ручные остановки. Не соответствует outcome.
- Строить новую БД, backup service и отдельный scheduler: больше миграционного риска, компонентов и обязанностей владельца. Для установленных проблем не требуется.
- Переиспользовать имеющиеся SQLite, timer, archive, release, ResearchStore и notification owners, исправив реальные границы: **выбрано**.

---

## 1. Checkpoint: что известно и что ещё не доказано

### 1.1. Источники и свежесть

**Git design anchor:** `339c50dabe128a4c672028141f93d214152b6252`, прочитан 13.10 через GitHub connector. Entry: `AGENTS.md` → `docs/FACTORY_SEMANTIC_MAP.md` → owners. Переход main на новый SHA сам по себе не требует deploy; проверяется relevant dependency closure. [G0]

**Runtime ниже — из переданных отчётов исполнителя, не новый live probe Project Chat.** Перед изменениями executor проверяет exact receipts и фактическое состояние. Особенно нельзя считать плановый readback на 02:18Z уже состоявшимся.

| Объект | Reported state | Граница вывода |
|---|---|---|
| Новый collector | Schedule зарегистрирован, авторизован, ACTIVE; до 13.10 02:00Z — `NOT_YET_ACTIVE`, calls=0 | Реальные новые admissions/SEARCH ещё не подтверждены приложенным readback |
| Intake | 13.10 02:00Z → 17.10 00:00Z | Это ограниченное окно, не standing grant |
| Expiry | 20.10 01:05Z | Не разрешает новые admissions после stop intake |
| Producer | `4378c5b82f2dc309ccd629b267affd5d19b34995` | Перепроверить deployed bytes; не обновлять ради нового main |
| Новый schedule | `4744d4017ac4b19625c5ee11ce4e20fdd4b36c6744f8c0889467052e2a6ef23c` | Activation `ACT-4744D4017AC4B196` |
| Storage envelope | `fa6450ba0fd9da64fa3792c8b5de0c22aacf948589f7e9b1e8e78ae236b8dcad` | Current frozen binding не менять задним числом |
| Storage | MODEL peak 40.69 GB; свободно ~77.3 GB; reserve ~28.7 GB | Модель не measurement будущей нагрузки; GB и GiB не смешивать |
| C1 | 24 episodes, 3336 point pairs; exact import replay и cold file verify PASS | Scientific looks=0 в этом delivery scope |
| C2 | 23 episodes, mature; `MIRROR_CONFLICT` на дневном `unit.json` | Sealed/imported C2 release отсутствует |
| Durability C2 | Producer + VPS recovery + ПК staging + Drive source package | Две VPS-директории — один failure domain; source package ≠ готовый release |
| Backup | SQLite ~99.80%; full/changed-file DELTA ~5.1 GB; 11.10 upload ~10.22 GB | Upload, resident bytes и transient peak — разные метрики |
| Forge | `BLOCK_FORGE_SELECTION_RISK`, `MARKET_EPOCH_CONTINUITY_UNRESOLVED` reported | После новых imports/code перепроверить; не считать диагноз вечным |

Для C1 сохранить anchors из S1 и receipt `13a5c91cfa7a7e52595ec938a49124f536786a9ee0ce337029b5e7f62ea2ac15`. Release: `1128cbcad55e4f11f666722d5b967b1aa5b3c8624ca3dfb9d02981c5651fe47c`.

Canary schedule: `2bfb07b6862365df825220811b63d20e045e085b9a51ffd24e1a935456df1be0`; activation `ACT-2BFB07B6862365DF`. Targets:

```text
C1 = REL-20261007T000000Z-20261008T000000Z
C2 = REL-20261008T000000Z-20261009T000000Z
24 × 139 = 3336; 23 × 139 = 3197; 47 × 139 = 6533 point pairs
```

Операционная точка продолжения: `local/canary_exit_and_100_per_day_arm_v1/20261013_resume/EXACT_RESUME_POINT.json`; конкретный reproducer: `c2-stop-receipt.json`. Эти имена — locators из отчёта, не доказательство наличия файлов в любой новой checkout.

### 1.2. Что проверено непосредственно в коде

1. `add_member_location_entries()` переносит `unit.json` вместе с нужным prefix publications; общий mirror проверяет exact file hash. Это объясняет межкогортный конфликт растущего индекса. [G1]
2. `scan_backup_inventory()` создаёт SQLite backup для inventory; `package_delta_backup()` снова создаёт SQLite backup при упаковке. Общий `BackupPayloadSnapshot` сейчас относится к publication-job files, не ко всем SQLite. **Риск расхождения snapshot A/B под concurrent writer требует targeted reproducer; факт повреждения текущей backup chain не установлен.** [G2]
3. DELTA использует `ZIP_STORED`, переносит весь изменившийся файл; локальный SQLite snapshot в delta packager удаляется в `finally` после записи entry. Утверждение «он обязательно живёт все 40–60 минут upload» кодом этого участка не подтверждается. Пиковое сосуществование snapshot и ZIP всё равно возможно. [G2]
4. `observation_schedule_retention.py::apply_retention` существует. Однако eligibility сканирует `call_ledger.payload_json` через `fetchall()` и проверяет legacy `due_observations`. Это не доказанная episode-safe и memory-bounded очистка активной системы. CLI `status` дополнительно повторяет evaluation. [G3]
5. TARGET=40 GiB, HARD=50 GiB; прогноз различает `DEGRADED` и `ACTION_REQUIRED`, но commissioning требует строку `factory_storage_gate == PASS`. Штатного scoped target risk acceptance в этом owner нет. [G4]
6. Текущий profile: 100/day, rolling100, active400, batch100, 3s pace, 1200 calls/day. Dispatch proof ограничен этим workload envelope. [G5]
7. Есть renewal owner, archive timers, local watch, daily pulse и provider-neutral heartbeat hook. Их наличие не доказывает episode handover или настроенный off-host deadman. [G6, G7]

**Следствие:** нет оснований повторять широкий аудит. Есть конкретные seams и достаточно owners для ограниченных ремонтов.

### 1.3. Реальные неизвестные, которые снимаются в работе

Первый live readback нового режима; полнота source package C2; exact SQLite size decomposition; memory/CPU/I/O budget host под совместной нагрузкой; возможности безопасного физического reclaim с сохранением ROWID/cursors; текущая конфигурация Telegram/deadman; актуальная research/protection continuity; наличие пригодного supply для повышения cap. Для этих пунктов не подставлять значения по памяти.

---

## 2. PRD: какой продукт должен получиться

### 2.1. Основные owner journeys

| Просьба Петра | Система делает сама | Что видит Пётр |
|---|---|---|
| «Продолжай текущий сбор в разрешённом режиме» | Проверяет standing grant, capacity, source protection, deadlines; готовит successor и переносит ownership intake | Подтверждение принятого режима; далее только проблемы / согласованная сводка |
| «Проверь, можно ли 500/day на полгода» | Планирует источник, calls, deadline bursts, tail, storage/backup/retention и ресурсы; измеряет недостающее в разрешённом scope | Один recommendation: допустимо, нужно ограниченное probe, либо конкретный bottleneck |
| «Применяй проверенный режим» | Делает runtime revision и безопасный cutover, создаёт внутренние IDs/receipts | Когда реально действует, что изменилось, как отменить |
| «Верни прежнюю нагрузку» | Создаёт новую ревизию прежних настроек; прекращает лишние новые admissions; сохраняет обязательства уже принятых | `ROLLBACK_APPLIED` или `DRAINING_TO_LIMIT`, без PR |
| «Забери готовые данные» | Разрешает roots/IDs, восстанавливает pending transfer, доставляет все допустимые зрелые когорты в bounded batch, verify/import/preflight | Получено N cohorts / M episodes; что готово для Forge и что конкретно заблокировано |
| «Что не так?» | Читает текущую истину и последний incident, предлагает safe action | Одна понятная причина, воздействие, автоматическое действие и следующий шаг |

Встроенные технические registration/authorization receipts остаются. **Ручная регистрация каждого объекта исчезает.** Не требуется Telegram-командный бот, новый dashboard либо постоянно работающий ПК.

### 2.2. Product DoD программы

**OPERABILITY_ACCEPTED** требует поведения, а не наличия команд:

- C1 и C2 доступны как точные immutable releases; история C1 и научный бюджет не изменены.
- Обычная повторная доставка и восстановление после transfer interruption выполняются свежим агентом без скрытых сведений из чата.
- Routine backup не переносит повторно retired legacy payload; реальные размер, время, peak и восстановимость подтверждены. Новые полезные данные продолжают защищаться.
- Существующий 100/day режим может продолжаться внутри одного разрешённого management envelope, в том числе при overlap successor intake и predecessor tail, без ручных IDs и сброса quotas.
- Численные настройки supported workload меняются/откатываются operationally. Повышение выше 100 демонстрируется на безопасной fixture/model path; live повышение — только по отдельному разрешению и измерениям.
- TARGET warning не маскируется под corruption/STOP; HARD/physical reserve/protection/integrity остаются обязательными ограничениями.
- При обычных сбоях автоматический safe recovery ограничен и наблюдаем; при серьёзных проблемах приходит actionable Telegram incident. Смерть VPS покрыта внешним watcher либо отдельно заявлена как неподтверждённая часть.
- После on-demand import есть metadata-only readiness по фактическому corpus. Технический blocker не выдаётся за отсутствие alpha.
- Нужные maintenance/retention scopes работают по утверждённой политике, не требуют еженедельного ручного списка файлов.

Целевой owner burden после выхода: **минуты, ориентир до 10–15 минут в неделю вне исследований**. Это acceptance target, не обещанный результат до недельного наблюдения. В неделю initial commissioning допустима большая нагрузка; каждый повторяющийся ручной шаг фиксируется как конкретный defect.

### 2.3. Non-goals

Не менять provider/network, capture population/floors/grid/point meanings, sampling seed или holdout roles ради производительности. Не вводить распределённый scheduler, новую БД, второй collector, универсальный gate override, WAL shipping, самописные page deltas, новый Telegram bot либо blanket rewrite legacy-модулей. Не запускать trading, signer, real money. Не строить генератор гипотез. Не обещать реальные 500/2000 admissions/day только по наличию диска.

---

## 3. SSD: общая модель и инварианты

### 3.1. Минимальная топология

```text
Пётр / executor
    → existing CLI: plan → approve/apply → status/rollback
    → одна collection runtime policy в existing operational store
    → existing scheduler / один account execution lane
         → admissions + frozen episode obligations + outbox/publications
         → existing archive/backup/maintenance owners
         → existing watch → Telegram / existing external heartbeat hook

ПК по запросу:
    resolve next ready cohorts → exact source view → verify/seal/import
    → metadata-only Forge preflight → отдельно разрешённая science operation
```

Для нового durable state предпочтительна существующая `observation_schedule_state.sqlite`; reader projections и command receipts не становятся вторым authoritative owner. Паттерн runtime revisions/idempotent commands уже есть в репозитории, например TradingRuntimePolicy. Переиспользовать идею/небольшие helpers, **не связывать collection с PaperPlane и не выделять общий policy framework ради симметрии**. [G8]

### 3.2. Три разных вида ограничений

| Вид | Пример | Поведение |
|---|---|---|
| Semantic / integrity invariant | PIT clocks, отсутствие повторного admission, frozen hashes, protected scopes | Не допускает operational override |
| Feasibility / safety constraint | физический free space для tail, доступные RAM/IO, deadline feasibility, provider route limits | Измеряется; непроходимое или неизвестное критическое условие блокирует расширение |
| Owner operating policy | 100/day, рекомендуемые 40 GiB, разрешённые 50 GiB HARD, сроки/retention/бюджет | Versioned runtime setting; меняется по разрешению и проверке, без PR внутри supported semantics |

**HARD остаётся жёстким относительно действующей policy.** Сам размер owner HARD не должен навсегда быть литералом Python: будущая обоснованная смена, например на другом томе, — explicit plan/apply с проверкой физики. Временно игнорировать текущий HARD запрещено. TARGET acceptance не расширяет HARD.

### 3.3. Что frozen, что меняется

Frozen: опубликованные admissions, T0, schedule каждого принятого episode, call/attempt identity, прошлые releases, scientific trial/exposure, source protection. Mutable/versioned: намерение продолжать сбор, будущие quantitative limits, выбранный operational profile, risk acceptance, состояние transfer/job/maintenance.

Runtime revision применяется к **будущим** admissions. Старое наблюдение не пересчитывается, уже принятый хвост не укорачивается, новый grant не сбрасывает weekly/rolling/lifetime accounting. Смена settings не является исправлением старой истории.

### 3.4. Безопасный откат — не путешествие назад во времени

`rollback` создаёт новую команду/ревизию с прежними settings. У новых уже допущенных episodes остаются прежние обязательства. Если 500/day уже создали больше active episodes, чем допускает старый режим100, состояние — `DRAINING_TO_LIMIT`, а не искусственное active≤400 или удаление jobs. Emergency stop выключает intake, **не управление текущим tail**.

Откат конфигурации обычно не требует Git. Откат несовместимого кода после schema/data migration может требовать forward repair; приложение не должно обещать «вернуть старый бинарник» без проверки совместимости.

### 3.5. Work sizing и checkpoint

| Итерация | Outcome | Зависимости | Предпочтительный тип |
|---|---|---|---|
| **I1** | C2 доставляется, old/new captures воспроизводимы | Existing C2 source, intact C1 | Bounded consumer repair + разрешённый live consume |
| **I2** | Backup amplification и ненужный HOT legacy устранены | Verified backups; I1 нужен для удаления canary dependencies | Repair existing backup/retention + staged OPERATE |
| **I3** | Runtime limits, rollback и непрерывный authorised intake | Базовые измерения I2; не обязательно ждать дорогого reclaim | Один coherent policy/lifecycle capability + commissioning |
| **I4** | Автономные durability/alerts/catch-up до Forge ready | I1; подходящие I2/I3 owners | Existing paths closure; code только по конкретному gap |
| **I5** | Проверен реальный research ingress; один ограниченный результат после grant | Корпус и настоящий Forge readiness | Native OPERATE/science; repair только сломанной границы |

Приоритет времени: reported intake заканчивается **17.10 00:00Z / 03:00 МСК**. Проверка continuation за 72h — **14.10 00:00Z / 03:00 МСК**, а не 15-го. К **15.10 12:00 МСК** должен быть исполнимый successor plan либо один конкретный blocker/ограниченный bridge. Не ждать конца всех пяти итераций для решения о следующем окне.

Если I2 physical reclaim или научный repair грозит сорвать эту дату — `REORDER`: I3 continuity раньше оставшейся очистки. Не выпускать пять emergency suffix PR и не превращать существующий одобренный collector в тестовый стенд. Запускать next schedule только по фактическим gates/authority; даты здесь — контрольные точки, не обещание готовности кода.

---

## 4. I1 — восстановить обычную доставку, а не замаскировать `MIRROR_CONFLICT`

**Outcome:** одна owner-команда доставляет C2 и следующие когорты; расширение дневного индекса не ломает точный replay старого capture. C1 release и science history неизменны.

**Entry:** `PATCH`. Точные source bytes/receipts доступны по reported locators. До кода проверить их наличие и hashes. `MIRROR_CONFLICT` не снимать вручную на canonical mirror.

### 4.1. Root cause и граница ремонта

Источник индексирует publications в `datasets/members_snapshot_plus_delta/<UTC-day>/unit.json`. Индекс растёт; payload publications сохраняют свои identities. Текущий transfer использует один mutable pathname как будто это immutable object. C1 захватил 8 publications, C2 требует 24. [O2, G1]

**Не рекомендуемый final fix:** «разрешить перезапись member_unit, если новый список начинается со старого». Это может пропустить C2, но следующий replay C1 с прежним transfer manifest встретит уже другой SHA. Кроме того, prefix списка сам по себе не проверяет schema/anchor, binding chain и bytes файлов.

В этой программе identity делится на:

```text
cohort / frozen closure identity — научная граница набора
capture / transfer identity      — конкретные bytes транспортного снимка
release identity                — sealed scientific dependency closure
```

Различие не даёт права менять closed source content. Старый transfer receipt остаётся читаемым; новое transport-представление не подменяет его задним числом.

### 4.2. Рекомендуемое устройство

**Небольшой capture-scoped source view** в существующем mirror/export owner. Отдельно сохраняются изменяемые metadata bytes конкретного capture; неизменяемые payload переиспользуются после hash verification. Это не новый data lake или глобальный CAS store.

Рабочая модель путей, не обязательные новые canonical имена:

```text
existing_mirror/
  captures/<capture_identity>/source/   # view с исходными relative paths
  ...existing shared immutable payload...
existing_sealed_releases/<cohort>/<release>/
```

Разрешены обычные файловые копии. Hardlinks/reflinks — только как необязательная оптимизация действительно immutable payload, с Windows/Linux fallback; **не связывать hardlink с mutable `unit.json`**. При текущих десятках MB простая копия часто дешевле сложного dedup. После complete release и независимого восстановления временное view может очищаться по owned retention; маленький packet и material metadata versions сохраняются.

Для каждого capture должны выполняться четыре свойства:

1. Полученный `unit.json` соответствует exact hash в его manifest; последующие captures не меняют эти bytes.
2. Source resolution ограничено publications/prefix, реально необходимыми closure; более поздний индекс не расширяет denominator или scientific input.
3. Ссылка на metadata не позволяет выйти за root, принять symlink/path traversal либо использовать чужую collection/activation.
4. Между построением manifest и скачиванием mutable index не может незаметно измениться. Предпочтение — producer один раз материализует маленький immutable metadata snapshot в existing export. Consumer-only решение допустимо, если оно действительно обеспечивает те же bytes и bounded recovery, а не надеется успеть до следующего append.

Если exporter нужно изменить, это **узкое расширение существующего capture owner** и отдельно разрешённый deploy; не весь новый main ради incidental updates. Для уже сохранённого C2 использовать verified packet/staging, если они полны. Не перегенерировать closure и не переснимать рынок.

### 4.3. Поведение старых captures и retries

Старый packet формата1 должен либо воспроизводиться через exact сохранённый source view, либо однозначно вести к already-imported exact sealed release с его полной verification. Не возвращать PASS только потому, что `release_id` записан в lineage. Если исходных exact metadata нет и release не был импортирован, вернуть typed missing-version reason; не фабриковать старый JSON из текущего индекса.

Fresh capture с тем же immutable closure может иметь новую **transport** identity только в явно поддержанной семантике, сохраняя старый packet. Изменение рыночных bytes/closed membership — конфликт, не очередная transport revision.

Transfer: stream во временные файлы в destination filesystem → hash/size → atomic publish. Не загружать весь tar в RAM на пути, заявленном как масштабируемый. На сбое оставить usable verified fragments и exact resume state. Повтор не скачивает совпавшие bytes и не пишет новую cohort lineage. Существующий CLI не должен отказывать раньше, чем выбрано правильное capture-scoped view.

На текущем масштабе можно сохранить bounded существующий transport, если измеренный memory envelope достаточен; перенос к streaming входит в ту же capability до заявления больших размеров, не в отдельную платформу.

### 4.4. Достаточное evidence

| Сценарий | Oracle / ожидаемый результат |
|---|---|
| Реальный trace C1(8 publications) → C2(24) | Исходный код воспроизводит конкретный conflict на изолированной копии; патч доставляет C2 без изменения C1 |
| Повтор C2 | `PASS_ALREADY_PRESENT_EXACT`, `epoch_bump=false`, прежние lineage/release bytes |
| Replay старого C1 после C2 | Старый packet/точный release остаётся валиден; нет необходимости откатить общий индекс |
| Ещё одно расширение открытого дня; crash transfer | Тот же public path завершается после bounded resume, без ручных files/IDs |
| Изменение старой publication, anchor либо protected dependency | Integrity refusal сохранён; prefix acceptance не скрывает tampering |

Новый durable regression оправдан именно этим межкогортным багом. Расширить существующий vertical fixture, не создавать отдельный тестовый framework. Положительный oracle: exact cohort episode/point set, hash-bound immutable payload, independently read release; не только stdout `PASS`.

### 4.5. Применение и rollback

После Git merge gate — отдельный bounded OPERATE на C2: source view → transfer/verify → seal/import → exact repeat → fresh-process cold check → existing Drive recovery, если нужный новый release ещё не покрыт. C1 только verify, не повторный capture. Ожидается 47 episodes и 6533 episode-point pairs; states/missingness сохраняются как есть.

Откат до новых writes — revert consumer кода. После нового transport schema старые readers не должны ошибочно трактовать его как старый shared mirror; compatibility проверяется. Partial import восстанавливается штатно; scientific lineage не удаляется ради clean retry.

**Handback I1:** root cause; selected design и почему меньше альтернативы; exact original reproducer; C1 hashes unchanged; C2 release/import/repeat/cold/Drive; следующий day-open case; фактические file/byte/wall/RSS; необходимость VPS deploy; residuals. Gate `DELIVERY_FIXED_AND_C2_IMPORTED` только после реального consume. Пока только fixtures — `CODE_READY_RUNTIME_PENDING`.

---

## 5. I2 — убрать гигабайтное размножение legacy и сделать maintenance безопасным

**Outcome:** ненужные legacy bodies больше не живут в routine HOT/backup; новые данные защищены небольшим, повторяемым backup. Runtime обслуживание не требует нового PR на каждый день или каждую очистку.

**Не цель:** назвать сжатый full-file replacement «настоящей SQLite delta». Переименование/сжатие без удаления причины — только промежуточный результат.

### 5.1. Узкая диагностика — один раз, на правильном источнике

Использовать уже проверенный consistent backup; если его локально нет — один exact download в разрешённую рабочую папку, не всю Drive-историю. На живом VPS читать bounded metadata, не `SELECT * ... payload_json` и не legacy retention `status` без оценки его ресурса.

Нужны: по таблицам/индексам allocated bytes и крупные payload classes; legacy/current/неопределённые зависимости; DB/WAL/free pages; retained full/delta/checkpoint graph; simultaneous staging timeline. Статистику payload вычислять потоково на копии и возвращать агрегаты без самих данных.

Полезные read-only diagnostics на копии: `PRAGMA page_size`, `page_count`, `freelist_count`, `quick_check`; `dbstat` — только если доступен в существующей SQLite build. Недоступный `dbstat` не оправдывает установку новой БД. [E2]

Разделить:

```text
resident_hot_bytes
new_useful_source_bytes_per_day
backup_upload_bytes_per_day
retained_remote_bytes
peak_transient_bytes_by_phase
```

Не суммировать независимые maxima как одновременный пик; не считать один full дважды и не включать диск ПК в расход VPS. Но процессный backup lock не защищает от RAM/IO contention с collector.

### 5.2. Сначала надёжная и дешёвая упаковка

Исправить существующие `remote_ops.py` / `offhost_backup.py`, не новый backup service:

- **Один consistent SQLite snapshot на один checkpoint.** Inventory, changed-set, packed entries, result inventory и stored chain tip вычисляются по тем же bytes. `BackupPayloadSnapshot` можно расширить либо аккуратно переиспользовать materialized source mapping. Не снимать SQLite повторно между inventory и упаковкой.
- Snapshot должен быть совместим с зафиксированными publication-job и operational state dependencies. Не обещать атомарный snapshot нескольких БД/файлов автоматически: нужная cross-store согласованность проверяется existing recovery contract; короткий fence — только если действительно нужен.
- Стандартный `ZIP_DEFLATED` с невысоким уровнем — первый кандидат. Один baseline STORED и один быстрый DEFLATE benchmark; второй уровень только при существенной развилке. Сохранить ZIP64 и bounded stream. `ZipInfo.compress_type` проверять на **самих entries**, иначе constructor может не дать ожидаемого эффекта. [E1]
- Один snapshot + один текущий archive, без лишней полной SQLite внутри другой временной папки. Snapshot освобождается после завершённой local artifact verification и исчезновения всех его consumers, не после произвольного timeout.
- Upload/retry использует immutable готовый artifact, не переснимает DB и не порождает новую цепь из-за network failure. Last-good checkpoint не заменяется до проверки нового. Никаких `sync --delete`.
- Native cold restore проверяет **reconstructed inventory** против manifest/chain, а не только подпись самого ZIP. SQLite consistency, material keys/ROWID/cursors и pending recovery читаются независимым кодовым путём.
- Старые STORED archives читаются; новые compressed entries не требуют переписывать старые archive hashes. Mixed chain проверяется. Если старые receipts содержат реально несовместимую inventory binding — incident с exact scope и новый корректный checkpoint; историю не чинить вымышленными hashes.

Иллюстрация низкого уровня, не готовый patch и не требование версии Python:

```python
# info/file_size, timestamps, permissions и stream policy — из existing owner.
info.compress_type = zipfile.ZIP_DEFLATED
# compress level задаётся поддержанным API фактически locked Python.
with archive.open(info, "w", force_zip64=True) as dst:
    stream_copy_and_hash(the_same_consistent_snapshot, dst)
# verify extracted bytes == inventory bytes; publish archive atomically.
```

**Отдельный targeted test на обнаруженный риск:** writer меняет SQLite после inventory step. Корректный checkpoint по-прежнему описывает один captured state; packaged bytes и result inventory не расходятся. Это проверка гипотезы о seam, не заявление, что существующие backups уже повреждены.

### 5.3. Legacy retirement: убрать ненужное из ежедневной нагрузки

Нельзя откладывать retirement бессрочно фразой «потом пригодится». Но возраст сам по себе не делает данные мусором.

Для конкретных legacy scopes получить **точный removal/compaction plan**: таблица/row identity или file path, bytes, причина ненужности, dependencies, archive locator/hash, consumers, rollback. Источником разрешённых scopes является решение владельца и current dependency graph, не wildcard `*202609*`.

| Класс | Действие |
|---|---|
| Cache, orphan scratch, завершённый owned staging | Удаление по narrowly owned policy после проверки отсутствия активного consumer |
| Retired legacy decoded bodies, гарантированно не нужны recovery | Один архив исходных bytes + native provenance-preserving compaction; исключить body из routine backups |
| Старые immutable market files | Перевести в COLD/retired inventory, если current consumers не требуют HOT; локальную копию удалить после проверки cold dependency closure |
| Quotas/tickets, IDs, authority, frozen protection, trial/negative history | Сохранять минимальную семантическую истину; не удалять как «legacy мусор» |
| STARTED/UNKNOWN attempts, active/tail episodes, open publications, незакрытые C2 deps | Защищены от удаления/compaction до разрешения соответствующего dependency |
| Неясная принадлежность | UNKNOWN с named missing owner; не выбирать жертву по размеру |

Полный исходный legacy rollback комплект сохраняется вне routine HOT. В новых checkpoints он не копируется заново. Удалять старые remote chains можно только целиком по reachability от retained restore points/научных pins, с проверенным replacement. Один pinned legacy archive достаточно только после доказательства его полного нужного scope.

### 5.4. Переиспользовать существующий retention owner, устранить его конкретные ограничения

`src/.../observation_schedule_retention.py` и `scripts/observation_schedule_retention.py` — исходная точка, не `hot90_sqlite_eligibility.py` как будто это единственная capability. [G3]

Требуемые изменения при подтверждении применимости:

1. Bounded keyset/chunk iteration вместо `.fetchall()` payload всех `call_ledger` и `poll_slots`; счётчики/summary не хранят все IDs в RAM. Shared query для status не запускается дважды.
2. Scope и cutoff фиксируются в плане; apply повторно проверяет candidate и protection под существующим writer fence, короткими транзакциями. На resume cursor не теряет и не повторяет semantic effects.
3. Eligibility учитывает **episode slots/rounds/outbox/publication и frozen export dependencies**, а не только legacy `due_observations`. Отсутствие legacy due rows не означает отсутствие episode obligations.
4. Все readers, которым действительно нужен body для recovery, видят его до закрытия обязательства. После compaction — явный `COMPACTED_PROVENANCE_ONLY`/archive locator, не фиктивный пустой успешный response.
5. Остаются исходные timing/status/occurrence identities; compaction не обновляет operational freshness и не дорисовывает `COMPLETE` у PAUSED legacy.
6. Тайм-/байт-budget maintenance принадлежит runtime policy. При близком due deadline или writer contention maintenance откладывается; collector не ждёт многоминутную maintenance transaction.

У retired legacy могут быть навсегда исторически PENDING due после остановки. Не «закрывать» их под уборку. Разрешённый retirement-record отделяет отказ от продолжения прежней кампании от факта наблюдения; exact historical state остаётся в архиве/необходимой metadata. Если current readers требуют сохранения такой строки, компактировать только ненужный body.

### 5.5. Физический reclaim и последующая устойчивость

Compaction payload может освободить страницы внутри SQLite, но не уменьшить файл. Не выдавать этот результат за освобождённые GB файловой системы. `VACUUM` может менять implicit ROWID и требует временного места; copy rehearsal должен проверять реальные consumers/cursors. [E3]

Предпочтение безопасному существующему native механизму физического reclaim. Если material ROWID stable не доказан, не запускать VACUUM вслепую. Тогда executor выбирает минимальный identity-preserving вариант: scoped rebuild с явным сохранением нужных row identities/sequence high-watermarks либо отказ от physical APPLY до конкретного исправления. Не придумывать универсальную миграционную платформу.

Порядок cutover: verified backup → measured rehearsal на копии → exact affected keys/hash baseline → bounded согласованное quiesce всех DB writers, при необходимости переснятие final state → reclaim/switch → schema/integrity/identity/resume checks → writer start → реальный следующий tick → новый verified recovery checkpoint. Смена root device/inode, lookup identity и active envelope отдельно учитываются. Нельзя restore старую snapshot поверх уже появившихся новых admissions: после новых writes rollback требует reconciliation/forward recovery.

Пауза в 5-minute capture имеет цену. Если операция не помещается между безопасными окнами, предложить измеренное maintenance window с честными gaps или выполнить reclaim на границе кампании. Не гарантировать zero gaps за счёт фиктивного late backfill.

После одноразовой очистки поддерживать bounded HOT автоматически: старые завершённые bodies/owned staging уходят по policy и verified archive. Не добавлять daily VACUUM. Измерять рост обычного актуального корпуса; окно retention, а не возраст проекта, должно определять крупный reusable HOT объём.

### 5.6. Экономическая проверка и достаточный результат

На одинаковом snapshot сравнить baseline и proposed path. Предварительный инженерный ориентир — кратное сокращение текущего ~5.1 GB routine payload, а не выигрыш 5%. **Рутинный вклад retired legacy body должен стать нулевым**; новый полезный payload может расти честно. Конкретные byte ceilings принимаются после разложения данных, не подгоняются под произвольный «100 MB».

Пример модели, не измерение: при compression ratio 0.2 один archive ~5.134 GB стал бы ~1.027 GB. Пиковые resident full + snapshot + new ZIP не равны одному ZIP; их пересчитать по реальному overlap. Реальный ratio пока UNKNOWN.

Oracle набор: extracted file hashes; SQLite `quick_check`/нужный `integrity_check` на копии; preserved material primary keys/ROWIDs; pending recovery scenario; C1/C2 release verification; interrupted upload resume с прежним checkpoint; actual full + changed-file path; обычный live backup после deploy при работающем collector.

**Handback I2:** before/after по пяти метрикам; exact contributions legacy/new; ratio/wall/RSS/peak; raw snapshot inventory consistency; deleted/compacted scope и bytes; last-good/new restore refs; actual collector delay/slot coverage вокруг maintenance; updated capacity forecast; next ordinary backup result или `AWAITING_ROUTINE_BACKUP` с точным временем/trigger. Подтверждённый stopped maintenance безопаснее fabricated экономии.

### 5.7. Если маленькая SQLite + сжатие всё равно дороги

Не писать собственный WAL shipper, page-delta format или SQLite session pipeline ради названия DELTA. Последний требует отдельного покрытия writers/schema/PK и меняет модель восстановления. [E5]

Только если после retirement измеренный новый HOT остаётся большим и routine backup materially ограничивает сбор — один bounded comparison existing approach против maintained content-deduplicating backup через имеющийся rclone transport. У adoption есть новый binary, ключ/пароль recovery, отдельная repository/retention semantics; это реальный scope/authority fork, не «поставить заодно». По умолчанию его нет. [E6]

---

## 6. I3 — лимиты, продолжение и откат как обычные операции

**Outcome:** после единственного структурного внедрения supported количественный режим можно измерить, разрешить, применить и откатить без Git/PR. Регистрация внутренних schedules/activations происходит автоматически внутри точного standing grant. Система не получает неограниченную власть над ресурсами.

**Это одна согласованная capability, а не независимые патчи `allow DEGRADED`, `cap 500`, `renew timer`.** Раздельные обходы оставят ту же проблему на следующем уровне.

### 6.1. Один runtime owner

Расширить существующий operational store и public CLI. Предлагаемые UX-названия — **дизайн интерфейса, не команды уже существующего кода**:

```text
collection status
collection plan --daily-cap 500 --horizon-days 180
collection apply --proposal <saved-plan> --expected-revision <revision>
collection rollback --to-revision <last-good> --expected-revision <revision>
collection stop-intake
collection reconcile
```

Исполнитель вправе реализовать это под existing `observation_schedule.py`/owner entry. Важен один публичный discoverable путь. Натуральная просьба владельца преобразуется агентом в exact proposal; Пётр не вводит эти флаги вручную.

Долговечные сущности — минимум:

- **Operating profile revision:** желаемая нагрузка, финансовые/ресурсные ceilings, duration/retention, continuation/notification policy, next effective boundary. Текущие численные значения хранятся вне Git.
- **Grant binding:** кто и какой exact proposal/диапазон разрешил, scope, expiry/revocation, permitted provider routes и recovery/tail authority. Переиспользовать существующий authority owner; не создавать альтернативный разрешающий ledger.
- **Command/apply receipt:** idempotency key, expected/current revision, input/evidence hashes, status и resulting IDs. Использовать existing operation/command storage; отдельная таблица только если соответствующего owner действительно нет.

Capacity measurements, risk acceptance и planned schedule относятся к одному proposal/receipt, а не требуют собственных сервисов, event bus и framework.

### 6.2. Содержание profile / proposal

Ниже логическая модель. Имена полей адаптируются к canonical schema в той же итерации; не поддерживать два независимых словаря.

```yaml
collection: OPPORTUNITY_EPISODES
revision: 7
previous_revision: 6
intent: RUN                         # либо STOP_INTAKE; не «kill все jobs»
quantitative_request:
  daily_cap: 500
  rolling_24h_cap: 500
  planning_horizon_days: 180
  intake_until: <explicit UTC instant>
resource_policy:
  target_bytes: <runtime owner value>
  hard_bytes: <runtime owner value>
  physical_free_floor_bytes: <measured conservative floor>
  provider_calls_per_day: <approved allocation>
  maintenance_time_and_io_budget: <approved limits>
continuation:
  enabled: true
  apply_changes_at: NEXT_SUPPORTED_UTC_BOUNDARY
  preserve_committed_tail: true
recovery:
  allowed_actions: <specific existing reversible actions>
  max_attempts_and_backoff: <bounded policy>
notifications:
  healthy_daily_digest: false       # рекомендация; existing preference сохраняется до APPLY
  incidents_and_recovery: true
binding:
  grant_ref: <exact approved grant>
  semantics_fingerprint: <population/grid/source/seed/protection-policy>
  capacity_evidence_ref: <measurement/model receipt>
  expected_current_revision: 6
```

500 и 180 — **пример желаемого запроса**, не разрешение и не доказанная capacity. Default quantitative values при migration не меняют работающий режим100. Отсутствие managed profile не делает legacy grant standing grant. Некорректный managed profile не проваливается молча в старый permissive путь.

### 6.3. TARGET: честное предупреждение с ограниченным owner acceptance

Не изменять исходный `DEGRADED` на `PASS`. Разделить status и решение:

```json
{
  "storage_health": "DEGRADED_TARGET",
  "hard_constraints": "PASS",
  "physical_and_tail_reserve": "PASS",
  "risk_acceptance": "VALID_FOR_EXACT_SCOPE",
  "activation_admission": "ALLOW_WITH_TARGET_RISK_ACCEPTANCE"
}
```

Acceptance связан с exact profile/plan, верхней границей принятого forecast, допустимой неопределённостью, сроком и ответственным owner. Простой `--force`, boolean `ignore_limits` и принятие любого `UNKNOWN` запрещены. После expiry либо существенного выхода за accepted forecast новые admissions прекращаются/ждут решения; уже принятый tail продолжает обслуживаться.

Здесь пользователь уже одобрил **возможность** принимать TARGET-риск; конкретное будущей activation acceptance всё равно связывается с её proposal. Initial defaults 40/50 GiB сохраняются до runtime APPLY. Старый commissioning envelope без version читается в старой семантике; новые варианты получают явную version/discriminator. Не добавлять поля в frozen V1 так, чтобы его прежний hash незаметно перестал означать то же самое.

**HARD violation, недостаток физического tail reserve, неизвестная критическая topology, integrity/protection conflict не принимаются через этот механизм.** Отдельная обоснованная смена owner hard budget возможна через plan/apply только если реальные safety constraints проходят; она не является target exception.

### 6.4. Численные лимиты: не литералы, а результат измерения и права

Для нового managed path исключить доменные magic ceilings100/400 там, где это значения прежнего proof, а не математические/протокольные ограничения. Сохраняются реальные ограничения parser/route, например max batch100, пока протокол не изменён и соответствующая новая семантика не квалифицирована. [G5, E4]

Обновить связанный contract/schema/compiler/budget estimator/admission/dispatch/status в одном outcome. **Не расширять исторический V1 диапазон незаметно**: новая поддержанная managed schema/adapter сохраняет old reader и frozen old identities.

Увеличение теперь проходит:

```text
request → resolve same semantics → provider/resource model
        → reuse applicable evidence или bounded new measurement
        → capacity admissibility + owner scope
        → plan/apply revision → prospective cutover → live observation
```

Evidence применяется к relevant dependency fingerprint, окружению, workload shape и режиму maintenance. Несвязанный documentation commit не обнуляет нагрузочный proof. Изменение batching/timing/storage topology/provider entitlement может его инвалидировать.

Если требуемое значение выходит за измеренный диапазон, это **операционный capacity probe**, а не новый PR на литерал: сначала model/fixture replay с запретом live calls, затем при необходимости отдельно разрешённый bounded live ramp. Новые code semantics нужны только когда текущий алгоритм объективно не умеет обслужить нагрузку, а не когда config-файл попал в write set.

### 6.5. Предрасчёт: почему свободного диска недостаточно для ×20

Обозначим D — admissions/day. При равномерном устойчивом потоке и 72h horizon примерно active=3D, post-T0 point obligations/day=138D. У трёх nomination sources с period15min — 288 requests/day. Даже при идеальном заполнении SEARCH batch100 нижняя оценка calls/day — `288 + ceil(138D/100)`. Реально её увеличивают группы времени, неполные batches, границы суток и shared account work. [MODEL на G5]

| D | Примерно active | Post-T0 points/day | Идеальный lower bound calls/day |
|---:|---:|---:|---:|
| 100 | 300 | 13 800 | 426 |
| 200 | 600 | 27 600 | 564 |
| 500 | 1 500 | 69 000 | 978 |
| 1 000 | 3 000 | 138 000 | 1 668 |
| 2 000 | 6 000 | 276 000 | 3 048 |

Текущие 1200/day — owner allocation из профиля, не универсальная характеристика всех тарифов Jupiter. Повысить allocation можно только после проверки реального entitlement/shared callers и отдельного разрешения. У public provider limits и у нашего budget разные owners. [E4]

Есть и burst limit: при n одновременно назначенных batches и минимальном межзапросном интервале3s только расстояние между первым и последним send не меньше `(n-1)×3s`. При 60 batches это177s, больше текущего 60s dispatch window даже без latency. Этот пример — stress shape; точное число batches даёт native assigned-time resolver, не формула active/100 для каждого тика.

**Следовательно:** поддержать произвольный количественный запрос без PR — да; обещать PASS2000/day при прежних timing/route/пейсинге — нет. Правильный отказ называет конкретную ось: например `DISPATCH_CAPACITY_INSUFFICIENT`, а не `MAX100_HARDCODED`. Снижение density, изменение windows, новый источник/parallel caller — изменение семантики/архитектуры, не скрытая калибровка.

### 6.6. Модель storage на полгода и 100 недель

Планирование не равно `текущий размер × число дней` и не предполагает вечный HOT. Для каждого реального filesystem считать:

```text
projected_peak(t) = current_nonoverlapping_resident
                  + retained_new_data(t, admitted_rate, retention_policy)
                  + maximum_simultaneous_transient_for_allowed_job_overlap(t)
                  + conservative_error_allowance
```

Отдельно runtime перед admission проверяет ещё не материализованные committed obligations + prospective obligations + fixed reserve относительно **current free space**. Не складывать тот же tail в projected occupancy и второй раз как уже resident bytes.

Для180d proposal нужны HOT retention, cold retention/capacity, mutable body lifecycle, backup generation retention, inodes/file count, CPU/IO, transfer/catch-up duration. Прогноз180d — модель, а не proof полугода runtime. Fresh pressure recalculation и автоматическое закрытие intake делают модель управляемой.

Через100 недель не должны линейно расти hot-path scans, непогашенные temp files и retention-chain enumeration. Долгая научная история может расти; она хранится в cold/archive с bounded current metadata и индексами. Не заявлять O(1) всей системы: требование — bounded routine working set при фиксированном текущем workload и retention.

### 6.7. Автоматическое продолжение без ручных activations

**Standing grant** — разрешение одному named collector на ограниченный период, неизменную source/population семантику и quantitative resource envelope. Это не permission на trading, новые providers или повышение лимитов само по себе.

Предлагается сначала согласовать один понятный срок normal operation, например30 дней;180 дней — допустимый запрос, если владелец явно выбирает его и capacity/retention проходят. Review через неделю не прекращает grant автоматически. По окончании grant — stop new intake с заранее разрешённым tail; не каждый день новый owner approval.

Система сама выполняет разрешённые внутренние `register → authorize → activate/rollover` и связывает каждый schedule с родительским grant. Нельзя просто вызвать старый `_phrase()` и считать, что строка разрешает операцию. Existing legacy same-envelope renewal не включать без episode-aware proof. [G6]

**Транзакционная модель:** одна control revision, compare-and-swap apply, unique transition identity `(collection_lineage, grant_revision, effective_boundary)`. Последовательность должна пережить смерть процесса после register, после authorization event и до/после cutover. Использовать существующие leases/outbox/idempotency, не создавать новую distributed saga.

На любой момент:

- не больше одного intake-owner на одну collection lineage;
- могут существовать несколько draining predecessors, обслуживаемых тем же worker/account lane;
- old и new obligations входят в общий resource/pace/account budget; новая activation не обнуляет debt;
- один UTC admission day не фрагментируется по incompatible profiles;
- sampling tickets, weekly dedup, rolling/day counters сохраняются через handover и restart;
- семантика/политика каждого admission определяется frozen binding этого admission, не today's settings.

Quantity/profile changes планировать на ближайшей поддержанной UTC-границе. Emergency stop-intake разрешён немедленно. Rollback внутри дня немедленно убирает новые admissions, если их продолжение небезопасно; полное возобновление на прежних параметрах — на следующей допустимой границе, без второго profile-fragment той же когорты.

Если текущий native scheduler умеет только один ACTIVE/DRAINING default, исправление этого selection owner входит сюда: глобальный earliest-deadline выбор обязательств из permitted lineages, priority уже committed observations перед optional nomination, **один** provider pacing lane. Не просто обходить `AMBIGUOUS` вторым timer.

### 6.8. Автоматическая реакция на риск и границы её полномочий

| Событие | Автоматическое действие в разрешённом envelope |
|---|---|
| Разовый transport failure / busy writer | Existing bounded retry/recovery; не повторять неопределённый provider request за старый point |
| Плохой новый quantitative profile | Stop extra intake; запланировать возврат last-good quantity на допустимую границу; дописать incident |
| Недостаток free/tail reserve | Немедленно запретить новые admissions, сохранить уже принятый drain, остановить необязательные maintenance jobs |
| TARGET выше нормы, acceptance валиден | Продолжить в exact accepted scope; один DEGRADED notification, не ежедневный approval |
| HARD/critical evidence unknown | Нет расширения / stop new intake; не «владелец ведь обещал почистить» |
| Grant истекает | Early warning; затем stop intake с исполнением зарезервированного tail |
| Integrity/protection ambiguity | Блокировать зависимый путь; никаких auto-delete, auto-reseal или reset history |

Automatic rollback разрешается только как заранее одобренное действие profile. Не auto-scale вверх и не менять научные фильтры под желаемый yield. Отсутствие новых supply само по себе не запускает повышение cap.

### 6.9. Verification I3 и live внедрение

Один параметризованный scenario suite через native entry, с независимым schedule/budget расчётом для контрольных случаев:

- TARGET-only excess принимается с exact unexpired acceptance и сохраняет DEGRADED; без acceptance не принимается; HARD/physical fail не принимается никогда через эту ветку.
- Запрос100 → более высокий supported запрос → rollback без изменения Git fingerprint; replay прежних admissions неизменен. Не выставлять synthetic limits в production.
- Handover A-tail + B-intake, в том числе crash после промежуточного события; один intake, отсутствие double admission, один aggregate pace/call budget.
- Отзыв/expiry grant, stale proposal, corrupt managed state, concurrent apply, lower limits ниже committed debt — ожидаемые typed результаты без потери tail.
- Большой requested cap с недостаточным dispatch или API budget отклоняется численно обоснованно.
- Replay исторического schedule1.0/hash и old corpus остаётся прежним; нет массовой переинтерпретации старых grants.

Deploy/application: exact release и forward/backward compatibility; active producer не менять попутно. Перед первым реальным cutover выполнить offline/rehearsed boundary, затем отдельно разрешённый live handover. Если к stop17.10 доказательства не готовы, заранее подготовить один законный bridge на действующей capability либо честный запланированный gap. Не выдать неподтверждённый новый scheduler за safe ради deadline.

**Handback I3:** текущие/запрошенные/effective значения и права; TARGET/HARD/physical decisions отдельно; capacity table; command replay/rollback proof; head/profile/grant/successor IDs; старые obligations preserved; exact live boundary и actual result; дата следующего expiry/continuation; remaining UNKNOWN. `MANAGED_CONTINUITY_LIVE_PROVEN` только после реального перехода, не после зелёной fixture.

---

## 7. I4 — фоновая эксплуатация и «забери готовое → Forge ready»

**Outcome:** отсутствие Петра и выключенный ПК не мешают работе в пределах разрешённого режима. Система сохраняет нужные данные, выдерживает обычные отказы, не спамит и догружает готовое одной просьбой.

### 7.1. Что автоматизировать, что оставить по запросу

Автоматически на VPS: nomination/admission/slots, cohort ownership, законное continuation, публикации, bounded durability, approved maintenance и alerts. По запросу: перенос на ПК и research. Это согласуется с S1; daily workstation importer не является prerequisite.

**Source package до ухода из HOT:** для зрелой когорты сформировать через existing export/archive owner dependency-complete frozen package или эквивалентный verified набор daily archives + metadata. Он обязан включать closure/schedule/protection/frames/member-prefix/publication/raw dependencies, а не только Parquet. Обычный HOT90 ZIP закрытого дня не считать полным покрытием позднее созданного frozen export автоматически.

Предпочтение лёгкому export/pack существующих bytes на VPS, а не новой тяжёлой materialization Forge corpus. Sealing/research projection остаются на ПК, пока измерения не покажут более простой вариант. Автоматический archive job использует те же functions/semantics, что проверенная ручная доставка; не второй divergent exporter.

Небольшие source packages могут повторять часть raw между когортами, если это дешевле общей сложной object store. Удаление ненужного промежуточного staging после verified package должно компенсировать temporary duplication. Решение опирается на measured bytes, не «dedup любой ценой».

### 7.2. Retention и отложенный catch-up

До удаления HOT dependency требуется verified независимая копия и воспроизводимость release/source view. Нельзя удалять единственную нужную часть, даже если TTL истёк. Если archive недоступен, dependency pin сохраняется; растущий backlog сначала вызывает warning, затем ограничивает **новый** intake при фактическом reserve pressure.

Initial proposed policy для обсуждения/измерения: recent HOT около14 дней при неизменном lower bound действующих schedules; cold source/recovery около180 дней; научно значимые frozen recipes/results/negative evidence и их необходимые data pins — по собственным contracts. Это предложения, не автоматическое изменение прежних 90d/HOT или уже frozen retention. [S1 §7; G5]

Фактические сроки применяются одним owner policy approval после capacity model. Выключенный ПК на30 дней должен быть covered, если cold window≥30d; бесконечная offline-сохранность не обещается. При намеренном истечении cold policy полный нужный научный пакет остаётся pinned либо retired с явным решением, а не пропадает как «cache».

Producer владеет inventory зрелых/заархивированных когорт, workstation lineage — импортированными у этого consumer. Не нужна отдельная распределённая синхронизация «кто что скачал», чтобы архивировать или считать cold durability. PC acknowledgement может быть convenience, но не safety authority.

### 7.3. Одна обычная delivery operation

`Забери готовые Opportunity Episodes` делает bounded enumeration, перенос, verify/seal/import, resume и metadata-only readiness. Exact IDs вычисляет existing owner. В output различать:

```text
discovered_ready / attempted / imported / already_present / blocked
next_maturity / backlog_remaining / cold_hydration_required
corpus_version / evidence_epoch / data_ready / forge_preflight_ready
```

Архивная hydration использует exact manifest/dependency hashes, не текущие provider endpoints. После сетевого сбоя продолжает тот же transfer; после partial import — existing import intent и тот же import time. Не переснимает пропущенные данные. Число cohorts/байт/время одного запуска ограничено; если backlog больше, даёт exact resume без ручных manifest edits.

**Fault isolation:** повреждённая cohort не должна бесконечно делать все последующие данные недоступными из-за механического FIFO. Если independent healthy cohorts могут быть приняты по контракту, завершить их и вернуть `PARTIAL` с явно перечисленными пропущенными identities/reasons. Не скрывать gap из inventory, не считать partial corpus полным universe и не выбирать только хорошие outcomes. Если native scientific/lineage gate не допускает partial import, сохранить typed blocker и исправить соответствующий owner, а не молча исключать cohort.

`Forge ready` здесь — точный metadata preflight для имеющегося corpus/role/policy. `data_ready=true` вместе с `forge_preflight_ready=false` допустимо и информативно. Глобальный scientific selection/continuity conflict не исчезает от успешного transport.

### 7.4. Оповещения, idle и recovery

Переиспользовать `operability_watch`, `collector_owner_pulse`, существующий Telegram и heartbeat hook. Не добавлять новый messenger/scheduler. [G7]

Нормальное отсутствие работы определяется **desired state и ожидаемыми due events**:

- до starts_at — ожидаемый pre-start, ноль calls;
- grant закончен и intake intentionally stopped — `IDLE`/drain state;
- desired RUN, а нужный activation исчез — incident, не «штатный idle»;
- пустой eligible supply — объяснимое отсутствие admissions, не обязательно outage;
- service alive, но obligations overdue/source не обновляется — не healthy.

Не переименовывать любой `TICK_REFUSED_NO_LIVE_DEFAULT` в успех. Сначала различить intent. Не снимать failed systemd state командой reset-failed вместо исправления статуса entry point.

По умолчанию для нового согласованного режима: никаких success-сообщений на каждую cohort/tick; один incident при существенном изменении, один recovery. Healthy digest — optional настройка, не новая обязанность владельца. Dedup по причине и scope, backoff без скрытия длительного persistent failure.

Пример сообщения:

> Сбор новых эпизодов остановлен: резерв на уже принятый 72h хвост ниже допустимого. 286 эпизодов продолжают наблюдаться. Очистка не выполнялась. Следующий безопасный шаг — применить подготовленный storage-план либо оставить drain. Проверка: 14.10 09:10 МСК, receipt …

Сообщение содержит фактическое воздействие, автоматическое действие, scope/time и один следующий шаг; не 15 внутренних enum без объяснения. Telegram failure сохраняется локально и не рушит collector; delivery retries не превращаются в повторные provider calls.

**Смерть всего VPS:** локальный timer не может сообщить о собственной недоступности. Если существующий внешний heartbeat receiver реально настроен — проверить controlled missed-heartbeat signal без остановки production collector. Если нет — `HOST_LOSS_ALERT_UNPROVEN`, один named external watcher как отдельный minimum-scope commissioning decision; не выдумывать Telegram delivery и не объявлять unattended protection полной.

### 7.5. Evidence I4

Достаточен один связный owner-path drill на disposable данных плюс реальные контрольные readbacks:

1. Restart/bounded interruption → committed tail восстановлен, нет duplicate request/admission, grants не расширены.
2. Drive временно недоступен → source остаётся; после recovery архив завершается; cleanup не удаляет pinned данные.
3. ПК отсутствует моделируемое окно → hydration из cold → нужный corpus → metadata Forge preflight, без VPS/provider при чтении уже перенесённого release.
4. Ordinary transfer остановлен и повторён; один corrupt dependency не превращается в невидимый skip.
5. Alert + dedup + recovery; expected idle не вызывает бесконечного инцидента. External deadman проверен либо явно не покрыт.
6. Под реальным collector прошёл хотя бы один обычный backup/archive cycle и передача первой новой mature cohort, когда она действительно появится. До maturity возможен `LIVE_PENDING_NEXT_COHORT`, не fake DONE.

**Handback I4:** что реально автоматизировано и commissioned; какие регулярные действия ещё требуют Петра и почему; actual alert/readback scope; late-PC recovery proof; archive/retention debt; next ready cohort; Forge readiness; remaining long-window checks. Для долгого soak достаточно сохранить next exact readback, а не держать chat/process в бесконечном ожидании.

---

## 8. I5 — использовать исправленную capability: Forge и один ограниченный результат

**Outcome:** полученный corpus действительно используется через обычный scientific ingress, а не просто накапливается. Это завершающая проверка operational/research fit, не доказательство торговой доходности.

### 8.1. Сначала metadata-only admission

Проверить текущие Git owners и data-plane evidence: collection/role, corpus version/epoch, source/schedule compatibility, preflight, research/universe policy, remaining scientific budget, open operations и prior working view. Использовать существующие canonical read APIs. Не импортировать новую cohort параллельно с коротким frozen научным запуском в одном corpus root.

Для reported `BLOCK_FORGE_SELECTION_RISK` и `MARKET_EPOCH_CONTINUITY_UNRESOLVED` найти earliest broken boundary по exact saved session/record. Возможны operational reconciliation, действительно повреждённый owner record, несовместимая семантика или отсутствующий evidence. Ни смена имени focus, ни новый пустой ResearchStore, ни quarantine неудобной истории не являются корректным repair.

Если это software defect, исправить соответствующий owner и прогнать тот же metadata ingress. Не открывать общий audit всей Forge и не переписывать scientific identity постфактум. Если требуется смысловое решение владельца — сформулировать конкретную альтернативу/воздействие один раз.

На design anchor появились и другие Git research contracts. Наличие старого draft в этом чате не даёт права игнорировать актуальные protection/assignment/prior owners. Новые canary/100-day exploratory data не становятся untouched holdout задним числом.

### 8.2. Отдельный scientific grant

Первый предложенный запуск из S1 остаётся **draft**, а не разрешением: одна ordinary operation, `LIMITED_RESULT`, `MAIN=1`, `ADAPTIVE=0`, `PREVIEW=0`, в пределах оставшейся policy. При сменившемся prior/context executor предлагает актуальный смысл до values; Пётр утверждает scientific scope отдельно. Исходная идея — связь раннего price/holders/liquidity с последующим поведением. Нельзя заявлять incremental effect сверх price-only baseline, если native comparator считает `SAME_DECISION_ELIGIBLE`.

В запросе до values фиксируются estimand, decision/target, predicates, baseline, missingness/attrition и действия для supported/not supported/inconclusive/technical stop. Exact query grammar читается из current preflight; не копируется из старого примера.

Одного результата достаточно для первого прохода. На positive — candidate + предусмотренный Critic, только если обосновано; на negative — scoped finding; на insufficient — конкретный limiting support; на technical stop — тот же operation/reservation и exact resume. Cap не создаёт `SEARCH_EXHAUSTED` и не разрешает второй MAIN.

### 8.3. Проверка и следующая продуктовая развилка

Свежий процесс читает original saved operation/result. Разрешённый exact numerical replay использует frozen inputs и не расходует новый scientific look. Сохранить denominator, missingness, cohort/mint dependence и limitation of mark-return proxy. Не утверждать fillability/net cashflow без execution evidence.

**Handback I5:** metadata blockers resolved/open; actual looks/reservations/operation identity; saved result/candidate/disposition/critic; replay; ограничения вывода; один следующий falsifier или data-need. Если scientific grant не выдан, корректный итог программы — `READY_FOR_CONTROLLED_FORGE`, а I5 value-bearing часть остаётся pending, не FAIL эксплуатации.

После этой итерации дальнейшая работа выбирается по информационной ценности: frozen experiment/chronological OOS, targeted data repair либо отказ от слабого вопроса. Не начинать очередной инфраструктурный цикл только потому, что есть свободное место.

---

## 9. Evidence и проверка по риску

### 9.1. Общий подход

Требуется доказанный результат, не универсальный TDD и не заданное количество тестов. Использовать existing tests/CLI/fixtures и независимый oracle. Новый durable test добавлять для material непокрытой регрессии: текущий C1→C2 bug, target acceptance/authority, tail-preserving rollback, snapshot A/B consistency и retention active-episode protection — такие риски есть.

Не дублировать один сценарий на всех уровнях. Unit нужен для компактной чистой логики; integration — для filesystem/SQLite/transport seam; end-to-end — для owner path. Моки допустимы для provider/clock/failures, но не заменяют production binding или actual installed timer. Реальные провайдерские calls только в разрешённом operational scope.

Critical oracle не должен быть копией формулы реализации. Для ресурсов — отдельный sanity calculation + sampled actual phase peaks; для данных — exact source membership/hashes и другой reader; для policy — отрицательные authority cases; для backup — restore, не лог upload.

### 9.2. Минимальная межитерационная матрица

| Риск | Достаточный наблюдаемый результат | Где |
|---|---|---|
| Mutable metadata конфликтует с immutable transfer | C1 → C2 → old C1 replay → later extension проходят с правильными identities | I1 |
| Успех за счёт permissive overwrite | Изменённая старая publication/anchor/hash остаётся refusal | I1 |
| Backup manifest описывает другой snapshot | Concurrent writer не меняет inventory пакуемого snapshot; native restore соответствует | I2 |
| Сжатие только «на бумаге» | Entry `compress_type`, actual bytes, mixed-chain restore, ordinary upload | I2 |
| Retention уничтожает ещё нужный body | Active/tail/unknown/publication/export refs защищены, retired body compacted | I2 |
| Физический reclaim ломает cursors | Material row identity/high-watermarks и next writer scenario сохраняются | I2 |
| TARGET acceptance стал universal bypass | TARGET-only exact case allowed; HARD/integrity/stale/corrupt cases denied | I3 |
| Scaling сбросил счётчики или изменил прошлое | Shared quota/pace/tail preserved; old schedule/release hashes unchanged | I3 |
| Successor duplication / пропавший tail | Crash-boundary resume оставляет один intake и все старые obligations | I3 |
| Rollback требует PR либо удаляет новые episodes | Runtime revision + drain, без Git diff и переписывания данных | I3 |
| ПК/Drive недоступны | Bounded catch-up, source pins, retry, явный partial coverage | I4 |
| Мониторинг жив, продукт стоит | Desired-state/progress/alert связаны; expected idle отличается от lost activation | I4 |
| Operational look оказался скрытой наукой | values/reservations=0 до grant; frozen one-MAIN после; same-result replay | I5 |

Это сценарии, не требование создать13 новых test files. Часть уже покрыта; executor должен показать reuse и заполнить именно пробелы.

### 9.3. Длительные проверки

Не имитировать «100 недель PASS» из фиктивного sleep. Time-advanced fixtures и большой исторический metadata corpus проверяют bounded scans/retention/rollovers без растущего hot-path RSS. Реальное длительное evidence: следующий backup, первый handover, первая новая mature cohort, 72h workload и недельный owner burden.

До получения последнего required live evidence состояние `CODE_READY_RUNTIME_PENDING` или конкретный `LIVE_PENDING_*`. При этом можно выполнять независимую следующую итерацию, если не потерян её truth/authority scope. Нет обязательной паузы всего проекта ради календарной maturity.

---

## 10. Delivery, authority, privacy и свобода executor

### 10.1. Что executor выбирает самостоятельно

Низкоуровневую реализацию, расположение helpers внутри существующих owners, точные индексы/SQL, размер безопасных chunks, способ построения fixture, кодовую декомпозицию, reuse regression evidence и порядок локальных проверок. Может `PATCH` решение по найденной фактической совместимости, если сохраняет outcome/invariants и не расширяет external/destructive scope.

Изменение architecture/semantics, новая услуга/credential, существенная цена/длительность/риск либо отказ от согласованной части outcome — `REPLAN` с recommendation. Не превращать обычный технический выбор в вопрос Петру. Не собирать неограниченный backlog «на будущее».

### 10.2. Границы применения

| Действие | Разрешение |
|---|---|
| Чтение Git и разрешённых локальных receipts, isolated fixtures/benchmark | В пределах выбранной итерации |
| Код/контракты/tests/generated views, обычная ветка/PR/CI | После точного EXECUTE scope, по current harness |
| Merge | Exact-head CI → readiness → отдельная exact owner phrase → guarded merge/readback |
| Deploy, timer/settings на VPS, реальная миграция | Отдельный exact OPERATE packet: target, scope, risk, rollback, expected evidence |
| Runtime profile change | Один exact plan approval; внутри заранее одобренного recovery/continuation scope — без повторной ручной регистрации |
| Provider calls / standing collection grant | Explicit ограниченный workload/период/route budget; старый grant не наследуется автоматически |
| Удаление/compaction | Exact first APPLY plan либо позже уже явно утверждённая narrow maintenance policy; не глобальное разрешение «чистить всё» |
| Drive/Telegram writes, credentials/новый service | Только существующий допустимый operational scope или новое явное разрешение |
| Science values/новые looks | Отдельное scientific scope/budget, не из permission на repair |

Программа не отменяет machine gates. Она меняет **конкретные owners/контракты**, где ранее семантика policy была слишком жёсткой или неполной. До принятия и deploy нового кода действует старый контракт.

### 10.3. Как не получить новую бюрократию

Пётр подтверждает понятный outcome/режим и риск один раз на настоящей границе. Executor связывает его с машинным proposal/hash. В нормальной будущей эксплуатации не требуется отдельное ручное «register», затем «authorize», затем «activate». Эти технические действия — части одной idempotent operation по одобренному scope.

Нельзя попросить неограниченный «admin access» ради удобства. Не добавлять подтверждения на промежуточный generated JSON. Не заводить отдельный PR для реального timestamp, live limit, нового cohort ID или текущего количества места.

### 10.4. Privacy и локальные данные

Raw payload, keys, addresses infrastructure и большие DB не помещаются в chat/Git. Для design/review достаточно sanitized schema/aggregate metrics, IDs/hashes/relative locators. Full local snapshot остаётся в разрешённом data/backup домене. Использовать synthetic fixtures для adversarial cases; реальные C1/C2 только для exact accepted technical verification, без ручного исследования доходностей.

---

## 11. Durable artifacts: исправлять владельца смысла в том же атоме

Каждая semantic/API/state/navigation change обновляет свой canonical owner и действительно затронутые consumers. Не размножать альтернативные specs.

| Изменение | Обязательная propagation |
|---|---|
| Capture identity/view, replay, partial delivery | Existing release contract, public CLI/help, operator recovery path, manifest schema/version при необходимости, relevant Catalog route |
| Compression/snapshot/retention | Backup/recovery contract, retention CLI и eligibility, source selection, restore recipe, operational runbook; labels не должны обещать page delta |
| Managed quantitative policy / target acceptance | New/extended canonical collection policy contract; schedule/compiler/lifecycle/storage admission/authority/CLI; old frozen schemas preserved |
| Continuation / multiple draining scopes | Scheduler selection/pacing/quota/recovery/status/alerts и exact grant lifecycle |
| Unattended archive/cleanup/cold catch-up | Existing archive/retention/delivery route; состояние freshness/progress и closed dependency inventory |
| Forge continuity repair | Только exact owning science/epoch contract и affected context/navigation, без изменения meaning задним числом |

Git хранит code, schema, durable policy semantics, reproduction и значимое sanitized evidence. Live revisions, timestamps, grants/receipts, DB/recovery files и operator actions — runtime plane. До closure новый agent должен найти единственный authoritative entry через AGENTS/semantic route и понять expected failure/resume без чтения этого чата.

Сам этот MD — программа/design input. При materialization исполнитель связывает выбранную итерацию с существующим task/harness contract; не делает одновременно дубликат PRD, отдельный SSD, отдельный 200-пунктный plan и ещё один audit artifact с тем же смыслом.

---

## 12. Handback, принятие итераций и точное продолжение

После каждого существенного результата — **один owner readout + существующие machine receipts/locators**. Если нужен формат для automation, сначала использовать native receipt; не новый общий журнал.

### 12.1. Общая форма

```text
ITERATION / MODE / EXACT SCOPE
OUTCOME: ACCEPTED | CODE_READY_RUNTIME_PENDING | PARTIAL | BLOCKED
Что реально изменилось для владельца — 2–4 предложения.

FACT: current Git/deployed/revision/corpus/receipt identities и observed time.
MODEL: расчёты, assumptions, bounds, uncertainty/invalidation.
UNKNOWN: только decision-relevant gaps и зависимые claims.

BEFORE → AFTER: основные числа, эффект и costs/burden.
EVIDENCE: reproducer, oracle, targeted checks, exact actual readback.
FAILURES/RETRIES: что не прошло и как восстановлено; ничего не скрывать.
AUTHORITY: что было разрешено/выполнено; что точно не выполнялось.
ROLLBACK: что уже reversible; где после новых writes нужен forward recovery.
RESIDUALS: один NOW, один WATCH с trigger.
NEXT: одна рекомендуемая итерация или exact owner action.
RESUME: одна точная команда/locator + что НЕ повторять.
```

Не присылать Петру выбор из пяти архитектур. Chat по этой отбивке принимает implementation/result в нужном scope, рекомендует следующий шаг и решает с Петром реальные deviations. Изолированный agent review не заменяет numerical/file/runtime oracle.

### 12.2. Решения Chat при отклонениях

- **Небольшой проверяемый drift:** продолжить/patch текущую итерацию, не перезапускать программу.
- **Тот же seam снова требует ручного восстановления:** пересмотреть owner boundary, а не добавлять suffix fix.
- **Дорогой reclaim задерживает continuation:** переключить NOW на I3 до срока; legacy retirement остаётся незавершённым outcome, не исчезает из плана.
- **Модель большого cap не проходит:** оставить/откатить к последнему допустимому профилю; назвать limiting axis, измерение и одно условие следующего запроса.
- **Предложенный fix требует нового сервиса либо изменения научного denominator:** stop/replan до решения, не silently simplify science.
- **Source retrieval/readback недоступны:** блокировать только зависимый verdict; не подменять live evidence старым отчетом.

### 12.3. Checkpoints по времени

Немедленно при I1 entry — проверить, пришёл ли уже readback новых admissions/SEARCH; не создавать второй ручной provider probe и не предполагать, что background job исполнителя завершилась.

**14 октября, 03:00 МСК:** 72h до stop текущего intake — deadline проверки continuity plan. **15 октября, до12:00 МСК:** совместный review фактического storage/backup и готовности continuation. Если работа возобновлена после этих дат, сначала сравнить current authority/intake state, не выполнять старый календарь задним числом.

После изменений: actual backup cycle; первая effective profile/renewal boundary; steady workload ~72h; первая новая mature cohort; недельный operational-fit readout. Даты вычисляются от **реальных** событий, не от времени написания MD.

---

## 13. Стартовая команда исполнителю

Этот блок — готовая постановка **I1**, не команда запустить все пять итераций без проверки.

```text
SMIAL. Активируй current AGENTS.md → semantic routes → exact owners.

MODE: EXECUTE — I1 программы SMIAL_MANAGED_COLLECTION_OPERABILITY_V1.
Основание: этот PRD+SSD V1 от13.10.2026, особенно §§0–4 и9–12.
NEXT_MODEL_EFFORT: SOL_XHIGH для границы capture identity/integrity;
рутинные проверки выполняй без переключений ради процедуры.

Outcome: устранить MIRROR_CONFLICT на растущем member_unit так, чтобы
обычный owner path доставлял C2, сохранял C1 и воспроизводил старый
capture после следующего. Не глобальное overwrite и не ручная правка mirror.

Стартовые runtime locators:
local/canary_exit_and_100_per_day_arm_v1/20261013_resume/EXACT_RESUME_POINT.json
и c2-stop-receipt.json.
C2: REL-20261008T000000Z-20261009T000000Z.
Reported active collector: ACT-4744D4017AC4B196; не менять его scope.

Сначала проверь наличие exact evidence и уже полученный live readback
нового collector. Читай только разрешённые источники. Если remote read
недоступен, продолжай независимые local/code steps, не выдумывая health.
Не запускай дополнительные provider calls и не останавливай сбор.

Воспроизведи старый C1→C2 conflict на isolated copy, выбери минимальный
capture-scoped/versioned source view либо эквивалент с доказанным old
replay. Проверь source-mutation race, historical manifest compatibility,
C1 unchanged, C2 exact repeat и genuine-conflict refusal.
Обнови actual semantic owners/CLI/runbook/required Catalog projections
в том же атоме. Не создавай второй importer/backup service/framework.

Дойди автономно до review-ready/CI/merge-readiness по current harness.
Первый owner stop — exact machine-rendered merge phrase либо material
scope/safety blocker. Не merge/deploy/production import без exact gate.
Подготовь один последующий OPERATE packet для применения I1 и C2 consume,
с независимой копией, rollback и числовым evidence; не исполняй его заранее.

Backup/legacy/policy/renewal здесь не менять. Можно зафиксировать только
обнаруженные relevant dependencies для следующих итераций. Если время
угрожает stop17.10, отрази отдельный continuity trigger; не расширяй I1.

Handback — §12 плюс I1-specific evidence. Tests по material risks,
existing suite reuse; не полное TDD/coverage ради количества.
Никакого нового science, очистки, grant expansion или изменения
исторических hashes. После принятого результата итерации верни exact
resume point и остановись для тактического review.
```

---

## 14. Источники, evidence scope и ограничения

### S — предоставленные материалы

**[S1]** `SMIAL_Jupiter_Tactical_Runbook_V2_2026-10-11(2).md`, полностью прочитан. Основа — цели, разделение planes, canary→normal→Forge, storage/retention, owner burden и handback. Новые runtime-policy/continuation требования этого документа **не выдаются за уже содержащиеся в S1**; они приняты пользователем в текущем запросе и спроектированы здесь.

**[O1]** Последнее сообщение владельца: activation `4744d401…` выполнена, до02:00Z ноль provider calls, live admissions ещё не представлены. Это reported runtime checkpoint, не direct readback Chat.

**[O2]** Отчёты executor в текущем треде от11–13.10: C1 release/receipt, C2 maturity/transfer conflict8→24 publications, storage43.34/40.69GB, SQLite99.80%, current commissioning и recovery locators. Их machine payload здесь не предоставлен. Executor проверяет exact files перед mutation.

### G — Git, один прочитанный design anchor

Base для ссылок: [lancerbeta/solana-alpha-lab @339c50dabe128a4c672028141f93d214152b6252](https://github.com/lancerbeta/solana-alpha-lab/tree/339c50dabe128a4c672028141f93d214152b6252). Это code/contract facts, не live health.

- **[G0]** [AGENTS.md](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/AGENTS.md), [FACTORY_SEMANTIC_MAP](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/docs/FACTORY_SEMANTIC_MAP.md): entry, routes, current authority, evidence границы.
- **[G1]** [live_cohort_vanilla_path.py](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/src/solana_alpha_lab/factory/live_cohort_vanilla_path.py), [opportunity_episode_release.py](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/src/solana_alpha_lab/factory/opportunity_episode_release.py): mutable `member_unit`, exact manifest/mirror, closure/seal/import; detailed prior source reads в этом треде дополнительно сверять по current blobs.
- **[G2]** [remote_ops.py](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/src/solana_alpha_lab/factory/remote_ops.py), [offhost_backup.py](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/src/solana_alpha_lab/factory/offhost_backup.py): consistent snapshots, stored ZIP, inventory и chain; copy lifetime и byte decomposition требуют actual readback.
- **[G3]** [retention owner](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/src/solana_alpha_lab/factory/observation_schedule_retention.py), [retention CLI](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/scripts/observation_schedule_retention.py): native APPLY существует, full payload scans и legacy due checks; не готовая гарантия episode-safe reclaim.
- **[G4]** [hot90_storage_admission.py](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/src/solana_alpha_lab/factory/hot90_storage_admission.py): 40/50GiB, commissioning PASS, physical producer reserve; новый scoped acceptance пока отсутствует.
- **[G5]** [Opportunity operator](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md), [core profile](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/configs/opportunity_episodes_jupiter_core_v1.yaml): boundaries, 139points, current quantitative settings, dispatch proof, raw retention.
- **[G6]** [same_envelope_renewal.py](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/src/solana_alpha_lab/factory/same_envelope_renewal.py): compiler/lease/authorization/rollover owner; episode-continuity proof не установлен чтением этого кода.
- **[G7]** [FACTORY_UNATTENDED_OPERABILITY](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/docs/operator/FACTORY_UNATTENDED_OPERABILITY.md): existing archive/watch/pulse/heartbeat, no-op и real write distinctions, external-watcher limitation.
- **[G8]** [trading_runtime_policy_v1.md](https://github.com/lancerbeta/solana-alpha-lab/blob/339c50dabe128a4c672028141f93d214152b6252/docs/contracts/trading_runtime_policy_v1.md): пример repo-native runtime revisions/commands/obligation-preserving policy, не разрешение переносить trading authority в collection.

### E — внешние первичные источники, проверены 13.10.2026

- **[E1]** [Python3.13 zipfile](https://docs.python.org/3.13/library/zipfile.html): STORED/DEFLATED, per-entry method, ZIP64. Реальную locked Python version выбирает existing environment, не эта ссылка.
- **[E2]** [SQLite Online Backup API](https://sqlite.org/backup.html), [PRAGMA](https://sqlite.org/pragma.html): consistent snapshot и bounded metadata diagnostics; incremental stepping API не равняется incremental remote backup.
- **[E3]** [SQLite VACUUM](https://sqlite.org/lang_vacuum.html): physical reclaim, scratch needs, ROWID и interrupted-copy caveats. Конкретная совместимость с SMIAL должна быть проверена на её schema/cursors.
- **[E4]** [Jupiter Tokens information, official source](https://github.com/jup-ag/docs/blob/main/tokens/token-information.mdx), [Jupiter rate limits](https://developers.jup.ag/docs/portal/rate-limits): query batch≤100; provider/account limits отдельно от локальных policy caps. Текущий entitlement пользователя из публичного документа не следует.
- **[E5]** [SQLite session extension](https://www.sqlite.org/sessionintro.html): changesets — отдельный механизм с требованиями к schema/PK/writer capture, не бесплатная замена backups. В этой программе не внедряется.
- **[E6]** [Restic repository copying/deduplication](https://restic.readthedocs.io/en/latest/045_working_with_repos.html): готовый maintained путь для отдельного сравнения, только если measured need останется; adoption здесь не разрешён.

### Итоговый truth boundary

Написан дизайн и bounded execution input, не выполнены product changes, deploy, provider calls, backup/retention APPLY или scientific looks. Новые thresholds, profile fields, CLI names, operational horizons и acceptance states выше — **предлагаемые требования**, кроме явно отмеченных existing facts. Текущие machine contracts изменяются только через их владельцев, с backward compatibility и exact evidence.
