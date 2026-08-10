# TASK-30 A11A — Offline route availability probe

## Назначение

Задать и проверить безопасную форму будущей технической проверки доступности
закрытой 15-минутной свечи для frozen-группы
`RC001-H07-H01-LIQUIDITY-RETENTION`. Consumer — owner, принимающий отдельное
решение о допустимости двухслотовой live-проверки.

## Решаемый вопрос

После A10 известно только, что метка 15m-интервала у выбранного публичного
маршрута соответствует началу интервала (`START_LABELED`). Этот атом не
собирает данные: он определяет, как будущая короткая проверка отличит
стабильную публикацию свечи от пробела поставщика и от собственной аварии
процесса.

## Scope

- Ровно три будущие закрытые 900-секундные границы и offsets `0, 15, 30, 60`.
- Не более 12 будущих OHLCV reads; no retry и no fallback.
- Детерминированная offline-оценка synthetic records и owner readout.

## Authority

В этом атоме: provider/API/RPC/WSS calls = 0; credentials = 0; raw writes = 0;
scheduler/background process = 0; R2/R3 = 0; wallet/signer/transaction = 0;
cash spend = 0. Ни двухслотовая проверка, ни 24-hour capture этим файлом не
разрешаются.

## Терминальные решения

- `READY_FOR_FIXED_DELAY_24H_TECHNICAL_CAPTURE` — только техническая
  готовность маршрута к следующему owner gate.
- `ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE` — маршрут показал revision или
  неверный интервал.
- `INCONCLUSIVE` — недостаточно данных либо зафиксирована проблема процесса.

`READY` не означает PIT-admissibility, evidence H07/H01, trial, execution,
settlement, PnL, NetReturn или authority.
