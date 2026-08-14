# TASK-30 A21 — результат patched Bitquery one-shot

## Решение

`ROUTE_UNKNOWN_STOP`

На Bitquery archive сейчас не переключаемся. TASK-30 остаётся `BLOCKED_DATA`:
один разрешённый patched POST израсходован, пригодная 96-слотовая панель не
получена.

## Что подтверждено

- `streaming.bitquery.io` снова прошёл DNS, TCP 443 и hostname-verified TLS.
- Локальный `BITQUERY_ACCESS_TOKEN` был прочитан один раз только после PASS
  preflight.
- Выполнен ровно один GraphQL POST на A21-путях; retry и fallback не
  выполнялись.
- HTTP-статус сохранён: `403`.
- Класс причины: текущий план Bitquery разрешает только `realtime`, а запрос
  требовал `archive:solana:DEXTradeByTokens`.
- Байты A20 не изменялись; `http_status` в A20 по-прежнему `null`.

## Что это не доказывает

- Нет PIT-admissible panel и H07/H01 evidence.
- Не установлены route feasibility или fillability.
- Нет execution, settlement, PnL, NetReturn, alpha, strategy или TASK-30
  acceptance.
- `403` не означает, что исторических сделок не было. Missing ≠ zero / flat /
  no-trade.
- Переключение на `realtime` не является PIT-историей для окна
  `[2026-08-12T00:00:00Z, 2026-08-13T00:00:00Z)`.

## Следующий ход

Не повторять archive POST. Любой Bitquery plan-upgrade, другой dataset или
другой провайдер — отдельный owner gate, не retry A21.
