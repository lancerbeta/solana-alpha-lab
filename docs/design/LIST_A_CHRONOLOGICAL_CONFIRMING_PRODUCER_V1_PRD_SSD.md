---
artifact_id: LIST_A_CHRONOLOGICAL_CONFIRMING_PRODUCER_V1_PRD_SSD
artifact_version: '1.0'
design_id: LIST_A_CHRONOLOGICAL_CONFIRMING_PRODUCER_V1
status: DESIGN_READY_FOR_SCOPED_EXECUTION_NOT_A_GIT_READY_TASK
as_of: '2026-10-14'
mode_of_this_document: DESIGN
expected_repository: lancerbeta/solana-alpha-lab
planning_base: 07c81a99f2d0f385df66de2e1a5254e224c6b3b3
predecessor_audit: SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1
scientific_owner: LIST_A_CONFIRMATION_PROTOCOL_V1
scientific_core_sha256: 3b62c8ccdc797c8f378aef831c2b5cad45bdc1e9c336ba94417bf54ccbd7e252
proposed_execution_mode: EXECUTE_PRODUCT_REPAIR_WITH_SYNTHETIC_ACCEPTANCE
real_sample_authorized: false
real_value_read_authorized: false
promotion_authority: NONE
recommended_model_effort: SOL_XHIGH
---

# List A confirming producer — единый PRD + SSD

## 0. Решение и критерий завершения

**Реализовать отсутствующий продуктовый переход: заранее заданный List A вопрос + точно допущенная выборка → одна зарезервированная попытка → принятый численный метод → содержательные scientific records → обычный dossier.** Это реализация, не новый общий аудит и не повтор #403/#404.

Confirmer — вычислитель одного заранее зафиксированного научного вопроса. Он не ищет гипотезы, не подбирает окна и не торгует. Для List A вопрос: отличается ли средний относительный рост цены у участников A от известного дополнения C в той же episode-популяции. Его положительный ответ — условная статистическая ассоциация, а не исполнимая alpha.

**DONE:** production entrypoint на трёх зарегистрированных синтетических случаях действительно проводит весь новый путь, сохраняет результат/lineage/charge и отдаёт их обычному consumer; независимые проверки подтверждают расчёт и защитные границы. Необходимые входной binding, reservation и выходной consumer входят в этот же атом. Функция bootstrap сама по себе, очередной `MISSING_PRODUCER` или тестовые вручную записанные scientific records — не результат задачи.

Разработка не требует реальной подтверждающей выборки. Её отсутствие не блокирует реализацию и synthetic acceptance. После выполнения состояние может быть одновременно:

```text
CONFIRMING_CAPABILITY = IMPLEMENTED_AND_SYNTHETICALLY_VERIFIED
REAL_SAMPLE_BINDING = UNBOUND
REAL_CONFIRMATION_EXECUTIONS = 0
REAL_VALUE_READ_AUTHORIZED = false
STRATEGY_PROMOTION = NOT_AUTHORIZED
```

Эти строки — смысл итогового отчёта, не требование добавить пять глобальных product enums.

## 1. Основание, текущая правда и границы уверенности

Репозиторий прочитан на `07c81a99f2d0f385df66de2e1a5254e224c6b3b3`, merge #404. Факт merge проверен; post-merge CI этим документом не удостоверяется. Coding executor перепроверяет свою точную базу и применимые gates перед mutation. Исторические результаты не заменяют current readback.

| Подтверждённый факт | Значение для реализации | Источник |
|---|---|---|
| #403 добавил Spec 1.4 для `REUSE_ONLY / EXPLORATORY_REUSE`; классификация умеет native E-outcomes | Не переписывать эту ветку как confirmer | S2, S3 |
| #404 получил реальные LIST 0.11 / MIXED 0.055 и SC06 −0.09 / −0.045 при прежнем prefix/denominator | Арифметический replay и его потребление уже проверены; не повторять весь smoke | S1 |
| List A метод, пороги, seeds и precedence приняты, но producer был оставлен будущей реализации | Реализовать этот метод, не выбирать новый statistical framework | S4, S5 |
| Generic DocumentRunner выполняет capability прежде, чем записывает completion; frozen replay не является новым confirming look | Новый маршрут обязан резервироваться раньше первого нового значения | S6 |
| `ResearchStore.append(..., before_commit=...)` выполняет проверку под writer lease и публикует manifest последним | Использовать существующий атомарный owner; не заводить отдельную БД научной истины | S7 |
| Episode discovery release помечен `EXPLORATORY_REUSE`; v1.4 verifier проверяет этот профиль | Вход confirmer нельзя получить переименованием роли уже опубликованного discovery corpus | S3, S8 |
| Dossier связывает execution и scientific records по exact identity; его generic obligations в значительной части проверяют наличие полей | Добавить узкий typed consumer нового результата, а не «набить ключи» для PRESENT | S9 |
| Обычный dossier загружает ExperimentSpec из Git | Зарегистрировать новую постоянную definition штатно; sample/run bindings оставить в data plane | S9, S10 |

**Не установлено:** текущая пригодность каких-либо реальных когорт для confirmation, полная история их exposure, их source-role compatibility, реальное качество ассоциации, рыночная калибровка интервалов. Эти неизвестные не восполняются synthetic PASS.

В §5–§12 ниже приняты **проектные решения** о новом исполнимом маршруте. Их нет в старом Git как реализованной capability. Научные формулы из S4/S5 отделены от этих решений. Starter в §20 принимает bounded design, не задним числом выдаёт разрешение старому аудиту.

## 2. Outcome, потребители, scope

### 2.1. Владелец получает

Возможность передать exact input binding, увидеть почему он допустим/заблокирован без вскрытия исходов, отдельно разрешить ровно одну попытку и затем прочитать результат вместе с выборкой, ограничениями, числом попыток и безопасным NEXT. После crash он продолжает ту же попытку, а не теряет историю или получает вторую «первую» проверку.

Потребители: scientific owner; `classify_lane`/DocumentRunner и registry dispatch; ResearchStore; `compose_experiment_dossier`/FactoryApplication/Workbench; следующий отдельно разрешённый процесс оценки стратегии.

### 2.2. In scope — одна вертикальная capability

1. Version-isolated определение List A confirming execution и его регистрация.
2. Production metadata binder точного native episode sample и runtime binding envelope.
3. Exact local execution grant, source-role/protection/exposure/chronology admission.
4. Durable pre-values reservation, single evaluator, retry/recovery без refunds.
5. Принятый crossed-cluster bootstrap и verdict с исходными floors.
6. Atomic result + substantive evidence + cold dossier, без автоматического PROMOTE.
7. Synthetic proof, targeted regressions и необходимая semantic/navigation propagation.

### 2.3. Не входит

Реальный confirming trial; подбор/сбор/покупка данных; изменение collector, quota, capture floor или live protected assignments; универсальный experiment framework; подбор estimator/seed/window; mixed hypothesis confirmer; новая стратегия, execution feasibility, quotes/costs, PAPER/SHADOW/live; облачная orchestration; новый сервис, очередь, DB, dependency или UI-раздел; ремонт всех старых dossier validation rules.

Не надо повторять blind Actor, настоящий LLM Critic или поиск гипотез. Здесь уже задан owner-approved first-test question. Старые synthetic KILL, trials, audit receipts и исчерпанные кампании не открывать повторно.

### 2.4. Entry

`START`, если на exact base остаётся F01 и доступны existing runtime/store checks. `PATCH` — если безопасно сместились пути/регистрация. `SKIP` или targeted repair — если capability уже реализована и подтверждается readback. Не создавать дубль.

Отсутствующие **части этого outcome** реализовать, а не превращать каждую в новый STOP. Внешняя authority, изменение научного meaning и расширение до collector/platform — реальные STOP. Отсутствие реального sample — штатный отрицательный preflight и положительный synthetic engineering path.

## 3. Неизменяемый научный контракт

Authoritative core: `configs/list_a_chronological_confirmation_v1.yaml::protocol_core` и S4. Не редактировать core, старые source pins, seed derivation, старый `sample_binding: UNBOUND` или исторические PASS/authorization ради новой реализации.

| Смысл | Frozen значение |
|---|---|
| Purpose | `FIRST_PREREGISTERED_TEST`; не выдумывать empirical development |
| Population | `OPPORTUNITY_EPISODES`, native admissions |
| A | `JUPITER:toporganicscore:5m`, membership `EPISODE_T0`, known TRUE; AB/AC/ABC включены |
| C | known FALSE в том же declared universe; UNKNOWN/INVALID не C |
| Decision / target | E1800 / E14400; PRICE `FIELD-USD-PRICE-001` |
| Return | `P(E14400) / P(E1800) − 1` |
| Estimand | episode-weighted mean A minus mean C, conditional on observed targets |
| Direction / delta | A greater than complement, `delta = 0` |
| Bootstrap | crossed mint × epoch-aligned decision-time blocks; 24h и 48h |
| Replicates | 4096 для каждого partition; один frozen seed каждого partition |
| Support | ≥30 contributing mints и ≥30 contributing time blocks в каждой группе и каждом partition; pooled floors также сохраняются |
| Missingness | target coverage ≥0.95 в каждой группе; разница missing rates ≤0.05 |
| Sensitivity | leave-one каждого contributing mint и каждого occupied block обоих partitions; point contrast, не новый bootstrap |
| Quantiles | nearest rank 1-based: 103 и 3994; Python indices 102 и 3993 |
| Numeric runtime | pinned CPython 3.13.14, binary64, canonical episode order, `math.fsum`; finite JSON, без EPS в verdict |
| Negative meaning | локальный результат этого вопроса/границы, не закрытие всей family |

E14400 означает 4h от T0, а интервал после E1800 — 12 600s = 3.5h. Ни эти часы, ни denominator не заменяются mint age, publication time или complete-case sample.

**Runtime qualification:** старые scientific source pins не обновлять на новый HEAD как будто это старое evidence. Создать новую компактную execution-qualification receipt: old core digest → текущие source-owner implementations/runtime → independent numeric/clock witnesses → результат совместимости. Core digest и seeds остаются прежними. Несовместимый runtime/meaning блокирует execute до explicit compatibility resolution; version string нельзя подделывать. Existing locked runtime переиспользовать.

Старые `value_read_authorized: false` и `activation_authorized: false` фиксируют отсутствие разрешения самим design artifact. Их не переводить в true. Будущее exact разрешение конкретного запуска хранится отдельным source-bound grant по §7. Никакого наследования разрешения от merge, core hash или status design.

## 4. Основные проектные решения

| ID | Решение | Почему |
|---|---|---|
| D1 | Новая capability `CAP-LIST-A-CHRONOLOGICAL-CONFIRMATION-001`, отдельная ветка Spec 1.5 | 1.4 — exploratory replay с другой readiness и обязательным frozen HFIC result; это не confirmation |
| D2 | Одна Git definition, immutable runtime execution binding в ResearchStore | Не коммитить sample/операционку на каждый run и не создавать фиктивную definition в тестовом consumer |
| D3 | Вход — bounded native episode sample envelope с доказуемой source role; не discovery-role converter | Нельзя разрешать confirmation источнику с `confirmatory_reuse_forbidden=true` |
| D4 | Новая reservation-семантика — у confirmer, атомарность — у существующего ResearchStore | Generic completion после вычисления недостаточна; второй журнал истины не нужен |
| D5 | Exclusive local execution lock на один study + durable attempt identity | Не держать глобальный ResearchStore writer lease весь bootstrap; не допускать два evaluator |
| D6 | Native point/prefix/list interpretation переиспользуется; bootstrap — небольшой pure module | Не дублировать E/PIT semantics и не строить универсальный scientific engine |
| D7 | Typed evidence projection для новой capability, legacy правила не ослабляются | Наличие ключа RESULT или summary не должно становиться научной валидностью |
| D8 | Приёмка — один native vertical suite на трёх cases + дешёвые branch/fault checks | Не нужен повтор общего большого smoke, но private-function PASS недостаточен |

Wire names новых объектов ниже — рекомендуемый проектный контракт. Executor может сократить внутренние классы/файлы и переиспользовать эквивалентный существующий механизм, если сохраняет meaning, consumer proof и документирует решение в том же атоме. Не менять публичную семантику молча под видом naming.

## 5. Архитектура и единственные владельцы

```text
Git List A protocol + Git ExperimentSpec 1.5
                    |
        prepare exact execution binding (metadata only)
                    |
      explicit source/sample grant; no default real grant
                    |
existing CLI / DocumentRunner / registered capability
                    |
    current admission + exclusive study execution
                    |
  ResearchStore: durable reservation / RUN_STARTED
                    |
    native prefix -> A/C/D -> exact target cells
                    |
  frozen method -> local protocol terminal + limits
                    |
 immutable result + atomic ResearchStore completion/evidence
                    |
 ordinary dossier -> owner PAUSE/REJECT/REVISE; PROMOTE gated
```

**Один owner на смысл:**

- Core/question/method — S4/S5; definition — Git ExperimentSpec.
- Bound sample, grant, reservation, charge, substantive result — typed records существующего ResearchStore. Файлы результата content-addressed и referenced им, не параллельная mutable truth.
- Episode/time/list/price semantics — `opportunity_episodes`, `hfic_research_scope`, `hfic_temporal_discovery`.
- Process exclusion — operational lock, не научная запись и не свидетельство untouched.
- Dossier/Workbench — производные views. Generic RUN не становится scientific evidence.

### 5.1. Минимальная файловая организация

Предпочтительно три небольших новых production modules:

```text
src/solana_alpha_lab/factory/list_a_confirmation.py
    orchestration, reservation/commit, status/resume, public capability handler
src/solana_alpha_lab/factory/list_a_confirmation_inputs.py
    closed bindings, role/exposure/protection/chronology, native input adaptation
src/solana_alpha_lab/factory/list_a_confirmation_method.py
    pure accepted calculation and typed result validation/projection helpers
```

Не выносить каждую dataclass в отдельный модуль. Допустимо два файла, если границы остаются ясными. Не импортировать code из `tests/` или `docs/evidence/` в production.

Переиспользовать `ResearchStore.append/find_record`, native manifest/schedule verification и atomic publish. Если требуется открыть private value-neutral helper, сделать минимальную public facade у его настоящего owner; не копировать реализацию в confirmer.

### 5.2. Registry и dispatch — обязательная часть

Descriptor: accepted по итогам этого delivery, `max_provider_calls=0`, `effect_class=OFFLINE_DATA_PLANE_WRITE`, `output_zone=DATA_ROOT_ONLY`, `promotion_authority=NONE`; подходящие существующие output kinds, включая scientific result. В implementation closure входят новый producer, method, input contract и изменённые authoritative dependencies.

Loader, classifier, `execute_capability`, DocumentRunner и CLI должны понимать **один и тот же** новый route. Handler registered capability не является обходом admission/reservation: direct dispatch подчиняется тем же условиям, что CLI. Pure calculator не публикует science и не является registry entrypoint.

Новая ветка DocumentRunner располагается до generic execution/persistence, которые рассчитаны на старый route. Для 1.5 один owner создаёт reservation и completion; generic runner не дописывает вторые TRIAL/RUN/evidence после возврата handler. Legacy 1.0–1.4 и их hashes/terminals сохраняются.

### 5.3. Планируемые API-границы

Названия ниже — новые design interfaces, не утверждение, что функции уже существуют. Dataclasses/dicts и точный spelling executor выбирает по existing style; смысл результата и единый owner обязательны.

```python
# list_a_confirmation_inputs.py
def inspect_confirmation(definition, sample_ref, *, root, data_root, now): ...
# -> typed metadata readiness + reasons + exact compiled binding proposal;
#    read-only, no grant/reservation/new outcome read.

def prepare_confirmation(definition, sample_ref, *, root, store, now): ...
# -> immutable execution_binding_id/hash via the same inspected semantics.

# list_a_confirmation.py: registered capability signature remains compatible
def execute_list_a_confirmation(spec, *, root, authority_phrase=None, capture_hooks=None): ...
# -> ordinary runner response + protocol_terminal + immutable result locator.
#    data_root/binding/grant references are validated; caller hooks do not grant rights.

def read_confirmation(store, *, trial_id): ...
# -> verified committed state/result; no source evaluator and no writes.

def resume_confirmation(store, *, trial_id, current_context): ...
# -> same frozen scientific attempt or typed refusal, never a fresh trial alias.

# list_a_confirmation_method.py
def calculate_list_a(observed_rows, denominators, *, qualified_protocol_core): ...
# -> closed deterministic method result; no I/O, store, authority or promotion.
```

Не оставлять два отдельно написанных алгоритма `inspect` и `execute`: общий validator возвращает typed compiled context, а execution повторно проверяет его current-sensitive части. Runtime result/public exceptions используют существующий `reason_codes + next_action` transport. Невалидный caller JSON не вызывает traceback с локальными путями или secrets.

## 6. Definition и runtime binding без Git-операционки

### 6.1. Git definition: Spec 1.5

Создать и штатно зарегистрировать `configs/experiment_specs/list_a_chronological_confirmation_v1.yaml`. Это конкретный List A first-test, не общий template factory. Definition фиксирует question, estimand, population, protocol core ref/hash, capability, explicit outcome и тип обязательного входа.

Spec 1.5 — version-isolated definition form для этого consumer. Не заполнять legacy quote question, фиктивную capability или `availability_cutoff` из commissioning fixture. Не передавать `hfic_replay_session_id`: новый confirming trial не обязан притворяться replay уже просмотренного результата.

Принцип формы (не полный ready-to-run JSON):

```yaml
schema: smial.experiment-spec
schema_version: '1.5'
experiment_id: EXP-LIST-A-CHRONOLOGICAL-CONFIRMATION-V1
hypothesis_version: HYP-LIST-A-CONDITIONAL-EPISODE-CONTRAST-V1
population: OPPORTUNITY_EPISODES
capability_id: CAP-LIST-A-CHRONOLOGICAL-CONFIRMATION-001
parameters:
  protocol_ref: repo://configs/list_a_chronological_confirmation_v1.yaml
  protocol_core_sha256: 3b62c8ccdc797c8f378aef831c2b5cad45bdc1e9c336ba94417bf54ccbd7e252
  input_contract: NATIVE_EPISODE_CONFIRMATION_SAMPLE_V1
required_outcomes:
  - point_id: E14400
    field_ids: [FIELD-USD-PRICE-001]
    role: PRIMARY
```

Сохранить нужные общие поля definition согласно existing owner. Новая схема закрытая. Scientific fields сравниваются с core, не просто принимаются как произвольные строки. Version 1.5 не разрешает произвольный estimator, MIXED, другое delta или E-outcome. Unknown fields/versions/roles — typed refusal.

**Hash domains:** `experiment_spec_sha256` по-прежнему canonical hash Git definition; YAML byte hash — отдельно по legacy contract. Нельзя записывать hash runtime envelope в поле, которое dossier сравнивает с Git definition. Новый `execution_binding_sha256` связывает конкретный sample/run и входит в execution identity и evidence snapshot отдельно.

Definition timestamps не выдаются за время доступности sample. Runtime `as_of`, data cutoff, prepared/frozen/reserved/completed times принадлежат execution binding/passport. Для 1.5 explicitly dispatch их validation; не менять смысл одноимённых полей старых версий.

### 6.2. Immutable execution binding

Production `prepare` компилирует owner question и exact sample в закрытый документ. Он сохраняется штатным append-only writer и возвращает logical ID/hash. Подготовка не запускает evaluator и не расходует scientific attempt.

Обязательные группы полей:

| Группа | Содержимое |
|---|---|
| Definition | experiment/hypothesis IDs, canonical definition hash, protocol core hash |
| Scientific recipe | native canonical query 1.2, query scientific hash, list definition/scope, native clocks, universe policy и их refs/hashes |
| Sample | exact source set, interval `[start,end)`, cohort/release/manifest/partition IDs, raw/semantic hashes, census/admission identity; никакого `latest` |
| Information provenance | complete exposure evidence refs; preregistration/development status; chronology/purge proof; protected role и frozen protection |
| Qualification | current implementation closure, accepted numeric runtime/serialization/seed protocol |
| Execution | study identity, data cutoff, operation budget, target domain, prepared/frozen identity |

`prepare` не модифицирует старый `sample_binding` внутри S5. Новый binding — собственный объект в data plane, bound к тому же scientific core. Новый dataset pointer сам по себе не заменяет exact bound set.

`query`, `sample`, `protocol` и `grant` имеют разные hashes. Сопоставление их полей делает компилятор, а не LLM. Actual compiled query/spec и compilation receipt существуют **до** reserve и первого value read; output не достраивает протокол задним числом.

### 6.3. Обычная definition registration и dossier

Новая Git definition, Catalog asset и lifecycle route регистрируются в этом атоме. Synthetic test использует тот же зарегистрированный definition owner — не вручную подложенный `projection.entities` и не monkeypatch `load_experiment_spec`.

Один definition может иметь явный runtime study/binding. Нельзя беззвучно объединять разные bindings в один результат. Dossier показывает exact run/binding и conflicts; при необходимости добавить bounded lookup по binding/run, не новую registry/UI-platform. Холодный поиск результата работает по returned locator без знания внутренних путей.

## 7. Sample admission, роли и authority

### 7.1. Новый bounded input port, а не новый collector

`NATIVE_EPISODE_CONFIRMATION_SAMPLE_V1` — локальный контракт входного пакета для producer. Содержит immutable native census/observations, schedule/list/provenance/protection metadata и source-set completeness. Он не собирает рынок и не изменяет существующий discovery release.

Binder допускает только source-owned пакет, чья role разрешает exact protocol consumption, а lineage доказывает native admissions и отсутствие запрещённого exposure. Нужны production validation и ordinary prepare path, не только test-only конструктор.

В этом атоме не обещается, что текущий collector уже производит подходящий real пакет. Проверяемый consumer и его production input contract должны существовать; реальный upstream provisioning/отдельный сбор требуют будущего exact scope. **В то же время нельзя оставить новый вход неописанным или stub:** writer/validator/metadata prepare и способ подать законный пакет должны быть реализованы и пройти acceptance.

Можно переиспользовать source-owner format/serializer для native rows. Если existing verifier совмещает integrity и mandatory exploratory-role checks, выделить value-neutral structural verification у source owner и оставить прежний exploratory wrapper строгим. Новый purpose-specific admission проверяет compatible source role отдельно. Generic `allow_protected=True`, `ignore_role` и отключение existing release checks запрещены.

Новый пакет не снимает `confirmatory_reuse_forbidden=true` ни с payload, ни с ancestors. Published `EXPLORATORY_REUSE` из #403/#404 — только negative control: expected refusal до target values. Copies, новые hashes, новый manifest или другое имя файла не очищают exposure.

### 7.2. Что проверяется до reservation

- Exact definition/core/query/schedule/list identity, source paths/hashes, collection/population/anchor и canonical source-set completeness.
- UTC-aware interval и immutable cutoff, frozen chronology и approved selection/purge rule.
- Source authority, complete exposure provenance и frozen/current protection независимо. `holdout=false`, отсутствие локальных records и пустой каталог не равны доказанной untouched history.
- Structural upper bounds support по разрешённым metadata. `<30` в необходимой оси — `INSUFFICIENT_POTENTIAL_SUPPORT` до look. Возможность ≥30 не доказывает actual support.
- Execution grant соответствует всему binding и текущему status; runtime/resource feasibility известны до новых данных.

Preflight **не читает target presence/missingness, numeric observations, Parquet statistics, return previews или scores**. Оpaque hashing отдельно от decoding. Не открывать весь mixed JSON, если в нём вместе с metadata находятся target counts; selective field projection либо заранее разделённый source-owner manifest.

### 7.3. Exact grant

Grant — отдельная source-bound local authority запись: study/binding hash, protocol/core, sample-source set и роль, executor/plane scope, `max_scientific_attempts=1`, validity/current revocation ref, domain `SYNTHETIC` или `REAL`. Это не API credential и не permission от review.

Предпочтительно расширить существующий local preview/authorize pattern, не создавать auth platform. `prepare` показывает canonical request hash; authorize принимает exact request через owner-controlled action. Один текст `approved:true` в произвольном входном JSON grant не создаёт. Регистрация source authority, manifest completeness и факт consumer grant — разные проверки.

**Purpose-specific consumption:** роль `UNTOUCHED_FORWARD_HOLDOUT` продолжает запрещать exploratory reader. Новый consumer может получить только узкое `ALLOW_EXACT_CONFIRMATION` для этого binding через проверенный matching grant и source contract, допускающий такое consumption. Это не перевод глобального protection в ALLOW. Explicit global revoke, несовместимый source role, `confirmatory_reuse_forbidden=true` или неполный inventory остаются DENY/UNRESOLVED. Простое переиспользование exploratory `protection_decision` с требованием ALLOW дало бы вечную блокировку законного holdout; его нельзя «лечить» снятием protection. Нужный purpose-bound adapter входит в этот атом, legacy checks не меняются.

После передачи starter разрешены grant/registration **только для контролируемых disposable synthetic cases этого атома** через production validation. Real grant, реальные protected assignments, провайдеры и live roots — вне scope. Synthetic flag не выключает checks: сохраняются exact sample, role, clocks, exposure и reservation; domain проходит через весь результат до dossier.

Повторная проверка current protection выполняется перед reserve, перед первым value read, при resume и перед completion. Более строгий текущий DENY/revoke блокирует новое действие. Исторический readback результата не переоформляет прошлое как свежее разрешение.

### 7.4. Exposure без новой платформы

Новая reservation является source-bound potentially-exposed evidence. Её должны видеть проверка этого study и admissibility последующих requests на тот же sample. Rename study, новый executor/model/prompt, другой Git head или повторное копирование исходника не дают чистую выборку.

Использовать существующие declared exposure/protection owners и ResearchStore. Если для новой capability нужен небольшой record kind внутри `RESEARCH_ARTIFACT` и bounded exact lookup — это часть реализации. Не строить глобальный cross-provider exposure warehouse. Authority scope — один canonical data plane одного оператора; дублирующий real plane/host не разрешён этим атомом.

## 8. Время, population и native values

### 8.1. Одна геометрия времени

`opportunity_episodes.resolve_point` владеет due/assigned/deadline. Для calendar clustering берётся `nominal_due(E1800)`, как требует S4/S5. Feature/price admissibility использует реальные availability clocks, а не calendar label.

E0 witness сохраняет исходную availability, не получает restamp в T0. Publication/import time не заменяет information time. Source visibility allowance, grid rounding и lateness должны иметь bound meaning; UNKNOWN компонент не становится нулём.

Для development/relevant exposure:

```text
E = maximum bound target-from-T0 horizon
    + non-double-counted grid / lateness / visibility allowances
boundary = max(dev_target_available_max, dev_decision_max + E)
validation_information_start > boundary
```

Purge information/label overlap применяется по frozen metadata rule до values. Equality на boundary не разрешена. E не прибавляется второй раз. Не применять весь 3-day observation grid как target horizon, если принятый вопрос использует E14400; не занижать allowance до номинальных 4h.

Для `FIRST_PREREGISTERED_TEST` без empirical development нет искусственного train set/dev timestamps. Нужны actual complete exposure provenance и preregistration boundary. Synthetic golden worlds — не empirical development для реального sample.

### 8.2. От admission к анализу

```text
all declared admissions
 -> source/list scope known (UNKNOWN/INVALID отдельно)
 -> native decision eligible
 -> group A или C, frozen before target inspection
 -> target observed / typed missing / late / censored / invalid
```

Join key — episode identity со source namespace и release lineage; mint остаётся clustering key. Exact duplicate episode с теми же scientific bytes deduplicates один раз; conflicting duplicate — отказ. Повторный mint в другом разрешённом цикле остаётся отдельным episode. Чужой target не лечит missing target другого episode.

Штатные `MISSING_TYPED/CENSORED/CENSORED_LATE/DISAPPEARED` source states — измеряемая missingness, не повод удалить admission. Поддельный `OBSERVED` с противоречивыми clocks/identity, неподтверждённая publication или изменённые hashes — нарушение валидности, а не обычный missing target. Использовать это различие native owner, не изобретать свою эвристику.

Для данного `LIST_CONTRAST` группы A и C disjoint и исчерпывают известную decision-eligible часть scope. Native universe/prefix interpretation не заменять «все строки с E14400». Target не участвует ни в D, ни в A/C, ни в purge.

UNKNOWN referenced membership трактуется по `REQUIRE_KNOWN_REFERENCED`: не превращается в FALSE/negative comparator. Нельзя скрыто сузить coverage до known subset, если frozen native scope требует отказ всего evaluation. Typed refusal и counts оставляются видимыми.

### 8.3. Отличие от readiness 1.4

Spec 1.4 требует COMPLETE required-outcome coverage для своего exploratory replay route. **List A confirmation использует собственные принятые 0.95/0.05 правила**, после reservation и фактического чтения. Нельзя вызвать projector 1.4, получить его 100%-coverage veto и объявить, что accepted List A метод требует 100%.

Переиспользуется prefix/identity/clock logic, а не чужая coverage policy. Cases с 95–100% coverage должны быть выразимы без lowering guards в legacy route.

## 9. Reservation, concurrency, idempotency и recovery

### 9.1. Три разные identity

1. **Study/budget identity** — owner-frozen scientific question + named study/source authority. Обеспечивает allowance 1; не меняется от formatting/command/model/retry.
2. **Trial identity** — exact accepted protocol/query/sample/exposure/role/grant/qualification binding. Менять его внутри pending trial нельзя.
3. **Technical execution attempt** — конкретный процесс/resume. Может быть несколько, но scientific charge остаётся один и уже потраченный.

Existing run key переиспользовать как вычислительную identity, добавив binding hash в его штатный config domain. Не менять ключи legacy runs. Run key, зависящий от Git/lockfile, не использовать как единственный scientific budget key: смена кода не даёт бесплатную новую проверку.

### 9.2. Минимальная реализация single evaluator

Scientific owner — ResearchStore. Использовать `append(..., before_commit=...)` для compare/recheck под writer lease. Callback не читает market values. Он заново читает exact reservation/allowance/grant/source metadata и отказывает при race. Нельзя использовать два независимых append как «одну атомарную reservation».

Рекомендуется local exclusive OS-backed lock на study на время одной evaluation; kernel release при смерти процесса, без lease-TTL takeover живого evaluator. Сначала переиспользовать подходящий существующий operational lock. При отсутствии — небольшой helper в owner module на поддерживаемой платформе, без нового dependency/DB/daemon. Lock содержит только operational identity, не result/charge. Неподдерживаемая FS/locking semantics → typed refusal до values. Не удерживать глобальный writer lease всю computation и не делать вложенный `writer_lease -> append` с не-reentrant API.

Lock + reservation работают совместно: lock запрещает concurrent evaluator, durable reservation запрещает новый scientific trial после crash. Acquire lock после завершения чужого процесса не означает reset попытки. Во время lock короткие ResearchStore append пользуются собственным lease.

### 9.3. State machine новой capability

Имена — scoped состояния, не новые глобальные enums:

| Состояние | Charge | Разрешённое действие |
|---|---:|---|
| PREPARED / BLOCKED_BEFORE_RESERVE | 0 | Metadata/status, исправление ещё не исполненного binding через новый immutable revision |
| RESERVED_POTENTIALLY_EXPOSED | 1 | Один admitted evaluator; source-bound pending history уже durable |
| RUNNING / INTERRUPTED | 1 | Только тот же trial; safe resume либо блокировка |
| COMPLETED | 1 | Verified saved-result replay без evaluator/target reads |
| INVALID_AFTER_RESERVE | 1 | История/exposure остаются; не переоткрывать как untouched |

Persist reservation и RUN_STARTED в одной manifest-last transaction **до первого numeric prefix/target read**. Reservation record — typed artifact у нового owner; existing TRIAL envelope используется только с корректной семантикой. Не штамповать итог `INCONCLUSIVE` как будто исследование уже выполнено. Итоговый trial record может быть записан в completion transaction; charge до него устанавливает reservation.

При неподтверждённом append source values не открываются. Первый value reader сам требует подтверждённую reservation identity, а не доверяет `reserved=True` от caller. Readback записи из нового процесса — oracle, что reservation реально committed.

### 9.4. Crash boundaries

| Где остановился процесс | Обязательное поведение |
|---|---|
| До reservation commit | Нет values, нет расхода; incomplete publication не выдаётся за committed trial |
| После reservation, до первого value | Charge/potential exposure уже 1; resume того же trial, не refund |
| После начала values / во время bootstrap | Pending/attempt history сохраняется; повтор только exact frozen identities/runtime, новый technical attempt, charge всё ещё 1 |
| Result bytes созданы, completion manifest ещё нет | Result orphan не становится evidence; допускается verified reuse или exact recomputation; один eventual completion |
| Completion committed, ответ потерян | Cold repeat читает прежний result; evaluator и target decoding = 0, новых records нет |
| Protection/source изменились после чтения | Не публиковать успешный scientific completion; сохранить invalid/pending evidence и факт exposure; исторические bytes не исправлять |

Не требуется сложный checkpoint каждого bootstrap replicate. Полный deterministic recompute того же разрешённого trial после crash дешевле и достаточен. Он учитывается как ещё один evaluator invocation, не новая independent confirmation. Изменённые code/runtime/seed/spec/sample требуют explicit compatibility/replan, не silent resume.

Новые process/trace artifacts имеют unique attempt IDs и immutable names. Shared `<kind>-replay.json` aliases из #404 не переиспользовать. History не восстанавливать угадыванием и не удалять для cap.

## 10. Принятый расчёт: низкий уровень

### 10.1. Вход pure method

До method подготовлены валидные observed A/C episode rows плюс полные denominators/missingness diagnostics. Method не ходит в store/provider, не выбирает sample, не меняет floors. Native price admissibility остаётся у temporal owner; не вводить вторую собственную проверку «цена достаточно правдоподобна».

Операционализация resampling: contributing labels — labels, имеющие хотя бы один допустимый observed target в pooled A∪C; group support считается отдельно в A/C. Labels с нулевым вкладом из excluded/missing-only seats не увеличивают actual support. Это явное уточнение реализации frozen contributing-support semantics, а не заявление о фактически независимых observations.

### 10.2. Алгоритм

1. Построить episode-weighted `r_i`; сохранить исходные A/C counts, observed/missing counts, reason masks и repeated-mint diagnostics.
2. Сверить actual group support, coverage, missing-rate gap. Недостаточность → scoped `INSUFFICIENT`, без seed shopping.
3. Отсортировать episodes canonical episode ID; mint labels lexicographic; block IDs numeric. Block ID — integer floor по UTC epoch, без float timestamp rounding на границе.
4. Для каждого h отдельно создать **локальный** `random.Random(seed_h)`. Не global RNG.
5. В каждой replicate выполнить M draws из M mint labels, затем T draws из T block labels, с возвращением через принятый `randrange`.
6. Сосчитать multiplicities. Для episode `w_i = m[mint_i] * t[block_i]`. Один набор weights используется для обеих групп.
7. Weighted group mean = `math.fsum(w_i*r_i) / math.fsum(w_i)`. Это не mean(cluster means) и не равный вес всем clusters.
8. Любая empty/nonfinite replicate → `INSUFFICIENT`; не отбросить replicate, не reroll, не уменьшить B.
9. Отсортировать 4096 contrasts и взять элементы 102/3993. Не вызывать generic type-7 quantile из descriptive audit.
10. Leave-one каждого mint и каждого occupied block 24h/48h: исключить его episodes, пересчитать point contrast; без новой resampling-сессии. Empty/nonfinite group → `INSUFFICIENT`.
11. Применить exact precedence и сравнения из §10.3. Scientific thresholds не округлять.

Память — O(N + M + T + B), не B копий rows и не N×B матрица. Для pet-scale достаточно прямой deterministic loop. Sparse per-cell preaggregation допустима, только если не меняет ordered binary64 computation и проверена отдельным oracle; это не обязательная оптимизация.

Core hash: `3b62c8ccdc797c8f378aef831c2b5cad45bdc1e9c336ba94417bf54ccbd7e252`.

```text
seed_h = int(SHA256_UTF8(core_sha256 + ':' + str(h))[:16], 16)
seed_86400  = 2055296707731192101
seed_172800 = 3449030900544075880
```

Не включать sample, время запуска или случайный UUID в seed rule. Они входят в trial identity, не меняют frozen estimator.

### 10.3. Terminal precedence

| Условие | Local protocol terminal |
|---|---|
| До look не хватает definition/binding/meaning | `BOUND_CONTRACT_NOT_READY` |
| Нарушены identity/protection/PIT/chronology | `INVALID_OR_BLOCKED` + точный reason/exposure stage |
| Support/coverage/finite/replicate/leave-one недостаточны | `INSUFFICIENT` |
| L24>0 AND L48>0 AND min(leave-one)>0 | `ASSOCIATION_SUPPORTED_CONDITIONAL` |
| U24<=0 AND U48<=0 AND max(leave-one)<=0 | `ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY` |
| Иначе | `INCONCLUSIVE_DEPENDENCE_OR_CONCENTRATION` |

Нулевая синтетическая разница попадает во второе statistical condition, а не автоматически в INCONCLUSIVE. Constant lattice разрешён как algebra witness; не вводить post-hoc veto «слишком красивый результат».

Adapter в existing passport enums задаётся явно и проверяется: supported → `trial_outcome=POSITIVE`, `scientific_terminal=RETAINED`; not-supported → `NEGATIVE / REJECTED`; insufficient/inconclusive → `INCONCLUSIVE / INCONCLUSIVE`; нарушенная валидность → `INVALID` и соответствующее execution state. Confirmed actual enum contract проверить перед реализацией. Local protocol terminal всегда сохраняется отдельно и показывается владельцу; generic enum не должен скрывать условный смысл. Ни один terminal не пишет owner PROMOTE/StrategyVersion автоматически.

### 10.4. Четыре дешёвых независимых numeric oracle

- **Weighted means:** A rows `(m1,t1,r=1/4)`, `(m2,t2,r=0)`, `(m3,t3,r=0)`; C rows `(m1,t2,r=−1/8)`, `(m2,t1,r=1/8)`. Mint multiplicities `(2,1,0)` и time `(1,2,0)` — по 3 draws из 3 labels. Weights A `(2,2,0)`, C `(4,1)`: mean A=1/8, mean C=−3/40, contrast=**1/5**. Fraction oracle ловит неправильные weights/group averaging; zero-weight row не даёт reroll.
- **Quantile:** sorted vector `0..4095` даёт **102, 3993**, не interpolated values. Проверяет nearest-rank отдельно от PR bootstrap кода.
- **Coverage:** `120/128=15/16=0.9375` не проходит 0.95; `122/128=61/64=0.953125` при C coverage 1 проходит coverage и gap, если прочие floors соблюдены.
- **Hash/seed:** независимый SHA256 calculation возвращает два seed выше. Не проверять seed вызовом самой production seed helper.

Мини-oracles не обходят support floors production run: это unit-level проверки pure arithmetic. По крайней мере один non-degenerate fixed-draw test должен связать sampler ordering/multiplicities с calculator; нельзя ограничиться постоянными returns, на которых неправильный bootstrap тоже «работает».

## 11. Результат, scientific records и обычный consumer

### 11.1. Canonical result

Закрытая result schema содержит:

```text
identity:
  definition/core/query/sample/execution_binding/trial/run hashes
  source manifest/partition/schedule/list/protection/exposure refs
  current implementation/runtime qualification
population:
  admitted, scope-known, D_A/D_C, observed A/C
  distinct/repeated mint, contributing blocks by h/group
  exact membership/analysis-row digest; typed exclusion/missing reason counts
method:
  B, seeds, order, quantile rule, runtime/numeric contract
result:
  mean_A, mean_C, delta_hat
  CI_24h, CI_48h; replicate counts/validity/digests
  leave-one counts, extrema and named dominating clusters
  support/coverage checks, protocol_terminal, reason_codes
lineage:
  reservation/grant IDs, execution attempts, exposure stage, completion refs
claim_limits:
  domain, conditional-on-observed, no causal/netreturn/calibration/strategy claim
```

Detailed vectors/readsets можно вынести в один compact content-addressed artifact. Не создавать отдельную scientific transaction на каждый bootstrap draw/episode. Нулевые числа — legitimate values, UNKNOWN — не zero. Инфинити/NaN не сериализуются как scientific result.

### 11.2. Commit

Result bytes сначала публикуются immutable с hash/readback. Затем **одна** ResearchStore transaction связывает завершение reservation/trial, RUN_COMPLETED/passport, RESEARCH_ARTIFACT и необходимые EXPERIMENT_METRIC/EVIDENCE_BINDING. Это один coherent completion, не три независимых успеха.

Каждый DIRECT carrier несёт exact experiment definition hash, binding/core/sample/trial/run identity и ссылку на один проверенный result. Не печатать в трёх carriers разные generic `observed_n` для A/C/total: A/C counts namespaced, один authoritative population object. Иначе generic dossier получает ложный CONFLICT.

Стоимость записи/дублирование payload минимизировать: один полный source-owned result и небольшие allowlisted projections. Reference consumer проверяет существование, hash, schema и identity, не только наличие `artifact_id`.

### 11.3. Typed projection, не generic «ключи присутствуют»

Для новой capability consumer validates complete result/lineage chain до использования её scientific fields. Отсутствующий artifact/неподтверждённая reservation/чужой spec/query/sample/hash → UNKNOWN/CONFLICT, не PRESENT. Правила старых capabilities не переопределять этим repair.

В ordinary dossier должны реально появиться подтверждённые внутри scope вещи: result, population/coverage/reasons, uncertainty intervals, robustness diagnostics, exposure/chronology и evidence class. У валидного `INSUFFICIENT` результат присутствует как **недостаточность**, а не «чисел нет, значит всё MISSING»; отсутствующие интервалы не объявлять вычисленными.

`PRESENT` означает доказательство доступно и связано, а не «пройден scientific gate». Пример: coverage 93.75% — корректно измеренная missingness и корректный terminal INSUFFICIENT, не missingness PASS.

**Новые domain-specific eligibility условия:** synthetic result, unsupported/invalid/insufficient confirmation или невалидная result lineage не разрешают promotion consideration даже при искусственно заполненных остальных generic keys. Добавить bounded guard этого capability/result type, не менять глобальную evidence policy ради его успеха. В real-positive случае всё равно нужны все существующие ENTRY/EXIT/COST/EXECUTION_REGIME и остальные gates.

Missing execution evidence не выставлять `NOT_APPLICABLE`, чтобы сделать PROMOTE зелёным. Положительная ассоциация не доказывает fillability или costs. Synthetic domain должен оставаться visible и non-promotable во всех downstream views.

### 11.4. Owner readback

Через обычный locator владелец видит question, exact sample interval, сколько episodes/mints/blocks, обе группы, effect/CI, local terminal, limiting reasons, текущую возможность resume и отсутствие trade authority. Для pending trial видны consumed allowance и NEXT, а не ложный NO_RUN.

Достаточно небольшого блока существующего dossier/CLI: без нового dashboard и runtime LLM translation. PAUSE/REJECT/REVISE пишутся existing FactoryApplication command по текущему snapshot. Тест PAUSE/replay/STALE и запрета PROMOTE использует реальные producer records, не authored scientific payload.

Cold `show/read` не читает исходные target values, не делает новый bootstrap, не создаёт store/projection и не переписывает trace. `execute/resume` — fresh authority action, `show` — historical read; это разные операции.

## 12. Публичная операционная поверхность

Предпочесть расширение существующего `scripts/hypothesis_fast_lane.py`, если это оставляет простой маршрут. Иначе один тонкий `scripts/list_a_confirmation.py` как transport к тому же application/producer owner; не две независимые реализации orchestration.

Необходимые операции, независимо от выбранного CLI spelling:

| Операция | Эффекты |
|---|---|
| `prepare` | Metadata validation/compile; immutable binding artifact при явной команде, no look/no grant |
| `authorize` | Exact local grant/revoke через approved owner path, no values |
| `classify` | Read-only readiness/current checks, no target coverage/no reserve |
| `submit` | Same production runner/registered capability; reservation → actual method → completion |
| `status/show` | Verified saved state/result, zero new values/evaluator/writes |
| `resume` | Exact trial/binding + current checks; same charge, new technical attempt только при необходимости |

В выводе: `execution_status`, `protocol_terminal`, `reason_codes`, `trial_id`, `run_id`, `execution_binding_sha256`, `scientific_charge`, `new_evaluator_invocation`, `domain`, `next_action`. Не заставлять owner строить JSON через private Python imports.

Повтор готового result не требует нового owner разрешения на научный look: look уже потрачен; действует право readback. Повтор execution request проверяет current authority и отказывает либо возвращает saved terminal согласно contract, не вновь вычисляет результат. Не запрашивать owner phrase на каждую внутреннюю инженерную фазу.

## 13. Минимально достаточное доказательство

### 13.1. Один небольшой native vertical suite

Создать **новый** deterministic synthetic fixture под новым input port. Не запускать старый исчерпанный Forge smoke; не требуется 139-point collector run на несколько виртуальных месяцев, если source contract надёжно задаёт exact admitted census и необходимые native points. Synthetic fixture авторит только входные observations/provenance/controlled test grants; не ready result, reservation, metric или dossier.

Проверяемый transport пишет и читает настоящие native Parquet/manifest/schedule/source metadata в том формате, который production binder принимает. Sample completeness/role validation, CLI, reservation, method, writer и consumer — production. Подготовка каждой case фиксируется до submit. Ожидаемые IDs/masks/returns вычислены из входной таблицы, не извлечены из product result.

**Рекомендуемый основной skeleton:** 32 admission дня через 48h, по 8 episodes в день: 4 A и 4 C. Итого **256 episodes, D_A=D_C=128**, 32 contributing blocks для каждого h/группы. Один A mint повторить через 8 дней в допустимом weekly cycle: A distinct mint=127, C=128; новый episode_id и отдельный contribution.

Virtual T0 например с 2026-11-02 00:15 UTC, последующие строки через 15m, следующие admission days через 2d; последний день — 2027-01-03. Это test clock, не прогноз будущего рынка. Source-side preregistration/exposure/witness clocks согласовать с этим миром. Нет ожидания календарных дней. Sampling/admission constraints в fixtures сохраняются.

Input projection минимальна по потребителю: census всех declared admissions; identity/list metadata; нужные native decision-prefix cells и E14400 PRICE. Не материализовать неиспользуемые market columns. Если выбранный реальный serializer требует дополнительные closure rows, заполнить их штатной synthetic source semantics; не подделывать closure. Уменьшить storage посредством existing serializer/сжатия, не посредством сокращения научных floors.

Три **обязательных** cases, каждая с собственным isolated study/grant, при неизменном method core:

| Case | Вход | Ожидаемый результат |
|---|---|---|
| POSITIVE | Pdecision=8; A exit=9, C exit=8; known metadata | delta=1/8, conditional supported при всех nonempty replicates; реальные CI/leave-one computed |
| NULL | Pdecision=8; A/C exit=8 | delta=0; `ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY`, не synthetic PROMOTE |
| INSUFFICIENT | POSITIVE, но 8 из 128 A targets typed-missing | D_A=128 прежний, observed_A=120, coverage .9375; `INSUFFICIENT`, no zero imputation |

Полезная дешёвая вариация в том же suite: 6 missing из 128 даёт coverage .953125 и gap .046875; при остальных достаточных inputs результат не блокируется чужим 100%-coverage правилом. Negative/ambiguous numeric terminals и boundary predicates также покрываются pure-method/table tests; отдельные большие worlds для каждого не нужны.

Геометрия skeleton, seeds, ranks и Fraction gold проверены при подготовке этого плана. Это model/design checks, **не выполнение будущего producer и не квалификация pinned CPython3.13.14**. Executor выполняет accepted RNG/calculation на своём qualified runtime; empty replicate не скрывает ради ожидаемого POSITIVE.

### 13.2. Самый ценный E2E witness

```text
registered Git definition
 -> production prepare from native sample files
 -> exact synthetic grant through real admission API
 -> ordinary CLI / DocumentRunner / capability dispatch
 -> committed reservation observed before first actual value read
 -> 4096 + 4096 real method replicates
 -> committed result + typed scientific records
 -> new process ordinary dossier
 -> PAUSE persisted; PROMOTE refused
 -> completed repeat: 0 evaluator, 0 target reads, 0 new charge/records
```

Этот witness обязательно positive и не завершается одним `READY`. NULL и INSUFFICIENT проходят тот же pipeline до сохранённого local terminal/dossier. Никакого test-side whitelist «считать payload научным».

### 13.3. Risk matrix — можно параметризовать, не создавать тест на каждую строку

| Риск | Минимальный oracle |
|---|---|
| Wrong formula/quantile/resampling | Fraction weighted gold 1/5; ranks; fixed-draw non-degenerate vector; seeds; full positive/null native runs |
| Future leakage/complete-case bias | Exact A/C IDs и D неизменны при смене target values/missingness; input label oracle |
| Identity/role laundering | foreign sample/query/core/schedule/definition, conflicting duplicate, exploratory forbidden source — отказ до values |
| Current authority/provenance | missing/incomplete/current revoked grant or inventory — отказ до values; supplied `COMPLETE`/`untouched` не authority |
| Chronology | strict boundary equality, overlapping info/labels, naive time/late publication masquerade, UNKNOWN allowance — typed refusal |
| One scientific attempt | два настоящих процесса на одном study: один evaluator/charge; loser видит typed busy/existing state |
| Crash before/after exposure | kill после durable reservation и после первых values: same trial/charge; original immutable identity only |
| Crash after result/before manifest | orphan не qualifying; eventual one atomic completion |
| Response loss after commit | fresh process exact saved replay без evaluator/target reads |
| Result consumer | wrong/missing result hash/ref, foreign run, stale snapshot, conflicting carrier; source-owned result остаётся единственным evidence owner |
| False promotion | synthetic/NULL/INSUFFICIENT не проходят consideration даже при дополнительных generic fields; execution evidence не fabricated |
| Legacy regressions | выбранные v1.4 readiness/missing/current protection/replay + existing dossier identity/decision tests |

Для before-values отказов oracle находится на **реальном file reader**: instrumentation считает реальные selected columns/rows/read phase. Отдельный canary намеренно вызывает forbidden read и должен быть пойман. Counter, который producer сам выставил в 0, доказательством не является.

Crash injection допускается на двух-трёх самых близких existing production boundaries; не строить fault-injection platform. Reservation-before-values проверяется fresh reader/record readback, concurrency — настоящими процессами, не последовательными mock calls.

### 13.4. Необходимая независимость

Числовой oracle использует literal inputs/Fraction и заранее заданные draws, не вызывает production helpers. Membership oracle строится до submit по input truth и native episode identity. Consumer verification читает committed records и result bytes, не строку success. Cold replay наблюдается новым процессом.

Требование — достаточное evidence, не универсальный TDD/100% coverage. Existing tests сначала; новые durable checks закрывают именно новые риски. Можно три файла: method tests, admission/reservation tests, один vertical test. Smoke helper не должен становиться больше producer из-за множества почти одинаковых worlds.

## 14. План реализации — один атом, без искусственных approval-пауз

### P0. Привязка и самый дешёвый probe

Прочитать AGENTS → harness/policy → semantic routes → S4/S5 и F01. Подтвердить exact base и отсутствие accepted confirmer. Зафиксировать authoritative owners и точный write set. Найти existing input/authority/locking primitives; нет нового tooling по умолчанию.

Зафиксировать три gaps, которые этот атом закрывает сам: confirming-compatible input binding, pre-values reservation, substantive result consumer. Не останавливаться на их ожидаемом отсутствии. Проверить locked runtime и возможность небольшого source fixture до больших scaffolds.

**Evidence P0:** frozen core/seeds; minimal schema/metadata test, который не требует real data. Ошибку source-role нельзя «исправить» override.

### P1. Вертикальный проход без лишних ветвей

Создать definition/schema/capability registration и runtime binding/typed source port. Реализовать минимальный POSITIVE end-to-end с production reservation, accepted method, atomic result/evidence и cold ordinary dossier. Synthetic grants через реальный validator. Metadata/authority bad inputs fail closed уже на этом шаге.

**Evidence P1:** действительный positive result и его source-owned records, не private helper. До этого не собирать большой delivery packet вокруг заглушек.

### P2. Failure и exact semantics

Добавить NULL/INSUFFICIENT, 95%-coverage guard distinction, independent numeric vectors; same-mint identity, chronology/protection/role conflicts. Реализовать same-trial resume и concurrency, проверить result-before-manifest/response-loss boundaries. Typed consumer не принимает чужие или неподтверждённые scientific payloads.

**Evidence P2:** таблица §13 без неподтверждённых PASS. Failing case исправляется в production owner и повторяется тем же путём; новый hook только если существующей точки недостаточно.

### P3. Propagation и delivery

Обновить definition/Catalog/routes/owner guide и необходимые obsolete «producer not implemented» ссылки с историческим scope. Старый frozen core/sample/ref не переписывать. Выполнить targeted legacy checks, risk-routed independent reviews, required machine gates на exact candidate. Полный local gate не дублировать на каждом commit.

**Evidence P3:** краткий owner report, replay/readback procedure, компактный proof, measured resource scope, source/current qualification hashes. Остановиться на exact merge phrase только после readiness; deploy/real run не следует из merge.

## 15. Managed write set и что читать, но не переписывать

Это bounded proposed write set, а не разрешение менять каждый файл. Executor материализует точные paths по current Git до product writes, исключает ненужные и не расширяет scope скрытно.

**Новые intended owners:**

```text
docs/tasks/LIST_A_CHRONOLOGICAL_CONFIRMING_PRODUCER_V1.md
docs/design/LIST_A_CHRONOLOGICAL_CONFIRMING_PRODUCER_V1_PRD_SSD.md
docs/contracts/list_a_confirming_execution_v1.md
catalog/schemas/experiment_spec_v1_5.schema.json
catalog/schemas/list_a_confirmation_input_v1.schema.json
catalog/schemas/list_a_confirmation_result_v1.schema.json
configs/experiment_specs/list_a_chronological_confirmation_v1.yaml
src/solana_alpha_lab/factory/list_a_confirmation.py
src/solana_alpha_lab/factory/list_a_confirmation_inputs.py
src/solana_alpha_lab/factory/list_a_confirmation_method.py
tests/test_list_a_confirmation_method_v1.py
tests/test_list_a_confirmation_admission_v1.py
tests/test_list_a_confirmation_vertical_v1.py
tests/fixtures/list_a_confirmation_v1/**
docs/evidence/list_a_confirming_producer_v1/**
docs/reports/list_a_confirming_producer_v1/**
```

**Existing direct consumers / registration:**

```text
configs/experiment_capability_registry_v2.yaml
src/solana_alpha_lab/factory/experiment_spec.py
src/solana_alpha_lab/factory/lane_classifier.py
src/solana_alpha_lab/factory/capabilities.py
src/solana_alpha_lab/factory/document_runner.py
src/solana_alpha_lab/factory/data_resolver.py
src/solana_alpha_lab/factory/run_passport.py
src/solana_alpha_lab/factory/experiment_evidence.py
src/solana_alpha_lab/factory/application.py
src/solana_alpha_lab/factory/research_workbench.py
src/solana_alpha_lab/factory/lifecycle_projection.py
src/solana_alpha_lab/factory/workbench.py
scripts/hypothesis_fast_lane.py
```

`application/workbench/lifecycle` только по реальной необходимости обычного readback/typed guard/definition registration; не переписывать их целиком. Один новый thin CLI допустим вместо расширения old CLI, не дополнительно к конкурирующему маршруту.

**Native helpers — по exact proof необходимости:** `opportunity_episode_release.py`, `opportunity_episodes.py`, `hfic_research_scope.py`, `hfic_temporal_discovery.py`, `research_store.py` — public value-neutral facade/structural reuse/locking, без изменения legacy scientific semantics. Не изменять collector/live schedule/protection defaults ради synthetic passage.

**Durable propagation:** relevant Catalog assets, manifest, generated edges/maps; одна operator guide секция и ссылки Forge/Critic только где они выбирают дальнейший маршрут. `docs/contracts/list_a_chronological_confirmation_v1.md` — link на новую implementation и явное historical/current различие, scientific method прежний. Не копировать этот PRD одновременно в task и contract целиком.

**Read-only scientific truth:** `configs/list_a_chronological_confirmation_v1.yaml::protocol_core`, historical sample UNBOUND и source pins; receipts предыдущих science/audit campaigns. Для dependency drift писать новое qualification evidence. Если native delivery gate требует затронуть exact historical delivery metadata, допустима лишь явно адресованная append-only dependency notice с frozen original ref/hash, без переписывания старых checks/authorization; такой path включается до final review. Не менять machine gate, чтобы пропустить pin.

## 16. Compatibility, безопасность и rollback

- Новые 1.5 semantics изолированы; old 1.0–1.4 schemas и existing fingerprints/replay meanings не мигрируются автоматически.
- Fixed-time replay остаётся exploratory. Confirmation не использует `FROZEN_EVIDENCE_REPLAY` и не наследует его `new_scientific_look=false`.
- Result/source/current protection/implementation binding проверяются у owners; raw hashes и canonical semantic hashes не взаимозаменяемы.
- Все paths в input refs relative/logical, contained; traversal/symlink/junction escape и foreign roots — refusal. Источники read-only. Никаких secrets в artifacts/logs.
- No network/provider/signing/real money. Test процесс получает только synthetic roots и необходимые immutable code/runtime, не home/credentials/production mounts.
- Error после reserve не стирает charge/возможный exposure; до reserve не выдумывает негативный научный verdict.
- Разработческий revert убирает новый code/schema/registry route, но не удаляет trials/reservations/results. Historical readback на compatible reader сохраняется; pending real trial после rollback не считается отменённым/untouched.
- Поддержка результата старой версии — explicit reader/contract; неизвестная версия даёт typed unsupported, не coercion к legacy.

## 17. Ресурсы и доказательства без новой бюрократии

Новая инженерная кампания, не продолжение исчерпанного MAIN budget #404. Это не разрешение обнулить прежние scientific counters: старые кампании остаются неизменны, а новые synthetic cases явно именованы и считаются отдельно.

Рекомендуемый envelope для этого атома: target incremental owned files ≤256 MiB; **forward hard cap 1 GiB** для нового checkout/proof/scratch целиком, с existing shared runtime/image/cache отдельно. Это проектное предложение, принимаемое starter, не заднее изменение старых 512/640 MiB. Cap относится к измеренной allocation принадлежащих атому файлов (checkout/proof/scratch и owned writable layers/volumes с identity dedup), а не к обещанию физического размера общего Docker VHD. Неизвестный размер внутри измеряемого scope блокирует продолжение; shared preexisting image/cache, directory metadata и физический VHD growth раскрываются отдельно и не объявляются нулём. Изолированная actual FS с понятным allocation предпочтительнее новой Docker-сборки.

Переиспользовать existing locked interpreter/dependencies; заранее настроить `UV_PROJECT_ENVIRONMENT`, чтобы hook не создал ещё одну .venv. Hooks не отключать. Docker только если он действительно нужен для безопасной изоляции; image build/pull/install вне default authority. Не строить новый resource watcher, если текущий launcher уже предоставляет необходимые bounds.

Fixture размер выбирается по числу различных contributing cluster labels/blocks, не по количеству гигабайт raw data. Нет обязательства собирать все поля и всю 139-point траекторию. Общие immutable inputs переиспользовать; mutable stores/grants/fault specimens не hardlink между cases. Runtime attempts сохранять в unique directories.

Scientific allowance = **1 per frozen study**, adaptive=0. POSITIVE/NULL/INSUFFICIENT — три заранее объявленных synthetic studies, не поиск выгодного результата. Fault/concurrency cases — controlled variants/continuations с явным учётом technical invocations и charges. Unit arithmetic runs не masquerade как scientific trials. Повтор тестов/CI сохраняет свой engineering receipt; реальные studies не затрагиваются.

Существующий автоматический cleanup обычных unit-test temporary directories допустим только для вновь созданных disposable fixtures этого тестового запуска. Это не разрешение удалять именованные acceptance stores, новые значимые failed-run witnesses или прошлые audit campaigns. Основные acceptance/fault receipts и их воспроизводимые входы сохраняются; нет требования архивировать навечно каждую дублирующую temp DB unit test.

Достаточен компактный Git packet: acceptance matrix, exact source/implementation refs, arithmetic gold, один positive/negative/insufficient result summary, reservation/recovery/readback witnesses и reproduction commands. Полные stores/raw transcripts не тащить в Git. Значимое negative evidence и charge ledger сохраняются; не копить десятки одинаковых worlds для формального PASS.

## 18. Definition of Done и review

**Все обязательные требования:**

- [ ] Production route registered и reachable через ordinary entrypoint; это не только test helper.
- [ ] Git definition штатно discoverable; binding/sample/grant/run остаются в data plane с exact identity.
- [ ] Compatible native input port реализован; exploratory/forbidden/unknown sources не принимаются за подтверждающие.
- [ ] Preflight/prepare не вскрывают outcomes; reservation подтверждена committed readback до первого значения.
- [ ] POSITIVE/NULL/INSUFFICIENT реально рассчитаны по frozen method; 4096×2/nearest-rank/shared weights/support/missingness/leave-one проверены.
- [ ] Exact A/C/episode counts и masks проверены независимо; repeated mint не схлопнут; target не меняет D.
- [ ] Concurrent same-study запуск не даёт второго evaluator/charge; crash/resume/replay сохраняют историю и original identity.
- [ ] Atomic final result/passport/substantive evidence прочитаны новым процессом; orphan/forged/foreign result не qualifies.
- [ ] Ordinary dossier показывает result/limits и правильный local terminal, не только generic INCONCLUSIVE; scientific evidence не получают лишнюю authority.
- [ ] Synthetic/NULL/INSUFFICIENT не позволяют promotion consideration; ENTRY/EXIT/COST/EEB не подделаны.
- [ ] Legacy targeted regressions и required independent review/machine gates проходят на exact candidate по Git policy.
- [ ] Durable navigation/contracts/CLI recovery обновлены в том же атоме; resources/counters/failures измерены и сохранены.

**Не является DONE:** missing real sample как excuse не реализовывать producer; schema-only/new enum-only patch; PRIVATE_METHOD_PASS; manual EVIDENCE_BINDING для демонстрации dossier; claim `FULL_PRODUCT_PATH` до стратегии; новый аудитор вместо нового production consumer.

Review roles: code, goal/DoD, architecture со scientific semantic premise; owner-UX для новых user-facing prepare/status/recovery surfaces по policy. Architecture reviewer независимо отвечает:

1. Может ли другой sample/query/role или current revoke попасть в computation?
2. Может ли crash/new code/name получить вторую «первую» проверку?
3. Не подменён ли conditional-on-observed estimand complete cases или 100%-coverage gate?
4. Может ли PASS unit tests скрыть неправильный bootstrap/nearest-rank/cluster weighting?
5. Может ли корректный result carrier без реального source-owned proof получить PRESENT/PROMOTE?

LLM согласие не oracle; exact machine/readback witnesses приоритетны. Не запускать ещё один отдельный широкий audit cycle для тех же вопросов.

## 19. Handback, STOP и следующий шаг

Финальный ответ executor:

```text
Result: IMPLEMENTED_AND_VERIFIED_IN_SYNTHETIC_SCOPE | BLOCKED_<exact reason>
Exact base/head/PR:
New ordinary command + returned locator:
POSITIVE / NULL / INSUFFICIENT terminals and numeric gold:
Reservation-before-values / one-evaluator / crash-resume / cold replay:
Dossier substantive evidence and promotion refusal:
Legacy checks / reviews / exact-head CI/readiness:
Real sample / real executions / authority: UNBOUND / 0 / false
Owned resources / retained attempts / residuals:
One NOW and one WATCH:
```

**STOP:** требуется изменить accepted estimand/floors/RNG/chronology/core; открыть реальные values/credentials/providers; изменить live collector/protection или глобальную authority; добавить платформу/вторую БД/новую dependency; превышен объявленный envelope; unsafe storage/process isolation; невозможно обеспечить required native consumer без существенного изменения соседнего продукта. Тогда exact evidence + bounded replan, а не молчаливое снижение DoD.

Ожидаемые отсутствующие input binding/reservation/consumer внутри данного scope **не STOP**, а то, что надо реализовать. Failed scientific synthetic case диагностировать, не перебирать seeds/данные и не переименовывать PASS.

После выполнения **NOW:** использовать новую capability для одного отдельно разрешённого sample-readiness/confirmation решения при наличии пригодного source-bound sample. **WATCH:** real source provisioning и real run по exact data authority; положительный proxy затем отдельно требует execution feasibility/strategy gates. Ещё один общий smoke не назначается автоматически.

## 20. Готовая команда coding executor

Передача владельцем следующего блока вместе с документом — scoped implementation request. Сам факт подготовки документа Chat не является разрешением mutate Git/runtime.

> **EXECUTE `LIST_A_CHRONOLOGICAL_CONFIRMING_PRODUCER_V1` по приложенному PRD+SSD целиком.**
>
> Цель — реализовать native confirming producer принятого List A метода: production input binding/authority, durable reservation до первого значения, single evaluator, accepted calculation, source-owned scientific records и ordinary cold dossier. Это продуктовый repair, не новый аудит.
>
> Принимаю решения D1–D8 и version-isolated Spec 1.5 / новую capability, включая разделение Git definition и runtime execution binding. Scientific core, thresholds, chronology, seeds и смысл legacy 1.0–1.4 не менять. Уточнение contributing labels и typed confirmation eligibility из этого документа входит в design.
>
> Разрешаю необходимую локальную реализацию и обычный Git delivery внутри exact task/write set; создание контролируемых synthetic sample envelopes и их scoped grants через production validators для acceptance. Реальные samples/values/holdouts, provider, credentials, live protection/collector, deployment, стратегии/торговля и деньги не разрешены. Наличие реального sample не является условием начала разработки.
>
> Сначала перепривяжи задачу к текущему Git через AGENTS и semantic routes, материализуй exact task, проверь reuse и locked runtime. Закрой вход и выход capability в том же атоме; не останавливайся на ожидаемом отсутствии producer/binding/consumer и не подменяй их test helpers. Реализуй самый короткий положительный production path, затем required failures и propagation.
>
> Synthetic acceptance: три заранее заданных cases POSITIVE/NULL/INSUFFICIENT; независимые arithmetic/membership oracles, реальная reservation-before-values, process concurrency, crash/resume, atomic completion и fresh-process ordinary readback. Старые audit stores/attempts не повторять и не переписывать. Считать new technical runs и scientific charges явно.
>
> Для новой инженерной кампании принимаю forward hard cap 1 GiB incremental owned files с целью ≤256 MiB и existing runtime/cache отдельно. Старые cap breaches/charges остаются историей. Не создавать новую .venv/image/dependency и не отключать Git hooks; cleanup прежних данных не разрешён. При реальной границе риска/authority остановись с exact checkpoint.
>
> Не объявляй synthetic supported result alpha, accepted real confirmation или разрешением PROMOTE. Не выполняй merge без новой exact-head owner phrase после CI и machine readiness. На выходе — работающий код, compact proof/readback и короткий owner handback из §19. Рекомендуемый effort — SOL_XHIGH; метод проверки выбирай по риску, без универсальной TDD-церемонии.

## 21. Проверяемые исходные references

Все Git references ниже относятся к planning base `07c81a99f2d0f385df66de2e1a5254e224c6b3b3`, если явно не указан исторический ref. Конкретные function names — прочитанные owners; новые имена §5/§15 — design proposal.

- **S1 — итог #404 / F01:** [OWNER_REPORT](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/docs/reports/science_lifecycle_smoke_v1/OWNER_REPORT.md), `docs/evidence/science_lifecycle_smoke_v1/{summary,chronology,findings}.json`, [repair proposal](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/docs/reports/science_lifecycle_smoke_v1/REPAIR_PRD_SSD.md).
- **S2 — predecessor repair:** `docs/reports/episode_native_required_outcomes_v1/OWNER_REPORT.md`, `tests/test_episode_native_required_outcome_contract_v1.py`.
- **S3 — 1.4 boundary:** [episode_native_required_outcomes_v1.md](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/docs/contracts/episode_native_required_outcomes_v1.md), `episode_required_outcomes.py::project_episode_required_outcomes`, `verify_frozen_episode_sources`.
- **S4 — accepted science:** [list_a_chronological_confirmation_v1.md](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/docs/contracts/list_a_chronological_confirmation_v1.md). Его метод и precedence авторитетнее примеров этого документа при обнаруженном противоречии.
- **S5 — exact core/seeds:** [configs/list_a_chronological_confirmation_v1.yaml](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/configs/list_a_chronological_confirmation_v1.yaml). Historical source pins внутри core — на `ba87f8e339d5cc3aa55322801ae56e3f92369446`, не новый implementation head.
- **S6 — existing execution:** `src/solana_alpha_lab/factory/document_runner.py::{RunContext,DocumentRunner.start_document,_frozen_hfic_replay_lineage}`, `capabilities.py::execute_capability`, `hfic_temporal_discovery.py::{bind_frozen_fixed_time_inputs,run_temporal_fixed_time_from_spec,execute_fixed_time_proxy_capability}`.
- **S7 — storage/recovery owner:** [research_store.py](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/research_store.py), public `append`, `find_record`, `writer_lease`; `docs/contracts/research_write_lookup_v1.md` и existing stale-writer recovery policy. OperationalStore не владеет научной истиной.
- **S8 — native source:** [opportunity_episode_release.py](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/opportunity_episode_release.py), `opportunity_episodes.py::resolve_point`, `hfic_research_scope.py`, `hfic_temporal_discovery.py::project_episode_decision_prefix`; `docs/contracts/opportunity_episodes_jupiter_v1.md`.
- **S9 — result consumer:** [experiment_evidence.py](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/experiment_evidence.py), `compose_experiment_dossier`, `_build_obligations`, `science_guard`; `docs/contracts/experiment_evidence_decision_v1.md`.
- **S10 — definition/operator path:** `research_workbench.py`, `lifecycle_projection.py`, `application.py::record_research_decision`, [scripts/hypothesis_fast_lane.py](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/scripts/hypothesis_fast_lane.py), `run_passport.py` canonical hash/identity helpers.
- **S11 — navigation/authority:** `AGENTS.md`, `docs/FACTORY_SEMANTIC_MAP.md`; routes `SEM-EXPERIMENT-CAPABILITIES`, `SEM-OWNER-LIFECYCLE`, `SEM-PRIOR-WORK`; `configs/experiment_capability_registry_v2.yaml`; exact Delivery Harness policy и `control/owner_attention_gate_v2.yaml`.

### Checkpoint этого планирования

**Goal/mode:** подготовить implementation-ready дизайн одного confirming atom, DESIGN. **Verified base:** `07c81a99…`, #404 merged. **Результат:** этот документ и проверенная арифметика skeleton/seeds/ranks/weighted example. **Не выполнено:** product code, новый producer, product tests, real data/read/confirmation, CI qualification или Git mutation. **Resume point:** executor starter §20 → current Git binding → P0; не новый общий research и не повтор smoke #404.
