# RC002 — truncation vs absence, офлайн

**Терминальное решение:** `CLOCK_DISCRIMINATORS_PRESENT_BODY_NOT_PINNED_LAYOUT`

Это разбор уже сохранённых A4 страниц TASK-40 и синтетических логов.
Новых provider-вызовов нет. Это не live PIT, не execution, не альфа.

## Что проверено

- retained A4: `local/task40_rc002_h11_bonding_curve_pda_gta`, 3 страницы, размеры совпали с TASK-40 runtime (`6478360` / `8166555` / `3070312`)
- sha256 страниц записан в acceptance; сырые JSON в git не входят
- txs: `2393`; Pump в keys: `2061`
- pinned discriminator + тело не сошлось: Create `1` (195 байт), Complete `1` (112 байт), CompletePumpAmmMigration `1` (168 байт), Trade `1258`
- полностью декодированных clock-событий: `0`
- unknown discriminator: `1094`
- `Log truncated`: `2` txs; хвост этих txs отброшен
- Create после truncated Trade в той же tx: `0`

Вывод: addressed history **содержит** дискриминаторы H11-часов, но pinned TASK-08 layout их тело не потребил. Это снимает закрытость `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`. Это **не** exclusive-заявление, что XB/RPC обрезал часы: возможен и schema skew.

## Что этим атомом не делается

- новый GTA / getTransaction
- GTA всего Pump program
- докодирование полных Create/Migration
- перепись receipts TASK-40/39
- live PIT / alpha / cashflow

Это не product DONE.
