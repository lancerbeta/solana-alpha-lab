# Ordinary price-path hypothesis through the feature surface

**Capability terminal:** `FEATURE_SURFACE_COMPOSITION_PASS`

**Product terminal:** `ORDINARY_HYPOTHESIS_COMPOSED_NOT_PROMOTABLE`

**Alpha / PIT_READY / operational-ready:** нет.

Обычная гипотеза `HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1` собралась как ExperimentSpec
через существующий surface и generic `ExperimentRunner`. Factory Python
(`runner.py`, `capabilities.py`, `read_model.py`, `workbench.py`,
`market_feature_surface.py`, `application.py`) не менялся. Это не четвёртый
coverage-архетип: тот же classifier CLI на price-path archetype даёт
`NOT_AN_ORDINARY_PROMOTION_STOP`, потому что у архетипа `next_safe_action`
не `DO_NOT_PROMOTE`.

`FEATURE_SURFACE_COMPOSITION_PASS` — это composition capability, не научное
продвижение. Следующая обычная гипотеза добавляется тем же `--spec`, без
нового Factory Python.

## Что видно владельцу

- `✓ FEAT-TARGET-TRADE-COUNT` = 149 (исторический A24 Git receipt)
- `✓ FEAT-BUY-SELL-COUNT-RATIO` = 96/53
- `!` return / peak-return / drawdown = typed `UNKNOWN` (96-slot панель в `local/`, не в Git)
- `next_safe_action` = `DO_NOT_PROMOTE`
- Ни один признак не `PIT_READY`. `UNKNOWN` не превращён в 0.

Гипотеза составлена. Продвигать её нельзя, пока return-path остаётся typed UNKNOWN.

## Не делаем из этого атома

VPS, Touch/Fee, новая quote KEEP family, заполнение TASK-28 скелетов,
замена default commissioning spec, feature store.

TASK-28 `feature_catalog.yaml` / `hypotheses.yaml` / `research_cycles.yaml`
остаются пустыми по freeze.
