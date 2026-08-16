# RC002 — identity Create 195 vs TASK-40 mint/curve, офлайн

**Терминальное решение:** `CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE`

После трёх Borsh-строк в retained Create 195 остаются ровно три pubkey. Они совпадают с TASK-40 `named_mint` и `bonding_curve`. Новых provider-вызовов нет. Pinned decoder не менялся. `create_at` этим телом не заполняется.

## Что проверено

- TASK-40 identity fail-closed: mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`, bonding_curve `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC`
- локальный reader (`string,string,string,pubkey,pubkey,pubkey`, remainder 0) не вызывает `decode_pump_program_data` и не импортирует `_`-API декодера
- git fixture getTransaction Create `195` → mint и bonding_curve совпадают; observed `name=Cope`, `symbol=Cope`; `user=BFx6LQHkgcvdQ3ySxZBDBigii4fDQvn7yw5pfWRdVAgm` (публичный адрес, обязательной identity нет)
- retained A4, те же 3 страницы TASK-40: тот же match на Create `195`

Вывод: шестипольное тело Create — это Create именно этого mint и этой bonding_curve. Поля `timestamp` в нём по-прежнему нет, поэтому `create_at := CreateEvent.timestamp` для этой подписи недоступен. Exclusive XB/RPC-cut и «текущий IDL» этим атомом не утверждаются.

## Что дальше не делается этим атомом

- fork / mutation pinned decoder
- вывод `create_at` из `blockTime` или из отсутствующего event timestamp
- перепись receipts TASK-40/39 и previous H11
- live PIT / alpha / cashflow

Это не product DONE и не закрытие TASK-40.

Следующий owner-gap: `create_at=MISSING_UNKNOWN` vs другая time-метка (не `blockTime` как `create_at`).
