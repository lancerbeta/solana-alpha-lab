# SMIAL — Research Shelf V1
## PRD + SSD для одного bounded atom

Дата: 24 октября 2026, Europe/Moscow.
Репозиторий: lancerbeta/solana-alpha-lab.
Проверенный main: ab13b7efa7efaf9762b6d12eca52e2348d1fe759.
Mode этого документа: DESIGN_ONLY. Entry recommendation: START.
Предлагаемое имя capability/atom: RESEARCH_SHELF_V1.

**Outcome:** Пётр и агенты сохраняют отложенный исследовательский вопрос одной короткой записью без PR; при следующем запуске исследования видят, к чему пора вернуться; результат связывается с существующим native исследованием и остаётся доступен будущему потребителю стратегии вместе с исходными ограничениями.

Документ — спецификация, а не доказательство реализации или разрешение на научный запуск. Перед исполнением сверить текущие AGENTS, semantic owners, policy и exact owner scope. Безопасный drift путей уточнить на месте; изменение outcome, authority или scientific semantics требует replan.

## 1. Решение и границы

Реализовать небольшую **полку исследовательских намерений** поверх Git. Она хранит идеи, предварительные наблюдения и обязательства вернуться к конкретной проверке. Native RESEARCH_FRAGMENT_V1, ResearchStore, ordinary operations, scientific budgets, эксперименты и promotion остаются владельцами своей истины.

В каждом продукте — свой namespace одинакового формата:
- SMIAL: новая data-ветка research-log.
- Scout: существующая data-ветка research-log.
- Записи: capsules/research_shelf_v1/<item_id>/<revision_sha256>.json.
- Код, schema, политика и постоянная навигация — в main через обычный engineering PR.
- Routine register/revise/link/close — append в data-ветку без PR после принятия capability и соответствующего metadata scope.
- Одна запись имеет одного владельца. Между продуктами — ссылки, без зеркальных редактируемых копий.

Полка не создаёт новую научную очередь, scheduler, evaluator, ResearchStore, БД, Issue tracker, сервис, автономный генератор или bot builder. Нет автоматического превращения WATCH в roadmap task. Текущие календарные уведомления продолжают служить сигналом открыть запись: проверка на запуске не гарантирует действие в настенное время, если пользователь не запускал исследование.

### Рассмотренные варианты

| Вариант | Решение |
|---|---|
| GitHub Issues как основной реестр | Удобный готовый backlog, но записи не являются Git tree/history. Не выбран при текущем требовании «в Git». |
| Один изменяемый Markdown/JSON в main | Прост, но routine changes конфликтуют с действующей review/merge моделью и загрязняют main оперативными переносами дат. |
| Одна общая полка в Scout | Меньше хранилищ, но SMIAL зависит от доступности другого продукта; сложнее ownership и граница private/public. |
| Две небольшие полки общего формата | Выбрано: независимость продуктов, reuse Scout transport, единый mental model без общей runtime dependency. |

Это проектное решение, а не требование внешнего framework. Совместимость обеспечивают маленький wire contract и одинаковые conformance fixtures. Общий Python package, monorepo, submodule и синхронизатор не нужны.

## 2. Подтверждённая база и существенные неизвестные

| FACT на проверенном ref | Следствие |
|---|---|
| AGENTS требует semantic route, exact task authority и guarded merge. | У полки нужен собственный route; не расширять delivery grants и не писать в main обходным путём. |
| ADR-006 разделяет capability Git, immutable ResearchStore и operational SQLite. FAST_LANE ограничен DATA_ROOT_ONLY. | Git публикация полки — отдельная metadata operation, не новый эффект внутри scientific Fast Lane. |
| research_fragments.py уже регистрирует exact native candidate/result, хранит планы и checks; source_snapshot используется UI и Forge. | Переиспользовать и ссылаться. Не переносить планы, counts, protection, caps или evaluator в полку. |
| RFV registration требует session_id, candidate_id, definition_sha256, result_ref/result_sha256 и declared role. | Идея без измерения законно живёт на новой полке; не подделывать RFV для её хранения. |
| Fragment run_due использует existing operations/reservations; recovery связывает landed result без повторного look. | Полка маршрутизирует к этому owner, не повторяет измерение после сбоя публикации. |
| forge-run уже имеет derived overlays вне receipt hash. | Использовать такой seam для краткой shelf summary; не менять hash-domain научного receipt. |
| Был реальный archive fingerprint incident: добавление readout projection фрагмента меняло frozen context. | Даты, lifecycle и обзор полки исключить из научной идентичности. Проверить отдельным regression oracle. |
| Native Forge требует frozen clean execution checkout и запрещает fetch/commit/ref movement в нём во время lifecycle. | Shelf transport работает в отдельном metadata repository/cache либо до freeze; внутри run читается закреплённый snapshot. |
| SMIAL public, Scout private. | Не копировать приватные Scout packet/formulas/results в публичную data-ветку. |
| Native passport уже сохраняет source_lineage для поддерживаемого HFIC replay; promotion manifest и StrategyVersion имеют точные source pointers. | Достаточен reader/resolver и явная связь с полкой; StrategyVersion schema менять не требуется. |

UNKNOWN: актуальные workstation RFV plan heads, protection, execution bindings, результаты и зарезервированные budgets. Они не проверялись из облака. Тексты напоминаний дают точные locators и исторические hints, но не live readiness. Новые market looks, запуск Forge, runtime repair и научная миграция в ходе проектирования не выполнялись.

## 3. Пользовательский сценарий

Пётр говорит: «Сохрани наблюдение X; вернуться после Y / 10 ноября; проверить Z». Агент:
1. Проверяет точный existing native/source identity, если он указан; предлагает reuse записи вместо дубликата.
2. Записывает краткое намерение, условие возврата и источник. ID, UTC clocks, revision/hash и Git transport заполняет инструмент.
3. Возвращает ID, смысл, дату/событие, ссылку и статус сохранения. Локальный неподтверждённый draft не называется сохранённым в Git.
4. При следующем research entry сначала показывает короткий обзор полки.
5. Для выбранной due записи читает actual native state и либо продолжает уже разрешённый exact scope, либо даёт одну конкретную постановку/границу.
6. После результата сохраняет exact link или новое решение о возврате. Закрытая запись остаётся доступна поиску происхождения.

Обычный readout:

> Полка: 2 пора проверить, 1 ждёт source readback, ближайшая дата — 10 ноября.
> TOPTRADED: наступил срок сверки; научный запуск пока не проверен. Следующее действие — metadata readback exact protocol и 14 cohorts.
> RFV-8228: ждать; контрольная дата 20 ноября, источник плана закреплён.

При отсутствии изменений — одна строка. Не записывать commit на каждый просмотр и не выводить полный архив перед каждым запросом.

## 4. Data contract V1

### 4.1 Хранение и идентичность

Каждая публикация — полная компактная JSON-ревизия одной записи. Предыдущие JSON-файлы не изменяются и не удаляются. Текущее состояние вычисляется по родителям ревизий в pinned tree; Git timestamp, имя «latest» и порядок файлов не выбирают победителя.

Stable item_id создаётся один раз, например RSI-SMIAL-<UUID>. Для миграции source-native объекта использовать стабильный origin_key, связывающий owner + exact object + цель follow-up. Повтор одного origin_key возвращает existing item; uniqueness непустого origin_key проверяется на каждом новом remote head, в том числе при concurrent genesis с разными UUID. Произвольные текстовые идеи не объединять по LLM similarity; явные duplicates связывать с канонической записью.

Canonical JSON: UTF-8, sorted keys, компактные separators, ensure_ascii=false, allow_nan=false, без BOM. revision_sha256 = SHA-256 canonical body без поля revision_sha256; trailing newline в файл входит, в этот digest — нет. Повтор использует те же подготовленные bytes, mutation_id и clocks, а не генерирует их заново.

| Поле | Назначение / минимум |
|---|---|
| schema_version | Строка "1.0"; неизвестная версия — явная ошибка конкретной записи |
| item_id, product, origin_key | Stable identity; product = SMIAL или SCOUT; origin_key nullable для новой свободной идеи |
| revision_sha256, parents, mutation_id | Hash; normal revision имеет одного parent, genesis — ни одного; mutation_id стабилен при retry |
| created_at, updated_at | RFC3339 UTC; created_at сохраняется во всех ревизиях |
| kind | IDEA, OBSERVATION или FOLLOW_UP; не scientific verdict |
| title, statement | Короткое название и точный сохраняемый смысл, включая вопрос/гипотезу |
| state | OPEN, FOLLOWING или CLOSED — только административный lifecycle |
| origin_refs | Источники утверждения; пустой список допустим для непроверенной идеи с явной пометкой |
| review | review_at, review_by и event; nullable, с семантикой ниже |
| next_action | intent + owner_route + optional exact scope_ref; данные, не shell command |
| native_links | Точные связи с native plan/operation/candidate/experiment/strategy и adopted revision |
| last_decision | Дата, disposition, reason, evidence refs и новая точка возврата; только содержательное изменение |
| closure | Для CLOSED: reason, evidence/ref либо явная административная причина, optional successor |
| change_reason | Зачем появилась новая ревизия; не generic heartbeat |

Неполную мысль можно сохранить: OPEN с отсутствующим trigger показывается NEEDS_TRIAGE на ближайшем research entry. Не выдумывать protocol, parameters, effect size, source timestamp или «положительный результат» ради заполнения формы. До предметного обсуждения такая запись не является поручением на исследование.

mutation_id — непустая, не состоящая только из whitespace opaque строка клиента.
UUID — допустимый способ генерации, не обязательный формат. Reader/writer не
обрезают, не нормализуют и не переиздают этот ID: retry и conflict сравнивают
точную строку. Опубликованные текстовые IDs Scout читаются без миграции истории.

Logical reference:
- Git: kind=GIT, repository, commit (40 hex), path, sha256 (проверенных file bytes).
- Native: kind=NATIVE, owner, entity_kind, entity_id, payload_sha256 при наличии, logical locator; физические workstation paths не публиковать.

Native locator сохраняет точные bytes логической ссылки: прежний относительный
locator или поддержанный URI `smial-data://research/records/...`. Reader не
обращается к URI и не превращает ссылку в разрешение доступа/научный допуск.
Физические пути, file URI и control/path traversal не становятся допустимыми.
- External/source hint: kind=REFERENCE, locator/description, observed_at, verification=UNVERIFIED или проверенный класс. Не все источники имеют durable hash; это отражается честно.
- Связь: relation + exact source/destination refs + adopted_item_revision. relation имеет понятный смысл: INSPIRED_BY, CONTINUED_FROM, RELATED, SUPERSEDED_BY, HANDED_OFF_TO.
- Ветка используется только для получения актуального head. Evidence ссылка закрепляется за commit и bytes, а не за moving branch URL.

adopted_item_revision ссылается на уже опубликованную прежнюю ревизию, не на собственный ещё не созданный hash/commit link revision. При capture существующего native объекта его точный источник входит в origin_refs; adoption link при необходимости добавляется следующей ревизией. Это исключает self-hash cycle.

Первоначальный ограничитель ресурса: 64 KiB на revision, 1 MiB на batch. Это защита transport/читаемости, не лимит науки. Большие отчёты, raw data, private bodies и ledgers остаются у owners; в записи — refs. При превышении дать конкретный oversized field/locator, сохранить подготовленный локальный draft и предложить ссылку вместо копии; без silent truncation.

### 4.2 Состояния и результаты не смешиваются

| Состояние полки | Значение |
|---|---|
| OPEN | Намерение сохранено; ждёт review/условия/определения следующей проверки |
| FOLLOWING | Есть exact native consumer; полка ведёт к его текущему состоянию |
| CLOSED | Намерение выполнено, отменено, заменено, признано дубликатом или явно передано native owner |

CLOSED с reason=HANDED_OFF не означает PASS/PROMOTE. Отказ провайдера, cap, технический STOP, INCONCLUSIVE и научное опровержение сохраняют разные native причины. Повторное рассмотрение оформляется новой ревизией с причиной и изменившимся условием; spent trials/exposure не обнуляются. Существенно новая научная формулировка получает native новую definition/version по существующим правилам.

### Общие вложенные типы и conformance

Нормативные поля envelope присутствуют всегда; неизвестные значения представлены null/[] по типу, а не выдуманным фактом. SHA-256 — 64 lowercase hex; clocks — RFC3339 UTC с Z. parents отсортированы, существуют в том же item, их hash проверяется; missing parent — ITEM_INVALID/INCOMPLETE. Удаление неизвестного поля при read/rewrite недопустимо: неподдерживаемый wire version отклоняется для affected item.

- review = {review_at: UTC|null, review_by: UTC|null, event: Event|null}.
- Event = {kind: NATIVE_STATUS|SOURCE_CHANGED|MANUAL, source: SourceLocator|null, condition: string|null, acknowledged_ref: Ref|null}.
- SourceLocator — {kind:GIT_PATH, repository, ref, path} либо {kind:NATIVE_ENTITY, owner, entity_kind, entity_id}. Это место поиска current состояния; полученный evidence всегда превращается в immutable Ref. Не произвольный URL/shell.
- NATIVE_STATUS сравнивает condition с поддерживаемым source-owned status/next_action; не интерпретирует формулы. SOURCE_CHANGED сравнивает immutable evidence с acknowledged_ref; без baseline возвращает UNKNOWN. MANUAL хранит condition человеческим текстом и автоматической истины не получает.
- next_action = null либо {intent, owner_route, scope_ref: Ref|null}.
- last_decision = null либо {at: UTC, disposition: string, reason: string, evidence_refs: Ref[]}; новые даты хранятся только в review.
- closure = null либо {reason: string, evidence_refs: Ref[], successor: Ref|null}; CLOSED требует closure.
- native_links — список {relation, adopted_item_revision: GitRef, destination_refs: Ref[], adoption_key: string|null, verification: VERIFIED|PARTIAL, gaps: string[]}. Source — adopted revision и её origin_refs; произвольный link не делает evidence научно допущенным.

При содержательном review/defer можно записать exact observed evidence в acknowledged_ref. Повтор того же MET без нового evidence не будит второй раз; новая review_at продолжает работать. UNKNOWN не подтверждается как обработанное событие. now>=review_by всегда даёт OVERDUE_REVIEW независимо от review_at; это administrative attention, не native expiry.

Общая conformance fixture нужна одна небольшая: genesis идеи; due дата; UNKNOWN event; содержательный defer с acknowledgement; exact native link к прежней revision; close; same-item fork/reconcile. В обоих репозиториях одинаковые JSON bytes и expected digests/projections. Fixture синтетическая, без private payloads и science runs.

item_id, product, origin_key и created_at неизменны в lineage item. Одинаковый mutation_id с другими prepared bytes — MUTATION_ID_CONFLICT, не retry. origin_key uniqueness проверяется также среди CLOSED/history; закрытие не освобождает source identity. Поле, не затронутое конкретным update, сохраняется.

Нормативный genesis example (только синтетика, не seed migration). Ниже JSON показан с отступами для чтения; publish сериализует его canonical-правилом выше. Оба readers обязаны получить revision_sha256 из примера; SHA-256 canonical file bytes с завершающим newline — dd7dde379c136e401e2647a6e1f022f689e14c0d18036bd8a98a38c7d82224e9.

```json
{
  "change_reason": "Synthetic capture.",
  "closure": null,
  "created_at": "2026-10-24T00:00:00Z",
  "item_id": "RSI-SCOUT-00000000-0000-4000-8000-000000000001",
  "kind": "IDEA",
  "last_decision": null,
  "mutation_id": "00000000-0000-4000-8000-000000000002",
  "native_links": [],
  "next_action": {
    "intent": "Review relevance only.",
    "owner_route": "LIFECYCLE",
    "scope_ref": null
  },
  "origin_key": null,
  "origin_refs": [],
  "parents": [],
  "product": "SCOUT",
  "review": {
    "event": {
      "acknowledged_ref": null,
      "condition": "A future consumer asks for this context.",
      "kind": "MANUAL",
      "source": null
    },
    "review_at": "2026-10-31T00:00:00Z",
    "review_by": null
  },
  "revision_sha256": "264ecdb2f41c005e7766dc065ae52d2c845e338beb07418607e33f24bb168465",
  "schema_version": "1.0",
  "state": "OPEN",
  "statement": "Synthetic unmeasured idea for wire conformance; no market claim.",
  "title": "Synthetic deferred observation",
  "updated_at": "2026-10-24T00:00:00Z"
}
```


## 5. Триггеры: когда посмотреть и когда разрешено действовать

review_at — время следующего просмотра.
review_by — желательная последняя точка внимания/напоминания.
Native input_closed_at, earliest evaluation и hard execution deadline — поля source-owned плана/протокола; полка их не переопределяет.

event — небольшая ссылка на source-owned сигнал:
- NATIVE_STATUS: известный adapter читает сохранённый native status/next_action или readiness receipt.
- SOURCE_CHANGED: после появления новой source revision пора перечитать сохранённое evidence; само изменение не значит поддержку гипотезы.
- MANUAL: условие человеческим текстом и источник проверки; автоматический evaluator его не «понимает». Нужна review_at либо NEEDS_TRIAGE.

Только adapters для реально используемых owners этого атома: SMIAL fragment/plan и Scout saved readiness/status. Новые события можно сразу сохранить как MANUAL. Универсальный predicate DSL, eval, произвольные shell/HTTP команды из записи и registry плагинов не создавать.

Результат event-read: MET / NOT_MET / UNKNOWN + exact source/as_of/reason. Отсутствие доступа, stale binding, повреждённый источник и неподдержанный adapter — UNKNOWN, не false и не ready.

**Attention:** наступил review_at ИЛИ review_by ИЛИ сработало новое, ещё не подтверждённое review событие. Это повод для review.
**Scientific action:** выполнены ВСЕ условия native protocol, actual authority, budget, protection, source availability и текущего запроса. Условия внимания и scientific admission — разные вычисления.

Для каждого entry:
1. Прочитать весь компактный active set на одном data commit; определить attention детерминированно.
2. Показать urgent/deadline, затем due, unresolved и ближайшие даты. Детали по умолчанию максимум 5, но totals и omitted_count обязательны; --all раскрывает остальные.
3. Истёкший native deadline → EXPIRED_REVIEW_REQUIRED, без переноса окна и запуска задним числом. Recovery уже сохранённого результата остаётся native metadata operation.
4. Без нового события и после содержательного defer одна и та же дата не создаёт повторный run. Новая review_at/decision записывается только при реальном решении.
5. При отсутствии события продолжать ждать; для MANUAL review дата защищает от вечной невидимости.
6. Скан не создаёт native reservation, не читает новые market values и не расходует look.

Существующий OPEN native attempt проверяется раньше запуска нового: resume/reconcile принадлежат native owner. Пауза/архивация карточки не останавливает его, не снимает universe gate и не возвращает budget.

## 6. Публикация без PR и восстановление

### 6.1 Узкая metadata policy

В main принять отдельный namespace-scoped контракт:
- Разрешены только append валидных V1 JSON в выделенный prefix data-ветки.
- Разрешены capture/review/defer/link/close и хранение verified source refs.
- Main, executable code, schemas, policy, experiment definitions и scientific grants через этот путь не изменяются.
- Только non-force публикация; никаких branch settings, history rewrite, удаления старых ревизий или прямого main push.
- Routine запись в принятом metadata scope не запускает delivery harness, CI/PR и повторный owner merge gate.
- Сохранённый в карточке scope_ref не создаёт и не продлевает разрешение на experiment, spend, provider или deploy.

Реализация полки — обычный engineering atom. Первичное создание data ref и публикация согласованных seed rows входят в явно принятый implementation/commissioning scope; не выводить разрешение из одной лишь доступности credential. Уже данное exact разрешение не спрашивать повторно.

### 6.2 Малый transport

Scout уже имеет lab_publish.publish_files. Для SMIAL применить тот же проверенный алгоритм append-only Git в узком helper, без runtime зависимости на Scout. Git auth — существующий transport. Не создавать новые credentials/scopes.

Использовать отдельный bare metadata cache/repository вне frozen execution checkout. Не переключать рабочую code branch, не менять её index/refs и не выполнять код из data-ветки. Normal reader читает закреплённый local snapshot; cloud reader — тот же commit через connector. Fetch/publish не прячутся внутрь DATA_ROOT_ONLY research owner.

Порядок одной операции:
1. Подготовить bytes и stable mutation_id один раз.
2. Получить актуальный data head H. Сначала найти exact prepared revision/mutation: те же bytes уже опубликованы → ALREADY_PUBLISHED, даже если current item уже имеет потомков.
3. Если revision ещё нет, проверить expected_heads конкретного item и uniqueness origin_key на этом H; провалидировать schema, refs/visibility, hash, secret/path/size guards.
4. Построить один commit с parent H, diff только по разрешённым новым JSON.
5. Non-force push либо API commit с expectedHeadOid=H.
6. Прочитать remote exact path/hash и подтвердить publication.
7. При гонке другой записи — перечитать новый H, повторить idempotent readback, item-head и origin-key проверки; retry тех же bytes максимум 3.
8. Если изменился сам item — STALE_ITEM_REVISION; сохранить draft и reapply содержательное изменение после чтения нового состояния. LWW запрещён.
9. Timeout после push → readback exact revision/mutation_id, затем ALREADY_PUBLISHED либо PENDING_PUBLICATION. Повтор science здесь отсутствует.

Contents API blob SHA не является branch CAS. При использовании Git Database REST создать commit с pinned parent и обновить ref non-force; при конфликте перечитать item. Не публиковать логически связанную batch раздельными неконтролируемыми file-update calls.

Для cloud без локального Git уже доступны connector operations create_blob → create_tree(base_tree_sha) → create_commit(parent_sha=H) → update_ref(expected_sha=H, force=false), затем exact readback. Это альтернативный transport того же prepared batch, не другой wire или обход branch protection. На acceptance доказать, что принятый namespace действительно допускает no-PR публикацию; settings/credentials не менять скрыто. Pure validate/prepare/fold не должны требовать RDP/ResearchStore при import; native adapters подгружаются только при доступности соответствующего source.

### 6.3 Конфликт и неполное чтение

Normal writer не создаёт fork одного item. Если fork всё же обнаружен (например, ручная публикация):
- reader сохраняет обе головы и возвращает ITEM_CONFLICT;
- affected item не выбирается для action; остальные продолжают работать;
- явная metadata reconciliation создаёт новую full revision с parents равными ВСЕМ текущим competing heads и объяснением решения;
- история сохраняется. Автоматически объединять противоречивые научные формулировки нельзя.

Missing branch = NOT_INITIALIZED, unreadable = UNAVAILABLE, offline cache = STALE_AS_OF, invalid item = ITEM_INVALID, incomplete listing = INCOMPLETE. Ни один случай не означает «полка пуста». Неполнота блокирует зависимое решение, но не отменяет независимое уже разрешённое native продолжение.

Чистое чтение не коммитит last_seen и не создаёт отдельный operational journal. Derived views/cache можно удалить и восстановить из data tree.

## 7. Интеграция с обычной Кузней

### Обязательный entry

В repository skill/command перед новым исследованием или research orientation:
- resolve route → bounded remote refresh в metadata cache → read summary;
- для frozen resume использовать already pinned scientific inputs; свежий обзор полки не переключает research question;
- для облачного чата — direct explicit-ref read по route, без запуска workstation.

На машинном public entry тоже должен быть read-only hook: например, derived shelf_summary в forge-run readout, вычисленный после scientific receipt hash. Он читает snapshot; не исполняет Git transport, native plan, provider или evaluator. Отсутствующий/неподтверждённый snapshot виден как UNAVAILABLE/STALE, с точной командой безопасного refresh. Не подменять этим next_action текущего native run.

Минимальная entry matrix:

| Вход | Как применяется полка |
|---|---|
| Fresh /hypothesis-forge, выбор/authoring нового исследования | Agent review до первого native preflight; actual cmd_forge_run._emit_run добавляет derived summary и при success, и при blocked/missing data root |
| Fresh direct experiment/operator entry вне Forge | Тот же metadata review на top-level task entry; route явно перечисляет применимые public commands, не оборачивает каждый helper |
| Frozen resume, approved RFV import/run-due | Review отдельной metadata CLI/agent operation; existing native continuation сохраняет scope и входы. Старый frozen executable может не иметь hook: ради обзора его code/refs не обновляются |

Final entry audit связывает каждый поддерживаемый research front door с этим общим review, чтобы direct path не оставался слепым. Никаких новых запретов на независимое уже разрешённое recovery.

Нужно доказать **реальный entry path**, а не только добавить фразу в AGENTS. На каждую tool invocation refresh не повторять: одна проверка на top-level research session, дополнительные — по явному изменению/запросу.

### Запись результата / отложенного вопроса

У agent orchestration после research result есть короткое правило:
- сохранять только явно удержанный fragment/вопрос/обязательство с useful next condition;
- native object уже есть → регистрировать pointer, не второй объект;
- терминал без дальнейшего обязательства → existing source/history, без нового OPEN;
- изменение уже известного item → revision, не ещё одна карточка.

Научные functions не начинают Git publication как побочный эффект. Agent/helper вызывает metadata operation отдельно, в принятом scope. Сбой публикации оставляет prepared bytes и native receipt, а не отменяет native результат. В следующей сессии восстанавливается только metadata link.

Для реально enabled RFV плана действуют существующие import caller и run-due. Generic shelf scan их автоматически не вызывает. При owner-authorized research, который уже покрывает конкретный native follow-up, агент может вызвать штатный runner после live gates без нового PR и без повторного разрешения на тот же scope.

## 8. Происхождение и дальнейшее использование

### 8.1 Кто чем владеет

| Сущность | Authoritative owner |
|---|---|
| Намерение вернуться, administrative state, review dates | Git shelf item revisions |
| Формула, definition, native candidate/version | Existing HFIC / hypothesis owners |
| Plan, windows, input eligibility, budgets, protection | Native ResearchStore/protocol owners |
| Исходы, negative evidence, trial/exposure | Existing results/ledgers |
| Decision/PROMOTE, StrategyVersion, execution constraints | Existing experiment/promotion/trading owners |
| Краткий объединённый обзор или dossier | Derived reader; никакой новой scientific authority |

### 8.2 Узкий link/resolve contract

Добавить операции show/resolve --item и find/resolve --native-ref. Они читают источники и возвращают машинный JSON-досье; не запускают research, не вычисляют новые returns и не публикуют комбинированный документ.

Связь с native candidate проверяется по реальному readback и сохраняет:
- adopted immutable shelf revision;
- session_id, candidate_id, полный definition_sha256;
- exact native record ID/payload hash, когда HYPOTHESIS_VERSION действительно существует;
- frozen draft/packet artifact ref/hash;
- result/critic refs и их actual hashes, когда они существуют;
- optional exact ExperimentSpec/hash, operation/plan или StrategyVersion identity.

Не все поля доступны на ранней стадии. Partial link допустим с явными gaps; COMPLETE_SOURCE_TRACE требует всех доказанных звеньев выбранного маршрута. Link подтверждает происхождение, не native научный приём внешнего evidence.

Inverse lookup включает CLOSED и исторические revisions. Возвращает все точные связи; при неоднозначности — AMBIGUOUS_SOURCE_LINK, без выбора по title/дате. Downstream читает adopted revision, не сегодняшний snooze/state.

Ошибочный association можно явно отозвать: новая full revision удаляет его из current native_links и сохраняет last_decision с причиной/refs. Исторический inverse lookup показывает его как RETRACTED_SOURCE_LINK; он больше не доказывает действующую связь. История исходного принятия остаётся доступной. Выбор adopted content определяется старой immutable revision, а актуальность самого association — текущей полной записью; эти два вопроса не смешивать.

### 8.3 Existing supported science→strategy path

Для поддерживаемого HFIC replay уже есть:

StrategyVersion.source_decision_asset_id
→ immutable DECISION_EVENT.promotion_handoff_manifest
→ exact ExperimentSpec + direct evidence
→ saved passport/result.source_lineage
→ native session/candidate/definition
→ exact shelf relation
→ adopted revision и original sources/limitations.

document_runner._frozen_hfic_replay_lineage проверяет Spec 1.3/1.4 REUSE_ONLY, завершённую session, candidate/definition, exact recipe, один grounded result, saved Critic terminal/hash. RUN_COMPLETED сохраняет passport с source_lineage. promotion_handoff уже сохраняет необходимые source pointers. Расширять StrategyVersion и promotion manifest ради полки не требуется.

Resolver читает exact decision по StrategyVersion.source_decision_asset_id и проверяет его manifest/hash. Existing compose_science_to_strategy_handoff выбирает latest PROMOTE для experiment; такой latest-view нельзя использовать для происхождения старой StrategyVersion. Затем идти только по direct evidence к точному RUN_COMPLETED/passport, без выбора «самого нового результата».

Для legacy/non-replay без этого моста нужен explicit verified link к exact ExperimentSpec/hash либо UNRESOLVED. Не угадывать session по сокращённому HYP alias. Будущий bot constructor/enhancer получает native допущенный artifact, а через resolver — откуда он возник, как проверялся и какие ограничения сохранились.

### 8.4 Что нельзя потерять

Dossier показывает exact source definition/parameters, population/clocks, estimand/target, method/config/code/input bindings, source run/result/critic, trial/exposure history, negative/inconclusive evidence, четыре native risk fields и allowed use — где они действительно сохранены. Недостающие вводные перечисляет, не достраивает.

Для measured SMIAL источников передавать настоящие RFV/result/native refs по existing prior_work_refs; проверять actual saved draft и Critic closure. Произвольный Git/shelf URI не добавлять туда как «поддерживаемый native prior»: текущий resolver его так не трактует.

Unmeasured idea проходит обычное native authoring/testing. Private Scout packet остаётся в Scout или разрешённом local-native storage. Внешний exploratory результат не становится native-admitted evidence от одного link: SOURCE_EVIDENCE_NOT_ADMITTED остаётся явным, пока поддерживаемый научный маршрут его не проверил. Это не блок регистрации/навигации; scientific promotion определяется существующими gates.

### 8.5 Recovery handoff

До native шага подготовить stable adoption_key из item_id + adopted_revision + intended destination owner/route + stable request identity. Ещё не существующий native ID не входит в pre-call key. Это identity metadata association, не замена native idempotency/operation owner. Export сам не создаёт candidate; после native шага link использует сохранённые exact outputs и прежний adoption_key.
Если native шаг завершился, а link publication нет:
- сначала native saved-state readback по известным identity;
- найти/подтвердить уже созданный target;
- опубликовать только link тем же adoption_key;
- не повторять MAIN, generation или Critic ради «красивого завершения» полки.
Если exact target нельзя восстановить, LINK_PENDING с missing identity и точным readback действием. Нельзя создавать второй candidate, предполагая, что первый не появился.

## 9. Навигация и конкретные seams

Имена новых файлов ниже — рекомендуемые; executor может выбрать соседние consistent paths при сохранении одного semantic owner.

| Existing owner / proposed file | Изменение |
|---|---|
| AGENTS.md | Короткий RESEARCH_SHELF route и правило entry/capture; без копии schema/истории |
| configs/factory_semantic_operability_v1.yaml + Catalog owners | Новый SEM-RESEARCH-SHELF; reference-only, authority_granted=false |
| docs/FACTORY_SEMANTIC_MAP.md | Регенерировать существующим generator, не править вручную |
| delivery-harness/context-map.yaml | L2 binding к contract/locator; ordinary task selection не менять |
| docs/contracts/research_shelf_v1.md (new) | Один canonical contract: wire, source boundaries, operation/recovery |
| configs/research_shelf_v1.json (new, либо existing config owner) | repository/ref/prefix/metadata-cache binding; без personal absolute paths |
| src/solana_alpha_lab/factory/research_shelf.py + scripts/research_shelf.py (proposed) | Малые reader/validator/append wrapper/trigger adapters/link resolver; без общего workflow engine |
| scripts/hypothesis_forge.py, repository hypothesis-forge SKILL/command | Actual read-only summary seam + top-level refresh/registration routing |
| research_fragments.py / hfic_prior_memory / promotion_handoff | Reuse existing read owners. Менять только если конкретный test выявил отсутствующий public accessor; не переносить scientific state |
| Existing lifecycle/workbench | Дать route к полке. Новый UI/dashboard не входит в первый atom; native fragment UI сохраняется |

Cloud route обязан называть repository + branch + prefix + explicit-ref read recipe. GitHub code search индексирует default branch; отсутствие search hits не означает отсутствие data-ветки.

Cloud checks: при research launch, выборе следующего вопроса, обсуждении status/deadlines или прямом «посмотри полку». На unrelated explanation/каждую реплику чтение не нужно. Existing project Kernel уже требует AGENTS → semantic route; переписывать constitution или делать Cloud Sources activation gate не требуется.

Предлагаемые команды/операции, exact spelling на усмотрение executor:
- list/show/resolve/find — read-only, JSON + краткий RU output;
- prepare/apply — prepare validated revision, scoped append;
- review — read-only attention с pinned source commits;
- link — verified existing native association;
- close/reopen/reconcile — metadata revisions с reason.
Это один CLI, не отдельный скрипт/receipt/service на каждый глагол.

## 10. Первичная миграция: конкретный набор

Сначала сверить active native objects и exact saved plans на workstation. Не читать весь архив. Начальный bounded read-set: две SMIAL проверки ниже, existing active fragment cards/plans и текущие сохранённые next actions, плюс cross-link на один Scout forward.

Текущие пять enabled напоминаний прочитаны 24.10.2026 через read-only schedule metadata; это transport hints, а не native runtime evidence. Они сводятся к трём предметным записям.

| Canonical item | Известный locator / время | Действие миграции |
|---|---|---|
| SMIAL TOPTRADED prospective 14d | RFV-B9572ACAD0F502B28E54BC11113B82EE; protocol SHA256 70246143a271ba4a2b74c53c499ac482bdbe1231f604f087f5d3532235741fd2 | Одна FOLLOW_UP запись; review_at 2026-11-10T09:00:00Z, review_by 2026-11-13T09:00:00Z. Сверить exact native protocol, result/terminal и scope. |
| SMIAL RFV-8228 | RFV-8228C9408D18DE5CC98C9C1EA924B1C8; plan artifact RF-ART-7C7A05CDF00A292D4E75A2247E35A706A54B826A; frozen plan SHA256 11e0f6becbd0600aeb081ad2d9a524399d67d774d33cd1bcd9d8baf230a72c61 | Одна FOLLOW_UP запись; review_at 2026-11-20T09:00:00Z, review_by 2026-11-23T09:00:00Z. Исторический hint от 23.10: FRAGMENT_EXECUTION_BINDING_CHANGED; actual current binding/rebind обязательно перечитать. |
| Scout concurrent forward | Source-owned item у Scout; protocol_id ea03ea87629c0a9a6cf489824c44573c3845ec3a8e5d9a7a22bfa8b2379e3902 (это ID, не file hash); [exact protocol](https://github.com/lancerbeta/marcopolo-scout/blob/21c4745809509509ea50ef9ee737113bfdecfa9a/capsules/concurrent_forward_observation_v1/ea03ea87629c0a9a6cf48982/protocol.json) | В SMIAL — read-only cross-reference/route, не вторая каноническая OPEN запись. Контроль 31.10 в 03:05 МСК. |

Из reminder prompts известны: TOPTRADED admissions [24.10 00:00Z, 07.11 00:00Z), earliest evaluation 10.11 00:06Z, hard deadline 14.11 00:00Z; RFV-8228 admissions [20.10 00:00Z, 17.11 00:00Z), input closure 20.11 01:00Z, hard deadline 24.11 00:00Z. Это pending native verification. В частности, напоминания 13/23 ноября 12:00 МСК не являются scientific deadlines: они на 15 часов раньше.

Сохранённые scope hints тоже переносятся как проверяемые ограничения: TOPTRADED MAIN≤1, PREVIEW=0, ADAPTIVE=0, LIMITED_RESULT; RFV-8228 — максимум одна evaluation. Readiness сверка начинается с metadata/readback, не с targets. Native evaluation и возможный rebind требуют своего действующего exact scope; metadata migration его не создаёт. При расхождении reminder и actual frozen plan решает native owner, а расхождение явно фиксируется.

Если native source недоступен, зарегистрировать саму обязанность и locators как UNVERIFIED_SOURCE, без PLAN_ENABLED/READY. Это завершённый capture и незавершённая native reconciliation; не выдавать полную миграцию за PASS. Не переносить окно и не чинить binding как часть metadata migration.

Старые closed/superseded записи не оживлять. Audit migration даёт одну небольшую таблицу: source → item/relation → disposition → unresolved. Один seed JSON package можно применять идемпотентно; новые журналы на каждую строку не нужны.

## 11. Минимальные вертикальные проверки и DoD

Техника — выбор исполнителя. TDD не обязателен. Использовать existing fixture factories и native public seams; добавить только проверки новых material risks. Mock transport/clock допустим, mock результата собственным алгоритмом — слабый oracle.

| ID / путь | Независимый oracle / ожидаемое поведение |
|---|---|
| V1 Capture → Git → cold/cloud-style read → due | Реальный disposable bare Git remote, ручная таблица дат/статусов. Register/revise сохраняются без main diff/PR. Cold explicit-ref reader видит те же refs и UNKNOWN. Чтение без Git/RDP/SQLite writes и market/provider calls. |
| V2 Concurrency + lost reply | Два реальных writers: разные items сохраняются; same-item stale parent отказывается после branch retry. Повтор тех же bytes — один revision. Timeout после фактического push распознаётся readback. Преднамеренный fork даёт CONFLICT, явный reconcile сохраняет обе истории. |
| V3 Date / event / unavailable / expiry | До/на/после UTC границы; MET/NOT_MET/UNKNOWN; неполная выдача; unreadable native source; прошедший hard deadline. Ноль science effects. У unrelated разрешённого continuation свой gate, отсутствующая полка не превращает результат в false/empty. |
| V4 Real Forge entry + frozen isolation | Вызвать реальный public entry с synthetic fixture, включая blocked/missing RDP: summary присутствует, source pinned, native next_action сохранён. При одной accepted code/input version изменить только snooze/state/другую запись: native Git fence, definition hash, market/archive fingerprint, frozen packet и spent counts не меняются. Новый accepted code законно имеет новую code identity; не исключать файлы из native code hash ради теста. Подмена material result hash по-прежнему отвергается. |
| V5 Origin → native → strategy reader | Поддерживаемый existing synthetic native путь: genuine prior refs → actual saved draft/freeze/Critic fields → exact native links → existing Spec/passport source_lineage → валидный StrategyVersion fixture → resolve origin. Сверить заранее заданные параметры, один adverse факт, один UNKNOWN и exposure. Два PROMOTE для одного experiment: старая StrategyVersion разрешается через её exact decision, не latest. CLOSED и более новая shelf revision не меняют adopted source. Fixture доказывает transport, не scientific PROMOTE. |
| V6 Publication failure после native результата + privacy | Native result уже сохранён; metadata push fails. Resume публикует только link, evaluator/Critic call count не растёт. Private Scout sentinel/body не попадает в public Git; permitted pointers остаются. Нет доступа к private source → UNAVAILABLE, не пустой admitted evidence. |
| V7 Migration и front-door legibility | Seed fixture: две даты одного RFV → один item; native completion → закрытие/ссылка, а не повтор; screenshot reminder date ≠ hard deadline. Новый isolated reader получает только AGENTS/semantic route и находит branch/prefix/exact source без task archaeology. |

Не нужно семь новых больших test modules: сгруппировать shared fixtures и расширить ближайшие проверки. Reuse tests/test_research_fragments_v1.py, tests/test_forge_native_lifecycle_closure_v1.py, tests/test_hfic... working-view/fingerprint и semantic route tests только в затронутом scope. Не прогонять новые LLM/scientific cycles ради metadata acceptance.

DoD:
- entry routing реально работает; cloud explicit-ref path проверен;
- no-PR writer изолирован от main/frozen execution; race/recovery проверены;
- native truth и provenance различены, supported downstream trace проходит;
- текущие seeds захвачены, partial native reconciliation явно отражена;
- source/private boundary выдержана;
- existing required CI/review/merge gates выполнены по current Git policy;
- handback содержит одну таблицу результата, exact code/data refs, проверки и residuals.

В этой design-сессии продуктовые тесты не запускались; таблица — обязательство будущей реализации, не reported PASS.

## 12. Порядок доставки, scope budget, rollback

Один engineering PR:
1. Проверить актуальные owners и strongest reuse; закрепить outcome/границы.
2. Реализовать wire reader + append с реальным Git fixture.
3. Добавить entry summary, source adapters и exact links/resolver.
4. Обновить только затронутые semantic owners; выполнить V1–V7 и existing required gate.
5. После accepted version выполнить authorized data-branch bootstrap + bounded seed capture/reconciliation; дать cold readback. Не запускать отложенные scientific checks этим атомом.

Ожидаемый масштаб — несколько сотен строк product code, focused tests и один canonical contract, а не новый subsystem. Это оценка, не line-count KPI. Если проект требует новую БД, scheduler, второй mutable registry, общий package, массовую schema migration или тысячи строк чужой scientific логики — остановиться и упростить. Не добиваться малого diff code-golf и удалением recovery.

Свобода исполнителя: filenames, internal decomposition, CLI spelling, выбор existing fixtures/валидатора, формат RU table и cache strategy. Invariants: один owner, append history, explicit refs, native authority, source privacy, frozen isolation, отсутствие hidden market looks.

Rollback: выключить entry hook/вернуть прежний reader code; data-ветку и native artifacts сохранить. Старые JSON читаются совместимым V1 reader. Ошибочную дату/метаданные исправить новой ревизией; не rewrite. Отказ capability не возвращает spent science budget.

### Через неделю и через 30 дней

| Горизонт | Проверяемый эффект / условие следующего изменения |
|---|---|
| 7 дней | Новая сессия находит все реальные active obligations; нет потерянных dates, duplicate entries, per-launch commits или повторных same-event experiments. |
| 30 дней | Закрытые/переданные записи не шумят; successful и negative lineage доступны; без сети виден truthful stale state; рабочий набор и чтение укладываются в обычную сессию. |
| WATCH | Только измеренный рост/медленное чтение обосновывает derived index. Он остаётся rebuildable. Новый scheduler рассматривается лишь если invocation-based review реально пропускает материальные сроки. |

Не превращать эту таблицу в новые scheduled jobs. NOW — реализовать этот bounded atom; WATCH — полнота due/readback и operator burden после фактического использования.

## 13. Что передать исполнителю

«Реализуй RESEARCH_SHELF_V1 по этому PRD+SSD на актуальном canonical SMIAL. Начни с AGENTS и SEM owners, сверь base. Сохрани existing ResearchStore/RFV/evaluators и scientific gates. Сделай один небольшой engineering PR, targeted vertical evidence и semantic propagation. Подготовь и после принятия версии выполни только разрешённый metadata bootstrap/seed capture; текущие deferred experiments этим заданием не запускаются. Routine metadata changes должны обходиться без PR. Остановись на реальной exact merge/authority boundary, не на каждом инженерном шаге. Если исходный scope не включает внешнюю seed publication — сначала подготовь конкретный batch и запроси только эту недостающую boundary. Final handback: outcome, exact code/data commits, tests, captured/unverified seeds, residuals, rollback, одно next action.»

## 14. Evidence и исследовательская база

Repository anchors (прочитаны на pinned ref):
- [AGENTS](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/AGENTS.md).
- [Semantic map](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/docs/FACTORY_SEMANTIC_MAP.md).
- [ADR-006](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/docs/decisions/ADR-006-hypothesis-fast-lane-research-data-plane.md).
- [Native fragments operator](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/docs/operator/RESEARCH_FRAGMENTS_V1.md).
- [Native fragment code](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/src/solana_alpha_lab/factory/research_fragments.py).
- [Forge skill](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/.agents/skills/hypothesis-forge/SKILL.md).
- [Frozen lifecycle boundary](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/docs/contracts/forge_native_lifecycle_closure_v1.md).
- [Archive fingerprint repair](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/docs/tasks/HFIC_ARCHIVE_FINGERPRINT_FORWARD_FIX_V1.md).
- [document_runner source lineage](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/src/solana_alpha_lab/factory/document_runner.py).
- [promotion_handoff](https://github.com/lancerbeta/solana-alpha-lab/blob/ab13b7efa7efaf9762b6d12eca52e2348d1fe759/src/solana_alpha_lab/factory/promotion_handoff.py).
- [Scout metadata publication policy](https://github.com/lancerbeta/marcopolo-scout/blob/d6e50ee1b0ad0dd2cd1063c999f4609b8744fa8f/control/research_lab_policy.yaml).

Primary external scan, checked 24.10.2026:
- [GitHub commit API](https://docs.github.com/en/graphql/reference/commits): expectedHeadOid и атомарная commit/ref publication.
- [GitHub code-search limitations](https://docs.github.com/en/search-github/github-code-search/about-github-code-search): default-branch search; нужен explicit-ref route.
- [GitHub Issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/learning-about-issues/about-issues): полноценный альтернативный backlog, не Git-tree authority.
- [Beads](https://github.com/gastownhall/beads): durable agent memory/startup discovery/atomic claim полезны как принципы; текущий Dolt runtime избыточен для задачи.
- [RD-Agent API](https://rdagent.readthedocs.io/en/stable/api_reference.html): hypothesis/feedback/trace ancestry и явный переход hypothesis→experiment.
- [MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/): version/run lineage отличается от mutable alias.
- [CloudWatch missing-data semantics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/alarms-and-missing-data.html): missing source требует отдельного состояния, не автоматического false.
- [Kubernetes CronJob](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/): scheduler сам по себе не даёт exactly-once; idempotent operation важнее нового timer.

Материалы пользователя: SMIAL Control Kernel V2.2; пять stable product/science/owner/truth/production/gold-case sources; приложенный strategic reframe prompt; screenshot расписания. Stable документы использованы для смысла и границ, не current-state claims.
