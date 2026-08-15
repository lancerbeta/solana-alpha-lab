# TASK-40 RC002 — GTA bonding_curve PDA, часы H11

**Терминальное решение:** `HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT`

Это один bounded Helius getTransactionsForAddress по bonding_curve,
выведенному PDA-семенами официального Pump IDL из mint TASK-38.
Это не live PIT, не execution, не альфа и не cashflow.

## Что проверено

- family: `H11_LIFECYCLE_CLOCK`
- trial: `TRIAL-RC002-H11-BONDING-CURVE-PDA-GTA-001` outcome `INCONCLUSIVE`
- mint: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`
- bonding_curve: `ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC` bump `255`
- txs: `2393`
- CreateEvent / CompleteEvent / CompletePumpAmmMigrationEvent: `0` / `0` / `0`
- Pump program in account keys: `2061`
- cohort n/pools/days/deployers: `0` / `0` / `0` / `0`
- missingness: `['CREATE_EVENT_NOT_IN_ADDRESSED_HISTORY', 'MIGRATION_EVENT_NOT_IN_ADDRESSED_HISTORY']`
- provider_requests: `3`; cash: `0`

## Что этим атомом не делается

- GTA всего Pump program
- повторный GTA mint
- H13 / H02 trial
- paid capture / второй провайдер
- live PIT / alpha / cashflow

Это не product DONE.
