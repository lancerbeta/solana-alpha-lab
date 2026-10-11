---
artifact_id: LIST_A_CONFIRMATION_PROTOCOL_FREEZE_V1
artifact_version: '1.0'
artifact_type: OWNER_PROPOSED_PRD_SSD_AND_EXECUTOR_HANDOFF
as_of: '2026-10-12'
planning_mode: DESIGN
repository: lancerbeta/solana-alpha-lab
verified_planning_main: ba87f8e339d5cc3aa55322801ae56e3f92369446
source_packet_sha256: 1a8f63840b18fcd6bed11c2deea2a2244092b81dfcc0f8f092906d712053a71f
execution_scope: PROTOCOL_AND_METADATA_BINDING_ONLY
empirical_confirmation_ready: false
scientific_look_authorized: false
product_runtime_mutation_authorized: false
---

# List A: заморозка научного протокола
## Единый PRD + SSD + план доказательства и передачи

**Рекомендуемый outcome:** превратить предложение из `OWNER_REVIEW_PACKET.md` в однозначный, проверенный до просмотра результатов научный контракт. Установить, что именно означает List A, какие реальные источники подходят, что о них уже видели, какую величину будем считать и какие результаты допустимы. Выпустить либо полностью связанный протокол, либо законченный технический дизайн с доказанным препятствием привязки данных. Не оставлять «почти READY» с выдуманными cohort IDs, молчаливыми defaults или непросмотренным источником, объявленным untouched.

**Это не ещё один широкий аудит и не реализация всего empirical confirmer.** Текущий атом материализует научный контракт, его конфигурацию и компактное воспроизводимое evidence. Production evaluator, substantive dossier adapter, EEB assembler, торговый runtime и рыночный запуск в него не входят. Их интерфейсные обязательства ниже достаточны, чтобы не заложить несовместимость сейчас; они не являются разрешением их реализовать.

**Самое важное для владельца:** здесь проверяется предложение «membership A связано с положительным будущим ценовым контрастом», а не «существует прибыльная стратегия». Положительный результат этой будущей проверки не создаёт PROMOTE, StrategyVersion, PAPER activation или торговое разрешение.

**Степень готовности этой постановки:** пригодна для самостоятельного выполнения contract/metadata-атома после стартовой команды владельца. Точные real data bindings, история exposure и разрешённый доступ к ним не установлены в этой сессии. Поэтому empirical implementation/run не объявляются готовыми заранее.

---

## 1. Основание, проверенные факты и поправки к пакету

### 1.1 Источники и приоритет

Основной вход — `SCIENCE_TO_TRADING_EVIDENCE_CONTINUITY_PROBE_V1_2026-10-12.zip`, прежде всего `OWNER_REVIEW_PACKET.md`. Его SHA256: `1a8f63840b18fcd6bed11c2deea2a2244092b81dfcc0f8f092906d712053a71f`. Пять файлов, перечисленных в `package_manifest.json`, независимо проверены по размеру и SHA256. Это проверка целостности переданного пакета, **не повторная проверка всех 44 Git-источников или product execution**.

Текущий read-only Git readback при планировании: `main@ba87f8e339d5cc3aa55322801ae56e3f92369446`. Повторно прочитаны `AGENTS.md`, semantic map, scientific disposition выбранного маршрута, существенный участок `DocumentRunner`, metadata resolver и reference tests. Прочие подробности source graph ниже происходят из приложенного packet и должны уточняться только по затронутым owners, а не через повторное чтение всей истории.

Authority при исполнении: exact owner task → effective frozen-base Git policy → этот принятый scope. Старый чат, научное предложение, branch state и комментарий в fixture не создают разрешений.

### 1.2 Что подтверждено

| Факт | Источник / граница |
|---|---|
| Reference List A — synthetic engineering question, не установленная рыночная association | Packet §1–3; `EpisodeFlowTests.look` и `authored_draft` |
| В reference fixture `A` соответствует `JUPITER:toporganicscore:5m` | `tests/test_hfic_list_aware_vertical_v1.py`, `CATEGORY` / `LIST_ID`. Это точная reference identity; её definition/version в реальном source ещё надо связать |
| Accepted chronological protocol выбранного маршрута не установлен | `docs/reports/forge_trust_closure_v1/SCIENTIFIC_DECISION.md`; это finding выбранного пути, не глобальное отсутствие любого OOS в SMIAL |
| Native proxy summary и technical `accepted_terminal_match` — разные результаты | `document_runner.py`: metric — terminal match, summary сохраняется как `RESEARCH_ARTIFACT(CAPABILITY_RESULT)` |
| Содержательный projection summary → science obligations не установлен в выбранном пути | Packet §2–3; `experiment_evidence.py`. Старый DIRECT-run-linkage repair сюда не подмешивать |
| Metadata resolver исследовательского корпуса ориентирован на current lineage / exploratory admission | `hfic_grounded_discovery.resolve_published_episode_binding`. Его нельзя назвать подтверждающим reader простым переименованием role |
| Market values, real-store metadata и native confirmer в исходном probe не запускались | `verification.json` / packet §1, §3 |
| Trading Closure — отдельный outcome | Packet описывает рабочую ветку на момент своего сбора. Её нынешняя готовность здесь не подтверждается |

### 1.3 Явные уточнения этого PRD/SSD

Ниже — проектные решения, а не исправленная задним числом исходная evidence.

| ID | Уточнение | Зачем |
|---|---|---|
| D01 | Начальный режим — `FIRST_PREREGISTERED_TEST`, пока не разрешён source-bound empirical development record. Имя атома остаётся историческим | Не называть synthetic fixture найденной alpha и не создавать фиктивную development sample |
| D02 | Reference A закрепляется как `JUPITER:toporganicscore:5m`; aliases не являются scientific identity | Не проверить по ошибке toptrending вместо toporganicscore |
| D03 | До values считаем только **верхнюю границу возможной достаточности** по разрешённым metadata. Target coverage и фактическая inferential support проверяются после отдельного look | Не читать outcomes ради «безобидного preflight» и не обещать sufficiency по числу файлов |
| D04 | Разделяем `protocol_core_sha256`, `sample_binding_sha256`, derived seeds и итоговую receipt identity | Убирает самоссылку hash→seed→hash и смешение физического файла со смыслом |
| D05 | Формула temporal purge/embargo имеет один явно названный anchor (§5), а не два неявно суммируемых периода | Устраняет неоднозначность исходного proposal; это не заявление о независимости выборок |
| D06 | Числа 30 clusters, 24/48 h, 4,096 replicates, 95% coverage — принятые для проверки design assumptions, не гарантия statistical coverage | Не выдавать инженерные screens за теорему или «industry standard» |
| D07 | Убираем из исходного proposal лимит «≤2 h / один metadata pass» | Работа ограничена outcome, полномочиями и ресурсной безопасностью, а не произвольным числом попыток |
| D08 | Проверяем короткий путь формирования/проверки **контракта**; большой trading E2E и настоящий pre-values reservation оставляем их production-атомам | Доказательство соответствует изменяемому объекту, не превращается в спектакль из всей Factory |

Численный estimator и правило решения исходного proposal сохраняются как рекомендуемый baseline с детализацией ниже. Изменять δ, universe, missingness claim, dependence rule или statistical thresholds исполнитель не может незаметно. До values изменение возможно только как явно выделенный meaning delta с обоснованием и необходимым owner acceptance.

---

## 2. PRD: цель и границы результата

### 2.1 Продуктовая проблема

У системы есть рабочий язык episodes, membership, price proxy и downstream trading machinery. Но без frozen scientific protocol два корректных исполнителя могут выбрать разные samples, способы оценки uncertainty и terminal conclusions. Тогда следующая серия ремонтов будет чинить не код, а несовместимые смыслы.

Этот атом должен снять такую неопределённость **до** empirical computation: принять одно значение вопроса и математического решения, связать данные и историю exposure, задать допустимый handoff следующему evaluator. Проверка «все поля заполнены» недостаточна.

### 2.2 Consumers

1. Владелец научного решения: понимает, что будущий результат разрешает утверждать и чего не разрешает.
2. Будущий native confirmer: получает exact protocol/sample identity и не выбирает метод по увиденному результату.
3. Dossier/scientific evidence owner: знает допустимый класс результата и не превращает proxy evidence в execution evidence.
4. Будущий executor: находит контракт через Git, а не через этот чат и не через временный Windows path.

Trading Closure — сосед, не implementer этого научного смысла. Оно не должно ждать реальной проверки List A для завершения своих независимых software obligations.

### 2.3 Scope текущего атома

Разрешённый после owner-start outcome: repo-grounded canonical task; один authoritative contract; одна versioned protocol config; exact доступные metadata bindings; independent расчёты и компактные contract checks; evidence/limitations; минимальная Catalog/navigation propagation; routine delivery по harness.

**Не входит:**

- чтение новых empirical price/return/target/feature values, empirical previews, запуск discovery/confirmation или изменение scientific look ledger;
- создание/модификация production confirmer, `DocumentRunner`, dossier whitelist, EEB schema/assembler, runtime policy, trading engine или protected assignment;
- выбор/покупка провайдера, сбор новой кампании, доступ к VPS, credentials, deploy, реальные сделки;
- широкое перепроектирование 03–05, новый DSL/statistics framework/registry/service;
- исправление соседнего незавершённого Closure/Catalog под видом своего scope.

### 2.4 Терминалы — не смешивать дизайн, данные и запуск

| Уровень | Что доказывается | Что не следует |
|---|---|---|
| `DESIGN_VALIDATED` — локальное поле отчёта, не новый глобальный enum | Method/criteria/config representation непротиворечивы и проверены на synthetic inputs | Real sample существует, не просмотрена или достаточна |
| `FROZEN_FOR_SEPARATE_AUTHORIZED_CONFIRMATION` | Все required real identity/exposure/metadata bindings разрешены; meaning принят; contract/config заморожены | Evaluator реализован, реальный look разрешён, эффект установлен |
| `BOUND_CONTRACT_NOT_READY` | Есть точный нерешённый binding/authority/feasibility/meaning gap с источником и следующей проверкой | Полный freeze состоялся; можно подставить fixture или latest cohort |

`DESIGN_VALIDATED` допускает полезное завершение дизайна при `BOUND_CONTRACT_NOT_READY`, но не masquerades as полный outcome. Формальный merge такого ограниченного результата не закрывает научный gap. Пустой config с `UNKNOWN` в обязательных fields не принимается за frozen protocol.

---

## 3. Полномочия и степени свободы

### 3.1 Что принимает стартовая команда

Стартовая команда в конце файла принимает **для contract-атома**, а не для рыночного запуска:

- conditional observational question из §4, δ=0, direction A > complement; экономическая достаточность не утверждается;
- repeated-mint episode estimand; отсутствующий empirical development не выдумывается;
- baseline estimator/sensitivity/support из §6 с указанными limitations;
- исправления D01–D08, metadata-only scope и отсутствие любых scientific look grants.

Точное имя real source root не нужно переписывать вручную из памяти владельца, если оно однозначно разрешается по canonical локальным read-only owners. Но permission на чтение root, историю exposure и смысл intended sample **нельзя вывести из факта, что путь существует**.

### 3.2 Матрица свободы

| Исполнитель выбирает самостоятельно | Требует meaning/authority boundary |
|---|---|
| Расположение временных проверок, структуру helper-кода, batching и порядок checks | Другой list/universe/estimand/δ; causal вместо predictive claim |
| Existing parser/helper и компактную форму metadata readset | Другую обработку missing targets, изменение inferential rule / minimum support |
| Нужные точечные повторения после изменённой причины отказа | Изменение роли/exposure источника, новое право на protected values или VPS |
| Изоляцию scratch и способ resource measurement | Покупку/установку новой зависимости, новые SaaS/API/платный compute |
| Дедупликацию evidence и минимальную Catalog propagation | Новую campaign, empirical look, sample selection по результатам |
| Уточнение moved paths и прочие semantically equivalent repairs постановки | Product code mutation вне write set, merge/deploy/history rewrite |

Промежуточный replan в пределах того же outcome и read/write authority — работа executor. Не требуется owner OK после каждого безопасного шага. На реальной boundary закончи независимую безопасную часть, сохрани checkpoint и сформулируй одно точное решение с рекомендуемым вариантом.

### 3.3 Бюджеты различны

Инженерная работа: без формального ограничения «два прогона», «два часа» или «ровно N тестов». Повторять только при приросте evidence: исправлена причина failure, закрывается новое material obligation или требуется воспроизводимость.

Научная работа **в текущем атоме: 0 looks**. `MAIN=1, adaptive=0` — контракт для будущего отдельно разрешённого эксперимента, не текущее разрешение. 4,096 bootstrap replicates — вычисления внутри одного будущего fixed analysis, не 4,096 новых гипотез; смена самого вопроса/метода не получает это исключение.

Resources: existing locked toolchain, по умолчанию stdlib + уже принятые repo зависимости. Никакого Docker ради маленького config. Перед существенной аллокацией оцени peak memory/temp disk и принадлежность resources. Прерывай конкретный unsafe lane, не компенсируй его повышением privileges. Нет безусловного права использовать весь хост или бесконечно расходовать деньги.

---

## 4. Frozen scientific meaning

### 4.1 Идентичность вопроса

Reference:

```text
population         = OPPORTUNITY_EPISODES
hypothesis_kind    = LIST_CONTRAST
reference_alias    = A
canonical_list_id  = JUPITER:toporganicscore:5m
membership_time    = EPISODE_T0
decision_point     = E1800
target_point       = E14400
field              = FIELD-USD-PRICE-001
estimand           = CONDITIONAL_EPISODE_WEIGHTED_PRICE_RELATIVE_CONTRAST
claim_form         = PREDICTIVE / OBSERVATIONAL, not CAUSAL
```

Alias resolution делается существующим semantic owner по pinned definition/schedule. Проверка test constant устанавливает reference intention, но не доказывает, что реальный source содержит совместимую definition/version. Отсутствует совместимый real list binding → exact gap, не auto-replace на trending/traded.

Для каждого episode i:

```text
r_i = P_i(E14400) / P_i(E1800) - 1
A = decision-eligible episodes с known TRUE membership в List A на T0
C = decision-eligible episodes с known FALSE membership в List A на T0
S_A, S_C = соответствующие episodes с admissible observed target
Δ = sum(r_i, i∈S_A)/|S_A| - sum(r_i, i∈S_C)/|S_C|
```

Comparator — complement **в том же declared universe**, не «все остальные токены Solana». UNKNOWN membership не попадает в C; неизвестный decision PRICE не становится zero или eligible. Excluded/unknown counts и причины сохраняются. Membership в B/C-списках не меняет A TRUE: AB/AC/ABC входят в A, если canonical condition именно `all_of:[A]`.

Поле denominator всегда указывает стадию: admitted → scope-known → decision-eligible → target-observed. Нельзя назвать `N` без этих distinctions. Target availability не участвует в eligibility и не исправляет прошлый signal.

### 4.2 Что не измеряем

Не causal effect попадания в список; не unseen-token generalization; не net return; не capacity; не returns портфеля с ограниченным числом слотов; не effect на всех admitted при неслучайных missing targets. Тайминг и weights остаются episode-based. Один mint может участвовать несколько раз; одинаковый episode с тем же hash участвует один раз, conflicting copy блокирует analysis.

`E14400` — четыре часа от T0. Разность nominal offsets E14400−E1800 = 12,600 секунд = 3.5 часа. Реальные decision/target availability deadlines вычисляет pinned `resolve_point`/schedule owner. Не задавать trading holding period «4 часа после входа».

### 4.3 Существует ли development evidence

Рекомендуемый default — `FIRST_PREREGISTERED_TEST`. Если найден ровно связанный empirical development record с accepted question/result/exposure provenance, зафиксировать его metadata и применимость; только после этого допустима формулировка independent chronological confirmation.

`NO_EMPIRICAL_DEVELOPMENT_RESULT` — утверждение только в исследованном scope. `UNRESOLVED_DEVELOPMENT_PROVENANCE` — другое состояние: нельзя превращать отсутствие ответа в доказанное отсутствие прошлых просмотров. Synthetic reference разрешает воспроизвести инженерный вопрос, но не создаёт real development dataset.

**Отсутствие development result не обязывает сначала сделать exploratory market run.** Первую hypothesis можно заранее проверить на пригодном непросмотренном sample. Потребуются те же exact meaning/exposure/data permissions, но не лишний промежуточный look.

---

## 5. Data binding, exposure и temporal separation

### 5.1 Порядок до outcomes

```text
canonical local locator / permitted metadata export
→ identity + schema/schedule/list-definition references
→ frozen and current protection assignments
→ exposure provenance scope and completeness
→ exact candidate sample definition
→ chronological/structural feasibility
→ freeze readiness report
```

Начинать с опубликованных manifests, schemas, assignments, ids, ledger headers и разрешённых projections. Не запускать exploratory resolver на protected source «чтобы посмотреть, что он вернёт». Разрешение metadata-only access отдельно от допустимости source для future look.

Если full records перемешивают metadata с values, используй existing column/field projection, которая не вычисляет и не возвращает outcomes. Если такой seam нет — запросить конкретный sanitized metadata export / narrower source. Не открывать весь Parquet/DataFrame ради пяти metadata колонок.

### 5.2 Что считаем metadata

**Допустимо при соответствующем read scope:** source/release/cohort IDs, schema and file hashes из manifests, declared time bounds, pinned schedule/definition, episode identity/T0, mint identity в минимальном локальном виде, protection assignments, metadata о prior look/reservation/result identity и explicit provenance. T0 membership mask допустима, если извлекается без numeric/target payload и нужна для bound universe/support upper bound.

**Не читать для preflight:** PRICE/HOLDERS/LIQUIDITY values, computed features, returns, target-observed/missing flags, result score/sign/p-value, Parquet min/max/statistics этих fields, sample `.head()`, embeddings/preview, автоматически создаваемые numeric summaries. Published prior empirical result не нужно повторно анализировать: для binding используется exact accepted claim ref, не новый outcome-derived selection.

Различать в evidence:

```text
metadata_fields_read
opaque_bytes_hashed
market_value_fields_deserialized
scientific_looks_created
```

Streaming SHA256 файла физически читает bytes. Это не чтение колонок/новый analysis само по себе, но не даёт права читать защищённый файл и не позволяет писать «physical reads=0». Предпочитай trusted manifest hashes. Для hash-only проверки protected/raw файла требуется разрешённый access; в receipt не выводятся contents.

### 5.3 Protection ≠ exposure

У каждого source два ответа:

1. **Protection/access:** какие roles/actions разрешены; какая current stricter assignment действует.
2. **Exposure:** что могли использовать для выбора этой hypothesis/method/threshold, какие prior looks/reservations/imports относятся к source и насколько полон этот учёт.

`holdout=false`, пустой список consumption IDs или отсутствие записи в одном ledger не доказывают untouched. Pending/crashed reservation означает potentially exposed в её scope. Смена journal/prompt/model/branch не возвращает data в untouched.

Если источник protected от exploratory reads, это **не обязательно** запрет навсегда использовать его в отдельно принятой confirmation. Freeze может описать точный protected sample и требуемую будущую role/authority, когда metadata доступна; он не меняет assignment и не вызывает values reader. У текущего exploratory reader его прежний DENY сохраняется. Неразрешённый конфликт owner/role или невозможность подтвердить exposure не получает `FROZEN`.

### 5.4 Sample binding

Binding должен содержать exact source-set membership: release/cohort/manifest refs, schedules, hashes и `[start,end)` UTC. Переименование presentation не меняет set; добавление новых cohorts — другая identity. `latest/current/all_available` в финальном empirical binding недопустимы.

Не выбирать самый выгодный/самый длинный удобный период. Если несколько semantically equivalent разрешённых windows подходят, применить до outcomes одно accepted deterministic правило. Рекомендуемый вариант: earliest admissible window после установленной exposure boundary с заранее заданным верхним временем/источниками. Численный конец/набор источников freeze связывает по действительному approved scope; сам этот документ их не выдумывает.

При отсутствии доступного подходящего closed sample: `BOUND_CONTRACT_NOT_READY`. Можно описать точное условие будущей доступности, но нельзя автоматически начать сбор, обещать ждать два месяца или считать будущие hashes уже связанными.

### 5.5 Однозначная chronology: проектное уточнение D05

Для empirical development/предыдущих относящихся к claim exposures получить:

- `dev_decision_max`: максимальный bound decision cutoff относящихся development episodes;
- `dev_target_available_max`: максимальный target availability/visibility deadline этих episodes;
- `E`: **один** conservative separation interval, вычисленный из pinned schedules как maximal target horizon от T0 плюс применимый lateness/visibility allowance. Если последняя часть неизвестна, E неизвестен; не подставлять ноль.

Рекомендуемое явное уточнение исходного proposal:

```text
separation_boundary = max(dev_target_available_max, dev_decision_max + E)
validation_information_start > separation_boundary
```

Здесь `validation_information_start` — самое раннее T0/feature-availability начало, используемое валидируемым вопросом, а не только дата готового label. Purge исключает overlap заявленных information/label intervals. **Не прибавлять E ещё раз к уже полученной separation_boundary.** Это явная консервативная policy, не математическое доказательство независимости. При ином принятом anchor policy меняется до look с rationale.

Для `FIRST_PREREGISTERED_TEST` без empirical development не создавать фиктивные dev instants. Проверить реальную exposure/protection границу и preregistration; condition развития не применима по явному основанию. Sample всё равно должен соответствовать accepted first-test design и быть не использованным для выбора вопроса.

Все offsets/deadlines считаются у существующего clock owner; UTC-aware values, half-open intervals, equality на strict boundary отвергается. Same mint across splits не purged лишь из-за identity: repeated-mint conditional episode claim сохраняется, overlap отдельно виден. Unseen-mint вопрос — новое решение.

### 5.6 Cheapest feasibility falsifier

До чтения targets вычислить разрешённые **верхние границы**: число возможных distinct mints, occupied calendar blocks и coverage metadata. Например, 14 полных epoch-aligned суток содержат 7 двухсуточных blocks; при требовании 30 это заведомо недостаточно независимо от цены и числа строк.

`upper_bound < threshold` → `BOUND_CONTRACT_NOT_READY / INSUFFICIENT_POTENTIAL_SUPPORT` до look. `upper_bound ≥ threshold` → лишь `SUPPORT_POSSIBLE_NOT_PROVEN`: после filters/missing targets support может исчезнуть. Не читать target missingness для превращения possible в actual pre-look.

Не подгонять threshold под доступную короткую историю. Если окно непригодно, сравнить cost/value дальнейшего ожидания и альтернативного вопроса до любого values read; не запускать method shopping.

---

## 6. Estimator, thresholds и terminal logic

### 6.1 Что замораживаем

Сохраняем предложенный packet baseline: episode-weighted mean contrast; двухфакторный crossed-cluster bootstrap по mint × frozen calendar time block; отдельные partitions 24 h / 48 h; fixed sensitivity, без выбора лучшего результата.

Это resampling групп зависимых observations, а не iid bootstrap строк. Owen обосновывает такое resampling для определённых crossed random-effects structures; это не гарантия корректного 95%-интервала для произвольного нестационарного рынка. Minimum cluster count тоже не устанавливает independence. Смысл ограничения сохраняется и в owner readout [E01, E02].

### 6.2 Точная арифметика baseline

Для partition h:

```text
block_seconds ∈ {86400, 172800}
block_id_i = floor(canonical_decision_at_i.unix_seconds / block_seconds)
cluster populations = distinct contributing mint ids / occupied block ids
B = 4096
```

Time labels сортируются численно, mint labels — по канонической идентичности в стабильном порядке. Нельзя использовать Python `hash()`, filesystem iteration order или локальную timezone.

В каждой replicate независимо выбираются с возвращением M mint labels из M и T time labels из T. Episode i получает weight `w_i = mint_multiplicity_i × time_multiplicity_i`. Для обеих групп weighted mean пересчитывается на **одном и том же** наборе resampling weights, затем берётся difference. Независимое resampling A и C потеряло бы общий time/mint dependence structure.

Не averaging готовых unweighted cluster means: при неодинаковом числе episodes это меняет episode-weighted estimand. Допустима оптимизация через `(mint, block, group) → sum_return, count` при доказанной эквивалентности численного порядка/правила rounding. Не материализовать B копий всех rows.

Generator — proposed stdlib `random.Random`, `randrange`, pinned supported Python/algorithm version. На каждой replicate сначала mint draws, затем time draws. Для каждого h отдельный seed:

```text
seed_h = int(SHA256(UTF8(protocol_core_sha256 + ':' + str(h))).hexdigest()[:16], 16)
```

`protocol_core_sha256` включает **seed derivation rule**, но не вычисленные `seed_h`, не свой hash и не final receipts. Derived seed проверяется повторным вычислением. Он не меняется ради более красивого interval.

Quantiles: ascending sorted Δ replicates; nearest-rank `k=ceil(p×B)` — **1-based**, p=0.025 / 0.975. При B=4096 это ranks 103 и 3994, индексы Python 102 и 3993. Не интерполировать и не round до вывода verdict.

Arithmetic interpretation r_i переиспользует native owner, включая admissibility numeric fields. В протоколе зафиксировать числовой backend и serialization policy; JSON NaN/Infinity недопустимы. Для hand oracles использовать Decimal/Fraction. Семантически значимую EPS-смягчающую проверку `L>δ` не добавлять. При сомнении из-за floating error — explicit numeric instability, не автоматический PASS.

### 6.3 Support и missingness — future run checks

Рекомендуемый baseline для **каждого** partition:

- минимум 30 distinct contributing mints и 30 occupied time blocks в целом;
- в каждой группе минимум 30 contributing mints и 30 contributing time blocks;
- обе группы имеют admissible observed targets;
- target coverage ≥95% в каждой decision-eligible группе; разница missing rates ≤5 percentage points;
- ни одна из фиксированных replicates не имеет пустой группы; нет reroll, отбрасывания неудачной replicate или другого метода;
- leave-one diagnostics каждого distinct mint и каждого occupied block обеих partitions сохраняют обе группы и finite calculation.

Нарушение support/coverage → `INSUFFICIENT`, не отрицательный market verdict. Malformed identity/clock/input → invalid, а не insufficient.

95% coverage — operational screen, не доказательство missing-at-random. Итоговый positive claim условен на observed targets. Return верхом не ограничен accepted protocol; нельзя из отсутствия нескольких targets вывести надёжный population lower bound. Симуляция «missing = −100%» может быть отдельным MODEL, но не незаметной коррекцией данных.

Не создавать универсальный `effective_N = min(mints, blocks)` или фиксированный power claim. Эти counts — support diagnostics. Случай, где несколько кластеров несут почти все observations, должен быть виден через group/cluster contributions и frozen leave-one diagnostics, а не замаскирован большим raw N.

### 6.4 Exact decision rule

Рекомендуемые `direction=A_GREATER_THAN_COMPLEMENT`, `δ=0`. Это проверка положительного conditional contrast; не минимальный экономически полезный edge.

Порядок:

1. Нет принятого полного method/sample/meaning binding → `BOUND_CONTRACT_NOT_READY` **до** future look.
2. Нарушены identity/protection/PIT/chronology → `INVALID_OR_BLOCKED`, с точным указанием, возник ли exposure до обнаружения.
3. Support/coverage/численная применимость отсутствуют → `INSUFFICIENT`.
4. Пусть `CI24=[L24,U24]`, `CI48=[L48,U48]`, D — все предусмотренные leave-one **point** contrasts; интервалы валидны, D не пуст.
5. `L24>δ AND L48>δ AND min(D)>δ` → `ASSOCIATION_SUPPORTED_CONDITIONAL`.
6. `U24<=δ AND U48<=δ AND max(D)<=δ` → `ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY`.
7. Иначе → `INCONCLUSIVE_DEPENDENCE_OR_CONCENTRATION`.

У terminal 6 предел claim: не поддержано положительное превосходство при exact frozen boundary; не «alpha на Solana нет», не closure всей family, не evidence отрицания исполнимого policy estimand.

Degenerate case должен быть определён до исполнения: отсутствующие группы, невозможные weights, malformed/non-finite statistic — не «идеально точный CI». Нулевой variance synthetic lattice может тестировать algebra/rule, но не доказывает empirically calibrated interval. Не вводить неописанное veto «слишком красиво» после результатов.

Положительный proxy result всё равно не закрывает ENTRY/EXIT/COST/EEB obligations и не создаёт qualified strategy. Существующий `science_guard=OWNER_MAY_CONSIDER_PROMOTION` не переписывается этим contract-атомом.

---

## 7. Предрасчёты и цена assumptions

Все числа ниже — **расчёты для дизайна**, не наблюдения рынка. Reproducer: `verify_planning.py`, результат: `planning_checks.json`.

| Проверка | Результат | Практический смысл |
|---|---|---|
| E14400−E1800 | 12,600 s = 3.5 h | Не путать возраст episode с holding |
| 30 полных 48h blocks | 60 суток | Возможный главный data-feasibility blocker. 30 occupied bins не обязательно 60 полностью покрытых суток: считать exact occupied ids, не duration/2 на глаз |
| 14 / 30 epoch-aligned дней | 7 / 15 двухсуточных blocks | Уже metadata может показать невозможность baseline support |
| Nearest-rank 2.5% / 97.5%, B=4096 | 103 / 3994 | Независимый oracle off-by-one и quantile convention |
| Tail probability Monte Carlo SE, биномиальная учебная модель | ≈0.00244, то есть 0.244 percentage points | Не ошибка confidence interval в units returns; увеличение B не лечит мало независимого evidence |
| 3,600 rows × 4,096 replicates ×2 partitions | 29,491,200 row-weight contributions при наивном проходе | Нет нужды хранить 29 млн rows. Агрегирование достаточных статистик/streaming допускаются |
| Coverage для 200 eligible episodes | 190/200 проходит 95%; 189/200 — нет | Деление exact; не округлять 94.5% до 95% для PASS |
| A={10%,20%}, C={0%,−10%} | Δ=20 percentage points | Точный расчёт, но при двух observations result обязан быть INSUFFICIENT |
| A={−10%,−20%}, C={0%,10%} | Δ=−20 pp | Negative algebra не освобождает от sufficiency |
| 3,000 строк из 3 mint identities | 3 mint clusters | Повторы не создают независимую поддержку |

**Малая проверка crossed resampling:** 2 mint clusters, по одному на A/C, 2 time blocks. Все упорядоченные resampling choices дают 16 комбинаций: 8 имеют обе группы, 8 теряют одну. Для выбранной additive hand table все 8 допустимых Δ=0.10. Это oracle веса/пустой группы, **не sufficient sample и не statistical calibration**. Нельзя перезапускать bootstrap, пока случайно не исчезнет empty replicate.

**Synthetic chronology oracle:** dev decision 00:30, dev target available 04:05, E=14,700 s. Formula §5.5 даёт threshold 04:35, не 08:10 и не 04:00. Это authored schedule для arithmetic test; actual source schedule может иметь другие окна.

**Проверка здравого смысла dependence:** у 30 равноотстоящих observations с гипотетической стационарной AR(1)-correlation rho variance mean относительно iid умножается на `1+2*sum((1-k/30)*rho^k,k=1..29)`. Для rho=.5 factor≈2.867, SE multiplier≈1.693; для rho=.8 factor≈7.668, multiplier≈2.769. Это analytic MODEL, не оценка SMIAL. Он показывает, почему count=30 сам по себе не даёт 30 независимых observations и почему этот протокол не обещает coverage для неучтённой serial dependence.

**Более простой путь не забыт:** если данных мало, descriptive Δ/denominators уже считает existing proxy. Не строить второй small-N evaluator и не выдавать слабый estimate за confirmation. Закончить конкретной data/assumption boundary; новый вопрос или более слабый claim выбираются отдельно до look.

---

## 8. SSD: артефакты, semantic ownership и hash model

### 8.1 Minimal write set

После entry переиспользовать существующий accepted owner, если он уже появился. Иначе рекомендуемые новые пути:

```text
docs/tasks/LIST_A_CONFIRMATION_PROTOCOL_FREEZE_V1.md
docs/contracts/list_a_chronological_confirmation_v1.md
configs/list_a_chronological_confirmation_v1.yaml
docs/evidence/list_a_confirmation_protocol_freeze_v1/**
```

Плюс только действительно необходимые existing Catalog/navigation owners и generated output штатным generator. Paths выше — предлагаемое размещение **новых** artifacts, не утверждение их существования на main.

- Task: authority/write set/DoD/exact delivery binding; не дублирует весь научный текст.
- Contract: authoritative meaning, method, gates, source responsibilities и limitations.
- Config: machine-readable fixed values и exact input bindings для этого протокола; не хранит live state или empirical scores.
- Evidence: input/source hashes, metadata readset, calculations/checks, disposition/coverage и owner handback. Малый verification helper здесь допустим как replay evidence, не новый production CLI.

Не создавать accepted capability-registry entry без реализации native confirmer. Не менять historical source packet и старый `SCIENTIFIC_DECISION.md` на PASS; связь supersession/next contract добавлять по current Git rules минимально и только когда принятый outcome действительно изменился.

### 8.2 Рекомендуемая config shape

Это schema-design illustration, **не ready production config**. Executor заполняет реальные hashes/refs по authority и не оставляет эти примерные empty/null поля в FROZEN artifact.

```yaml
schema: smial.list-a-confirmation-protocol
schema_version: '1.0'
protocol_id: LIST_A_CONFIRMATION_PROTOCOL_V1
purpose: FIRST_PREREGISTERED_TEST
question:
  population: OPPORTUNITY_EPISODES
  canonical_list_id: 'JUPITER:toporganicscore:5m'
  list_definition_ref: null
  list_definition_sha256: null
  membership_time: EPISODE_T0
  decision_point: E1800
  target_point: E14400
  price_field_id: FIELD-USD-PRICE-001
  contrast: EPISODE_WEIGHTED_MEAN_A_MINUS_ELIGIBLE_COMPLEMENT
  target_missingness_claim: CONDITIONAL_ON_OBSERVED_TARGETS
  direction: A_GREATER_THAN_COMPLEMENT
  delta: '0'
interpretation:
  native_query_ref: null
  native_query_semantic_sha256: null
  schedule_bindings: []
  repeated_mint: PRESERVE_AND_MODEL_DEPENDENCE
  duplicate_episode: EXACT_COPY_DEDUP_CONFLICT_REFUSE
inference:
  method: CROSSED_CLUSTER_PERCENTILE_BOOTSTRAP
  cluster_axes: [MINT, CANONICAL_DECISION_TIME_BLOCK]
  time_block_seconds: [86400, 172800]
  epoch_anchor: '1970-01-01T00:00:00Z'
  replicates_per_partition: 4096
  minimum_mints_each_group: 30
  minimum_blocks_each_group_each_partition: 30
  target_coverage_min: '0.95'
  missing_rate_gap_max: '0.05'
  quantile_method: NEAREST_RANK_1BASED
  quantiles: ['0.025', '0.975']
  seed_rule: SHA256_PROTOCOL_CORE_COLON_BLOCK_SECONDS_FIRST16_HEX
  empty_replicate_policy: INSUFFICIENT_NO_REROLL
  sensitivity: BOTH_PARTITIONS_AND_ALL_DECLARED_LEAVE_ONE
  numeric_runtime_ref: null
sample_binding:
  status: UNBOUND
  source_scope_ref: null
  sources: []
  interval_start: null
  interval_end_exclusive: null
  exposure_provenance_refs: []
  protection_refs: []
  current_protection_check_ref: null
  structural_feasibility_ref: null
  chronology_proof_ref: null
future_execution_contract:
  main_allowance: 1
  adaptive_allowance: 0
  reserve_before_values: true
  reuse_exploratory_grant: false
  value_read_authorized: false
  activation_authorized: false
non_claims:
  - NO_EMPIRICAL_EFFECT_ESTABLISHED_BY_FREEZE
  - NO_CAUSAL_OR_UNCONDITIONAL_POPULATION_CLAIM
  - NO_EXECUTABLE_POLICY_QUALIFICATION
  - NO_PROMOTE_NO_STRATEGY_NO_ACTIVATION
```

Не переиспользовать boolean поля как implicit authority. `value_read_authorized:false` сохраняется и в полностью frozen протоколе: будущий grant — отдельный owner object/readback, связанный exact identities, а не toggle в этом YAML.

`null` с reason допустим только для действительно неприменимого, например dev result при принятом first-test scope. Required actual list/query/schedule/source identities не null при FROZEN.

### 8.3 Hash domains

| Hash | Meaning | Не сравнивать с |
|---|---|---|
| Raw source packet SHA256 | Точные полученные bytes | Query scientific hash |
| Existing canonical ExperimentSpec hash | Действующий repo algorithm, исключающий описанные presentation fields | Raw YAML byte hash |
| Dossier/manifest spec byte hash | Точное историческое представление spec, если таков current owner | Canonical spec hash |
| Query/recipe semantic hash | Canonical scientific rule с scope | Source sample membership |
| `protocol_core_sha256` | Question, interpretation rule/owner versions, method, numbers, seed derivation, verdict logic, scientific constraints | Текст оформления/receipt timestamps |
| `sample_binding_sha256` | Exact source-set membership/hashes/intervals/exposure/protection snapshot references | Derived latest runtime health |
| Freeze receipt identity | Core + sample + accepted meaning ref + validation evidence identity | Authority будущего real run |

Не вводить свой generic hashing framework. Использовать существующий canonical JSON owner там, где его meaning совпадает. Предложенные domains должны быть явно описаны; serialized set/list order каноничен, bool не принимается как int, отсутствующие/empty/default fields не считаются тождественными без правила.

Protection/exposure меняются со временем: frozen snapshot сохраняется, а future read gate повторно проверяет current stricter state. Изменение текущего protection не rehash-ит прошлую историю и не делает старое разрешение актуальным.

### 8.4 Никаких скрытых scientific mutations

Config/schema validation и scratch arithmetic не вызывают `DocumentRunner`, `discovery-execute`, `.append()` реального ResearchStore, prepare-write/rebuild projection или activation. Existing parser должен быть проверен на side effects перед использованием с real root. Structural input нельзя «подготовить» запуском product workflow.

Если чтение требует writable cache/projection, route не metadata-only без дальнейшего обоснования. Для проверки использовать существующий readonly seam или sanitizer/export. State writes производить только в собственном synthetic scratch, нигде не выдавая их за source evidence.

---

## 9. Подход к доказательству: obligations, а не тотальный E2E

Использовать полезное из Big Agentic Audit v2: exact material obligation, genuine source/consumer, независимый oracle, positive/negative witness, честный уровень fidelity и сохранение непроверенного. **Не исполнять его целиком как отдельный audit-only контракт:** текущая задача разрешает contract delivery и не меняет trading runtime.

Здесь главный объект — stateless scientific protocol/config и его metadata binding. Для него эффективнее contract lint, exact calculations, table-driven decision checks и несколько коротких integration seams. Process-kill/concurrency proof нужен там, где **изменяется durable state owner**; в этом атоме такого изменения нет. Его не имитировать тестом dict вместо будущего reservation store.

| Риск | Самое дешёвое достаточное evidence сейчас | Что оставить native implementation |
|---|---|---|
| Неправильный list/clock/scope | Existing canonical resolver/parser на безопасном fixture + independent expected identity/deadline | Полный market→signal path |
| Неверные formula/quantile/strict inequality | Literal Fraction/Decimal расчёт + table cases | Actual evaluator output на достаточном lattice |
| Exposure притворяется untouched | Exact metadata provenance/readset + adversarial binding fixtures | Durable reservation/lease/crash recovery |
| Source/config hash drift | Recompute hash domains, semantic mutation и reordered representation pair | Native result replay/source revalidation |
| Ложный «готово» при отсутствующем source | Guard table + cold consumer readout | Actual accepted source reader |
| Proxy превращается в qualified strategy | Проверка contract/non-claim/caller mapping и существующего strict downstream design | Real producer→dossier→guard negative journey |
| Заявление validator не соответствует сохранённым bytes | Fresh-process reopen итоговых файлов, проверка hashes/consistency | ResearchStore atomic append/replay |

«LLM написала» не меняет подходящий oracle. Мы не делаем общего утверждения, что vertical loop плох для LLM. Применяем его к короткому реальному freeze handoff; не заставляем весь продукт имитировать trading journey ради проверки YAML. Метод соответствует также рекомендации комбинировать deterministic checks и review по типу outcome, а не единственной предписанной траектории агента [E03].

---

## 10. Матрица обязательств текущего атома

Freeze denominator до финальных checks. Набор ниже выведен из material рисков именно этого scope, не квота тестов. Один test может закрыть несколько obligations. Новые material gaps добавлять с причиной; не удалять failed rows.

| ID | Обещание / нужный witness | Oracle и ожидаемый результат |
|---|---|---|
| F01 | Source packet/accepted Git/reference identity не подменены | Packet hashes; immutable Git refs; alias A resolves to canonical reference. Старый dirty Closure не current scientific truth |
| F02 | True List A и complement имеют прежний смысл | Synthetic A/B/AB/UNKNOWN membership; UNKNOWN не C, AB в A, intended universe не расширен |
| F03 | Preflight не открывает numeric/target columns | Column access log/canary в собственном fixture; denied/protected/unknown metadata case достигает binding guard; до/после real-scope read-only inventory где доступно |
| F04 | Exposure и protection независимы | `holdout=false` + unknown ledger не READY; pending reservation не untouched; current stricter assignment не проигнорирована |
| F05 | Exact sample identity, no latest fallback | Добавить unrelated/newer cohort → frozen set unchanged; замена bound source hash → blocker |
| F06 | Chronology не обходит deadline | Strict boundary equality / overlap / timezone-naive refuse; synthetic §7 threshold=04:35; declared first-test без fake dev refs |
| F07 | Structural feasibility не выдаётся за actual sufficiency | 14-day upper bound fails30; possible sufficient metadata не удостоверяет target coverage; никакого preview ради подтверждения |
| F08 | Estimator arithmetic и resampling meaning однозначны | Hand Δ ±0.20; 16 crossed choices / 8 empty; episode weights, shared group resampling, ranks103/3994; no reroll |
| F09 | Verdict terminal/precedence точны | 24h positive +48h crosses → INCONCLUSIVE; leave-one crosses → INCONCLUSIVE; tiny positive → INSUFFICIENT; invalid precedence; zero boundary проверена |
| F10 | Hashes/seed не самоссылочны и не смешаны | Same semantic config/reordered presentation → same core; δ/block/source change → соответствующий hash changes; derived seed recomputation; wrong hash class refused |
| F11 | Файл реально пригоден следующему consumer | Fresh process открывает exact config/contract, считает hashes и выдаёт тот же readiness/non-claims; changed/truncated bytes не проходят |
| F12 | Durable навигация/cleanup/authority не дают ложной готовности | Generated propagation штатная; scoped diff; no runtime/science writes; owned temp cleaned; один точный resume point |

Для F03 нельзя писать «native confirmer denied values», если confirmer не создан. Правильный claim: проверен **текущий metadata access path** или только contract/check fixture. Если current access path не позволяет подтвердить guard без product изменения, отметить `BLOCKED`/`CONTRACT_ONLY`; это запрет FROZEN для зависимого binding, а не повод строить evaluator тайно.

### 10.1 Небольшой набор worlds

- **W-VALID:** exact synthetic definition/schedule/source/exposure metadata; известные допустимые bindings. Достижимый contract-ready result, без empirical claims.
- **W-BINDING:** по одному foreign hash, UNKNOWN exposure, protected role conflict, duplicate/conflicting episode и newer unrelated cohort. Shape валиден, чтобы достигать нужного guard.
- **W-TIME:** equality/overlap, target availability позже, naive vs UTC; boundary oracle зафиксирован заранее.
- **W-RULE:** authored interval/support tuples для всех rule branches; tiny means не получили scientific support.

Это не четыре больших базы: возможно четыре набора небольших JSON объектов. Большие raw fixtures и контейнеры не требуются без доказанной необходимости конкретного parser/storage seam.

### 10.2 Canary проверки

До расширенного прохода: один valid contract case принимается; один invalid, но shape-valid, достигает target guard; одно контролируемое изменение hash/threshold/returned status в **копии** ловится независимым checker. Если observer верит только `PASS` из лога, он не годится.

Сильный guard имеет positive witness. Если checker отвергает всё — safety ещё не доказала полезность. Если CLI выдал PASS, а новый процесс не читает тот же binding, F11 не пройден.

### 10.3 Что считать достаточным evidence

`CONTRACT_ONLY`: schema, input guard, table rule, hash mapping. `MODEL_ONLY`: независимые математические расчёты. `SEGMENT_PRODUCT_PATH`: реально исполненный bounded current metadata/parser→consumer seam. `FULL_PRODUCT_PATH` здесь допустим **только для freeze workflow**, если все его реальные producers/consumers прошли; не для Science→Trading целиком.

Не суммировать эти уровни в 100% science readiness. Final receipt перечисляет expected/actual/readback/source ref для каждого F01–F12, не только общий зелёный счетчик.

---

## 11. План исполнителю: один атом, зависимые срезы

### Срез A — закрепить base, scope и semantic owners

**Вход:** этот MD, исходный packet, доступный repo. **Выход:** canonical task binding и минимальный delta map.

- [ ] Прочитать current `AGENTS.md` и `.agents/skills/delivery-harness/SKILL.md`; использовать route реально выбранного клиента. Один isolated checkout/worktree, не вложенный root в active Closure.
- [ ] `git status --porcelain`, root/remote/current main readback; не менять чужие dirty bytes. Если main ушёл вперёд, сравнить только owners вопроса, metadata, evidence и policy; old source inventory не новая authority.
- [ ] Semantic routes: `SEM-EXPERIMENT-CAPABILITIES`, `SEM-OWNER-LIFECYCLE`, `SEM-PRIOR-WORK`, `SEM-AUTHORITY-BOUNDARIES`. При working Catalog failure отличить dirty-tree issue от accepted main.
- [ ] Проверить active time gates и current task/write policy. Record `START_AS_WRITTEN` / `START_WITH_PATCH` / `BLOCKED` по harness vocabulary.
- [ ] Materialize exact task; retain source spec один раз по repo convention; freeze required review roles и allowed writes. Не создавать второй документ «plan» с иной семантикой.

**Проверка:** sources и authority достаточно для следующего безопасного шага; никакого empirical code execution. Model effort recommendation — `SOL_XHIGH` один раз для этой contract/science-boundary работы.

### Срез B — metadata feasibility раньше оформления большого freeze

**Вход:** exact source locators из current canonical owner в доступном read scope. **Выход:** sample/exposure/feasibility record либо concrete gap.

- [ ] Найти metadata owners без values. Проверить definition A, schedule/query interpretation и actual permitted read path.
- [ ] Разрешить source-set/exposure/protection graph; для каждого source указать known/unknown и locators. Не читать весь history corpus.
- [ ] Вычислить chronology, interval overlap и potential cluster-support upper bounds. Record readset и zero semantic target/feature reads.
- [ ] При неизвестном/недоступном source закончить безопасный design, не перебирать произвольные datasets. Record точный missing owner/path/access/provenance и действие, которое его разрешит.

**Проверка:** независимая сверка inventory/hash domains и hand clock arithmetic; actor/report не заменяют actual metadata evidence. Не считай отрицательный feasibility report отрицательным market result.

### Срез C — собрать authoritative contract/config

**Вход:** meaning из §4–6 и результаты B. **Выход:** один contract + config без unresolved methodological ambiguity.

- [ ] Записать first-test/confirmation purpose с доказанным основанием; conditional estimand и claim boundary.
- [ ] Зафиксировать sampler/order/seed/quantiles/thresholds/support/missingness/diagnostics/terminal precedence без future placeholders для самого метода.
- [ ] Разделить protocol-core и sample-binding; exact data заполнять только из B. Если B blocked — config status UNBOUND и companion gap, не fake ready.
- [ ] Сделать future consumer requirements из §12 однозначными, без product code или изменение enum consumers.
- [ ] Обновить реально затронутую navigation/Catalog тем способом, который требует current owner. Новые accepted capabilities не объявлять.

**Проверка:** F01–F10, existing parsers + компактный evidence helper. Не нужен новый validator framework.

### Срез D — опровергающие checks и холодный consumer

**Вход:** exact candidate artifacts. **Выход:** verifiable readiness/failure receipt.

- [ ] Зафиксировать F01–F12 и initial coverage; выполнить valid/invalid/contradiction canaries.
- [ ] Выполнить независимые hand calculations, rule table, metadata/time/hash negative cases и короткий actual consumer seam там, где он существует.
- [ ] Отдельный процесс повторно открывает сохранённые final config/contract/receipt, recomputes fingerprints и выводит readiness с причиной. Не reuse mutable in-memory objects из writer.
- [ ] Проверить отказ stronger downstream claims: protocol freeze не создаёт scientific metric/verdict/PROMOTE/EEB/strategy/activation.
- [ ] Архитектурный review отдельно проверяет inferential premises и protection/exposure, не просто совпадение code с тестом.

**Проверка:** output JSON/MD согласован с bytes/readback; невыполненный Fxx виден; recovered checker runs/invalid fixtures не исчезли. Это не полный native confirmer proof.

### Срез E — cleanup, review, delivery и handback

- [ ] Сохранить compact reproducible oracles, relevant failure trace и fingerprints; убрать own temp databases/roots/processes/containers, если действительно создавались.
- [ ] Проверить replay без прежней тяжёлой среды; проверить non-target preservation и remaining owned resources.
- [ ] Risk-routed isolated reviews по current policy. Для этого substantive contract: code/artifact review, goal/DoD, architecture; owner-UX только при material operator surface change / deterministic policy floor. Не изображать model diversity, если она не установлена.
- [ ] Bind evidence/preflight/branch push/PR и exact-head CI по harness; не делать full local gate на каждом edit.
- [ ] Только после machine readiness PASS запросить exact owner phrase для конкретного PR/head. Этот документ merge не разрешает.
- [ ] Handback: §15. Незакрытая data boundary остаётся незакрытой даже после принятия полезного ограниченного contract design.

Ни один срез не имеет автоматического owner-approval pause внутри согласованной обратимой работы. Упёрся в missing empirical source — не прекращай безопасную проверку math/config; но и не пересекай values boundary.

---

## 12. Следующий native confirmer: что обязаны учесть сейчас, но не строить

Назначение этого раздела — зафиксировать интерфейсный handoff, а не реализовать второй atom. Исходный packet §10 остаётся conditional. После protocol freeze можно дать отдельный software scope; настоящий market look и тогда не следует из Git permission.

### 12.1 Required native route

```text
exact protocol + exact source metadata + current grant
→ metadata/protection/exposure gate
→ atomic durable source-bound look reservation
→ first value read under that reservation
→ native conditional contrast/uncertainty/verdict
→ allowlisted substantive result projection
→ ResearchStore committed records
→ cold dossier with same exact verdict and limits
```

`DocumentRunner` по проверенному packet/source path может выполнить capability до generic RUN_STARTED/append. Поэтому добавление result projection hook **не обеспечивает** pre-values reservation. Future implementation должна использовать/расширить existing public transaction/reservation owners, а не private `_reserve` или новую lock DB.

### 12.2 Reservation / crash contract

До values reservation связывает protocol/spec/query/source fingerprint, MAIN identity, role/grant/exposure и executor ownership. Concurrent contender не читает values как второй evaluator. Crash после reservation означает attempted/potentially exposed, даже если начало read не доказано. Outstanding reservation занимает allowance; отсутствие result не возвращает untouched.

Completed-result replay читает frozen result без evaluator. Resume unresolved работает только по тому же source/protocol/reservation и принятому recovery rule. Изменился source или grant/pending ownership неразрешимы — BLOCKED, не новый MAIN. Эти свойства сейчас описываются; доказательство на real SQLite/ResearchStore, barrier и process kill относится к будущей реализации.

### 12.3 Scientific result → dossier

Native result должен нести substantive statistic/verdict/limits и exact identities. `accepted_terminal_match` остаётся technical. Не whitelist-ить любой `RESEARCH_ARTIFACT`; не подсовывать в whole-path test `_scientific_payload()` вместо producer.

Future positive proxy route заканчивается usable conditional association readout, **не** automatic PROMOTE. Negative/inconclusive/insufficient результаты столь же first-class; generic presence-only guard не становится scientific evaluator.

### 12.4 Sample ≠ portable policy; A ≠ B

Конкретные исследовательские cohort IDs остаются в sample lineage. Portable recipe связывается отдельно; удаление cohort restriction без qualification меняет claim. Если `episode_query` нужен runtime, его совместимое представление и compilation receipt должны войти в spec **до** scientific execution/PROMOTE hash. Не rehash исторический manifest ради удобства.

Этот A-protocol не является контрактом executable B-policy. Для B потребуются accepted admission arbitration/size/funding/latency/exit/cost/failure semantics и native EEB. Contemporary E1800 buy/reverse quote не доказывает E14400 exit. Historical EEB class не переименовывается в delayed-exit evidence. Это отдельная source-owner boundary, не work item данного freeze.

### 12.5 Не повторять Trading Closure

Driver/adapters/successor/общие незавершённые обязательства/partial inventory/cold recovery/readback — K04/Closure. K05/эффективность/FCF и K07/live signer не начинают здесь новые подсистемы. После frozen A отдельный implementation design берёт только реально оставшиеся science/result-consumer seams. Одно source gap не порождает семь PR по номерам кандидатов.

---

## 13. Совместимость, безопасность, cleanup

### 13.1 Rollback

Неиспользованный contract/config можно отменить обычным Git revert. После того как artifact участвовал в реальном look, его не переписывать; новый meaning — новая version + явная supersession, old exposures остаются. Freeze revert не очищает ResearchStore или holdout историю.

Не менять query, manifest, global policy или scientific record ради прохождения нового validator. Genuine failure fixture → исправить fixture с сохранённой причиной; genuine source conflict → typed blocker. Не «согласовывать» Oracle с удобным output.

### 13.2 Изоляция

Git read transport допустим в существующих scopes. Product egress, wallet/RPC/provider calls и paid model invocations не часть этого атома. Scratch fixtures synthetic; no real credentials mounts, no automatic production hooks/watchers. Read-only real metadata scope не превращать в запуск реальных workers.

Не выводить raw real mint populations/host paths/secrets в публичные artifacts без необходимости. Для отчёта достаточно identities/hashes/counts и controlled evidence locators; exact raw metadata остаётся у canonical data owner согласно его retention.

### 13.3 Cleanup — явный выходной критерий

Перед созданием существенного resource записать owner, root/PID/container label, baseline existed, disposition. После сохранения маленьких проверок/evidence удалить принадлежащие этой работе scratch DBs, cached fixture copies и processes. Не удалять canonical contract/config, полезный compact reproducer и доказательства решений.

Никаких global prune, force cleanup чужого worktree/cache/.venv, branch deletion или reset чужих изменений. Ссылки/junction/hardlinks и escape из owned root запрещают удаление до разрешения. Потребность будущего consumer может обосновать небольшой retained artifact; «может ещё пригодится» не обосновывает сохранение гигабайтов.

Receipt: created resources, retained compact artifacts and reason, removed roots/process readback, remaining_owned_bytes, before/after non-target fingerprints. Если ресурсов не создавали — показать этот scope, не придумывать cleanup activity.

---

## 14. Definition of Done и invalidators

**Полный freeze принимается только когда одновременно:**

1. Reference meaning соответствует canonical List A и native point/clock/universe semantics; first-test/confirmation label имеет основание.
2. Реальные sample identities, exact interval/source hashes и exposure/protection provenance разрешены в предусмотренном read scope; UNKNOWN не стал untouched.
3. До outcomes проверены temporal/structural upper bounds; actual target support остаётся future run obligation.
4. Protocol/config однозначно задают estimator, all fixed numbers, seed/hash domains, quantiles, sensitivity и terminal precedence.
5. Приняты conditional claim и методологические ограничения; нет заявления general 95% coverage, unconditional population inference или экономической квалификации.
6. F01–F12 имеют достаточное evidence в их declared scope. BLOCKED/read failure не маркирован PASS.
7. Fresh consumer читает exact persisted artifacts, fingerprints совпадают; final contract не требует этого чата.
8. Product/scientific/operational writers не использованы; market values/provider calls/scientific looks/activation = 0 по проверенному scope, а не по одному log assertion.
9. Durable navigation/standard generated surfaces согласованы; cleanup выполнен.
10. Effective delivery/review/CI/owner gates соблюдены; proposal принят в exact scope. Нет неявного разрешения следующего implementation или real look.

Если пункт 2/3 не выполнен, можно принять законченный validated design как ограниченный результат, но terminal — `BOUND_CONTRACT_NOT_READY` с конкретным blocker, не полный freeze. Новая задача не выбирается по «latest» или автоматически из всех candidates.

**Invalidators, требующие пересмотра принятого дизайна:** другое canonical meaning A; unknown/contaminated exposure; incompatibility native price/clock semantics; insufficient source support для принятых partitions; неоправданная crossed dependence assumption для требуемой силы claim; изменившийся method/value criterion; source conflict; потребность unconditional или executable estimand. Ни одно не лечится ещё одним seed или post-look фильтром.

---

## 15. Формат handback — владелец должен понять за минуту

Начало отчёта:

```text
Result: FROZEN_FOR_SEPARATE_AUTHORIZED_CONFIRMATION | BOUND_CONTRACT_NOT_READY
What is ready: ...
What is NOT ready: ...
Scientific looks / market values / provider calls / runtime writes: ...
Exact contract/config hashes: ...
Data/exposure status: ...
Checks and fidelity: ...
Material owner decision: NONE | exact decision + recommendation
One next step: ...
```

За ним компактно: accepted meaning, source/protection/exposure table, deterministic calculation outputs, F01–F12 coverage, invalidated runs/deviations, cleanup, exact consumer route. Полный hash inventory глубже, не в executive paragraph.

**Resume при `FROZEN`:** следующий отдельный software contract — native confirmer + narrow substantive science projection и source-bound pre-values reservation, проверенные на synthetic data. Empirical look — ещё отдельное exact permission.

**Resume при `NOT_READY`:** назвать **первый отсутствующий источник/решение**, уже проверенные независимые части и конкретную команду/metadata export/owner choice, необходимую для продолжения. Не назначать месяцы capture автоматически и не гонять весь design заново. При отсутствии реальных bindings synthetic-only implementation допустима только как отдельный явно принятый software scope, не автоматический обход freeze.

---

## 16. Команда запуска для исполнителя

Передать этот MD. Исходный ZIP полезен для provenance, но смысл/метод/границы/DoD текущего атома полностью приведены здесь; не требуется старый чат.

> EXECUTE `LIST_A_CONFIRMATION_PROTOCOL_FREEZE_V1` по приложенному PRD+SSD. Принимаю для этого contract-атома решения D01–D08: first-test, пока не подтверждён empirical development; reference A=`JUPITER:toporganicscore:5m`; conditional episode-weighted price contrast E1800→E14400, direction A>complement, δ=0; baseline method/screens/limitations и hash/chronology rules документа. Подготовь и проверь canonical protocol/config и exact доступные metadata/exposure bindings. Пользуйся только разрешённым локальным read-only metadata scope; этот текст не даёт нового VPS/data/credential доступа. Новые empirical values, scientific looks, capture, product runtime/code вне write set, EEB/Trading Closure repair, deploy и деньги не разрешены. Не устанавливай произвольные лимиты часов/попыток; продолжай безопасные зависимые шаги до доказанного outcome. Если источники не позволяют полный freeze, закончи independent design evidence и верни `BOUND_CONTRACT_NOT_READY` с точным blocker вместо фиктивного READY. Обязательны cleanup и current delivery gates; merge — только после exact-head readiness и отдельной owner phrase.

---

## 17. Источники для проверки и научные ограничения

### Входные материалы

- **P01:** `OWNER_REVIEW_PACKET.md` из переданного ZIP; sha256 `1a8f63840b18fcd6bed11c2deea2a2244092b81dfcc0f8f092906d712053a71f`; основные §2–6, §9–12.
- **P02:** `source_inventory.json`, `verification.json`, `DESIGN_REVIEW.md`, `package_manifest.json` того же ZIP. Их hashes проверены; изложенные там historical runs не переименованы в наши новые product runs.
- **P03:** `BIG_AGENTIC_AUDIT_PORTABLE_V2`, приложенный текст. Перенесены obligation/oracle/non-vacuity/fidelity principles; audit-only mutation scope и большие campaign defaults не подменяют этот конкретный contract-atom.

### Повторно прочитанные Git anchors

Все следующие refs при планировании — commit `ba87f8e339d5cc3aa55322801ae56e3f92369446`:

| Ref | Exact path / что проверять |
|---|---|
| G01 | `AGENTS.md` — authority/delivery/context |
| G02 | `docs/FACTORY_SEMANTIC_MAP.md` — routes к owners |
| G03 | `docs/reports/forge_trust_closure_v1/SCIENTIFIC_DECISION.md` — protocol C/unknowns |
| G04 | `src/solana_alpha_lab/factory/document_runner.py:720–865` — technical metric / capability-result artifact / append |
| G05 | `src/solana_alpha_lab/factory/hfic_grounded_discovery.py:178–328` — current/exploratory metadata resolver, hash/columns/protection |
| G06 | `tests/test_forge_research_flow_reliability_v1.py:825–960` — synthetic reference question |
| G07 | `tests/test_hfic_list_aware_vertical_v1.py:1–200` — exact A identity / fixture clocks |

Другие точные owners из проверенного packet, для targeted entry/review при необходимости: `hfic_research_scope.py`, `hfic_temporal_discovery.py`, `hfic_ordinary_operation.py`, `research_store.py`, `experiment_evidence.py`, `application.py`, `promotion_handoff.py`; `docs/contracts/experiment_evidence_decision_v1.md`, `science_to_strategy_handoff_v1.md`, `episode_decision_continuity_v1.md`; `configs/experiment_capability_registry_v2.yaml`; current harness/domain policy. Packet inventory содержит их historical hashes; исполнитель проверяет current applicability, не читает все 44 механически.

### Внешние первоисточники — ограниченное назначение

- **E01:** Art B. Owen, *The pigeonhole bootstrap*, Annals of Applied Statistics / arXiv:0712.1111. https://arxiv.org/abs/0712.1111 — основание crossed resampling при определённых random-effects assumptions; не proof coverage именно этого ratio-of-weighted-means contrast в произвольном рынке.
- **E02:** A. Colin Cameron, Douglas L. Miller, *A Practitioner’s Guide to Cluster-Robust Inference* (2015). https://doi.org/10.3368/jhr.50.2.317 — dependence/few-cluster complications; не источник universal minimum=30 для нашего bootstrap.
- **E03:** Anthropic, *Demystifying evals for AI agents* (2026-01-09). https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents — выбирать outcome grader по задаче; deterministic там, где достаточен, review для semantic premises. Не доказательство «vertical loop неэффективен для LLM» и не причина вводить новый eval framework.

### Что выполнено в этой planning-сессии

Read-only Git/source inspection; проверка пяти упакованных файлов по size/SHA256; независимое переизложение 14 исходных арифметических cases; дополнительные clock/support/quantile/crossed-resampling расчёты и rule-table checks. `planning_checks.json` содержит точные scopes и результаты. Ни product tests, ни real metadata/market look, ни empirical coverage, ни независимый canonical delivery review не выполнены. Reproducer — вспомогательное planning evidence, не production implementation.
