# Ordinary market PIT — primary X bind

**Это не live audition и не MOVE 3.** Offline preflight внутри Muv-2 Move 1.

**Product terminal:** `GIT_RETAINED_CELLS_CANNOT_BIND_PRIMARY_X`

**Гипотеза заморожена:** `HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1`

Primary X = `liquidity / mcap` на Tokens V2 snapshot. Quote — будущий outcome, не предиктор.

- Git qualification: 12 ячеек, ключ `mcap` = 0, X = typed UNKNOWN
- Fixture с обоими полями биндит отношение; `fdv` не подменяет `mcap`
- Factory `runner.py` не менялся
- PIT_READY / alpha / live Jupiter: нет

Следующий шаг — отдельное owner-разрешение на bounded Jupiter capture, который **сохраняет raw token-list envelope**. Иначе X снова будет UNKNOWN.
