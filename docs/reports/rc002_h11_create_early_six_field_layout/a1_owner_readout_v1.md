# RC002 — ранний шестипольный Create, офлайн

**Терминальное решение:** `CREATE_EARLY_LAYOUT_BORSH_CONSUMED_TIMESTAMP_INVARIANT`

Кандидат `DROP_CREATE_FIELDS_AFTER_USER`: pinned TASK-08 CreateEvent только до `user` (`name, symbol, uri, mint, bonding_curve, user`). Новых provider-вызовов нет. Pinned decoder не менялся.

## Что проверено

- после Borsh-строк name/symbol/uri у Create 195 остаётся ровно 96 байт = три pubkey
- синтетика шести полей: публичный `decode_pump_program_data` доходит до конца Borsh и падает `decoded_event_missing_timestamp`
- синтетика текущего pinned Create на кандидате → `event_payload_trailing_bytes`
- git fixture getTransaction Create `195` → тот же `decoded_event_missing_timestamp`
- retained A4, те же 3 страницы TASK-40: Create `195` → тот же код; Complete `112` и Migration `168` по-прежнему consume под `DROP_TRAILING_QUOTE_MINT`

Вывод: это тело Create на Borsh совпадает с ранним шестипольным layout. Поля `timestamp` в нём нет, поэтому pinned decoder не возвращает `DecodedPumpEvent`. `create_at` из `CreateEvent.timestamp` для этой подписи недоступен. Exclusive XB/RPC-cut и «текущий IDL» этим атомом не утверждаются.

## Что дальше не делается этим атомом

- fork / mutation pinned decoder
- вывод `create_at` из `blockTime`
- перепись receipts TASK-40/39 и previous H11
- live PIT / alpha / cashflow

Это не product DONE и не закрытие TASK-40.
