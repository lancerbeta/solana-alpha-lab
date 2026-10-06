> Repo note (2026-10-06, SWITCH_AND_BIND): stored verbatim from the owner-provided file
> (trailing whitespace stripped). `NEXT_EXECUTOR_PROMPT_RU.md` is an operational command, not
> in Git. The runbook correction in section 2/G5 is now in
> `docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md`; the route qualification is in
> `CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-011` (parser PASS, pace UNPROVEN). This file
> grants no authority for any later phase.

# SMIAL — от запуска Jupiter до полезного исследовательского решения
## Operating Blueprint + Runbook V1 · 6 октября 2026

**Кому:** Пётр, Project Chat, coding/operations executor.
**Режим этого документа:** DESIGN. Это сохраняемая программа и основание для отдельных точных команд, а не разрешение на все будущие изменения.
**Проверенный Git anchor:** `lancerbeta/solana-alpha-lab`, main `9efc74c0d57b10addcc4fe31155e2333fbac13c3`. На каждом выполнении проверить актуальный Git.
**Последний источник о VPS:** отчёт исполнителя, приведённый владельцем 6 октября 2026. Его исходные operational receipts в этой design-сессии не перечитывались.
**Продолжение:** утверждённого `SMIAL_Opportunity_Episodes_JUPITER_CORE_Blueprint_V1_2026-10-05.md`, не замена научных invariants.
**Первый следующий шаг:** `JUPITER_CORE_COMMISSIONING / SWITCH_AND_BIND`; точная команда — отдельный файл `NEXT_EXECUTOR_PROMPT_RU.md`.

---

## 1. Решение для владельца

**Переключаемся на Jupiter как единственный основной сбор. Не ждём legacy до 12–13 октября и не ремонтируем совместный pacing ради сохранения низкоценного потока.** Старый сбор обратимо останавливаем; историю сохраняем, непроснятый хвост честно отмечаем. Две постоянные intake-lanes сейчас не нужны.

После безопасного переключения: небольшой настоящий запуск → полный цикл доставки → работа на 100 допусках в сутки → использование данных и измерение хранения → при доказанном спросе 200/сутки → ограниченная проверка гипотез → решение продолжить, изменить конкретный подход или прекратить направление. Не наращиваем инфраструктуру вместо использования.

**Цель — не 1000 строк в неделю.** Цель — регулярно получать достаточно разнообразных пригодных эпизодов, чтобы дешёво проверять механизмы краткосрочного движения и отбраковывать слабые идеи. Конечная цель SMIAL — реализуемый чистый доход после затрат, но сбор и статистическая ассоциация его ещё не доказывают.

### Что считаем успехом этой программы

1. Jupiter работает в ограниченном ресурсе без регулярного вмешательства владельца.
2. Готовые данные одной обычной командой попадают с VPS на ПК и доступны свежей Forge.
3. Есть сотни пригодных эпизодов в неделю; тысяча и более — следующий доказуемый режим, не обещание источника.
4. Пройдены минимум один содержательный исследовательский цикл и его повторное использование без изменения collector-кода под вопрос.
5. Горячее хранение ограничено сроком и незавершённой работой; долговечны сами наблюдения, нужный богатый контекст и доказательства происхождения, а не вся история исполнения.
6. По направлению принято решение на данных. Честное опровержение полезно; бессрочный `UNKNOWN` и месяцы только технических PR — нет.

Это программа data/research operation. Деньги, signer, trading/execution infrastructure и продвижение стратегии требуют следующих отдельных решений.

---

## 2. Что известно, что не доказано, что исправляет этот план

### Подтверждено текущим Git [G1–G5]

- Есть публичная ветка Opportunity Episodes, versioned `NOMINATION_T0`, 139 planned points до 72h, PRICE/LIQUIDITY/HOLDERS/TIME, штатные delivery/import/Forge owners.
- В PR #377 добавлена явная подготовка ускоренного writer lookup; это не выполненная на VPS подготовка и не сокращение хранилища.
- В PR #378 добавлены durable round plan и отказ в нормальном выпуске неоднозначного/частично выполненного после crash отбора.
- `pause_schedule` переводит activation в `PAUSED_OPERATOR` и пишет lifecycle evidence. Он останавливает и приём, и наблюдения этой activation.
- Episode `stop-intake` — иной control: закрывает новые admissions, оставляя принятые trajectories. Его нельзя предполагать доступным для legacy.
- **V1 не допускает ceiling выше 100/сутки:** ограничение есть в semantic validator и schema. Максимум при полном заполнении — 700 admissions за семь суток. Это не просто default YAML.
- Текущий schedule требует raw retention не меньше 11 дней. Фактическая eviction/compaction не следует из наличия этого поля.

### По последнему отчёту исполнителя [U1], не новый live readback

- VPS: 6 vCPU, примерно 6.2 GB RAM, без swap; filesystem 103 GB, свободно около 78 GB; недавних OOM не найдено.
- Установлен `27366b752cd0fae9683dd50373ea8ff8da5a6f6d`, а не новый main.
- OPS около 5.02 GB; RDP около 5.92 GB; local backup около 5.03 GB. Эти слои нельзя путать с размером нового episode corpus.
- Один relevant legacy scope ACTIVE: `ACT-2B6CC977`, schedule key `OBS-EMERGENCY-FORWARD-20261004T094500Z`; exact schedule SHA взять из machine readback, не вывести из имени.
- Другой scope PAUSED; три ABORTED, в двух остаются 438 старых PENDING. Их не оживляем и не переписываем ради «везде COMPLETE».
- Совместная работа legacy+episode провалила account pacing: после episode первый legacy request ушёл через 1 s при принятой паузе 3 s.
- Scratch restore mutable state и additive open новым кодом прошли; immutable RDP был скопирован с живого хоста, а не восстановлен off-host. Полный disaster restore НЕ доказан.
- Scratch writer lookup: 54 s, 181 MB RSS, около 5.1 MB и 8427 новых файлов; это измерение на конкретной копии, не универсальный SLA.
- Copy receipt: `ea090a83cf62d234ddbc7e9e47ec103cfaa95b065fadcd15bf2e9182d0340ede`.
- Три category 5m и один SEARCH дали parser-compatible HTTP 200. SEARCH проверял только публичный USDC mint.
- Protection assignment inventory не создан. Пустой каталог не доказывает отсутствие защищённых исследовательских данных.

### Важные поправки к прежним рекомендациям

**Не ждать legacy.** Ожидание и ремонт overlap — не единственные варианты. Приоритет нового направления оправдывает явное прекращение старого, с сохранением прошлых данных и признанием потери будущих наблюдений.

**Не требовать нового диска.** Backup на том же filesystem допустим как локальная recovery-копия; защита от потери VPS должна принадлежать проверенному внешнему хранению. Отдельный том сам по себе не решает обе задачи.

**Не выдавать writer optimization за экономию GB.** Ускорение append устраняет повторное чтение всей истории. Retention/compaction — другой, ещё не выполненный результат.

**Не обещать размер 5–25 GB/год.** Это допустимая целевая модель одной компактной копии, не замер богатого production-потока и не сумма всех backups/raw.

**Четыре probe не доказали account safety.** Исполнитель сообщил, что они шли тем же ключом параллельно legacy без общей паузы. Сохранить как `parser/route qualification PASS`; shared-account discipline — FAILED/UNPROVEN в том проходе. Не переписывать receipt и не повторять те же requests только ради чистой истории.

**«16 полезных из четырёх когорт» — свидетельство владельца о прежней продуктивности, не новый статистический расчёт.** Его достаточно, чтобы не тратить недели на сохранение старого collector; недостаточно для утверждения, что весь newborn-рынок не содержит alpha.

---

## 3. Целевая простая система

```text
Jupiter: три activity-категории, один раунд каждые 15 минут
    → известные protection/asset/core правила
    → ограниченный воспроизводимый отбор
    → committed episode T0
    → 5m snapshots первые 6h, hourly до 72h
    → наблюдения + богатый payload + явные пропуски
    → действующий release/transport/import

VPS: только capture, активная работа, небольшой рабочий запас
    ↓ готовые неизменяемые данные
ПК: build/seal/import, компактный корпус, Forge и числовые расчёты
    ↓ проверенная резервная копия
Уже существующее внешнее хранилище: восстановление при потере VPS/ПК
```

Одна используемая capture-lane и один существующий scheduler. Новая SQLite, брокер, сервис, universal feature store, отдельный importer или backup-протокол не нужны. Начинаем с уже проверенных owners. Legacy-таблицы можно оставить в общей БД; их физическое удаление не prerequisite запуска.

Частота 5m/1h не повышается. Возраст токена не ограничивает эпизод возрастом рождения. T0 — момент нашего допуска, не старт pump. Категория с названием `5m` и наш раунд каждые 15m — разные часы.

**Упрощение относительно newborn:** не сопровождаем огромное число рождений в надежде, что несколько станут интересны; глубокое наблюдение начинается после пригодного contemporaneous snapshot. Не дублируем RECENT в новой lane. Но отрицательные исходы ПОСЛЕ admission обязательно остаются: иначе получим новый survivor-only dataset.

---

## 4. Дорожная карта с конечным результатом каждого этапа

Сроки относительны фактическому запуску. Они не основание объявить PASS. Фазы — не обязательные отдельные PR.

| Фаза | Результат | DoD | Решение дальше |
|---|---|---|---|
| A. SWITCH_AND_BIND — сейчас | Старый поток не мешает; точные bindings для запуска готовы | Legacy/renewal quiesced; receipts сохранены; protection выяснен; минимальный registry/runbook PR готов; reusable measurements не повторены | Merge только долговечных изменений, затем exact deploy gate |
| B. Первый живой цикл | Небольшой Jupiter canary действительно доставил данные | 24/day × 2 полных UTC дня; затем tail до 72h+rounding/grace; две реальные когорты через public path, повтор import, nonempty cold restore | PASS → 100/day. Supply/dependency/quality проблема → точечное решение, не бесконечный canary |
| C. Ограниченная рабочая эксплуатация | Сотни эпизодов и полезный запуск Forge | До 100/day, семь суток intake; ежедневная короткая карточка; первые зрелые когорты используются сразу; первый механизм проверен при достаточном support | Сохранить, расширить admission-cap или изменить доказанную границу данных |
| D. Облегчение хранения и, при спросе, capacity | Диск растёт предсказуемо; нет лишних постоянных копий | Измеренные bytes/day и bytes/episode; verified eviction на отдельной копии; recovery/replay сохранены; для >100/day — validated новый envelope | Применить разрешённую retention; при избытке qualified supply — 200/day |
| E. Новый поток в деле | Код+LLM+данные дают проверяемые решения, а не только архив | Ограниченная серия вопросов, простой baseline, negative control, затем один frozen chronological OOS при наличии кандидата | CONTINUE / REFRAME_DATA / CHANGE_REPRESENTATION / STOP_CURRENT_SCOPE |

### A. SWITCH_AND_BIND: что делаем прямо сейчас

Используем имеющийся публичный pause, а не новый legacy drain. Останавливаем только запускающие collector и legacy-renewal triggers, даём уже выполняющемуся процессу завершиться, фиксируем точные states, затем ставим `ACT-2B6CC977` на паузу. Renewal не должен создать следующую legacy activation незаметно. Backup/архивацию/health не выключаем оптом.

**Осознанная цена:** будущие 97 obligations из прежнего readback, а также появившиеся до cutoff, могут остаться непроснятыми. Их не удаляем, не заполняем задним числом и не выдаём за COMPLETE. Точный объём фиксирует свежий readback. Пауза обратима как control, но утрата исторических observations необратима.

Состояние других PAUSED/ABORTED activations само по себе не требует ремонта. Не называем их здоровыми; просто не используем в новой scientific population.

В одном небольшом Git change закрепляем реальные route evidence, correction к runbook «нужна эксклюзивная рабочая lane, а не COMPLETE всей истории», bootstrap protection rule и ссылку на эту программу. Это не разрешает deploy. Исходные raw/host receipts остаются operational; Git хранит минимальные sanitized evidence refs и смысл.

**Не блокировать весь пакет на одной неизвестности:** cessation, сохранение receipts и registry-подготовка полезны даже при unresolved protection. Не создавать ещё один общий preflight-проект.

### B. Canary: проверить весь рабочий путь, не только HTTP

Один профиль: ceiling 24/day, ровно два полных UTC-дня intake, cap 48, затем закрытие intake. Последняя trajectory требует 72h плюс grid/grace. Полный итог примерно через пять суток от старта. Полномочия и ресурсный резерв должны покрывать этот хвост.

До включения — exact accepted SHA, producer-local storage envelope, policy/assignment pins, account allocation; подготовка lookup прямо на canonical root под writer fences. Новая lane сначала disabled. Обычный запуск/деплой не выполняют preparation автоматически. После запуска — проверка первых настоящих nomination и SEARCH batches; USDC probe не доказывает полный bulk/absent/missing путь.

**DoD реальной эксплуатации:**

- Ни одна committed admission не потеряна/переписана. Все штатно завершённые, исчезнувшие и field-missing episodes посчитаны.
- Нет неразрешённого integrity/protection conflict, quota breach, OOM. Process alive не заменяет progress.
- Предлагаемый operating threshold: не менее 95% due dispatch opportunities имеют реальную своевременную попытку; scheduler no-request отдельно. Это инженерный порог, не significance test. Каждому пропуску есть состояние; наличие reason не превращает 100% ошибок в PASS.
- Provider success, numeric missingness и collector lateness показаны отдельно, по полям и source. Повторяющиеся значения holders не считаются автоматически доказательством свежего измерения.
- Две зрелые UTC-когорты импортируются обычным путём; повтор exact, без ручных JSON/flags.
- Непустой набор новой lane восстанавливается off-host вместе с обязательными immutable dependencies, затем читается без исходного VPS/сети. Восстановление только SQLite недостаточно.
- Замерены nominated/eligible/admitted/distinct/mature/query-support, bytes/day, wall/RSS и вмешательства оператора.

Если source supply не дал двух непустых когорт, это не повод искусственно добивать admissions. Технические пройденные части сохраняются, общий data-fit остаётся ограниченным. Не продлевать пустой canary больше одного дополнительного диагностического окна без решения о причине.

**Ранняя проверка полезности:** уже через первые два полных дня intake оценить candidate funnel. Если slots доступны, но реальных пригодных mint почти нет, искать причину в source/protection/asset/core/ticket saturation; не ждать окончания месяца. При существенном denominator нарушение — stop new intake, сохранить доступный tail.

### C. Семь суток на 100/day: использовать до нового строительства

После B — один неизменный профиль на семь суток, cap ≤100/day. Цель режима — наблюдать реальный usable supply и провести первый ordinary Forge cycle, а не накопить максимально возможный N.

Первые суточные cohorts будут полностью зрелыми примерно на четвёртые сутки от их начала; между тем можно заранее зарегистрировать вопрос, не смотреть будущие outcomes. Не ждать 72h, если конкретный иной уже поддержанный diagnostic имеет достаточные данные; не обходить штатный public release ради ускорения.

Предлагаемый ориентир data-fit: 300–700 admissions/week и несколько сотен decision-usable episodes. Это ориентир throughput, не правило научной значимости и не оправдание исключения оставшихся. Показывать отдельно количество допусков и joint support конкретного вопроса.

**Полезный результат недели:** минимум один поддержанный вопрос завершён ordinary lifecycle либо до просмотра outcomes предъявлено точное недостаточное поле/окно/support. Во втором случае должно быть понятно, что изменит решение; простого «копим дальше» нет.

Routine maintenance после наладки: целиться в ≤30 минут owner-вмешательств в неделю, не считая собственно исследования. Это proposed service target. Два ручных recovery ремонта одного шва за семь дней — повод пересмотреть owner boundary, не выпускать бесконечную цепочку suffix patches.

### D. Тысяча в неделю: расширение из-за demand, не vanity target

Текущий код не может принять 1000/week с ceiling 100/day. Для расширения нужен один bounded capacity change в существующем contract/schema/compiler/tests, с сохранением старых валидных schedules и trial history. Не снимать ограничения глобально и не менять historical pins.

**Рекомендуемый следующий профиль: 200/day**, но только если 100/day реально ограничивает пригодный поток. При заполнении это до 1400 admissions/week; nominal одновременная нагрузка около 600 active episodes. Active cap, burst, cutoff/tail overlap, WAL, files/inodes и ресурсный резерв пересчитываются вместе, не правится одно число.

Условие для повышения: несколько полных дней показывают устойчивую очередь невыбранных, сейчас пригодных tickets; оценка distinct eligible supply позволяет заполнить новый режим; именно N/support, а не неисправный parser/импорт/отсутствие вопроса, ограничивает следующий consumer. Диагностика должна учитывать, что pending mint может повторяться сотни раз — сумма появления в списках не равна количеству новых рынков.

Если pending supply нет — ceiling не поможет. Сначала понять узкое место. Другой interval/source, критерий population или representation рассматриваются только по измеренному провалу; не устраивать бесконечный provider comparison.

**1000 admissions ≠1000 usable episodes.** При доле joint support u необходимый intake для 1000 usable/week равен `1000 / (7u)` в сутки. При u=0.8 — около 179/day. Это объясняет профиль 200/day, но u ещё надо измерить.

2000+/week — только после успешного использования 200/day и нового named demand. 300/day даёт nominal 2100/week, около 900 active episodes; сейчас не build target.

Смена профильных границ prospective, без intraday cohort fragments. First canary tail закончить до следующей activation. Для дальнейшего episode→episode handover пользоваться уже поддержанной границей; если её proof не готов, предпочесть небольшой запланированный intake gap, а не новый параллельный collector.

### E. Решение по данным, а не по красоте графиков

Первый bounded discovery batch: предложить максимум три механизма, по максимум двум заранее указанным representations/вариантам каждого — до шести exploratory числовых попыток, либо более строгий текущий Git budget. Это recommendation для нового research grant, не запуск сейчас. Не тратить шесть попыток обязательно; cheapest falsifier может остановить после первой.

Примеры механизмов, НЕ готовые стратегии:

- Продолжение движения: цена растёт, holders поддерживают движение, liquidity не исчезает; сравнить с одним price-only правилом.
- Расхождение: price растёт без поддержки holders/liquidity; проверить, связан ли такой prefix с худшим последующим path.
- Восстановление после отката: price откатился, а liquidity/holders удержались; проверить последующее поведение при одинаковом decision-time периметре.

В V1 использовать только уже поддержанные point/delta/return/time operators и максимум восемь selected points. EMA, normalized shape или новое поле добавляется только при конкретном surviving question. Не выдавать захваченный rich JSON за уже разрешённый feature vocabulary.

Научная дисциплина остаётся короткой, но реальной:

- Точное decision time; все inputs доступны к нему. E0 — admission witness, не гарантированный fill.
- Исходная база — все admissions; eligibility только по decision-prefix. Исчезнувший target не выкидывается ради прибыли. Нулевая цена и rug не дорисовываются.
- В результате отдельно наблюдаемый mark return и target attrition. Чувствительность к плохим исходам/задержкам/затратам фиксируется до продвижения; универсальной «-100% всем missing» нет.
- Один простой competing baseline и дешёвый null/negative control до сложной модели.
- Хронологический следующий блок для OOS, без повторного выбора по результатам. Перекрывающиеся target windows очищаются по реальному horizon вопроса, не автоматически по всем 72h хранения.
- Повторные mint и общий рыночный день не выдаются за независимые trials. Кластерная чувствительность/исключение крупнейшего winner/дня — дешёвые проверки концентрации; это диагностика, не повод заново подгонять рецепт.
- Старые exposures/negatives не исчезают после нового main, импорта или нового LLM. Canary data с exploratory exposure не становятся untouched holdout.

Surviving candidate → отдельный frozen experiment → chronological OOS → только затем paper/shadow/quote-aware feasibility. При маленькой позиции допустима conservative impact/cost model для раннего отсева, но не заявление «исполняется без проскальзывания».

---

## 5. Код + LLM + данные: где может быть реальное преимущество

Qlib — не примитивный backtester, а полноценная модульная quant-платформа; RD-Agent уже сочетает гипотезы, реализацию, backtest и feedback [W1, W2]. Поэтому число агентов, текстов и PR не доказывает преимущество SMIAL.

**Наш путь к преимуществу — специализация данных и проверяемых вопросов:**

| Роль | За что отвечает | Чего не делает |
|---|---|---|
| Детерминированный код | membership, clocks, projection, budgets, численные результаты, replay | Не объясняет сигнал красивой историей вместо evidence |
| LLM / Forge | механизм, конкурирующее объяснение, хороший falsifier, следующий наиболее информативный вопрос | Не читает весь raw dump, не меняет frozen outcome/holdout, не изобретает значение missing |
| Данные | активный рынок, post-admission trajectory, holders/liquidity/price, provenance и негативные исходы | Не обещают random sample всей Solana, исполнение или независимость |
| Владелец | продуктовый приоритет, риск, стоимость, реальные внешние действия | Не выбирает SQL индексы и не подтверждает каждый passing test |

Богатый context ценен, если можно адресно вернуться к нужному snapshot и типизировать новое поле с честной исторической availability. Он не должен постоянно раздувать LLM context и hot SQLite.

**Как проверить superiority без большого сравнительного проекта:** сначала сравнить цену решения/качество на одних frozen episodes между простым price-only baseline и специализированным price+liquidity+holders+time вопросом при одинаковых budget, costs и temporal split. Если специализация не даёт полезного различения или уменьшения неопределённости — усложнять агента рано. Позже можно один раз дать тот же разрешённый dataset готовому Qlib/RD-Agent baseline, но только когда такой benchmark реально изменит решение BUILD/ADOPT; миграция сейчас не нужна.

Итоговая формула преимущества: `лучше выбранный рынок × полезные PIT-поля × качественный falsifier × дешёвый воспроизводимый цикл`, а не «наша платформа сложнее».

---

## 6. Хранение: богатые данные без вечного операционного журнала

### Где что живёт

**VPS — рабочая зона:** активные trajectories, ещё не опубликованные/доставленные данные, recovery state, ограниченное окно подробного raw. Первоначально не ниже текущего 11-day контракта; целиться в 11–14 дней для eligible raw, а не обещать автоматическое удаление всего после календарного срока.

**ПК — исследовательский архив:** компактные core и rich snapshot representations, membership/selection/protection, recipes/results/negative history, локальный mirror по реальной необходимости. Workstation может быть OFF 72h: догоняется доставка, не задним числом рынок.

**Внешнее хранилище — резерв:** необходимый immutable research evidence плюс соответствующий mutable checkpoint/ссылки. Одного off-host SQLite без RDP недостаточно. Пользоваться уже имеющимися backup/archive owners, не строить новый cloud service.

### Что сохранять, что сокращать

| Слой | Долговременная судьба | Проверка перед сокращением |
|---|---|---|
| 139-point core, clocks, field states | KEEP; сжато, неизменно по смыслу | Public consumer/cold numerical replay |
| Богатый snapshot выбранного mint | KEEP в одной компактной representation; exact raw — там, где ещё нужен по контракту | Reprojection нужного поля; зависимые hashes и byte semantics |
| Selection/membership/protection | KEEP компактно: почему взяли и какие границы были | Исходная база и причины exclusions восстановимы, protected values не раскрыты |
| Due ledger, completed call payloads, подробный bookkeeping | COMPACT после terminal + seal + checked delivery/restore | Нет active/retry/replay consumer; сохранён минимальный итог и identity/conflict proof |
| Broad nomination raw, не являющийся обязательным pin | SHORT RETENTION либо compressed COLD, по доказанной необходимости | Не удалена единственная copy доказательства отбора/доступности |
| Staging/export/redundant mirror | DELETEABLE после проверенной доставки и отсутствия pins | Source of truth и backup не зависят от него |
| Derived lookup/index/obsolete nodes | Rebuildable; ограниченное обслуживание только по measured bottleneck | Fresh-process preparation/rollback работоспособны |

**Hash без доступных bytes не заменяет backup.** Если existing release требует original raw, этот raw либо остаётся доступным COLD, либо надо явно изменить representation contract и доказать preserved replay. Нельзя тихо удалить «ненужное» и оставить broken references.

Компактное evidence rejected/not-selected frame тоже может расти со временем опроса. Поэтому не обещаем строго `O(admissions)` для всего вечного архива. Честная модель:

`durable = episodes × compressed episode bytes + frames × compact selection bytes + experiments/results`.

`hot = active work + recent eligible raw/ops + unpublished/undelivered backlog + bounded staging`.

### Порядок объёма при 1000 admissions/week

MODEL: 52 недели, 52 000 episodes, 7 228 000 nominal points/year.

При 0.5–2.0 KB на сжатый snapshot — **3.6–14.5 GB/year только snapshot-часть**. Это sensitivity из исходного blueprint, не production measurement. Добавляются membership/frame/protection metadata и сохранённые raw dependencies. Полезная цель для одной compact durable copy — порядка 5–25 GB/year, но допускается больше, если доказан useful richness/recovery value. Вторая независимая полная копия примерно удваивает durable часть; версии/дельты считаются отдельно.

**Не связывать успех запуска с попаданием в 5 GB.** Даже 50 GB/year может быть разумной ценой ценных данных. Неприемлемы не сами гигабайты, а неизвестный рост, повторные исторические scans и много постоянно дублируемых бесполезных representations.

Текущую оценку «~1.9 MB/token со всеми тестовыми копиями →100 GB/year» нельзя использовать как линейный production forecast: в tiny fixture смешаны fixed overhead, sparse/gap trajectories, copy topology и полезные данные.

### Недельный retention review: точный результат

Уже назначенный review не отменяется. Его момент — проверка полученных фактов, не автоматическое право удалять.

Он обязан показать:

1. Fixed bytes/day от scanner и служб отдельно от marginal bytes/episode. Реальные разнообразные objects, не миллионы дублей одного synthetic payload.
2. Logical file bytes и физически занятые blocks/inodes, WAL, backup/staging peak, shared chunks без двойного счёта.
3. Hot footprint на выбранном окне, durable/year для 100/500/1000 admissions/week; repeated mint отдельно.
4. Какие exact files/rows имеют живой consumer, какие pins запрещают cleanup.
5. Replay/restore на отдельной копии после предлагаемого сокращения.
6. `KEEP_CURRENT / LIGHTEN_NOW / NEED_MORE_EVIDENCE` и один минимальный механизм. Новая storage-платформа не default.

До разрешённого реального удаления действует прежний retention contract. TTL в YAML не является evidence освобождённых bytes. SQLite DELETE не обязательно уменьшает физический файл; measured reclaim и bounded maintenance window проверяются отдельно, без routine VACUUM live-БД под capture.

---

## 7. Ресурсная математика: что проверять при каждом повышении

Обозначения: `a` — фактические admissions/day, `u` — joint support нужного вопроса, `n_t` — реальные tokens, требующие SEARCH на назначенном grid instant.

- Nominal active episodes в устойчивом 72h-потоке: около `3a`, плюс grid/closure/handover reserve.
- Future observation slots/day: `138a`, плюс E0 из nomination witness. Slots не равны HTTP calls.
- Приём/week ≤`7 × ceiling`, только при полном supply и без interruption.
- Usable/week ≈`7au`; это measured question-specific subset, не новый denominator.
- Nomination calls/day: `3 × 96 = 288` при непрерывном 24h intake.
- Search calls считать по schedule: `Σ ceil(n_t / max_batch)` с учётом exact grouping, коротких batches и missed slots, не делить все points на 100.
- Account budget = все фактические consumers, включая ручные probes. Новый ключ не разрешает предполагать новый независимый лимит.

| a, admissions/day | Номинальный максимум/week | Active 72h, ориентир | Future point slots/day |
|---:|---:|---:|---:|
| 24 | 168 при постоянном режиме; canary cap48 | 72 при постоянном режиме | 3 312 |
| 100 | 700 | 300 | 13 800 |
| 150 | 1 050 | 450 | 20 700 |
| 200 | 1 400 | 600 | 27 600 |
| 300 | 2 100 | 900 | 41 400 |

Это MODEL, не гарантия rate limit или способности VPS. Источник может не иметь столько distinct пригодных tokens.

На 100→200/day проверять вместе: validator/schema, day/rolling/cycle caps, active cap, grant lifetime, dispatch wall, batch grouping, per-call local storage limit, bytes/day, peak tail + export + backup, next-run behavior. Измеренные worker peaks сравнивать с unit caps; p95 tick wall с heartbeat cadence сам по себе недостаточен — проверяется фактическая своевременность dispatch.

Volume bindings в отчёте: отдельной строкой `Factory scope used` и `whole filesystem used`. Порог 85% monitoring общего диска не заменяет current Factory TARGET≤40 GiB/HARD≤50 GiB. Нельзя сложить capacity reserves и реальные resident bytes как будто это уже записанные данные.

---

## 8. Развилки: что менять, а что не трогать

| Наблюдение | Действие | Запрещённый «ремонт» |
|---|---|---|
| Legacy мешает новому потоку | Pause exact legacy + renewal fence, признать gaps | Ждать календарь ради формального COMPLETE; чинить overlap без consumer |
| Все candidates `UNRESOLVED_SCOPE` | Найти owners protection и собрать metadata projection | Назначить complete по отсутствию каталога; дать владельцу вспоминать тысячи mint |
| HTTP 200, но eligible supply почти пуст | Разложить funnel и проверить одну earliest cause | Неделями масштабировать scanner, снижать floor задним числом |
| 100/day стабильно заполнены, много distinct pending | Малый capacity extension и новый envelope | Повышать cap поверх существующего validator или сбрасывать seed |
| Supply большой, usable question support маленький | Проверить missingness/decision windows/parser/clock | Считать все 139 points независимыми примерами |
| Candidate держится на исчезнувших target или одном winner | Falsifier/sensitivity; не promotion | Выкинуть missing targets или переопределить exit после просмотра |
| Writer/storage снова линейно дорожает | Измерить earliest owner boundary; компактный repair | Новый DB/service «на всякий случай» |
| ПК был выключен | Bounded delivery/import catch-up | Backfill не снятых holders/liquidity |
| Публикация/selection конфликтует | Stop new intake при material risk, preserve evidence, exact repair | Удалить плохой episode/cohort ради зелёного отчёта |
| 2 повтора одного seam после ремонта | Пересмотреть boundary внутри одного coherent atom | Добавлять suffix-fix за suffix-fix |
| Две недели есть данные, нет ни одного usable вопроса | Review consumer/representation; сократить сбор до достаточного | Новые collectors/features ради ощущения прогресса |
| Все заранее выбранные механизмы отвергнуты | STOP_CURRENT_SCOPE или один обоснованный pivot | «Alpha не существует» либо бесконечный hidden search |

Не превращать таблицу в автоматический controller или новую policy engine. Это правила человеческого решения и поведение агента в текущем разрешённом scope.

---

## 9. Protection без бюрократии и ложного empty inventory

Цель защиты — не право торговать mint и не blanket ban на уже известные токены. Это не раскрыть данные, которые уже зарезервированы для чужого/последующего confirmatory исследования.

**Рекомендуемое bootstrap решение:** canary и первый обычный batch являются `EXPLORATORY_REUSE`; новый holdout для них не создаётся. Существующие активные protected assignments других экспериментов сохраняются.

Исполнитель сначала проверяет metadata canonical experiment/split/assignment owners в известных research roots: IDs, role, интервалы, refs. Не читает сами outcomes. При наличии совпадений строит один маленький frozen assignment document. При доказанном отсутствии — допустим честный пустой inventory с перечисленными проверенными источниками и ограниченным scope, не с обещанием «в мире нет protected tokens».

Если полноту проверить нельзя, возвращает одну конкретную границу: какой owner/source недоступен и какое решение требуется. Нельзя просить владельца составить список mint с памяти. До решения можно завершить pause, registry и deploy package; broad exploratory exposure/activation остаётся закрытым.

Raw response — недоверенные входные данные. Token descriptions/URLs не становятся инструкциями LLM или shell. Protected values не публикуются в Chat/Git и не идут в diagnostics examples. Возможная exposure прежних probes фиксируется, а не стирается; при её материальности соответствующий holdout уже не untouched.

---

## 10. Failure, rollback и restart

**До первого episode admission:** ошибка deploy/preparation → lane остаётся disabled, legacy автоматически не возобновляется. Можно вернуться к проверенному code SHA, но operational grant не переносится сам собой. При no-live collector timer off — ожидаемый остановленный scope, не фиктивный GREEN.

**После admissions:** предпочтительный control — episode stop-intake и сохранение доступного observation/publication tail. Если сам tail небезопасен из-за диска, credentials или corruption — pause с сохранёнными obligations и явными gaps; не удалять их. Не делать code rollback на версию, которая не понимает текущие данные, без copy compatibility proof.

**Writer lookup:** производный; после restore/moved-root/old-writer append требует explicit reprepare по текущему contract. Не копировать filesystem-bound index с другого root. Не превращать его порчу в разрешение ослабить canonical manifest checks.

**Backup:** mutable checkpoint и immutable release/chunks должны ссылаться на совместимые identities. Restore непустого representative набора проверяет content и ordinary read/replay. На маленькой canary не требуется восстановить все 5.9 GB legacy-архива, если scoped backup/rollback гарантии названы честно; единственную immutable копию новых данных не удалять.

**Частичная selection:** текущий #378 gate сохраняется. Operator не имеет «сделать scientific-ready» override. Статистическое исключение cohort не стирает его operational/selection evidence и не должно становиться скрытым survivor selection.

**Cleanup:** всегда отдельная destructive authority с точным scope, after verification, без заодно-cleanup legacy. Временный workspace удаляется только по предусмотренному scope после сохранения всех нужных receipts; `/var/tmp` не является durable owner evidence.

---

## 11. Правила завершения программы

### Data operation accepted

Actual canary и ordinary next-run прошли; main≠deployed не перепутаны; одна рабочая lane; нет resource/integrity/protection violation; публичный transfer/import и representative full evidence restore доказаны. Принимается конкретный envelope, не любой будущий throughput.

### Research operation accepted

Свежая Forge понимает population/clocks/features, выполняет поддержанный frozen question, Critic/final/replay; повторный запуск не требует исправления collector или ручного Context Packet. Учет looks сохранён. Если support недостаточен, принят только data path, не выдуманный scientific run.

### Решение по направлению

Через первые 2–4 недели РЕАЛЬНОЙ работы, а не ожидания approvals, предъявить: funnel/supply, joint support, owner burden, bytes/cost per useful decision, список зарегистрированных falsifiers, surviving candidates и отрицательные результаты. Это checkpoint, не обещание достаточной статистики за срок.

- **CONTINUE:** есть достаточный поток и полезные вопросы; следующий эксперимент имеет понятную ожидаемую ценность.
- **CHANGE_REPRESENTATION:** конкретный живой механизм упирается в отсутствующее поле/оператор/гранулярность; один smallest vertical extension.
- **REFRAME_DATA:** выбранный vendor frame/доступность не даёт нужного рынка; сначала дешевейшая альтернативная nomination/unit-of-analysis, не платная система по инерции.
- **STOP_CURRENT_SCOPE:** зафиксированный search budget исчерпан без обещающего результата либо maintenance съедает продуктовую ценность. Это не доказательство отсутствия alpha во всём рынке.

P&L claims — только после соответствующих execution/cost/failure/OOS этапов. До этого zero real money.

---

## 12. Сверка с чужим опытом: что берём, чего не тащим

[W3–W4] Практика canary/pipeline rollout: небольшой временно ограниченный настоящий поток, проверка ВСЕГО цикла и явное решение расширять/останавливать. Применение здесь — один 24/day canary до зрелого release; не fleet, не blue/green кластер.

[W1–W2] Qlib/RD-Agent: separation данных, формального вычисления, эксперимента и feedback. Применение — проверяемый numerical owner + LLM hypothesis/falsifier + сохранённая история. Не копируем factor zoo или multi-agent scheduler без bottleneck.

[W5] Hidden technical debt: границы, зависимости данных, обратные связи и неиспользуемые features могут стоить больше модельного кода. Применение — каждый дополнительный слой имеет named consumer и exit condition; регулярная проверка useful yield важнее completeness theatre.

[W6] Time-series validation не должна обучать на будущем и тестировать прошлое. В irregular episode data не копируем `TimeSeriesSplit` слепо: используем calendar/availability boundaries, реальные target overlap и mint/day dependence.

Это инженерные основания, не evidence прибыльности нашей реализации.

---

## 13. Контекст для нового треда и правила для Project Chat

Не восстанавливать всю переписку. Прочитать этот документ, exact последний operational readout, затем `AGENTS.md → semantic routes → exact owners`. Проверить актуальный main/deploy/account/state. Исторические hashes — anchors, не вечные live facts.

**NOW:** Jupiter-only commissioning и реальный useful loop.
**WATCH:** облегчение хранения по первому настоящему measured inventory, без удаления scientific evidence.

Сначала говорить владельцу, какое решение и действие нужно, потом детали. Одна команда на bounded outcome; routine failures и reviews исправляет исполнитель внутри scope. При повторном seam — проверить abstraction, а не упаковать ещё один suffix PR. Не обещать «последний ремонт», потому что это не проверяемо; обещать конечный scope и критерий остановки.

Стратегический challenge на каждом материальном checkpoint:

> Если забыть уже написанный код, это всё ещё самый дешёвый способ получить следующее полезное решение? Какие данные мы реально использовали? Что можно не делать?

Если полезность не растёт, Project Chat поднимает pivot сам, не ждёт пока Пётр через месяц заметит «кладбище». Не защищает прежнюю рекомендацию ради последовательности.

### Минимальный handback после каждого шага

`scope / exact code+runtime IDs / что реально сделано / evidence refs / UNKNOWN / resource+data effect / один следующий шаг`.

Live timestamps/receipts и state остаются вне Git. Git обновляется для changed semantics/contracts/routes/recipes, а не для каждого poll, паузы и процента диска.

### Resume point на момент создания V1

- Программа подготовлена, runtime в этой сессии НЕ менялся.
- Сообщён overlap FAIL. Предпочтение owner — не ждать legacy и при необходимости отключить.
- Credentials/provider покупки не требуются; четыре qualification receipts уже существуют.
- Copy rehearsal есть; полный immutable off-host restore ещё ограничен.
- Protection требует metadata resolution.
- Сначала передать `NEXT_EXECUTOR_PROMPT_RU.md`: reversible legacy cessation + receipt preservation + protection resolution + минимальный registry/runbook PR. Ни deploy, ни новый provider call этот первый scope не разрешает.

---

## 14. Источники и границы доказательства

**U1.** Последний owner-provided отчёт `Commissioning prep OPPORTUNITY_EPISODES: итог` (6 октября 2026) и предшествующий preflight. Исходные receipts названы `/var/tmp/smial-prep-receipts-20261006/`; не прочитаны в этой design-сессии. Данные в разделах 2 и 6, помеченные «по отчёту», не являются новым измерением автора документа.

**S1.** `SMIAL_Opportunity_Episodes_JUPITER_CORE_Blueprint_V1_2026-10-05(1).md`, предоставленный в разговоре: population/identity/schedule, rich context, split-host path, sampling, models, scientific acceptance. Старый main anchor и некоторые implementation assumptions не переносятся как current truth.

**S2.** Project file `01_PRODUCT_AND_SCIENCE_CONSTITUTION(1).md`: scientific invariants и cashflow objective. Историческое ограничение «молодые» расширено явным принятым pivot на активные спекулятивные токены; возраст токена не равен episode age.

Git прочитан на `9efc74c0d57b10addcc4fe31155e2333fbac13c3`:

- **G1:** `AGENTS.md`, `docs/FACTORY_SEMANTIC_MAP.md`; operational/development authority и маршруты.
- **G2:** `configs/opportunity_episodes_jupiter_core_v1.yaml`; sources/floors/grid/caps/budgets/retention template, не activation.
- **G3:** `src/solana_alpha_lab/factory/opportunity_episodes.py`, `validate_episode_schedule_semantics`; cap≤100 и min raw retention.
- **G4:** `src/solana_alpha_lab/factory/observation_schedule_lifecycle.py`, `pause_schedule`, `abort_schedule`; реальные control semantics.
- **G5:** `docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md`; explicit lookup preparation, protected inventory, canary/storage prerequisites. Строка blanket legacy COMPLETE требует bounded correction по новому owner решению.

Public primary sources, прочитаны 6 октября 2026:

- **W1:** Microsoft Qlib, official README: https://github.com/microsoft/qlib . Использованы scope/modularity/workflow, не перенесены benchmark returns.
- **W2:** Microsoft Research, *R&D-Agent-Quant: A Multi-Agent Framework for Data-Centric Factors and Model Joint Optimization*: https://www.microsoft.com/en-us/research/publication/rd-agent-quant-a-multi-agent-framework-for-data-centric-factors-and-model-joint-optimization/ . Использована research/development/feedback модель, не заявление о превосходстве SMIAL.
- **W3:** Google SRE Workbook, *Canarying Releases*: https://sre.google/workbook/canarying-releases/ . Ограниченный rollout и минимально достаточная оценка.
- **W4:** Google SRE Workbook, *Data Processing Pipelines*: https://sre.google/workbook/data-processing/ . Проверять сквозной pipeline, не один процесс.
- **W5:** Google Research, *Hidden Technical Debt in Machine Learning Systems*: https://research.google/pubs/hidden-technical-debt-in-machine-learning-systems/ . Контроль сложности и data dependencies.
- **W6:** scikit-learn official `TimeSeriesSplit`: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html . Хронологическая validation; не готовый splitter для irregular SMIAL episodes.

Конец V1. Версионировать при изменении стратегии/критериев, не после каждого operational readback.
