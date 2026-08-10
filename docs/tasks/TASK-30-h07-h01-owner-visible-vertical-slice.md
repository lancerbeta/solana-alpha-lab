# TASK-30 — H07/H01 owner-visible vertical slice

## Назначение

Этот атом даёт владельцу один честный ответ по замороженной группе
`RC001-H07-H01-LIQUIDITY-RETENTION`: можно ли уже запускать ограниченную
диагностику, или сначала нужно получить конкретные недостающие данные.

Consumer — `TASK30_H07_H01_EXACT_DATA_CONTRACT_ENTRY_GATE`.

Это не тест стратегии и не запуск research trial. Он не выбирает провайдера,
не собирает историю, не запускает планировщик и не открывает holdout.

## Замороженная основа

- group: `RC001-H07-H01-LIQUIDITY-RETENTION`;
- definition hash:
  `14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7`;
- входы: PIT liquidity-retention state, multi-notional route persistence,
  post-migration continuation context;
- требуемые truth-гaps: непрерывная PIT price history и settled execution truth.

## Допустимые решения

- `RUN_LIMITED_DIAGNOSTIC` — только когда каждый объявленный diagnostic input
  явно доступен;
- `CAPTURE_REQUIRED` — отсутствует названный PIT input и его получение является
  самым дешёвым следующим способом снять неопределённость;
- `REDESIGN_DATA` — допустимый capture не способен создать замороженные входы;
- `CLOSE_ROUTE` — именованный маршрут не может выполнить контракт в лимите.

Сейчас допустим только `CAPTURE_REQUIRED`. Это означает «сформулировать точный
следующий data-contract gate», а не «автоматически собирать данные».

## Non-claims

Текущая price/transport feasibility не является trial, alpha, стратегией,
execution, settlement, PnL или numeric NetReturn. Missing/UNKNOWN не означает
zero, no-trade, flat или settled.

## Граница

В этом атоме запрещены provider/API/RPC/WSS, credentials, raw data, R2/R3,
wallet, signer, transaction, cash, scheduler, background process, выбор
провайдера и изменение canonical статуса TASK-30.

`STATE_CHANGE=NONE`.
