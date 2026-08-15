# TASK-30 A25 — измеримость замороженного H07/H01

**Терминальное решение:** `ESTIMAND_NOT_COMPUTABLE_TARGETED_CAPABILITY_GAP_PROVEN`

Это диагностика **измеримости**, а не утверждение об эффекте.
Вопрос был один: можно ли честно посчитать замороженный estimand
`RC001-H07-H01-LIQUIDITY-RETENTION` на панели A24.

## Метрики замороженного estimand

- `MISSINGNESS_RATE`: `COMPUTABLE_WITH_TYPED_GAPS`
- `PIT_ROUTE_SURVIVAL`: `NOT_COMPUTABLE`
  - отсутствуют поля: `ROUTE_FEASIBILITY.available_at, ROUTE_FEASIBILITY.evaluated_at, ROUTE_FEASIBILITY.ingested_at, ROUTE_FEASIBILITY.input_mint, ROUTE_FEASIBILITY.notional, ROUTE_FEASIBILITY.observed_at, ROUTE_FEASIBILITY.output_mint, ROUTE_FEASIBILITY.price_impact, ROUTE_FEASIBILITY.quoted_amounts, ROUTE_FEASIBILITY.route_identifier_or_status, ROUTE_FEASIBILITY.separate_fees, ROUTE_FEASIBILITY.source_or_raw_sha256, ROUTE_FEASIBILITY.typed_gap_or_failure`
- `QUOTE_AVAILABILITY`: `NOT_COMPUTABLE`
  - отсутствуют поля: `ROUTE_FEASIBILITY.available_at, ROUTE_FEASIBILITY.evaluated_at, ROUTE_FEASIBILITY.ingested_at, ROUTE_FEASIBILITY.input_mint, ROUTE_FEASIBILITY.notional, ROUTE_FEASIBILITY.observed_at, ROUTE_FEASIBILITY.output_mint, ROUTE_FEASIBILITY.price_impact, ROUTE_FEASIBILITY.quoted_amounts, ROUTE_FEASIBILITY.route_identifier_or_status, ROUTE_FEASIBILITY.separate_fees, ROUTE_FEASIBILITY.source_or_raw_sha256, ROUTE_FEASIBILITY.typed_gap_or_failure`

## Что посчитано и на чём

- Слотов всего: `96`
- Потреблено как наблюдения: `35`
- Потреблено как типизированные пропуски: `61`
- Неизвестное покрытие: `0`
- `MISSINGNESS_RATE` (OHLC): `0.635417`
- Свежие наблюдения ликвидности: `35`
- Перенесённые (carry-forward) слоты ликвидности: `60`

Слоты `STATE_PERSISTENCE_PROVEN` **не** считаются наблюдёнными сделками,
а carry-forward резервы **не** считаются свежим наблюдением ликвидности.

## Точность и мощность

- Единица кластера: `POOL_DAY`
- Независимых кластеров: `1`
- Степеней свободы между кластерами: `0`
- Стандартная ошибка: `UNDEFINED_SINGLE_CLUSTER_ZERO_BETWEEN_CLUSTER_DF`
- Наивная биномиальная SE `0.049124` — `INVALID_SLOTS_ARE_NOT_INDEPENDENT_REPLICATES`

Один пул за один день — это **один** кластер, а не 96 независимых
наблюдений. Между кластерами дисперсия не идентифицируется, поэтому
валидной стандартной ошибки и доверительного интервала здесь нет.

## Какие данные нужны для решающего теста

- Единица набора: `POOL_DAY`
- Минимум кластеров для определённой межкластерной дисперсии: `2`
- Минимум кластеров для определённого двухгруппового теста: `4`
- Слотов на кластер: `96` × `900` с
- Покрытие слотов: `TYPED_GAP_REQUIRED_NO_IMPUTATION`
- Оценок маршрута на кластер: `SLOTS_PER_CLUSTER_TIMES_NOTIONAL_BUCKET_COUNT`
- Размер набора нотионалов: `None` (параметр `NOTIONAL_BUCKET_SET_V1`)
- Решающий масштаб выводим из этой панели: `False` — `BETWEEN_CLUSTER_VARIANCE_UNIDENTIFIED_AT_ONE_CLUSTER`
- Цель следующего измерения: `VARIANCE_CALIBRATION_PILOT_NOT_HYPOTHESIS_TEST`

### Отсутствующие поля

- `POST_MIGRATION_CONTEXT.migration_or_program_context`
- `POST_MIGRATION_CONTEXT.pre_and_post_boundary_continuity`
- `ROUTE_FEASIBILITY.available_at`
- `ROUTE_FEASIBILITY.evaluated_at`
- `ROUTE_FEASIBILITY.ingested_at`
- `ROUTE_FEASIBILITY.input_mint`
- `ROUTE_FEASIBILITY.notional`
- `ROUTE_FEASIBILITY.observed_at`
- `ROUTE_FEASIBILITY.output_mint`
- `ROUTE_FEASIBILITY.price_impact`
- `ROUTE_FEASIBILITY.quoted_amounts`
- `ROUTE_FEASIBILITY.route_identifier_or_status`
- `ROUTE_FEASIBILITY.separate_fees`
- `ROUTE_FEASIBILITY.source_or_raw_sha256`
- `ROUTE_FEASIBILITY.typed_gap_or_failure`

### Неразрешённые замороженные параметры

- `NOTIONAL_BUCKET_SET_V1`: `FROZEN_PARAMETER_DEFINITION_ABSENT`

## Ограничения

- `SINGLE_POOL_DAY_IS_ONE_CLUSTER_NOT_NINETY_SIX_OBSERVATIONS`
- `BETWEEN_CLUSTER_VARIANCE_UNIDENTIFIED_NO_VALID_STANDARD_ERROR`
- `STATE_PERSISTENCE_SLOTS_ARE_TYPED_GAPS_NOT_OBSERVED_TRADES`
- `NO_ROUTE_FEASIBILITY_LANE_OBSERVATION_IN_A_TRADE_ONLY_PANEL`
- `NO_MIGRATION_BOUNDARY_CONTINUITY_IN_A_SINGLE_DAY_WINDOW`
- `RETROSPECTIVE_ONLY_NO_PROSPECTIVE_PIT_ROUTE`
- `REPRESENTATIVENESS_OF_THE_SUBJECT_POOL_NOT_ESTABLISHED`

## Что дальше

Decide whether to fund a variance-calibration capture that adds the named route-feasibility lane over at least the minimum cluster count, or to retire RC001-H07-H01. This is not a trial, alpha or acceptance.

`TASK-30` остаётся `BLOCKED_DATA`. RC001 не продвигается.
