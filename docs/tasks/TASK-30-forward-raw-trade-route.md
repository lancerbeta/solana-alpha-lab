# TASK-30 A12 — Forward raw trade route offline contract

## Назначение

Зафиксировать минимальный офлайн-контракт будущего forward raw-trade route для
frozen consumer `RC001-H07-H01-LIQUIDITY-RETENTION`.

Это не collector и не выбор Helius. Контракт проверяет только то, что будущий
маршрут обязан различать наблюдаемое событие, собственную потерю покрытия и
неопределённость до любого построения 15m research panel.

## Решаемый вопрос

Можно ли подготовить безопасный будущий owner packet для одного raw-observation
route, не превращая reconnect, отсутствие записи или пустой интервал в
`no-trade` либо complete data.

## Scope

- Pure offline validation только над synthetic envelopes.
- Одно frozen pool identity binding и явные coverage states.
- Deterministic Russian owner readout.
- Reuse-first finding: official Helius stream is only `WRAP_CANDIDATE`;
  Yellowstone/replay class is `WATCH_ONLY`.

## Authority and non-claims

provider/API/RPC/WSS calls, credential use, raw writes, scheduler/background
processes, dependencies, R2/R3, wallet/signer/transaction actions, cash,
trial and Project Sources changes равны нулю.

Контракт не выбирает provider, endpoint, parser, recovery source или storage.
Он не доказывает data completeness, PIT admissibility, H07/H01 evidence,
alpha, strategy, execution, settlement, PnL или numeric NetReturn.
