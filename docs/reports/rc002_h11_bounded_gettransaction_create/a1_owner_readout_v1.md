# RC002 — bounded getTransaction Create, один запрос

**Терминальное решение:** `CREATE_GETTX_SAME_195_STILL_TRUNCATED`

Один keyless `getTransaction` по pinned Create-подписи из TASK-40 A4. Маршрут `SOLANA-STANDARD-GET-TRANSACTION-001`. Helius не вызывался. Pinned decoder не менялся.

## Что проверено

- подпись `4fi62bv2A67i6rFh6naBrLyVoteXT4EnXaQzK7K2rboujxRy2AxEu5epesgG7hRcT3xhpZx15EKGG4BxxspX61EH`
- GTA Create Program-data: 195, без маркера `Log truncated`
- live HTTP 200, 11246 bytes
- getTransaction Create Program-data снова **195** (длина совпала с GTA; это не доказанная byte-identity)
- кандидат `DROP_QUOTE_MINT_AND_VIRTUAL_QUOTE_RESERVES` → `borsh_payload_truncated`

Вывод: публичный standard-RPC не восстановил более длинное Create-тело. Create 195 — не артефакт одной GTA-страницы. Exclusive XB/RPC-cut по этому логу не доказан, но гипотеза «GTA обрезал, а getTransaction восстановит» на этом запросе не подтвердилась.

## Что дальше не делается этим атомом

- Helius `getTransaction` / новый GTA
- перепись receipts TASK-40/39
- mutation pinned decoder
- live PIT / alpha / cashflow

Это не product DONE и не закрытие TASK-40.
