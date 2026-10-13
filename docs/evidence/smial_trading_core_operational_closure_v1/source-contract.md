---
document_id: SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1
version: "1.0"
as_of: "2026-10-11"
status: REPO_GROUNDED_DESIGN_NOT_EXECUTED
repository: lancerbeta/solana-alpha-lab
planning_main: ba87f8e339d5cc3aa55322801ae56e3f92369446
predecessor_pr: 396
predecessor_content_head: 8047be7868eb4c672be689faab29cca7e4a28ab3
chat_mode: DESIGN
executor_mode: AUDIT_REPAIR_AND_OPERATIONAL_CLOSURE
proposed_entry: START_WITH_PATCH
proposed_model_effort: SOL_XHIGH
owner_decisions: PROPOSED_D1_D4_ACCEPTED_ONLY_BY_EXPLICIT_START_COMMAND
external_operations_authority: NONE
live_money_authority: NONE
admin_ui: EXCLUDED
---

# SMIAL — завершение операционного PAPER/SHADOW-контура
## Единое задание исполнителю: PRD + SSD + реализационный план + доказательства приёмки

**Рекомендуемый результат:** довести уже собранный торговый контур до состояния, когда для его первой разрешённой PAPER/SHADOW-эксплуатации нужны конкретная допущенная стратегия, действующие настройки/доступ и commissioning, а не дописывание очередного внутреннего перехода.

Не ограничивай работу буквальной поддержкой `V2`, исправлением нескольких прошлых findings или новым отчётом об аудите. Заверши один связный owner outcome: **обычный процесс сам потребляет поступающие episodes, обрабатывает решения и результаты, обслуживает старые позиции при смене стратегии, переживает отказы и даёт правдивый readback**. Исправляй подтверждённые пробелы до выполнения этого outcome.

**Граница обещания:** software-готовность PAPER/SHADOW и проверяемая граница будущего исполнения. Не готовность к реальным деньгам, не доказательство alpha, не live health. Реальный signer, отправка транзакций, chain/wallet reconciliation и их финансовая авторизация не превращаются в «осталось только включить», если соответствующий код/доказательства отсутствуют.

---

## 0. Старт, authority и способ работы

### 0.1 Команда, которую владелец передаёт вместе с этим MD

> **EXECUTE `SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1` по приложенному MD. Принимаю для этого software-атома решения D1–D4 из §2: successor через отдельную scientific identity; один источник новых входов на mode при сохранении обслуживания предшественников; отдельный учёт незавершённых обязательств в общем операционном лимите; продолжение исходных выходов и reconciliation после остановки входов. Реализуй и проверь обычный PAPER/SHADOW-путь, включая необходимые last-mile adapters, безопасное восстановление и cleanup. Рабочие настройки, реальные данные/процессы, provider calls, credentials, deploy, signer, транзакции и деньги этим не разрешены. Не останавливайся между безопасными зависимыми шагами. Merge — только по действующему exact-head gate и отдельной owner phrase.**

Сам MD — предложение, не свидетельство owner approval. Если поступило только «прочитай/оцени», оставайся в DESIGN/REVIEW. Когда владелец явно передал указанную EXECUTE-команду, не проси повторно разрешать уже принятые D1–D4 и routine engineering.

### 0.2 Entry и текущая база

Репозиторий: `lancerbeta/solana-alpha-lab`. Проверенный planning anchor — `main@ba87f8e339d5cc3aa55322801ae56e3f92369446`, merge #396; merged branch head — `8047be7868eb4c672be689faab29cca7e4a28ab3` [G01]. При подготовке post-merge CI ещё выполнялся; никакого PASS ему заранее не приписывается.

Перед product writes: `AGENTS.md` → текущий Delivery Harness → `SEM-OWNER-LIFECYCLE`, при необходимости `SEM-LIVE-COLLECTION`, `SEM-PROVIDER-ROUTES`, `SEM-REMOTE-OPS-RECOVERY`. Затем точные owners из §15. Зафиксируй current base/HEAD, upstream, branch, dirty state, predecessor status, active time gates и пересечение с параллельным CI-fix. Не используй `context --pr` для product diff. Не выбирай работу по «latest task».

Плановый SHA — не требование откатить новый `main`. Routine drift или уже сделанный repair → пересопоставить зависимости и PATCH план. Failed predecessor CI требует объяснения и существующего gate, но не останавливает независимое read-only проектирование. Не прикрывать реальный product regression словом «формальность».

Материализуй один exact task contract из этого задания в штатном bootstrap-порядке. Source MD остаётся единым PRD/SSD; contract содержит binding/write set/gates, а не второй пересказ. Новые названия методов/полей ниже — **семантические примеры**, если явно не сказано, что это существующий API. Конкретную реализацию выбирай по current owners.

### 0.3 Полномочия

Разрешены после EXECUTE: scoped локальные изменения product/docs/tests, небольшой deterministic driver/fixtures, настоящая disposable SQLite, subprocess/fault injection, существующий locked toolchain, минимальные расширения текущих stores/контрактов по задаче, обычные commits/non-force task push/PR/review/CI по harness. Новые публичные официальные docs можно читать; это не provider call.

Не разрешены: рабочий runtime/remote host, чтение защищённого holdout, реальные scientific trials/PROMOTE, рабочая policy APPLY, активация collector/provider/strategy, API/RPC/WSS-запросы, новые credentials/grants, расходы, wallets/signers, `/execute`, `/build`, testnet/devnet транзакции, repository settings, force/history rewrite. Новый package/image/service — только после доказанной необходимости и соответствующего отдельного gate. Наличие старого key/доступа/разрешения из PMF не является новым разрешением.

Изолированный local HTTP fake для тестирования транспорта допустим только если текущая политика явно позволяет loopback; иначе подменяй самый нижний HTTP transport без сетевых sockets. Это не разрешение ослабить egress guard.

Engineering effort ограничен outcome и ресурсной безопасностью, **не числом попыток или repairs**. Не применять «два прохода — и стоп», не reroll-until-green. Каждый повтор объясняется новым evidence/исправлением/заранее названной проверкой воспроизводимости. При повторном разрыве одного seam пересмотри модель владения, а не наращивай suffix-adapters.

### 0.4 Один NOW и один WATCH

**NOW:** закрыть операционную связность PAPER/SHADOW по этой спецификации. **WATCH:** commissioning конкретной реально допущенной стратегии после software acceptance, наличия операционного профиля и отдельного разрешения. Админка и настоящий денежный execution — не скрытые этапы этой campaign.

---

## 1. От чего отталкиваемся: факт, вывод, неизвестность

### 1.1 Проверенные Git-факты

| Факт на planning anchor | Следствие |
|---|---|
| #396 merged. Отчёт сохраняет `REPAIR_PARTIAL_BLOCKED`, S08/S13 не закрыты [G01, G04] | Не начинать с нуля, но и не наследовать полную готовность |
| Native transaction PATCH сохраняет normal admission denial/cancellation через outcome API; ошибки продолжают rollback. Отчёт содержит A–D и origin-integrity repairs [G04, G06] | Это regression baseline, не повод снова проектировать outcome API |
| Основной runbook требует `init → load → activate → episode → attempt → result → exit → attempt → result → readback` [G05] | Сам по себе ручной проход не доказывает unattended-операционку |
| `TradingContinuityRunner.__init__` читает research-data, ищет PROMOTE, пересобирает handoff и проверяет recipe; все CLI-команды используют runner. Есть предел чтения 10 000 records [G06] | Проверить холодные control/recovery paths без ResearchStore и рост исторического store; не объявлять их доступными по warm-instance тесту |
| `runner.exit` отказывает, когда bot не `RUNNING`; operator-close доступен отдельно [G06] | Нужна явная политика manage-existing после прекращения новых входов |
| Handoff привязывает identity к experiment; существующая материализация использует V1. Scientific decision, definition и activation различны [G07, predecessor source] | Не ослаблять `V1` guard ради буквального старого теста |
| Entry-admission, outstanding inventory, settled и drain-clear — разные множества. Старые лимиты не охватывают автоматически EXIT/UNRESOLVED [G08, G09] | Исправить операционный риск отдельной принятой семантикой, не переименовать старый показатель |
| Старый `unattended_shadow` — `COMMISSIONING_ONLY` над закреплённой offline-когортой [G10] | Он не заменяет ordinary continuous driver |
| Execution domain объявляет PAPER/SHADOW, `live_authority=false` [G11] | Нельзя выдать core readiness за готовность к реальным транзакциям |
| PMF quote-only transport существует, но policy привязана к exact one-shot identity, amount, authority и одному запросу [G13] | Переиспользовать полезный transport/parser, не наследовать научный scope и не снимать guards старого caller |

Числа PASS в отчёте — сохранённое evidence исполнителя, не тесты, заново выполненные при подготовке этого документа. Новый executor проверяет их exact bindings и повторяет только затронутые проверки по действующей политике.

### 1.2 Что является проектным выводом, а не уже доказанным багом

У ручного runner есть потенциальные эксплуатационные узкие места: зависимость безопасных команд от полного research context; отсутствие доказанного producer-driven долгого цикла; обслуживание draining/старых epochs; cap bypass при смене identity; отсутствие обычного quote-adapter caller; partial EXIT; холодный restore с отставшим snapshot.

Это **targeted audit hypotheses**. Получи native reproducer/trace и исправь earliest boundary. Если current main уже закрывает конкретную гипотезу, засчитай прямое evidence, не создай лишний слой.

### 1.3 Что мы не знаем из Git

Не установлены текущий host health, доступность ключей/квот, реальный поток episodes, latency/route качество, фактические позиции/средства, доступность конкретной scientific strategy. Это не основания для software-заглушек и не разрешение читать live. В конце отдели `SOFTWARE_GAP` от `EXTERNAL_UNVERIFIED` и `MISSING_OWNER_CONFIGURATION`.

---

## 2. D1–D4: смысловые решения для этого атома

Эти решения становятся authority только с явной стартовой командой §0.1. Они снимают известные развилки заранее. Если текущий canonical owner содержит материально несовместимое более новое решение, останови **зависимую** ветку и предъяви точный конфликт; не выбирай удобную трактовку молча.

### D1. Successor — новая допущенная стратегия, а не искусственная V2

Новая/изменённая гипотеза, entry/exit recipe, population или материально иной execution regime проходит собственный frozen science/evidence path. Естественный downstream объект — `B@V1` от нового `ExperimentSpec/PROMOTE`, рядом с `A@V1` от прежнего. Сам restart неизменной стратегии не создаёт научную версию; существующая activation продолжается либо создаётся отдельно разрешённая новая epoch по её смыслу, но не автоматически при каждом запуске процесса.

Не вводить новый strategy-family registry, автоматический номер Vn, универсальный migration DSL или новые scientific permissions. `A→B` в runtime означает операционную смену источника новых входов, **не** доказательство, что B лучше, и не scientific supersession A.

Same identity+different frozen content остаётся конфликтом. Новый вход B требует собственного проверенного handoff, а не скопированного PROMOTE A. Перезапуск возвращается к durable activation; имя файла/«последняя версия» не выбирает стратегию.

**Исторический audit:** S08/S13 первоначально требовали active same-ID V2. Их source bytes и результаты не переписывать в PASS. Принятое изменение критерия оформить как явное owner-approved supersession этого требования: новое доказательство — положительная continuity `A@V1 → B@V1` с открытой A, плюс отрицательные проверки незаконной same-ID V2. Старый исход остаётся исторически PARTIAL, новый capability принимается по обновлённому explicit contract. Это не снятие denominator после неудачного теста: сохраняются причины, исходный риск и более точный replacement oracle.

### D2. Один источник новых входов на mode; общий учёт незавершённых обязательств

Pet-scale default для **нового ordinary operating profile**: не более одного entry-enabled successor в каждом mode. Несколько предшественников могут оставаться manage-existing/draining. PAPER и SHADOW по-прежнему независимы. Это не ограничение будущего портфеля навсегда, а достаточный сейчас operating envelope.

Новая identity/epoch не освобождает ранее занятый операционный лимит. На switch/first activation нового operating profile проверяется конфликт с уже entry-enabled legacy instances: не игнорировать их и не выключать автоматически без соответствующего explicit control scope. В пределах mode общий capacity check видит старые и новые обязательства. Числа лимитов не выдумывать: перед первым обычным запуском необходим явно заданный owner-authorized operating envelope; отсутствие необходимого общего лимита — `CONFIGURATION_REQUIRED`, не unlimited.

**Семантика capacity:** outstanding obligation включает unattempted reservation, возможный submitted entry, известную открытую/частичную позицию, EXIT_REQUIRED/EXITING и unreconciled inventory. Definitive non-fill освобождает reservation; подтверждённый полный выход освобождает inventory; UNKNOWN не освобождает ничего. Состояние CLOSED само по себе не доказывает, что риск уже reconciled.

Старые `OPEN_RISK_STATES`, `max_open_positions` и исторические policy receipts не переопределять задним числом. Оформи versioned basis/добавочный операционный safety check **у существующего risk owner**, с теми же authoritative positions и одной transaction boundary. Существующие entry-admission лимиты продолжают действовать; новый safety envelope может только дополнительно запретить вход. Не строить второй risk engine или competing inventory store.

Для reservation/unknown-entry используется связанный верхний bound из admission. Для известного остатка — доказуемый residual quantity/cost basis; не считать это current equity или VaR. При неполной identity/величине, от которой зависит лимит, — UNKNOWN и блок нового входа. Денежные лимиты нельзя освобождать простой сменой state.

Неизвестный исход попытки, потеря достоверного inventory/readback или невозможность обслуживать due exits блокирует новые входы соответствующего mode. При доказанно локальном неисправном объекте scope блокировки может быть уже **только если** существующие контракты позволяют исключить влияние на общий лимит; иначе mode-wide. Старые выходы и reconciliation продолжаются. Не добавлять угадываемые daily-loss/SL/VaR/процент капитала.

### D3. Прекращение новых входов не прекращает обслуживание старых позиций

В core явно различены `may_open_new` и `must_manage_existing`. PAUSE, смена successor, RETIRE-entry и нормальный STOP/drain запрещают новые входы, но не отменяют frozen exit/reconciliation уже принятых позиций.

**Нормальный stop:** отменить только ещё не attempted reservations, сохранять known/possible inventory, продолжать исходные scheduled exits и выяснение результатов; полностью остановленный bot допустим только после доказанного отсутствия inventory/unknown attempts. STOP не является обещанием немедленной продажи. Немедленный operator close — отдельное действие с собственной idempotency и без переинтерпретации стратегии.

Frozen exit работает по originating position/epoch/recipe независимо от текущего entry-active successor, списка токенов и active research corpus. Новая стратегия не принимает старую позицию «на баланс» без отдельного контракта. Старый identity guard заменяется ровно там, где он ошибочно смешивал inactive entry и запрет управлять существующим риском; проверки происхождения сохраняются.

Отсутствие research catalog/file после activation не должно лишать status/pause/stop/reconcile. Для автоматического выхода требуется доказанный сохранённый operating context; при его corruption — запрет вычислять выдуманный exit, сохранение позиции и отдельный доказуемый operator/recovery path. Ни одна из этих веток не разрешает угадывать цену или fill.

### D4. Полнота software scope, без подмены commissioning

В scope входят ordinary continuous driver, local read-only source adapter, automatic PAPER result adapter и обычный quote-only SHADOW adapter с выключенным внешним доступом по умолчанию. Их production code тестируется через поддельный нижний transport; не только через приготовленные `SignalDecision`/`Result`.

Для принятого operating profile основные положительные и recovery paths не могут требовать ручного JSON на каждый episode/attempt. Ручные низкоуровневые команды сохраняются как diagnosis/recovery, не primary product path.

**Не входит:** signer/live swap implementation и реальные финансовые операции. По денежному пути исполнитель обязан выдать конкретную capability boundary: существующий owner/реальный adapter/test либо `NOT_IMPLEMENTED`/`NOT_VERIFIED`, но не продавать отсутствие кода как «внешняя проверка». Полная галочка этой задачи относится только к явно названному PAPER/SHADOW scope.

---

## 3. PRD: желаемая эксплуатация и критерий полезности

### 3.1 Кто пользуется

Один оператор и его executor; обычный source collector; допущенная frozen strategy; будущий commissioning operator; agent, пришедший через semantic route без этого чата. Научная кузня — producer definition/evidence, а не runtime orchestrator.

### 3.2 Нормальный owner journey

1. Оператор видит техническую совместимость exact strategy и какие обязательные параметры/источники нужны. Scientific eligibility остаётся отдельной.
2. Явно активирует разрешённый PAPER/SHADOW profile. Само чтение definition/статуса ничего не запускает.
3. Запускает один обычный процесс/существующий host entry point. Тот самостоятельно получает новые/созревшие decision slots, outcomes и exits; не ждёт копирования IDs между CLI-командами.
4. Приходит B: выполняется одна проверяемая операция switch. A больше не принимает новые входы, но завершает свои позиции; B не обходит занятый лимит A.
5. Pause/restart/source outage/quote failure не теряют позиции и не оживляют старые сигналы. После restart процесс сначала восстанавливает обязательства, потом допускает новые входы.
6. Одним status/readback видно: что entry-active, что draining, какой риск/UNKNOWN, насколько свежи source/progress, что именно мешает входам, и что делать.
7. Backup восстанавливается в чистом root. Повторный старт не создаёт новую activation или повторную покупку.

Число команд не самостоятельный KPI. Но необходимость вручную подавать каждый episode, result или exit — FAIL основного journey.

### 3.3 Scope

`accepted handoff → runtime compatibility → explicit activation/profile → source-driven decisions → admission → automatic modeled/quote-only attempt/result → position/exit/reconciliation → control/status/recovery → technical feedback/retire-entry`.

Включены стыки с source publication, retention и semantic navigation, если без них путь ломается. Исходный collector/Forge алгоритм не переписывается; работаем с их contract/API. Включены полный/частичный результат, unknown/no-route, backlog, restart/restore, migration compatibility и unit/evidence-class correctness.

Не включены admin UI, новая alpha, изменение frozen thresholds/populations, research replay на закрытых holdouts, generic expression language, distributed orchestration, production deployment, новый мониторинговый SaaS, Telegram setup, HFT или multi-wallet portfolio.

### 3.4 Что считается окончанием

**`READY_FOR_PAPER_SHADOW_COMMISSIONING`** допустим, когда executable core и ordinary adapters действительно есть, все обязательные scenarios пройдены, contracts согласованы, cold operator journey проверен, остались только конкретные scientific/operational inputs и externally gated checks.

**`PARTIAL_SOFTWARE_GAP`** — остаётся недописанный caller/adapter/state transition либо непроверенная обязательная recovery ветка. Это полезный checkpoint, но не requested completion.

**`BLOCKED_OWNER_DECISION`** — точный новый смысловой конфликт вне D1–D4, а не обычный выбор реализации.

Никакой процент coverage не компенсирует missing critical path. «Поддерживаем только fixture» не сужает согласованный scope. Баги, обнаруженные внутри него, чинятся в этой campaign; новый крупный продукт/внешняя authority boundary не прячется внутрь.

---

## 4. SSD: минимальная архитектура и authoritative owners

### 4.1 Опорная модель

```text
Git: frozen strategy + executable recipe + contracts
ResearchStore: original scientific decisions/evidence
             │ verification at activation/material change
             ▼
Existing PaperPlane DB: activated operating binding, controls,
                        decisions/admissions, attempts/results,
                        positions, work/progress checkpoints
             ▲                         │
Source SQLite/publications ─ readonly ─ ordinary tick/run coordinator
                                       │
                               same execution engine
                                       │
                   PAPER model / SHADOW quote-only adapter
                                       │
                         truthful status + recovery
```

Одна семантика — один owner. Предпочтительно существующий процесс/CLI и одна PaperPlane DB; небольшой отдельный runner-процесс допустим, если он проще безопасной врезки в collector. Не связывай жизнеспособность коллектора с падением торговли. Не добавляй Redis/Kafka/Celery/Temporal, отдельный workflow DB, exchange SDK или Docker cluster без доказанной необходимости.

### 4.2 Operating binding вместо повторного science bootstrap на каждой команде

При explicit activation свяжи маленький воспроизводимый operating context: exact strategy body/hash, exact PROMOTE/manifest/evidence binding, executable recipe/hash, source/schedule compatibility, mode/profile, activation identity, versions нужных контрактов и origin refs. Хранить в существующем authoritative activation/event owner либо его минимальном расширении; не в новом scientific registry.

Это **frozen derivative для исполнения**, не новая научная истина. Ссылка на origin и способ byte/hash проверки обязательны. Нельзя создать binding из текущего файла, когда исходный PROMOTE не найден/непроверяем, или ретроспективно дооснастить старый event выдуманным payload.

После activation readback, controls и приём результата уже начатой попытки не зависят от сканирования всего ResearchStore. Safety commands/result на отсутствующем runtime store не создают новую пустую DB; bootstrap допустим только через explicit initialization/activation path. Entry и автоматический выход используют exact frozen binding, а не «последнюю» strategy в Git. Текущая integrity проверяется по зависимости, необходимой действию; source unavailability не приравнивается к content corruption.

Проверь холодный запуск отдельного процесса после удаления/недоступности research-data и после unrelated роста более 10 000 записей. Наличие прежнего Python-объекта `runner` в памяти не считается проверкой восстановления.

### 4.3 Разделить data roots и evidence class

Текущий offline runner требует `<repo>/local/...` и synthetic marker. Не вырывай этот предохранитель, чтобы получить «production path». Выдели переиспользуемый core, а режим/authority/root protection оставь на boundary. Один resolver определяет authoritative runtime store; не создавать одновременно `paper_plane.sqlite` и `paper_plane_state.sqlite` как две истины.

Source roots read-only; runtime DB writable только в явно разрешённом scope. Основному операторскому пути не нужно копировать весь collector или research corpus под каждый bot. Fixtures могут физически разводить source/runtime roots так же, как предполагается на host. Symlink/junction/hardlink/path traversal checks и невмешательство в чужое сохраняются.

Различай `PAPER/SHADOW`, `SYNTHETIC/OBSERVED`, `network authority` и `live financial authority`. `--mode SHADOW` не превращает fake quote в рынок, `--mode PAPER` не даёт доступ к произвольному root, новый runtime profile не разрешает signer.

### 4.4 Runtime compatibility до неприятного сюрприза

Расширь существующий preflight/handoff compatibility read model: способен ли ordinary execution выполнить exact frozen recipe, source semantics, required inputs, exit и execution regime? Это техническая совместимость, не новый scientific PROMOTE gate.

Покрыть текущую принятую grammar/list operators и unit semantics через shared owners. `LIST_CONTRAST` и `MIXED_LIST_NUMERIC` обязательны. Если код поддерживает иной реально потребляемый recipe — включить его в representative proof. Не реализовывать EMA/DSL «про запас».

Различай frozen **definition** списка и конкретный membership snapshot. Для динамического списка фиксируется смысл/версия definition, а membership нового episode берётся из допустимого ему T0 frame/snapshot с собственными clocks и provenance; не из сегодняшнего latest и не из membership старого episode. Если `membership_snapshot_shas` в исходном contract — буквально frozen content predicate, нельзя объявить его динамическим списком без нового scientific решения. Если это ссылки на исследовательское evidence, они не должны становиться случайным запретом всех будущих snapshots. Разделение проверяется у shared scope owner и фиксируется до activation, без выдуманной ретроактивной доступности.

Research-corpus cohort selection не является автоматически runtime population. Нельзя удалить cohort filter, заменить его будущими episodes и объявить ту же hypothesis. Если frozen contract отделяет evidence sample от runtime universe, использовать это разделение; если не отделяет — typed incompatibility **до activation**, с точным требуемым science/input decision. Неподдерживаемое не помечать ready. Не менять scientific meaning для удобства runner.

---

## 5. Ordinary continuous driver: вместо ручного склеивания

### 5.1 Entry points и обязанности

Сначала проверь существующий owner/entry point. Предпочтительно расширить `scripts/trading_continuity.py` и `TradingContinuityRunner` либо вынести один небольшой coordinator рядом. Концептуальные операции:

- `check`: readonly compatibility/config/authority readiness;
- `activate/switch/control`: explicit idempotent control writes;
- `tick`: одна законченная bounded итерация;
- `run`: повторяет тот же tick, умеет graceful shutdown;
- `status`: readonly machine/human view без scientific bootstrap;
- `backup/restore-check`: существующий native recovery path.

Это не предписание конкретных flags. На выходе нужны реальные `--help`, проверенные команды и один обычный entry point. Product code не импортирует tests, fixture constructors или старый `COMMISSIONING_ONLY` как источник бизнес-логики.

### 5.2 Порядок итерации

Приоритет: **unknown-result recovery → due exits/operator-close → cancellation/drain → новые решения/admission**. Большой entry backlog не должен вытеснять обслуживание существующего риска.

```python
# Псевдокод desired ordering; не готовый API.
context = resolve_existing_runtime_without_recreating_it()
with acquire_existing_single_writer_ownership(context):
    reconcile_pending_attempts(context)       # повтор той же identity
    service_existing_positions(context)       # frozen origin, включая draining
    apply_pending_controls_and_cancellations(context)
    health = inspect_source_progress_and_inventory(context)
    if health.allows_new_entries:
        for work in bounded_due_decision_items(context):
            persist_decision_and_admission_outcome(work)
            dispatch_admitted_attempt_if_still_allowed(work)
    persist_progress_summary(context)
```

Нельзя удерживать write transaction через HTTP/длительную файловую операцию. Решения, idempotency и claim-before-effect проходят текущие atomic boundaries. Single-writer ownership выбирай минимальное по текущему host; обязательны проверка concurrent launch и отсутствие второго sender после restart. Не строить распределённый lease service. При необходимости короткой DB claim использовать ту же DB и fencing, а не «файл жив» как единственное доказательство.

### 5.3 Discovery, очередь и cursor

Driver сам обнаруживает episodes и вычисляет due points через existing `resolve_point`. Не принимать вручную составленный список IDs как единственный обычный источник работы. Publication/outbox visibility остаётся source-owned.

Нужны стабильная identity work item и durable объяснение исхода. Conceptual key:

```text
(mode, activation_epoch_id, strategy_sha256, episode_id,
 recipe_sha256, decision_slot, work_kind)
```

Нельзя использовать mint или один wall-clock timestamp как cursor. Equal timestamps, late-arriving admissions, publication rollover, crash между страницами и вставка элемента «раньше cursor» не должны терять eligible work. Используй source-native monotonic sequence/устойчивую pagination, или bounded re-enumeration + idempotent anti-join; добавочный pending index допустим в существующей DB. Временный cursor не становится единственной истиной о совершённых эффектах.

После admission denial сохраняются source decision и evaluation context. POLICY revision может разрешить новое evaluation в ещё допустимом временном окне по контракту #396. После expiry нельзя переоценить старый ENTER как свежий. Work считается обработанным, когда его outcome durable, не когда его ID выдан из iterator.

No-op tick не должен перечитывать весь historic ResearchStore или записывать сотни одинаковых events. Доказать bounded work на backlog и стабильное поведение при росте истории; не оптимизировать на основании предположений.

### 5.4 Время и freshness

Раздельно хранить source event/request/response/first-visibility, frozen decision cutoff, фактическое computation/attempt time и observation time результата. Исторический `decision_at` может быть cutoff; фактическая отправка не должна его подменять, чтобы пройти max_age.

Просроченный вход — durable `SKIPPED_STALE`/существующий equivalent с origin, не задним числом исполненная сделка. Future point не заполняет missing past point. Поздняя publication сохраняет реальную source first-visibility; различные crash histories не обязаны иметь одинаковое physical-ingestion время.

Используй текущие policy windows. Новые operational latency/heartbeat thresholds должны иметь named consumer и источник: profile/schedule/явный operator setting. Не ставить 15 секунд/30 секунд/24 часа как якобы принятое значение. В proof применяй synthetic values и отмечай их как fixture, не production defaults.

---

## 6. Смена стратегий и управление старым риском

### 6.1 Switch protocol

Preflight B проверяет definition/manifest/recipe/source/mode/config **до изменения A**. Затем короткая атомарная операция фиксирует switch identity, expected current activation, A entry-disabled/manage-existing и B entry-enabled. Runtime policy/общие лимиты не исчезают и не заменяются defaults.

Если B не прошла preflight — A не выключать как побочный эффект. Если race/stale expected-current — отказ без частичного switch. Повтор same key+same body идемпотентен; different body — конфликт. New entries A, ещё не submitted, не могут просочиться после commit переключения. Already attempting A не объявлять отменённым без outcome.

Во время switch разрешена открытая A и active B, но B получает admission только в доступном общем envelope. Старые positions перечисляются по PaperPlane inventory, а не только через entry-active pointer.

### 6.2 Минимальный state contract

| Ситуация | Новый вход | Старая позиция / результат | Что видно оператору |
|---|---|---|---|
| A entry-active, sources/inventory достоверны | По admission | Frozen exit работает | Scope + freshness + limits |
| A paused | Нет | Exit/reconcile продолжаются | PAUSED, возможный inventory |
| A replaced by B | Только B, с общим лимитом | A manage-existing по собственному origin | B active, A draining |
| STOP/drain | Нет; unattempted отменяются | Known/unknown не исчезают, due exits обслуживаются | DRAINING до flat/definitive state |
| Source stale, позиций нет | Нет stale entries | Нет выдуманных outcomes | SOURCE_STALE/необходимое действие |
| Source/reconciliation/exit health потерян с возможной позицией | Новые запрещены | Доступные безопасные recovery/exit продолжаются | ACTION_REQUIRED, не «0 positions» |
| Flat подтверждён, дополнительные costs неизвестны | По risk-policy dependencies | Экономика UNKNOWN сохраняется | Flat != complete net accounting |
| Frozen origin повреждён | Запрет зависимой торговли | Нельзя пересчитать из latest; independent status/operator guard доступны | INTEGRITY_CONFLICT + exact recovery |

Таблица — семантика. Переиспользуй существующие enums/statuses; не вводи enum на каждую комбинацию. `STOPPED` не должен означать существование выполняющегося background exit, а `DRAINING` — гарантированную продажу.

### 6.3 Exit due против цены/маршрута

Поддерживаемый frozen time-exit порождает обязательство в заданное contract время; отсутствие цены/маршрута не стирает это обязательство. Но если target в научном объекте является лишь evaluation label, его нельзя самовольно превратить в execution rule: compatibility должна потребовать явный executable exit binding.

Разделяй `exit obligation due`, `exit decision` и `fill/result`. Невозможность сейчас получить quote не означает CANCELLED/flat. После definitive no-route допускается новая отдельно идентифицированная попытка выхода с реальным новым временем; после UNKNOWN сначала выясняется прежняя. Поздний recovery quote не «лечит» старый scientific target и не переписывает его evidence.

Выходы A используют её frozen rules и позицию, а не новые membership/predicates B. Удаление mint из списка, завершение admission cohort или retirement research candidate не должны удалять exit watch.

---

## 7. Исполнение без денег: полноценные adapters, а не тестовые объекты

### 7.1 Общая boundary

Core потребляет provider-neutral attempt/result. Adapter отвечает за реальные semantics своих внешних bytes и evidence class. PAPER model не доказывает route. SHADOW quote не доказывает fill. Названия старых modeled outcomes `LANDED_SUCCESS` не дают факта landing вне model evidence class.

Attempt сначала durable, затем возможный внешний/model effect. Idempotency включает originating position, side, request content и attempt identity. Повтор команды не даёт новый `send_permitted=true`. Изменить ключ после timeout — не recovery.

Prepared-but-not-known-sent и possibly-sent нужно различать ровно настолько, насколько это доказуемо. Сбой после committed attempt до acknowledgment нельзя автоматически трактовать как «ничего не было». Для offline model исход может быть воспроизводимо вычислен из frozen attempt; для внешнего адаптера нужен его собственный reconciliation contract. Никакого generic exactly-once network обещания.

### 7.2 PAPER

Production PAPER adapter сам получает допустимые входные observations/model inputs, применяет **явную versioned модель** latency/fill/fees/failures и сохраняет result, связанный с attempt. Не подставляет ad hoc $30/20bps из acceptance example. Используются exact execution inputs/bound regime.

Модель не читает future price, чтобы исполнить более ранний entry. При отсутствующих данных сохраняет UNKNOWN/no-route-as-model согласно явной модели, не берёт последний удобный price. Рандомность, если действительно нужна existing model, имеет фиксируемый seed и version; deterministic default дешевле.

### 7.3 SHADOW quote-only

Рекомендуемый транспорт для текущего стыка — existing Jupiter quote-only route, после разрешения current canonical route binding. В Git есть one-shot PMF implementation; это reuse candidate, **не пригодный бездумно бесконечный caller** [G13]. Извлеки/переиспользуй чистый transport/validation там, где это дешевле, сохрани прежние one-shot guards и tests. Не оборачивать старый exact owner phrase общим циклом.

Свежая официальная документация Jupiter на дату планирования описывает `GET /swap/v2/order` без `taker` как quote-only: `transaction` — null; `outAmount` — ожидаемый результат, не fill. Platform fee уже включена в quote [E01]. Не добавлять signer/taker/payer, `/build` или `/execute`. Подробный wire contract фиксируется по current official API и current registry, не по древнему PMF payload.

Нужен **работающий production HTTP adapter с выключенной внешней authority**, проверенный на fake transport, а не abstract Protocol без реализации. Actual external validation остаётся отдельной operation. Если новый registry/schema owner нужен для binding, не переписывать immutable исторические записи и не заявлять observed provider qualification на основании fixture.

Обязательные проверки: exact input/output mint, amount в raw units, decimals/denomination, side, route/request identity, provider/observed times, finite/positive amounts, response limits, HTTP errors, malformed/schema drift, missing fields, timeout, rate-limit, redirect/host guard. Credentials не появляются в URL, logs, receipts или fixtures. Fake secret — заведомо synthetic canary, не реальный key.

`transaction:null` при разрешённом quote-only — не отсутствие маршрута. Unexpected transaction bytes — отказ/санитизация без persistence signing payload. Не считать HTTP 200 доказательством допустимого quote. Не подставлять fee=0, если не хватает fee semantics. Поля request/response сохраняют минимально необходимый provenance/hash и sanitized raw evidence вне публичного Git.

USD notional не равен raw token amount. FX/decimals и funding asset должны приходить из explicit bound execution contract и доступного в момент запроса источника. Нельзя считать 0.01 SOL эквивалентом $30 потому, что так было в PMF. Rounding не увеличивает разрешённый размер. Fee в input/output token и уже net quote нельзя вычитать повторно; неизвестная конверсия оставляет экономику UNKNOWN.

SHADOW запускает buy/sell наблюдения по времени соответствующего decision/exit, а не только мгновенный round trip после entry. Quote results могут питать явно обозначенную modeled shadow-position; они не создают реальные inventory или realized cashflow.

### 7.4 Costs и partial results

Сохрани #396 cumulative additional-cost floor, monotonic result clocks, exact replay и one definitive result на attempt. Additional costs не дублируют fees, уже включённые в price leg/quote. Неизвестное остаётся неизвестным; поздний known total не уменьшает ранее подтверждённый floor.

Закрой текущий partial-exit gap **минимальным учётом остатка**, не стратегией scale-in/out и не order-book emulator. Definitive частичный EXIT завершает данную attempt, уменьшает known remaining quantity, но не объявляет позицию flat; следующая attempt с новой identity работает с остатком. Unknown partial quantity запрещает новый potentially overlapping exit до reconciliation. Overfill/negative/NaN/unsupported units — отказ без перезаписи фактов.

Legacy `PARTIAL` entry остаётся прежним definitive less-than-admitted outcome, если таков current contract. Не переопределять его как streaming fill update задним числом. Для нового partial EXIT при необходимости добавить минимальный versioned result contract у existing owner. Использовать quantity sold/remaining явно; `filled_notional_usd` entry нельзя молча переиспользовать как exit proceeds. Исторические полные exits и hashes неизменны.

Разделять realized частичную leg, оставшийся inventory и полный reconciled result. Дефицит final costs не даёт confirmed NetReturn; он не обязан блокировать физический drain, если quantity/attempt outcome доказаны и risk policy не зависит от неизвестной экономики.

### 7.5 Денежный execution: честная граница

Никаких реальных signed transactions. Официальная Solana RPC документация отдельно предупреждает: успешный ответ `sendTransaction` не означает confirmed execution [E02]. Поэтому transport acknowledgment, timeout и настоящий chain outcome не могут быть сведены к этому offline model.

В финале дай короткий code-backed ledger по live: intent binding; authorization; quote/build; signer isolation; send/retry; finality; wallet/token deltas; fees/rent; inventory reconciliation. Для каждого — существующий exact owner/test либо `NOT_IMPLEMENTED`/`UNVERIFIED`. Не строить эти компоненты в текущем атоме и не писать, что отсутствующий live код осталось лишь «проверить в бою».

---

## 8. Admission, safety envelope и единый transaction смысл

### 8.1 Не сломать исправление #396

Нормальный business outcome (`NO_ENTER`, `UNKNOWN`, `DENIED`, `CANCELLED`) не является исключением транзакционной целостности. Source packet, evaluation/refusal и предусмотренная отмена reservation должны сохраняться согласованно. Genuine exception/identity conflict/native SQLite failure продолжают откатывать незавершённое действие. Broad catch-and-commit запрещён.

Atomic boundary включает current control/profile revision, inventory snapshot, admission decision и frozen reservation. Entry source не считается обработанным до durable outcome. Attempt boundary повторно проверяет stop/switch/stale и подтверждает ту же frozen reservation. Не пересчитывать старый admitted amount после policy change.

### 8.2 Общий envelope на примерах

Fixture, не production limit: mode cap `$30`; A уже занимает `$30`. Switch на B не освобождает лимит. B просит `$30` → DENIED с сохранённым reason и origin, даже если у B ноль собственных позиций.

A получила definitive частичный exit 40% → доказанный остаток cost basis `$18`. B всё ещё просит `$30`; cap headroom `$12` не означает auto-shrink B до `$12`. До полного освобождения/явного изменения принятого envelope её admission остаётся запрещённым.

Если A exit outcome UNKNOWN, capacity не уменьшается на предполагаемую проданную долю. Если A entry завершился definitive non-fill, reservation освобождается; если fee неизвестна, её экономический UNKNOWN виден отдельно. Когда quantity/attempt risk уже доказанно flat, неизвестная дополнительная стоимость не превращается в fictitious inventory, но не разрешает полную net-прибыль.

Все эти значения независимо вычисляются в тесте; лимит и amount задаются synthetic owner policy. Existing policy chain/revision hashes сохраняются. Никаких рабочих limits в Git task receipt.

### 8.3 Veto и recovery не должны образовать дедлок

Safety gate блокирует **новые entries**, но не чтение state, pause, выяснение результата, исправление source access, восстановление exact binding или уже разрешённый exit. При global policy invalid нельзя делать новые ставки, но нельзя лишать систему способа убрать существующий риск.

Нормализация FAILED/UNKNOWN/NO_ROUTE должна отличать definitive non-fill от unknown external outcome. Инвентарь нельзя обнулить по timeout, пустому HTTP response, отсутствию записи в recent-cache или исчерпанию технического retry budget.

---

## 9. Readback, monitor и обратная связь

### 9.1 Одна operator surface без ремонта админки

Развивай existing CLI/read models. Status имеет JSON для machine и компактное русское представление для человека. Оператор получает:

- exact runtime source, mode, activation/profile revisions; entry-active и manage-existing instances;
- known/possible inventory, reservations, pending attempts, due/failed exits, причины admission refusal;
- source availability/freshness, last completed work, queue/backlog lag, earliest overdue item;
- отдельно process alive, input fresh, progress moving, integrity verified, exit/reconciliation healthy;
- scoped trade model PnL, additional costs/UNKNOWN и remaining inventory; никаких mixed-mode cashflow headlines;
- actionable reason, безопасное действие и boundary, если нужен owner.

GET/status не создаёт/мигрирует DB, не checkpoint-ит её, не регистрирует activation, не обновляет science, не читает credentials и не делает сеть. Native WAL coordination в ранее принятом scope не считать business write. Missing/corrupt/read-denied state не отображать как нули.

CLI `status` и safety controls не требуют файл **текущей entry strategy** для обслуживания всех старых позиций. Если отдельный объект невозможно интерпретировать — показывается его raw identity и UNKNOWN reason, не исчезает вся область.

### 9.2 Мониторинг по механизму отказа

Используй существующий heartbeat/change-feed/operator-attention механизм, если он подходит. Не добавлять внешнего notifier. Обнаружение зависания проверяется отдельным наблюдателем/командой, а не только самим умершим процессом.

Каждый alert: scope, stable incident key, reason, age/freshness basis, affected work/positions, next safe action. Безопасный no-signal — не incident. Alive-with-no-progress при ожидаемой работе — incident. Постоянная одинаковая ошибка не создаёт тысячи events и owner notifications; сохраняются первый факт, состояние/счётчик и изменение существенных обстоятельств.

Recovery не стирает incident/evidence. Технический auto-resume допустим после доказанного устранения технической причины и current authority; explicit owner PAUSE/STOP сам по себе не снимается улучшением feed.

### 9.3 Feedback не подменяет science

Execution readout связывает observations/attempts/results с exact strategy/epoch/decision и даёт downstream review evidence. Технический health monitor может закрыть новые входы. Он не переписывает hypothesis, не выдаёт PROMOTE, не переносит paper profit в OOS и не tune-ит frozen rule.

Если experiment уже имеет собственные monitoring/degrade thresholds, проверять их exact semantics. Отсутствующие scientific thresholds не выдумывать ради завершённой таблицы; показывать `NOT_CONFIGURED` отдельно от software health. Retirement entry не стирает отрицательные/неполные результаты и незакрытые позиции.

---

## 10. Recovery, retention, migration и безопасный rollback

### 10.1 Cold restart — основной, не исключительный путь

После старта:

1. Найти exact runtime store и прочитать version/integrity/control state без bootstrapping неизвестного источника.
2. Восстановить все manage-existing activations и pending obligations из durable owners, а не только current strategy config.
3. Сопоставить accepted attempts/results, устранить повторяемые after-commit projections/drain gaps; не отправлять повторно неизвестное.
4. Проверить source/progress/profile совместимость, затем допустить новые entries, если сохранилось разрешение.

Обычный process restart не меняет activation_epoch и не сбрасывает pause. Новая epoch — explicit operation с её scope. Старый backup/cursor не даёт повторного входа по старым сигналам.

### 10.2 Backup/restore

Переиспользуй native SQLite backup и текущий mutable backup owner. Main `.sqlite` без WAL не является достаточным снимком живого state. Нужен согласованный набор: runtime DB, frozen operating bindings, минимальные зависимости для незавершённых решений/выходов, необходимый source cursor/watermark и версии кода/схем.

Не копировать многогигабайтный research corpus под каждую backup задачи. Не требовать атомарного snapshot двух независимых БД, которого фактически нет: задай согласованный cut/manifest или короткое quiesce новых entries и доказуемые dependency pins. Выходы/reconciliation не блокировать на длительный архив.

Restore в **новом isolated root/process** проверяет integrity, exact mode/identity/policy, events/positions, pending result и исключение двойных effects. Подними independent fake external ledger, который не откатывается вместе с runtime backup: последующий result должен быть reconciled, а не отправлен второй раз. До reconciliation restored state не включает новые entries автоматически.

Старые NULL provenance/legacy rows не «ремонтируются» по latest files. Reader должен честно показывать gap, команды — разрешать только доказуемо безопасные действия. Migration additive/versioned с explicit rollback compatibility; если старый бинарник больше не может безопасно открыть store, назови это до delivery и подготовь forward recovery. `git revert` не является rollback данных.

### 10.3 Retention

Рабочая retention и campaign cleanup различны. До удаления исходных publication/local membership/recipe dependencies проверь consumers открытых/неизвестных позиций и pending work. Можно удерживать минимальный immutable dependency closure либо materialized verified operating evidence, не весь источник навсегда.

Если нужный prefix действительно потерян, нельзя восстанавливать его текущими данными. Новые entries отказываются с сохранением gap; старое обязательство обслуживается тем безопасным путём, который подтверждён remaining origin. Полное отсутствие backing evidence не превращается в flat.

Прогнозировать storage по фактическому producer cadence и measured bytes/event, учитывать backup/staging. Существующие repository storage caps не менять. Synthetic длинный прогон не требует реального ожидания недель или наращивания многогигабайтных fixtures.

### 10.4 Rollback

Code/docs rollback — обычный обратимый change по harness. Accepted science/runtime history сохраняется. Новый code version не переписывает originating semantics старых позиций. При incompatibility: остановка новых входов, обслуживание/экспорт/восстановление через совместимый owner, затем дальнейший patch. Не удалять DB, чтобы «вернуть зелёное состояние».

---

## 11. Главный сквозной proof и независимые оракулы

### 11.1 Proof не должен сам играть роль coordinator

Используй existing `EpisodeScenario`, `FactoryApplication`, ResearchStore, materialization, real source/store и validators. Synthetic science evidence/clock — только в disposable root, с собственным Git commit exact spec bytes, как исправлено в #396. Parent checkout HEAD не должен незаметно становиться producer identity fixture.

Test harness подаёт vendor-shaped bytes, продвигает controlled clock и вносит fault. **Он не вызывает вручную `episode → attempt → result → exit` вместо ordinary run loop** и не вставляет готовый `SignalDecision` в главный proof. Прямые engine tests остаются дополнительными.

Минимальный independent observer — новый readonly connection/process и, где проверяется external effect, отдельный маленький fake transport ledger. Test assertions не берут expected identity sets/денежные суммы из той же production-функции, которую проверяют.

### 11.2 Основной owner journey: A → B при открытой A

Synthetic значения, не торговая рекомендация:

- A — `ListA TRUE at T0` + положительный delta holders E300→E1800; явный frozen time exit.
- B — собственный experiment/PROMOTE/strategy с **другим** predicate, например отрицательный delta. Это помогает заметить, что runner продолжает применять A после switch.
- На A: один valid ENTER, один NO_ENTER, один UNKNOWN, один valid ENTER, которому отказывает общий лимит. EXPECTED sets задаются заранее.
- Открыть A model-position; провести explicit switch на B до выхода A. A перестаёт получать новые entries; B видит занятый лимит A.
- Удалить mint A из текущего list feed; сделать ResearchStore A недоступным; остановить и заново запустить процесс. A сохраняет origin, quantity, exit deadline и обслуживание; B не наследует predicates A.
- На выходе A: definitive no-route → UNKNOWN observation → definitive частичный выход → остаток → полный выход. Контракты могут требовать отдельные attempts между definitive outcomes; UNKNOWN выясняется на той же identity.
- После освобождения лимита новая своевременная B opportunity допускается; прежний просроченный B сигнал не оживает.
- Pause B между admission и attempt, restart, resume по explicit command; unattempted cancellation и old pause не теряются.
- Drain, backup/restore в fresh root, повтор callback и независимая сверка конечных states/effects.

Не все отказы обязаны искусственно помещаться в один attempt или одну строку timeline. Разбей primary journey на несколько контролируемых segments, сохрани один scenario manifest и causal identities. Это не разрешение обходить driver.

### 11.3 Временной оракул

Для schedule, использованного в исходной постановке: T0 `12:01:10Z`; E300 assigned `12:10`, deadline `12:15`; E1800 assigned `12:35`, deadline `12:40`; E3600 assigned `13:05`, deadline `13:10`.

Это literal fixture oracle **при том же schedule binding**. На current schedule сначала независимым расчётом сверить значения. Не переносить старые числа, если выбран иной schedule; не менять production `resolve_point`, чтобы совпал пример. Existing default-test exit E14400 не превращать молча в E3600: новый fixture явно задаёт поддерживаемый target.

Проверки: deadline−ε, deadline, deadline+allowed latency и stale; поздняя physical visibility; equal timestamp с разными IDs; источник после replay/publication; forward/backward clock jump. As-of обработки берётся от clock ordinary runner, а не устанавливается тестом в прошлое в обход expiry.

### 11.4 Денежные оракулы

**Полный round trip из #396:** notional `$30`, entry price `0.000003`, quantity `10 000 000`; fee `20 bps` на leg. Exit price `0.0000033`: gross proceeds `$33`, entry fee `$0.06`, exit fee `$0.07` при HALF_UP, gross PnL `$3`, trade net `$2.87`. Additional known cost `$0.02` → modeled net `$2.85`. Это модель, не весь cashflow.

**Частичный выход:** те же 10 000 000 units и entry fee `$0.06`. Продано 4 000 000 по `0.0000033`: proceeds `$13.20`, fee `$0.03`, остаток 6 000 000. Затем 6 000 000 по `0.000003`: proceeds `$18.00`, fee `$0.04`. Итог proceeds `$31.20`, gross PnL `$1.20`, суммарные leg fees `$0.13`, trade net `$1.07`; additional cost `$0.01` → `$1.06`. Ни partial result, ни replay не должны обнулить 6 000 000 до второй продажи. При UNKNOWN цены/количества промежуточный итог остаётся incomplete.

Распределение cost basis/entry fees между partial legs должно сходиться к итоговым raw totals без «потерянного цента». Оракул aggregate считается отдельно; per-leg rounding и residual adjustment явно принадлежат accounting contract. Quote-adapter economics проверяются отдельным fixture, где output уже содержит fee: второй раз вычитать её нельзя.

### 11.5 Оракул полноты множеств

Сверяй не только counts:

```text
source identities
  → source decisions {ENTER, NO_ENTER, UNKNOWN/BLOCKED}
  → admission evaluations {ADMITTED, DENIED, CANCELLED, STALE/...}
  → stable attempt identities and their side/content
  → accepted result identities linked to exact attempts
  → quantity/terminal/incomplete obligations
```

Один source ENTER может иметь несколько **различимых** policy evaluations, но не несколько незаметно задвоенных positions. Все допущенные отправки имеют source/authority/admission; каждый отказ/пропуск объясним. Проверяй sets, foreign-key relationships и уникальность content binding: missing+duplicate не компенсируют друг друга по count.

### 11.6 Оракул состояния после реального process loss

Не ограничиваться `raise RuntimeError` внутри monkeypatch. Хотя бы ключевые commit/send/result окна проверить прекращением настоящего disposable subprocess и restart. Observer читает committed SQLite, fake external ledger — независимо. Не обещать power-loss/disk-hardware tolerance, если проверен только process kill.

Для source/decision/origin corruption — отдельно изменить body при прежнем hash column, clock при прежних выбранных IDs, provenance без accepted binding. Читать полный accepted fingerprint, а не несколько полей. Это защита от обнаруживаемой corruption/drift, не криптографическая защита от атакующего, который контролирует всю DB и все её trust anchors.

---

## 12. Матрица обязательных проверок

Все строки обязательны для соответствующего заявленного operating profile. Existing exact evidence можно переиспользовать по harness и неизменной dependency closure; не выдавать исторический PASS за проверку изменённой ветки. One test may prove several rows, но каждая строка имеет явный evidence locator и scope.

| ID | Проверяемый риск | Достаточное observable evidence |
|---|---|---|
| C01 | Ложная activation / неполный handoff | Valid neighbor активируется явно; nomination/legacy/identity/recipe/regime mismatch отказывают без activation |
| C02 | Обычного цикла нет | Real run process сам проходит source→decision→attempt/result→exit→readback без пошаговых test/owner вызовов |
| C03 | Ошибка list/recipe/PIT | Mixed и list-only проходят shared owners; UNKNOWN/late/missing decision PRICE не превращаются в ENTER; будущий point не меняет историю |
| C04 | Потеря work при cursor/backlog | Equal timestamps, late insert, pagination/restart/publication сохраняют exact expected source/outcome sets; stale не исполняется задним числом |
| C05 | Отказ теряет историю / false commit | Normal DENIED/cancellation durable; genuine native/typed/unexpected fault rollback; сохраняются #396 A–D |
| C06 | Repeated start/signal/attempt/result | Stable identities, одно допустимое действие, exact replay; conflict не перезаписывает content; новая process invocation не создаёт epoch |
| C07 | Неверная смена strategy | Positive A→B с собственной science binding, A open; invalid B не выключает A; concurrent/stale switch атомарно отказывает |
| C08 | Cap bypass новой identity / exit-state | A outstanding продолжает потреблять общий mode envelope; B не auto-shrink; UNKNOWN не освобождает headroom; PAPER/SHADOW независимы |
| C09 | Pause/stop мешает безопасному выходу | No new attempt после control commit, unattempted CANCELLED; due originating exits/UNKNOWN reconciliation продолжаются в drain |
| C10 | Latest files нужны для старого риска | Cold status/control/result/old exit после source research unavailable и unrelated history growth; integrity conflict остаётся typed |
| C11 | Неправильные result/partial semantics | Definitive failure, unknown→definitive, partial entry/exit, overfill и conflicts; quantity conservation и exact remaining obligation |
| C12 | No-route/timeout превращается в flat | Старый inventory/exit obligation сохраняется; unknown не resend; definitive failed exit retry — новая identity |
| C13 | Source/entry/exit provenance corruption | Body-only/clock/hash-column corruption обнаруживается перед потреблением; accepted binding/rollback проверены независимым readback |
| C14 | Модель/quote/actual fill смешаны | Настоящий adapter+fake HTTP bytes; evidence classes, raw units, fee-in-quote, quote-only null transaction; чужой mint/amount/schema отказ |
| C15 | Двойной sender / starvation | Concurrent process launch/controls и реальные SQLite connections; нет двойной отправки, due exits обслуживаются при entry backlog |
| C16 | Умерший/зависший процесс выглядит healthy | Отдельный status/observer обнаруживает stale progress; no-signal не ложная авария; explicit pause не auto-resume |
| C17 | Snapshot/readonly/config drift | WAL-aware fresh readonly snapshot, missing/corrupt/locked state typed; no GET writes; authoritative locator один |
| C18 | Restore теряет или повторяет обязательства | Native backup, fresh root/process; independent fake external state не откатывается; reconciliation до новых entries |
| C19 | Retention/legacy/deploy rollback | Нужные origin dependencies переживают cleanup/смену current; legacy не fabrication; declared migration/rollback реально проверены |
| C20 | Неверная экономика/деноминатор | Literal $2.87/$2.85 и partial $1.07/$1.06; costs UNKNOWN/floor; exact sets и no mixed-money headline |
| C21 | Через две недели всё тормозит/растёт | Representative virtual-time stream, несколько объёмов history, measured tick/backlog/RSS/disk slope, preserved storage policy; не sleep две недели |
| C22 | Operator не может воспользоваться | Cold operator/agent из semantic root проходит check/start/status/control/recovery по runbook без внутреннего Python/ручных JSON на каждый token |
| C23 | Sandbox/authority/cleanup escape | LIVE/provider/signing disabled; actual path/egress/secret canaries; owned roots удалены, non-target fingerprints unchanged |
| C24 | Замаскированы остатки и старая приёмка | D1 decision + S08/S13 historical mapping честны; delivery ledger отличает software gaps/config/external checks/live non-scope |

Не заменять C07 отрицательным `V2 rejected`, C02 — ручным CLI-tour, C10 — warm object, C18 — copying одного sqlite-файла, C21 — одним пустым tick, C22 — чтением runbook его автором. Любая такая подмена — evidence gap, не PASS.

---

## 13. Реализационный маршрут внутри одной campaign

Это зависимые вертикальные срезы одного outcome, не автоматически шесть PR или шесть owner approvals. Default — одна task branch и один coherent delivery PR с обозримыми commits. Если фактический blast radius требует отдельного delivery boundary, сохраняй тот же outcome и объясни реальную причину; не оставляй «подготовили продолжение» вместо основного результата.

### Slice A — Reconcile baseline и operating contract

**Вход:** current main, #396 acceptance/evidence, D1–D4 и existing owners. **Выход:** exact task binding/write set, agreed semantics у canonical owners, owner-path gap map и минимальный воспроизводимый отказ primary run journey.

Проверь existing frozen proof/transaction/origin/dispatch consumers в нужном scope. Не повторяй весь большой audit по инерции. Зафиксируй work items как `already_proven / native_defect / missing_capability / owner_decision / external_check`, не одним «P1 backlog».

Первый falsifier: cold process со своей accepted strategy должен автономно получить source episode и пройти к result. Если отсутствует ordinary coordinator/adapter, это точный missing link, а не повод построить generic platform.

### Slice B — Durable runtime context и управление без science bootstrap

**Вход:** exact verified activation. **Выход:** frozen operating binding, один store resolver, independent status/control/result/origin recovery.

Сначала C10/C13/C17 counterexamples. Исправь lifecycle-dependent loading и consumer checks, сохрани #396 fingerprints/transaction outcomes. Покажи cold recovery с недоступным ResearchStore и неизменным origin. Минимальная schema evolution входит сюда вместе с compatibility/backup.

### Slice C — Ordinary driver и automatic adapters

**Вход:** runtime context, source owner и accepted profile. **Выход:** реальный `tick/run`, durable work progress, automatic PAPER и quote-only SHADOW code paths.

Добавь source enumeration/deadlines, reserve→attempt→result scheduling и recovery priorities. Reuse PMF только в подходящем transport/parser seam. Проверь wire-shaped positive/negative responses и egress. Primary C02/C03/C04/C14/C15 evidence идёт от настоящего entry point.

### Slice D — Switch, shared safety envelope, exits и partial accounting

**Вход:** same driver/state owner. **Выход:** положительная A→B continuity, общие обязательства, автоматические exits у draining A, partial remainder и truthful economics.

Технический порядок выбирай по earliest failure. Не делай два risk inventories. Новая семантика version-bound; old APIs/receipts не меняют смысл. C07–C12/C20 proof должен проходить через обычный caller. Если прежний unit oracle держался за устаревшую семантику, менять его только с прямой ссылкой на D1–D4, сохранив legacy contract tests.

### Slice E — Operation under faults

**Вход:** ordinary long-running path. **Выход:** actual subprocess restart, no-double-effect restore, freshness/backlog health, safe retention, cold operator runbook.

Здесь не надо «построить мониторинг». Нужны несколько проверяемых показателей и доступный existing status/attention path. Гоняй виртуальное время и увеличиваемую историю; отдельно измерь real process behavior. Чини подтверждённый bottleneck, а не проектируй кластер.

### Slice F — Whole-outcome proof, независимый review и cleanup

**Вход:** finished candidate content. **Выход:** exact evidence C01–C24, accepted operating envelope, честный residual ledger, cleaned campaign, required reviews/bindings/CI.

Используй независимые CODE, GOAL/DOD, ARCHITECTURE и OWNER-UX reviews по current harness. Критикам дай exact contract/diff/source refs, но не объясняй заранее, почему всё должно быть PASS. Architecture critic обязан атаковать shared premise, а не только Python. Model diversity не утверждать без доказательства.

После финальных product правок обновить evidence лишь в invalidated scope; exact-head gates соблюдать. Failed check не обходить переназванием scenario или записью «формальность».

### Checkpoint при реальном разрыве контекста

Сохрани: objective/scope/mode; current branch/base/head/dirty files; approved D1–D4 и новые unresolved forks; завершённые slices/evidence; exact next command/test; owned resources; запреты и причины оставшихся blockers. Не оставляй важный контекст только в беседе. Не требовать owner OK для безопасного продолжения уже разрешённого scope.

---

## 14. DoD, приёмка и residual ledger

### 14.1 Обязательные условия

**Поведение:** ordinary process работает из source-shaped inputs; модели/quotes формируются adapters; A→B/old exits/risk/restart/restore проходят; нет ручного orchestration на каждый token. Отказы и unknown сохраняют объяснимое состояние.

**Смысл:** D1–D4 канонизированы в соответствующих existing owners; frozen science не переписана; population/units/clocks/evidence classes/limits не дрейфуют между consumers; future agent не принимает older partial audit за full acceptance.

**Доказательства:** C01–C24 имеют exact scope, direct oracle и executed result либо явный некомпенсируемый blocker. Critical applicable gaps = 0 для READY. Вновь найденные material bugs имеют native before/after либо честно обозначенное missing-before/new-capability evidence. Review agreement само по себе не доказательство.

**Эксплуатация:** cold operator запускает/останавливает/диагностирует/восстанавливает по runbook; source unavailable не отрезает все controls; flat/UNKNOWN/progress различимы; future commissioning не требует дописывать внутренний caller.

**Ресурсы:** campaign cleanup проверен, compact regeneration работает, тяжёлые disposable ресурсы удалены. Продуктовый код и необходимые regressions сохранены.

**Delivery:** generated propagation, exact required reviewers, bindings, CI/readiness/merge/post-merge — по harness. Engineering acceptance != scientific eligibility, runtime health или owner cashflow.

### 14.2 Что допустимо оставить commissioning

| Остаток | Допустим после software READY? | Условие |
|---|---|---|
| Конкретная scientific strategy ещё не прошла свои gates | Да | Software проверен synthetic eligible neighbor; реальное promotion не сфабриковано |
| Actual profile values, runtime roots, provider credentials/quota | Да | Код/контракт/config validation готовы; требуется explicit owner operation, а не новая разработка |
| Read-only source access на целевом host, реальные feed/quote delays и route availability | Да | Тот же production adapter проверен offline; подготовлен exact preflight/commissioning recipe |
| Нет ordinary scheduler/caller, quote adapter — stub, exit требует ручной обработки каждой строки | Нет | Это SOFTWARE_GAP |
| Switch/source-loss/partial/restore не проверен | Нет для заявленного core scope | Это EVIDENCE_GAP или product defect |
| Literal same-ID V2 не реализована | Да по принятому D1 | Историческая S08/S13 не переписана; positive successor и guard доказаны |
| Неподдерживаемая новая гипотеза/DSL/другая сеть | Да вне envelope | Совместимость сообщает это до activation; нельзя называть universal strategy support |
| Signer/send/chain-wallet reconciliation отсутствует или не проверен | Только вне этой галочки | Явно LIVE_NOT_READY/NOT_ASSESSED, не «осталась лишь боевая проверка» |

### 14.3 Какие файлы нужны на выходе

Переиспользовать existing harness locations/formats. Минимум: изменённый product code/contract/read model; focused regressions/fixture generator; exact task binding; компактный closure report с C01–C24 и S08/S13 mapping; machine evidence/required reviews; updated operator runbook; cleanup receipt. Не создавать новый documentation estate.

Каждый material conclusion: source/ref, commit/input fingerprint, method, actual result, scope/limitations. Logs объясняют; persisted assertions/readback доказывают. В final coverage считать accepted source/result **IDs**, не только counts.

### 14.4 Формат final handback исполнителя

```text
VERDICT: READY_FOR_PAPER_SHADOW_COMMISSIONING | PARTIAL_SOFTWARE_GAP | BLOCKED_OWNER_DECISION
EXACT_BASE / CONTENT_HEAD / PR / CI_AND_GATE_STATE
OWNER_OUTCOME: что теперь можно сделать обычным путём
D1_D4: canonical decision references
PRIMARY_JOURNEY: команда, exact inputs, actual persisted result
CRITICAL_COVERAGE: C01–C24; gaps отдельно, без усреднения
OLD_AUDIT: S08/S13 original → explicit replacement decision → new evidence
REPAIRS: подтверждённые причины и их before/after
OPERATING_ENVELOPE: какие recipe/source/mode/result поддержаны
RESIDUALS: SOFTWARE_GAP / EVIDENCE_GAP / CONFIG_REQUIRED / EXTERNAL_UNVERIFIED / OUT_OF_SCOPE
LIVE_BOUNDARY: фактический code-backed ledger, без финансовой authority
CLEANUP: owned bytes/resources before/after, preserved non-targets
ROLLBACK_AND_RESUME: exact safe path
NEXT_OWNER_ACTION: только реальный gate
```

Не заявлять DONE при частичной цели. Если software действительно завершён, не заканчивать новым списком «ещё хорошо бы» внутри той же обязательной цепочки. Optional improvements — максимум WATCH с конкретным trigger.

---

## 15. Карта владельцев кода и источников для исполнителя

Все G-источники ниже проверены read-only на `ba87f8e339d5cc3aa55322801ae56e3f92369446`, если прямо не отмечено иное. Проверены указанные файлы/выдержки, не весь репозиторий и не рабочий host. Paths соседних owners разрешай через imports/Catalog, не через поиск «последнего» task.

| Ref | Existing owner / source | Как использовать |
|---|---|---|
| G01 | PR #396; branch main; merge `ba87f8e339d5cc3aa55322801ae56e3f92369446`, content `8047be7868eb4c672be689faab29cca7e4a28ab3` | Predecessor identity; более поздний CI/main перечитать |
| G02 | `AGENTS.md` | Front door, gates, context, roles, authority |
| G03 | `docs/FACTORY_SEMANTIC_MAP.md` | SEM-OWNER-LIFECYCLE и смежные routes; reference-only |
| G04 | `docs/reports/smial_trading_continuity_v1/REPORT.md` | Baseline/53-case candidate/A–D/origin/dispatch history; source denominator и limitations |
| G05 | `docs/operator/TRADING_CONTINUITY_OFFLINE_V1.md` | Текущий ручной operator path и recreate/cleanup |
| G06 | `src/solana_alpha_lab/factory/trading_runner.py` | Activation/root/provenance/normal outcome/origin/result/exit; прочитаны основной constructor и callers |
| G07 | `docs/contracts/science_to_strategy_handoff_v1.md` | Scientific manifest, definition/activation distinction и execution inputs |
| G08 | `docs/contracts/trading_runtime_policy_v1.md` | Runtime envelope owner, atomic admission, revision/legacy scopes |
| G09 | `docs/contracts/risk_and_economics_v1.md` | Entry risk vs inventory, fee/mark/path/economic scope |
| G10 | `src/solana_alpha_lab/factory/unattended_shadow.py` | Исторический pinned commissioning; не ordinary driver |
| G11 | `configs/execution_domain_v1.json` | Existing import boundaries и exact execution test inventory |
| G12 | `delivery-harness/policies/solana-alpha-lab.md` | Mission/verification economy/storage/remote/provider boundaries |
| G13 | `src/solana_alpha_lab/pmf_quote_slice_one_shot.py`; `docs/tasks/PMF-QUOTE-SLICE-ONE-SHOT-V1.md` | Candidate reuse только полезного transport; старую one-shot authority не переносить |
| G14 | `control/active_time_gates.json` | Проверить текущие applicable due gates; historical TASK21 не становится новым objective |

**Точные existing implementation owners, известные из текущих imports/контрактов и predecessor inventory, но не все заново прочитаны целиком при планировании:**

- `src/solana_alpha_lab/factory/episode_decision.py`, `hfic_research_scope.py`, `hfic_temporal_discovery.py`, `observation_schedule_store.py`, `opportunity_episode_release.py` — recipe/source/list/prefix/visibility;
- `src/solana_alpha_lab/factory/promotion_handoff.py`, `strategy_runtime.py` — materialization, version/decision validation;
- `src/solana_alpha_lab/factory/paper_plane.py`, `paper_shadow_commands.py`, `paper_shadow_operations.py`, `trading_runtime_policy.py`, `risk_economics.py`, `trading_operations.py` — execution/control/risk/accounting/readback;
- `scripts/trading_continuity.py`, `scripts/prove_trading_continuity.py` — ordinary CLI и existing offline proof;
- `tests/test_trading_continuity_v1.py`, `tests/test_paper_shadow_execution_integrity_vertical_v1.py`, `tests/test_trading_runtime_admission_concurrency_v1.py`, `tests/test_trading_runtime_policy_backup_restore_v1.py` — direct regressions;
- `docs/contracts/episode_decision_continuity_v1.md`, `docs/contracts/owner_lifecycle_projection_spine_v1.md`, Catalog assets/generated map — затронутая durable semantics/navigation.

**Предлагаемые, ещё не существующие артефакты:** exact task `docs/tasks/SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1.md`; при необходимости один closure report/evidence directory по current harness и один bounded module для coordinator/quote adapter. Не создавать их дублями существующего owner.

### Freshness и точные ссылки

Git base permalink prefix:
`https://github.com/lancerbeta/solana-alpha-lab/blob/ba87f8e339d5cc3aa55322801ae56e3f92369446/`

- PR: https://github.com/lancerbeta/solana-alpha-lab/pull/396
- G04: https://github.com/lancerbeta/solana-alpha-lab/blob/ba87f8e339d5cc3aa55322801ae56e3f92369446/docs/reports/smial_trading_continuity_v1/REPORT.md
- G06: https://github.com/lancerbeta/solana-alpha-lab/blob/ba87f8e339d5cc3aa55322801ae56e3f92369446/src/solana_alpha_lab/factory/trading_runner.py
- E01, официальный Jupiter, проверено 11.10.2026: https://developers.jup.ag/docs/swap/order-and-execute — quote-only/no-taker и граница quote/execute/fee interpretation. Реальный endpoint не вызывался.
- E02, официальная Solana RPC, проверено 11.10.2026: https://solana.com/docs/rpc/http/sendtransaction — acknowledgment не равен processing/confirmation. Реальный RPC не вызывался.

Current provider semantic map указывает `CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-011`, а прочитанная prose domain policy ещё содержит pin `...-010`. Это **обнаруженный navigation/pin conflict**, не право выбрать удобный provider grant. До изменения provider binding разреши exact authority у current canonical binding по harness; если конфликт затрагивает delivery, исправь конкретный stale consumer в разрешённом scope либо предъяви authority blocker. После однозначного machine resolution current binding обычный stale prose reference — navigation repair, не новая product/owner развилка. Если authoritative owners действительно расходятся, gate сохраняется. Immutable registry predecessor не менять. Никаких новых provider qualification claims из offline test.

---

## 16. Cleanup — самостоятельный финальный шаг

### 16.1 До выделения ресурсов

Сохраняй ownership: campaign ID, exact root/marker/realpath, existed-before, purpose, created process/container/volume IDs, ожидаемый объём и disposal rule. Secrets, чужие paths и содержимое env в публичный receipt не писать. Default — existing env, compact fixtures и SQLite; Docker/новые images/services — NONE, пока limitation не доказан и gate не пройден.

### 16.2 Что сохранить

Product fixes, canonical contracts, compact generator/fixtures, focused tests, минимальные before/after/evidence/review summaries и exact reproduce commands. Mutable runtime histories реальной системы не трогать. Не сохранять много-GB sandbox потому, что «может пригодиться».

Retained temporary resource оправдан только конкретным невоспроизводимым evidence/ongoing consumer с указанным trigger/сроком и разрешением; неопределённая future optionality недостаточна. Лучше immutable маленький reproducer, чем вся среда.

### 16.3 Последовательность

1. Финальный candidate proof и необходимые review evidence сохранены вне disposable root.
2. На чистом новом root проверена regeneration и независимость от старой DB.
3. Остановлены только созданные этой campaign процессы; проверены IDs, владение, отсутствие shared use.
4. Удалены owned DB/WAL/SHM/temp files, fixture Git repos, containers/volumes/images — только реально созданные/неразделяемые и разрешённые этой задачей.
5. Machine readback подтверждает absence/remaining bytes/process status и сохранение non-target fingerprints.
6. Последняя проверка воспроизводимости не оставляет новую забытую среду; её ресурсы тоже очищены и отражены в receipt.

Нельзя: global Docker prune, удаление shared uv/cache/.venv, чужих branches/history, protected datasets, production backups, путей по непроверенному prefix. Обычный code rollback не удаляет принятые runtime/science records.

**Cleanup FAIL — это незавершённая часть deliverable, а не сноска.** При отсутствии полномочий на конкретный owned residual сохрани точный residual и safe removal instruction, не заявляй CLEAN.

---

## 17. Краткое поручение, которое должно остаться у исполнителя

Собери не демонстрацию, а обычный PAPER/SHADOW operating path вокруг уже существующих owners. Закрой смену стратегии, сохранение старого риска, общий safety envelope, автоматический цикл, настоящие adapters на поддельном внешнем transport, cold recovery и operator readback. Сначала проверяй путь и его самый ранний разрыв, затем чини и доказывай на том же пути. Не сужай цель до того, что легко протестировать; не строй то, что не нужно согласованному operating profile.

Принимай локальные инженерные решения самостоятельно. Meaning/authority заранее заданы D1–D4 и границами. Новую реальную boundary предъявляй точно, безопасные независимые шаги продолжай. Сохраняй semantic truth в том же атоме. Закончи пригодным к commissioning software, честным ledger того, что ещё не доказано, и удалённой временной средой.
