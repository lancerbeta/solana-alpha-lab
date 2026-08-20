# Factory Common Market Feature Surface v1

**Терминал:** `FEATURE_SURFACE_COMPOSITION_PASS`

**Alpha / PIT_READY / operational-ready:** нет.

Три архетипа (price/path, liquidity/quote, creator-pressure) собрались через один `ExperimentSpec` + generic `ExperimentRunner` + capability `CAP-OFFLINE-MARKET-FEATURE-RESOLVE-001`. `runner.py` не менялся.

## Что видно владельцу

Required features в Cockpit-lite / Workbench:

- `✓ FEAT-TARGET-TRADE-COUNT` = 149 (исторический A24 Git receipt)
- `✓ FEAT-BUY-SELL-COUNT-RATIO` = 96/53
- `✓ FEAT-QUOTE-AVAILABILITY` = 1.0 на A1 cells, класс `FORWARD_ONLY`, это не KEEP
- `!` return/drawdown/volume/liquidity size = typed `UNKNOWN` (96-slot панель живёт в `local/`, не в Git)
- `—` creator direct share/sell = `MISSING`
- `— FEAT-CREATOR-CLUSTER-SHARE` = `MISSING_CAPABILITY`

Ни один признак не `PIT_READY`. `UNKNOWN` не превращён в 0.

## Git-патч к записке «Мув»

- `main` = `38ee8f4` (PR #159), quote-only KEEP уже `EXHAUSTED`.
- `feature_catalog.yaml` / `hypotheses.yaml` / `research_cycles.yaml` остаются пустыми: это freeze TASK-28, не дырка для заполнения.
- Словарь признаков живёт в Factory-owned surface config.

## Не делаем дальше из этого атома

VPS, Touch/Fee, новая quote KEEP family, entity graph, feature store.

**Следующий атом (MOVE 2, отдельный контракт):** одна обычная гипотеза через этот surface, core runner change target = 0.
