# Отчёт владельцу — COLLECTOR_CAMPAIGN_CUTOVER_TRUTH_V1

**Срез:** 2026-09-29
**Результат атома:** непрерывность кампании и выбор tick описываются проверяемыми lifecycle-фактами.

## Что изменилось

- Историческая регистрация той же семьи, чьё окно завершилось к границе predecessor, получает HISTORICAL_OUT_OF_WINDOW и не выглядит продолжением.
- AUTHORIZED без связанного rollover и двух проверенных append-only transition events оставляет owner attention активным.
- После истечения окна DRAINING без доказанного successor остаётся GAP; оператору указана только существующая forward-only процедура NON_ADMITTING, без задних дат.
- Неподтверждённый ACTIVE не вытесняет DRAINING predecessor: alert привязывает GAP к отдельному continuity activation; без доказанного predecessor continuity остаётся UNKNOWN с owner attention.
- Зарегистрированное окно, начинающееся после cutover, помечается WINDOW_MISSES_CUTOVER и не получает невыполнимую инструкцию rollover.
- CLI захватывает единый UTC now после чтения runtime-конфига и до открытия SQLite; кандидаты проецируются через project_activation_as_of.
- Alert, operator runbook и Catalog описывают те же правила.

## Проверка

78 целевых unittest теста прошли. В тестах provider/credential вызовы не выполнялись; CLI replay заглушает физические зависимости и проверяет границу времени. Это доказывает локальную проекцию и lifecycle-поведение, но не live cutover.

## Product Horizon

**Capability radar:** NONE; no configured tool candidate conditions matched, and no installation authority is implied.

- NOW: после этого checkpoint оформить отдельный контракт FACTORY_OPERABILITY_BOUNDED_CALL_DIAGNOSTICS_V1. Ценность — измерить и ограничить память/длительность watch на диагностическом представлении. Основание — переданная исходная оценка полной истории call_ledger (40 127 строк, 1,39 ГБ payload) и 15-минутный watch; этот атом её не переизмерял. Риск/стоимость — новая SQLite projection, транзакционное сопровождение и resumable backfill. Владелец решения — владелец Factory. Триггер — завершение текущего continuity checkpoint.
- WATCH: при первом живом будущем cutover проверить наличие двух связанных immutable events и отсутствие приёма predecessor после boundary. Основание — только изолированные тесты; live доказательства здесь нет. Цена ложного PASS — незамеченный admission gap. Владелец — оператор Factory; триггер — отдельный live commissioning gate и наступление cutover.

## Границы

Не менялись live VPS, credentials, provider paths, activation/authority, SQLite schema, retention, campaign limits, научные параметры или append-only история. Не заявляются успешный live rollover, непрерывность на 7 дней или исправление call_ledger memory path.
