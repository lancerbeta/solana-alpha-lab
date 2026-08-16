# RC002 — H11 паркуем с приоритета, науку не удаляем

**Терминальное решение:** `H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED`
**Фраза владельца:** `H11 паркуем`

Это **снятие H11 с живого приоритета фабрики**, а не опровержение гипотезы, не подтверждение, не canonical DONE, не alpha и не разрешение платить за данные.

## Что именно припарковано

- гипотеза: `HYP-RC002-H11-LIFECYCLE-CLOCK-V1`
- цикл: `RESEARCH-CYCLE-RC002-001`
- consumer: `RC002-H11-LIFECYCLE-CLOCK`
- приоритет: `PARKED_FROM_PRIORITY`
- наука: `RETAINED` (удаление: `false`)
- вердикт по гипотезе: `NOT_REFUTED_NOT_SUPPORTED`
- family status: `PARKED_FROM_PRIORITY_NOT_CANONICAL_DONE`

Экран H11 **не бежал** на живой вселенной: TASK-36 остаётся `HISTORICAL_ROUTE_INADEQUATE_REPLAN`, `n=0`. Это не `H11_SCREEN_NEGATIVE` и не `H11_SCREEN_POSITIVE_EARNS_PROSPECTIVE_CONFIRMATION`.

## Почему так

Цель владельца — быстрее и качественнее product-market fit: короткое окно 15 минут–4 часа, где видно цену, можно коснуться рынка и понять деньги после издержек. H11 отвечает на другой вопрос (добавляют ли часы после миграции информацию сверх времени суток). Даже идеальный PASS экрана даёт только право *потом* проверять это вперёд — не стратегию и не выручку.

Дешёвый уже лежащий кэш (история PumpSwap pool) структурно не содержит Create/CompletePumpAmmMigration. Один mint после офлайн-разбора дал 1 pool / 0 days / 0 deployers против минимума 8 / 2 / 2. `create_at` остаётся `MISSING_UNKNOWN`. Второго признака экрана (running peak) нет. Effect screen запрещён.

Доделывать этот mint или платить за уже опровергнутые маршруты не приближает PMF.

## Что остаётся истинным (не переписывать)

- TASK-36: `HISTORICAL_ROUTE_INADEQUATE_REPLAN`, n=0, trial INCONCLUSIVE
- TASK-37 capture: `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`, trial INCONCLUSIVE; определения часов заморожены
- cohort after TASK-40 close: `H11_COHORT_NOT_READY_SCREEN_FORBIDDEN`
- mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`
- bonding_curve: `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC`
- migration_at bound: `1756321522`
- TASK-39/40 science receipts и pinned decoder не менялись
- trial ledger не менялся

## Стоит ли вернуться к H11?

Только по **новой точной фразе** и **новому exact-контракту**. Календарь сам по себе не триггер (`calendar_elapsed_is_return_trigger=false`).

### Возвращаться когда

`NEW_EXACT_CONTRACT_FOR_SAMPLE_CAMPAIGN_BRIEF_EIGHT_PLUS_POOLS_BONDING_CURVE_OR_MINT_HISTORY_OLDER_COMPLETE_MIGRATION_LAYOUT_RETROSPECTIVE_PEAK_PATH_AND_900S_OUTCOMES_WITH_COST_CAP_AND_STOP_IF_METHOD_FAILS_ON_SECOND_IDENTITY`

Иными словами: владелец отдельно авторизует бриф кампании выборки (ещё не оплату), который сразу называет ≥8 outcome-independent pools, историю bonding_curve или mint (не pool GTA), layout Complete/Migration который уже consume-ится на retained A4, ретроспективный price path для peak, исходы 900s, кап стоимости и stop «метод падает на 2-й identity».

### Не возвращаться когда

- `ONE_MINT_DECODE_RESUME`
- `MORE_CREATES_OPTION_C`
- `POOL_GTA_REPLAY`
- `PINNED_DECODER_MINT_OR_BONDING_CURVE_GTA`
- `H11_EFFECT_SCREEN_RERUN`
- `LOWER_MINIMA_8_2_2`
- `COHORT_READY_FROM_N1`
- `H13_TRIAL`
- `H02_H10_H14_TRIAL`
- `PAID_CAPTURE_ON_FALSIFIED_ROUTES`
- `CALENDAR_ELAPSED_UNPARK`

H13 и H02 сами не оживают: в TASK-28 они `BLOCKED_DATA` (нет непрерывной PIT-цены и settled execution). Этот атом их не стартует (`h13_or_h02_started=false`).

## Что этим атомом не делается

- paid capture / второй провайдер (`paid_capture_authorized=false`)
- rerun H11 effect screen (`effect_screen_eligible=false`)
- PMF-контур цены и исполнения (нужна отдельная фраза)
- canonical DONE / PIT / alpha / cashflow

Следующий ход после merge этот атом не выбирает.
