# TASK-30 — результат Bitquery PIT capture

## Решение

`ROUTE_UNKNOWN_STOP`

На Bitquery сейчас не переключаемся. TASK-30 остаётся `BLOCKED_DATA`: один
разрешённый запрос израсходован, а пригодная 96-слотовая панель не получена.

## Что подтверждено

- `streaming.bitquery.io` успешно прошёл DNS, TCP 443 и hostname-verified TLS
  preflight.
- Локальный `BITQUERY_ACCESS_TOKEN` был прочитан один раз только после PASS
  preflight.
- Выполнен ровно один GraphQL POST; retry и fallback не выполнялись.
- Транспорт завершился классом `TRANSPORT_ERROR`.
- После обнаружения дефекта evidence capture офлайн-регрессия исправлена и
  покрыта 16 тестами; второй запрос для восстановления потерянной причины не
  выполнялся.

## Что осталось неизвестным

Pre-patch обработчик ошибочно объединял реальный сетевой отказ и HTTP error в
один класс и не сохранял тело/статус при stop. Поэтому нельзя честно установить,
был ли это HTTP auth/schema ответ Bitquery или разрыв транспорта. Ответные байты
не доступны, а значит нельзя посчитать ни observations, ни typed gaps.

`UNKNOWN` здесь не означает zero, flat, no-trade, inactive или отсутствие
исторических данных.

## Что это не доказывает

- Нет PIT-admissible panel и H07/H01 evidence.
- Не установлены route feasibility или fillability для `10, 25, 50, 100 USD`.
- Нет execution, settlement, PnL, NetReturn, alpha, strategy или TASK-30
  acceptance.

## Следующий ход

Зафиксировать `BITQUERY-SOLANA-PUMPSWAP-OHLCV-001` в provider registry как
наблюдённый `ROUTE_UNKNOWN_STOP`, сохранить TASK-30 в `BLOCKED_DATA` и не
повторять этот запрос без нового явного owner gate.
