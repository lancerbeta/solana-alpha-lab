# Quote-native H900 MOVE 2 OOS — итог для владельца

## Вердикт

Уникальная Free-key попытка **прошла capture gate**, исключила 12 A1 mint
и на searchable Y=`SELL_H900` дала тот же ordinal sign:

`REPLICATED_SIGN_NOT_ALPHA`.

Это не alpha, не NetReturn, не закрытие family и **не MOVE 3**.
Знак replicated; кандидат и следующий MOVE не заработаны.

## Что произошло

1. Reservation записана при `credential_reads=0`; затем один process-env
   credential read. Та же попытка `run=20260818T220557Z` дала 34 consumed GET
   с hash-bound `observed_at`: discovery + t0 quotes + 10 `SELL_H900`.
2. Capture PASS. Frozen cohort: 6 RECENT + 6 TRADED, пересечение с A1 mint
   пустое. Cohort snapshot bind'ит discovery body SHA; `reselected=false`.
3. Sample valid на H900: 10 complete X/Y, 9 time-separated, recent 4 + traded 6,
   TRADED share `1`. Mechanism: 21 concordant / 15 discordant. H3600 не
   наблюдался и остаётся только robustness, не searchable Y.
4. Git receipt восстановлен из local envelopes **той же** попытки, без новых
   provider GET и без recapture-only retry.

## Почему это не alpha и не MOVE 3

Контракт заранее заморозил правило `concordant > discordant` без rate floor
на A1 31/14. Знак выжил на fresh disjoint 6+6. Это replication screening-hint,
не NetReturn и не право на MOVE 3. Следующий контракт — только owner decision.

## Следующее решение владельца

Оставить replicated sign без расширения, либо отдельный later contract.
`MOVE 3` этим атомом не открыт. Молчаливый retry этой же попытки запрещён.
