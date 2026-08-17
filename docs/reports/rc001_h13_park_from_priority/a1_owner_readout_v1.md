# RC001 — H13 паркуем с приоритета, науку не удаляем

**Терминальное решение:** `H13_PARKED_FROM_PRIORITY_SCIENCE_RETAINED`
**Решение владельца:** `PARK_H13_FROM_PRIORITY`

Это **снятие H13 с живого приоритета фабрики**, а не опровержение гипотезы, не подтверждение, не canonical DONE, не alpha и не разрешение собирать данные или платить за них.

## Что припарковано

- family: `RC001-H13-COMPOSITE-VETO`
- priority: `PARKED_FROM_PRIORITY`
- science: `RETAINED` (удаление: `false`)
- hypothesis verdict: `NOT_REFUTED_NOT_SUPPORTED`
- family status: `PARKED_FROM_PRIORITY_NOT_CANONICAL_DONE`

## Почему

H13 остаётся `BLOCKED_DATA`: entity route не пригоден для downstream decision, непрерывной PIT-цены нет, settled execution truth нет. Продолжение без нового exact-контракта превратило бы неизвестность в иллюзию evidence.

- TASK-24: `STOP_NO_RELIABLE_ENTITY_SIGNAL`, entity route: `NOT_ADMISSIBLE`
- TASK-28 H13: `BLOCKED_DATA` — `ENTITY_ROUTE_NOT_ADMISSIBLE, CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE, SETTLED_EXECUTION_TRUTH_UNAVAILABLE`
- definition SHA-256: `f1f020f4fa79acd2f2de667d71b8002d5821f45e9070a0f259c63210b23a16d0`

## Что с другими RC001 семьями

- H07/H01 historical A27 receipt: `RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED`; этот атом не делает unpark
- H02/H10/H14: `BLOCKED_DATA`; H02/H10/H14 автоматически не стартует.
- Этот атом не выбирает следующую RC001 семью.

## Когда можно вернуться к H13

Только после новой точной owner-задачи, а не по календарю, recency или частичному кешу:
`NEW_EXACT_CONTRACT_WITH_EXPLICIT_OWNER_DECISION_AND_SEPARATE_ADMISSIBLE_ENTITY_PIT_AND_SETTLED_EXECUTION_EVIDENCE`

- group: `RC001-H13-COMPOSITE-VETO`
- frozen definition: `f1f020f4fa79acd2f2de667d71b8002d5821f45e9070a0f259c63210b23a16d0`
- обязательно закрыть каждый исходный blocker: `ENTITY_ROUTE_NOT_ADMISSIBLE, CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE, SETTLED_EXECUTION_TRUTH_UNAVAILABLE`

## Что этим атомом не делается

- `H13_TRIAL`
- `H02_H10_H14_TRIAL`
- `ENTITY_ROUTE_REDESIGN_OR_CAPTURE`
- `CONTINUOUS_PIT_OR_EXECUTION_CAPTURE`
- `H07_H01_UNPARK`
- `PROVIDER_OR_CREDENTIAL_CALL`

Нет provider/network/credential/wallet/cash side effects. Этот атом не меняет RC001 freeze и не запускает trial.
