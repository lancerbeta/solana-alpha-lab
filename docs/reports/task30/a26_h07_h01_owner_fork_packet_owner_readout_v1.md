# TASK-30 A26 — $5 Helius не фальсифицирует H07/H01

**Терминальное решение:** `FIVE_DOLLAR_HELIUS_CANNOT_FALSIFY_OWNER_FORK_READY`

Это **доказательство, что дешёвая покупка не закрывает estimand**,
а не испытание гипотезы и не разрешение тратить.

## Почему не $5 Helius

- замороженный терминал A25: `ESTIMAND_NOT_COMPUTABLE_TARGETED_CAPABILITY_GAP_PROVEN`
- независимых кластеров `POOL_DAY`: `1`
- минимум кластеров для калибровки дисперсии: `4`
- статус `ROUTE_FEASIBILITY` в реестре: `REGISTRY_GAP`
- операции Helius: `GET_SIGNATURES_FOR_ADDRESS, GET_TRANSACTIONS_FOR_ADDRESS_FULL, LOGS_SUBSCRIBE_MENTIONS`
- они дают историю сделок/логов, а не 13 полей полосы котировок
- `|NOTIONAL_BUCKET_SET_V1|`: отсутствует — `UNDEFINED_NOTIONAL_BUCKET_SET_ABSENT`
- иллюстрация `4×96×1=384` — `ILLUSTRATIVE_N1_NOT_A_FROZEN_PARAMETER`
- подписка преждевременна; агент не трогает кошелёк, seed, signer, карту

## Причины

- `WRONG_LANE_HELIUS_IS_TRADE_HISTORY_NOT_ROUTE_FEASIBILITY`
- `FOUR_POOL_DAY_CLUSTERS_NOT_PURCHASABLE_WITH_FIVE_DOLLARS_ON_THIS_ROUTE`
- `NOTIONAL_BUCKET_SET_V1_ABSENT_SO_QUOTE_CALL_BUDGET_UNDEFINED`
- `REGISTRY_GAP_FOR_ROUTE_FEASIBILITY_PROVIDER`

## Что выбрать после merge этого пакета

Ни один форк этим атомом не выбран.

- `RETIRE_RC001_H07_H01_LIQUIDITY_RETENTION` — `OK T30-A26 RETIRE_RC001_H07_H01_LIQUIDITY_RETENTION` — `ELIGIBLE_AFTER_MERGE`
- `FREEZE_NOTIONAL_BUCKET_SET_V1` — `OK T30-A26 FREEZE_NOTIONAL_BUCKET_SET_V1` — `ELIGIBLE_AFTER_MERGE`
- `AUTHORIZE_VARIANCE_CALIBRATION_CAPTURE` — `OK T30-A26 AUTHORIZE_VARIANCE_CALIBRATION_CAPTURE` — `INELIGIBLE_UNTIL_PRECONDITIONS`

`AUTHORIZE_VARIANCE_CALIBRATION_CAPTURE` остаётся `INELIGIBLE_UNTIL_PRECONDITIONS`:
нужны замороженные нотионалы, строка `ROUTE_FEASIBILITY` в реестре с observed receipt
и отдельный атом на ≥4 кластера `POOL_DAY`.

`TASK-30` остаётся `BLOCKED_DATA`. Это не DONE, не альфа и не cashflow.
