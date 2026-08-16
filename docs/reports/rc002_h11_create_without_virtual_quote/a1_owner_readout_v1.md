# RC002 — Create без virtual_quote_reserves, офлайн

**Терминальное решение:** `CREATE_STILL_TRUNCATED_NEED_GETTRANSACTION`

Кандидат `DROP_QUOTE_MINT_AND_VIRTUAL_QUOTE_RESERVES`: pinned TASK-08 CreateEvent без хвостовых `quote_mint` и `virtual_quote_reserves`. Complete/Migration на этом кандидате не режутся. Новых provider-вызовов нет. Pinned decoder не менялся.

## Что проверено

- синтетика Create без двух quote-полей полностью consume-ится кандидатом
- синтетика Create с текущим pinned layout на кандидате падает
- retained A4, те же 3 страницы TASK-40:
  - Create `195` → всё ещё `borsh_payload_truncated`
  - Complete `112` и Migration `168` по-прежнему consume под предыдущим кандидатом `DROP_TRAILING_QUOTE_MINT` (регрессия)

Вывод: Create 195 короче даже этого Create-only layout. Offline field-mask по двум trailing quote-полям Create не объясняет тело. Exclusive XB/RPC-cut по Create — нет: truncation совместим и с более длинным layout, и с другим кодированием.

## Что дальше не делается этим атомом

- `getTransaction` (нужен отдельный owner OK)
- перепись receipts TASK-40/39 и previous older-IDL
- mutation pinned decoder
- live PIT / alpha / cashflow

Это не product DONE и не закрытие TASK-40.
