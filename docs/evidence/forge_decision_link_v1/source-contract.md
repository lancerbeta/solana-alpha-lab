---
title: "SMIAL — проверяемый выбор исследования и условный перенос опыта"
atom_id: FORGE_DECISION_LINK_V1
version: "1.0"
as_of: "2026-10-10"
mode: RESEARCH_AND_DESIGN_ONLY
status: PROPOSED_EXECUTOR_CONTRACT_REQUIRES_CURRENT_GIT_ENTRY
repository: lancerbeta/solana-alpha-lab
research_base: 76993054cfaeeee7e9fb6e7b718add8cf27e404a
recommended_effort: SOL_XHIGH
implementation_executed: false
scientific_or_economic_gain_established: false
production_or_market_authority_granted: false
---

# FORGE_DECISION_LINK_V1
## Не новый «мозг», а проверяемая связь: почему этот тест → что он показал → что допустимо перенести дальше

**Рекомендация:** один отдельный, вертикально законченный атом поверх существующей Кузницы. Не заменять researcher, evaluator, память, search policy или Delivery Harness. Сначала доказать конкретный пробел передачи решения; затем восполнить его минимальным расширением текущих producers и `scientific_disposition`. Проверить совместимость и реальное потребление на следующем шаге. Сравнение качества выбора — отдельная ось evidence, не условие, которое можно «закрыть» правильной формой JSON.

**Ожидаемый продуктовый результат:** новый агент без предыдущего чата может установить, почему был выбран именно этот тест, какие исходы должны были изменить решение, что реально наблюдалось, что осталось не опровергнутым и почему старый вывод применим или неприменим сейчас. При этом ни объяснение, ни его исправление не меняют научную идентичность, бюджет, ограничения данных или полномочия.

Этот MD самодостаточен для сильного coding executor. Имена новых полей ниже — предложенный контракт, а не утверждение, что такие API уже существуют. Точные привязки текущих owners разрешаются при Entry. Не нужен второй дублирующий PRD/пошаговый plan.

### Команда для передачи исполнителю

> Реализуй `FORGE_DECISION_LINK_V1` по этому документу в разрешённом task scope. Начни с текущего `AGENTS.md`, semantic routes и проверки достаточности уже существующих источников. Не строи параллельную память, research controller или новую систему бюджетов. Закрой выбранную вертикаль от сохранённого основания теста до source-bound авторского вывода и его чтения следующим consumer. Проведи impact-scoped qualification с реальными producers/stores, сохранением исходных отказов и проверкой отсутствия изменений scientific keys, charges, legacy packets и guards. Отдельно оцени добавочную пользу externalized decision policy относительно действующего A9. Не выдавай техническую связность за более умный выбор или alpha. Инженерные решения и связанные локальные repairs принимай самостоятельно; material science, external, settings и merge gates сохраняй. Доведи разрешённый атом до проверенного PR и machine merge-readiness, не выполняя merge без точной owner-фразы.

---

# Часть I. Решение и основания

## 1. Что именно принимаем из §13, а что не внедряем

Исходный Strategic Reframe V3 предлагает не немедленный новый research engine, а проверку: помогает ли явное сопоставление альтернатив, наблюдений и следующих решений выбирать полезный тест. Его §16 прямо предупреждает, что current A9 уже содержит большую часть этой дисциплины. Если различие между CONTROL и CHALLENGER только словесное, правильный исход — `NO_DISTINCT_TREATMENT`, а не новый framework. [U1, §§13, 16]

Принимаем три идеи:

1. **Решение важнее числа гипотез.** Для выбранного шага понятно, какой неизвестный факт изменит последующее действие. Нельзя вознаграждать активность, длину текста, количество KILL или хороший proxy score.
2. **Урок условен.** Отрицательный результат относится к конкретным question, measurement, universe, clocks, execution assumptions и evidence. Он не превращается автоматически в закрытие семейства.
3. **Происхождение решения должно переживать смену агента.** Старые результаты и ограничения доступны через текущие owners, а не через восстановление разговора.

Не внедряем сейчас population search, постоянные agent personas, MAP-Elites archive, автономный выбор бюджета, learned ranker, отдельную graph DB, embeddings, автоматические mutation/crossover/resurrection и новый evaluator. Эти механизмы добавляют другие степени свободы до доказательства, что именно они нужны.

**Отличие этой рекомендации от исходного NOW:** V3 предлагал чистый report-only probe. Здесь владелец дополнительно просит надёжность и долговечный инженерный патч. Поэтому выделены два разных результата: техническая непрерывность объяснения и сравнительная полезность политики выбора. Первый можно принять по source-bound vertical evidence; второй нельзя объявить доказанным по первому. Никакого скрытого повышения report-only исследования до разрешения на рыночные looks.

## 2. Что проверено в базе

Срез `main` во время исследования: `76993054cfaeeee7e9fb6e7b718add8cf27e404a`, уже включает merge PR #394. Это Git-state, не live health. VPS, реальные новые когорты, защищённые исходы и текущий полный ResearchStore не читались. [G0]

| Существующий механизм | Что он уже делает | Следствие для патча |
|---|---|---|
| Operator A5/A9/A10 | Cards, mundane alternative, falsifier, ordinal Pareto, information/decision value, strongest rejected alternative | Не добавлять заново «думай о пользе теста» и не объявлять это новым интеллектом |
| Ordinary operation / reservation | Request, spec, journal, lineage, pending/completed occupancy и admission до values | Встраиваться в этот путь; не заводить второй execution или budget owner |
| Generated draft / freeze / Critic | Сохранённые candidates, fixed identity, отдельные frozen packets, resume | Не реконструировать старые мысли после результата; не менять frozen packet при повторном чтении |
| Evidence-guided memory | Bounded working set, полный safety guard независимо от ranking, два research clocks, source detail | Не подменять полный архив выбранными красивыми «уроками» |
| Scientific disposition | Source-bound авторская оценка, supersession/withdrawal, вычисляемая применимость и cold readout | Это owner пострезультатного урока; отдельный lesson registry не нужен |
| Dossier / Workbench / strategy boundary | Execution отдельно от scientific evidence и решения, DIRECT joins, typed refusals | Новая записка не должна стать научным evidence и открыть PROMOTE |

В inspected draft schema есть `pareto_factors`, `strongest_rejected_alternative`, candidate-level falsifier и прочие текстовые поля. Это уже объяснения, а не «полное отсутствие выбора». Но явная структурная связь **pre-exposure option/outcome plan → exact performed test → conditional post-result update** в просмотренных владельцах не установлена. Это более узкий кандидат на gap; окончательно подтвердить его нужно consumer reproducer, а не отсутствием понравившегося имени поля. [G1–G7]

Сохранённое EGG evidence говорит `QUALITY_GAIN_NOT_ESTABLISHED`: перенос памяти проверяли, но улучшение формулирования/выбора смешивалось с подготовкой и repairs. Новая работа не вправе переименовать этот исторический результат в PASS. [G5]

## 3. Внешние референсы: переносим принцип, не платформу

| Референс | Проверенный механизм | Что берём | Что не переносим |
|---|---|---|---|
| RD-Agent(Q) | Hypothesis, experiment, execution feedback и history/parent links разделены; прошлое участвует в следующем предложении | Узкий интерфейс между researcher и evidence, явные связи между решениями | Его equities results как доказательство Solana edge; целый framework вместо текущего ядра |
| Qlib Recorder | Experiment и конкретный run/recorder — разные сущности; параметры, результаты и artifacts связаны с запуском | Точная привязка intent/result и воспроизводимость | Второй MLflow backend рядом с ResearchStore; implicit create на read path |
| AutoScientist-Quant | Один controller выбирает improve/combine/pivot/stop и parent с учётом бюджета; feedback отделён от final test | Явно различать вид следующего шага и источник feedback | Автономный controller без проверенного evaluator и дополнительных полномочий |
| FactorMiner | Experiences от прошлых trials влияют на генерацию; отдельные skills выполняют проверяемые вычисления | Уроки, реально изменяющие следующий запрос, и проверка вклада памяти | Вечные forbidden directions, factor correlation как независимость механизмов, прибыльность без издержек |
| ReasoningBank | Краткие lessons из успешных и неуспешных попыток используются в следующих задачах | Компактное условное знание, не только список winners | LLM self-judge как scientific authority; перенос web/software benchmark gain на финансовую науку |
| W3C PROV-DM | Разделены сущность, деятельность, использование, происхождение и ответственность | Несколько типизированных отношений с фиксированными refs | RDF/онтологию/graph DB; provenance как доказательство истинности или причинности |
| Anthropic evals | Outcome среды отличается от transcript, trial и суждения grader | Риск-ориентированный набор задач, независимый oracle, наблюдаемые результаты | LLM голосование вместо readback, best-of-N вместо first-attempt evidence |

Источники [E1–E8]. Их результаты здесь не воспроизводились. Это источники дизайна, а не доказательства bottleneck SMIAL.

В частности, просмотренный `rdagent/core/proposal.py` реализует trace как историю пар experiment/feedback и отдельные parent indices; в этой конкретной реализации есть ограничение multi-parent. Это полезный масштаб: серьёзный исследовательский цикл не требует enterprise graph platform. Проверка кода закреплена на blob `39cd0523c8075347171863b1f11cba669034c170`, не является утверждением обо всех сценариях RD-Agent. [E2]

Авторов AutoScientist-Quant пришлось исправлять унаследованную оценку с lookahead. Поэтому «умный controller» не повод ослаблять независимость evaluator или адаптировать закрытый test к новым результатам. [E4]

## 4. Решение по альтернативам

| Вариант | Выигрыш | Риск / цена | Решение |
|---|---|---|---|
| Только переписать Prompt A9 | Очень дёшево | Во многом уже существует; не обеспечивает durable linkage | Использовать для чистого policy probe, не как основной reliability outcome |
| **Минимальный decision link внутри existing owners** | Восстановимость решения, корректный перенос ограниченного урока, база для последующей оценки chooser | Затрагивает identity/recovery/context seams, требует вертикальной проверки | **Рекомендуемый путь** |
| Новый research controller / ecology | Больше вариантов и более сложное управление поиском | Новый движок, evaluator dependence, exposure и integration risk; необходимость не доказана | Не NOW |

**Достаточное ожидание impact:** высокая уверенность в ценности корректной трассировки конкретного решения, если cold consumer сейчас теряет её; средняя — в снижении повторного разбора и ошибок переноса; низкая/неизвестная — в улучшении научного выбора до сравнения. Alpha и cashflow этим патчем не оцениваются.

---

# Часть II. PRD — один законченный outcome

## 5. Owner outcome и consumers

После патча владелец или новый агент по штатному read route отвечает:

> Почему выбрали этот шаг вместо доступной альтернативы? Что было известно тогда? Что именно проверили? Какие результаты изменили бы решение? Что получили фактически? Что из этого применимо сейчас и какое действие только предложено, а какое действительно разрешено?

Named consumers:

- текущий author/оператор, формулирующий следующий разрешённый scientific шаг;
- новый агент после cold restart, читающий результат и причины решения без чата;
- source-bound disposition reader и bounded context следующей задачи;
- существующие независимые Critic/review и owner-facing readouts — только в пределах их роли.

**До/после, без заявлений об интеллекте:**

```text
До: результат и часть объяснения есть, но связь выбранного теста с условиями
    следующего решения приходится собирать из разрозненных artifacts/чата.
После: один точный read route ведёт по сохранённым source-owned связям;
       отсутствующее явно NOT_RECORDED, противоречивое — типизированный gap.
```

Если этот «до» не воспроизводится, не изобретать пробел. Исполнитель должен доказать уже существующий путь и ограничиться реальным navigation/projection defect либо завершить `NO_MATERIAL_DELTA`.

## 6. Scope

### Основная изменяемая вертикаль

```text
existing authorized ordinary request + bound context + validated query
  → краткое основание выбранного теста, если оно подано
  → existing admission / reservation, до первого соответствующего value read
  → existing execution / saved result
  → existing candidate / session references, где этот результат действительно используется
  → existing authored scientific disposition с точной связью и условным уроком
  → cold exact read / bounded context следующего consumer
```

Primary support: **ordinary OPPORTUNITY_EPISODES, existing BASE route**, в том числе ветка, не давшая candidate. NORMALIZED_TRAJECTORY_EPISODES и дополнительные cycles проверяются на совместимость и сохранность accounting; они не становятся обязательной новой implementation surface без реального пересечения с изменённым owner.

Две точки выбранной вертикали не покрывают весь путь «данные → торговая стратегия». На выходе проверяется, что соседние consumers не потеряли смысл и что scientific/strategy guards не получили новую authority.

### Входит

- Потерянные связи и механически проверяемая целостность pre-test explanation / post-test assessment.
- Forward-only поддержка новых records, чтение старых без выдуманного provenance.
- Source-bound conditional lesson, применимость и точные ограничения через существующего disposition owner.
- Правильные restart/retry/late result/conflict/missing-source действия.
- Минимальная CLI/descriptor/operator/readout propagation и адресные regression checks.
- Небольшой impact-scoped audit и отдельный policy comparison на разрешённых exposed/synthetic cases.

### Не входит

- Новый search algorithm, ranker, learned policy, population/archive, агентная команда или автоматическое выделение бюджета.
- Изменение estimand, scientific thresholds, query grammar, evaluator arithmetic, look limits, novelty identity, close/PARK или admission правил ради выигрыша.
- Запуск новых real-market MAIN/PREVIEW/ADAPTIVE, чтение protected data/holdout, provider calls, collection, strategy activation, деньги.
- Переписывание historical ResearchStore, поиск «лучшего старого результата», ретроактивная preregistration.
- Переписывание collector, SQLite readers, dossier или Delivery Harness «заодно». Связанный regression чинить адресно по source owner; новый самостоятельный продуктовый outcome — вне scope.

## 7. Requirements

| ID | Требование | Наблюдаемый результат |
|---|---|---|
| R1 | Existing-first и gap proof | На Entry конкретный consumer trace показывает, что отсутствует, либо доказывает существующую capability |
| R2 | Проверяемое основание до соответствующего чтения values | Записанный план связан с exact context/query; timestamp не единственное evidence порядка |
| R3 | Наука и полномочия не принадлежат записке | Любой note остаётся advisory; admission, counts, protected reads и PROMOTE неизменны |
| R4 | Реальный producer → result link | Native execution сам сохраняет связь; тест не дописывает её в store после выполнения |
| R5 | Условный, source-bound post-result урок | Existing disposition показывает basis, scope, surviving subclaim и reconsideration condition; UNKNOWN сохранён |
| R6 | Cold consumer без чата | Новый процесс находит исходное основание, настоящий result и актуальную применимость через штатный read route |
| R7 | Совместимость scientific identity | Изменение объяснения/его версии не создаёт новый market, look, operation или budget root |
| R8 | Recovery и race safety | Crash/ACK loss/конкурирующий submit не создают второго look и не подменяют первоначальное основание |
| R9 | Ограниченный context и независимый Critic | Не раздувается обязательный packet; explanation не становится persuasion packet или заменой полного safety guard |
| R10 | Раздельная оценка качества | Reliability PASS не повышает `QUALITY_GAIN_NOT_ESTABLISHED`; policy intervention различим и оценивается отдельно |
| R11 | Практическая эксплуатация и rollback | Read-only операции без writes; старый путь usable; откат не удаляет evidence; точные safe next actions |
| R12 | Цельная поставка | Изменённые contracts/schemas/CLI/docs/catalog/tests согласованы; native qualification, evidence и current delivery gates |

---

# Часть III. SSD — минимальная архитектура

## 8. Одна семантика — один владелец

| Смысл | Authoritative owner | Что запрещено дублировать |
|---|---|---|
| Market/evidence identity, доступность, защиты | Действующие evidence/admission/source owners | Свой «research epoch» по тексту notes |
| Разрешённый request, quota, reservation, operation | `hfic_ordinary_operation` и действующая research policy | Второй scheduler/ledger/allocator |
| Pre-test explanation | Существующий durable attempt/reservation context; ниже — narrow extension | Отдельный writable dashboard или общий decision journal |
| Посчитанный result | Действующий discovery/evaluator/result owner | LLM-пересказ вместо чисел/denominator/result identity |
| Post-result authored assessment / lesson | `hfic_scientific_disposition` для поддерживаемого subject/verdict; candidate/Critic artifacts сохраняют свои положительные исходы | Второй lesson lifecycle, «интеллектуальная» БД, coercion положительного исхода в negative advice |
| Candidate identity / freeze / Critic | Действующие card/session/packet owners | Parent label как основание нового canonical candidate ID |
| Что видит следующий агент | Derived exact read и bounded context | Новая memory eligibility, ranking или suppression authority |

Рекомендуемая форма: **небольшие взаимосвязанные фрагменты данных в уже существующие моменты записи, ноль новых сервисов**.

- До теста: `decision_basis` — сжатое авторское обоснование, связанное с проверяемым request/context.
- После результата: optional `decision_update` внутри существующего scientific disposition для поддерживаемых им subjects/verdicts — exact basis ref, source result и условный урок. Положительные candidate outcomes продолжают собственный штатный путь, как описано в §10.1.

Названия можно адаптировать к каноническому словарю, но meanings не смешивать. Post-result disposition требует существующего result: нельзя использовать его как preregistration путём фиктивного `result_refs=[]` или подставленного успеха.

### Правило выбора места хранения

Первый выбор — additive metadata у **существующего per-look reservation/attempt artifact**, с неизменными logical accounting keys. Operation может содержать несколько разных tests; один operation-level текст не должен ошибочно объяснять каждый из них.

Если exact inspection показывает, что durable pre-test basis уже хранится у другого текущего owner, переиспользовать его и добавить только missing refs/projection. Если embedding в reservation нарушает существующую транзакционность/схему, допустим один narrow `RESEARCH_ARTIFACT` внутри того же ResearchStore, связанный с reservation одной атомарной записью или доказанным безопасным ordering. Это инженерный выбор с named reason, не разрешение на новый общий `RecordKind` или parallel lifecycle.

Для STOP без test/reservation сохранить объяснение через существующий no-worthy/draft/disposition путь, применимый к его actual subject. Если такого typed subject нет, достаточно исходного report/readout; не создавать fake operation, пустой trial или ложный научный отказ ради completeness новой схемы.

## 9. Минимальная семантика pre-test basis

### 9.1. Что нужно выразить

| Поле смысла | Откуда | Требование |
|---|---|---|
| Какое решение меняем | Автор | Конкретный допустимый выбор: продолжить вопрос, остановить его, запросить measurement repair, предложить отдельный protocol |
| Факты и ограничения | Exact source refs / context | Версии, cutoff и evidence class; известное отличается от предположения |
| Различающиеся версии | Автор, обычно 1–3 содержательных alternatives | Не требовать quota; singleton/UNKNOWN допускаются с причиной |
| Различающий observable | Автор + validated capability/query | Уже поддерживаемый вопрос либо точный missing capability; отсутствие наблюдения не превращать в ноль |
| Выбранный test или STOP | Автор | Ссылка на real canonical request, не executable команда из свободного текста |
| Исход → дальнейший выбор | Автор до этого результата | Поддержка/опровержение/недостаточность/infra failure разделены; proposed next не authority |
| Почему не другая опция | Автор | Ordinal dominance/cost/feasibility; один strongest alternative либо NONE |
| Связь с прошлым | Exact refs + scope explanation | Что переносится, что не переносится, почему; relation не означает scientific confirmation |

Не копировать `population`, `target`, `estimand`, `explanatory_condition` в конкурирующую «версию истины». Они принадлежат текущему validated query / candidate scope. Basis ссылается на них; отображение может показывать производную короткую расшифровку.

Не добавлять fake probability of success, numerical information gain или weighted intelligence score. При отсутствии cost estimate указывать UNKNOWN; при наличии известного ordering достаточно «metadata inspection дешевле нового MAIN и не открывает outcomes».

### 9.2. Иллюстративный input

Это **проект новой формы**, не готовая команда текущего CLI. Угловые placeholders разрешаются из реальных owners, не копируются в executed fixture. Размер и names окончательно закрепляет executor после Entry.

```json
{
  "decision_basis": {
    "schema_version": "1.0",
    "decision_question": "Нужен ли следующий тест этой связи или сначала проверка её измерения?",
    "basis_refs": [
      {"ref": "<existing-context-or-source-ref>", "sha256": "<verified-64hex>"}
    ],
    "alternatives": [
      {"id": "A", "prediction": "Связь сохранится при сопоставимой наблюдаемости цены."},
      {"id": "B", "prediction": "Наблюдаемая связь объясняется различием активности и свежести цены."}
    ],
    "test_choices": [
      {
        "id": "T1",
        "query_ref": "<canonical-supported-query-ref>",
        "discriminator": "Заранее выбранное сравнение при сопоставимой наблюдаемости.",
        "outcome_actions": [
          {"outcome": "<frozen-supported-outcome>", "proposed_next": "Предложить отдельную независимую проверку."},
          {"outcome": "INSUFFICIENT", "proposed_next": "Сохранить неопределённость; не закрывать семейство."},
          {"outcome": "INFRA_FAILURE", "proposed_next": "Диагностировать execution; не записывать отрицательный рыночный вывод."}
        ]
      }
    ],
    "selected_choice_id": "T1",
    "choice_reason": "Проверяет самое сильное альтернативное объяснение существующими средствами.",
    "strongest_rejected_choice_id": null,
    "rejected_choice_status": "NO_OTHER_ADMISSIBLE_CHOICE",
    "prior_links": [],
    "authority_granted": false
  }
}
```

Этот пример не вводит stratification/evaluator в продукт. Если реальный query grammar не поддерживает указанный discriminator, такой T1 должен стать capability option или STOP до нового look, а не самодельной статистикой inside patch.

### 9.3. Механическая проверка не равна научной оценке

Код проверяет supported version/shape, exact refs/hashes, phase order, наличие выбранного ID, отсутствие dangling refs, scope/authority consistency и ресурсные пределы. Он **не** объявляет explanations materially different по длине строки, не требует фальшивой causal story и не ранжирует научную ценность на основе заполненности полей.

Author/LLM отвечает за содержательную постановку; existing Critic — за проверку в своей роли; evaluator — за реальные результаты; owner/current policy — за смысл и полномочия. При substantive ambiguity оставить UNKNOWN или запросить ровно нужное material decision, не кодировать догадку как guard.

## 10. Post-result update: дополнить существующий disposition

`ORDINARY_SCIENTIFIC_DISPOSITION_V1` уже имеет basis, judgement, caveats, provenance, head/supersession и computed applicability. Патч добавляет только недостающее, а не расширяет все verdict enums ради красивых операторов.

Предлагаемый optional блок:

```json
{
  "decision_update": {
    "schema_version": "1.0",
    "decision_basis_ref": "<exact-saved-pretest-ref>",
    "decision_basis_sha256": "<verified-64hex>",
    "observed_outcome_ref": "<existing-bound-result-ref>",
    "comparison_with_plan": "<source-grounded comparison, not a new calculation>",
    "surviving_subclaim": "<narrow authored statement or explicit NOT_ESTABLISHED>",
    "reconsideration_condition": "<what changed evidence would justify review, not permission>",
    "forbidden_inference": "<what this result does not establish>",
    "advice_authority": "AUTHORED_ADVISORY_ONLY"
  }
}
```

Result refs/hashes/calculation version уже содержатся в `basis` текущего disposition. Не дублировать их отдельно, если общая schema позволяет адресную ссылку; illustrative block показывает смысл связи, а не приказ сделать duplicate fields.

Необязательное отсутствие старого pre-test basis — `NOT_RECORDED`: это не повод запретить прежний законный scientific disposition или стереть результат. Новый assessment может честно описывать результат без заявления, что такой план был заранее зафиксирован.

**Применимость остаётся computed on read у существующего owner.** Result revision, иной market, иная measurement surface, supersession, withdrawal и conflict не переопределяются новым модулем. Сверить, какие из этих axes owner уже проверяет машинно; недостающий semantic axis остаётся явным authored limitation, не вымышленным machine proof. Одних совпавших ID недостаточно, чтобы объявить перенос на новый measurement научно валидным.

### Операторы из §13

`Mutate / Crossover / Repair / Pivot / Resurrect / Stop` допустимы как компактное **авторское описание намерения**, если это помогает текущему consumer. Они не становятся командами scheduler и новыми global states.

- `Repair`: implementation/measurement correction не объявляется новым механизмом и не снимает exposure.
- `Resurrect`: ссылка на ограничение старого отрицательного результата и изменившееся условие; не grant открыть семейство или запустить MAIN.
- `Crossover`: parent refs и совместимость hypotheses не доказывают incremental conjunction gain. Для этого нужен отдельный accepted test.
- `Stop`: остановка конкретного вопроса/проверки, не неявное закрытие family.

Все шесть полей/операторов добавлять необязательно. Если они не меняют current readout, оставить обычный rationale с точными links.

### 10.1. Не расширять verdict algebra незаметно

На исследованном base `QUESTION` disposition поддерживает `LIMITED_NON_CANDIDATE_FOR_THIS_QUESTION` и `INSUFFICIENT_EVIDENCE`; другие перечисленные варианты относятся к определённым bounded search assessments. Это **не универсальный журнал любого положительного результата**. [G6]

Поэтому:

- Новый `decision_update` входит в disposition только когда actual subject/verdict уже допустим. Информативный negative, scoped STOP и честный insufficient дают полноценный основной lesson path.
- Если test дал candidate, сохранять basis ref вместе с реально связанным saved result/candidate artifact и показывать его через exact read. Положительный outcome и Critic/finalize остаются у нынешнего владельца; нельзя требовать `INSUFFICIENT_EVIDENCE` только ради нового поля.
- В bounded readout две легитимные цепочки различимы: `basis → result → existing disposition` и `basis → result → candidate / own Critic outcome`. Это derived navigation, не новый общий lifecycle.
- Отсутствие отдельного авторского conditional lesson у положительного terminal показывает `NOT_RECORDED`, но не понижает сам terminal и не блокирует старый путь. Полный positive outcome по-прежнему доступен из его original source.
- Если реальный необходимый consumer требует новый класс post-positive authored assessment, сначала доказать, почему existing candidate/report fields недостаточны. Это не автоматическое право расширить scientific disposition verdicts. Предпочтительно ограничить первую поставку source links и существующим lesson subset, чем менять смысл всех outcomes.

V02 доказывает полный linked assessment path на валидном disposition case, а V03/V14 — живой положительный counterpart без coercion и ухудшения. Надёжная «память о неудачах» не должна мешать успешному кандидату пройти дальше.

## 11. Identity, clocks и exposure — критические invariants

### 11.1. Разделить identity и integrity

```text
scientific query / market / slot / accounting root / run identity
    принадлежат действующим owners и не переопределяются этим патчем

decision_basis content hash
    доказывает, какую именно записку сохранили; НЕ выдаёт новый scientific slot

disposition head + bound basis/result hashes
    связывают конкретную авторскую оценку; НЕ повышают evidence class
```

Физический artifact hash новой записи может отличаться из-за добавленного payload. **Логическая identity и стоимость scientific attempt не должны от этого стать другими.** Тесты должны сравнивать именно оба слоя, а не требовать побайтово одинаковый новый event со старым.

Не включать optional rationale, author model, prompt wording, new note schema version или narrative parent relation в `market_evidence_epoch_sha256`, scientific slot, current query identity, accounting root или существующие run keys. Уже существующая prompt/capability provenance может законно измениться; это не refund занятого scientific market.

Повтор одного exact look с другим объяснением не запускает новый look. До первого commit автор может исправлять draft. После durable binding первоначальное основание immutable; конфликтующая новая записка получает typed conflict или отдельный честный post-result commentary, но не подменяет план и не создаёт запасной attempt.

### 11.2. Когда именно «до результата»

Basis сохраняется до **первого соответствующего value-bearing шага**, а не просто до успешного ответа MAIN. Если exact result уже раскрыт или same look уже landed без basis, новый текст не может задним числом получить pre-test status: сохранить его только как post-result commentary с честной фазой либо вернуть typed diagnostic. Сам replay доступен по прежним правилам. Если PREVIEW уже был открыт, его результат — prior exposure и явно входит в basis последующего MAIN. Нельзя называть такую запись «до любых данных».

Для record доказать ordering через actual reservation/commit/read boundary и source refs. `authored_at` от модели не доказательство. Writer присваивает время своим current clock; не допускать backdated `effective_at` для вновь записанного урока.

Initial research cutoff существующего preflight не сдвигается. Новые observations того же admitted run относятся к его explicit same-run evidence. Они не становятся частью первоначальной памяти задним числом.

### 11.3. Не забыть inventory self-invalidation

Append нового advisory artifact меняет ResearchStore inventory. Current EGG связывает preflight/read detail с inventory; поэтому новый note способен сам сделать используемый receipt stale.

Не чинить это blanket ignore inventory. Предпочесть embedding в уже необходимую атомарную запись. Если отдельный append необходим, использовать текущий доказанный reissue/rebind путь только при неизменных material sources, cutoff, selection и guard basis. Поддельно свежий cutoff или пересобранный frozen packet недопустимы. Проверить этот стык явно.

## 12. Атомарность, concurrency, resume

Изменение строится вокруг существующей writer lease / before-commit проверки, не вокруг нового lock service.

Рекомендуемый порядок для **действительно нового**, разрешённого ordinary look:

```text
validate public input / canonical query / optional note shape
→ resolve exact sources and existing admission
→ under existing writer boundary:
      recheck operation/slot/request/expected note binding
      persist reservation with bound basis (or same-transaction artifact+ref)
→ only now invoke existing value loader/evaluator
→ existing result commit retains reference to the actual basis
→ independent readback
```

Это семантический порядок, не новая реализация executor. Фактические hook points выбрать по коду; не обходить public ingress и не переписывать existing `_reserve`/ledger целиком.

| Ситуация | Ожидаемое поведение |
|---|---|
| Неверный новый basis / unsupported version / unknown selected ID | Отказ до нового value read и look reservation; существующая работа не повреждена |
| Crash до commit reservation | Нет выдуманной занятой попытки/сохранённого плана; следующая попытка решается текущим admission |
| Crash после reservation, до values | Resume с original plan/ref и occupied slot; не повторная генерация нового плана |
| Result committed, ответ потерян | Вернуть saved result + original links; no repeated evaluation / double charge |
| Plan A уже bound, submit plan B для того же pending/landed look | Typed conflict с exact locator A; не silently overwrite, не новый budget |
| Другой writer дописал unrelated advisory record | Не делает прежний market «новым»; scoped rebind или видимый stale-read по текущему contract |
| Два разных post-result assessments | Existing expected-head/supersession/conflict rules; не last-writer-wins по удобной дате |
| Source result изменён calculation revision | Старый plan/assessment остаётся историей; applicability требует review; не новый MAIN автоматически |
| Упал writer новой записки | Source-owned result остаётся читаемым; linkage/assessment gap виден; нет ложного rollback уже совершившегося scientific look |
| Read-only consumer без прав записи | Читает существующие records, не создаёт каталоги/DB/leases и не исправляет history |

Recovery actions возвращать как точные existing command/locator либо конкретный proposed action в том же readout. Не добавлять «попробуйте ещё раз» без определения, какой шаг разрешено повторить.

## 13. Интеграция с candidate, Critic и следующей памятью

### 13.1. Candidate transport

Ссылка следует только за реально связанным result/candidate. Candidate ordinal, одинаковый title или «похожая идея» не основание join. Не переопределять canonical `HFIC-CAND-*` identity и existing card projector ради нового explanation.

Если сохранённый plan касается choice между несколькими tests, это не доказывает проверку всех опций. У исполненного test должны быть реальные result refs; rejected/not-run варианты остаются proposed.

No-candidate/negative path обязан сохранить useful assessment без manufactured candidate. Положительный counterpart не обязан создавать negative disposition ради linked view. Иначе patch искажает память в одну из двух сторон.

### 13.2. Critic не получает историю убеждения

В frozen Critic packet не надо автоматически класть весь ranking, самооценку автора и narrative «почему мой кандидат лучший». Независимый Critic получает selected candidate, admitted evidence, discriminant/falsifier и material restrictions по текущему contract.

Если новые факты необходимы Critic, включить лишь минимальный source-bound факт/ссылку в текущем packet owner; проверить packet version и mandatory source closure. Объяснение выбора остаётся доступным owner/reviewer отдельно. Parent relationships не дают Critic дополнительную authority, а факт «видел урок» не является его endorsement.

Все authored strings — недоверенные данные. Ни `proposed_next`, ни quoted source, ни parent comment не исполняются как shell/tool command и не меняют инструкции/allowlist агента. При отображении через HTML/Workbench использовать действующий escaping; ограничить bytes/глубину/размер arrays по existing safety conventions. Добавить harmless instruction-in-data и HTML marker в targeted negative fixture, если затронут display/tool consumer; не тратить тест на реальный опасный вызов.

Saved packets старых версий не пересобирать. При необходимости новой additive версии применять её только к новым packets; не создавать новое `HFIC-V1.x` merely ради названия note.

### 13.3. Потребление следующей задачей

Основной lesson path — существующие `disposition-show` / `scientific_disposition_context` и адресный read detail. Положительный candidate остаётся доступен через нынешний candidate/prior source; при общем readout явно указывать разный owner, не сводить разные verdicts в один. `hfic_generation_context` не становится владельцем lessons. Он может давать ссылку/минимальную проекцию source-bound assessment, если это действительно помогает следующему consumer.

Не менять memory eligibility, structural ranking, full-archive guard или число scientific attempts. Не подставлять LLM rewrite в `finding` с authority `SAVED_DESCRIPTIVE_RESULT_ONLY`: описание урока остаётся authored advisory, численный readout — computed result.

Старый source detail со `surviving_observation=NOT_RECORDED` не «восстановить» угадыванием. Новые fields заполнять только из сохранённого typed assessment, с его source/version/applicability; когда такого assessment нет, UNKNOWN/NOT_RECORDED — правильный ответ.

### 13.4. Context budget

На исследованном base: общий Forge/Critic operational envelope — 65536 bytes; growth warning — 20480; initial memory до 8 capsules, Critic до 64. В EGG retained growth case был packet 64440 bytes. Это почти заполненный packet, а не приглашение добавлять ещё 4 KiB. [G2, G5]

Предпочесть exact ref + короткий advisory summary в существующем bounded section. Отдельный detail читается по текущим правилам. Не увеличивать глобальный cap; optional omission видна, mandatory source/grounding не усекать. Новый planner не должен платить многократным чтением всех partitions за каждую relation.

## 14. Compatibility и обратимость

| Объект | Новый reader | Новый writer / rollout |
|---|---|---|
| Исторический request/reservation без basis | Прежняя semantics + NOT_RECORDED только в новой view | Никакого backfill; replay по старому контракту |
| Новый request с валидным basis | Проверить ref/version/integrity | Forward-only запись в реальный pre-value seam |
| Новый request без basis | Прежний допустимый путь, без claim decision-link completeness | Не вводить глобальную обязательность нового ритуала |
| Неверный явно поданный basis | Typed invalid input, не молчаливое игнорирование | Не превращать malformed new input в «старый формат» |
| Старый disposition | Без новых предположений | Existing correction/withdrawal сохраняются |
| Новый linked disposition | Проверить source/result/basis relation, вернуть advisory/class/applicability | Один existing disposition owner; narrow schema evolution |
| Pending run старой версии | Original saved context, counts, packets и expected next | Не заставлять regenerate/refreeze/ещё один MAIN |
| Старый reader/writer после rollback | Доказать supported compatibility либо typed unsupported на новой части | Не терять basis/изменять promises молча; старые научные records остаются доступны |

Рекомендуемый rollout — **reader-first и optional forward writer через существующий ingress**, а не глобальная смена алгоритма выбора. Existing A9 продолжает действовать. Добавленное поле принимает уже имеющееся авторское основание и делает его проверяемым; не требует каждый раз полной decision matrix.

Связность и exact read можно внедрять после technical qualification. Сделать expanded matrix обязательной частью обычного выбора можно только по доказанному useful treatment и в пределах согласованной policy authority. Если quality comparison не дал выигрыша, оставить нынешнюю selection policy и тонкий traceability path — при условии, что последний имеет собственного доказанного consumer, а не лежит мёртвым framework «на потом».

**Откат:** обычный code revert/отключение нового writer path в разрешённом порядке; не удалять notes/results/assessments. Existing supersession/withdrawal — для исправления authored advice, не переписывания его прошлого. На смешанных legacy/new/pending данных заранее проверить, что rollback не уничтожает диагностику и не разрешает дополнительный look.

---

# Часть IV. Проверка изменения, а не всей фабрики

## 15. Entry и baseline: сначала доказать, что патч нужен

В одном рабочем checkout/worktree:

1. Read current `AGENTS.md`, Harness policy, active time gates, semantic routes `SEM-HYPOTHESIS-FORGE`, `SEM-PRIOR-WORK`, `SEM-OWNER-LIFECYCLE`. Pin exact candidate base. Изменившийся head переоценивать по touched owners, не по хронологии «самый новый task».
2. Найти реальный current path из accepted request до result и existing disposition. Просмотреть producer, serializers, read projections и tests. Проверить, не добавили decision link после research base этого MD.
3. На owned synthetic fixture пройти cold owner question: восстановимы ли pre-test choice/outcome expectations, exact test/result и conditional applicability без авторского чата?
4. Разложить потерю: `NOT_AUTHORED`, `AUTHORED_NOT_PERSISTED`, `PERSISTED_NOT_LINKED`, `LINKED_NOT_EXPOSED`, `NO_GAP`. Это локальные diagnostic labels, не новый global enum.
5. При `NO_GAP`: использовать существующий механизм. Нового слоя не строить; если остаётся только prompt utility hypothesis, провести report-only comparison. Если нет material delta — закрыть задачу с evidence и рекомендацией не внедрять.
6. Если gap только навигационный — исправить projection/descriptor, не вводить новую запись. Если real pre-test facts никогда не сохранялись — narrow forward extension по §§8–14.

Entry не является очередной owner approval остановкой. Executor сам выбирает минимальную реализацию в пределах outcome. Настоящее изменение scientific meaning/authority — отдельная граница.

## 16. Impact-scoped Big Agentic Audit

Это квалификация **патча и прямых соседей**, не повтор 56-charter кампании. Внутренние states/producers/readers остаются настоящими; synthetic только внешние данные и модельные ответы. Все skipped edges обозначаются.

Сначала составить один machine-readable obligation ledger: current producer→consumer, expected/forbidden, baseline/candidate identity, fixture/fault schedule, independent oracle, fidelity и evidence ref. Исходный denominator фиксируется до прогона. Новые material edges добавляются с reason; неудобные не исчезают.

### Минимальный набор смысловых charters

Число test functions произвольно: один сценарий может закрыть несколько obligations. Неприменимость требует current-contract основания, не отсутствия готового теста.

| ID | Реальная проверка | Oracle / что запрещено |
|---|---|---|
| V01 | Existing legacy ordinary path без new basis | Те же scientific semantics, keys, counters, legal stops; historic artifacts не rewritten |
| V02 | Новый valid basis → admission/reservation → native result → допустимый existing linked disposition → cold exact consumer | Каждый join создан real producer; новые refs не внесены тестом в середине; result соответствует независимому expected fixture |
| V03 | Positive candidate counterpart плюс non-candidate / informative negative / insufficient | Positive проходит existing candidate/own Critic path без ложного negative disposition; negative lesson доступен без fake candidate; insufficient не отрицательный факт |
| V04 | Malformed/unknown-version/contradicting selected ID/hash/source | Достигает именно new boundary; отказывает до нового reservation/value read; existing records intact |
| V05 | Note-only wording/model/policy metadata perturbation | Не новый query/market/slot/budget root; повтор occupied look не расходует ещё одну попытку |
| V06 | Crash сразу после reservation и после result commit до ACK | Реальный child process, persisted state, cold resume; original basis/result, no double charge/regeneration |
| V07 | Два concurrent basis на один logical attempt; параллельный unrelated append | Compare-before-commit, один original binding; typed conflict; unrelated object не блокируется глобально |
| V08 | New note/disposition append → stale preflight/detail request | Разрешённый reissue лишь на эквивалентной basis; initial cutoff и full source guard не меняются |
| V09 | Добавление future/late-only records | Earlier context/choice binding остаётся original; current later applicability может измениться явно |
| V10 | Withdrawal/supersession/result correction/source disappearance | Existing disposition lifecycle; old bytes preserved; missing evidence не выдаёт актуальный lesson |
| V11 | Чужой experiment/run/result с похожим title, conflicting refs | Нет weak join и повышения DIRECT/evidence class; note не способен открыть PROMOTE |
| V12 | Ложный hard close / changed-measurement resurrection / технический FAIL | Full guard остаётся authority; correct scope/rebase виден; ни permanent ban, ни automatic reopen |
| V13 | BASE → admitted representation / cycle continuation | Existing accounting lineage и pending semantics сохранены; new metadata не даёт отдельный pool |
| V14 | Freeze/runner-up/revision/finalize на затронутом пути | Original packet source integrity; независимый Critic не получает ranking persuasion; C1/C2 и session/run terminal не перепутаны |
| V15 | Packet у cap и рост archive на existing fixture | Нет mandatory truncation, cap unchanged, omission/detail explicit; no per-link full rescan explosion |
| V16 | Read-only CLI и действующий owner-facing consumer | No business/DB/WAL writes, no commissioning/repair; одно состояние/смысл на обоих surfaces |
| V17 | New reader на legacy/new mix; rollback reader и pending state | Нет data migration, fake preregistration и повторного science ради совместимости |
| V18 | Harness canaries: wrong link, missing terminal, changed artifact | Independent oracle реально FAIL/nonzero; integrity PASS не означает product/quality PASS |

Обязательные сцепления: **pending reservation × changed explanation × resume**; **result revision × assessment supersession × next-context read**; **new advisory append × bound preflight × full-archive guard**. По необходимости объединить с V06/V08/V10, не считать независимые одномерные проверки доказанной тройкой.

### Fidelity и non-vacuity

- `FULL_PRODUCT_PATH` допустим только для выбранной узкой вертикали basis→реальный test→assessment→cold consumer, без hand-injected internal link. Это synthetic technical acceptance, не full strategy qualification.
- `SEGMENT_PRODUCT_PATH` — legitimate intermediate fixture с явно пропущенным producer.
- `CONTRACT_ONLY` — field/parser/guard test.
- `MODEL_ONLY` — решение LLM по packet без product execution.

Negative input обязан дойти до целевого guard. Пустая, невалидная по upstream schema карточка не доказывает надёжность новой lineage проверки. Для significant denial нужен valid counterpart, который проходит, иначе можно получить «безопасно, потому что всё BLOCKED».

## 17. Практические fixtures и независимые oracles

Переиспользовать existing audit/Trust Closure infrastructure и shipped serializers/ResearchStore. Не начинать с нового simulator.

| Мир | Назначение |
|---|---|
| CLEAN-DISCRIMINATOR | Два допустимых объяснения, один реальный supported query, заранее известный synthetic result; one chosen path |
| HONEST-NO-EDGE | Валидный negative/insufficient result; сохранить ограниченный урок без продвижения |
| PREVIEW-ALREADY-EXPOSED | Prefix/preview уже прочитан; subsequent plan честно post-preview, не untouched preregistration |
| SAME-KEY-DIFFERENT-STORY | Меняется только объяснение или model provenance; original look identity/charge unchanged |
| SCOPED-OLD-LESSON | Старый FAIL имеет exact measurement scope; новое условие не тождественно новому разрешению |
| PENDING-AND-LATE | Persisted reservation, потерянный ACK, unrelated append, late result; cold resume |
| PACKET-PRESSURE | Existing near-cap fixture; новая optional summary не выталкивает guard/grounding |

Oracle priority: current contract → независимая маленькая reference calculation/сопоставление persisted refs → state invariants и before/after inventories → доказанное metamorphic relation → source-grounded semantic review. Не копировать implementation в expected calculator.

Сохранять actual commands, source/ref/runtime fingerprint, attempt id, injected boundary, observed order и independent readback. Seed не заменяет schedule race. Случайная задержка менее полезна, чем barrier в конкретном commit/ACK стыке.

Читать код/шаблонный report недостаточно для технического PASS. И наоборот, source-only evidence хватает, чтобы **не** строить дублирующий слой, если точный existing consumer уже содержит нужную семантику; тогда доказывается reuse, не выдуманный defect.

## 18. Отдельная оценка полезности выбора

### 18.1. Что сравниваем

Сохранить сильный CONTROL: current A9/A10, текущая доступная память, guards, те же facts и разрешённый menu. CHALLENGER отличается только компактной, внешне фиксируемой decision matrix с явными последствиями outcomes и conditional update.

Не сравнивать «текущая система» с arm без памяти, худшей моделью или меньшим read-set. Не давать challenger заранее отредактированный правильный урок.

До модельных outputs проверить **distinct treatment**. Если текущий author уже делает эквивалентную таблицу/логику, `NO_DISTINCT_TREATMENT` — полезное опровержение необходимости нового ритуала. Оно не опровергает ценность исправления реальной потери persisted link.

### 18.2. Casebook

Выбрать небольшой, заранее закрытый набор already-exposed source-bound historical decisions; practical minimum — две materially разные истории и отдельные positive/scope controls. Этапы одной holder истории не выдавать за независимые репликации. Pure synthetic worlds нужны для проверки ошибок, не вместо всех исторических cases.

Подходящие anchors, не автоматические нынешние задачи:

- old holder concentration relation → exact top-quartile rule rejection → later measurement rebase;
- другой законченный rule/falsifier с иным failure scope, после проверки поздних dispositions;
- redundant H≥3 при universe H≥50 — integrity/control, не сложный научный endpoint;
- живой consumer с cold resume и incomplete evidence — traceability/operability, не market efficacy.

Для каждой точки заранее заморозить `answerability sheet`: доступные факты, несколько допустимых действий, запрещённые выводы, неизвестное и source-supported basis оценки. Судить качество теста по тому, что его возможные outcomes могли различить **тогда**, не по тому, оказался ли outcome позже положительным.

Исторические публичные итоги уже могли быть в весах модели. Анонимизация снижает подсказки, но не делает retrospective replay prospective forecast.

### 18.3. Порядок и resources

Перед comparison freeze: cases/decision points, одинаковые packets и current-authority sidecar, модель/effort, available tools, read-set, cost envelope, output schema и judge source set. Затем независимый initial choice → заданный исторический feedback → within-arm update → transfer на другую историю.

Рутинные механические trials и настройка harness не ограничены произвольными «четырьмя попытками». Но comparison нельзя подгонять бесконечными повторами: все outcomes и setup failures сохраняются, development повторения отделены от исходного evaluation denominator. Новый test batch оправдан новым material вопросом или проверкой instability, не поиском понравившегося ответа.

Число calls вывести из frozen cases × arms × decision points × действительно нужные repeats внутри текущего разрешённого бюджета. Никакого нового paid transport/account/key или сброса scientific caps. Предлагаемые в исходном V3 12 calls — его дешёвый pilot envelope, не универсальная норма и не автоматическое разрешение здесь. При необходимости другого envelope зафиксировать отличие до outputs; материальный новый расход — owner gate.

Для **MODEL_ONLY** task-choice comparison не требуется строить полноценного tool-using агента в Docker. Подходит существующий разрешённый fresh-context model call с только безопасным packet и выключенными tools. Полномочия model transport и product runtime раздельны. Если tools невозможно отключить, не называть такой запуск доказанно изолированным/blind: либо использовать доступный безопасный tool-less путь, либо сохранить точный предел. Review critics не становятся evaluation actors автоматически.

### 18.4. Оценка и правило adoption

Оценивать: admissible/useful TEST/STOP, способность различить альтернативы, корректный scope урока, false bans, unjustified continuation/resurrection, изменение решения после релевантного факта, подготовку, output size, calls/cost и operator intervention. Форма JSON и длина rationale не primary endpoint.

Judge использует source-supported answerability; LLM может помогать, но несогласие по научной интерпретации остаётся спорным/UNKNOWN. Автоматический guard, остановивший плохую модельную заявку, — успех safety, не успех decision quality модели.

| Итог | Следствие |
|---|---|
| `LOCAL_SIGNAL_TO_ADOPT` | Допустим малый доказанный consumer/prompt delta; дальнейшее обобщение только на новом заранее выбранном case |
| `NO_ADDED_VALUE` / `NO_DISTINCT_TREATMENT` | Current selection policy оставить; traceability repair оценивается по собственному outcome |
| `QUALITY_UNVERIFIED` / `INCONCLUSIVE` | Не заявлять better chooser, не делать matrix обязательной и не добавлять ranker |
| Есть конкретный sensing/evaluator discriminator gap | Назвать его точно; не расширять этот атом в новую научную платформу |

Даже локальный positive signal не доказывает general compounding, доходность, независимость моделей или causal вклад памяти отдельно от формата процедуры.

## 19. Definition of Done и уровни принятия

### Техническая приёмка

| DoD | Достаточное evidence |
|---|---|
| D1 Scope и real delta | Current base/owners, baseline consumer reproducer либо доказанное reuse/no-delta; выбран минимальный seam |
| D2 Pre-value binding | Actual persisted basis перед целевым loader; negative counterpart с zero new effects |
| D3 Native round trip | V02 через настоящие producers/stores, cold read без чата, включая путь без candidate |
| D4 Truth boundaries | Advisory не допускается как scientific metric/binding/decision authority; existing PROMOTE refusal сохранён |
| D5 Identity/accounting | V05–V09/V13: original logical keys, occupancy и cutoff не меняются от новых объяснений/metadata |
| D6 Recovery/conflicts | Реальные interruption/ACK/race tests, тот же result/plan, no double charge; exact safe resume |
| D7 Conditional memory | Exact source/result/update link, applicability существующего owner, no false family close/reopen |
| D8 Compatibility | Legacy/new/pending/read-only и rollback, старые source bytes/packets сохраняются |
| D9 Context/independence | Packet bounds/omissions/full safety и selected-candidate Critic separation доказаны на затронутых маршрутах |
| D10 Harness и reproducibility | Negative canary реально обнаруживается; новый owned root запускает documented entry; все attempts retained |
| D11 Propagation/delivery | Public descriptor, schema, contract, docs/routes/generated views и tests согласованы; current required reviewers/CI/readiness |
| D12 Honest decision readout | Отдельно technical confidence, quality result, unresolved scope, costs и один next step |

Нельзя объявить `TECHNICAL_DECISION_LINK_VERIFIED`, если native producer→cold consumer существует только в hand-built fixtures. Нельзя считать продукт бесперебойным в real runtime после synthetic tests. Все material selected obligations закрыты evidence либо отражены как блокеры соответствующего acceptance, а не переименованы в PASS.

### Отдельные verdict axes

```text
TECHNICAL_CONTINUITY: VERIFIED_IN_SYNTHETIC_SCOPE | PARTIAL | FAILED | NO_MATERIAL_DELTA
CHOICE_QUALITY: LOCAL_SIGNAL_TO_ADOPT | NO_ADDED_VALUE | NO_DISTINCT_TREATMENT | UNVERIFIED
LIVE_USE: NOT_EXECUTED
MARKET_ALPHA / OOS / REALIZED_ECONOMICS: NOT_EVALUATED
```

Это report labels, не новые global product enums. `NO_MATERIAL_DELTA` — правильное закрытие лишней работы. `PARTIAL` остаётся частичным; нельзя считать отсутствие model transport причиной провалить уже независимо доказанный read-only lineage repair, но и нельзя по нему сделать quality/actor claim.

---

# Часть V. Исполнение, доказательства и границы

## 20. Порядок работы в одном атоме

### S0 — BIND / CHEAPEST FALSIFIER

Разрешить current owners и gates, пройти §15, зафиксировать real delta. До крупного scaffolding проверить самый короткий native seam и валидность fixtures. Compile targeted obligation ledger; текущий write set закрепить в exact task contract. Не менять main или чужой PR ради подготовки.

### S1 — CONTRACT / CHARACTERIZATION

Разделить существующие и новые semantics, выбрать место pre-test basis, shape additive update, identity и compatibility rules. Отобрать existing tests, написать только недостающий material regression/reproducer. Test-first полезен, но не универсальная процедура. Отдельная сущность/сервис не нужна, если current payload owner выражает требуемое.

### S2 — NARROW IMPLEMENTATION

Один public ingress/serializer/producer path, существующие post-result owners по actual terminal и один связный read consumer. При необходимости небольшой pure helper для проверки формы/refs; не второй orchestration core. Сначала использовать изменение в настоящей вертикали, затем оформлять derived artifacts. Прямая локальная причина падения DoD чинится здесь, не откладывается в суффиксный атом.

### S3 — IMPACT QUALIFICATION

Same-path baseline/candidate comparison, genuine persistence/recovery, negative/positive canaries, targeted interactions, legacy/packet/guards. New scope-sensitive edge обнаружен — добавить obligation и проверить; science outcome не сужать под имеющиеся tests. Полный Big Audit не повторять без отдельного material trigger.

### S4 — QUALITY / OWNER READOUT

Проверить distinct treatment и провести доступный честный comparison по §18. Exact readout отделяет data/lineage proof от inferred lesson и quality result. Нет эффекта — не внедрять обязательную новую политику. Не подбирать другой benchmark до победы.

### S5 — PROPAGATE / REVIEW / DELIVERY

Привести контракты, authoring descriptors, operator examples, source routes/catalog и generated projections в согласованное состояние. Risk-routed independent review по актуальному task/Harness. Targeted local checks на changed consumers; full gate имеет одного owner по текущей Git policy. CI PASS → machine merge-readiness → точная owner phrase → guarded merge/post-merge readback только в отдельно разрешённом scope.

Не спрашивать владельца, какой helper, fixture engine, low-level data structure или test order выбрать. Остановки только по реальной authority/meaning/resource boundary или необратимому действию. При context pressure сохранить точный checkpoint; не обнулять attempts и не перечитывать весь repo.

## 21. Начальные source owners и impact surface

Это исследованные locators, не frozen executable write set. Executor заново разрешает текущие version/owners и расширяет write set только причинно необходимыми consumers.

| Группа | Путь / назначение |
|---|---|
| Public entry | `scripts/hypothesis_forge.py`; existing operation input, preflight, discovery, disposition/read commands |
| Research request/admission | `src/solana_alpha_lab/factory/hfic_ordinary_operation.py`; reservation, occupancy, parent/accounting, replay |
| Authoring/freeze | `src/solana_alpha_lab/factory/hfic_session.py`; generated draft, frozen session, recovery; actual projector owner разрешить из него |
| Post-result lesson | `src/solana_alpha_lab/factory/hfic_scientific_disposition.py`; schema `catalog/schemas/hfic_scientific_disposition_v1.schema.json` |
| Context | `src/solana_alpha_lab/factory/hfic_generation_context.py`, current preflight/prior owners; только direct-consumer delta |
| Protocol/schema | `docs/contracts/forge_evidence_guided_generation_v1.md`; `docs/contracts/hfic_scientific_disposition_continuity_v1.md`; `catalog/schemas/hypothesis_forge_draft_v1_2.schema.json` — изменять лишь при нужном public field |
| Operator | `docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md`; `.agents/skills/hypothesis-forge/SKILL.md`; не альтернативный operator manual |
| Adjacent readout/guards | Current dossier/Workbench/`forge-run` consumers через semantic route; по умолчанию только qualification |
| Existing regressions | `tests/test_forge_research_flow_reliability_v1.py`; `tests/test_hfic_prefreeze_draft_recovery_v1.py`; `tests/test_forge_evidence_identity_and_owner_gold_v1.py`; source-specific disposition/context tests разрешить текущим search |
| Audit reuse | `tests/fixtures/big_agentic_audit_v1/` и `tests/fixtures/forge_trust_closure_v1/`; exact pinned source, не stale baseline verdicts |

До первого дальнего CI проверить прямые downstream checks изменённых contracts. Предыдущий repair показал цену забытых policy-string checks, byte pins и test Git identity. Здесь не повторять это: найти references/hashes/validators для actual changed files, проверить отдельно synthetic Git environment при Git-based test. Не подставлять новую строку в комментарий ради старого string assertion. Если pin утверждал historical immutability, сохранить исторический смысл и добавить корректный current binding с основанием; не «обновить все хэши» без разбора.

## 22. Артефакты и evidence economy

Минимальная поставка, не каталог отчётности:

1. Source-owner patch + нужная contract/schema/descriptor propagation.
2. Расширенные existing regression fixtures/tests и один reusable native replay route для новой вертикали.
3. Один manifest/ledger для bindings, obligations, attempts, source fingerprints и результатов; readable view генерируется/сверяется с ним.
4. Один owner readout: before/after, scope, technical/quality axes, остатки, cost и next.
5. Если модельный comparison выполнен — frozen packets, original arm outputs и source-grounded grading как evidence этого же атома, не новая benchmark platform.

Large synthetic stores/traces — вне Git по текущей retention policy, с проверенными refs/hashes/размером и описанной доступностью. Компактные воспроизводимые fixtures и high-risk failures сохраняются durable. Hash без доступного artifact не объявлять переносимым replay kit.

Source change инвалидирует только зависимое evidence. Доказать equivalence unchanged dependencies и перепроверить изменённые consumers; нельзя просто сложить PASS с разных revisions в «final head всё прошло». CLI shell code и summary различают PASS/FAIL/INCOMPLETE/HARNESS_ERROR; receipt integrity не заменяет semantic grade.

## 23. Автономия и инструменты

Внутри отдельно принятого executor task допустимы inspection, bounded product/test/doc changes, isolated synthetic writes, необходимый локальный refactor, чтение официальных docs и routine Git delivery по действующей policy. Связанный repair должен устранять нарушенное обещание, а не открывать новый outcome.

Default tools: current locked Python/uv/runtime, existing test/CLI runner, ResearchStore, стандартные JSON/schema utilities, существующая disposable sandbox. Не требуются Qlib/RD-Agent install, LangGraph, Neo4j, MLflow, OpenTelemetry service, new MCP, embeddings или paid agents. Named consumer новых capabilities — actual ordinary author/cold reader; неизвестная future интеграция не основание зависимости.

Для product runs: controlled synthetic inputs, no real stores/secrets/holdouts, no provider egress, owned mounts/processes, independent before/after inventory. Если работа read-only — реальная read-only проверка. Model transport только через уже разрешённую возможность и safe packets; не давать модели Docker socket/host tooling под видом sandbox.

**Не авторизованы этим документом:** merge, deploy, settings/security grants, purchase, новая подписка/API credential, внешние writes, реальный collection/look/holdout, wallet/signer/transaction, money, history rewrite и очистка чужих ресурсов. При передаче executor владельцем эти запреты не мешают routine engineering внутри его task, но требуют точного отдельного gate для перечисленных действий.

## 24. Resource/stopping rules и handback

Выбрать практический resource envelope из существующей среды до массовых runs: product CPU/RAM/storage/timeout и model cost отдельно. Учитывать все retained attempts. Не наследовать буквально «56 charters / 200 sequences / 4 retries»; использовать actual impact graph и цену нового evidence. Не менять научный budget под предлогом engineering campaign.

Продолжать пока next probe различает material cause, закрывает непроверенный edge, проверяет regression или действительно оценивает declared instability. Если серия действий повторяет тот же seam без новой информации — менять диагностику/дизайн, а не устраивать reroll until green. Смена owner outcome, новый evaluator, новый provider, destructive action или невозможность доказать isolation — stop соответствующего lane, завершить независимую безопасную часть.

Checkpoint при необходимости:

```text
goal / exact outcome and scope
base + current candidate + current policy refs
verified source owners and selected design
completed/failed/invalidated attempts + actual artifact locators
remaining material obligations / exact blocked boundary
technical vs quality conclusions
resource use / current grants / owned processes
exact next command or source question
prohibited assumptions (no new look, no rewritten old basis, no automatic reopen)
```

Final handback: verdict → какой путь теперь реально работает → strongest independent evidence → как сохранены old contracts/guards → что не доказано → один next step. Не «добавлены N файлов» и не «всё production-ready».

---

# Часть VI. Примеры смысла и дальнейшее развитие

## 25. Три предметных примера

### A. Избыточный новый вопрос

Предположим, exact bound universe уже требует holders ≥50. Предлагается test только holders ≥3. При этих предусловиях такой predicate не разделит текущую популяцию. Прежний исторический H≥3 recipe в другой популяции остаётся исторически корректно читаемым. Более содержательный вопрос о Δholders не обязан быть избыточным. [U1, §2; G1]

Basis сохраняет: какой именно universe проверен, какой вопрос не различает данных, почему выбран STOP/другая разрешённая опция. Не записывает «holders family бесполезна». Срабатывание deterministic redundancy guard — не доказательство интеллекта модели.

### B. Не переносить старое отрицание за его пределы

История top-holders percentage содержит ограниченную sign replication, затем rejection конкретного top-quartile veto, затем measurement rebase. Это не история holder-count C1–C4. [U1, §2]

Корректный update: «данное правило не прошло этот protocol на прежнем measurement; перенос отказа ограничен позднейшим rebase». Reconsideration condition: «нужна проверенная новая measurement/protocol applicability», а не «разрешаю повторить MAIN». Current source chain обязана подтвердить точный статус перед consumer use.

### C. Перспективная формулировка при неподходящем evaluator

Две альтернативы различаются исполнимым выходом и failed-exit risk, а available capability возвращает лишь price-relative proxy. Нельзя выбрать его, а затем сделать execution вывод по красивому результату. Basis фиксирует gap или более узкий вопрос, который evaluator действительно отвечает. Если нет полезного разрешённого различения — STOP/capability option. Патч не дописывает NetReturn engine ради завершения примера.

## 26. Защита от «умной бюрократии»

- Заполняем связь для **реального существенного выбора**, не протоколируем каждую внутреннюю мысль или tool call.
- Routine known test может сослаться на existing accepted rationale; не обязан заново генерировать rivals и таблицу.
- `NOT_RECORDED`, `UNKNOWN`, `NONE` имеют точный смысл и не автоматически проваливают обычный старый путь.
- Модель свободна предложить иной научный вопрос в рамках authority; schema проверяет transport/integrity, а не творческую ортодоксию.
- Новая схема не задаёт обязательную taxonomy всего рынка и не заставляет заполнить все niches.
- Нельзя улучшить quality score простым наращиванием длины; полная цена включает подготовку и чтение объяснения человеком.
- Не сохранять скрытый chain-of-thought. Нужны публичное краткое обоснование, выбранное действие, факты, source refs и outcome mapping.

## 27. NOW / WATCH

**NOW:** `FORGE_DECISION_LINK_V1`, если Entry подтверждает потерю material decision linkage; иначе доказанное reuse и маленький distinct-treatment probe без нового слоя.

**WATCH:** более сильная selection policy / маленький repertoire альтернатив. Trigger — на новых заранее выбранных задачах repeatedly observed ошибки выбора при уже полном decision link: ложное закрытие, неверный перенос урока, пропуск различающего теста, высокое operator rework. Тогда расширять ровно этот consumer, сохраняя evaluator и exposure boundary.

Само накопление records, число агентов и наличие свободных дней до cohorts не являются trigger для нового controller. После ремонта capability использовать, а не немедленно проектировать следующий governance слой.

---

# Источники и область проверки

Все внешние источники читались 10.10.2026; результатов авторов мы самостоятельно не воспроизводили. Repo refs ниже — research evidence, не замена current Git Entry исполнителя.

## Пользовательские материалы

- **[U1]** `SMIAL_Strategic_Reframe_V3_2026-10-10.md`, SHA256 `bd41b28b6f9e603327e7dd8465331d1c05b3ad25371476b2d08b13dabeb4872a`. Особенно §§1–2, 5, 8, 10, 13, 16. Исходный NOW — report-only decision-reuse probe, не разрешение менять science.
- **[U2]** `Вставленный текст(20261010-164340).txt`, Big Agentic Audit Portable V2, SHA256 `4842a9cc127152abe3fcac8c2b537111d44de9a72cabbadf64285d942a18ef16`. Переиспользованы obligations, real seams, independent oracles, fidelity, recovery, actor boundaries и adaptive evidence economy; широкая campaign не копировалась.

## Git — точные owners

- **[G0]** [main research base](https://github.com/lancerbeta/solana-alpha-lab/commit/76993054cfaeeee7e9fb6e7b718add8cf27e404a); [AGENTS.md](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/AGENTS.md); [semantic map](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/docs/FACTORY_SEMANTIC_MAP.md).
- **[G1]** [Operator A5/A9/A10 и native routes](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md).
- **[G2]** [HFIC config](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/configs/hypothesis_forge_independent_critic_v1.yaml); [draft schema](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/catalog/schemas/hypothesis_forge_draft_v1_2.schema.json).
- **[G3]** [ordinary request, reservation, accounting and replay](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/src/solana_alpha_lab/factory/hfic_ordinary_operation.py).
- **[G4]** [evidence-guided generation contract](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/docs/contracts/forge_evidence_guided_generation_v1.md).
- **[G5]** [EGG retained readout and quality limits](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/docs/evidence/forge_evidence_guided_generation_v1/READOUT.md).
- **[G6]** [scientific disposition continuity](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/docs/contracts/hfic_scientific_disposition_continuity_v1.md).
- **[G7]** [generation context source/ref/cutoff implementation](https://github.com/lancerbeta/solana-alpha-lab/blob/76993054cfaeeee7e9fb6e7b718add8cf27e404a/src/solana_alpha_lab/factory/hfic_generation_context.py).

## Внешние первоисточники

- **[E1]** [R&D-Agent-Quant paper, v2](https://arxiv.org/html/2505.15155v2).
- **[E2]** [RD-Agent core proposal/Trace](https://github.com/microsoft/RD-Agent/blob/main/rdagent/core/proposal.py), просмотренный Git blob `39cd0523c8075347171863b1f11cba669034c170` (main URL mutable; exact blob указан для повторной проверки).
- **[E3]** [Qlib Recorder official documentation](https://qlib.readthedocs.io/en/stable/component/recorder.html).
- **[E4]** [AutoScientist-Quant, official Google Research publication](https://research.google/pubs/autoscientist-quant-self-evolving-coding-agents-for-automatic-research-in-quantitative-investment/); [paper v2](https://arxiv.org/html/2608.28632v2).
- **[E5]** [FactorMiner paper v2](https://arxiv.org/html/2602.14670v2).
- **[E6]** [ReasoningBank, official Google Research](https://www.research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/); [official research implementation](https://github.com/google-research/reasoning-bank).
- **[E7]** [W3C PROV-DM](https://www.w3.org/TR/prov-dm/). Использована концептуальная семантика provenance, не рекомендация внедрять весь стандарт.
- **[E8]** [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents); [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

**Checkpoint этого документа:** RESEARCH+DESIGN завершены в описанном scope. Implementation, synthetic qualification, model comparison, new market research и rollout не выполнялись. Exact resume point исполнителя — §15 / S0, current Git Entry и cold-consumer gap probe, а не немедленное создание новой схемы.
