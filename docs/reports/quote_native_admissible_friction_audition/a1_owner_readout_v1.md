# Quote-native admissible friction audition — итог для владельца

## Вердикт

Свежий Free-key campaign **прошёл capture gate** и дал screening-hint:

`DIRECTIONAL_HINT_NOT_CONFIRMATION`.

Это не alpha, не NetReturn, не MOVE 2 и не закрытие family. Точный H900
friction mechanism **не опровергнут** на этом admissible sample.

## Что разблокировалось

1. Capture больше не является blocker'ом текущего contour: attempt reservation
   до чтения ключа и hash-bound `observed_at` на 50 consumed rows попали в
   канонический receipt.
2. Numeric floors снова выполнены: 12 complete X/Y (порог 10), 10
   time-separated (порог 6), обе strata, TRADED control kill не сработал, 0×429.
3. Frozen relation `QuotedRoundTripFriction(t0) → QuotedLiquidationRecovery(H900)`
   дала 31 concordant vs 14 discordant pairs. H3600 остался robustness
   (9 moved / 2 same) и **не** был вторым searchable Y.

Следующее решение владельца — отдельный MOVE 2 контракт на fresh untouched
cohort с тем же frozen rule, либо оставить hint без OOS.

## Наблюдения

- Заморожен outcome-blind cohort: 6 RECENT + 6 TRADED.
- 50 GET: Token API 2× HTTP 200; Swap API 47× HTTP 200 и 1× HTTP 400
  (`SELL_H3600` RECENT_2, typed missing).
- Один credential read после reservation; ноль retry/fallback; нет
  taker/build/execute/wallet/signer; cash spend = $0.
- Две H900 клетки с `Y=X` исключены из direction, как и раньше.

## Почему это hint, а не кандидат

Concordance на одном 12-cell window может быть sample luck. Контракт запрещает
tuning и MOVE 2 внутри этого атома. Replication — только новым контрактом.

## Ограничения

- H14400 остаётся explicit gap.
- Один typed HTTP 400 на H3600 не обнуляется.
- Screening не есть execution fitness и не есть NetReturn.
- Вложенные `campaign.non_claims` / `mechanism.non_claims` в runtime — leftover
  wrapped scorer'ов; канон только top-level acceptance/readout.
