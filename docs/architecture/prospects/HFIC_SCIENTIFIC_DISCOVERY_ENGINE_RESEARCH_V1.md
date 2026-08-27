# Hypothesis Forge как научная машина поиска: независимый синтез V1

**Дата:** 2026-08-27  
**Контекст:** Solana Alpha Lab, production HFIC после успешного `NO_WORTHY_HYPOTHESIS` smoke  
**Цель:** определить, какие научные и инженерные подходы действительно способны превратить ручную Кузницу в труднокопируемый discovery engine — от архитектуры автономных космических систем до достижимых атомов ближайшего года.

## Прямой вывод

Исходный ресерч в целом сильный: он правильно ставит experimental design, statistical validity, memory и execution truth выше «ещё более умного LLM». Но его рейтинг слишком рано перескакивает от конституции научной фабрики к конкретным моделям — Hawkes, GNN, RL, foundation models. Для текущей Solana Alpha Lab это как выбирать алгоритм наведения телескопа, когда у аппарата один узкий датчик и неполная карта того, что он уже видел.

Главный bottleneck сейчас — **не качество генерации текста и не отсутствие сложной математики**. Это разрыв между:

1. картой реально доступных, PIT-safe и ещё не потреблённых наблюдений;
2. систематическим покрытием разных механизмов, а не вариаций одной семьи;
3. выбором следующего evidence-bearing действия;
4. статистической защитой от адаптивного поиска;
5. дешёвым, независимым и исполнимым evaluator'ом.

Поэтому ближайшая эволюция должна выглядеть не как `HFIC → больше агентов → автономный генератор`, а как:

```text
EVIDENCE WORLD MODEL
→ QUALITY-DIVERSITY EXPLORATION
→ ONE DECISION-BEARING QUESTION
→ PRE-REGISTERED FALSIFIER + NEGATIVE CONTROLS
→ MINIMAL FRESH EVIDENCE
→ ANYTIME-VALID KILL / CONTINUE
→ MEMORY + SEARCH-DEBT UPDATE
```

LLM здесь — генератор и переводчик между дисциплинами. Интеллект системы находится в устройстве цикла.

## Что переносить из других отраслей

| Донорская область | Что там решают | Полезный перенос в HFIC | Что не стоит копировать |
|---|---|---|---|
| **NASA/JPL spacecraft autonomy** | Автономно выбирать научные цели при ограничениях энергии, времени, связи и риска | State model, resource-bounded planning, layered verification, typed anomaly recovery | Тяжёлую космическую MBSE-бюрократию и модель «всё известно заранее» |
| **Self-driving laboratories** | Выбирать следующий дорогой физический эксперимент по результатам предыдущих | Closed loop, active learning, failure-as-data, experiment value per cost | Иллюзию, что trading имеет такой же чистый автоматический oracle, как XRD или компилятор |
| **FDA adaptive/platform trials** | Адаптивно отбрасывать слабые arms, сохраняя валидность вывода | Заранее разрешённые ветки, futility stops, общий control, exploration/confirmation split | Медицинские sample-size шаблоны без адаптации к clustered time-series |
| **Intelligence analysis** | Сравнивать конкурирующие объяснения при неполной и противоречивой информации | Абдукция, diagnostic evidence, поиск опровергающих наблюдений | ACH как «магическую таблицу»: эмпирическая эффективность метода смешанная |
| **Software verification** | Находить ошибки, когда правильный ответ неизвестен или дорог | Metamorphic relations: какие преобразования должны сохранять, уничтожать или инвертировать эффект | Считать, что прохождение тестов доказывает экономический механизм |
| **Epidemiology** | Выявлять скрытое смешение причин и систематические bias | Negative-control exposure/outcome и falsification endpoints | Причинные заявления без подходящих environments и сильных предпосылок |
| **Evolutionary robotics** | Не схлопывать поиск в один локальный optimum | Quality-diversity / MAP-Elites: лучший кандидат в каждой механистической нише | Безлимитное размножение вариантов и optimization по уже потреблённому Y |
| **Financial econometrics** | Отделять фактор от результата data snooping | Global trial/search ledger, deflated evidence, Reality Check, familywise/FDR discipline | Одну универсальную поправку, якобы компенсирующую любой adaptive search |
| **Reliability engineering** | Обнаруживать, изолировать и восстанавливаться после отказов | Evidence FDIR: DATA / MODEL / OPERATOR / SOFTWARE / MARKET anomaly attribution | Превращать каждую отрицательную гипотезу в инфраструктурный инцидент |
| **Ecology/medicine** | Моделировать жизненный цикл, смерть и конкурирующие исходы | Survival, hazard, competing risks для route/liquidity/attention/price failure | Сводить всё к одному binary winner label |

Главный урок NASA не в «начинке корабля», а в архитектуре доверия. В Autonomous Sciencecraft Experiment научный анализ порождал observation requests, planner проверял их, robust executor проверял planner, а fault protection контролировал уже исполняемые команды. Авторы отдельно отмечали, что наиболее частыми были **ошибки модели мира**, часть которых не обнаружилась из-за отсутствия высокоточного testbed. Для HFIC это прямое предупреждение: интеллект генератора не компенсирует бедную или неверную evidence model. [JPL ASE](https://ai.jpl.nasa.gov/public/documents/papers/tran-sasemas2005-PreventingResponding.pdf)

AEGIS на марсоходах тоже не «рассуждает обо всём Марсе»: он анализирует доступное изображение, ранжирует цели по заданным критериям и направляет конкретный инструмент. Это правильная модель bounded autonomy для Forge. [JPL AEGIS](https://ml.jpl.nasa.gov/products.html)

## Моя матрица приоритетов

Шкала: `1` — низко/просто, `5` — высоко/сложно. `Реальность` означает применимость к текущим данным, RDP и ручному HFIC, а не общую зрелость метода в науке.

| № | «Мозг» / перенос | Что добавляет Forge | Почему важен именно сейчас | Сложн. | Реальность | Fit | Impact | Durable edge | Горизонт |
|---:|---|---|---|---:|---:|---:|---:|---:|---|
| **1** | **Evidence Opportunity World Model** — spacecraft state estimation + mission planning | Единую карту `observed / derivable / missing / consumed / closed / collectable`, включая стоимость и first reliable availability | Production smoke показал: правильный `NO_WORTHY`, но следующий evidence action не встроен. Без карты frontier генератор либо повторяется, либо строит preparatory loops | 2 | 5 | 5 | 5 | 4 | сейчас–3 мес |
| **2** | **Quality-Diversity mechanism map** — MAP-Elites / novelty archive | Не один глобальный ranking, а лучшего кандидата в каждой нише `actor × mechanism × state transition × observable × estimand` | Прямо лечит схлопывание в quote-native/H900 и «шесть разных названий одного X» | 3 | 5 | 5 | 5 | 5 | сейчас–6 мес |
| **3** | **Adaptive-analysis firewall + search debt** | Учитывает каждый prompt, visual look, transform, threshold, reopen и family-relative attempt | В automated discovery главный риск — не пропустить alpha, а заслуженно поверить ложной alpha. Finance давно показывает, что повторное использование данных требует более высокого evidence hurdle | 3 | 5 | 5 | 5 | 5 | сейчас–6 мес |
| **4** | **Exploration / confirmation protocol** — adaptive clinical trials | Явные роли dataset: discovery, validation, fresh confirmation; заранее разрешённые ветки `drop / extend / collect / stop` | Уже есть правильные labels, но ветка `NO_WORTHY → next evidence option` ещё не замкнута | 2 | 5 | 5 | 5 | 4 | сейчас–3 мес |
| **5** | **Negative controls + metamorphic falsification** | Для каждой карты: что должно не меняться, исчезнуть или инвертироваться, если механизм реален | Дешевле нового сложного model. Отличает mechanism от proxy, regime confounding и measurement artifact | 2 | 4 | 5 | 5 | 5 | сейчас–6 мес |
| **6** | **Claim–Evidence–Argument assurance graph** — NASA assurance cases | Явно связывает claim, evidence, warrant, counterargument и остаточную неопределённость | RDP уже умеет provenance; следующий шаг — не больше receipts, а проверяемая логика «почему evidence поддерживает именно этот вывод» | 2 | 5 | 5 | 4 | 4 | сейчас–3 мес |
| **7** | **Evidence FDIR** — fault detection, isolation, recovery | Разделяет `DATA_GAP / MODEL_GAP / OPERATOR_GAP / SOFTWARE_DEFECT / MARKET_NULL / REGIME_MISMATCH` | Не даёт лечить отсутствие alpha патчем инфраструктуры и, наоборот, считать broken sensor отрицательным market evidence | 2 | 5 | 5 | 4 | 3 | сейчас–3 мес |
| **8** | **Value of Information / Bayesian experiment design** | Выбирает не самую красивую гипотезу, а observation с максимальным ожидаемым снижением decision uncertainty на call/час/$ | Это будущий настоящий scheduler Factory. Но сначала нужны world model, candidate diversity и хотя бы несколько повторяемых evidence windows | 3 | 4 | 5 | 5 | 5 | 3–9 мес |
| **9** | **Anytime-valid sequential kill / futility** | Позволяет законно остановить слабую family по мере поступления данных, не делая вид, что optional stopping бесплатен | Идеально для дорогих prospective windows и вечерних циклов; снижает стоимость отрицательной истины | 3 | 3 | 5 | 5 | 5 | 3–9 мес |
| **10** | **Abductive competing-mechanism matrix** — intelligence analysis | Один observable одновременно объясняется несколькими механизмами; выбирается evidence с максимальной diagnosticity | Forge сейчас умеет дивергенцию по классам, но ещё слабо заставляет кандидатов конкурировать за одно наблюдение | 2 | 5 | 5 | 4 | 3 | сейчас–6 мес |
| **11** | **Cohort-relative / cross-sectional state** | Заменяет абсолютные thresholds на contemporaneous rank, attention share, liquidity share и survival относительно запусков того же часа | Дёшево, PIT-естественно и устойчивее к scale drift; текущий multi-token panel уже ближе к такой постановке | 2 | 4 | 5 | 5 | 5 | сейчас–6 мес |
| **12** | **Survival / hazard / competing risks** | Предсказывает не «winner», а время до route loss, liquidity collapse, attention death, drawdown или recovery | Мемкоин — lifecycle object; эта постановка часто экономически ближе к veto/exit, чем regression будущего return | 3 | 3 | 5 | 5 | 5 | 3–9 мес |
| **13** | **Executable microstructure world** | Route topology, notional response, impact asymmetry, quote availability, adverse-selection proxies | Это ближайший к cash layer и уже частично существует; преимущество возникает из собственных PIT quote surfaces, а не из общедоступной свечи | 3 | 4 | 5 | 5 | 5 | сейчас–9 мес |
| **14** | **Regime/environment model** — changepoints, drift, coarse state | Различает dead mechanism, временно неподходящий regime и measurement shift | Нестационарность здесь — часть объекта. Но sophisticated HMM сейчас преждевременен; сначала достаточно coarse, заранее заданных environments | 3 | 3 | 5 | 5 | 5 | 3–12 мес |
| **15** | **Bayesian family memory + hierarchical partial pooling** | Обновляет prior mechanism family и соединяет token/window/regime evidence без ложного IID | Станет очень ценным после нескольких независимых windows; на нынешних 24 mint может лишь математически оформить нехватку данных | 4 | 2 | 5 | 4 | 5 | 6–15 мес |
| **16** | **Symbolic/program discovery + deterministic evaluator** — FunSearch/AlphaEvolve pattern | LLM создаёт короткие интерпретируемые transforms/rules, evaluator проверяет typing, PIT, cost и frozen metric | Перспективнее «LLM пишет гипотезы», но только когда evaluator не равен consumed backtest. Иначе это сверхскоростной p-hacking | 4 | 2 | 5 | 4 | 4 | 9–18 мес |
| **17** | **Invariant prediction / environment stress tests** | Ищет связи, сохраняющиеся между днями, launchpad/cohort/regime, и явно показывает их границы | Полезнее громкого causal-discovery claim. Требует нескольких environments и не отменяет сильных assumptions | 5 | 2 | 4 | 4 | 4 | 9–18 мес |
| **18** | **Marked event processes / Hawkes** | Моделирует clustering и возбуждение buy/sell/route events | Отлично соответствует cascade physics, но без нормального event stream это дорогая формула над отсутствующими данными | 4 | 1 | 4 | 4 | 4 | 12–24 мес |
| **19** | **Temporal actor graph / motifs** | Повторяющиеся deployer/funder/buyer структуры, capital migration, coordination | Потенциально сильный proprietary moat, но high-risk data engineering; раньше named consumer легко породит год preparatory work | 5 | 1 | 4 | 5 | 5 | 12–24 мес |
| **20** | **Co-Scientist tournament / evolutionary hypothesis population** | Generation, proximity, reflection, ranking и evolution нескольких гипотез | Современное направление реально развивается, но число агентов — commodity. Без evidence evaluator турнир выбирает наиболее убедительный текст | 4 | 3 | 4 | 3 | 2 | 9–18 мес |
| **21** | **Decision-focused learning + calibrated abstention + robust utility** | Оптимизирует downstream trading decision/regret, а не forecast accuracy; умеет `ABSTAIN` | Очень важно на promotion/risk layer, но не решает сегодняшнюю бедность discovery evidence | 4 | 2 | 4 | 4 | 4 | 12–24 мес |
| **22** | **Contextual bandit for research budget** | Распределяет calls/время между mechanism families по learning progress | Естественный meta-controller после десятков честных cycles; сейчас posterior почти целиком состоит из prior | 4 | 1 | 5 | 4 | 4 | 12–24 мес |
| **23** | **RL / agent-based digital twin / giant GNN / foundation model** | Multi-step policy и синтетические counterfactual worlds | Может стать полезным поздно, но сейчас сильнее увеличит surface area самообмана, чем discovery power | 5 | 1 | 3 | 3 | 2 | 24+ мес |

## Чем эта версия отличается от исходной

### Что в исходнике нужно оставить

- Information gain / cost как objective научного расхода.
- Multiplicity и search debt как системный governor.
- Anytime-valid inference для последовательных окон.
- Regime, microstructure, survival и hierarchical evidence как domain-native toolbox.
- Скепсис к RL, foundation models, giant GNN и «совету из двадцати агентов».

### Что было недооценено

1. **Quality-diversity важнее раннего scalar ranker.** Обычный ranker снова выберет знакомую family, потому что у неё больше prior artifacts и легче сформулировать falsifier. MAP-Elites-подобный архив сохраняет одного сильного кандидата в каждой механистической нише и делает пустые области видимыми. Исходная работа MAP-Elites именно про «освещение» пространства, а не поиск одного optimum. [Mouret & Clune](https://arxiv.org/abs/1504.04909)
2. **Metamorphic и negative-control tests — дешёвый недостающий слой.** Если X якобы измеряет taker pressure, эффект должен разрушаться или меняться предсказуемо при controls, не связанных с механизмом; если не разрушается, вероятен regime/measurement proxy. Negative controls используются для обнаружения confounding и bias в observational research. [Lipsitch et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC3053408/)
3. **Assurance logic важнее количества receipts.** NASA assurance case фиксирует не только evidence, но и почему claim следует из evidence, какие counterarguments рассмотрены. [NASA assurance cases](https://sma.nasa.gov/news/articles/newsitem/2020/09/22/new-tool-for-developing-safety-assurance-cases)
4. **Evaluator — центр автономной науки.** FunSearch и AlphaEvolve работают потому, что LLM-предложения можно быстро и автоматически проверить. [FunSearch](https://deepmind.google/blog/funsearch-making-new-discoveries-in-mathematical-sciences-using-large-language-models/), [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/). В trading evaluator шумный, нестационарный и подвержен adaptive reuse; поэтому переносить нужно архитектуру, но не масштаб search.
5. **`NO_WORTHY` должен маршрутизировать следующий epistemic action.** Голый `STOP` безопасен, но операционно незавершён. Он должен завершаться одним из `WAIT_FOR_NEW_EVIDENCE / FORWARD_DATA_OPTION_READY / CAPABILITY_OPTION_READY`, не исполняя действие без owner gate.

### Что было слегка переоценено

- **Bayesian experiment selection как P0-1.** Он действительно фундаментален, но сейчас выбирать почти не из чего: один узкий prospective panel, consumed Y и мало независимых environments. До world model и QD frontier Bayesian scheduler будет присваивать точные числа бедному набору вариантов.
- **Hawkes и causal ML как близкий moat.** Оба могут стать сильными, но требуют event history/environments, которых пока нет. Сегодня они скорее named future consumers, чем атомы.
- **Bayesian priors как автоматическая память.** Число в prior не делает предположение объективным. До достаточного family evidence лучше хранить ordinal belief + reason codes + bounds, не псевдоточность.
- **Critic ensemble.** Google Co-Scientist уже использует генерацию, proximity, reflection, ranking и evolution, но это подтверждает архитектурный паттерн, а не готовый перенос в finance. [Nature Co-Scientist](https://www.nature.com/articles/s41586-026-10644-y). Без независимого evaluator агенты способны только коррелированно спорить.

## Целевая архитектура: не шесть агентов, а семь функций

```text
1. SENSORIUM / EVIDENCE WORLD MODEL
   Что реально известно, доступно, потреблено и измеримо дальше
                         ↓
2. QUALITY-DIVERSITY EXPLORER
   Разные mechanism niches, contradiction и negative-space search
                         ↓
3. QUESTION & EXPERIMENT PLANNER
   Value of information / cost / feasibility / first reliable availability
                         ↓
4. STATISTICAL GOVERNOR
   Search debt / discovery-confirmation / sequential validity / controls
                         ↓
5. EXECUTION & EVALUATOR
   Frozen spec → Fast Lane / Change Lane / data option → typed result
                         ↓
6. ASSURANCE & FAULT MANAGEMENT
   Critic / claim-evidence argument / anomaly attribution / fail-closed
                         ↓
7. RESEARCH MEMORY
   Priors, terminals, failure modes, consumed evidence и learning progress
                         ↺
```

Это ближе к автономному научному аппарату, чем к чат-боту. Верхние слои свободно придумывают; чем ближе к данным, деньгам и мутациям, тем система детерминированнее и строже.

## Реалистичный прогноз импакта

Нельзя честно прогнозировать «+X% к alpha»: база содержит слишком мало независимых production cycles и ни одной найденной достойной новой гипотезы. Можно прогнозировать измеримые изменения научного процесса.

| Изменение | Наиболее вероятный эффект | Как проверить | Уверенность |
|---|---|---|---|
| `NO_WORTHY → typed next action` | Убирает экзотические ручные промпты и тупик после честного отказа | После одного slash owner получает один понятный следующий gate | Высокая |
| Evidence frontier + QD map | Резко снижает semantic duplicates и same-family collapse; не обязано повышать PASS-rate | 10 cycles: ≥4 непустые mechanism niches, duplicate/reopen share <20% | Средне-высокая |
| Search debt + confirmation firewall | Снижает ложные открытия; внешне может увеличить число `NO_WORTHY/KILL` | Любой reported effect связан со всеми trials и fresh confirmation status | Высокая |
| Negative controls + metamorphic tests | Быстрее убивает proxy-механизмы до дорогого forward collection | Каждая selected card имеет ≥1 negative control и ≥1 invariance/inversion test | Средне-высокая |
| Новый multi-window prospective sensorium | Единственный ближайший ход, реально способный создать новые исполнимые X/Y | Появляются несколько unconsumed PIT environments и хотя бы один critic-worthy falsifier | Средняя |
| Sequential/VoI planner после накопления окон | Меньше calls и времени до того же decision quality | Сравнить calls/time-to-kill с фиксированными планами на 5–10 families | Средняя, пока не измерено |
| Co-Scientist / evolutionary search сейчас | Больше красивых кандидатов, но слабый прирост истины | Вероятен рост rejected duplicates без роста fresh-confirmed effects | Средне-высокая |

Self-driving labs показывают, что closed-loop active learning способен резко сократить число физических экспериментов, но перенос чисел в рынок был бы нечестным: у материалов есть физический instrument oracle, у стратегии — noisy adaptive outcome. Даже A-Lab, сочетавшая historical knowledge, ML, robotics и active learning, имела как успешные, так и computational/synthesis failure modes; позднее публикация потребовала correction. Это усиливает, а не ослабляет тезис о независимой верификации. [A-Lab](https://www.nature.com/articles/s41586-023-06734-w), [correction coverage](https://cen.acs.org/research-integrity/Nature-robot-chemist-paper-corrected/104/web/2026/01)

## Что делать в Solana Alpha Lab

### Сейчас: один небольшой closure, не «строительство ranker»

`HFIC_NO_WORTHY_NEXT_ACTION_V1` должен встроить в обычный `/hypothesis-forge` автоматическую ветку:

- `WAIT_FOR_NEW_EVIDENCE` — если новый сбор не оправдан;
- `FORWARD_DATA_OPTION_READY` — ровно один bounded capture contract;
- `CAPABILITY_OPTION_READY` — ровно одна capability delta с named consumer;
- ни collection, ни Git, ни experiment без owner gate.

Это убирает ручной метапромпт, но не даёт Forge превращать каждый `NO_WORTHY` в инфраструктурный проект.

### Следом: две компактные интеллектуальные надстройки

1. **`HFIC_QUALITY_DIVERSITY_PORTFOLIO_V1`**  
   Candidate coordinates: `actor / mechanism / state transition / observable / estimand / failure mode`. Один elite на niche, novelty floor, пустые niches видимы, expected alpha не используется при генерации.
2. **`HFIC_FALSIFICATION_CONTROLS_AND_SEARCH_DEBT_V1`**  
   Каждая selected card обязана назвать discovery/confirmation role, trial budget, negative control, metamorphic relation и какие попытки входят в family search debt.

### Затем: не собирать «всё», а расширить sensorium

Следующая prospective campaign должна дать не двадцать новых колонок, а несколько ортогональных наблюдательных осей на одном contemporaneous cohort и unconsumed outcomes:

- relative attention/flow state;
- executable liquidity/route fragility по нескольким notionals;
- lifecycle/hazard clocks;
- coarse contemporaneous market/cohort regime;
- typed missingness и provider failure как данные.

Ключевой дизайн: один primary preregistered falsifier, остальные новые observables — discovery-only до следующего fresh window. Иначе расширение sensorium мгновенно превращается в расширение p-hacking surface.

### После 3–5 независимых evidence epochs

Только тогда материализовать:

- VoI scheduler;
- anytime-valid futility/continuation;
- coarse regime model;
- hierarchical family priors;
- survival/competing-risks baselines.

Hawkes, graph/entity layer, symbolic evolution, Co-Scientist tournament и research-budget bandit должны ждать named consumer и достаточный event/environment history.

## Итоговый Top-10 для ближайших 12 месяцев

| Приоритет | Направление | Почему именно оно |
|---:|---|---|
| **P0-1** | Evidence Opportunity World Model + typed next action | Замыкает цикл после `NO_WORTHY` и показывает реальный frontier |
| **P0-2** | Quality-Diversity mechanism map | Лечит наблюдавшееся схлопывание семей |
| **P0-3** | Exploration/confirmation firewall + search debt | Не позволяет автоматизации масштабировать самообман |
| **P0-4** | Negative controls + metamorphic falsifiers | Максимальный kill-value за минимальную стоимость |
| **P0-5** | Prospective multi-window sensorium | Единственный слой, создающий действительно новую evidence surface |
| **P1-6** | Cohort-relative/cross-sectional state | Дёшево и устойчиво к scale/regime drift |
| **P1-7** | Survival/competing risks | Правильный язык жизненного цикла мемкоина |
| **P1-8** | Executable microstructure | Ближайшая связь research result с реальными деньгами |
| **P1-9** | VoI experiment scheduler | Делает следующий научный расход оптимальным, когда появится выбор |
| **P1-10** | Anytime-valid sequential inference | Сокращает time/calls-to-kill без статистического мошенничества |

## Финальный вердикт

Исходная формула «moat = memory + priors + experimental design + statistical validity + ontology + execution truth» верна. Моя поправка: перед priors и experiment ranking нужен ещё один фундаментальный слой — **evidence opportunity model + quality-diversity frontier**.

Сегодня у проекта уже есть хороший flight computer, журнал миссии, safety interlocks и независимый mission review. Но sensorium пока узок, а onboard scientist после честного `NO_WORTHY` не умеет сам сформулировать один следующий измерительный манёвр. Поэтому ближайший высокий импакт — не «волшебный шар» как более творческая модель, а **автономный выбор следующего проверяемого вопроса и минимального нового наблюдения**.

Когда этот контур замкнётся, более сильные модели действительно дадут рычаг: они будут исследовать структурированное пространство и получать проверяемую обратную связь. До этого они лишь быстрее наполняют архив красиво сформулированными отказами.

## Источники и ограничения

Матрица — инженерный синтез, а не мета-анализ effect sizes. Баллы отражают текущую зрелость Solana Alpha Lab и должны пересматриваться после накопления production cycles. Ключевые основания:

- [JPL Autonomous Sciencecraft: safe layered autonomy](https://ai.jpl.nasa.gov/public/documents/papers/tran-sasemas2005-PreventingResponding.pdf)
- [NASA Systems Engineering Handbook](https://science.nasa.gov/wp-content/uploads/2023/04/nasa_systems_engineering_handbook_0.pdf)
- [NASA assurance cases](https://sma.nasa.gov/news/articles/newsitem/2020/09/22/new-tool-for-developing-safety-assurance-cases)
- [FDA Adaptive Designs Guidance](https://www.fda.gov/media/78495/download)
- [Dwork et al.: reusable holdout and adaptive data analysis](https://www.cis.upenn.edu/~aaroth/reusable.html)
- [White: Reality Check for Data Snooping](https://users.ssc.wisc.edu/~behansen/718/White2000.pdf)
- [Harvey, Liu & Zhu: multiple testing in expected returns](https://academic.oup.com/rfs/article/29/1/5/1843824)
- [Johari et al.: always-valid inference](https://ideas.repec.org/a/inm/oropre/v70y2022i3p1806-1821.html)
- [Mouret & Clune: MAP-Elites](https://arxiv.org/abs/1504.04909)
- [Lipsitch et al.: negative controls](https://pmc.ncbi.nlm.nih.gov/articles/PMC3053408/)
- [Peters, Bühlmann & Meinshausen: invariant prediction](https://arxiv.org/abs/1501.01332)
- [DeepMind FunSearch](https://www.nature.com/articles/s41586-023-06924-6)
- [DeepMind AlphaEvolve](https://arxiv.org/abs/2506.13131)
- [Google/DeepMind Co-Scientist](https://www.nature.com/articles/s41586-026-10644-y)
- [A-Lab autonomous materials discovery](https://www.nature.com/articles/s41586-023-06734-w)

