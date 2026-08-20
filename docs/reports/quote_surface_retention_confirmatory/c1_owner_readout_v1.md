# Quote-surface retention confirmatory — owner readout

Живая Free-key confirmatory 6+6 завершилась. Терминал —
`CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY`. Измерение с часами
сработало в обоих strata. KEEP не дал median/tail uplift против
eligible baseline. Это закрытие family, не Atom 2, не alpha и не
`FACTORY_V1_OPERATIONAL_READY`. Recapture не делается. PR #156 остаётся
`SAMPLE_INVALID_REPLAN_REQUIRED`.

## Packet

| Field | Value |
| --- | --- |
| QUESTION | После квалификации часов: есть ли у KEEP-if-`RETENTION_DELTA >= 0` decision utility для входа на H900 и выхода на H3600? |
| ESTIMAND | KEEP versus eligible baseline на H900→H3600 ForwardQuotedReturn, не PnL |
| POPULATION | новая live 6 RECENT + 6 TRADED, исключая A1, MOVE 2, commissioning, ATOM 5, ATOM 6 и PR 156 |
| DATA | capture policy + шесть exclusion receipts; runtime hash-bound |
| RESULT | `CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY` (`NO_MEDIAN_OR_TAIL_UPLIFT`) |
| UNCERTAINTY | screening hint, не OOS confirmation |
| ROBUSTNESS | searchable Y = точный sell `BUY_H900` на H3600; `clock_valid` time-separation |
| FAILURE | KEEP median и p90 не лучше baseline при валидных клетках в обоих strata |
| DECISION | закрыть exact quote-surface retention family; без Atom 2 |
| NEXT | не EXTEND_TO_SHADOW; не VPS; ATOM 5 и ATOM 6 остаются закрытыми |

## Что говорят числа

Capture PASS: 62 GET, 1 credential read, 0 retries/fallbacks, cash $0.
12 frozen cells, пересечение mint с excluded (включая 12 mint PR #156) = 0.

Валидных decision/outcome cells: RECENT 5 / TRADED 6. Пол ≥4 на стратум.
Одна RECENT клетка `UNKNOWN` (не VETO и не numeric zero). Часы:
11 `CLOCK_VALID`, 1 `UNKNOWN`. KEEP: RECENT 2 / TRADED 4. VETO: RECENT 3 /
TRADED 2.

KEEP median Y `-0.0272814` против baseline `-0.0272693`; KEEP p90
`0.4983044` против baseline `0.7529128`. Направление совпадает, strata
не unstable. Uplift нет — family закрывается честно, без TRADED-only
rescue.

## Architecture residual

Поле `capture.searchable_y_kind` в runtime осталось `SELL_H900` от WRAP
старого envelope. Скоринг шёл по `SELL_H3600_FROM_BUY_H900`. Поле
`family_close` в WRAP-receipt — helper friction-аудиции и остаётся
`false`; научный close читается из `terminal` /
`retention.terminal`. Не чинить recapture-ом и не открывать Atom 2.
