# Population Fit ATOM 1 — owner readout

Терминал: `NOMINATE_IN_SCOPE_MATURITY_BOUNDARY_TEST`.

Это не alpha, не TRADED-as-product, не feature tournament и не ATOM 2.

## Решение

Шесть независимых Git-кампаний (84 строки, 0 mint-reuse, overlay `#168` не считался новым рынком) дают одну картину:

1. Source-strata нестабильны: ATOM 5 и ATOM 6 закрылись `STRATUM_UNSTABLE`, kept = только `TRADED`.
2. Сверхсвежий `/recent` (~18–69 с) — не product EARLY. Честный EARLY (5–15m, early-path, не TRADED) имеет median Y `-0.027` и **0 положительных из 17**. Один MOVE2 TRADED в возрасте 5–15m из product EARLY Y исключён.
3. `TRADED` нельзя принять как population: возраст до ~650 дней, launchpad на frozen cells неизвестен, это control source.
4. Зрелость определяется pre-outcome полями на **всех** 84 строках (`missing_age_n=0`). Исторический source-traffic в 30–120m не пуст (`seasoned_source_supply_n=6`), границы **не** двигались по Y.

Заморожено для ATOM 2:

- EARLY: pump.fun, `[5m, 15m)`
- SEASONED: pump.fun, `[30m, 120m]`
- common: liquidity ≥ $1000, 0.01 SOL, без consumed mint
- source ≠ population; reclassify через bulk Tokens V2 search

## Что дальше

Следующий атом — `IN_SCOPE_POPULATION_AND_STATE_DISCOVERY_V1` (новая кампания, 3-call supply gate до quote). Этот атом его не запускает.

Provider calls: 0. Factory runner не менялся.
