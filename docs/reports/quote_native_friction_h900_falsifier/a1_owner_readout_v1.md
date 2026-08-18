# t0 friction → +15m quoted liquidation

Владелец разрешил quote-only look на **четырёх unused T21 freeze mint**: B, C и два R3, один notional `0.01 SOL`. A24 и T21 A запрещены. Live discovery нет. `+60m/+240m` — явный gap.

## Что получилось

Терминал машины: `DIRECTIONAL_HINT_NOT_CONFIRMATION`. Это **не** confirmation, не NetReturn, не live universe и не MOVE 2.

`panel_started_at`: `2026-08-18T07:56:21Z`. Всего 9 keyless GET на `JUPITER-SOLANA-SWAP-V2-ORDER-001`, без taker, без `/execute`, без credential/.env. Retry 0. Cash $0.

t0 остановился на HTTP 429 после 6 вызовов: B и C — buy+reverse `QUOTE_OBSERVED`; R3_1 buy `QUOTE_OBSERVED`, reverse `RATE_LIMITED`; R3_2 не достигнута. Retry не было.

+15m `SELL_H900` due `2026-08-18T08:11:21Z`, снято `2026-08-18T08:11:39Z` (18 с после due, внутри slack 120 с). Три delayed sell с quoted buy — `QUOTE_OBSERVED`.

Quote-only atomic amounts (не fill, не NetReturn):

| Identity | Buy in | t0 reverse out | H900 sell out | X friction | Y recovery |
|---|---|---|---|---|---|
| T21_R2_MINT_B | 10000000 | 9755375 | 9755375 | −2.446% | −2.446% |
| T21_R2_MINT_C | 10000000 | 9727199 | 9727199 | −2.728% | −2.728% |
| T21_R3_MINT_1 | 10000000 | RATE_LIMITED | 9752928 | missing | −2.471% |
| T21_R3_MINT_2 | NOT_REACHED | NOT_REACHED | SCHEDULED | missing | missing |

Полных X+Y клеток: **2**. Concordance 1/1, поэтому машина дала directional hint. На обеих полных клетках **Y в точности равен X** (тот же `outAmount`). За 900 секунд quoted liquidation не сдвинулась. Это не предсказание будущего, а застывшая котировка stale cohort.

`SAMPLE_INVALID` не ставился: две полные клетки есть. Family **не** закрывается. Порог не подбирался.

## Что это не значит

Не alpha, не NetReturn, не fill, не live 15m memecoin universe, не MOVE 2. H13/H02/H11/H07 не трогались. Missing не ноль.

## Дальше

Не замораживать rule по этим двум клеткам. Следующий атом, если продолжать family, — **свежее outcome-blind окно**, не confirmation holdout на этой выборке и не `+60/+240` backfill.
