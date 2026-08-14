# TASK-30 A22 — результат Helius `getTransactionsForAddress` one-shot

## Решение

`PAGINATION_REQUIRED_STOP`

Helius технически работает и отдаёт нужный тип данных, но полная пачка за один
вызов не получена. TASK-30 остаётся `BLOCKED_DATA`; второй запрос запрещён и не
выполнялся.

## Что подтверждено

- `mainnet.helius-rpc.com` прошёл DNS, TCP 443 и hostname-verified TLS.
- `HELIUS_API_KEY` был прочитан один раз только после PASS preflight.
- Выполнен ровно один `getTransactionsForAddress` POST: HTTP 200, retry и
  fallback — 0, cash spend — 0.
- Ответ содержит 520 полных успешных транзакций, напрямую ссылающихся на pool
  `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`, внутри окна
  `[2026-08-12T00:00:00Z, 2026-08-13T00:00:00Z)` и в возрастающем порядке.
- Ответ содержит `paginationToken`: за первой страницей есть продолжение.
- Сырые 9 012 030 байт сохранены вне Git; SHA-256:
  `7244a4c049c7ebe5f77d6136513d402c9af568dd0ccabb3a842160ab61a72bcc`.

## Что это означает для build vs buy

Покупать нового поставщика сейчас рано. Уже имеющийся Helius доказал доступ к
полным историческим транзакциям по адресу; узкое место — не отсутствие данных,
а запрещённая в A22 пагинация и ещё не выполненная проверка их пригодности для
96-слотовой PIT-панели. При этом текущий тариф аккаунта и достаточность его
квоты отдельно не устанавливались: подтверждено только отсутствие cash spend
в этом атоме.

## Что это не доказывает

- 520 транзакций — неполная пачка, а не вся активность за день.
- Нет готовой OHLCV/15m-панели, PIT admissibility или H07/H01 evidence.
- Не установлены fillability, route feasibility, execution, settlement, PnL,
  NetReturn, alpha, strategy или TASK-30 acceptance.
- Наличие пагинации не является provider failure или provider unavailability.

## Следующий продуктовый ход

После доставки A22 владелец решает, остаётся ли
`RC001-H07-H01-LIQUIDITY-RETENTION` приоритетным. Если да, нужен новый exact
owner gate на ограниченную Helius-пагинацию и последующую data-admissibility
проверку. Это не retry A22 и не запускается автоматически.
