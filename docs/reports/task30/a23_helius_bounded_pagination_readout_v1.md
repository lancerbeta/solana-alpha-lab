# TASK-30 A23 — результат ограниченной Helius-пагинации

## Решение

`COMPLETE_RAW_BATCH_CANDIDATE`

Для точного A22 pool/day batch новый поставщик или покупка сейчас не нужны.
Retained A22 page содержит все 520 транзакций: единственный continuation вернул
HTTP 200, пустую `data` и `paginationToken=null`.

## Что подтверждено

- A22 page 0 переиспользована без refetch и совпала по SHA-256, 520 строкам и
  cursor SHA-256.
- DNS, TCP 443 и hostname-verified TLS прошли до единственного чтения локального
  `HELIUS_API_KEY`.
- Выполнен ровно 1 continuation POST из разрешённых 2; retry, redirect,
  fallback, second provider и purchase/plan changes — 0.
- Continuation занял 93 байта, вернул 0 транзакций и null cursor. Его SHA-256:
  `6770f134e61d334451780ded411fe5dd79e0577f2c532a5d3a8a694b8c58ae81`.
- Полный raw-batch candidate содержит 520 уникальных успешных транзакций в
  строгом `(slot, transactionIndex)` порядке внутри закрытого UTC-окна.
- Upper bound текущего atom: 10 Helius credits и 93 новых байта. Второй вызов
  не выполнялся.

## Продуктовый вывод

Для точного `RC001-H07-H01-LIQUIDITY-RETENTION` bottleneck сдвинулся. Вопрос
«есть ли вообще полный исторический raw batch» закрыт положительно. Следующий
decision gap — пригодны ли эти транзакции для воспроизводимой PIT-safe
15-минутной market panel и достаточно ли их полей для H07/H01 estimand.

Покупка альтернативного data provider сейчас преждевременна: она не устраняет
этот transformation/admissibility gap. Возвращаться к рынку поставщиков стоит
только если текущие raw bytes не позволяют построить требуемые наблюдения либо
если позднее появится доказанный throughput/coverage gap на большем universe.

## Что это не доказывает

- Complete raw batch — не готовая 96-slot panel и не PIT admissibility.
- Не установлены price/volume construction, missing-slot semantics,
  fillability, route feasibility, execution, settlement, PnL или NetReturn.
- Нет результата H07/H01, alpha, strategy promotion или TASK-30 acceptance.
- Один pool/day не доказывает provider reliability, масштабируемость тарифа или
  достаточность квоты для широкого universe.

## Stop и следующий gate

Внешняя authority A23 исчерпана: новых provider calls, retry, fallback или
покупки нет. После delivery владелец решает, остаётся ли RC001 приоритетным; если
да, нужен отдельный exact atom на raw-to-PIT data admissibility, не A24 provider
pivot.
