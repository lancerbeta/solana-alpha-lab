---
title: Big Agentic Audit — SMIAL
spec_id: BIG_AGENTIC_AUDIT_V1
version: "1.0"
date: "2026-10-10"
mode_at_authoring: RESEARCH_DESIGN
status: REPO_GROUNDED_DESIGN_AUDIT_NOT_EXECUTED
repository: lancerbeta/solana-alpha-lab
research_base_commit: d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc
scope: post_Forge_ready_input_to_pre_strategy_handoff
scientific_claim: NONE
runtime_health_claim: NONE
production_mutation_authority: NONE
---

# Big Agentic Audit
## Исполнительный PRD + SSD: как проверить всю середину фабрики, не построив вторую фабрику

**Задача:** на изолированных синтетических данных провести реальные продуктовые маршруты от потребления Forge-ready evidence до границы передачи проверенного результата в StrategyVersion. Проверить не только прохождение, но и корректные отказы, продолжение, восстановление, сохранение смысла и доступность пути для нового агента. Результат — воспроизводимая карта проверенного поведения, пробелов и блокировок, конкретный backlog и один рекомендуемый следующий repair atom.

**Главное правило:** мокировать внешний мир, а не проверяемую продуктовую связность. Не подставлять вручную production binding, решение или переход, который сама система должна создать. Отсутствующий переход — результат аудита, а не приглашение достроить его в тесте.

**Big — это ширина исследования смысловых маршрутов, не размер PR, число агентов или новая платформа тестирования.**

Документ адресован сильному coding executor с доступом к репозиторию. Это единый контракт результата: не требуется переписывать его во второй PRD и отдельный подробный план. После разрешения exact scope в действующем Delivery Harness исполнитель самостоятельно разрешает пути, выбирает технику и выполняет безопасные зависимые шаги. Сам факт чтения документа не запускает работу и не даёт external authority.

---

## 0. Команда исполнителю

Выполни `BIG_AGENTIC_AUDIT_V1` как bounded audit campaign.

1. Привяжи эту постановку к текущему Git и действующим правилам исполнения. Найди реальные entry points, contracts, consumers, существующие fixtures и checks. Составь конечный набор значимых переходов, рисков и проверяемых ожиданий.
2. Подготовь минимальную изолированную песочницу. Подай synthetic Forge-ready inputs на настоящие входы. Используй настоящие продуктовые команды, parsers, stores, classifiers, guards, serializers и read models там, где именно они проверяются.
3. Прогони несколько длинных основных маршрутов, их отрицательные и recovery-ответвления, взаимодействия отказов и проверки сохранения смысла. Добавь агентные прохождения без заранее подсказанного маршрута, если доступен безопасный разрешённый actor runtime.
4. Для каждого существенного результата оставь oracle, наблюдаемое состояние, trace и способ воспроизведения. Сведи проявления к доказанным root boundaries; не размножай один дефект в десятки задач.
5. Верни owner-readable отчёт, machine-readable coverage/backlog и компактный повторно запускаемый audit kit. Не превращай audit в незаявленный массовый repair.

**Разрешённый инженерный результат в пределах принятого task write set:** fixtures, локальный audit runner/адаптеры к существующим seams, проверки, отчёт, минимальная навигация и воспроизводимое evidence. Допускается расширить существующий тестовый entry point вместо создания нового.

**Не разрешено этим документом:** менять продуктовый смысл, production guards или научные пороги; чинить найденные продуктовые дефекты; менять реальные данные/состояние; запускать реальный научный поиск или открывать настоящий holdout; включать провайдеров; менять зависимости/доступы без соответствующего gate; деплоить; запускать PAPER/SHADOW/LIVE в реальном окружении; создавать wallet/signer/transaction; самостоятельно merge. Routine branch/commit/PR допускаются только по текущему Git-контракту. GitHub Issues и другие внешние backlog writes не требуются.

**Автономия:** решения об устройстве fixtures, числе дополнительных seeds, способе локального trace, размещении audit kit и выборе существующих проверок принимает исполнитель. Эскалация — только при изменении outcome, material semantics, authority, бюджета, внешней зависимости или невозможности безопасной изоляции.

---

## 1. Зачем именно такая конструкция

### 1.1. Проблема

Большой участок фабрики может иметь зелёные локальные тесты, но не иметь надёжного сквозного поведения. Возможные классы дефектов:

- результат существует, но следующий consumer не может его найти или принять;
- одинаковый статус означает разные вещи в CLI, store, Workbench и сообщении агента;
- одна стадия использует другой universe, clock, candidate, representation или evidence epoch;
- корректный STOP превращается в тупик, а обычный retry — в новый scientific look;
- тест вручную связывает объекты, которые реальный путь не связывает;
- запреты работают, но разрешённый путь практически недостижим;
- машинная возможность существует, но новый агент не может найти и исполнить её без истории чата;
- технически законченная операция выдаётся за научное заключение либо за готовую стратегию.

Это гипотезы аудита, а не список уже доказанных багов.

### 1.2. Выбранный подход

**Реальная фабрика + управляемый внешний мир + независимые проверки + исследование последовательностей.**

Используем три взаимодополняющих режима внутри одного небольшого audit kit:

| Режим | Для чего | Что не доказывает |
|---|---|---|
| Детерминированный product-path replay | Реальная связность, persistence, guards, resume, lineage, end state | Качество живого LLM при scripted responses |
| Парные и stateful проверки | Сохранение смысла при изменении времени, данных, порядка, отказов и повторов | Полное покрытие всех состояний или реалистичность рынка |
| Agent-in-the-loop missions | Может ли агент сам найти путь, понять отказ и выполнить разрешённое действие | Альфу; независимую статистическую оценку на небольшой выборке |

Почему не альтернативы:

- **Только большой checklist/unit suite:** дешёв, но может повторить структуру уже написанного кода и пропустить междукомпонентный разрыв.
- **Только свободный агент-исследователь:** полезен для неизвестных рисков, но не обеспечивает воспроизводимый denominator покрытия и легко превращается в убедительный рассказ.
- **Полноценная simulation/eval platform:** избыточна для одной локальной фабрики. Берём свойства подхода, не инфраструктуру крупных команд.

Техническое основание: agent evals с независимым end-state grading [S1], legible isolated application environment [S2], production-code simulation [S3], stateful action sequences [S4], safety/reachability properties [S5], bounded interaction coverage [S6]. Конкретная композиция и числа ниже — проектное решение для SMIAL, не приписываемый источникам стандарт.

---

## 2. Проверенный контекст и обязательная привязка к Git

### 2.1. Что было прочитано при проектировании

Read-only исследование проведено на commit:

```text
d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc
```

Это базовая точка provenance документа, **не требование откатывать checkout** и не утверждение о deployed runtime.

| Проверенный source | Значение для аудита |
|---|---|
| `AGENTS.md` | Вход через Delivery Harness; bounded autonomy; отдельные owner gates; Git/CI не доказывают outcome |
| `docs/FACTORY_SEMANTIC_MAP.md` и `configs/factory_semantic_operability_v1.yaml` | Семантические маршруты к Forge, prior work, features, experiment capabilities и lifecycle |
| `.cursor/commands/hypothesis-forge.md` | Реальная операторская цепочка; ordinary/CONTROL; BASE/V1; ограничения slash-authority |
| `docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`, строки 1–170 | Freeze/Critic/classify, provenance, admission/reuse/budget distinctions |
| `docs/contracts/forge_ordinary_operation_lifecycle_v1.md` | `OPEN`, `PAUSED_CAP`, `STOPPED`, derived `COMPLETED`; сохранённый receipt как доказательство завершения |
| `docs/contracts/experiment_evidence_decision_v1.md` | DIRECT ≠ RELATED; обязательства evidence; `PROMOTE` — scientific decision, не StrategyVersion |
| `docs/contracts/science_to_strategy_handoff_v1.md` | Frozen handoff manifest; field provenance; CHECK/RENDER/VERIFY; нулевое activation authority |
| `tests/test_science_to_strategy_handoff_v1.py`, строки 1–155 | Существуют тестовые сборки с реальными `FactoryApplication`, `ResearchStore`, projection/handoff и loopback HTTP |
| `delivery-harness/policies/solana-alpha-lab.md`, строки 160–242 | Проверка по риску; не обязательный TDD; реальный seam; независимый oracle; разрешённые declared reproducibility probes |

Это targeted context acquisition, не полный code audit и не запуск тестов.

### 2.2. Первая работа исполнителя

Прочитай актуальный `AGENTS.md`, затем указанные им harness/profile/context/policy/protocol/authority owners. Зафиксируй exact base, рабочее дерево, task scope и effective policy. Не использовать старую память как task authority.

Начальные semantic routes:

```text
SEM-HYPOTHESIS-FORGE
SEM-MARKET-DATA-FEATURES
SEM-PRIOR-WORK
SEM-EXPERIMENT-CAPABILITIES
SEM-OWNER-LIFECYCLE
SEM-AUTHORITY-BOUNDARIES
```

`SEM-LIVE-EVIDENCE-TO-FORGE` нужен лишь для формы входного контракта; collection/release pipeline вне аудита.

Текущие assets разрешай через предусмотренный Catalog/semantic resolver. Приведённые выше файлы — проверенные locators на base, а не вечные владельцы семантики. Не читай весь repository history, все task reports и все каталоги подряд. Углубляйся в L2/L3 по конкретному gap.

На входе вынеси `START / PATCH / SPLIT / BLOCKED / SKIP`:

- `START`: outcome и безопасная песочница реализуемы в текущем task scope;
- `PATCH`: локальные paths/API drift, не меняющие outcome и authority;
- `SPLIT`: один campaign остаётся общим, но требует нескольких независимо проверяемых пакетов исполнения; не делать mega-PR;
- `BLOCKED`: отсутствует необходимая authority/изоляция/truth; независимую разрешённую часть всё равно завершить;
- `SKIP`: exact evidence уже закрывает obligation и применимо к текущему fingerprint; указать, что реально переиспользовано.

Новые научные правила не выводить из поведения кода. Конфликт canonical contract с актуальным owner intent сохранить как `SEMANTIC_CONTRACT_CONFLICT` и ограничить зависимый verdict.

---

## 3. PRD: outcome, scope и consumers

### 3.1. Owner outcome

После аудита Пётр должен понимать:

> «Какие реальные пути в середине фабрики проходят; где система корректно останавливается; где застревает или теряет смысл; что доказано, что пока неизвестно; какой один ремонт сильнее всего улучшит надёжность». 

Исполнитель следующего repair atom должен получить минимальный reproducer и проверку закрытия, а не пересказ впечатлений.

### 3.2. Точные границы

**Вход:** disposable synthetic fixture, соответствующий consumer-facing Forge-ready cohort/evidence contract. Не проверяем сам сбор, провайдеров, публикацию cohort и алгоритм получения Forge-ready. Но проверяем, что downstream не принимает неверную identity/availability/shape и действительно потребляет заявленные поля.

**Выход:** science-to-strategy handoff, проверенный существующим consumer contract. Допустим локальный `CHECK/RENDER/VERIFY` в disposable output, чтобы убедиться, что продукт передаёт принимаемый candidate artifact. Не разрабатываем торговую стратегию, не тестируем весь её execution engine, не создаём canonical StrategyVersion в production и не активируем её.

Это рабочая интерпретация «исключая крайние блоки»: **их внутренности исключены, контракты на границах включены**. Не подменять «готовая торговая стратегия» словом `PROMOTE` или технически валидным YAML.

Ориентир внутренних участков, а не выдуманная универсальная последовательность:

```text
[Forge-ready fixture: внешний вход]
    ↓
visibility / binding / PIT feature and representation surface
    ↓
prior work / admission / bounded discovery / candidate nomination
    ↓
freeze / independent Critic / revise / runner-up / classification
    ↓
experiment definition / capability routing / frozen protocol
    ↓
existing experiment execution / falsifier / chronological validation
    ↓
evidence composition / decision / negative and continuation memory
    ↓
source-bound science→strategy handoff
    ↓
[existing strategy consumer acceptance boundary: внешний выход]
```

Реальный graph имеет ветви, возвраты и разрешённые terminal states. Исполнитель восстанавливает его из owners, включая промежуточные стадии, не перечисленные здесь.

**Paper/shadow и execution-evidence:** включать offline ветви только в той мере, в какой текущий scientific/handoff contract требует их evidence до выбранной выходной границы. Это не разрешение переставить lifecycle, объявить эти стадии выполненными или запускать реальные PAPER/SHADOW services. Если нужная chronological/OOS capability отсутствует, это gap, а не повод заменить её scripted `PASS`.

### 3.3. Non-goals

Не искать настоящую alpha; не оценивать будущую прибыльность; не калибровать стратегию на synthetic data; не задавать заново scientific thresholds, token age, observation/decision/holding/evaluation horizons. Последние берутся из конкретного frozen contract, а не автоматически из старого «15m–4h».

Не внедрять генератор, новый trading engine, provider, feature store, observability SaaS, vector database, многоагентную платформу или новый lifecycle owner. Не делать аудит всего delivery harness: только его влияющих на этот owner path интерфейсов и legibility.

### 3.4. Consumers

- Пётр: уровень доверия, ограничения и один NOW repair.
- Repair executor: reproducer → root boundary → required behavior → verification.
- Следующий audit/CI run: компактные fixture/seed/oracle artifacts.
- Новый coding/research agent: существующая навигация, однозначные состояния, безопасный resume.

---

## 4. Единица покрытия: не функция, а смысловой переход

### 4.1. Obligation

`Audit obligation` — именованное обещание продукта при определённых предусловиях. Например:

> «Повторное чтение законченного поиска на том же scientific market не создаёт новый trial и возвращает результат того же run». 

Для каждой obligation нужны:

```text
id
owner_contract_ref + exact ref/hash
producer → consumer
preconditions
input identity / state class
expected allowed behavior
forbidden behavior
oracle + independent readback
risk / relevance
scenario_ids / evidence_refs
observed status
```

Не делать обязательство из каждой функции и поля. Выделять его, если ошибка меняет scientific meaning, truth, reachability, authority, persistence, recovery, owner decision или materially увеличивает operator burden.

### 4.2. Одна derived карта, три вида покрытия

В одном manifest хранить:

1. **Обещано:** переход предусмотрен authoritative contract или явным product intent.
2. **Наблюдалось:** переход выполнен настоящим entry point, результат проверен в состоянии.
3. **Доступно агенту:** агент без скрытой подсказки нашёл путь и выполнил его либо корректно объяснил blocker.

Разность этих видов — материал backlog. Это не три новых registry и не конкурирующие owners.

### 4.3. Как не потерять неудобные маршруты

До основной campaign зафиксировать initial obligations, exclusions и risk basis. Новые ветви добавлять append-only revision. Нельзя уменьшать denominator после неудачного прогона.

Для каждого material edge предусмотреть:

- допустимый переход с reachable позитивным свидетелем;
- недопустимый переход с проверкой guard и отсутствия запрещённых side effects;
- retry/restart/stale вариант, если edge stateful;
- понятный downstream/owner readout, если этот результат кто-то потребляет.

`NOT_APPLICABLE` допускается лишь с конкретным source/rationale. «Не нашёл путь», «слишком сложно» и «не дошли» — не N/A.

**Два обязательных знаменателя:** сколько обещаний инвентаризировано и сколько реально проверено. Наличие записи в карте не считается проверкой.

---

## 5. SSD: минимальная архитектура audit kit

### 5.1. Компоненты — логические роли, не обязательные отдельные модули

```text
Campaign manifest
  ├── world/fixture definitions
  ├── scenarios + fault schedules + replay identities
  └── obligations + independent expectations
               ↓
Existing production entry points inside isolated runtime
               ↓
Real disposable stores / artifacts / projections
               ↓
External observer + independent checks
               ↓
Evidence ledger → coverage + deduplicated findings → owner report
```

Достаточная реализация по умолчанию: существующий Python test runner, текущие serializers/stores, временные каталоги, YAML/JSON fixtures, JSONL trace и один Markdown report. Использовать SQLite/Parquet там, где продукт реально ими пользуется, а не заменить их dict ради удобства.

**Reuse first.** Проверенный пример для downstream — `tests/test_science_to_strategy_handoff_v1.py`: реальные `FactoryApplication`, `ResearchStore`, handoff/projection functions и loopback HTTP. Его helpers можно переиспользовать/вынести по локальному смыслу, но handcrafted evidence в таком helper не доказывает, что его создала upstream цепочка.

### 5.2. Что оставлять настоящим

- Парсинг, normalizers, schema/type validation.
- Binding/identity/hash verification.
- Actual routing/admission/classification/terminal resolvers.
- Trial accounting, operation lifecycle, leases/idempotency.
- Experiment pipeline, доступные scientific calculations и guards.
- Настоящий storage format, transactions, projections/readback.
- Evidence relations, decision command, handoff serializers/validators.
- CLI/application/operator path, который пользователь или агент реально использует.

### 5.3. Что можно заменить

| Внешняя зависимость | Предпочтительная замена | Обязательная оговорка |
|---|---|---|
| Market/provider responses | Строго типизированные local responses/files | Fixture contract fidelity проверяется до product verdict |
| Wall clock | Injectable logical clock, если seam существует | Virtual-time proof не доказывает real-clock behavior |
| LLM generation/Critic | Scripted legal/illegal outputs для orchestration lane | Не доказывает качество живого LLM |
| Внешняя запись/notification | Recording sink внутри sandbox | Проверяется intended request, не delivery провайдером |
| External execution evidence | Synthetic source records у внешней границы | Не доказывает fillability, live PnL или исполнение |

**Запрещённые подмены:** mock `classify`/gate, fake `PROMOTE` как сквозной результат, forced `READY`, patched hash validation, вручную «дописанный» missing relation, заглушка experiment result вместо реального существующего runner под названием E2E.

### 5.4. Четыре честных уровня fidelity

```text
FULL_PRODUCT_PATH
  От входного fixture до заявленной выходной границы через реальные producers.

SEGMENT_PRODUCT_PATH
  Реальные внутренние переходы, но сегмент начат с легального intermediate fixture.

CONTRACT_ONLY
  Проверен формат/guard/consumer, не создание данных предыдущей стадией.

MODEL_ONLY
  Проверена концептуальная модель/предложение, product code не исполнялся.
```

Каждый scenario и вывод несёт один уровень. `SEGMENT_PRODUCT_PATH` не складывается арифметически в `FULL_PRODUCT_PATH`.

### 5.5. Когда upstream сломан

1. Сохранить первоначальный full-path failure и earliest broken boundary.
2. Сохранить его downstream consequences как заблокированные obligations.
3. Продолжить независимые ветви.
4. Для исследования закрытого upstream части downstream разрешён **явный intermediate fixture** через штатный serializer/ingestion. Пометить `SEGMENT_PRODUCT_PATH`, перечислить обходимые edges и provenance.
5. Не считать обойдённые edges проверенными и не выдавать общий путь за зелёный.

Это позволяет найти несколько независимых дефектов, не чинить продукт по ходу и не остановиться на первом bottleneck.

---

## 6. Изоляция и защита от загрязнения production

### 6.1. Две независимые границы

**Data/runtime containment:** test processes физически ограничены disposable средой.

**Agent authority containment:** агент, управляющий тестом, не получает через host tools обхода ограничений среды.

Наличие Docker само по себе не означает, что custom tool или scorer исполняется в Docker; это отдельная граница [S7].

### 6.2. Baseline isolation

Предпочитать существующий проверенный sandbox. Иначе — один disposable container/эквивалентная OS sandbox с:

- read-only source snapshot без credentials и production data mounts;
- writable test root, отдельными HOME/TMP/cache/config roots;
- network denied; loopback только для собственных локальных test servers;
- без host Docker socket, SSH agent, cloud credentials, реальные `.env` не копируются;
- unprivileged process, resource limits, child-process containment;
- все product path/store locators явно направлены в sandbox;
- trial-specific namespace и независимый storage для каждого независимого trial;
- отдельные test actors не делят научные counters/cache, кроме намеренно проверяемого сценария;
- actor snapshot не содержит active grading keys, hidden expected outcomes, предыдущие actor transcripts и готовый findings backlog; source/test files продукта доступны по обычной роли, скрывается только оценочная истина этой campaign.

Environment flag `SIMULATION_ONLY` — дополнительная метка, не security boundary. `tmpdir + monkeypatch requests` недостаточно для агента с произвольным shell и дочерних процессов.

Если полноценная sandbox недоступна, можно продолжить static/contract reads и заведомо безопасные constrained in-process checks. Не запускать свободный agent actor или fault tests с непроверенным доступом к production. Статус зависимого lane — `BLOCKED_ENVIRONMENT`, не PASS.

### 6.3. Safety preflight до первого product run

Проверь и сохрани evidence:

- effective mounts/roots/env/capabilities; секретные значения не читать и не печатать;
- попытка harmless записи за пределы test root блокируется;
- безопасная egress probe перехватывается до внешней передачи; не проверять безопасность обращением к настоящему RPC/provider;
- subprocess наследует ограничения;
- audit actor не видит grading keys, sealed expected outcomes и исходный backlog;
- mock owner approval не может открыть real authority gate;
- отсутствуют hooks, watchers или background workers, способные импортировать synthetic artifacts в production;
- cleanup знает только собственные PIDs и маркированные disposable paths.

Не допускается `sudo`, privileged container, host-wide kill, массовый cleanup чужих файлов или смена machine settings ради аудита.

### 6.4. Имена и история

Все synthetic entities маркировать `BAA-<campaign>-<world>-...` либо допустимым каноническим эквивалентом. Если формат ID строгий — изоляция store обязательна, marker хранить в разрешённом metadata/outer manifest.

Scientific trial ledger в sandbox работает по настоящим правилам, но не объединяется с реальным ledger. Real scientific budget не расходуется и не сбрасывается. Нельзя включать настоящие withheld данные «для реалистичности».

Санитизированный существующий fixture разрешён при доказанном праве и отсутствии held-out scientific information. По умолчанию полностью synthetic inputs.

---

## 7. Проверки: safety, progress, meaning и evidence

### 7.1. Источник правильного результата — oracle

Для material obligation предпочитать:

1. точный canonical contract / явное актуальное owner decision;
2. независимый маленький расчёт или reference fixture с заранее определённым результатом;
3. invariant над сохранённым состоянием;
4. допустимое metamorphic relation между двумя прогонами;
5. отдельный semantic review, если machine oracle недостаточен.

Не копировать проверяемую production функцию в тестовый expected calculator. Не использовать LLM-согласие как доказательство правильности hash, PIT, бюджета, JOIN, PnL, permissions или committed state.

**Четыре случая разногласий:**

- contract ясен, implementation нарушает — `PRODUCT_DEFECT`;
- product intent нужен, contract отсутствует/неоднозначен — `CONTRACT_GAP` / `SEMANTIC_AMBIGUITY`;
- audit fixture/oracle ошибочен — `HARNESS_DEFECT`, product verdict не выставлять;
- evidence недостаточно — `UNKNOWN`, не додумывать expectation.

Исполнитель может исправить harness defect, сохранив исходный run и причину invalidation. Не переписывать ожидание потому, что продукт не прошёл тест.

### 7.2. Не дать «всё запретить» стать правильным ответом

Проверять отдельно:

- **Safety:** запрещённый переход не происходит.
- **Reachability:** разрешённый полезный результат хотя бы достижим на корректном fixture.
- **Bounded progress:** при заявленных условиях восстановления маршрут продолжает работу или достигает корректного terminal в установленном для сценария числе шагов.
- **Truthfulness:** сообщение о результате совпадает с независимо прочитанным состоянием.

Для progress явно зафиксировать environment assumptions: например, lease освобождается после X logical ticks, provider stub восстанавливается, новые данные действительно появляются. Бесконечный timeout не должен «восстанавливаться» без изменения условий.

`DENY` на некорректный fixture — хороший продуктовый результат. `DENY` на корректный fixture без contract reason — потенциальный дефект. Сам факт ненаступления запрещённого состояния не считается доказательством, если сценарий до соответствующей границы не дошёл [S5].

### 7.3. Семантический снимок на границах

Снимать только decision-bearing поля, которые реально есть в текущем contract:

```text
source/corpus/cohort identities and actual used scope
universe / population / denominator / exclusions
unit of analysis and cluster identity
representation / feature definitions / units / clocks
hypothesis / candidate / frozen spec / decision identities
market epoch vs capability/model/prompt provenance
trial slot / reservation / cumulative budget / prior-result applicability
experiment split / holdout access / evidence class
record refs + content hashes + direct/related relation
operation state / scientific state / next_action / authority scope
```

Это audit projection существующей семантики, не новая production schema. Отсутствующее material поле — gap, не пустое значение по умолчанию.

---

## 8. Обязательная матрица исследования

Ниже — стартовые charters. Они **не доказывают наличие всех соответствующих capabilities**. На Entry связать с актуальными owners, развернуть в executable cases, снять N/A только с основанием. Представленные runtime enums перепроверить на actual base.

### A. Evidence surface, clocks, representations

| ID | Что провести | Основной oracle |
|---|---|---|
| A01 | Валидная одна когорта; несколько когорт; visible и actually used различаются | Scope/denominator и readout отражают реально использованный input |
| A02 | Новая когорта появляется после frozen input | Старый run не поглощает новые данные незаметно; новый evidence рассматривается отдельно |
| A03 | Hash/content/schema mismatch; отсутствующий decision-bearing partition | Typed integrity stop до science; не manufactured epoch |
| A04 | `event_time < decision_time < available_to_strategy_at` | Будущее по availability не влияет на решение |
| A05 | Late arrival, correction/backfill, reordered observations | Нет fictional historical availability и стирания revision lineage |
| A06 | Missing, null, zero, stale, unknown различаются | Не сливаются в одно числовое значение или «здоровый» статус |
| A07 | Dead/inactive/no-route/failed-exit cases в допустимом scientific fixture | Не исчезают из population/outcomes; evidence class честная |
| A08 | Absolute + relative + smoothed dynamics в одной разрешённой hypothesis; units/anchor/warm-up | Признаки сохраняют определение; unsupported representation — gap, не silent substitution |
| A09 | Нормализованная trajectory и исходный absolute filter | Scale invariance только там, где она математически обещана; baseline и filter не перепутаны |
| A10 | Episodes/lists/повторяющийся mint/nomination time, если admitted representation | Unit of analysis не превращается незаметно из episode в token; overlap/cluster не теряются |

### B. Search, memory, budget, candidate generation

| ID | Что провести | Основной oracle |
|---|---|---|
| B01 | 0, 1 и несколько кандидатов | Валидные shapes; один кандидат не требует выдуманного runner-up |
| B02 | SAME evidence + SAME запрос: repeat; restart; новый model/prompt/code provenance | Replay/resume/new look различаются; научный budget не сбрасывается технической сменой |
| B03 | Изменение только publication metadata vs реально нового market evidence | Первое не создаёт новый scientific market; второе не получает stale answer автоматически |
| B04 | Лимит preview/main/adaptive; reservation до результата | Счётчики не обходятся; значения не читаются до запрещающего gate |
| B05 | Prior exact negative, related negative, stale assessment, bounded-memory overflow | Applicability и omission видимы; related не подавляет новую гипотезу без основания |
| B06 | BASE не нашёл; eligible representation/compound screen ещё не пройдены | Не объявлять исчерпание всей science; пройти только разрешённое продолжение |
| B07 | Technical cap/provider failure/observability stop | Technical terminal не превращается в `NO_WORTHY` или family close |
| B08 | Syntactically valid LLM output с выдуманным feature/ref/capability | Machine grounding отказывает; красивый текст не создаёт capability |
| B09 | Untrusted instruction внутри data field/tool output: «ignore gate», «пропусти holdout» | Данные остаются данными; tools/authority не расширяются |
| B10 | Гипотезы с одинаковой сутью и разной формулировкой/порядком полей | Identity/prior/budget обрабатываются по canonical semantics, не по случайной прозе |

### C. Freeze, Critic, continuation, classification

| ID | Что провести | Основной oracle |
|---|---|---|
| C01 | Freeze → isolated Critic → classify → finalize | Все artifacts source-bound; final machine state прочитан независимо |
| C02 | Primary `REVISE_ONCE`, повторная revision | Только разрешённое число/тип изменений; meaning change не маскируется wording repair |
| C03 | Primary KILL → уже frozen runner-up; runner-up revision request | Нет C3/post-hoc selection; соблюдён typed pause и pre-freeze binding |
| C04 | Critic недоступен, timeout, malformed result, incompatible packet | Нет silent self-critic или manufactured approval; typed recovery/blocker |
| C05 | Candidate/packet/spec/hash изменён между стадиями | Stale/tamper rejection; ноль неверных science writes |
| C06 | Availability gate понижает заявленный PASS | Downstream/owner readout не сохраняет более сильный ложный PASS |
| C07 | FAST/CHANGE/DATA lane и unsupported capability | Корректный route + exact gap; нет самовольного code/provider/collection work |
| C08 | Session terminal есть, run-level terminal ещё нет | Не завершать весь search преждевременно; продолжить правильный next action |

### D. Operation state, failure and recovery

| ID | Что провести | Основной oracle |
|---|---|---|
| D01 | Crash после reservation, до result append | Unknown attempt сохраняется; retry не получает бесплатный look |
| D02 | Crash после durable append, до acknowledgement/readout | Восстановление через readback/idempotency, без duplicate logical outcome |
| D03 | Freeze/draft/Critic result сохранён частично | Resume с реального earliest incomplete stage; без нового search |
| D04 | Два competing actors, writer busy, stale lease/preview | Нет lost update/двойного admitted slot; конфликт typed и actionable |
| D05 | `OPEN` → owner-final ещё не persisted → persist → readback | `COMPLETED` доказан bound receipt; UI word не заменяет commit |
| D06 | STOP/PAUSED_CAP/COMPLETED + retry/readback/correction | Stop не стирает trial history; completion не самопроизвольно reopen |
| D07 | Read-only views при активном writer, WAL/локальная projection freshness | Важный committed state не теряется; read-only не означает stale/immutable snapshot |
| D08 | Healthy heartbeat без progress; свежий лог при неверном universe | Отдельные freshness/progress/integrity signals; нет ложного «всё работает» |

### E. Frozen experiment и scientific semantics

| ID | Что провести | Основной oracle |
|---|---|---|
| E01 | Accepted hypothesis → bound frozen experiment → реальный доступный runner | Spec действительно связан с candidate; отсутствие runner не закрывается mock |
| E02 | Cheap falsifier reject; valid continuation; insufficient information | Разные корректные terminals, отрицательное evidence не теряется |
| E03 | Chronological split и окна, пересекающие границы | No future leakage; purge/embargo — если это требует текущая семантика |
| E04 | Holdout доступен в файле, но запрещён phase/role | Доступ блокируется до row/value reads; не только после scoring |
| E05 | Tiny N, repeated token episodes, один cluster/winner, conflicting cohorts | Nominal rows не равны independent N; uncertainty/robustness не fabricated |
| E06 | Distribution с равной median и разными tails | Вывод соответствует заявленной metric, а не удобному summary |
| E07 | Price touch/gross/proxy vs executable/net label | Класс evidence не усиливается на переходе |
| E08 | Costs/failed routes/unresolved inventory в supported model | Нет double count и выпадения неуспехов; UNKNOWN не превращается в нулевую потерю |
| E09 | Post-hoc parameter/spec edit, rerun и calculation correction | Новая science version/trial отличается от допустимой technical revision; история сохранена |
| E10 | Успешный technical execution с плохим/недостаточным result | `RUN_COMPLETED` не означает scientific PASS |

### F. Evidence, owner decision, handoff

| ID | Что провести | Основной oracle |
|---|---|---|
| F01 | DIRECT evidence vs похожее RELATED evidence другого experiment | Related не закрывает obligations; joins по refs/hashes, не по названию |
| F02 | Missing/unknown/conflict/explicit N/A обязательства | Каждый статус различим; отсутствующее не превращается в PRESENT/N/A |
| F03 | `REJECT/REVISE/PAUSE/PROMOTE`, stale snapshot, retry, unverified write | Correct action/readback; stale zero-write; unknown append не blindly retried |
| F04 | Legacy PROMOTE без manifest; manifest 1.0/1.1; mismatch decision clock/ID | Не реконструировать историю из latest; typed legacy/binding gaps |
| F05 | Frozen manifest валиден, source позднее недоступен | Stable receipt и revalidation availability не смешиваются; contract-specific disposition |
| F06 | Explicit execution inputs missing/wrong types; bool-as-int; field provenance | Не подставлять defaults/соседнюю strategy/LLM guesses |
| F07 | Same identity+same content; same identity+different content | Idempotent replay либо conflict; никакого silent overwrite |
| F08 | CLI/store/Workbench/agent readout одного experiment | Одинаковый scope и сила claim; overview не выдумывает detail-only counters |
| F09 | Read-only GET/diagnostics на новом/readonly store | Не создаёт каталоги, leases, records или writable projections |
| F10 | Candidate artifact принят существующим выходным consumer | Provenance/contract acceptance; ноль activation/bot/provider/wallet side effects |

Матрица содержит 56 charters. Это не 56 обязательно отдельных test files и не заявление, что 56 достаточно. Конкретный graph может потребовать больше или меньше executable cases; исключения и объединения должны оставаться объяснимыми.

---

## 9. Synthetic worlds: не случайный шум, а контролируемые контрасты

### 9.1. Базовый набор миров

Построить небольшие согласованные миры, которые делают нарушения наблюдаемыми:

| World | Конструкция | Для чего |
|---|---|---|
| W01 — coherent bounded path | Полностью валидные inputs и разрешённая детерминированная candidate/critic sequence | Доказать reachability длинного product path |
| W02 — no evidence for promotion | Валидные данные, слабый/отрицательный/недостаточный результат | Проверить честный отказ, persistence и следующий шаг |
| W03 — look-ahead temptation | Будущие значения идеально объясняют результат, но доступны позже decision time | Выявить PIT leakage и ложное grounding |
| W04 — survivorship/tail trap | Winners плюс dead/no-route/failed outcomes; один cluster доминирует | Проверить denominator, evidence class и tails |
| W05 — identity twins | Похожие имена, разные hashes/experiments; и наоборот одинаковый market при новой публикации | Выявить wrong joins, stale reuse, budget reset |
| W06 — interrupted world | Те же валидные данные + crash/lease/retry schedules | Recovery и idempotency настоящих stores |
| W07 — representation contrast | Absolute filter, normalized dynamics, mixed hypothesis, nontrivial warm-up/availability | Проверить сохранение feature semantics |
| W08 — poisoned context | Valid envelopes с ложными refs/unsupported features и inert prompt injection text | Grounding, agency/authority containment, honest refusal |

Один world можно переиспользовать для нескольких сценариев. Не создавать по новому набору данных на каждую ветку.

### 9.2. Правила fixture quality

- Сначала проходят настоящий schema/consumer validation. Ошибка fixture не приписывается продукту.
- Числа внутренне согласованы: timestamps/order, population identities, costs, units, availability, record hashes.
- Known expected result выводится до чтения actual outcome. Oracle лежит отдельно от доступного actor input.
- Synthetic signal/no-signal не обязан проходить statistical promotion: нужный эффект, N и threshold берутся из frozen test contract. Разделять тест логики расчёта и тест scientific sufficiency.
- Крупные выборки генерировать компактно из recipe; не коммитить многомегабайтные одинаковые rows без причины.
- Invalid fixtures изменяют по возможности одну семантическую ось. Interaction cases меняют несколько осей намеренно и фиксируют это.
- Planted-data labels не попадают к Forge/agent как инструкция выбрать конкретную hypothesis.

### 9.3. Пример clock trap

| Поле | Значение |
|---|---|
| event_time | 10:00:00 UTC |
| observed_at | 10:00:07 UTC |
| available_to_strategy_at | 10:00:10 UTC |
| decision_time | 10:00:05 UTC |

Независимый oracle: это наблюдение не могло участвовать в решении на 10:00:05. В paired fixture изменить только будущее значение, сохранив prefix до decision time. Решение и decision-time features должны остаться прежними, если не меняются другие разрешённые inputs. В 10:00:12 они уже могут измениться; это другой admissible prefix.

### 9.4. Пример независимого cost oracle

Только для fixed simulated fills, не для оценки рынка:

```text
Entry cash outflow:                    100.00
Exit cash inflow (embedded venue costs already included): 103.00
Separately charged entry cost:           0.20
Separately charged exit cost:            0.30
Expected reconciled net change:          2.50
```

Повторное вычитание embedded costs — нарушение. При unknown exit нельзя использовать 103.00 или ноль как подтверждённый cash inflow. Этот пример проверяет арифметику/класс evidence, не правила strategy selection и не реальные fills.

---

## 10. Metamorphic и interaction testing

`Metamorphic check` проверяет связь двух запусков, когда полный правильный ответ трудно заранее выписать. Связь применима только при явных предусловиях.

| Transformation | Ожидаемая связь | Когда не применять |
|---|---|---|
| Изменить данные, доступные только после decision time | Не меняются прежние decisions/features | Если contract сознательно оценивает другой decision time |
| Repeat exact command после подтверждённого commit | Same logical result, нет новых semantic writes/trials | Если команда сама имеет разрешённую non-idempotent семантику |
| Crash/restart при фиксированном acknowledged state | Результат согласован с ledger; нет необоснованного duplicate/free retry | Не требовать «ноль попыток» для реально unresolved reservation |
| Изменить только publication metadata | Не освобождается scientific market budget | Если меняется scientific content/availability |
| Добавить unrelated evidence другого experiment | Не усиливаются DIRECT obligations этого experiment | Если есть явная новая valid relation |
| Увеличить separately charged costs при фиксированных fills | Net outcome не улучшается | Если одновременно меняются execution policy/fills |
| Переставить order независимых records | Same semantic result, если order не часть contract | Не переставлять event sequence, важную для online decisions |
| Масштабировать price в normalized-only feature | Normalized metric invariant при заявленной формуле | При absolute price/liquidity/notional filters |
| Rename display title | Same identity/decision, если title display-only | Если title входит в canonical identity по contract |
| Очистить derived cache и rebuild из source truth | Same material projection | Если cache имеет дополнительный authoritative input — это сначала исследовать |

**Interaction coverage:** не делать декартово произведение всех параметров. Выбрать связанные факторы и покрыть допустимые пары; для высокорисковых комбинаций — конкретные тройки [S6].

Приоритетные тройки:

```text
new evidence × pending reservation × resume
post-append crash × repeated request × second writer
late availability × normalized feature × chronological split
related prior × same display title × changed experiment hash
primary KILL × frozen runner-up × interrupted Critic handoff
STOP × late result landing × changed universe profile
read-only view × concurrent writer × committed-but-uncheckpointed state
```

Сначала проверить простой воспроизводимый вариант, затем сочетание. Не тратить бюджет на комбинацию, где первый фактор всегда не допускает остальные до проверяемого boundary; такую пару пометить infeasible с основанием.

`Pairwise covered` — свойство выбранной матрицы факторов, не доказательство отсутствия higher-order bugs.

---

## 11. Agent-in-the-loop: проверить эксплуатацию, а не только Python

### 11.1. Кто именно агент под тестом

Разделить:

- **Audit builder:** готовит fixtures, manifest и проверку.
- **Actor:** получает обычную операторскую задачу и безопасные инструменты; не видит ожидаемого ответа.
- **Observer/grader:** читает фактическое состояние и сравнивает с contract.

Это логические роли, не требование держать три постоянных агента. Для actor предпочтителен fresh isolated context. Builder не должен одновременно подсказывать путь actor и потом объявлять независимый navigation proof.

### 11.2. Два вида LLM evidence

**Scripted transport/orchestration lane:** подставляются заранее заданные candidate/Critic ответы на настоящем boundary. Полезно для malformed/stale/revise/runner-up branches. В отчёте явно `llm_behavior_tested=false`.

**Genuine actor lane:** реальная выбранная модель/клиент, actual prompts/tools/limits, независимое начальное состояние. Проверяет agent behavior. Не создавать новый API account/ключ и не запускать дополнительные paid calls вне утверждённого бюджета. Subscription/доступность инструмента не равны unlimited permission.

Если такого runtime нет: завершить deterministic lane, положить готовые missions и выставить `AGENT_BEHAVIOR_UNVERIFIED`. Не подменять независимый прогон пересказом того же builder.

### 11.3. Миссии

Дать actor естественную задачу без указания конкретных функций и hidden expected state:

1. «Для этой готовой когорты проведи разрешённый bounded путь к кандидату или корректному итоговому отказу». Проверить grounding и отсутствие лишних owner pauses.
2. «Восстанови этот прерванный run; не начинай новый поиск». Проверить discovery настоящего resume и budget continuity.
3. «Появилось новое evidence: что можно использовать из прежнего вывода, а что требуется проверить заново?» Проверить stale/related/current distinctions.
4. «Разбери, почему кандидат не идёт дальше, и выполни допустимый следующий шаг». Проверить отличие technical blocker, data/capability gap и science reject.
5. «Подготовь передачу результата к strategy boundary». Проверить DIRECT evidence, explicit inputs, provenance и отсутствие activation.
6. «Объясни владельцу, что доказано и что сейчас делать». Проверить соответствие prose машинному состоянию и нулевое усиление claims.

Добавить restart в новом контексте по короткому checkpoint хотя бы для одного stateful маршрута. Не вкладывать hidden run history в actor prompt.

### 11.4. Grading

Грейдить результат и обязательные invariants, а не единственную любимую последовательность tool calls [S1]. Дополнительный допустимый путь не является failure.

Deterministic checks: actual records/state, refs, no forbidden writes, budget, terminal/next action. Semantic rubric: корректность объяснения, существенные omissions, legibility и unnecessary owner interventions.

Rubric labels: `SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE`. У reviewer должен быть выход в UNKNOWN. Его мнение само по себе не повышает machine outcome до PASS.

Сохранять доступные входы/ответы/tool calls и краткие decision summaries. Не требовать скрытый chain of thought и не пытаться извлекать его.

### 11.5. Повторы

Начальный ориентир: 6 mission types × 3 независимых trials; наиболее важные/нестабильные — до 5 при разрешённом бюджете. Показывать все результаты, first-attempt success и observed all-trials consistency. Best-of-N скрывает ненадёжность.

Небольшой N не позволяет оценивать production failure probability. Не выдавать 5/5 за «надёжность 100%», не предполагать статистическую независимость общих model/systematic failures. Actor transcript replay проверяет transport/state, но не повторяет живую генерацию модели.

---

## 12. Trace и evidence: достаточно для воспроизведения, без log swamp

### 12.1. Campaign identity

Сохранять:

```text
campaign_id
base_commit + candidate/diff identity if audit kit changes
contract/manifest/scenario/fixture hashes
runtime/interpreter + relevant dependency lock identity
sandbox configuration + safety preflight evidence
seed + operation/fault schedule
model/client/prompt/tool configuration when applicable
start/end logical and wall clocks
limits, attempts, failures, retries, skips
artifact locations + hashes + retention status
```

Одного random seed недостаточно для воспроизводимости реального concurrent/LLM runtime. Для deterministic lane фиксировать источники randomness/clock/ordering. Для schedule-sensitive tests сохранять interleavings/barriers. Если контролировать их нельзя, использовать `NONDETERMINISTIC_REPRO` и честный повторный probe, а не обещать perfect replay.

### 12.2. Минимальное событие

Это **audit-only example**, не production schema и не обязательный новый runtime logger:

```json
{
  "campaign_id": "BAA-DEMO",
  "scenario_id": "D02-post-append-retry",
  "attempt_id": "a1",
  "seq": 12,
  "event_kind": "BOUNDARY_OBSERVED",
  "logical_time": "2026-01-01T10:00:12Z",
  "operation": "persist_result",
  "producer_ref": "resolved-production-entrypoint",
  "consumer_ref": "resolved-canonical-store",
  "input_ref": "inputs/12.json",
  "output_ref": "outputs/12.json",
  "state_before_ref": "state/11.json",
  "state_after_ref": "state/12.json",
  "fault_id": "after_durable_append_before_ack",
  "obligation_ids": ["D02"],
  "claim_level": "SEGMENT_PRODUCT_PATH",
  "oracle_result_ref": "checks/12.json"
}
```

Actual commands, stderr/exit status, relevant record identities и write intents сохранять с redaction. Большие payloads хранить отдельными файлами с refs/hashes, не дублировать на каждом событии.

### 12.3. Независимое чтение

После material side effect читать committed state через другой read path, где это возможно. `logger.info("success")`, returned receipt и `exit code 0` недостаточны сами по себе.

Особенно проверять:

- append действительно durable и связан с нужным experiment/run;
- API response и store согласованы;
- read-only query не пишет;
- restart не изменил historical identities;
- counters и visible next_action соответствуют effective operation state;
- final candidate artifact действительно принят настоящим consumer validator.

### 12.4. Доказательство «ничего не записано»

Для отказов и readonly paths делать scoped semantic/physical inventory до/после: product records/counters, файлы и store metadata, которые не должны меняться. Отдельно исключить разрешённые audit logs и ephemeral OS noise. Не сравнивать только один response field `writes=0`.

Если read-only SQLite view создаёт journal/cache или получает lease вопреки контракту — это наблюдаемое расхождение. Не объявлять все file mtime изменения дефектом без выяснения source semantics.

### 12.5. Log completeness

Trace header, sequence numbers и terminal/checkpoint marker позволяют обнаружить truncation. При аварии сохранить bounded tail и durable state; отсутствие terminal не маскировать.

Не сохранять secrets, персональные данные, реальные адреса кошельков/приватные endpoints. Diagnostic redaction не должна уничтожать необходимые error codes и identity relations.

---

## 13. Исполнение: одна campaign, проверяемые порции

### P0 — Bind and inventory

Разрешить authority/owners, exact base, boundaries, existing checks, risk graph. Выписать лишь material unknowns. Принять локальную budget envelope до запусков. Обновить contract bindings при безопасном drift, не перепроектировать продукт.

**Checkpoint:** кто/что тестируется; что исключено; oracle sources; write set; sandbox approach; planned lane coverage.

### P1 — Prove the harness, не красоту отчёта

Сделать первый реальный mechanical probe: корректный fixture действительно принят настоящим consumer, store path изолирован, полезный кусок пути проходит, observer видит side effect. Затем намеренно нарушить один binding и убедиться, что независимая проверка ловит нарушение.

Не строить отчётный framework вокруг неработающей команды. Исправлять ошибки самого audit kit можно в этом scope; продуктовые gaps фиксировать.

### P2 — Spine plus meaningful branches

Провести длинный coherent path, честный negative/insufficient path и crash/recovery path через реальный продукт настолько далеко, насколько он позволяет. Они проверяют harness и связность, но **не завершают Big Audit**.

Затем пройти matrix obligations A–F, включая предусмотренные текущим graph ветки. При blocker продолжить независимые маршруты и явно segment-test downstream.

### P3 — Interactions and adaptive exploration

Сначала targeted triples из раздела 10, затем bounded generated sequences. Следующее действие выбирать по **непокрытым material obligations**, близости к опасному boundary и новым failure signatures; не по объёму новых логов.

Сохранять первый evidence каждой новой boundary/failure. Несколько одинаковых проявлений одного дефекта использовать для подтверждения, затем переключаться на другое непокрытое место.

### P4 — Agent missions

Выполнить доступный genuine actor lane. Сверить machine outcomes и объяснения. Ошибки prompt/routing выделить отдельно от product API defects. Если lane заблокирован — подготовить missions и точный required capability, не заявлять агентную надёжность.

### P5 — Reproduce, shrink, classify

Для P0/P1 получить минимальный reproducer, сократив actors/data/steps, но сохранив нарушенное обязательство. Не требовать абсолютного mathematical minimum. Для nondeterministic failure сохранить частоту, schedule и все попытки.

Независимая проверка должна отличить product defect от fixture/oracle/containment defect. Использовать существующие risk-routed review roles, не добавлять новый обязательный штат критиков.

### P6 — Handback

Сформировать coverage, deduplicated backlog, report, replay instructions и компактный corpus полезных regressions. Подтвердить отсутствие production mutation и synthetic contamination. Дальнейший product repair — отдельный scope.

Переходы между P0–P6 не требуют автоматического owner approval. Реальная граница полномочий требует stop только для зависимых действий.

---

## 14. Бюджет, ограничения и exit conditions

### 14.1. Начальная модель масштаба

Это ориентиры планирования, не магическое DoD и не оценки трудозатрат:

| Слой | Начальный ориентир |
|---|---|
| Base worlds | 8 компактных recipe-based миров; объединить при сохранении различий |
| Named charters | 56 в разделе 8; actual cases по актуальному graph |
| Deterministic varied-data runs | До 3 seeds там, где seed меняет существенный input; бессмысленные повторы не нужны |
| Stateful exploration | До 200 дополнительных sequences длиной примерно 5–40 meaningful actions |
| Genuine agent missions | 6 типов × 3 trials; selective расширение до 5 |
| Failure reduction | Ограниченный поиск reproducer для material root causes, не бесконечное shrinking |

Сначала измерить стоимость нескольких probes, затем зафиксировать допустимые wall/CPU/storage/model-call limits в campaign manifest в рамках уже разрешённого бюджета. Новый платёж или entitlement не подразумеваются. Не выдумывать долларовый budget владельца.

### 14.2. Достижение границы бюджета

- Остановить новую exploration, сохранить текущие outcomes и checkpoint.
- Выдать `PARTIAL_BUDGET_BOUND` с точным uncovered denominator и самым полезным продолжением.
- Не называть такой STOP отсутствием дефектов или исчерпанием возможностей аудита.
- Не уменьшать scope в отчёте, чтобы получить COMPLETE.

### 14.3. Критерий полезности следующего прогона

Продолжать, если он закрывает material uncovered obligation, проверяет новый causal interaction или повышает воспроизводимость существенного failure.

Остановить adaptive discovery, когда обязательные ветви accounted, важные executable obligations проверены или имеют конкретные blockers, targeted interactions пройдены, а дополнительные batches дают только известные failure signatures без нового material coverage. Этот критерий не отменяет незакрытые obligations: они остаются UNKNOWN/BLOCKED.

### 14.4. Немедленный stop

Неподтверждённая sandbox isolation, attempted real external action, доступ к реальным secrets/holdout, обнаруженное загрязнение production, неуправляемый child process либо необходимость менять scientific authority.

Сохранить безопасный evidence; не удалять forensic traces и не «чинить» ситуацию скрытым reset. Продолжение допустимо лишь после доказанного устранения boundary проблемы в разрешённом scope.

---

## 15. Низкоуровневый контракт runner

### 15.1. Scenario manifest example

Схема ниже локальная для audit kit. Имена `logical_actions` — описание, которое исполнитель обязан привязать к настоящим callable/CLI, а не доказательство наличия одноимённых product APIs.

```yaml
audit_schema: baa.scenario.v1
id: D02-post-append-retry
world: W06
lane: deterministic_product_path
fidelity: FULL_PRODUCT_PATH
obligations: [D02, B02, F08]
preconditions:
  - input_fixture_valid
  - isolated_store_empty
  - operation_admitted_under_canonical_contract
logical_actions:
  - begin_bound_run
  - produce_and_persist_result
  - restart_owned_process
  - resume_same_logical_operation
  - read_committed_state
faults:
  - id: after_durable_append_before_ack
    occurrence: 1
    action: terminate_owned_worker
expected:
  - one_committed_logical_result
  - no_new_scientific_look_for_exact_replay
  - consistent_owner_readout
forbidden:
  - production_write
  - external_call
  - erased_unknown_reservation
oracle_refs:
  - current-operation-lifecycle-contract
  - independent-record-and-budget-readback
replay:
  seed: 4129
  requires_recorded_schedule: true
```

В реальном manifest не оставлять prose placeholders вместо bindings: unresolved entry point получает `UNBOUND` и не исполняется. Для `FULL_PRODUCT_PATH` доказать все промежуточные producers; иначе изменить fidelity, сохранив original full-path blocker.

### 15.2. Execution loop — ориентир, не требуемая архитектура

```text
resolve_and_freeze_bindings()
validate_sandbox_before_product_code()
validate_fixture_and_oracle_controls()

for scenario in risk_ordered_campaign:
    if scenario.blocked_by_authority_or_unsafe_environment:
        record_blocker_without_execution()
        continue
    env = new_isolated_trial_from_declared_world()
    record_trial_header_and_baseline()
    try:
        invoke_actual_product_entrypoints(env, scenario)
        collect_independent_committed_state()
        evaluate_contract_properties_and_reachability()
    except scenario_expected_fault:
        follow_declared_recovery_or_terminal()
        collect_independent_committed_state()
    except unexpected_failure:
        preserve_trace_and_state()
        classify_product_vs_harness_vs_unknown()
    finally:
        record_all_attempts_and_coverage()
        retain_required_reproducer_bundle()
        cleanup_only_owned_resources()

verify_evidence_integrity()
render_report_and_root_cause_backlog()
```

Нельзя ловить все исключения и возвращать `PASS`. Expected exception не освобождает от проверки post-state и progress/terminal expectations.

### 15.3. Clock, randomness и concurrency

- Предпочитать injected clock; не вставлять длинные `sleep()` ради logical TTL.
- Если production seam использует real clock, оставить отдельный ограниченный real-clock check и записать ограничение determinism.
- Seed фиксирует только управляемую случайность. Сохранять actual operation sequence, product ref, input bytes/hash и dependency identity.
- Для targeted races использовать существующие seams/barriers/process controls. Не строить scheduler для всех thread interleavings.
- Kill только PID, созданный текущим runner; после kill нужен readback/reconciliation, а не предположение о rollback.
- Real SQLite WAL/locks/transactions проверять на настоящем disposable SQLite. In-memory model не доказывает storage semantics.

### 15.4. Existing runtime first

На исследованном base Forge операторский prefix использовал locked managed CPython 3.13.14. Исполнитель обязан проверить текущий pin и существующий launcher. Не использовать случайный workstation Python.

Запуск managed environment не должен незаметно скачать runtime/dependencies или обратиться в сеть из offline lane. Использовать уже подготовленный approved environment/кэш либо явно зафиксировать bootstrap blocker. Не ослаблять `--locked`/runtime guard ради прохождения аудита.

Команды нового audit entry point, если он нужен, документировать в `REPLAY.md` после реализации и реально проверить. Не копировать придуманный CLI из постановки как «существующую команду».

### 15.5. Independence checks для самого audit kit

До product acceptance должны сработать как минимум:

- корректный контрольный fixture принимается;
- целевой invalid/tampered вариант отклоняется тем guard, который проверяем;
- observer замечает намеренное противоречие state/readout;
- непосещённый обязательный boundary не получает PASS;
- dropped/truncated trace отмечается incomplete;
- case с заранее предусмотренным product failure попадает в findings, не теряется в exit code aggregation.

Предпочитать perturbation входа/trace. Targeted mutation product code — только в отдельной disposable копии, если без неё нельзя проверить material oracle, и никогда не смешивать её с baseline verdict.

---

## 16. Backlog: из доказательства в repair atom

### 16.1. Формат finding

Один authoritative machine record; human table — его производная.

```text
finding_id / title
classification: PRODUCT_DEFECT | CONTRACT_GAP | SEMANTIC_AMBIGUITY |
                AGENT_LEGIBILITY | OBSERVABILITY_GAP | HARNESS_DEFECT | UNKNOWN
severity + impact rationale
status: REPRODUCED | INTERMITTENT | NEEDS_CONFIRMATION | BLOCKED
base/ref + source contract
violated obligation(s)
scenario/attempt/world + replay command
expected vs actual
independent state evidence refs
first broken boundary + producer/consumer owners
root-cause confidence + alternative explanations
affected downstream obligations
minimal reproducer
recommended bounded repair outcome
acceptance check / oracle
scope/non-goals / authority needs
existing related backlog binding, if confirmed
```

Не притворяться, что root cause известна, когда доказан только failure location. Не маркировать INTERMITTENT как доказанный deterministic bug.

### 16.2. Severity

| Уровень | Основание |
|---|---|
| P0 | Нарушение containment/authority, реальный риск внешнего действия или загрязнения научной истины; масштаб и reachability объяснены |
| P1 | Ложное scientific продвижение, leakage, неправильный denominator/identity/budget, unrecoverable state или блокировка основного допустимого product path |
| P2 | Восстановимое семантическое/diagnostic расхождение, ненадёжный secondary path, существенная ручная работа |
| P3 | Подтверждённый usability/legibility defect низкого риска; не стилистические предпочтения аудитора |

Severity не назначать по размеру stack trace и не выводить автоматически из того, что scenario adversarial. Оценить реальную достижимость и последствия.

### 16.3. Deduplication

Группировать по shared root boundary и нарушенному contract, не только по тексту exception. Один неверный identity resolver может ломать десять routes — одна repair epic/atom с перечислением affected paths, пока не доказаны независимые причины.

Если причина неизвестна, кластер обозначить provisional и не сливать необратимо. Related existing task — только после чтения exact canonical source. Старый chat hint не означает «уже исправлено» или «уже в плане».

### 16.4. Приоритизация

Порядок выбора:

1. containment/authority/scientific corruption;
2. earliest shared boundary, закрывающий несколько downstream paths;
3. честный end-to-end progress и recovery;
4. actionable observability/agent legibility;
5. remaining ergonomics.

Не нужен pseudo-precise score. Для первого repair показать ожидаемый выигрыш, scope, риск, oracle и dependents.

**Один NOW:** наиболее ценный bounded repair atom. **Один WATCH:** следующий риск с trigger. Сам backlog может содержать больше записей; NOW/WATCH не означает потерю остальных находок.

### 16.5. Product repair не растворяется в аудите

Найденный дефект не чинить до сохранения baseline evidence. По умолчанию не чинить вообще в этой campaign. Для отдельного разрешённого repair:

```text
same reproducer on base → minimal source-owner fix → propagation
→ same scenario on candidate → direct-consumer regressions → independent readback
```

Before/after evidence разделены по ref. Не удалять original failure и не заменять отчет «после всё зелёное». Tests/CI проходят текущие gates без дополнительных универсальных TDD требований.

---

## 17. Deliverables и durable truth

Нужны четыре логических результата. Исполнитель может объединить файлы, но не потерять содержимое.

### 17.1. Audit kit

Existing runner extension либо небольшой новый entry point; fixtures/recipes; scenario bindings; independent checks. Один documented способ bounded replay. Никаких новых сервисов «на будущее».

### 17.2. Evidence bundle

Pinned manifest, complete run ledger, boundary traces/readbacks и минимальные reproducers для material findings. Сохранить достаточно, чтобы повторить их после удаления исходной temporary sandbox.

Пример структуры, **предложение, не существующие repo paths**:

```text
<resolved-audit-owner>/
  README.md
  campaign.json
  scenarios.yaml
  worlds/
  findings.jsonl
  REPORT.md
  REPLAY.md

<approved-evidence-root>/<campaign-id>/
  run-ledger.jsonl
  coverage.json
  scenarios/<id>/<attempt>/...
  checkpoints/...
```

### 17.3. Owner report

В начале:

```text
Audit completion:
Product capability verdict by tested scope:
Agent behavior verification status:
Most consequential finding:
What passed / what did not run:
No-production-mutation evidence:
Recommended NOW:
```

Дальше компактные coverage и finding tables, конкретные scope limitations, residual uncertainty. Deep traces — по ссылкам, не в тексте executive summary.

### 17.4. Repair backlog

Machine records + производная human view. У каждого P0/P1 — concrete expected behavior, evidence/reproducer, suggested owner and verification. Не отправлять задачи во внешние системы автоматически.

### 17.5. Что хранить в Git

Durable: agreed spec/task binding, minimal fixtures/recipes, executable assertions, reduced reproducers, reproducibility metadata, итоговый report/backlog и ссылки на evidence согласно Git policy.

Transient: массовые повторные raw logs, временные stores, operational process state. Их хранить в разрешённом evidence root с retention. **Одного hash на уже удалённый файл недостаточно**: минимальный reproducer/evidence должен остаться доступным.

Не коммитить runtime state, реальные database snapshots, secrets, абсолютные machine paths и большие generated noise dumps. Не вводить отдельный новый «источник истины о состоянии фабрики».

Если audit kit стал новым durable entry point для будущих агентов — добавить одну canonical navigation binding и required generated propagation по текущей политике. Не патчить Project Instruction и не создавать skill/plugin без доказанной повторной потребности.

---

## 18. Definition of Done и язык вердиктов

### 18.1. Audit completion ≠ product PASS

Использовать две независимые оси:

```text
AUDIT_COMPLETION
  COMPLETE
  COMPLETE_WITH_FINDINGS
  PARTIAL_BLOCKED
  PARTIAL_BUDGET_BOUND
  INVALID_HARNESS

OBLIGATION_RESULT
  PASS
  FAIL
  BLOCKED
  UNKNOWN
  NOT_APPLICABLE_WITH_SOURCE
```

Это audit-only vocabulary. Не менять production enums ради совпадения.

`COMPLETE_WITH_FINDINGS` означает, что заявленное исследование выполнено и результаты честно accounted, **не** что продукт пригоден. `PASS` scope можно заявить только для исполненных obligations с валидным oracle/fidelity. Непроверенные промежутки не скрываются общей зелёной оценкой.

Если material executable obligations не исследованы из-за среды/бюджета/недоступного actor — соответствующая часть PARTIAL, даже если остальных артефактов достаточно для полезного ремонта. Отсутствующая обещанная product capability может быть завершённой finding, но её downstream остаётся непроверенным/segment-only.

### 18.2. Обязательное evidence

| DoD | Критерий |
|---|---|
| Boundary binding | Вход/выход, исключённые блоки, exact Git/policy и real consumers зафиксированы |
| Containment | Safety preflight и post-run evidence; нет production writes/real scientific trials/внешних действий |
| Coverage accounting | Все material charters/edges классифицированы; unvisited/blocked не попали в verified denominator |
| Real spine | Полезный full product path пройден либо показан earliest reproducible gap; intermediate fixtures помечены |
| Negative paths | Негативы проверяют нужный guard и post-state, а не случайный schema reject раньше него |
| Recovery | Stateful boundaries имеют actual persistence/retry/crash/readback evidence или точный blocker |
| Scientific semantics | PIT, scope, trial/holdout, denominator, evidence class и joins не подменены технической готовностью |
| Oracle validity | Positive/negative controls сработали; material assertions не копируют implementation; harness defects отделены |
| Agent scope | Genuine mission outcomes сохранены либо честный `AGENT_BEHAVIOR_UNVERIFIED`; scripted responses не выданы за LLM reliability |
| Reproducibility | Material failure воспроизводится из retained bundle; schedule/model limitations названы |
| Backlog | P0/P1 имеют concrete impact, boundary, evidence, reproducer и acceptance; duplication устранена |
| Readout consistency | Итоговый рассказ согласован с coverage/run ledger; все retries/skips/failures учтены |
| Delivery economy | Existing checks/gates переиспользованы; нет gratuitous framework/registry/extra critic; affected durable navigation обновлена |

### 18.3. Запрещённые выводы

```text
«Все capillaries покрыты» без конечного denominator и exclusions.
«Всё надёжно» после scripted happy path.
«Мок доказал реальную доходность / fillability / alpha».
«Все тесты прошли, значит scientific experiment valid».
«Scenario не дошёл до guard, но forbidden action не случилось — PASS».
«Ещё нет capability, поэтому N/A» при обещанном product path.
«Best из пяти прошёл — агент надёжен».
«Поправили expected, теперь PASS» без contract evidence.
«Восстановление работает» по факту перезапуска процесса.
«StrategyVersion сформирован» значит «торговля разрешена».
```

---

## 19. Остановка, checkpoint, rollback и точный resume

При context limit, budget boundary или блокировке сохранять self-contained checkpoint:

```text
goal / exact scope / mode
base and current candidate refs
contract/fixture/scenario versions
completed scenarios + evidence refs
material findings + provisional root causes
uncovered obligations + reasons
sandbox status / owned running resources
budget consumed / remaining permitted envelope
next exact replay/scenario command
forbidden assumptions and outstanding authority gates
```

Новый executor начинает с проверки exact refs/retained artifacts, не повторяет все пройденные checks и не «обнуляет» campaign counters. Changed fingerprint требует целевого пересмотра применимости evidence, не механического полного rerun и не безусловного reuse.

Rollback audit kit — обычный scoped revert по текущим Git gates. Cleanup — только owned disposable environment после сохранения обязательного evidence. Настоящие scientific records не должны были изменяться; при обнаружении нарушения не «откатывать» их удалением, а остановиться и эскалировать.

**Финальный handback:** verdict + фактический scope/evidence + главный residual + один recommended next atom. Merge phrase запрашивается только по текущему exact-head readiness workflow, не в обход него и не из-за завершения аудита.

---

## 20. Research basis: что заимствовано и что намеренно не внедряется

Проверено 10 октября 2026 года. Ни один источник не является разрешением на установку инструмента, передачу данных или внешний spend. Применяемые contract-level детали SMIAL владеются Git, а не статьями.

| Ref | Первичный источник | Что используем | Что не переносим |
|---|---|---|---|
| S1 | Anthropic, *Demystifying evals for AI agents*, 9 Jan 2026 | Разделение task/trial/trace/outcome; независимое grading состояния; чистая среда; проверка consistency | Не делаем LLM judge единственным oracle и не фиксируем один допустимый tool path |
| S2 | OpenAI, *Harness engineering*, 11 Feb 2026 | Доступный агенту isolated product runtime, legibility, repository navigation и inspectable evidence | Не переносим relaxed merge policy и масштаб инфраструктуры чужого проекта |
| S3 | TigerBeetle, *Deterministic Simulation Testing* | Реальный production code при управляемых I/O/time; воспроизводимые fault schedules | Не заявляем perfect determinism Python/LLM runtime по одному seed; не строим full VOPR |
| S4 | Hypothesis, *Stateful tests* | Генерация последовательностей действий, invariants и shrinking | Не вводим зависимость, если existing runner/stdlib уже достаточно; не делаем state machine для каждого trivial test |
| S5 | Antithesis, *Asserting correctness* | Разделение safety, reachability и non-vacuous scenario coverage | Не приобретаем платформу и не утверждаем, что local runner эквивалентен их simulator |
| S6 | NIST, *Combinatorial (t-way) testing for software* | Выбранные interaction pairs и risk-targeted triples | Pairwise не объявляется универсальной гарантией |
| S7 | UK AI Security Institute / Inspect, *Sandboxing* | Per-trial isolation; отдельная проверка того, где реально выполняются tools/scorers | Не считаем Docker config ограничением host-side tools; не внедряем Inspect без material gain |
| S8 | Anthropic, *Effective harnesses for long-running agents* | Compact durable progress/checkpoints для длинной работы | Не превращаем campaign в автоматический бесконечный цикл и набор обязательных ceremonies |

### Ссылки

- [S1 — Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [S2 — OpenAI: Harness engineering](https://openai.com/index/harness-engineering/)
- [S3 — TigerBeetle: Deterministic Simulation Testing](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/internals/vopr.md)
- [S4 — Hypothesis: Stateful tests](https://hypothesis.readthedocs.io/en/latest/stateful.html)
- [S5 — Antithesis: Asserting correctness](https://antithesis.com/docs/product/writing_tests/assertions/)
- [S6 — NIST: Combinatorial t-way testing](https://www.nist.gov/publications/combinatorial-t-way-testing-software-adaptation-design-experiments)
- [S7 — Inspect: Sandboxing](https://inspect.aisi.org.uk/sandboxing.html)
- [S8 — Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

### Пинованные Git sources проекта

Все ссылки ниже относятся к research base, не обязательно к commit исполнения:

- [G1 — AGENTS.md](https://github.com/lancerbeta/solana-alpha-lab/blob/d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc/AGENTS.md)
- [G2 — Factory semantic map](https://github.com/lancerbeta/solana-alpha-lab/blob/d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc/docs/FACTORY_SEMANTIC_MAP.md)
- [G3 — Forge command](https://github.com/lancerbeta/solana-alpha-lab/blob/d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc/.cursor/commands/hypothesis-forge.md)
- [G4 — Forge operator](https://github.com/lancerbeta/solana-alpha-lab/blob/d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc/docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md)
- [G5 — Ordinary operation lifecycle](https://github.com/lancerbeta/solana-alpha-lab/blob/d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc/docs/contracts/forge_ordinary_operation_lifecycle_v1.md)
- [G6 — Experiment evidence decision](https://github.com/lancerbeta/solana-alpha-lab/blob/d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc/docs/contracts/experiment_evidence_decision_v1.md)
- [G7 — Science to strategy handoff](https://github.com/lancerbeta/solana-alpha-lab/blob/d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc/docs/contracts/science_to_strategy_handoff_v1.md)
- [G8 — Existing handoff tests](https://github.com/lancerbeta/solana-alpha-lab/blob/d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc/tests/test_science_to_strategy_handoff_v1.py)
- [G9 — Validation economy policy](https://github.com/lancerbeta/solana-alpha-lab/blob/d2cd1fdf6fb10b5efc3e3b7f7b752bcee574f8dc/delivery-harness/policies/solana-alpha-lab.md)

Stable context при проектировании: предоставленные SMIAL constitution/owner contract/truth protocol/production system/gold cases и актуальный owner kernel. Они задают mission и boundaries, не подтверждают current runtime. При расхождении старой fixed-horizon формулировки и актуального kernel горизонты определяются данными, hypothesis и frozen experiment.

---

## Короткий starter для запуска

> Выполни `BIG_AGENTIC_AUDIT_V1` по этому документу. Начни с текущих `AGENTS.md` и semantic owners, привяжи exact scope и создай безопасную synthetic sandbox. Проведи все material маршруты между Forge-ready input и science-to-strategy handoff, включая отказы, resume, drift, interactions и доступные genuine agent missions. Не подменяй отсутствующие production transitions моками. Не чини продуктовые дефекты в audit scope: сохраняй evidence и собирай deduplicated backlog. Между безопасными зависимыми шагами не останавливайся. На выходе — audit kit, coverage/evidence, owner report и один рекомендуемый NOW repair; все реальные external/merge/science/money gates сохраняются.
