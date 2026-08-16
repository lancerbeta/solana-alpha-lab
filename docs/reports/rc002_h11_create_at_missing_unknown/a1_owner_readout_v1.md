# RC002 — create_at этого mint = MISSING_UNKNOWN

**Терминальное решение:** `CREATE_AT_MISSING_UNKNOWN`

Владелец выбрал A. Create 195 этого mint identity-совпал с TASK-40, но поля `CreateEvent.timestamp` в теле нет. `create_at` остаётся `null`, статус `MISSING_UNKNOWN`. `blockTime` не используется. Pinned decoder и TASK-37 `create_at := CreateEvent.timestamp` не переписываются.

## Что проверено

- TASK-40 mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`, bonding_curve `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC`
- identity receipt: `CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE`
- layout receipt: `CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT`
- binder не читает fixture `blockTime` и не эмитит i64 `create_at`

Это не закрытие TASK-40, не cohort-rewrite часов и не product DONE.

Complete/Migration на этой истории по-прежнему читаются под прежними кандидатами. Больше Creates — WATCH, не этот атом.
