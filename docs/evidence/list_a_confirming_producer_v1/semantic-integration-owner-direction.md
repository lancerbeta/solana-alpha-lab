## PR #406 — targeted semantic/integration review → bounded repair → Git delivery

**Owner direction:** продолжить текущий `LIST_A_CHRONOLOGICAL_CONFIRMING_PRODUCER_V1` до качественного завершения. Это не новая задача и не разрешение перепроектировать научный протокол.

**Review anchor:** PR #406, head `72151e2a011ce8a5899bebfdaa18cf23a4801039`. Перед работой перепроверь фактический HEAD — не повторяй то, что уже исправлено.

Я отдельно посмотрел продуктовые стыки и семантику, не CI. Общий confirming path выглядит состоятельно, но выявлены **два material gap**, которые стоит закрыть до merge или доказательно определить как границу следующего атома.

### F01 — P1: несовместимость single-schedule sample с I3 daily collection

**В чём проблема**

После #405 штатный managed collector создаёт отдельный frozen child schedule на каждые UTC-сутки. У каждого child собственные `schedule_sha256`, `activation_id`, activation window, при сохранении общей collection lineage и совместимой научной семантики.

Но новый confirmer использует один `Sample.schedule_rel` и в `source_metadata()` проверяет все admissions против одного schedule:

- `admission.schedule_sha256 == schedule.schedule_sha256`;
- каждый `T0` должен попадать в его activation window;
- schedule binding и clock resolver общие для всех строк.

Существующая synthetic fixture обходит этот стык: она создаёт единый schedule на весь интервал ноябрь–январь.

Для принятого List A метода нужны ≥30 contributing time blocks **в каждой группе и каждом partition**, включая 48-часовой. Одних суток intake недостаточно.

**Это не претензия к bootstrap. Это несовместимость production input contract с естественным выходом managed collector.**

**Что сделать**

1. Сначала дешёвый falsifier на реальных production validators, но полностью синтетических данных: два или более разных daily child schedules с исходными SHA/activation IDs. Проверь, можно ли законно собрать их в один confirmation sample. По текущему code path ожидается отказ.
2. Если отказ подтверждается, выбери минимальное исправление authoritative source binding. Предпочтительная модель — один immutable sample/source set с canonical набором frozen schedules, каждый admission привязан к своему исходному schedule/activation. Не создавать виртуальный многомесячный schedule и не переписывать admission identities.
3. Каждую строку валидировать по **её** schedule, activation window, native clocks и исходному frame/admission witness. Между schedules проверять совместимость cohort family, membership/list definition, population, nomination, observation grid и исходных scientific semantics. Несовместимые семьи не объединять ради sample size.
4. Сохранять полный population denominator, исходные source hashes, protection/exposure provenance, overlap/acquisition identities и scientific budget. Не разрешать fragmented same-day cohort или дублирующие admissions.
5. Если несколько schedule документов требуют versioned input contract — используй минимальное совместимое versioning. Существующие single-schedule stored bindings и results не ломать.

**Acceptance:** один native vertical synthetic sample с несколькими настоящими daily schedule identities, ≥30 contributing mint и 30 time blocks в обеих группах/partition; штатные prepare → authorize → classify → submit → result → cold dossier. Независимый oracle сверяет schedule/admission ownership и population. Negative cases: чужой schedule, несовместимая family, конфликтующий duplicate, один UTC cohort с двумя владельцами.

Исходные `EXPLORATORY_REUSE` данные не переклассифицировать. Поддержка многодневного binding **не выдаёт разрешения на реальное confirming consumption**. Для REAL по-прежнему нужны собственные untouched source authority и grant.

### F02 — P1: calendar maturity определяется после reservation

**В чём проблема**

`source_metadata()` проверяет `interval_end_exclusive <= data_cutoff` и potential support. Но это не гарантирует, что все `E14400.availability_deadline <= data_cutoff`.

В `evaluate_native()` сейчас сначала вызывается `pq.read_table(...)`, затем проверяется `TARGET_NOT_MATURE_AT_CUTOFF`. Scientific charge к этому моменту уже сохранён.

Следовательно, объективно незрелая выборка способна потратить единственную scientific attempt на ошибке, обнаружимой исключительно по metadata.

**Что сделать**

1. Собрать один корректный disposable TEST sample с достаточными mint/time blocks, но последним `T0`, у которого `E14400.availability_deadline > frozen data_cutoff`.
2. Подтвердить реальный current path и receipt: что именно успевает произойти до отказа.
3. Исправить в pre-values admission: для всех заявленных admissions вычислять maturity через authoritative `opportunity_episodes.resolve_point` и их собственные schedule bindings. Учесть native rounding/grid/grace, не вычислять `T0 + 14400` вручную как подмену clock owner.
4. Нужный результат — typed `BOUND_CONTRACT_NOT_READY` / `TARGET_NOT_MATURE_AT_CUTOFF` **до reservation**, с понятным NEXT: дождаться зрелости или отдельно перепривязать exact sample по обычным правилам. Никакого автоматического изменения sample boundaries.
5. Проверять календарную зрелость, **не** фактическое наличие outcome. Не читать target values, target-missingness, Parquet statistics, preview или observed-counts ради preflight.

**Acceptance:** незрелый sample → 0 target decodes, 0 evaluator, 0 reservations, 0 scientific charges. Зрелый sample с честными `MISSING_TYPED` по-прежнему допускается к evaluator и получает штатную проверку coverage; denominator не меняется от будущих результатов.

### Приоритет и техническая свобода

Действует прежний **goal-based owner mandate**. Самостоятельно исправляй outcome-local code, schemas, fixtures, Catalog, tests, docs, task write set и direct consumers в рамках accepted semantics. Не спрашивай разрешения на безопасные обратимые микрошаги или очередной reviewer `NOT_READY`.

Порядок работы:

1. F02 — дешевле, исправить первым.
2. F01 — минимальный multi-schedule source-binding repair с настоящим vertical consumer proof.
3. При необходимости только связанные regression checks, затем fresh review, binding, preflight, push, exact-head CI.

Не превращать два finding в новый универсальный data model, framework, scheduler или исследовательскую программу.

**Если F01 требует существенно изменить frozen scientific meaning, trust model или продуктовый контракт за пределами уже согласованного outcome**, не делать это скрытно. Представить один доказательный checkpoint с минимальным вариантом продолжения. Но сам по себе дополнительный input schema, schedule mapping или новый тест не является поводом остановиться.

Если окажется, что полноценная multi-schedule интеграция действительно несоразмерна текущему атомy, допускаю явный `SPLIT`: закрыть F02, зафиксировать `REAL_SOURCE_INTEGRATION_UNVERIFIED`, оформить ровно один successor с воспроизводимым seam и точным DoD. Тогда #406 может претендовать лишь на merge как synthetic-verified capability, **не** как real-ready confirmer. Не объявляй F01 устранённым по документации.

### Неизменяемые инварианты

- Frozen List A core, estimand, A/C interpretation, E1800/E14400, bootstrap, seeds, 4096, thresholds 95%/5%, 30/30 и verdict precedence — без изменений.
- PIT и provenance, original source roles, full denominator, negative/UNKNOWN history — без ослабления.
- Reservation-before-values, scientific allowance=1, crash/replay/atomic carriers, typed cold result и обычные promotion guards — сохранить.
- Семь исторических scientific charges, saved trials, прежние failures и evidence — не переписывать и не запускать заново. Disposable TEST executions отдельно от named science.
- Никаких REAL grants/values, providers, credentials, live/deploy, денег, новых сервисов или зависимостей.
- Green CI не заменяет semantic correctness; reviewer PASS не отменяет конкретный воспроизводимый counterexample.

### Итог, который хочу увидеть

Краткий owner handback:

| Finding | До | После | Independent evidence |
|---|---|---|---|
| F01 multi-schedule | Exact refusal/compatibility boundary | Fixed / explicit SPLIT | Multi-day native sample + ownership oracle |
| F02 maturity | Exact charge/read boundary | Pre-values refusal | Zero-value/zero-charge receipt |
| Legacy/science | Existing invariants | Unchanged | Targeted regressions + cold replay |

Отдельно назови остаточные REAL/source-availability UNKNOWN и влияние на эксплуатацию.

**Цель:** закрыть два реальных стыка, а не набрать дополнительные тесты. Если bounded repair доказан — самостоятельно довести #406 до exact-head CI PASS и machine merge-readiness PASS; затем остановиться **один раз** за отдельной exact owner merge phrase. Merge сейчас не разрешён.