# RC002 — older IDL clock body, офлайн

**Терминальное решение:** `MIXED_CLOCK_BODIES_NOT_UNIFORM`

Кандидат `DROP_TRAILING_QUOTE_MINT`: pinned TASK-08 layout часов без хвостового `quote_mint`. Новых provider-вызовов нет. Pinned decoder не менялся.

## Что проверено

- длины Program data **включая** 8-байтовый дискриминатор: Complete `112` (= 8+104), Migration `168` (= 8+160)
- 104 и 160 совпадают с pinned Complete/Migration **минус** pubkey `quote_mint` (32)
- синтетика без `quote_mint` полностью consume-ится кандидатом
- синтетика с текущим pinned layout на кандидате падает
- retained A4, те же 3 страницы TASK-40:
  - Complete `112` → consume
  - Migration `168` → consume
  - Create `195` → `borsh_payload_truncated` (тело всё ещё короче кандидата, у которого остаётся `virtual_quote_reserves`)
- Complete пришёл через CPI: Pump **нет** в top-level `accountKeys`

Вывод: для Complete и Migration schema-skew (нет trailing `quote_mint`) **достаточен**. Create этим кандидатом не объясняется. Exclusive XB/RPC-cut по всем трём часам — нет.

## Что дальше не делается этим атомом

- второй Create-кандидат (выбросить ещё и `virtual_quote_reserves`)
- `getTransaction`
- перепись receipts TASK-40/39
- mutation pinned decoder
- live PIT / alpha / cashflow

Это не product DONE и не закрытие TASK-40.
