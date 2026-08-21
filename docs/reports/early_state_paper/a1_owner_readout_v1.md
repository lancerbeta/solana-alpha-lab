# EARLY state → paper plane — owner readout

Терминалы: научный `EARLY_STATE_NO_DECISION_VALUE`; продуктовый `GENERIC_RESEARCH_TO_PAPER_PLANE_PASS`.

Это не alpha, не NetReturn, не live. Factory core Python не менялся (runner sha закреплён). Provider calls: 0.

## Научный ответ (честный)

Замороженная гипотеза: «EARLY-токены с ликвидностью ≥ $2000 на момент решения живут лучше в терминах удержания ликвидности к T+76m». Ответ на 27 pinned mint'ах: **решающей ценности нет** — все 27 монет и живы, и их ликвидность ровно на уровне решения (ratio = 1 у всех), бин разложения пустой (LOW n=0 при пороге 8). Гейт промоушена не пройден — правило в промоушен не идёт. Это валидный научный результат, а не провал данных.

Netflow-фича (X2) была честно исключена у 21 из 27 (нулевая органика в 5-минутном окне) — UNKNOWN не превращался в ноль.

## Продуктовый ответ (главный)

Путь `decision → StrategyVersion → BotInstance → PAPER → позиция → exit → reconciliation` **работает end-to-end без bespoke pipeline**:

- Новый truth contract `strategy_version.schema.json` (микро-live запрещён схемой).
- Две конфигурации стратегий (`STRAT-V-EARLY-LIQ-FLOOR`, `STRAT-V-EARLY-NETFLOW-TILT`) — COMMISSIONING_ONLY.
- Один generic engine (`paper_plane.py`): SQLite store ботов и позиций, lifecycle из ARCH-INTENT-005, SIMULATED_FILL никогда не становится REAL_FILL.
- **Leverage test PASS**: вторая стратегия отличается только YAML — движок тот же, поведение разное (27 vs 3 fill'ов).
- 57 позиций прошли полный цикл до RECONCILED; нелегальные переходы fail-closed.

## OPERATIONS view

Strategy / Bot / Mode / Signal / Position / Exit readiness / Reconciliation / Blocker / Next safe action — все девять полей отдаются проекцией; сейчас: 2 бота PAPER, 0 открытых позиций, reconciliation CLEAN, next = CONTINUE_PAPER_OBSERVATION.

## Что дальше

ATOM 3 `FACTORY_REMOTE_OPERATIONS_V1` — реальный VPS + backup + monitoring, теперь с named consumer (paper-боты).
