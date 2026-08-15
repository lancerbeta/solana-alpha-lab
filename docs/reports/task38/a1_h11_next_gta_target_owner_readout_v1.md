# TASK-38 RC002 — следующий bounded GTA target

**Терминальное решение:** `NEXT_BOUNDED_GTA_TARGET_NAMED`

Это offline naming адреса из уже захваченных A22/A23 байт. Это не новый Helius-вызов, не live PIT, не execution, не альфа и не cashflow. Именование цели не разрешает GTA.

## Что проверено

- family: `H11_LIFECYCLE_CLOCK`
- research cycle: `RESEARCH-CYCLE-RC002-001`
- trial: `TRIAL-RC002-H11-NEXT-GTA-TARGET-001` outcome `PASS`
- resolver SHA-256: `202010698e66fab87dc7fb8d4a553fd98bed43e39ff0fdfe36bdd8cf7a6d9e95`
- named kind: `TOKEN_MINT`
- named address: `DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK`
- network authorized: `False`
- live universe txs: `520`
- pool-owned mints after exclusions: `1`
- CreateEvent mints / bonding_curve: `0` / `0`
- incidental other-owner mints: `51`
- Pump program in account keys: `0`
- exact gap: named target is not a network authorization; getTransactionsForAddress remains forbidden in this atom
- RC001 definitions unchanged; remaining H13/H02 deprioritized
- RC001 holdout not consumed

## Маршрут

- scanned `HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001` target=`PUMPSWAP_POOL_ADDRESS` pool=`URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S`
- decoder: pinned TASK-08 Pump Create/Complete/CompletePumpAmmMigration
- unique resolver: pool-owned vault mint, else CreateEvent mint, else unique bonding_curve; never Pump program, never scanned pool, never wrapped-SOL quote
- new provider requests: 0; cash: 0

## Что этим атомом не делается

- новый getTransactionsForAddress / Helius call
- GTA всего Pump program `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`
- live PIT / available_to_strategy_at
- H11 effect screen, H13 или H02 trial
- paid capture / второй провайдер
- RC001 mutation, wallet, signer, tx, deployment

Это не product DONE, не альфа и не cashflow.
