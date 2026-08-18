# Новый clock quoted-buy +15m

Владелец разрешил **новый** quote-only clock только для уже quoted buys: A24 оба notional и T21_R2_MINT_A `0.01 SOL`. Старый due_at не пересобирался. Leftover B/C и T21 A `0.001 SOL` запрещены.

## Что получилось

Терминал: `H900_PANEL_OBSERVED`. Это measurement panel, не hypothesis trial и не canonical DONE.

Новый `panel_started_at`: `2026-08-18T01:36:24Z`. Всего 9 keyless GET на `JUPITER-SOLANA-SWAP-V2-ORDER-001`, без taker, без `/execute`, без credential/.env. Retry 0. Cash $0.

t0 (6 вызовов): три buy — `QUOTE_OBSERVED`. A24 reverse оба notional — `QUOTE_OBSERVED`. Reverse T21_R2_MINT_A — HTTP 429, typed `RATE_LIMITED`, без retry. Это не провал протокола.

+15m `SELL_H900` due `2026-08-18T01:51:24Z`, снято `2026-08-18T01:52:14Z` (около 50 с после due, внутри slack 120 с). Все три delayed sell — `QUOTE_OBSERVED`. Дешёвый инвалидатор «quoted buy не даёт comparable sell на +15m» **не сработал**.

Quote-only `outAmount` (не fill, не NetReturn, не alpha):

| Cell | Buy in | Buy out | t0 reverse out | H900 sell out |
|---|---|---|---|---|
| A24 `0.01 SOL` | 10000000 | 10333269704 | 9933549 | 9959269 |
| A24 `0.001 SOL` | 1000000 | 1033357612 | 994641 | 997270 |
| T21_R2_MINT_A `0.01 SOL` | 10000000 | 299378607512 | RATE_LIMITED | 9755194 |

+60m `SELL_H3600` due `2026-08-18T02:36:24Z` и +240m `SELL_H14400` due `2026-08-18T05:36:24Z` записаны как `EXPLICIT_GAP`. Backfill запрещён.

Старый runtime receipt панели t0 не мутировался.

## Что это не значит

Не alpha, не NetReturn, не fill, не MOVE 1 complete, не MOVE 2. H13/H02/H11/H07 не трогались. Это не live PIT dataset.

## Дальше

Следующий шаг — решение владельца. Не авто-start leftover t0, не +60m/+240m backfill, не taker, не `/execute`, не H02.
