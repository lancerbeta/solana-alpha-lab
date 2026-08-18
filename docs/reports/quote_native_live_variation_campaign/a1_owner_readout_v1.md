# Live Tokens V2 sample → +15m / +60m quoted variation

Владелец разрешил keyless discovery через Jupiter Tokens V2 (`/recent` + `/toptraded/1h`) и quote-only `/swap/v2/order` без taker. T21 freeze и A24 запрещены. `+240m` — явный gap. Это не friction-prediction trial и не Factory v1.

## Что получилось

Терминал машины: `SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY`. Это **не** directional hint, не confirmation, не NetReturn, не alpha и не MOVE 2.

Discovery (2 GET, оба HTTP 200, keyless): `/tokens/v2/recent` в `2026-08-18T09:35:50Z`, затем `/toptraded/1h` в `09:35:52Z`. Когорта заморожена: 6 RECENT + 6 TRADED клеток, notional `0.01 SOL`. Реестр v8 добавлен после этого наблюдения; семантика семи маршрутов v7 не менялась.

`panel_started_at`: `2026-08-18T09:36:11Z`. Всего 14 keyless GET, retry 0, cash $0, credential/.env 0, `/execute` 0.

t0 остановился на HTTP 429 после шести `/order` вызовов (~10 с при паузе 2 с; дальше пауза поднята до 3 с, всё ещё `pace >=2s`). Retry не было. Остаток t0 остался `NOT_REACHED`, это не догон.

+15m due `2026-08-18T09:51:11Z`, снято `09:52:29Z` (внутри slack 120 с). +60m due `10:36:11Z`, снято `10:36:43Z`. Только parent-quoted sell: RECENT_1, RECENT_2, RECENT_3.

Quote-only atomic amounts (не fill, не NetReturn):

| Identity | Buy in | t0 reverse out | H900 sell out | H3600 sell out | X | Y |
|---|---|---|---|---|---|---|
| RECENT_1 | 10000000 | 9727419 | 9028630 | 9028630 | −2.726% | −9.714% |
| RECENT_2 | 10000000 | 9756891 | 9263746 | 9263746 | −2.431% | −7.363% |
| RECENT_3 | 10000000 | RATE_LIMITED | 8363852 | 8363852 | missing | −16.361% |
| RECENT_4–6 и все TRADED | NOT_REACHED | NOT_REACHED | SCHEDULED | SCHEDULED | missing | missing |

Полных X+Y клеток: **2** (оба RECENT, оба `Y≠X`). Time-separated: **2**. TRADED complete: **0**. Kill на контроле не сработал. Success-пол (≥10 complete и ≥6 time-separated, оба страта) не набран.

На трёх parented sell `outAmount` в +15m и +60m совпал; response sha256 при этом разные, это не копия строки. Это не механизм и не hint.

Family **не** закрывается. Порог не подбирался. H13/H02/H11/H07 не трогались.

## Что это не значит

Не alpha, не NetReturn, не fillable, не live 15m universe claim, не MOVE 2, не закрытие quote-native family. Missing не ноль. `Y=X` на этой выборке не наблюдался; двух клеток недостаточно, чтобы говорить о variation-present.

## Дальше

Не замораживать rule. Следующий атом, если продолжать family, — отдельный контракт: либо более редкий paced quote на свежем окне (MOVE 2 только после `VARIATION_PRESENT_NOT_MECHANISM`), либо owner-решение по tighter keyless 429. `+240m` не догонять.
