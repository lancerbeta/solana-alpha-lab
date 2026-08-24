# EARLY_HOLDER_CONCENTRATION_ACTIONABILITY_RULE_OOS_V1 — owner readout

## Verdict

`REPLICATED_RELATION_NOT_ACTIONABLE_AS_TOP_QUARTILE_VETO`

Phase A закрыта offline, без Jupiter. Замороженное правило
`HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_V1` не прошло development-set
decision-utility gate на двух уже завершённых holder-окнах.

Механизм **остаётся** `HOLDER_CONCENTRATION_MECHANISM_REPLICATED`.
Это **не** закрытие Kendall-репликации. Это отказ считать top-quartile
veto достаточно полезным entry-правилом, чтобы тратить fresh OOS.

Jupiter не вызывался. Альтернативный порог, median split, 20/30/40%
search, continuous score и третий mechanism-sample **не открывались**.

## Frozen rule (до row-level Y)

Среди X-valid eligible: `veto_count = ceil(n / 4)` самых высоких
`audit.topHoldersPercentage`; остальное `PASS`; missing X =
`VETO_UNKNOWN`. Абсолютный `X > N%` не искался.

## Почему FAIL

Нужны были **все** условия. Упали A, B и C; покрытие D прошло.

| Gate | Result |
| --- | --- |
| A directional, оба окна: median PASS > median VETO **и** > median ALL | FAIL: PASS > VETO, но PASS **не** > ALL |
| B pooled: median PASS > 0 | FAIL: pooled median PASS = `-0.0272814` |
| C оба окна: operational_bad_rate PASS < ALL X-valid | FAIL: оба = `1.0` |
| D оба окна: PASS count >= 12 | PASS: 16 и 16 |

`operational_bad` = H900 `MARKET_EXECUTION_UNAVAILABLE` **или** rankable
`Y < 0`. Numeric Y для MEU не подставлялся.

### Окна (development only)

Initial falsifier: X-valid 22, missing 2, PASS 16, VETO 6;
median Y PASS `-0.0272814`, VETO `-0.3441751`, ALL `-0.0272814`;
PASS MEU 0 / VETO MEU 3.

Confirmatory: X-valid 22, missing 2, PASS 16, VETO 6;
median Y PASS `-0.0272814`, VETO `-0.1292694`, ALL `-0.0272814`;
PASS MEU 0 / VETO MEU 4.

Pooled: PASS 32, VETO 12, missing 4; median Y PASS `-0.0272814`,
VETO `-0.2312574`; negative-Y rate на rankable = `1.0`.

Veto-хвост хуже по median Y, и MEU почти целиком сидит в VETO.
Этого мало: PASS всё равно везде с отрицательным quote-only H900 Y,
поэтому правило не улучшает opportunity quality относительно всех
X-valid и не даёт median PASS > 0.

## Evidence

`docs/evidence/early_holder_concentration_actionability_rule_oos/a1_phase_a_receipt_v1.json`

SHA-256: `924e6d8087bfe281922aee291cdf16fa3323b09a8a9633ca520a59626b0c2c39`

`decision_time_eligible_count` = ICP freeze cohort (24 на окно), включая
X-missing. `x_valid_count` = 22. Coverage D смотрит PASS count, не 24.

## Residual (не rescue)

Много rankable Y совпадают ровно с `-0.0272814` в обоих окнах.
Это ограничивает информативность quote-only recovery для bulk PASS,
но **не** повод менять percentile или порог в этом атоме.

`jupiter_top_holders_pool_exclusion = UNKNOWN`.

Initial + confirmatory окна после этой инспекции — DESIGN/DEVELOPMENT
evidence для данного правила. Они больше не validation evidence для
этой policy.

## Что дальше

`NEXT = DESIGN_ONLY_REFRAME`

Вернуться к owner. Не искать автоматически другое concentration-правило.
Не открывать Paper / Strategy / Shadow / третий holder sample.

Возможный следующий **owner-selected** ход, не этот атом:

- новый cheap mechanism search; или
- DESIGN_ONLY переформулировка estimand, если owner считает, что
  quote-only H900 Y слишком слабо различает bulk cohort.

## Non-claims

No alpha, no NetReturn, no Paper, no Strategy, no Shadow, no live Jupiter
in this atom, no canonical DONE for a trading rule.
