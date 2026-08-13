# TASK-30 — terminal route decision

## Решение

`CLOSE_CURRENT_DATA_ROUTE_LIMITED_NEGATIVE_RESULT`

Текущий именованный public/free маршрут закрыт с ограниченным отрицательным результатом; H07/H01 остаются BLOCKED_DATA.

## Что это значит

- Текущий именованный public/free data-route больше не продолжаем.
- `RC001-H07-H01-LIQUIDITY-RETENTION` остаётся `BLOCKED_DATA`.
- Новых provider/API/RPC/WSS-запросов не требуется.

## Что не утверждается

- Это не закрытие гипотезы и не доказательство непригодности всех провайдеров.
- UNKNOWN не означает inactive, zero, flat, no-trade или settled.
- Нет trial, price/volume panel, execution, settlement, PnL, NetReturn или cashflow.

## Когда можно открыть маршрут снова

Только при `NAMED_CONSUMER_PLUS_REPRODUCIBLE_PIT_ROUTE_AND_EXECUTION_TRUTH` через новый owner gate.
