# Quote-surface retention falsifier — owner readout

Живая Free-key кампания завершилась. Терминал —
`SAMPLE_INVALID_REPLAN_REQUIRED`. Это не закрытие семейства, не PASS,
не Atom 2 и не `FACTORY_V1_OPERATIONAL_READY`. Recapture по этому receipt
не делается.

## Packet

| Field | Value |
| --- | --- |
| QUESTION | Есть ли у заранее замороженного KEEP-if-`RETENTION_DELTA >= 0` decision utility для входа на H900 и выхода на H3600? |
| ESTIMAND | KEEP versus eligible baseline на H900→H3600 ForwardQuotedReturn, не PnL |
| POPULATION | новая live 6 RECENT + 6 TRADED, исключая A1, MOVE 2, commissioning, ATOM 5 и ATOM 6 |
| DATA | capture policy + пять exclusion receipts; runtime hash-bound |
| RESULT | `SAMPLE_INVALID_REPLAN_REQUIRED` (`INSUFFICIENT_VALID_CELLS_PER_STRATUM`) |
| UNCERTAINTY | screening hint, не OOS confirmation |
| ROBUSTNESS | searchable Y = точный sell `BUY_H900` на H3600 |
| FAILURE | RECENT не дал ≥4 time-separated complete cells; TRADED-only не спасает |
| DECISION | REPLAN; без post-hoc threshold; без recapture suffix; без Atom 2 |
| NEXT | не EXTEND_TO_SHADOW; не VPS; ATOM 5 и ATOM 6 остаются закрытыми |

## Что говорят числа

Capture PASS: 62 GET, 1 credential read, 0 retries/fallbacks, cash $0.
12 frozen cells, mint overlap с excluded = 0.

Валидных decision/outcome cells: RECENT 0 / TRADED 6. Пол ≥4 на стратум.
RECENT: H900 reverse и H3600 sell вернули тот же `outAmount` (sticky quote).
Часы H900 и H3600 различаются (~45 мин), но этот атом WRAP-нул прежний
прокси `Y≠X` (равный recovered SOL = клетка не complete). Это
консервативно и не закрывает семейство. Менять правило после просмотра
выборки нельзя. TRADED: 3 KEEP / 3 VETO, все с разным reverse/sell.
TRADED-only PASS запрещён.

## Architecture residual

Поле `capture.searchable_y_kind` в runtime осталось `SELL_H900` от WRAP
старого envelope. Скоринг шёл по `SELL_H3600_FROM_BUY_H900`. Не читать это
как второй searchable Y и не чинить recapture-ом.

## Non-claims

Нет alpha, NetReturn, Atom 2, VPS, paid plan, second provider, `/execute`,
wallet, signer, transaction, post-hoc threshold search, TRADED-only rescue
или `FACTORY_V1_OPERATIONAL_READY`.
