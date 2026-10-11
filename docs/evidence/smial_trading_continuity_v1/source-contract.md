---
document_id: SMIAL_TRADING_CONTINUITY_AUDIT_REPAIR_V1
version: "1.0"
as_of: "2026-10-11"
status: REPO_GROUNDED_EXECUTOR_SPEC_NOT_EXECUTED
repository: lancerbeta/solana-alpha-lab
authoring_ref: main
authoring_commit: d244af69bfd7ddc2850b9e5e5823323956e325c4
chat_mode: DESIGN_ONLY
executor_mode: AUDIT_THEN_REPAIR_WITHIN_EXACT_CONTRACT
scope: post_forge_handoff_to_paper_shadow_execution_reconciliation
admin_ui: EXCLUDED
live_money_authority: NONE
runtime_health_claim: NONE
scientific_claim: NONE
---

# SMIAL: сквозной аудит и repair торгового контура
## Самодостаточное задание исполнителю — PRD + SSD + проверяемые сценарии

**Результат нужен не в виде «нашли несколько багов», а в виде восстановленной и доказанной цепочки:** актуальный выход научного контура → воспроизводимое торговое решение → PAPER/SHADOW → честный результат исполнения → позиция, выход, reconciliation → понятный операторский readback.

Сначала реконструируй весь этот путь и его опасные ответвления. Затем исправь подтверждённые material gaps в согласованном scope и повторно пройди тот же обычный путь. Не останавливайся после первого найденного дефекта, одного repair atom или формального числа попыток. Не подменяй сквозной результат набором успешных локальных тестов.

**Граница:** это подготовка и ремонт software capability в изолированной среде. Не запуск реальной стратегии, не подтверждение alpha, не live commissioning. Админку/Workbench UI не перерабатывать. Коллектор и научную кузню не переизобретать; проверить и при необходимости минимально восстановить их выходные стыки с торговлей.

---

## 0. Команда на старт и правила использования документа

Владелец передаёт исполнителю этот файл и следующую команду:

> **EXECUTE `SMIAL_TRADING_CONTINUITY_AUDIT_REPAIR_V1` по приложенному MD.** Проведи repo-grounded аудит, затем выполни необходимые подтверждённые ремонты внутри указанного торгового scope. Локальная материализация exact task contract и привязка этой спецификации входят в задание. Сам выбери инженерную тактику, минимально достаточную песочницу и разбиение на проверяемые изменения. Не запрашивай подтверждения на безопасные зависимые шаги. Сохраняй текущие Git/security/science gates; merge, deploy, provider calls, новые credentials, wallet/signer, реальные транзакции и расходы не разрешены этой командой. После проверки сохрани компактное evidence и удали созданные для работы тяжёлые disposable-ресурсы по §15. Остановись только на реальной authority/product boundary либо предъяви завершённый результат с exact-head evidence.

Перед product writes:

1. Прочитай текущий `AGENTS.md`, его маршруты, elected-client Delivery Harness и exact policies. Зафиксируй local HEAD, upstream/base, branch, dirty state и вмешивающуюся параллельную работу. Не выбирай другую задачу по «свежести».
2. Свяжи owner objective с одним exact task contract по текущему harness. Если контракт уже существует — проверь identity и scope, не создай дубль. Если отсутствует — материализуй его из этого задания в разрешённом bootstrap-порядке; не обходи machine gate. Название задачи задано явно, но новые runtime/product owners заранее не объявлены.
3. На текущем base уточни concrete write set по dependency closure торгового пути. Исходный SHA выше — доказанный planning anchor, **не приказ откатить свежий main**. Drift оцени по затронутым owners, а не переписывай всё исследование.
4. Выбери entry verdict текущего harness. Routine drift → `START_WITH_PATCH`; реальный product/authority конфликт → только зависимый участок `BLOCKED`. Не превращай подготовку task contract в отдельный проект или серию согласований.

Не дублируй эту спецификацию отдельными PRD/SSD/планами. Task contract содержит binding, scope и DoD. Semantic delta обновляет этот документ и canonical owner в том же изменении.

### Отличия от исходного audit-промпта

Auditor-only заменён на **baseline → audit → repair → independent verification**. Вместо двух входных артефактов — этот единый документ. Не действует максимум одного repair atom или ориентир 5–8 probes: нужны все critical journeys в bounded scope. Удаляется временная среда, а не product fixes/regressions. Проценты coverage не компенсируют незакрытый P0.

Из [S0] сохранены capability-first, independent oracle, falsifiable probes, отрицательное evidence, root-cause investigation, отсутствие lucky-pass и запрет framework ради аудита.

## 1. Что уже установлено при подготовке

### 1.1 Evidence boundary

Read-only Git-проверка выполнена на `d244af69bfd7ddc2850b9e5e5823323956e325c4` (`main`, merge PR #395). Прочитаны front door/policies, профиль execution-domain, ключевые контракты и выборочные участки кода. **Тесты, VPS, рабочие SQLite/ResearchStore, текущие процессы, реальные стратегии и provider routes не запускались.** Это подготовленный execution design, не законченный аудит здоровья.

| Подтверждено в указанном Git-срезе | Следствие для исполнителя | Источник |
|---|---|---|
| Handoff принимает scientific `PROMOTE`; `StrategyVersion` — Git definition, не activation | Номинация, научный вердикт, materialization и запуск — разные gates | G04 |
| `ExecutionEvidenceBindingV1` связывает population, tested notional, quote-pair denominator и fee/cost provenance | Нельзя материализовать режим B из evidence режима A | G16 |
| `StrategyVersion` v1.1 передаёт готовые `SignalDecision`/`ExitDecision` в generic PaperPlane | Научные признаки и названия списков не должны проникнуть внутрь execution engine | G06, G07 |
| `SignalDecision` имеет закрытую schema, `additionalProperties=false`, и `evidence_refs`; поля `episode_id` в ней нет | Нельзя просто приписать новые поля к JSON. Нужен проверяемый provenance binding через существующий seam либо обоснованное versioned contract change | G08 |
| `hfic_research_scope` уже владеет list definitions, selector и membership; состояния `TRUE/FALSE/UNKNOWN/INVALID` | Переиспользовать семантику. Не строить торговый парсер списков с другим смыслом | G09 |
| Episode — отдельная identity; research joins используют `episode_id`, не только mint. Release зависит от завершения траектории до E259200 | Зрелый research release не является своевременным intraday feed. Нужен доказанный доступ к разрешённому prefix, без обхода maturity gate | G10 |
| Старый unattended SHADOW использует pinned offline cohort и маркирован `COMMISSIONING_ONLY` | Его наличие/heartbeat не доказывает ordinary runner для новой стратегии | G11 |
| Runtime policy раздельна по PAPER/SHADOW; effective notional не увеличивает strategy request; revisions и admission binding существуют | Проверять composition, scope и recovery существующего механизма, а не создавать новый риск-движок | G05 |
| `OPEN_RISK_STATES` в коде не включает `EXIT_REQUIRED`, `EXITING`, `UNRESOLVED`; economics §8 называет лимит entry-admission, а не всего inventory | Разные понятия нельзя свести в один счётчик. Расширение риск-политики — отдельное смысловое решение, не «очевидный fix» | G06, G12 |
| В repo есть большой предшествующий integrity design и A4 read-freshness report от 09.10.2026; текущий код открывает readonly SQLite через `mode=ro` | Сначала пересопоставить исторические findings с текущим кодом; исправленные defects оставить regression baseline | G13, G14, G06 |

**Исторические сигналы для проверки, не новый runtime verdict:** отчёт A4 оставляет F01 — ordinary timely episode decision producer, F03 — external attempt/result consumer, F04 — согласованность risk/settled/drain classifications. F02/WAL freshness описан как исправленный в synthetic/offline scope. Нумерация F01–F04 из этого отчёта **не равна** F1–F12 старого integrity design. Не смешивай реестры и не объявляй старую рекомендацию новым task authority. [G13, G14]

### 1.2 Смысловая карта для чтения

`AGENTS.md` → Delivery Harness → `docs/FACTORY_SEMANTIC_MAP.md` → `SEM-OWNER-LIFECYCLE` и Catalog owners. Для данных — `SEM-LIVE-COLLECTION`, `SEM-MARKET-DATA-FEATURES`; Forge — только на handoff/dependency boundary. Exact paths и scope прочитанного — §18. [G01–G03]

По imports/relations дочитай `promotion_handoff`, activation resolver, recipe/feature owners, prefix reader, `paper_shadow_commands`, `paper_shadow_operations`, `trading_operations`, `risk_economics`, application/lifecycle readback. Методы разрешай на своём base. Найденный canonical execution-attempt vocabulary [G17] ещё не доказывает его интеграцию с PaperPlane.

Routes помогают найти owner, но не дают authority. Отсутствие отдельного «trading» route не defect, если путь однозначно находится через lifecycle. [G03]

## 2. PRD: outcome, scope и пользователи

### 2.1 Owner outcome

Пётр должен получить проверяемый ответ:

> Когда кузня выдаст действительно допустимую к следующему шагу версию, сможет ли существующий software-контур без ручного склеивания внутренних объектов принять её, своевременно выработать решения из нужной population, честно проиграть PAPER/SHADOW, пережить отказы и объяснить итог? Что уже исправлено, что доказано только offline и какой exact внешний/смысловой gate остаётся?

**Почему сейчас:** downstream долго почти не использовался по обычному пути, а upstream semantics изменились. Проверяем риск несовместимости цепочки, не «улучшаем торговлю вообще».

**Named consumers:** первая реально прошедшая научные gates стратегия; обычный decision producer/runner; PaperPlane и будущий отдельно разрешённый execution adapter; операторские команды/readback; downstream решение о допустимом продолжении исследования/commissioning.

### 2.2 In scope

Проверить и восстановить необходимую связность:

```text
scientific handoff eligibility + frozen provenance
  → StrategyVersion materialization / verification
  → separate activation and mode eligibility
  → source-bound population/list/recipe + timely observable prefix
  → SignalDecision / ExitDecision
  → runtime admission and idempotent intent
  → quote/model/provider-neutral attempt and result seam
  → Position / exit / reconciliation / modeled accounting
  → pause / drain / resume / recovery / truthful machine readback
  → versioned feedback, without automatic scientific promotion
```

В scope входят отсутствующие last-mile bindings и обычный local entry point, если без них заявленная цепочка существует только в тесте. Малый adapter/producer допустим, когда это подтверждённый gap между существующими owners. Он должен остаться production-capable кодом с offline запуском, а не отдельным demonstration engine.

### 2.3 Non-goals

Не строить новый торговый движок, универсальный strategy DSL, feature store, scheduler/service mesh, отдельную БД позиций, новый UI или платформу аудита. Не внедрять новую alpha-гипотезу и не искать лучшие параметры; synthetic recipes здесь — test fixtures, не научные trials. Не открывать реальные holdouts и не переписывать promotion/history.

Не активировать коллектор, стратегию или provider на рабочем хосте; не менять рабочие политики/БД; не получать quotes через реальные API; не создавать signer/wallet и не отправлять транзакции, включая devnet/testnet. Не вводить количественные live-risk defaults. Не чинить несвязанные участки admin UI.

**Backend operator semantics не исключены вместе с админкой.** Pause/stop/drain, readback freshness, null/unknown и recovery проверяются через существующий CLI/application/service seam без браузерного redesign. Непосредственно необходимый backend fix разрешён; HTML/CSS/навигационный redesign — нет.

Не превращать общий ориентир intraday в жёсткую константу возраста токена или горизонтов: token age, observation/decision/holding/evaluation horizons различны и следуют frozen recipe/experiment. Старые Source-формулировки про «молодые, 15m–4h» не разрешают менять population и окна. [S1, текущая owner-постановка]

## 3. Полномочия, ресурсы и остановки

| Действие | Полномочие этой campaign |
|---|---|
| Read-only repo inspection, local branch/workspace, scoped product/docs/tests fixes | Да, после exact contract и entry gate |
| Existing locked toolchain, компактные fixtures, subprocesses, настоящая disposable SQLite, fault injection | Да, в изолированном scope и с учётом ресурсов |
| Коммиты, обычный non-force task-branch push, PR/CI/reviews | По действующему base-bound Delivery Harness, без отдельного micro-approval |
| Несколько независимых read-only reviewers / probes | Да, если среда поддерживает и это даёт material evidence; isolation и запись результатов обязательны |
| Новый package/image/tool, network install или иной внешний dependency | Не подразумевается. Сначала existing capability; затем named need и соответствующий текущий gate |
| Рабочие runtime state/policy, VPS, deploy/settings, provider calls, credentials, spend, signing/transactions | Нет; нужен exact отдельный owner gate |
| Merge | Только существующий exact-head CI → readiness → owner phrase → guarded merge → post-merge readback |
| Удаление созданных в этой campaign disposable-ресурсов | Да, **только** по проверенному ownership manifest и §15 |
| Удаление чужих данных, старых env, shared caches, Git history/branches; global prune | Нет |

**Нет лимита «две попытки», «один repair», «восемь probes».** Работай до достаточного evidence по согласованному outcome. Однако unlimited engineering effort не означает unlimited API calls, деньги, дисковый рост или научный budget. Каждый повтор имеет причину: изменённый root cause, новый scope evidence либо заранее объявленная race/reproducibility probe. Не reroll-until-green.

Бюджет здесь управляется outcome и ресурсной безопасностью: фиксируй существенные затраты и progress, уменьшай fixtures, когда масштаб ничего не доказывает. При исчерпании безопасного локального ресурса сохрани checkpoint; не занимай диск/память операционной системы до отказа. Полезную независимую работу продолжай без заблокированного внешнего действия.

**Обязательный replan, не автоматическое обращение к владельцу:** повтор одного seam failure после repair, новая competing truth, несколько симптоматических adapters, audit без ordinary path, постоянные environment failures. Сначала измени инженерный подход внутри scope. Владелец нужен, только когда меняются meaning, риск, бюджет, внешний commitment или неизбежная authority boundary. Failed machine gate не отменяется заверением владельца.

Один `NOW` — эта campaign. `WATCH` — отдельно разрешённое commissioning конкретной стратегии после её offline acceptance и scientific eligibility; не скрытый live этап текущей работы.

## 4. Capability contract и карта стыков

### 4.1 Различай три «номинации»

Номинация токена поставщиком — факт участия в source frame. Номинация гипотезы кузней — исследовательский candidate. Scientific `PROMOTE` — принятый научный decision с frozen evidence. Ни одна из первых двух не должна попадать в activation через совпадение имени, статус «ready» в соседнем модуле или commissioning template.

### 4.2 Минимальная таблица capability reconstruction

До ремонта заполни по реальному коду следующую карту. Это audit artifact, не новый production registry.

| Стык | Что должно передаваться | Что надо доказать |
|---|---|---|
| Science → handoff | Exact decision, spec/evidence identities, tested regime | Latest evidence не заменяет decision-time receipt; reject неподходящей номинации |
| Handoff → StrategyVersion | Frozen definition + явные execution inputs | Реальная materialization/verify; без выдуманных risk defaults и activation |
| Strategy → activation | Version/hash, allowed mode, activation identity | Git definition не равна запущенному bot; stale/conflicting activation не принимается |
| Episode/list → producer | Population/episode, T0 membership, definition/selector hashes, clocks | Birth ≠ episode; source list ≠ execution universe; нет survivor/future leakage |
| Recipe/prefix → decision | Frozen algorithm/window/transform + доступные inputs | Replay и ordinary producer имеют одну семантику; нет maturity bypass |
| Decision → admission | Exact identity/body, as-of, evidence refs, declared/runtime limits | Idempotency, freshness, mode/version binding, atomic capacity decision |
| Admission → attempt | Frozen admitted size/fee/policy + stable intent/attempt identity | Нет повторной покупки при retry/crash; policy change не пересчитывает старый admission |
| Attempt → result | Typed success/non-fill/unknown, cost/quantity evidence | Quote ≠ fill; timeout ≠ non-fill; consumer достижим обычным путём |
| Position → exit | Entry-origin recipe/version/epoch, current observable exit evidence | Смена списка/версии не бросает позицию и не подменяет exit новым смыслом |
| Exit → reconciliation | Inventory evidence + causal attempts/events + accounting | UNKNOWN остаётся открытым вопросом; нет fabricated flat/PnL |
| State → operator/readback | Согласованный snapshot, scope/freshness, safe action | Новый read видит committed state; чтение не bootstrap-ит БД |
| Outcome → feedback | Model class, strategy/version, denominator, negative evidence | Paper economics не становятся live FCF или автоматическим promotion |

Для каждого стыка записывай `owner → actual caller → input → state mutation → durable output → consumer → end-state oracle`. **Отсутствие caller — отдельный факт:** schema, функция или passing smoke не заменяют production wiring.

### 4.3 Truth ownership

Git: definitions/contracts; ResearchStore: научные append-only evidence/decisions; PaperPlane: runtime positions/commands/policy; views производные. Операционные значения не переносятся в Git. [G04, G05]

Не добавляй `handoff.sqlite`, вторую position ledger или current-strategy registry. Adapter внешнего execution vocabulary не оправдывает двух truth owners и зеркальную запись в две БД.

## 5. SSD: семантика, которую нельзя потерять на стыках

### 5.1 Научный handoff и materialization

Используй существующие `CHECK → RENDER → VERIFY` и version dispatch. Проверяй frozen `decision_event_id`, effective time, ExperimentSpec hash, population, evidence refs/hashes и execution-regime binding. Исторический manifest 1.0 не «достраивается» из сегодняшних записей; blocker сохраняет точный смысл. [G04, G16]

Материализация должна оставлять источник каждого material поля: science-derived, contract-fixed либо explicitly supplied execution input. Тестовые execution inputs можно задать в synthetic fixture; пропущенное настоящее значение нельзя заимствовать из ближайшей стратегии. Same identity + same bytes — идемпотентность; same identity + different content — conflict без overwrite.

Проверь и положительный путь: валидный handoff действительно становится definition, которую обычный consumer способен загрузить **без ручного редактирования тестом**. Expected deny для недостаточного handoff — safety PASS, но не доказательство работоспособности materialization.

### 5.2 Один source-bound producer вместо ручной подачи готовых сигналов

`paper_plane.py` должен остаться generic engine. Новый или исправленный producer находится **до** `SignalDecision`; повторно использует текущие recipe/list/feature owners и отдаёт результат через текущую decision schema. Execution-domain import boundaries учитывать как contract, не обходить незаметным импортом Forge в движок. [G06, G07, G15]

У producer должны быть однозначно связаны:

```text
strategy_id / version / spec hash
activation_epoch_id / mode
population identity / population contract
recipe identity / version / content hash
source collection / episode_id / mint / T0
list definition + selector + membership evidence bindings
decision point / cutoff / first reliable availability
exact input evidence refs / typed missingness
```

Это **логический набор связей**, не предложение добавить все поля в `SignalDecision`. Текущая schema закрыта. Сначала используй её `evidence_refs` и существующий проверяемый receipt/artifact. Consumer обязан разрешать binding и обнаруживать missing/conflicting target; бессодержательная строка с SHA не доказывает доступность provenance. Если текущий seam не может выразить material связь — минимальное versioned расширение соответствующего owner, compatibility и consumers в том же repair. Не создавать v1.2 «на всякий случай». [G08]

**Ключевой acceptance:** fixture поставляет исходные source-shaped bytes/наблюдения, а не конечный `ENTER`. Нормальный application/runner путь сам вызывает producer, validator, admission и result consumer. Direct injection `SignalDecision` допустим для локальных engine probes, но не засчитывается как whole-chain proof.

Проверь два разных supported recipe shape: list-only и mixed list + numeric trajectory. Это проверка выразимости существующих contracts, не требование универсального языка стратегий. Новая допустимая комбинация известных primitives должна запускаться конфигурацией. Unsupported expression должна давать typed capability gap, а не тихо упрощённый сигнал; такой gap не закрывает обещанный supported path.

### 5.3 Episode, список, watchlist и позиция — разные сущности

`OPPORTUNITY_EPISODES` — population со своей admission identity. Mint может встречаться в разных episodes. Списки Jupiter относятся к source frame; `watchlist_membership` относится к стратегии/гипотезе; состояние позиции `WATCHED` не является ни тем, ни другим.

Используй canonical `hfic_research_scope`: definitions/aliases, `ADMISSION_FRAME_V1` или допустимый `LOCAL_MEMBERSHIP_SNAPSHOT_V1`, bounded selector, `EPISODE_T0` и declared coverage. [G09, G10]

Обязательные semantic cases:

- Один episode в двух исходных списках не даёт две одинаковые торговые попытки. Убрать повтор доставки, сохранив оба evidence refs; не дедуплицировать разные episodes просто по mint.
- Alias списка не создаёт новый question, look или trade. Изменение definition/selector/window — material semantic change с versioning, не переименование.
- `UNKNOWN` не превращается в `FALSE`, нулевое membership или разрешение. Текущий selector требует известности **всех referenced lists**: даже `A=TRUE`, `B=UNKNOWN` для `any_of=[A,B]` остаётся `UNKNOWN`, а не short-circuit TRUE. `INVALID` имеет отдельный refusal. Не заменяй это обычной трёхзначной Boolean логикой. [G09]
- `count min=2,max=2` и `count min=2` различаются. Несколько aliases одного canonical list не увеличивают count.
- Membership в T0 не означает current membership и не доказывает наличие live sell route. Local snapshot имеет собственную availability; загрузка файла позднее не делает его исторически доступным.
- Выпадение токена из списка запрещает только то, что действительно запрещает frozen entry/universe contract. **Открытая позиция остаётся в inventory/exit/reconciliation до честного терминала.** Нельзя удалять её вместе с watchlist row.

При неизвестном необходимом membership остановись до numeric loader там, где это требует scope contract. Это проверяется не только результатом, но и отсутствием чтения запрещённых числовых inputs.

### 5.4 Timely prefix, clocks и frozen feature interpretation

Research release с завершёнными будущими точками и своевременное решение — разные продукты. Не выдавай final/sealed dataset за feed, доступный раньше. Если имеющийся reader умеет только matured release, докажи gap и добавь минимальный read-only prefix seam **над существующим source owner**, а не выключай его maturity protection и не запускай второй collector.

Проверять отдельно:

```text
event_time: когда произошло событие
observed/received: когда источник/процесс его увидел
first_reliable_available_at: когда input впервые допустим по контракту
ingested/visible_at: когда consumer фактически мог получить bytes
decision_cutoff: заранее установленная граница frozen recipe
as_of: явное время исполнения/проверки решения
```

Решение не может зависеть от input, недоступного в decision time. Receipt/ingestion нельзя задним числом приравнять к event time. Grid deadline и stale-signal policy не заменяют друг друга. Данные с поздним availability сохраняются как late/missing evidence, но не лечат старое решение.

Для episode schedule использовать один `resolve_point`. **Контрольный пример:** T0=`12:01:10Z`; E1800 nominal due=`12:31:10Z`, assigned=`12:35:00Z`, availability deadline/decision cutoff=`12:40:00Z`. Не `12:31:10` и не автоматически `12:35`. E300 для такого T0 имеет assigned `12:10`, deadline `12:15`; E3600 — assigned `13:05`, deadline `13:10`. Это fixture schedule arithmetic, не обещание точности реального feed. [G10, G14]

Replay и timely producer должны использовать одну реализацию семантики recipe: lookback, point selection, normalization, units, missingness, rounding и warm-up. При существующем EMA/сглаживании — тот же causal window, seed и minimum-history policy; не добавлять EMA, если recipe её не требует. Запрещены symmetric windows, nearest-point healing, интерполяция и backfill, не разрешённые exact contract.

Смена будущего E14400 не должна менять decision на E1800, его semantic identity или использованные input refs. Логи loader должны доказать, что будущая точка не читалась для решения, а не только что результат случайно совпал.

### 5.5 Identity, activation и повторная доставка

Разделяй **business identity** решения и fingerprint его content. Identity задаётся логическим событием, а не текущим process time или случайным UUID на каждом retry. Content fingerprint нужен, чтобы тот же ID с другим body давал conflict, а не новый вход.

Концептуально, не вместо текущего identity owner:

```text
logical decision key = strategy/version + activation + episode + frozen recipe + decision slot
body fingerprint = canonical accepted decision content
replay(same key, same body) → same result / no second effect
replay(same key, conflicting body) → typed conflict / no overwrite
```

Если рецепт или corrected source меняет смысл уже принятого решения, не скрывай это сменой ID: нужна предусмотренная revision/version semantics. Нельзя «исправить идемпотентность», каждый раз генерируя новый ключ. В текущем code `position_id_for_signal_decision` напрямую зависит от signal ID; producer identity поэтому является money-adjacent invariant. [G07]

Проверь одинаковый mint в двух episodes; два разных signals на mint; две strategy versions; перекрывающиеся activation epochs; PAPER и SHADOW. Дедупликация подавляет повтор **одного** намерения, а admission policy отдельно решает допустимость нескольких намерений. «Один mint — одна позиция навсегда» не вводится.

`as_of` обязателен; existing future-skew guard и max-age сохраняются. Старые записи с отсутствующими fingerprints трактуются только по declared compatibility, не переписываются скрытым backfill. Смена strategy bytes под той же identity должна обнаруживаться. [G05]

Exit работает относительно originating position/version. Новый epoch не должен автоматически переинтерпретировать старую позицию. Допустимость scientific ExitDecision после deactivation — прочитай у current activation owner: старый design оставлял это отдельным вопросом. Если решение не принято, не выдумывай разрешение; сохрани существующий безопасный operator/reconciliation path и заблокируй только неоднозначную автоматическую ветку. [G13]

### 5.6 Admission, stop, in-flight и внешний result seam

Сохраняй существующий serialized SQLite admission: strategy request, runtime policy и current inventory должны оцениваться вместе. Runtime cap может уменьшить requested notional, но не увеличить его. Недостаточный headroom для целого заявленного entry — block, не незаявленное auto-shrink. Mode/strategy-family/bot-local scopes различаются. Admission замораживает effective size/fee/policy revision/hash. [G05]

Проверь notional/fee mismatch между admission и fill; race двух конкурирующих admissions; stale policy write; replay той же команды; rollback append-only; неизвестный notional relevant open-risk row; новую version в той же strategy family.

Состояния обработки не смешивать:

| Класс | Что проверять |
|---|---|
| Pre-attempt: `WATCHED/SIGNALLED/INTENT_CREATED` | Stop/pause/invalid policy запрещают новый effect; честная cancellation может позволить drain без выдуманного fill |
| Possibly submitted: `ATTEMPTING/UNKNOWN` | Повтор signal не auto-fill и не новый send; требуется reconciliation |
| Open/exit-pending inventory | Entry-side stop не удаляет inventory и не отключает управление уже открытой позицией |
| Definitive non-fill | Возможен честный terminal без позиции, но chargeable costs не исчезают |
| Reconciled close | Терминал требует соответствующего evidence, а не команды «закрыть» |

Для external-attempt seam сначала выясни, что уже реализовано из старого A5. Если seam отсутствует, создай минимальный provider-neutral input/result consumer в существующем position owner. Обычный runner должен его вызывать; API без caller — незакрытый gap.

Разделяй: intent → attempt occurrence → observation/result → reconciliation. Повтор доставки одного observation не создаёт новый attempt. Неопределённый transport timeout не доказывает, что effect не произошёл. Missing route, pre-send reject, definite processed failure и uncertain outcome должны сохранять разные последствия для inventory и fees. Provider-specific quirks остаются в adapter, не в общем lifecycle.

**В этой campaign внешняя сторона — controlled fake/replay, не реальные отправки.** PAPER — model evidence; SHADOW — только тот тип наблюдения, который реально подтверждает source. Synthetic quote может проверить software mapping, но не становится `REAL_FILL` или доказательством executable market liquidity. Live/micro-live guards сохранить. [G06]

Не вводи generic partial-fill machinery только ради полного алфавита биржевых статусов. Unsupported outcome должен честно отказываться/требовать reconciliation; невозможность принять необходимый текущему contract outcome — material gap. Объём реализации выбирается по поддерживаемому execution product, не по всему миру trading.

### 5.7 Inventory risk и обязательная граница смыслового решения

В текущих contracts entry-admission limit, outstanding inventory, operator-settled и drain-cleared — **не одно множество**. Например, `CLOSED` может быть operator-settled, но ещё не drain-cleared; `CANCELLED` — non-fill и PnL N/A. [G06, G12, G13]

Построй одну таблицу `state → entry-admission / possible inventory / operator-settled / drain-cleared / next safe action` из authoritative owners. Найди consumers, которые случайно используют не ту колонку. Исправление неправильного consumer, дублирующей несовместимой константы или ложного readout входит в scope.

**Но:** включить `EXIT_*`/`UNRESOLVED` в admission veto или переопределить лимит всей strategy family — material risk-policy change, а не механическая унификация. Старый design явно выделял такое решение отдельно. Не делай silent «более безопасный default». Подготовь точный diff поведения, минимальный counterexample и рекомендацию; dependent policy verdict остаётся blocked до owner decision. Независимые repairs продолжай. [G12, G13]

При возможной открытой позиции потеря наблюдаемости не должна отображаться как flat/healthy. Проверяй существующий guard новых входов отдельно от narrow entry counter и сохраняй доступность exit/reconciliation. Неразрешённый конфликт safety policy нельзя закрыть зелёным тестом текущей реализации.

### 5.8 Accounting и readback

PAPER/SHADOW, versions, epochs и evidence classes не смешивать. Reconciled model PnL и open marks не суммировать в «TOTAL», equity, cashflow или свободный капитал. В текущем economics contract модельные fees — не total real trading costs; `NETRETURN_STATUS=NOT_ESTABLISHED`, `OWNER_FCF_STATUS=NOT_AVAILABLE`. [G12]

Используй independent arithmetic oracle §10, не импорт production PnL helper как ожидаемый ответ. Проверяй exact units/Decimal, round-trip fee inclusion, mark vs settle, no-route/failed exit и UNKNOWN. Отдельно разберись, включена ли route fee уже в quote output: повторное вычитание такой fee — double count, а не консервативность. Новую cost model без contract не выдумывать.

Readback берётся из действительного persistent state независимым connection/process, не из возвращённого только что объекта. Проверяй причинный event order, согласованность policy/inventory в одном snapshot и следующий свежий read после commit. SQLite WAL sidecars допускаются в уже принятом узком scope; это не permission создавать root/DB/schema, делать migration/checkpoint/repair или business writes при GET. [G14]

Missing source, corrupt DB, OS access denial и SQL read error — разные источники UNKNOWN, не нулевые позиции/PnL. Существующий read model должен сообщить status, scope, as-of и next safe action. TTL нельзя придумать в projection: например, текущая mark-freshness policy явно `NOT_DEFINED`. [G12]

## 6. Песочница: настоящая логика, поддельный внешний мир

### 6.1 Самый дешёвый достаточный substrate

Начни с existing locked Python toolchain, маленьких tracked fixtures, disposable filesystem и настоящей SQLite. Для concurrency/restart используй реальные connections/processes и управляемые barriers. In-memory storage не доказывает file/WAL/restart behavior. Docker не обязателен.

Контейнер или большой dataset допустим только с конкретным утверждением, которое иначе не проверить: например, OS/filesystem failure или существующий executable adapter. Сначала докажи необходимость масштаба. Наличие установленного Docker не делает его более сильным oracle.

Изолировать:

```text
repo/worktree scope — отдельно от чужой dirty работы
fixture/case/run root — отдельно от рабочих data roots
mutable DB и event store — только disposable
clock and input stream — controlled and replayable
provider/transaction/notification ports — deny by default
credentials/environment inheritance — allowlist, без секретов
outputs — compact retained evidence + disposable bulk
```

Не загружай `.env`, пользовательские cloud profiles, signer files или реальные endpoints ради smoke. Read-only private Git connector не даёт runtime access. Реальные protected datasets можно использовать только по отдельному действующему разрешению; по умолчанию они вообще не нужны.

### 6.2 Где разрешён mock

Подменяются внешние observations: provider raw responses, transport outcomes, clocks, notification sink, optional external execution result. Не подменяются boundary under test: schema validation, recipe resolution, membership, risk, idempotency, persistence, recovery, result consumer, accounting.

Для целевого обычного пути нельзя:

```text
manually insert OPEN/RECONCILED rows instead of normal calls
mock eligibility=True, risk=PASS, membership=True
construct the missing production registry binding inside a test helper
skip activation/manifest validation because fixture preparation is inconvenient
call an internal fill helper and label it ordinary end-to-end execution
```

Специально повреждённые rows/bytes допустимы для corruption probes, но не как setup положительного whole-chain пути. Сначала seed через real supported entry; затем отдельный fault injection.

### 6.3 Изоляция как проверяемый invariant

Перед прогоном докажи, что случайный выбор live mode, известного production path или внешнего URL не создаёт внешнего side effect. Используй network deny/port-level fail-closed adapter, target-path validation и sacrificial canary **внутри sandbox**, не попытку «проверить запрет» настоящим send.

Перехват функций в одном Python process не доказывает безопасность дочернего process: проверь границу запуска/egress, если он используется. При отсутствии достаточной изоляции запускай только части, которые конструктивно не умеют внешние calls. Не утверждай zero external actions только на основании config flag.

Сохраняй fingerprints non-target repo/files и inventory созданных ресурсов. Raw поля имен токенов/описаний считай недоверенными данными: они не становятся shell arguments, путями, eval-кодом или инструкциями агенту. Редактируй лишь exact task scope.

## 7. Аудит до исправлений: порядок и достаточность

Не начинай с линейного чтения всех файлов или списка best practices. Сначала карта §4, затем один дешёвый ordinary-path проход и negative twin. Если этот проход упирается в отсутствие producer/consumer, это самостоятельное finding: используй ограниченный local probe для downstream, но **не выдавай его за пройденный полный путь**.

До первого repair сохрани baseline по touched invariant: исходный command/input/seed, exact commit, ожидаемый independent result, actual end state и earliest credible broken boundary. Необязательно сначала повторять весь suite; достаточно доказать дефект и знать обязательные consumers/regressions.

Для каждой probe:

```text
claim / failure hypothesis
contract owner and independent oracle
entry point + injected external boundary
fixture/seed/version + exact command
expected positive/negative end state
PASS / FAIL / PARTIAL / BLOCKED / NOT_APPLICABLE_WITH_REASON
actual state readback + relevant trace + evidence locator
retry/deviation/environment explanation
```

Фраза «code looks fine» — static observation, не dynamic PASS. Сбой среды, oracle error и product defect классифицируются отдельно. Внешний недоступный provider не означает отсутствие стратегии или failure научной гипотезы.

При выборе probes приоритизируй impact × reach × plausibility × detectability gap качественно, без выдуманных точных score. Расширяй план, когда обнаружен новый критический путь. Заверши расширение, когда дополнительные варианты не могут materially изменить verdict/repair decision в согласованном scope.

## 8. Начальная scenario matrix

Это покрытие классов риска, **не требование 24 отдельных новых тестовых файлов**. Параметризуй и объединяй общую подготовку; existing adequate checks засчитываются. P0 — критично для acceptance заявленного offline software scope. `NOT_APPLICABLE` требует доказанного отсутствия supported path/consumer и не может скрыть недостающую обязательную возможность.

| ID / priority | Проверяемая гипотеза и setup | Oracle / требуемый end-state evidence |
|---|---|---|
| S00 / P0 | Ошибочная live config, внешний endpoint или production-like path может покинуть sandbox | Sacrificial canary + isolation boundary: ноль внешних effects, реальных data-root writes и credential use; отказ до опасного действия |
| S01 / P0 | Token nomination / nominated hypothesis / failed experiment может пройти как scientific PROMOTE | Существующий handoff guard отказывает с причиной; нет strategy materialization/activation/intent |
| S02 / P0 | Handoff «лечится» latest evidence либо режим исполнения меняется незаметно | Valid fixture materializes; missing/legacy/tampered manifest, другое decision/time/population/size/fee дают canonical blocker; source bytes неизменны |
| S03 / P0 | Definition смешана с activation, либо valid strategy не загружается обычным runner | Real CHECK/RENDER/VERIFY → normal load → отдельная sandbox activation; до неё нет bot/effect; LIVE denied |
| S04 / P0 | List semantics теряются при переносе в торговлю | Независимая truth table для list-only/mixed, aliases, `exactly2`/`atLeast2`, UNKNOWN/INVALID; coverage refusal не читает запрещённые numeric inputs |
| S05 / P0 | Duplicate membership даёт второй trade, а mint-dedup стирает другой episode | Один logical episode event → один effect; разные episodes сохраняют identity и независимое membership; outcomes проходят текущий admission policy |
| S06 / P0 | Полный путь существует только при ручной подаче SignalDecision | Source-shaped fixture → ordinary producer → decision → PaperPlane → modeled result; consumers вызваны штатно, provenance разрешим; O1/O5/O8 из §9 |
| S07 / P0 | Используются недоступные/будущие values или неправильный clock | Hand-calculated grid/cutoff; late input отвергнут; изменение future point не меняет decision; loader-readset подтверждён |
| S08 / P0 | Retry/content drift/version switch создают второй effect или ломают старый exit | Same ID/body replay; same ID/different body отказ; explicit as-of/future guard; originating version/epoch сохранён; new version не переопределяет old position |
| S09 / P0 | Конкурентные admissions превышают policy либо используют mixed scopes | Barrier-controlled real SQLite connections; один permitted reservation при одном свободном slot; frozen admitted amount/fee/revision; PAPER/SHADOW и family/bot scopes не смешаны |
| S10 / P0 | Stop/pause/invalid policy не доминирует над ещё не отправленным intent | Pre-attempt идёт в permitted non-fill terminal, не OPEN; repeated command идемпотентна; ATTEMPTING/UNKNOWN не auto-fill |
| S11 / P0 | Result consumer не существует либо маскирует NO_ROUTE/reject/failure как fill | Обычная submit/result boundary со fake external side; по каждой supported terminal class правильные state/inventory/cost consequence; unsupported явно отказано |
| S12 / P0 | Lost acknowledgement, delayed/duplicate callback или restart повторяет side effect | После uncertain attempt сначала reconciliation той же identity; positive/negative поздний результат применён один раз; conflicting result не перезаписывает accepted evidence |
| S13 / P0 | Исчезновение из списка/route loss/смена версии бросает позицию | Inventory остаётся видимым; exit/reconcile доступны; no-route не становится CLOSED/zero loss; recovery продолжает originating contract |
| S14 / P0 | Crash между state и event/command оставляет split truth | Детерминированные fault points до/после commit; состояние и causal event оба есть либо обоих нет; restart не дублирует admission/fill/command |
| S15 / P0 | Два GET или живой WAL возвращают stale/mixed состояние | Реальный writer + независимые reads: один snapshot внутренне согласован, следующий видит commit; concurrent readers не закрывают handles друг друга; business rows не изменены чтением |
| S16 / P0 | PnL/denominator скрывает расходы, failures или несовместимые scopes | Independent Decimal oracle §10; exact counts и accounting components; marks отдельно; UNKNOWN не zero; нет LIVE/FCF claims |
| S17 / P0 | Missing/corrupt/inaccessible state выглядит как healthy/flat; restore неполон | Native failure, а не декоративный chmod; typed unavailable; поддерживаемый backup/restore в свежий root; integrity, lineage, policy и pending inventory восстановлены |
| S18 / P0 | Stop/drain/entry-limit используют несовместимые state sets | Матрица §5.7 сверена между command, engine и readback; pre-attempt cancellation не требует fill; unresolved inventory не объявлено drained; policy fork выделен отдельно |
| S19 / P1 | Новый путь сломал legacy v1.0 или старый schema/store | Existing commissioning/regression suite и fixture старого store; version dispatch честен; compatibility не превращает legacy smoke в новую scientific strategy |
| S20 / P1 | Поодиночке всё работает, но чередование событий/restart создаёт orphan/двойной effect | Mixed deterministic stream: arrivals, duplicates, pause/resume, revision, route loss, restart; conservation counts + no orphan + bounded resource growth |
| S21 / P1 | После repair следующий агент/оператор не найдёт ordinary entry или использует stale truth | Независимый reader следует canonical route к команде, supported scope, failure/recovery/readback; нет competing owners/ручной секретной процедуры |
| S22 / P0 | Audit оставляет гигабайты или cleanup удаляет не своё | Resource manifest, pre/post inventory, clean-room reproduction после удаления bulk, non-target files сохранены; §15 |
| S23 / P0 | Engineering fixtures/negative outcomes изменяют научную историю или разрешают promotion | Ноль изменений real trial/holdout/promotion/activation state; synthetic evidence явно отделено; feedback не auto-promote |

Для положительного значения safety guard проверь и допустимого соседа. Система, которая отказывает всем сигналам, может пройти deny tests, но обязана провалить S03/S06.

## 9. Разжёванный основной сценарий: episode → decision → closed modeled outcome

### 9.1 Минимальный synthetic world

Fixture должна быть маленькой, полностью искусственной и явно помеченной `SYNTHETIC_OFFLINE`. Используй syntactically valid IDs/mints через существующие fixtures, без связи с реальными wallets. Согласованный scientific manifest генерируется штатным code path в disposable ResearchStore; это не новый настоящий scientific look.

Семантический recipe A:

```text
population: OPPORTUNITY_EPISODES
membership: ListA at episode T0, source-bound
entry: membership known TRUE AND delta(holder_count, E300, E1800) > 0
exit: frozen fixed-time E3600 example
size / modeled fee / policy: explicit fixture inputs
```

Recipe B — supported list-only selector, без искусственного numeric predicate «лишь бы engine работал». Перенос известной комбинации не должен требовать нового if по имени стратегии внутри PaperPlane.

Наполнение и expected decision:

| Case | Inputs | Ожидаемый смысл |
|---|---|---|
| O1 | A TRUE, holders 60→66 timely; тот же episode присутствует также в B | Один ENTER logical event, одна admission/effect identity |
| O2 | Тот же mint в другом weekly episode; A FALSE | NO_ENTER; membership первого episode не наследуется |
| O3 | A TRUE, holders 60→60 | NO_ENTER |
| O4 | A TRUE, первый holder input missing | Typed UNKNOWN/unavailable, без delta относительно нуля |
| O5 | A UNKNOWN | Coverage refusal до numeric loader; не FALSE и не ENTER |
| O6 | A TRUE, конечный holder input available после cutoff | Late/missing зафиксировано, значение не влияет на старый decision |
| O7 | Replay O1 после restart, другой delivery order, duplicate membership | Те же semantic decision/body binding и single effect; без второго slot |
| O8 | Изменены только future E14400/поздняя correction | Решение O1 и его допустимый readset неизменны |

Таблица является independent ожидаемым результатом, а не генерируется вызовом production predicate. Canonical enum/refusal code уточняй по актуальному owner; UNKNOWN и BLOCKED не объединять для удобства теста. Для coverage refusal важны причина и отсутствие запрещённого чтения.

### 9.2 Реальный путь исполнения fixture

```text
source-shaped admission frame + timed observation prefix
    ↓ existing source/list/recipe resolver
normal decision producer (real code; controlled clock)
    ↓ schema-valid SignalDecision + resolvable provenance
ordinary runner/application binding
    ↓ current activation and runtime admission
PaperPlane position/intent
    ↓ controlled PAPER or SHADOW result adapter
entry outcome → originating ExitDecision → exit outcome
    ↓ independent persistent readback
reconciliation + modeled economics + operator state
```

Не seed-ить напрямую result rows, не менять production code на `if test`, не обходить required bindings. Если нормального entry point нет — это и есть gap, который нужно восстановить. Первый smoke может быть partial, но финальный S06 должен запускаться на исправленном ordinary path.

### 9.3 Negative/recovery continuations того же сценария

После admission, но до attempt: pause/stop → честный non-fill/cancel; нет покупок. После possible attempt, но до acknowledgement: restart → та же uncertain identity и reconciliation, не новый trade. После entry: убрать mint из source list и дать no-route на exit → inventory остаётся и PnL не выдаётся за settled. Затем controlled recovery evidence завершает тот же lifecycle без двойного close.

Отдельно: активировать новую version для новых decisions при старой открытой позиции. Новая version не меняет entry-origin exit и не скрывает её inventory. Критерий допустимости scientific exit после смены epoch берётся из current contract либо остаётся отдельным blocked policy question (§5.5).

## 10. Независимые oracles и несимметричные ловушки

### 10.1 Денежный oracle — только modeled PAPER example

Используй Decimal strings; округление current accounting — `ROUND_HALF_UP` до cents. Fixture без дополнительных costs:

```text
entered_notional = 30.00 USD
entry_price     = 0.000003 USD/token
quantity        = 10,000,000 tokens
exit_price      = 0.0000033 USD/token
exit_notional   = 33.00 USD
modeled fee     = 20 bps on each notional
entry_fee       = round_half_up(30 × 20 / 10000, 0.01) = 0.06
exit_fee        = round_half_up(33 × 20 / 10000, 0.01) = 0.07
gross           = 3.00
modeled_net     = 3.00 − 0.06 − 0.07 = 2.87 USD
```

Ожидаемые значения задаются независимо от production helpers. Добавь один tiny-price/large-quantity вариант и одну rounding boundary, которые существующие tests ещё не закрывают. Когда exit неизвестен, ожидается **не** `2.87`/`0.00`, а unresolved inventory и неполный settled result. Этот расчёт не включает реальные chain/provider/infra costs и не доказывает NetReturn/FCF. [G12]

Проверь отдельно failed attempt с известными chargeable costs и без fill. Position PnL может быть N/A по contract, но известная стоимость попытки не должна исчезнуть или превратиться в «нулевую операцию». Если current accounting умеет только modeled fill fees, отрази точный capability gap/отдельный cost plane, не создавай ложный all-cost headline.

### 10.2 Conservation oracle

На одном изолированном stream составь независимо ожидаемые множества:

```text
source episodes / distinct mints / duplicate deliveries
eligible vs NO_ENTER vs UNKNOWN/BLOCKED decisions
unique admitted intents / definitive non-fill / in-flight unknown
entered inventory / exit-pending / closed awaiting reconcile / reconciled
```

Сравни sets/IDs, не только суммарные counts: два пропуска и два дубля могут взаимно погаситься. Считай all admitted episodes, а не только survivors/filled rows. Для handoff execution denominator проверяй существующий invariant `two_way_n + entry_only_n + no_entry_n + unknown_n = population_n`. [G16]

### 10.3 State oracle

Проверяй конец сценария независимым connection/process либо sanctioned snapshot read. Не используй единственный результат функции как доказательство одновременно «команда сработала» и «состояние записано».

Fault injection направлять в точную границу: до state transaction, после durable intent, после commit до return, между observation receipt и обработкой. Не rely только на случайный `sleep` и гонку в надежде на воспроизведение. Для racy finding фиксируй controlled interleaving; для natural stress — все trials и наблюдённую частоту, без выборки успешных.

### 10.4 Assumption challenge

Как минимум один критический oracle должен быть способен опровергнуть ошибку, одновременно записанную в code, test и документации. Здесь лучшие кандидаты: hand-calculated clocks; list coverage truth table; independent PnL; actual committed SQLite state; намеренное отсутствие production binding.

При необходимости targeted mutation доказывает силу проверки: временно сломай конкретный invariant в disposable copy и убедись, что assertion ловит его. Не запускать mutation framework на весь repo; сохранить минимальное evidence и убрать mutation.

## 11. Repair: root cause → propagation → тот же путь

### 11.1 Классификация findings

Каждая находка получает class и evidence strength:

```text
DEFECT — реализованный contract нарушен
SEAM_GAP — нужный producer/binding/consumer отсутствует
SEMANTIC_CONFLICT — owners/consumers расходятся в meaning
OPERABILITY_GAP — failure/recovery/readback не дают безопасного управления
EVIDENCE_GAP — пока не доказано; не автоматически product bug
ENVIRONMENT_OR_ORACLE_ERROR — проблема самого audit
INTENTIONAL_UNSUPPORTED — явно допустимая граница, не скрытый «готово»
```

Evidence strength: `CONFIRMED / PROBABLE / UNVERIFIED`. Для deterministic defect желательно минимальное воспроизведение и повтор после ремонта; 2/2 — хороший контроль воспроизводимости, не бюджет на поиск причины. Код-reading finding без динамического доказательства не усиливать до runtime fact.

### 11.2 Разрешённый repair loop

```text
owner scenario → earliest broken boundary → минимальный source-owner fix
→ реальные consumers/contract/navigation propagation
→ тот же scenario и negative/recovery twin
→ cross-chain regression → independent review
```

Чини раньше потерянный смысл, а не добавляй fallback в последнем consumer. Если membership потерялось до decision, не угадывай его из названия strategy в engine. Если event не записался атомарно, не лечи projection синтезированным event. Если обычный caller не существует, тестовый adapter не закрывает gap.

Grouping — по invariant и единому observable outcome, не по числу файлов. Можно иметь несколько coherent increments и commits внутри campaign. PR-разбиение выбирается по reviewability, regression surface и действующему harness, не по квоте «один finding — один PR». Между безопасными зависимыми шагами owner OK не нужен; exact merge gate остаётся для каждого действительно поставляемого PR.

### 11.3 Предпочтительный порядок, уточняемый baseline

**Сначала source/decision continuity.** Проверить и закрыть F01-подобный seam: recipe/population/list provenance + timely prefix → ordinary producer → current decision contracts. Без этого downstream happy-path proof слишком легко оказывается искусственным.

**Затем attempt/result continuity.** Проверить текущую реализацию A5/F03; минимально состыковать ordinary caller, outcome vocabulary и inventory/reconciliation. Не строить живой execution adapter вместо offline contract proof.

**Затем state/operations consistency.** Проверить F04-подобные consumers, pause/drain/resume, accounting и fresh readback. Механические semantic mismatches чинить; неподтверждённые risk-policy изменения вывести на owner boundary.

Это не три обязательных новых PR. Если более ранний P0 safety defect блокирует сами probes, исправь его первым и запиши reorder. Уже исправленный A4 не нужно переписывать: достаточно точной regression и cross-consumer проверки.

### 11.4 Reuse и новые зависимости

После первого material blocker до custom construction прочитай текущий reuse registry/решение у canonical owner. `ADOPT → WRAP → REUSE/REPAIR → BUILD`: для этого scope наиболее вероятен reuse существующего Python/SQLite spine. Новый инструмент нужен только для named unsupported verification/production seam и с показанным выигрышем.

Не добавляй audit service, новую CI платформу, постоянный chaos cluster или второй engine. Репозиторные review/security rules важнее общих skill-рецептов; universal TDD, новые tests на каждую правку и отдельный critic на каждый микрошаг не требуются. Code review и обязательные triggered roles сохраняются. [G01, G18]

## 12. Execution phases и контроль результата

**A — Anchor и baseline.** Карта §4, различение historical/current findings, маленькая sandbox, safety proof S00. Сохрани baseline до target-code changes. Первые falsifiers — O1/O5/O8; missing path фиксируется как finding, не мешая независимым downstream probes. Preparatory-only PR не нужен.

**B — Audit и repair increments.** Каждый coherent fix имеет before/after path, consumer/semantic propagation, regression surface и rollback. Одна общая scenario matrix сохраняет whole-chain outcome; её нельзя заменить локальными определениями «готово».

**C — Whole-chain и review.** Повтори обычный путь из source-shaped inputs и критические negative/recovery branches в fresh process/root. Review — exact contract/diff/evidence и текущие role floors: code, material goal/DoD/architecture; owner-UX при изменении CLI/readout. При требуемом semantic-premise packet используй существующий механизм. Отсутствие независимого reviewer не имитировать: deterministic evidence сохраняется, `SINGLE_AGENT_REVIEW_FALLBACK` не разрешает merge. [G18]

**D — Cleanup и handback.** Выполни §15, затем final evidence binding и доступные delivery gates. Late inventory changes требуют применимой перепроверки. Cleanup входит и в partial handback. Verified offline path не равен merged/deployed/runtime DONE.

## 13. DoD: что должно стать истинным

### 13.1 Главный acceptance

**Недостаточно:** `tests PASS`, найдено N дефектов, «всё fail-closed», есть красивый отчёт или producer function без caller.

**Достаточно для `OFFLINE_CHAIN_VERIFIED`:** на exact code candidate сохранены и воспроизводимы:

1. **Ordinary positive continuity.** Valid source-bound handoff/strategy и supported list-only/mixed recipe достигают normal decision/admission/result/exit/reconciliation/readback без ручной сборки недостающих business bindings. Synthetic activation отделена от materialization; деньги/провайдеры отсутствуют.
2. **Semantic and temporal fidelity.** Episode/list/recipe/version/provenance и clocks проходят все границы; O1–O8 дают независимые expected outcomes; повторные memberships/доставки не создают duplicate effect.
3. **Negative and recovery correctness.** Stop, stale input, missing scope, invalid policy, possible attempt, no-route exit, crash, concurrent write/read и restore не дают fabricated fill/flat/PnL, orphan inventory или потерю управления старой позицией.
4. **Accounting/readback truth.** Independent денежный и conservation oracle сходятся; class/scope/UNKNOWN видимы; свежий read соответствует persistent state и не мутирует business data. Известные limits не выданы за total-risk/equity.
5. **Durable repair and reproducibility.** Product fixes, compact regressions и затронутые canonical docs/routes согласованы; старые semantics не переписаны. Повтор на fresh disposable root возможен из repo + небольших fixtures + точной команды. Нет обязательной многогигабайтной среды.
6. **Safety, review, cleanup.** Нет неразрешённых external/runtime/science actions; mandatory reviews/checks выполнены в доступном scope; cleanup доказан, а незакрытые authority gates названы точно.

Критический required путь нельзя вычеркнуть из scope после того, как он упал. Если missing producer или unsupported обязательный recipe не восстановлен, результат — partial, даже когда все реализованные guards работают.

### 13.2 Отдельные verdict axes

```text
AUDIT_VALIDITY:
  VALID | VALID_WITH_LIMITATIONS | INSUFFICIENT

CAPABILITY_OUTCOME:
  OFFLINE_CHAIN_VERIFIED
  NO_MATERIAL_REPAIR_NEEDED_IN_VERIFIED_SCOPE
  REPAIR_PARTIAL_BLOCKED
  AUDIT_INCONCLUSIVE

DELIVERY:
  LOCAL_VERIFIED | PR_REVIEW_PENDING | READY_FOR_OWNER_MERGE_PHRASE
  | MERGED_WITH_POST_MERGE_READBACK

EXTERNAL_COMMISSIONING:
  NOT_ASSESSED_NO_AUTHORITY   # для этой campaign

CLEANUP:
  CLEAN | RETAINED_EXACT_JUSTIFIED_ARTIFACT | BLOCKED_OWNERSHIP_OR_EVIDENCE
```

Это report vocabulary, не новые production schemas/statuses. `NO_MATERIAL_REPAIR_NEEDED_IN_VERIFIED_SCOPE` допустим только после достаточной проверки, не после code scan. Успешный expected refusal засчитывается в safety coverage, **не** вместо positive continuity. `OFFLINE_CHAIN_VERIFIED` никогда не означает разрешённый live запуск или прибыльность.

### 13.3 Метрики доверия к проходу

Сохрани исходные useful метрики [S0], но показывай raw числители/знаменатели и PASS/FAIL/BLOCKED отдельно:

| Метрика | Правило здесь |
|---|---|
| COC — Critical Outcome Coverage | Какие critical outcomes реально проверены / какие требовались; testing coverage не равно доле успешно восстановленных outcomes |
| RJC — Runtime Journey Coverage | Сколько critical ordinary journeys реально исполнено end-to-end; isolated engine probes отдельно |
| ARC — Adversarial Risk Coverage | Какие top failure hypotheses реально атакованы, а не перечислены |
| DER — Direct Evidence Ratio | Material conclusions с direct machine evidence / все material conclusions; static facts честно выделены |
| PEF — Plan Execution Fidelity | Planned → attempted → executed → evidenced; equivalent replacement объяснён; original denominator не исчезает |
| FR — Finding Reproducibility | Deterministic reproduction и after-fix; для races/intermittent — метод, все trials и частота |
| Critical evidence gaps | Точное число и список P0 UNKNOWN/BLOCKED. Для сильного whole-chain verdict — 0 в заявленном scope |

Targets исходника 85%/80% не дают права закрывать красный критический путь. Число tests/строк/commits/critic approvals не является outcome metric.

## 14. Evidence, логирование и durable artifacts

### 14.1 Что логировать

Собирай полную **релевантную техническую** траекторию: входная identity/hash, entry point, переход состояния, causal relation, reason/refusal, source availability, attempt/result identity, policy binding, expected/actual, restart/fault point. Нужен ответ «где пропал смысл и что записалось», а не dump всего процесса.

Пример компактной audit-записи; поля не навязываются production schema:

```json
{
  "scenario_id": "S12",
  "step": "reconcile_after_lost_ack",
  "input_ref": "fixture:lost-ack-v1",
  "identity_ref": "same-logical-attempt",
  "expected": "single_effect_after_reconciliation",
  "actual_status": "PASS",
  "oracle_ref": "independent-persisted-state-check",
  "evidence_ref": "relative-path-in-audit-output"
}
```

Реальные значения результата записывает только прогон. Этот JSON — **пример shape, не готовый receipt и не evidence PASS**. В machine evidence используй existing accepted schemas/whitelists; новые narrative fields не добавлять в harness completion JSON.

Не логировать secrets, raw environment, приватные endpoints, большие dumps или внутренние рассуждения модели. Untrusted token text не нужен в ключах/путях. Для reproducible fixtures сохраняй seed/generator/input hash; для irreproducible минимального failure — необходимые безопасные source bytes до cleanup.

Если output содержит run-specific IDs/time, раздели raw hash и documented deterministic projection для сравнения. Не нормализуй semantic clocks, event order, IDs/versions или missingness ради совпадения.

### 14.2 Finding/repair ledger

Один компактный ledger может находиться в итоговом report; отдельная БД/сервис не нужны.

```text
finding_id + historical_source_id (если есть)
claim / type / priority / evidence strength
scenario + reproducer + base evidence
root owner / affected consumers / blast radius
repair decision + why not cheaper alternative
changed paths / contract delta / compatibility
verification + after evidence
residual / owner gate / rollback
```

Отдельно помечай: fixed now; already fixed/revalidated; unsupported by intent; genuine owner decision; evidence gap. «Рекомендованный дальнейший repair» не считать выполненным текущим repair.

### 14.3 Что оставить в Git

Product code, canonical contract/schema/route updates по impact, compact test fixtures/regressions, task binding, небольшие before/after summaries и необходимые review/completion receipts. Historical scientific/operational evidence не переписывать. Generated Catalog/navigation обновляются своим generator/sync, не вручную. [G18]

Bulk traces, Docker layers, mutable DB, большие replay corpora и временные adapters не коммитить. Для synthetic reproducible run — ключевые результаты, exact command, input/output hashes. Goldens, которые читают tests, — в test fixtures, не в reports. Если можно расширить существующий regression — не создавать дубликат.

Изменение semantic/API/recipe/entry point обязательно отражается в authoritative owner и relevant discovery route. Новый агент должен найти normal command, prerequisites, supported population/recipe classes, failure codes и readback без чтения этого чата и истории десятка PR.

## 15. Обязательная финализация среды: удалить, а не «может пригодиться»

### 15.1 Учёт до создания

Заведи **временный operational resource manifest** в sandbox. Это не новый repo registry. До material allocation записывай:

```text
campaign/run ID; kind; exact path/resource ID; created_by_this_run
purpose / named consuming probe; baseline existed-or-not
ownership marker/labels; estimated and actual size
cleanup action; retention reason only when concrete
```

Планируй отдельные case roots; при необходимости — task-scoped cache/image/build resources. Не прячь гигабайты в global cache, который потом нельзя безопасно удалить. Инвентаризация размеров/диска — diagnostics, не permission чистить найденное чужое.

### 15.2 Что сохраняется по умолчанию

**Только** маленькие устойчивые artifacts: исправленный код; минимальные source fixtures/генератор; oracle; точная reproduce command; компактные traces/report/receipts. Они должны пережить удаление больших databases/replays/containers.

Большой artifact сохраняется лишь при конкретной доказанной необходимости: уникальное невоспроизводимое evidence или уже назначенный непосредственный consumer, которому невозможно дать меньший эквивалент. Укажи exact artifact, bytes, consumer, причину невозможности regeneration/minimization, срок/trigger удаления и authority. «Можно переиспользовать», «вдруг вернёмся», «дорого снова скачать» без текущего consumer — недостаточно. Обычный результат — **удаление**.

### 15.3 Safe cleanup procedure

1. Закрой targeted processes/SQLite handles; заверши локальные записи. Сохрани минимальное evidence и hashes. Для stateful failure сохрани нужное доказательство до удаления, а не после.
2. Докажи воспроизводимость из compact retained assets в fresh disposable root. Не маскируй зависимость от удаляемой базы/cached answers. После прогона этот второй root тоже входит в cleanup.
3. Удали только manifest-owned paths. Перед удалением проверь realpath, marker, отсутствие symlink/reparse escape, отсутствие совпадения с repo/home/root/production/чужим checkout и отсутствие неожиданного shared use. Несовпадение — stop только destructive cleanup, не «угадывание» цели.
4. Если Docker действительно использовался: останови/удали только exact созданные containers, volumes и networks по IDs/labels; task-specific image/builder/cache — только если доказано отсутствие pre-existing/shared consumers. Не трогай external volumes и shared baseline layers.
5. Удали созданные transient fixtures, temporary instrumentation, bulk logs/replays, DB-копии, virtualenv/cache только этой campaign, если они не нужны текущей delivery. Не удаляй task branch, сохранённые commits, основной checkout или чужие env. Рабочая ветка сохраняется по policy.
6. После удаления bulk повтори compact reproduction в новом disposable root без старой БД/cached answers; удали и этот root. Выполни post-cleanup readback: оставшиеся processes/containers/volumes/paths, итоговые bytes, non-target fingerprints и Git dirty state. Ожидаются только намеренные product changes/retained evidence, никаких забытых mocks/patches.

**Запрещены:** `docker system prune -a`, `docker volume prune`, общий `git clean -fdx`, broad `rm -rf` по предполагаемому parent, ручное удаление глобальной Docker/WSL storage, удаление чужих backups или единственного forensic evidence. Полезность cleanup не отменяет ownership boundary.

На Windows/Docker Desktop логическое освобождение Docker data и уменьшение физического VHDX — разные результаты. Не обещай второй из первого и не запускай compaction/reset глобальной среды без отдельного разрешения. Укажи оба наблюдаемых состояния, если различие material.

### 15.4 Cleanup evidence

```text
created resources → peak/actual usage → deleted resources
retained: exact file/resource + size + justified immediate consumer
unexpected leftovers: none / exact blocker
non-target preservation: evidence
reproduction after bulk deletion: command + result
final cleanup status: CLEAN / justified retention / blocked
```

Cleanup обязателен и при неудаче campaign: минимальное evidence сохранить, ненужный bulk убрать. Если происхождение ресурса не доказано, не удалять его и не заявлять CLEAN. Укажи exact ownership gap. Не оставляй cleanup «следующему агенту» как необязательную рекомендацию.

## 16. Delivery, rollback и незавершённая работа

### 16.1 Delivery

Existing execution-domain tests брать из `configs/execution_domain_v1.json`; locked toolchain, targeted changed-behavior/direct-consumer checks сначала. Whole-chain команда в итоге должна быть точной и проверенной: entry point, selector, inputs. Flags не угадывать — сверить `--help`. При недостатке runner допустим компактный reproducible probe, не framework. [G15]

Exact task contract, reviews, bind, push/PR, CI и merge — по base-bound harness [G01, G18]. Не использовать harness-control-only mode для product diff, не расширять control prefixes и не отключать gates. Full-gate owner/exact-candidate reuse сохраняются; stale SHA, hidden skip и reroll не acceptance. Owner phrase — только после exact-head CI и readiness PASS.

### 16.2 Rollback

State/schema changes проверить на disposable upgrade/restore: additive compatibility, поддерживаемый backup, обнаружение несовместимого old code. Code revert не равен data rollback; destructive downgrade запрещён. Рабочие VPS/БД не мигрируются. Будущий deploy требует отдельного gate. История append-only; при drift — обычный replan, не force-push/перепривязка исторического evidence.

### 16.3 Checkpoint

До деградации контекста сохрани: goal/scope/phase; repo/branch/HEAD/base/dirty inventory; canonical owners; facts/hypotheses/unknowns; scenarios и evidence; defects/fixes/pending checks; resource manifest/cleanup; unresolved owner gate; **exact resume command и следующий проверяемый outcome**; prohibited assumptions/non-target assets.

Context reset не даёт новых scientific budget/authority и не требует повторять неизменившийся PASS. Resume — от checkpoint плюс свежий readback, не от памяти агента.

## 17. Финальный ответ исполнителя

Сначала verdict и одно next action. Затем: доказанная offline capability отдельно от delivery/commissioning; карта ordinary path после repair; findings с root cause/before-after/consumers/residuals; scenario results и метрики §13; независимые oracles/review; failures/retries/skips; непроверенные external/scientific/risk-policy вопросы; cleanup bytes и сохранённое; точная reproduce command; head/CI/review state и rollback.

Явно сообщи, был ли normal producer/runner или только engine injection. Уже исправленное не выдавай за новую работу. Required outcome не достигнут — partial с причиной, не список предложений вместо ремонта.

Owner summary — до 10 строк. Компактная итоговая таблица: **область → исходный риск → сделано и доказано → остаток**, четыре области: handoff/population/decisions; execution/positions/recovery; accounting/readback; verification/cleanup.

---

## 18. Источники и происхождение решения

### 18.1 Git evidence

Все G-ссылки относятся к одному authoring commit:

```text
repository: lancerbeta/solana-alpha-lab
ref: d244af69bfd7ddc2850b9e5e5823323956e325c4
permalink prefix:
https://github.com/lancerbeta/solana-alpha-lab/blob/d244af69bfd7ddc2850b9e5e5823323956e325c4/
```

| Ref | Exact path / evidence scope |
|---|---|
| G01 | `AGENTS.md`; `delivery-harness/harness.yaml`; `delivery-harness/project-profile.yaml`; `delivery-harness/context-map.yaml`; `delivery-harness/policies/solana-alpha-lab.md`; read-only прочитаны |
| G02 | `control/owner_attention_gate_v2.yaml`; `.cursor/rules/10-input-routing.mdc`; authority/routing, не permission на конкретный runtime action |
| G03 | `docs/FACTORY_SEMANTIC_MAP.md`; current navigation projection, не roadmap и не health |
| G04 | `docs/contracts/science_to_strategy_handoff_v1.md`; frozen handoff/materialization/provenance contract |
| G05 | `docs/contracts/trading_runtime_policy_v1.md`; sizing/admission/revisions/identity/readback contract |
| G06 | `src/solana_alpha_lab/factory/paper_plane.py`, строки 1–230; module intent, states/sets, no-REAL_FILL guard, Decimal mark helper, SQLite connection entry; не полный code audit |
| G07 | `src/solana_alpha_lab/factory/strategy_runtime.py`; schema dispatch, hashes, normalization и position identity owner |
| G08 | `catalog/schemas/signal_decision_v1.schema.json`; closed current schema |
| G09 | `src/solana_alpha_lab/factory/hfic_research_scope.py`, строки 1–230; selector/coverage/alias/definition owner; не весь module |
| G10 | `docs/contracts/opportunity_episodes_jupiter_v1.md`, прочитанный основной contract excerpt; identities, schedule, admission, release, population/protection boundaries |
| G11 | `src/solana_alpha_lab/factory/unattended_shadow.py`; existing commissioning-only pinned-cohort runner |
| G12 | `docs/contracts/risk_and_economics_v1.md`; scope/evidence/accounting/risk/read-purity semantics |
| G13 | `docs/architecture/PAPER_SHADOW_EXECUTION_INTEGRITY_PRD_SSD_V1.md`, основной excerpt; исторический design/defect map, не доказательство текущей реализации всех A1–A6 |
| G14 | `docs/reports/paper_plane_read_freshness/a1_owner_readout_v1.md`; сохранённый synthetic/offline A4 report и next-scope hints; не новый live readback |
| G15 | `configs/execution_domain_v1.json`; declared source/import/consumer/test inventory |
| G16 | `docs/tasks/EXECUTION_EVIDENCE_SEAM_V1.md`; прочитанный task/contract intent и DoD; историческое task status не используется для выбора работы |
| G17 | Targeted search обнаружил `docs/contracts/data_contract_v1.md`, `schemas/schema_v1.sql`, `src/solana_alpha_lab/contracts/schema_v1.py`; execution-attempt vocabulary; для полного current mapping требуется дочитывание |
| G18 | `.agents/skills/delivery-harness/SKILL.md`; `docs/agent/DELIVERY_HARNESS_PROTOCOL.md` (основной workflow); execution/review/validation/evidence rules |

Git evidence показывает contracts и прочитанные code surfaces. Только исполнитель с local dynamic evidence сможет закрыть реальные scenario verdicts. Material statements из report остаются report-derived, пока не воспроизведены на его candidate.

### 18.2 Приложенные источники

**S0:** `Вставленный Markdown(9).md` — исходный capability audit prompt. SHA256:
`934699944ca4b7d5e004c3d0c44a3f92f92cb838ef8f7a821f7c279ba79d794c`.

**S1:** `01_PRODUCT_AND_SCIENCE_CONSTITUTION(1).md` — estimand, PIT, lifecycle и non-claims.
**S2:** `02_OWNER_CHAT_EXECUTOR_CONTRACT(1).md` — роли, authority и Vertical Capability Repair Loop.
**S3:** `03_TRUTH_AND_CONTEXT_PROTOCOL(1).md` — truth planes, routing, provenance и freshness.
**S4:** `04_PRODUCTION_AND_EVOLUTION_SYSTEM(1).md` — operability, reconciliation, recovery и economics.
**S5:** `05_BEHAVIORAL_GOLD_CASES(1).md` — поведенческие safety cases.

Эти Sources — stable meaning, не current repo/runtime state. Где их старые примеры или организационная процедура уже изменены, применяется текущий owner scope и соответствующий canonical Git owner, без silent rewrite истории.

### 18.3 Внешние primary references

**E1 — Anthropic, “Demystifying evals for AI agents”, 09.01.2026:** outcome важнее transcript; positive/negative cases; изоляция trials; проверять результат, не единственную предписанную последовательность calls. Не основание вводить eval platform.

```text
https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
```

**E2 — SQLite WAL, проверено 11.10.2026:** read-only WAL зависит от WAL/SHM; main DB bytes недостаточны для current-state proof. Конкретное принятое поведение — G06/G14.

```text
https://www.sqlite.org/wal.html
```

**E3 — Solana retry/confirmation, проверено 11.10.2026:** новая подпись до expiry исходного blockhash может привести к принятию обеих транзакций. Это основание offline uncertain-outcome probes, не разрешение live rebroadcast/sign/send. Future adapter отдельно сверяет актуальные status/finality rules.

```text
https://solana.com/developers/cookbook/transactions/retry
https://solana.com/developers/cookbook/transactions/confirmation
```
