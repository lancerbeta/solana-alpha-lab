# TASK-30 A11B — Two-slot live shakedown owner packet

## Назначение

Зафиксировать проверяемый **офлайн** пакет owner-review для будущей
двухслотовой технической проверки доступности закрытой 15-минутной свечи.
Consumer — owner, который решает, давать ли отдельное узкое разрешение на
восемь публичных GET-запросов.

## Scope

- Один кандидат: уже наблюдавшийся в A10 публичный keyless OHLCV маршрут
  GeckoTerminal для frozen Solana pool.
- Ровно две закрытые 900-секундные границы, независимые foreground starts.
- На каждую границу offsets `0, 15, 30, 60` секунд; не более восьми будущих
  GET.
- Обязательные raw-manifest/health receipt после каждого будущего ответа и
  запрет второго слота до read-back receipt первого.

## Authority

В A11B: provider/API/RPC/WSS calls = 0; credentials = 0; raw writes = 0;
scheduler/background process = 0; R2/R3 = 0; wallet/signer/transaction = 0;
cash spend = 0; TASK-30 trial/acceptance = 0.

`provider_candidate` не означает selected provider. Пакет имеет статус
`OWNER_APPROVAL_REQUIRED`; он не даёт external authority и не запускает
shakedown.

## Terminal packet statuses

- `OWNER_APPROVAL_REQUIRED` — офлайн-пакет валиден, но внешний read всё ещё
  требует точного owner gate.
- `PACKET_REJECTED` — структура нарушает safety boundary; живой запуск
  запрещён.

## Non-claims

A11B не создаёт data panel, PIT-admissibility, H07/H01 evidence, research
trial, execution, settlement, PnL, numeric NetReturn или 24-hour capture
authority. Missing и process failure не превращаются в zero, flat или market
gap.
