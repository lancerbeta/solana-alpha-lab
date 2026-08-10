# TASK-30 Route Availability Probe Contract v1

## Purpose and frozen binding

Контракт задаёт только будущую техническую проверку публикации закрытой свечи
для `RC001-H07-H01-LIQUIDITY-RETENTION`. Он фиксирует `OBSERVATION_WINDOW_15M`,
`interval_seconds=900` и результат A10 `START_LABELED`; это не изменение
hypothesis и не выбор provider.

## Future probe shape

Будущий owner-approved probe наблюдает три закрытые границы; для каждой
запрашивает один и тот же OHLCV route на offsets `0, 15, 30, 60` seconds.
Верхняя граница — 12 reads. Повтор, fallback и скрытая подмена поставщика
запрещены.

## Record states

`VALID_OBSERVATION` содержит ожидаемую и наблюдённую метку интервала и
fingerprint свечи.

`TYPED_GAP` — наблюдаемый market/provider gap. Он остаётся неизвестностью и
может дать лишь `INCONCLUSIVE`.

`PROCESS_NOT_STARTED`, `RECEIPT_WRITE_FAILED`, `PRIOR_MANIFEST_UNREADABLE` и
`MONITORING_LOST` — capture-health failures. Ни один из них не является
market/provider gap: любой из них немедленно возвращает `INCONCLUSIVE` и
`execution_disposition=STOP_RUN`.

## Publication rule

Если во всех трёх слотах допустимая свеча впервые появилась на разрешённом
offset и её fingerprint не менялся в последующих допустимых наблюдениях,
fixed delay равен максимуму трёх first-visible offsets. Неверная метка
интервала или revision после публикации даёт
`ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE`.

## Anti-one-shot activation ladder

1. Этот offline атом и synthetic acceptance.
2. Отдельный owner packet для двухслотового live shakedown с exact provider,
   endpoint, pool identity, quota, raw retention, monitoring и recovery.
3. Только после успешной live shakedown — отдельный owner decision о 24-hour
   technical capture.

Потеря monitoring или незакрытая авария на ступени 2 останавливает run сразу;
она не допускает тихий restart и не переносится в следующий шаг как «пробел
данных».

## Non-claims

Contract не создаёт provider route, scheduler, dataset, panel, alpha evidence,
research trial, trade, execution truth, settlement или numeric NetReturn.
