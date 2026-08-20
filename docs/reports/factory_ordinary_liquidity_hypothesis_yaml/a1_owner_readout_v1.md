# Ordinary liquidity hypothesis as YAML

**Это не MOVE 3.** Вторая обычная гипотеза — YAML на уже существующем `--spec` CLI.

**Capability terminal:** `FEATURE_SURFACE_COMPOSITION_PASS`

**Product terminal:** `ORDINARY_HYPOTHESIS_COMPOSED_NOT_PROMOTABLE`

**Alpha / PIT_READY / KEEP / operational-ready:** нет.

- `✓ FEAT-QUOTE-AVAILABILITY` = 1.0, класс `FORWARD_ONLY`, это не KEEP
- `!` quoted friction / pool liquidity / liquidity retention = typed `UNKNOWN`
- CLI `scripts/run_factory_ordinary_market_hypothesis.py` не менялся
- Factory Python не менялся

Гипотеза составлена. Продвигать execution-гипотезу нельзя, пока quote forward-only и friction UNKNOWN.
