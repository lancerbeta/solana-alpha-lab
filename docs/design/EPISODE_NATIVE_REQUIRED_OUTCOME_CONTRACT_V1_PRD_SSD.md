---
design_id: EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1
version: '1.0'
status: DESIGN_COMPLETE_NOT_EXECUTED
mode: DESIGN
as_of: '2026-10-14'
expected_repository: lancerbeta/solana-alpha-lab
planning_main: dbe491595c7122735a418e67341be5cad9dbf45e
reproducer_product_base: 94b391d658b52035ae88e2da05f1ea25ff17b0f8
origin: SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1_TARGETED_CONTINUATION
recommended_model_effort: SOL_XHIGH
implementation_authority: EXPLICIT_OWNER_EXECUTION_COMMAND_REQUIRED
scientific_authority: NONE
production_runtime_authority: NONE
---

# Native episode outcomes: PRD + SSD одного ремонтного атома

## 0. Решение и результат для владельца

**Исправляем передачу уже сформулированной episode-гипотезы на классификацию выполнимости.** После ремонта система умеет выразить её требуемый outcome, проверить точные источники, часы и покрытие и сохранить объяснимый результат. Она больше не требует переименовать `E14400` в `Y14400`, подставить newborn-выборку или вернуться к менее строгому Spec 1.1.

Рекомендуемое решение: **новый ExperimentSpec 1.4 для ограниченного episode-native `REUSE_ONLY`-маршрута**, отдельная episode-проекция доступности outcomes и подключение к настоящим loader/classifier/HFIC consumers. Версии Spec 1.0–1.3 и их научный смысл не меняются. Новый Spec использует существующий frozen `parameters.temporal_recipe`; ещё одна копия научного query не появляется.

**Конечный результат атома:** легальный synthetic E1800→E14400 recipe проходит настоящий source-bound handoff до сохранённой классификации; испорченные или неполные bindings дают правильный отказ, читаемый после перезапуска. Полный Forge → Science → Trading этим не объявляется выполненным.

Это не ремонт «плохого Critic»: сохранённый `KILL_LOW_INFORMATION_VALUE` остаётся как есть. Не строим chronological validation, не производим qualifying science evidence, не продвигаем стратегию и не повторяем широкую smoke-кампанию.

### Одно решение о смысле, которое принимает owner при запуске

Принять новый versioned **контракт выразимости и readiness**, а не новый научный вопрос:

- episode identity, population, universe/list rules, точки, часы и исходные source hashes сохраняются;
- доступность outcomes определяется на заранее определённой decision-base, без complete-case сокращения;
- `COMPLETE` означает полное metadata-покрытие требуемых outcome cells, не научную достаточность или прибыльность;
- episode-ветка только повторно использует уже опубликованные immutable источники. Новое наблюдение, provider и live-сбор не авторизованы.

Передача исполнителю команды из §15 разрешает именно этот атом. Подготовка этого документа сама по себе не изменила репозиторий и не дала разрешение на merge.

## 1. Основание: что доказано, что предлагается

### 1.1. Подтверждённое в прочитанном Git

Planning snapshot — `dbe491595c7122735a418e67341be5cad9dbf45e`, содержащий merge PR #402. Original failing product snapshot — `94b391d658b52035ae88e2da05f1ea25ff17b0f8`. При старте исполнитель проверяет фактический `main`; эти значения — provenance, не команда откатить checkout.

| Факт | Следствие для ремонта | Источник |
|---|---|---|
| Spec 1.3 принимает в `required_outcomes[].point_id` только `^[XY][0-9]{1,7}$`; whole-spec control проходит, E14400 — нет | Исправление требует versioned schema, не изменения данных или порогов | S02, S03 |
| Его `observation_request` также описывает `TOKEN_MINT`, `x_point/y_points`, polling и scheduling | Добавить `E` в regex недостаточно: нельзя протащить episode под чужим request-контрактом | S02 |
| `experiment_spec.py` и `lane_classifier.py` отдельно выбирают schemas по версии | Закрыть оба входа и прямых consumers; новый файл schema сам по себе не outcome | S04, S05 |
| Projector фиксирует `X300`, `BASE_X_X300_VALID_X_ELIGIBLE_V1`; frozen raw branch всё ещё индексирует по mint и отказывает при повторном mint между releases | Не расширять raw projector неявной episode-интерпретацией; сохранять повторные episodes одного mint | S06 |
| Есть native `resolve_point`, identity/protection owner, scope/membership owner и shared `evaluate_episode_prefix` без будущего outcome | Переиспользовать эти семантические owners; не писать второй evaluator | S07–S09 |
| Native scientific runner использует `parameters.temporal_recipe`, его `spec`, `scientific_identity`, `frozen_input` и manifest bindings | Именно этот recipe связывает новый Spec с существующим научным входом | S06, S10 |
| Зарегистрирован `CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001`: offline, provider calls=0, `promotion_authority=NONE` | Переиспользуем его текущий смысл; не регистрируем «подтверждающий эксперимент» под новым именем | S11 |
| В существующем classifier exact prior run проверяется до raw outcome projection | Для новой episode-ветки current protection и binding checks должны предшествовать и READY, и возврату REPLAY | S05 |

Точный аудит отдельно установил: старые Critic KILL нельзя объяснять отсутствующим OOS-механизмом по несуществующему classifier receipt. Новый actual candidate завершился научным KILL раньше schema-перехода. **Schema counterexample доказывает необходимое препятствие, но не прохождение Critic.** Не переписывать этот вывод.

### 1.2. Проектные решения этого документа

Новый Spec 1.4, форма его reuse-запроса, episode projection и acceptance matrix ниже — **предлагаемое изменение**, а не описание уже существующей реализации. Локальные новые имена error codes и размещение helper могут быть уточнены исполнителем в пределах эквивалентного контракта.

Не установлены и не обещаются: accepted chronological producer/consumer для этого estimand, scientific acceptance текущей гипотезы, действительная market PIT-готовность, работа live collector, blind Actor, strategy activation. Нет необходимости разрешать эти вопросы для данного атома.

## 2. Цель, consumers, границы

### Desired capability

> Fresh native episode candidate с точным frozen recipe можно передать штатному классификатору с explicit required outcomes. Проверка использует только принадлежащие recipe источники, сохраняет episode identity и decision-base, не читает будущие численные результаты и возвращает проверяемую классификацию либо конкретный blocker.

**Consumers:** Independent Critic / authoring instructions; `validate_experiment_document`; `classify_lane`; HFIC `run_live_classifier` / application of classification / finalize / saved readback; ближайшая граница existing DocumentRunner; будущий источник scientific evidence как читатель явного контракта. Workbench не становится новым truth owner.

**Начало проверяемого пути:** валидный frozen candidate + принадлежащий ему native recipe + immutable released/imported episode inputs. **Конец:** сохранённый classifier receipt с source-bound outcome coverage и fresh-process readback. Сгенерировать эти preconditions можно existing native fixtures; находить гипотезу живой LLM заново не требуется.

### In scope

Версия Spec; native source binding; episode required-outcome interpretation; masks/denominators и coverage; readiness/replay guard; HFIC packet/receipt integration; необходимая совместимость прямого runner handoff без запуска эксперимента; authoring/navigation propagation; один компактный vertical proof и локальные негативные вариации.

### Non-goals

Новые коллекции/расписания/точки; X/Y→E translation; новая population или evaluation horizon; OOS scorer, bootstrap, statistical tests и подтверждающий protocol; изменения scientific thresholds, selection policy, risk, trial budgets; новый DSL/registry capability; revival старых KILL; strategy/activation/PAPER; UI redesign; blind-agent infrastructure; исправление всех findings обоих аудитов.

**Почему NOW:** препятствие точно воспроизводится и блокирует необходимый episode handoff независимо от количества созревших данных. **WATCH:** после proof этого атома проверить accepted chronological continuation того же estimand. Не начинать WATCH внутри ремонта.

## 3. Архитектурное решение и альтернативы

| Подход | Решение |
|---|---|
| Расширить regex Spec 1.3 до X/Y/E | Отклонён: меняет старый contract, оставляет чужую population/request и raw projector |
| Продолжать через Spec 1.1 | Отклонён для нового strict path: воспроизводит artifact-route без требуемого explicit outcome-контракта |
| Spec 1.4 + native reuse branch + shared episode semantics | **Выбран:** version-isolated изменение, без новой экспериментальной платформы |

### 3.1. Новая версия без миграции старой истины

Создать `catalog/schemas/experiment_spec_v1_4.schema.json`. Старые schemas, fixtures, canonical hashes, completed sessions и receipts не переинтерпретировать. Spec 1.4 в этом атоме поддерживает только:

- `population=OPPORTUNITY_EPISODES`;
- уже поддержанный frozen temporal recipe с query 1.2;
- существующий `CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001` в его текущем offline research-artifact значении;
- explicit `required_outcomes` и `REUSE_ONLY / EXPLORATORY_REUSE`;
- provider call budget=0; без разрешения на сбор, confirmation или promotion.

Другие сочетания не пробовать угадать и не направлять в legacy fallback. Typed unsupported/invalid outcome предпочтительнее ложного READY. Spec 1.1 со старым episode recipe остаётся читаемым по прежним правилам; не выполнять auto-upgrade сохранённого документа.

Version number `1.4` относится к **ExperimentSpec**, не к Critic packet, query или HFIC search identity. Их версии не повышать «для симметрии».

### 3.2. Один authoritative recipe, минимум новых полей

В Spec 1.4 сохранить существующий верхнеуровневый научный envelope и `data_bindings`. Native recipe остаётся в `parameters.temporal_recipe`:

- `recipe.spec` — canonical query и scientific meaning;
- `recipe.scientific_identity` — существующая идентичность query;
- `recipe.frozen_input` — exact source closure, не указатель на «текущий корпус»;
- `data_bindings` — manifests и fingerprints, проверяемые штатным resolver.

Минимальный episode reuse-request **не копирует** поля legacy scheduler. Рекомендуемая форма:

```yaml
# Фрагмент новой версии, не полный runnable ExperimentSpec.
schema: smial.experiment-spec
schema_version: '1.4'
population: OPPORTUNITY_EPISODES
capability_id: CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001
observation_request:
  collection_mode: REUSE_ONLY
  requested_evidence_role: EXPLORATORY_REUSE
required_outcomes:
  - point_id: E14400
    field_ids: [FIELD-USD-PRICE-001]
    role: PRIMARY
# parameters.temporal_recipe и data_bindings берутся из native producer;
# все остальные обязательные поля envelope сохраняются.
```

Источник request однозначно определяется frozen recipe и его bindings. Не дублировать список releases, query, clocks или selection rules в ещё одном вручную согласуемом объекте. Если существующий loader требует отдельный discriminator, добавить только discriminator, не новую копию истины.

`observation_request` новой версии — **повторное использование точных источников**, не новый observation schedule. Он не вызывает старый X/Y schedule compiler и не включает фиктивные `source_poll`, `x_point`, TOKEN_MINT или budgets провайдера. Научное расписание читается из проверенного source artifact каждой release.

Практически допустима self-contained schema по текущему repository-паттерну. Не строить общий schema generator, новую dependency или сеть `$ref` только ради одной версии. Все schema refs разрешаются локально.

### 3.3. Строгая нормализация outcomes

Shape проверяется schema; смысл — native semantic owner. Regex `E…` не является allowlist: точку проверяет `opportunity_episodes` под конкретным schedule contract. `E000300`, неизвестный offset, X/Y, неподдержанный field и неверное сочетание version/population отказываются.

Flattened ключ outcome: `(point_id, field_id)`, с отдельной PRIMARY/AUXILIARY ролью. Дубликат с конфликтующей ролью — invalid, а не «первый победил». Нельзя молча пропустить malformed элемент или выкинуть required field при дедупликации.

PRIMARY coverage обязана включать post-decision target dependencies frozen recipe. Для E1800→E14400 нельзя объявить только E1800 или случайный E900 и получить COMPLETE. Decision/reference inputs остаются prefix obligations; их не нужно выдавать за будущий outcome. AUXILIARY принимаются лишь с явной связью с объявленным consumer/recipe; ничего не выводить из свободного текста `question`, `primary_y` или `horizon_notional`.

В атом не входит конструктор новых метрик. На неизвестную форму target — typed unsupported, не реконструкция формулы по названию.

## 4. Source binding и сохранение смысла

### 4.1. Bind до чтения значений

Повторно использовать `bind_frozen_fixed_time_inputs` и существующий evidence resolver, при необходимости выделив минимальную чистую metadata-часть из владельца. Native recipe нельзя копировать в новую альтернативную реализацию binder.

Для каждой реально используемой release проверить:

1. manifest ID/fingerprint и принадлежность native episode collection;
2. exact `(collection, cohort_id, release_id)` и относящиеся к ним census/observations hashes;
3. полный pinned `frozen_input`, canonical query identity и его связь с frozen candidate definition;
4. schedule artifact: byte hash и semantic hash с их различным смыслом; schedule contract, anchor и declared fields;
5. availability cutoff, admissible source role, frozen/current protection и принадлежность источников списков;
6. paths через existing safe resolver, без подстановки абсолютного пути, `..`, symlink/junction escape или live default root.

Проверять содержимое против hash, не только равенство двух строк hash. Две ссылки на разные manifests не становятся связанными от одинакового display label. Входной `outcome_readiness=COMPLETE`, N или projection, присланные пользователем/LLM, не являются evidence.

Связь recipe→manifest должна быть полной. Нельзя подменить один отсутствующий frozen input любым найденным current dataset; нельзя получить READY, проигнорировав часть cohort set.

Не требовать единственного schedule hash на все исторические releases, если native source owner разрешает несколько точных bindings **одного поддержанного контракта**. Каждый episode проверяется против своего schedule. Конфликт источников одного episode — отказ, не выбор «новейшего». Не поддержанные source combinations остаются typed unsupported.

### 4.2. Episode, mint и выборка

`episode_id` — единица решения. `mint` — атрибут актива, который может повториться в другом допустимом цикле. Для источников сохраняется namespace `(collection, cohort_id, release_id)`; идентичные повторы source references дедуплицируются по canonical rules, конфликтующее повторение identity отвергается.

Важная разница с raw projector: **два легальных episodes одного mint не схлопываются в одну строку и не лечат missing outcome друг друга**. Одновременно физически продублированная запись не должна удвоить N.

Не изобретать новую selection policy. Исходная научная семантика принадлежит `hfic_research_scope`, frozen query и действовавшему native universe contract. Текущая более строгая защита данных может запретить использование, но не может молча переписать historical universe/min_holders.

### 4.3. Protection и replay

Проверять frozen source protection и актуальные более строгие ограничения через существующий metadata gate. `DENY_PROTECTED`, `UNRESOLVED_SCOPE`, отсутствующий completeness proof или недоступный источник защиты никогда не превращаются в ALLOW.

**До обоих положительных исходов — READY и REPLAY_AVAILABLE — episode path заново проверяет source integrity и applicable current protection.** Старый cache/receipt/replay key не даёт нового доступа. При появившемся запрете отказывается весь запрошенный frozen scope; не создавать автоматически новую меньшую выборку из «ещё разрешённых» episodes.

Сохранённый исторический результат можно показать как сохранённый результат, если это разрешает его текущая read policy. Это не разрешение снова читать источники или выполнять capability. Cold readback и executable revalidation — разные операции.

## 5. Episode projection: N, masks, clocks и no-look

### 5.1. Что считать

Проекция — производный metadata artifact существующих источников. Это не новый store, не engine scientific sufficiency и не новый scientific evidence kind.

Различать три множества, не называть их все `base_x`:

- **A — admissions:** все committed episodes exact frozen sources. Это исходный population denominator; capture floor, позднее исчезновение или плохой outcome задним числом его не меняют.
- **D — decision base:** episodes, которые по native frozen universe/list coverage и decision-prefix semantics доступны для решения. A\D сохраняется с причинами и counts.
- **M/C — matched/comparator:** masks той же D по существующему query. Comparator определяется заданным contrast; при `MATCHED_VS_DECISION_ELIGIBLE` M и C могут пересекаться. Не вводить универсальную проверку их непересечения.

Outcome coverage для required cells считается **на фиксированной D до outcome missingness**, отдельно можно показать M/C. Это не значит, что every admission eligible. Это значит, что eligibility не выбирается по будущим результатам.

UNKNOWN/INVALID membership не становится FALSE. Если unresolved membership мешает доказать D, readiness блокируется; reported known counts не подменяют полный N. На пустой D или неизвестной D COMPLETE недостижим. Требования достаточности и ограничения native политики остаются прежними; новый произвольный `min_n` не добавлять.

### 5.2. Prefix reuse без второго evaluator

Для LIST_CONTRAST использовать canonical list definitions/masks, decision eligibility и observed decision PRICE. Для MIXED_LIST_NUMERIC/NUMERIC_IN_SCOPE — те же native feature/predicate semantics. Минимум доказательства включает LIST_CONTRAST и одну допустимую numeric-in-scope вариацию; поддержка не должна исчезнуть из-за отсутствия numeric `features` у list-only query.

Переиспользовать `evaluate_episode_prefix`, `episode_decision_price` и `hfic_research_scope`, сохранив полный набор native universe gates. Один вызов prefix helper сам по себе не доказывает, что внешний universe-policy gate был пройден.

Если native pipeline уже имеет source-bound decision masks, читать/проверять их. Если они только transient, допустимо выделить shared pure prefix-selection helper и передать его output projector. Нельзя для получения masks запускать целиком `execute_temporal_discovery`, а затем выбросить численные outcomes.

Prefix numeric reads разрешены **только там, где они необходимы для существующей decision eligibility/predicates**, после metadata protection, в точных разрешённых cells до decision cutoff. Это не новый научный look или повтор MAIN. Outcome projection сама численные targets не читает.

### 5.3. Часы не взаимозаменяемы

У каждого episode T0 — durable `NOMINATION_T0`, а не возраст токена или timestamp импорта. Для каждой точки используется `resolve_point(schedule_binding, T0, point)` с настоящими nominal, assigned, dispatch и availability deadlines. `FIRST_RELIABLE_AVAILABLE_AT` не заменяется nominal time.

Раздельны:

- **decision cutoff** — native deadline decision point, ограничивающий prefix;
- **point deadline** — допустимость конкретного observation;
- **Spec availability_cutoff / as_of** — граница доступности источников для research-read.

У E14400 нормальный outcome позже decision cutoff E1800. Это не leakage: запрещён его **доступ при принятии решения**, а не последующая проверка наличия outcome. Поздний target не лечится соседней точкой; late correction не получает вымышленную раннюю availability. E0 witness использует собственные правила возраста и clocks; его не restamp на T0.

Показательный off-grid пример для текущего schedule: T0=`12:00:07Z`; E1800 nominal=`12:30:07Z`, assigned=`12:35:00Z`, availability deadline=`12:40:00Z`. Тест должен ловить реализацию `T0+1800+300`, которая ошибочно даст `12:35:07Z`. Значения теста проверяются по pinned schedule contract, не копированием тела resolver.

### 5.4. Coverage и readable membership

Для каждого `(point_id, field_id)` required outcome показать минимум `denominator_n`, observed, typed-missing, late/censored, absent, invalid/other — в vocabulary текущего native source owner. Непересекающиеся state counts должны объяснять D полностью. Corrupt/conflicting source — integrity refusal, не обычный missing.

`COMPLETE` только если D доказана, непуста и каждый required cell имеет допустимый native OBSERVED state/clocks. Неполное покрытие → существующий `BLOCKED_DATA` с episode-специфичным reason/next action; не уменьшать D до observed subset. Ready coverage ещё ничего не говорит о независимости выборки, исполнении ордеров, statistical support или CONTINUE/PROMOTE.

**Закрыть ограничение старого membership oracle в пределах нового seam:** предоставить bounded exact membership artifact с episode IDs, relevant masks, reasons и fingerprint. В обычном receipt — counts + immutable ref/hash; в маленьком synthetic fixture можно сохранить весь список. Не печатать тысячи IDs в owner summary и не строить глобальный registry выборок. Старые saved discovery outputs не переписывать.

### 5.5. Доказуемое отсутствие target-value look

Metadata reader выбирает explicit allowlist columns; outcome `typed_value`/численные payloads не материализуются. Нельзя `SELECT *`/загрузить весь результат, удалить value и назвать чтение metadata-only. Не подключать numeric target loader ради проверки status.

Полезно разнести разрешения чтения: metadata всех exact cells; prefix values только точных разрешённых keys; никакого post-decision numeric outcome loader. Библиотека может читать/хешировать opaque bytes файлов — это отдельно от выдачи численных target cells приложению. Не обещать «ноль физических чтений parquet pages» вместо реально проверяемой границы.

В evidence отдельно учитывать `prefix_value_cells_read`, `target_value_cells_materialized`, `outcome_evaluations`, `new_scientific_looks`. Ожидание для нового classify/projection path: последние три равны 0. Счётчик, который сама функция выставила в 0, недостаточен: нужен reader trace/spy и canary из §10.

## 6. Продуктовая связность, сохранение и fail-closed

### 6.1. Один путь, а не новая зелёная боковая команда

```text
frozen candidate + native temporal_recipe + exact released source
    → ExperimentSpec 1.4 loader / semantic validation
    → evidence + schedule + protection binding
    → native scope / decision-prefix masks
    → episode required-outcome metadata projection
    → existing capability/lane checks
    → HFIC authoritative classification + persisted receipt
    → fresh-process saved readback
```

JSON schema, private helper и отдельный happy unit test не закрывают атом без HFIC consumer. B5 offline classifier — только hint; authoritative HFIC path должен принять тот же Spec и корректно сохранить результат без зависшего `AWAITING_CLASSIFICATION`.

Новый branch не обходит capability status, effect class, allowed output zone, parameter/schema identity, implementation hashes, frozen definition/PIT feature gates, budget и authority. `required_feature_ids=[]` у capability-only recipe не означает, что все источники PIT_READY.

### 6.2. Что сохраняет receipt

Использовать existing classifier/session receipt и storage owner. При необходимости добавить optional **versioned episode outcome binding**; один producer, human/machine views производные. Не расширять старые receipt hashes неявным `null` полем: absent new field у legacy остаётся прежней сериализацией.

Необходимая информация, размещение адаптируется к существующему owner:

```text
contract/version + ExperimentSpec canonical identity
frozen candidate definition + native recipe scientific identity
exact source closure and schedule bindings
population/anchor/time contract + scope/universe rule identity
A/D/M/C counts, membership ref/hash and unresolved counts
required cell coverage + readiness + reason_codes + next_action
current protection fingerprint used for this evaluation
value-read scope and explicit non-claims
```

Не вводить вручную другую canonicalization. YAML byte hash, ExperimentSpec canonical hash, query scientific hash и source content hash имеют разные meanings. Все сравнения используют соответствующий существующий hash owner; перенос root не меняет semantic identity.

`PASS_FAST_LANE_READY` / `REPLAY_AVAILABLE` означает готовность существующего reusable artifact-route, **не принятую chronological validation**. Новый result не устанавливает научные обязательства `PRESENT`, не создаёт scientific `PROMOTE`, `StrategyVersion`, activation и не меняет `KILL_LOW_INFORMATION_VALUE` старой сессии.

### 6.3. Idempotency и восстановление

Повтор exact successful classification не создаёт новый scientific trial/решение и читает тот же persisted result по existing transaction identity. Новый процесс восстанавливает результат без MAIN, outcome decode и новой записи.

Не добавлять собственную transaction/lease систему. Existing atomic append и idempotent replay остаются owner. Если финальная запись не подтверждена, статус UNKNOWN/typed write failure, не success-log; resume использует штатный путь. Для этого ремонта достаточно existing persistence tests и одного fresh-process readback; отдельная crash-fuzz campaign не нужна.

### 6.4. Прямой runner handoff

Проверить все version branches на непосредственном пути Spec→existing capability dispatch. New 1.4 не должен «случайно сработать» как legacy Spec без проверки outcomes. Native recipe shape/method остаются понятны существующему fixed-time proxy consumer.

В атом входит необходимая узкая schema/dispatch/binding совместимость этого handoff; **не входит запуск численного эксперимента**. Unsupported consumer должен отказать до чтения values и side effects. Не создавать новый runner или дописывать confirmation protocol, чтобы добиться конечного scientific PASS.

## 7. Ошибки и решения классификатора

Использовать существующие terminals; новые granular reasons вводить только для точного actionable различения episode failures. Названия ниже — рекомендуемые локальные коды, не заявление об уже существующих enums.

| Класс входа/состояния | Требуемое поведение | Что запрещено |
|---|---|---|
| Spec shape/version/population/point invalid | `DENY_INVALID_SPEC`, точный field/reason | Fallback в raw/1.1 |
| Exact source отсутствует или ещё недоступен на cutoff | `BLOCKED_DATA`, `RESOLVE_IMMUTABLE_DATA_BINDINGS` либо native equivalent | Подстановка current/latest release |
| Source/manifest/definition/schedule hash противоречит содержимому | Integrity refusal, например `EPISODE_SOURCE_BINDING_CONFLICT` | Missing=0, silent rebind |
| Protection DENY / unresolved / changed to stricter | Native typed refusal до value reads, также на replay | Тихо отфильтровать запрещённые строки |
| UNKNOWN/INVALID list coverage | Actionable scope blocker, counts/reasons сохранены | UNKNOWN→FALSE, красивый меньший N |
| Валидный отсутствующий/late/censored required outcome | `BLOCKED_DATA`, например `EPISODE_OUTCOME_COVERAGE_UNRESOLVED`; D неизменна | COMPLETE на complete cases |
| Required target dependency не объявлена / чужая точка | Invalid/unsupported required-outcome contract | Парсить target из prose |
| Всё metadata покрыто, existing capability допустима | Existing ready/replay terminal + проверенный receipt | Научное acceptance/PROMOTE |
| Capability/method действительно не поддержаны | Existing `CHANGE_LANE_CAPABILITY_GAP` либо typed unsupported | Регистрировать capability/ослаблять gate в этом атоме |

Owner-facing next action — по-русски, machine IDs — канонические. Для missing outcome: «Покрытие E14400 — 19/20; выборка не сокращена. Проверить указанный immutable source; сбор не запускался». Для integrity conflict: «Источник не соответствует frozen fingerprint; повтор на новых данных потребует нового binding». Не писать автоматически «нужно больше данных» при ошибке схемы/identity.

## 8. Реализация: owner map и bounded write set

### 8.1. Основные точки изменения

| Owner / путь | Изменение |
|---|---|
| `catalog/schemas/experiment_spec_v1_4.schema.json` — NEW | Native REUSE_ONLY shape, explicit E outcomes, strict envelope |
| `src/solana_alpha_lab/factory/experiment_spec.py` | Распознавание новой версии без legacy fallback |
| `src/solana_alpha_lab/factory/lane_classifier.py` | Explicit native branch, source-bound projection до ready/replay, existing gates сохранены |
| `src/solana_alpha_lab/factory/hfic_session.py` | Authoritative classify/receipt/readback совместимость новой версии, если требуются изменения |
| `src/solana_alpha_lab/factory/hfic_temporal_discovery.py` | Переиспользование/небольшое выделение frozen binder и prefix semantics, без изменения арифметики |
| Небольшой новый `episode_required_outcomes.py` в том же factory package — рекомендуемое размещение | Только episode binding/projection; не ещё один evaluator/storage layer |
| `src/solana_alpha_lab/factory/document_runner.py`, `run_passport.py`, `data_resolver.py` — условно | Только доказанно необходимая new-version/direct-consumer совместимость; не менять legacy meaning/hash algorithm |
| Relevant strict receipt/schema owners — условно | Additive source-bound episode receipt field, только если существующая схема требует |

`opportunity_episodes.py`, `hfic_research_scope.py`, `live_cohort_schedule_artifact.py`, release owners — преимущественно **reuse**. Допустим минимальный shared read/projection helper внутри найденного owner, если без него consumer вынужден дублировать семантику. Не менять collection policy, point grid, thresholds, membership grammar или protection.

`scientific_eligibility_projection.py` и его config/schema — **legacy semantics protected**. Предпочтительно не менять; допустим явно version-dispatched вызов нового owner, но не E-ветка, замаскированная под `base_x_population`.

### 8.2. Durable propagation в том же атоме

Обновить новые schema/Catalog assets и только реально затронутые generated projections штатным генератором. Existing `AGENTS.md` и owner-attention policy не менять. Task/implementation/evidence pins согласовывать через delivery harness, не вручную расширять control write prefixes.

Нужны точные инструкции для будущего агента:

- `.agents/skills/independent-hypothesis-critic/SKILL.md`: условие выбора Spec 1.3 для legacy и 1.4 для данного native route; запрет auto-upgrade старых packets;
- `.agents/skills/hypothesis-forge/SKILL.md` и `docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`: тот же выбор, source-binding semantics, interpretation of readiness, recovery next action;
- короткий canonical contract `docs/contracts/episode_native_required_outcomes_v1.md` — рекомендуемое новое расположение, либо существующий очевидный owner без дублирующего документа;
- relevant capability metadata/hash pin только при реальном изменении implementation closure по existing policy; capability ID/status/effect/promotion authority не расширять.

Не переписывать аудиты #401/#402, старые recipes и научные decisions «под исправленное поведение». Они остаются historical evidence. Новый repair evidence ссылается на них и показывает закрытие точного blocker.

### 8.3. Свобода исполнителя

Executor сам выбирает названия helpers, объём extraction, dataclass либо mapping, место маленького membership artifact, selective test commands и метод reader instrumentation. Не требуется новая service/DB/CLI, универсальная иерархия обработчиков или разделение каждого слоя на PR.

До продуктовых writes исполнитель выводит **точный** managed write set из этой owner map и current callers, фиксирует его в одном task contract. Перемещённый файл, новый локальный direct caller или сгенерированный Catalog файл — routine binding, не повод спрашивать owner. Смена scientific meaning, новая authority или дополнительный продуктовый outcome — реальная граница и replan.

## 9. Low-level ориентиры

Ниже контрактная последовательность, не готовая реализация и не новые публичные API по умолчанию.

```python
# Existing helpers нужно вызвать, а не повторить их алгоритмы.
def project_episode_required_outcomes(spec, *, repo_root, data_root, as_of):
    validate_native_spec_and_required_cells(spec)
    frozen = bind_exact_native_recipe_and_sources(spec, repo_root, data_root)
    check_frozen_and_current_protection(frozen)  # до любых value readers
    required = resolve_required_cells_from_native_target(spec, frozen)

    # Общие native owners; нет target evaluator / нового научного look.
    masks = resolve_native_decision_masks(frozen, prefix_values_only=True)
    metadata = read_exact_outcome_metadata(frozen, required)
    coverage = count_required_cells(metadata, denominator=masks.decision_base)
    return bind_projection_to_spec_sources_masks_and_protection(
        spec, frozen, masks, coverage
    )
```

Имена placeholder-функций — логические шаги. В реализации связать с настоящими `bind_frozen_fixed_time_inputs`, `resolve_point`, scope owner и prefix owner; не создавать набор wrapper-классов ради соответствия этой записи.

Ключевые технические детали:

**Reader.** Parameterized file/SQL reads, allowlist columns, точные filters по native identity; сначала metadata и protection. Snapshot источников не должен меняться между проверкой hashes и чтением. Переиспользовать existing immutable import/files и readonly snapshot; если во время чтения выявлен drift — typed refusal. Не строить отдельную locking platform.

**Identity.** Проверять spec hash соответствующим canonical owner. Byte hashes расписаний не равны их semantic hashes. При lineage tie не выбирать release по timestamp. Duplicate source с одинаковыми bytes обрабатывается штатно; одна identity с другими bytes — conflict.

**Projection receipt.** Hash включает contract/version, spec/recipe/source identities, required-cell set, masks и applicable protection. Audit timestamp можно хранить вне semantic hash по существующим правилам. Не менять старые hash definitions для удобства нового поля.

**Новый dependency/consumer.** Product code не импортирует `tests/fixtures` или `docs/evidence/probe_metadata.py`. Последний сам объявляет себя evidence-only scanner, не production reader. Его нельзя просто перенести как «готовый безопасный парсер» без проверки контракта. Сначала переиспользовать existing selective Parquet/metadata readers.

**Missingness.** Healthy empty store, unreadable store и zero eligible не равны друг другу. Отсутствующее поле receipt остаётся UNKNOWN/ABSENT, не False и не [].

## 10. Минимально достаточное доказательство

### 10.1. Что не запускаем

Не повторять 300+ token world, 3+1 blind миссии, двухнедельный PAPER sweep или live LLM Critic. Не строить новый Docker image и не создавать ещё одну `.venv`. Existing locked runtime, disposable data root и обычный test runner достаточны.

Проверяется **ремонт handoff**, не способность придумать гипотезу. Для входа в `PASS_TO_CLASSIFICATION` допустим явно scripted schema-valid Critic response через штатную test boundary. Он не является genuine scientific acceptance. Product schema/binder/classifier/storage не мокируются.

### 10.2. Один компактный native fixture

Переиспользовать helpers из `tests/test_hfic_list_aware_vertical_v1.py`, `tests/test_opportunity_episodes_harness_v1.py`, `tests/test_forge_research_flow_reliability_v1.py` и `_bind_experiment` из temporal production runner tests. Не запускать старый audit script целиком: у него отдельная world/history и machine-specific orchestration.

Planning default — **24 admitted episodes**, две легальные cohort/cycle группы; как минимум один mint повторяется в другом разрешённом цикле после окончания прежнего active episode. Число можно уменьшить, если позитивный path остаётся non-vacuous при текущих guards. Не подгонять N или пороги после scientific outcome; научный experiment здесь не исполняется.

Зафиксировать маленькую таблицу oracle **до запуска**. Удобная конфигурация:

- A=24; два episodes имеют известное universe exclusion;
- ещё два не decision-eligible по однозначному native prefix status;
- D=20; LIST_CONTRAST даёт M=10 и eligible-complement C=10;
- у всех D валидный metadata outcome E14400; отдельная вариация оставляет 19/20;
- clocks и commissioning metadata хронологичны; off-grid T0 присутствует;
- typed-missing/late future points вне required horizon не удаляют admission.

Это иллюстрация размерности, не требование менять native policy ради этих чисел. Если actual native contract требует другой cardinality, до proof заполнить новую ручную таблицу с объяснением; исходные eligibility rules не менять.

Production ingress/shape используются по существующим fixture producers. Когда release требует closure всех schedule slots, завершить их в виртуальном времени штатными валидными terminal states. Не ждать дни и не отключать maturity gate.

### 10.3. Один vertical positive witness

1. Воспроизвести существующий whole-spec X/Y control и E-point failure на baseline; записать точную причину. Это дешёвый RED reproducer, не повтор всего аудита.
2. Сформировать новый synthetic native frozen candidate/recipe/source через existing fixture path. Старый KILL candidate не трогать.
3. Создать Spec 1.4 из этого recipe, прогнать настоящий loader, binding/projection и `run_live_classifier`/authoritative classify.
4. Проверить явный ready terminal для поддержанного reuse-route и persisted source-bound coverage/membership. Не принимать только возвращённый `LaneDecision`.
5. Новый процесс читает сохранённую классификацию; inventory/trial counts не растут, новое научное вычисление не запускается.
6. Проверить отсутствие promotion/strategy/runtime writes; shared scientific guard по-прежнему не разрешает promotion на основании одного readiness receipt. Отказ должен объясняться отсутствием qualifying scientific evidence, а не нераспознанной новой версией Spec: schema-only отказ не доказывает этот guard.

Сценарий можно оформить одним integration test с параметром LIST_CONTRAST / одна MIXED_LIST_NUMERIC вариация на том же наборе. Численные параметры prefix заранее фиксированы; target PnL не оценивается.

**Fidelity:** полный путь только внутри объявленной repair boundary. Это не полный lifecycle и не `GENUINE_BLIND` Forge. Если подготовка frozen fixture требует native synthetic discovery look, он выполняется и учитывается отдельно как fixture setup; нулевой счётчик новых looks относится к проверяемому classify/projection/readback пути, не скрывает подготовительную попытку.

### 10.4. Негативные вариации того же fixture

Не создавать отдельную среду для каждой строки; параметризовать minimal counterexamples. Один valid control должен доходить до той же проверяемой границы.

| ID | Вариация | Независимый oracle / необходимый результат |
|---|---|---|
| T1 | 1.3 + E; 1.4 + X/Y, неизвестная E-точка, wrong version/population | Старый отказ сохранён; новая версия не уходит в raw fallback |
| T2 | PRIMARY не содержит фактический E14400 target; duplicate/conflicting role; чужой field | Exact semantic/schema refusal, не silently normalized COMPLETE |
| T3 | Другой definition/query hash, foreign release/manifest, подменённый schedule или path | Integrity/identity refusal до outcome/prefix values где это возможно; нет side effects |
| T4 | Same mint в двух episodes; target есть лишь у одного; conflicting duplicate episode | N не схлопывается; чужой outcome не «лечит» missing; conflicting duplicate отказывает |
| T5 | Один required outcome отсутствует/typed missing/late | D=20 сохраняется, coverage=19/20, не READY. Неполнота вне required horizon не даёт ложный veto |
| T6 | Off-grid T0; wrong anchor/time clock; deadline ± минимальный шаг | Результат по pinned native time contract; observation после decision не попадает в prefix |
| T7 | UNKNOWN/INVALID referenced membership; comparator с разрешённым overlap | Нет UNKNOWN→FALSE или ошибочного запрета overlap; D/M/C соответствуют ручному expected |
| T8 | Frozen ALLOW, current protection DENY/unresolved; также exact replay | Current gate повторно применяется; no value reads; не создаётся уменьшенный scope |
| T9 | Подсунутый COMPLETE projection/N; сохранённый readback + изменившийся source | Caller projection не доверяется; новое действие revalidates; historical view не считается новым READY |
| T10 | Два валидно перепубликованных synthetic worlds различаются только target numeric values | Semantic masks/counts/readiness одинаковы; source hashes могут и должны отличаться; target value-read trace=0 |
| T11 | Повтор exact classification и cold readback; legacy Spec 1.1/1.3 controls | Idempotency, no new look/write на readback; legacy identities/semantics сохранены |

Если одна вариация падает в schema до target gate, она не засчитывает проверку более глубокого protection/identity guard. Для такого guard поправить только входной shape до legal, не отключать upstream validator.

### 10.5. Два дешёвых canary, не новая mutation-платформа

**Membership oracle:** точные expected episode IDs/masks заданы маленькой fixture truth table, независимой от output classifier. Намеренно испорченный один mask/ID в копии readout должен обнаруживаться. Проверки одного aggregate N недостаточно: разные выборки могут иметь одинаковый размер.

**No-look oracle:** recorder/spy на реальном reader boundary контролирует requested columns/keys и вызовы outcome evaluator. Intentional unsafe reader в отдельном test-only canary — например попытка запросить outcome value / полный value result — должен вызвать отказ теста. Одного monkeypatch `execute_temporal_discovery` недостаточно, если target values могли быть загружены раньше.

Дополнительная targeted mutation нужна только если эти проверки не различают реальный material риск. Не запускать массовую мутационку и не гонять все stochastic варианты.

### 10.6. Existing regressions вместо обязательного нового набора на каждый файл

Сначала выбрать уже существующие cases из:

- `tests/test_horizon_eligibility_vertical_slice_v1.py`, `tests/test_scientific_eligibility_projection_v1.py` — legacy raw coverage/identity;
- `tests/test_fast_lane_classifier.py`, `tests/test_observation_fast_lane_routing_closure.py` — existing lane/authority/persistence;
- `tests/test_hfic_temporal_production_runner_v1.py` — frozen recipe binding, no-look и existing artifact-route;
- relevant native list/episode flow tests — фактические masks и clocks.

Рекомендуемое место нового vertical proof — один `tests/test_episode_native_required_outcome_contract_v1.py`; допустимо расширить существующие tests, если это проще. Список выше — карта reuse, не команда прогнать каждую suite целиком при каждой правке.

Executor фиксирует проверенную фактическую команду в handback. Пример синтаксиса для unittest-style repository: `uv run --locked --managed-python python -m unittest tests.test_episode_native_required_outcome_contract_v1`; перед использованием проверить действующий test entry point. Не устанавливать pytest или другой runner только ради примера.

## 11. DoD: закрытие ремонта, не красивый PARTIAL

| Обязательство | Достаточное evidence |
|---|---|
| Выразимость | Whole valid Spec 1.4 с исходным E recipe проходит; legacy schemas не ослаблены |
| Native semantics | Точные source/schedule/definition bindings; episode identity и native clocks; no E↔X/Y translation |
| Denominator | Ручной membership oracle совпадает с native masks; missing outcome не уменьшает D; повторный mint проверен |
| No-look / protection | Реальные reader traces + canary; future outcome materialization/evaluation и new scientific looks=0; current protection применяется на replay |
| Consumer closure | Настоящий authoritative classifier сохраняет ready либо правильный blocked result; cold readback его обнаруживает без новых writes |
| No overclaim | Готовность только reusable artifact-route; no scientific PROMOTE/strategy/activation; старые KILL не переписаны |
| Legacy / direct consumers | Selected protected regressions; новые версии не проваливаются в тихий старый dispatch |
| Durable truth | Новый агент находит правильный Spec и next action через штатные skill/docs/Catalog; exact recipe/hash semantics согласованы |

**Успех атома требует позитивного witness.** Документированный новый downstream blocker после schema patch не равен DONE: либо закончить входящие в этот scope binder/classifier/receipt изменения, либо вернуть `PARTIAL_BLOCKED` с earliest boundary. Scope нельзя постфактум сузить до regex.

Допустимый остаток после PASS: accepted chronological confirmation ещё не установлена, actual hypothesis научно не принята, blind discovery и весь lifecycle не доказаны. Эти остатки не мешают принять именно данный bounded repair.

## 12. Порядок исполнения без искусственных остановок

### P0 — Rebind и reproducer

Прочитать `AGENTS.md` → semantic routes → exact owners; проверить current head/policy, affected caller versions, audit pins и original counterexample. Freeze task/write set, source refs, выбранный новый schema contract и expected test oracle. Повторить только дешёвый failing schema→handoff probe.

Entry: `START` при сохранённой причине; `PATCH` для обычного drift paths/base; `SKIP` лишь если exact current implementation уже закрывает DoD; `REPLAN/BLOCKED` при смене смысла или недоступной authority. Не начинать заново широкое inventory проекта.

### P1 — Один узкий vertical implementation

Добавить new schema, native binding/projection, version dispatch и authoritative consumer. Сначала довести positive path до реального сохранённого receipt, а не собирать отчёт вокруг промежуточного failing wrapper. Использовать минимальную extraction shared owners; identity/clock/evaluator не переписывать.

### P2 — Counterexamples и cold proof

Пройти параметризованные material negatives, independent membership и no-look canaries, fresh-process readback и selected legacy regressions. Исправления внутри согласованного seam делать до его полного DoD; соседние проблемы — отдельно записать, не расширять outcome.

### P3 — Propagation и delivery

Согласовать skill/operator contract, schema/Catalog/generated outputs и компактное evidence. Required review roles: `CODE_REVIEWER`, `GOAL_DOD_CRITIC`, `ARCHITECTURE_CRITIC`, `OWNER_UX_CRITIC` — последнее необходимо из-за меняющихся instructions/reason/next-action/readback для оператора и агента.

Архитектурный review должен назвать, что способно пройти тесты и всё ещё подменить science: mint collapse; outcome-conditioned D; nominal clock вместо availability; forged source hash; stale replay protection; metadata receipt, выданный за scientific evidence.

Далее ordinary harness: exact candidate checks, non-force task branch delivery, CI, machine readiness. Полный gate не повторять на каждый commit. Merge — только exact owner phrase после readiness, затем guarded merge и post-merge readback по действующей policy.

## 13. Safety, stops и rollback

Только isolated synthetic stores, existing locked runtime и local source. No provider/API/RPC/WSS, secrets/grants, purchase, deploy/settings, signer/wallet/transactions, real data runs или production state writes. Ремонт не требует текущего VPS или доступа к накопленным market outcomes.

Не создавать новый Docker image, общий cache, service или зависимости. Использовать один existing environment; footprint только owned test artifacts. Не удалять старые audit environments и evidence под видом cleanup этого атома.

**Stop/replan:** требуется другая population/estimand/clock/policy, изменение native scientific threshold/budget, новый accepted confirmation protocol, новая provider capability, ослабление protection, mutation реальных данных или интеграция соседнего trading outcome. На safe технических шагах внутри declared seam owner approval не запрашивать.

**Rollback:** code/schema/новые docs через ordinary revert; legacy документы не мигрированы и продолжают читаться. Новые synthetic receipts не удалять ради чистой истории; сохранять scope/version. Production deployment не выполняется, DB migration не планируется. Если выбранное решение потребует migration существующих stores, сначала обосновать необходимость и перепланировать, а не расширять атом скрытно.

## 14. Handback и checkpoint

В начале handback — 5–8 строк по-русски: что теперь может сделать оператор; exact repaired path; результат positive/negative proof; что не доказано; один следующий шаг. Далее достаточно:

1. exact base/head, managed write set и проверки;
2. canonical contract/schema refs и actual replay/test command;
3. небольшой machine receipt: source/mask hashes, denominator, required coverage, value-read scope, stored classification/cold readback;
4. residuals, legacy compatibility, rollback, review/CI/readiness state.

Полные repeated logs не коммитить. Хранить compact source recipes и failing/passing evidence, достаточные для воспроизведения. При остановке checkpoint включает objective/scope, head, completed proof, current earliest blocker, remaining tests и точный resume point; не заставлять следующего агента перечитывать переписку.

**Следующий decision после PASS:** отдельный bounded разбор accepted chronological validation producer/consumer для того же native estimand. Не автоматически «запустить кузню» или «запустить торговлю».

## 15. Готовая команда исполнителю

> Выполни `EPISODE_NATIVE_REQUIRED_OUTCOME_CONTRACT_V1` по этому PRD+SSD как один bounded product repair. Принимаю описанный контракт ExperimentSpec 1.4 для native episode `REUSE_ONLY`: сохранить legacy 1.0–1.3, source-bound frozen temporal recipe, episode identity, clocks, masks/denominators и все scientific/authority gates. Разрешены необходимые локальные изменения schema/binder/projector/classifier/HFIC/direct-consumer compatibility, tests и durable navigation в точном task write set; runtime-проверки только на isolated synthetic data. Сначала перепривяжи постановку к текущему Git и воспроизведи исходный отказ. Доведи настоящий handoff до persisted classification и cold readback, проверь существенные counterexamples, membership и no-target-look независимыми oracles. Не ограничивай repair schema-only PASS и не расширяй его в OOS/confirmation, новый capability, strategy или PAPER. Сохранённые KILL и audit history не менять. Технические решения и безопасные зависимые шаги выполняй самостоятельно. Product code не импортирует audit/test helpers. Реальные данные, provider, внешние полномочия, deployment, деньги, destructive cleanup и merge не разрешены. На выходе — проверяемый repair evidence и PR по current delivery harness; точную merge-фразу запросить только после exact-head CI и machine readiness.

## 16. Источники и привязка для следующего агента

Implementation sources и machine counterexample ниже проверялись read-only на planning main `dbe491595c7122735a418e67341be5cad9dbf45e`; source search мог возвращать старый индекс, поэтому material contents перепроверены `fetch_file` на этом exact ref. Tool чтение не является local execution/test result.

Базовый permalink для файлов: `https://github.com/lancerbeta/solana-alpha-lab/blob/dbe491595c7122735a418e67341be5cad9dbf45e/` + указанный путь.

| ID | Exact source / scope |
|---|---|
| S01 | `AGENTS.md`; `docs/FACTORY_SEMANTIC_MAP.md` — authority, routes, delivery |
| S02 | `catalog/schemas/experiment_spec_v1_3.schema.json` — legacy required-outcome и request shape |
| S03 | `docs/evidence/synthetic_lifecycle_targeted_v1/contract-boundary.json`; переданный owner report и `REPAIR_PRD_SSD.md` — original counterexample и границы утверждений |
| S04 | `src/solana_alpha_lab/factory/experiment_spec.py` — document version loader |
| S05 | `src/solana_alpha_lab/factory/lane_classifier.py` — version dispatch, capability gates, existing replay и outcome readiness |
| S06 | `src/solana_alpha_lab/factory/scientific_eligibility_projection.py` — raw X300 semantics, selective metadata reads, existing frozen temporal branch |
| S07 | `src/solana_alpha_lab/factory/opportunity_episodes.py`; `docs/contracts/opportunity_episodes_jupiter_v1.md` — identity, grid, resolver, protection, release |
| S08 | `src/solana_alpha_lab/factory/hfic_research_scope.py` — list semantics и UNKNOWN/INVALID |
| S09 | `src/solana_alpha_lab/factory/hfic_temporal_discovery.py` — canonical query, prefix owner, native recipe |
| S10 | `tests/test_hfic_temporal_production_runner_v1.py::_bind_experiment`; `tests/fixtures/synthetic_lifecycle_targeted_v1/campaign.py` — actual temporal_recipe handoff и native fixture reuse |
| S11 | `configs/experiment_capability_registry_v2.yaml` — existing fixed-time proxy; promotion_authority NONE |
| S12 | `src/solana_alpha_lab/factory/run_passport.py`; `tests/test_horizon_eligibility_vertical_slice_v1.py` — hash/legacy test conventions |
| S13 | `docs/evidence/list_a_confirmation_protocol_freeze_v1/probe_metadata.py` — evidence-only scanner; не production reader |

Stable project constitution/owner contract определяют запреты на усиление readiness до science, mutation без scope и отдельные owner gates. Текущие implementation details и exact task authority остаются у Git. Никакой external benchmark, новая платформа или общая рекомендация не подменяли проверку этого repository seam.
