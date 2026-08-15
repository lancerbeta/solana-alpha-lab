# TASK-30 A24 — решение по admissibility raw→PIT

**Терминальное решение:** `LIMITED_DIAGNOSTIC_PANEL_READY`

Уже оплаченный нулём batch превращён в типизированную 96-слотовую панель.
Это не trial, не alpha и не принятие TASK-30.

## Покрытие

- Транзакции: `520`
- Target buy/sell: `96` / `53`
- Other-pool trades (исключения): `4`
- CloseUserVolumeAccumulatorEvent: `10`
- Truncated logs: `14`
- OBSERVED_TARGET_TRADES: `35`
- PROVEN_NO_TARGET_TRADE: `1`
- STATE_PERSISTENCE_PROVEN: `60`
- UNKNOWN_COVERAGE: `0`

## PIT

- Исторический retrieval **не** задран к `blockTime`.
- Ретроспективная market-history usability: да.
- Проспективная PIT-route usability: нет.

## Ограничения

- `RETROSPECTIVE_ONLY_FIRST_RELIABLE_AVAILABILITY_IS_CAPTURE_TIME`
- `NO_PROSPECTIVE_PIT_ROUTE`
- `NO_MULTI_NOTIONAL_ROUTE_PERSISTENCE`
- `NO_POST_MIGRATION_CONTINUATION_PROOF`
- `NO_CONTINUOUS_PRICE_PATH`
- `OHLC_NULL_WHEN_NO_TARGET_TRADE`
- `RESERVE_CARRY_FORWARD_ONLY_WHEN_STATE_PERSISTENCE_PROVEN`

## Что дальше

Решить, запускать ли один frozen H07/H01 limited diagnostic по новому точному контракту. Это не trial и не alpha.
