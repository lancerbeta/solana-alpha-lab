# Quote-native панель — t0 измерение

Владелец разрешил quote-only панель. Пулы я взял из Git, без live-поиска: A24 post-migration mint и три независимых mint из TASK-21 R2 freeze.

## Что получилось

Терминал: `T0_PANEL_OBSERVED`. Это measurement panel, не hypothesis trial и не canonical DONE.

- 6 keyless GET на `JUPITER-SOLANA-SWAP-V2-ORDER-001`, без taker, без `/execute`, без credential/.env.
- Identity 1 (`A24_POST_MIGRATION`): оба notional, buy и reverse — `QUOTE_OBSERVED`.
- Identity 2 (`T21_R2_MINT_A`) buy `0.01 SOL` — тоже `QUOTE_OBSERVED`. Дешёвый инвалидатор «протокол ломается уже на второй identity» **не сработал**.
- Reverse второй identity вернул HTTP 429. Это typed `RATE_LIMITED`, не провал протокола. Дальнейшие t0-вызовы остановлены без retry. Остальные горизонты остаются `SCHEDULED`.

На наблюдаемых quote видны fee/route поля, которые one-shot sanitizer раньше отбрасывал: `feeBps`, `platformFee`, `priceImpactPct`, `routePlan`. Missing по-прежнему не заполняется нулём.

## Что это не значит

Не alpha, не NetReturn, не fill, не MOVE 2. H13/H02/H11/H07 не трогались. Horizons +15m/+60m/+240m ещё не снимались. Mint B и C на t0 не дошли из‑за rate limit.

## Дальше

`wave=due` читает только Git t0-receipt и снимает **только due horizon sells**, без leftover t0. Исходный t0 clock: `2026-08-17T23:30:59Z`. Оставшиеся горизонты quoted buys:

- +15m `SELL_H900`: `2026-08-17T23:45:59Z` — A24 оба notional и T21_R2_MINT_A `0.01 SOL`
- +60m `SELL_H3600`: `2026-08-18T00:30:59Z`
- +240m `SELL_H14400`: `2026-08-18T03:30:59Z`

Следующий provider call — решение владельца: горизонты только для уже quoted buys, или **новый** t0 clock для leftover B/C и T21_A `0.001 SOL`. Не retry 429. Не taker. Не `/execute`. Не H02.
