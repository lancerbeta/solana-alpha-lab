# RC002 — successor-close TASK-40: create_at gap + bound migration_at

**Терминальное решение:** `TASK40_CLOSED_CREATE_AT_GAP_MIGRATION_AT_BOUND`

TASK-40 для этого mint закрыт successor-записью. Исходный capture остаётся
`HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT` / `INCONCLUSIVE` и не переписывается.
`create_at = null` / `MISSING_UNKNOWN`. `migration_at = 1756321522` из
`CompletePumpAmmMigrationEvent.timestamp`. `CompleteEvent.timestamp = 1756321521`
— это `MIGRATION_STARTED`, не `migration_at`. Trial ledger не менялся.

## Что проверено

- TASK-40 mint `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`, bonding_curve `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC`
- TASK-40 acceptance bytes `ce13526f883f0b25cc709d7afaf307c63d1c60d652c2ac0f54e5d6fcb753a895`
- create_at receipt `CREATE_AT_MISSING_UNKNOWN`
- Complete/Migration receipt `COMPLETE_MIGRATION_IDENTITY_MATCH`
- Destination pool (публичный): `URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`
- Binder не читает `blockTime` и не декодирует события заново

Это не canonical DONE, не PIT, не alpha, не H11 effect screen и не option C
(больше Creates).
