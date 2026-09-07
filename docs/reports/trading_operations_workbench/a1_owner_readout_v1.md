# TRADING_OPERATIONS_WORKBENCH_V2 — owner readout

Petr на GET `/operations` видит один вертикальный контур: что исполняется,
где путь Signal→Risk→Execution остановился, какой bounded command безопасен
и что runtime реально стал после команды. Parallel V2 store/service нет.

## VERDICT

```text
START_WITH_PATCH
TRADING_OPERATIONS_WORKBENCH_V2_READY_FOR_MERGE
```

## EXACT BASE / HEAD / PR

```text
BASE = dbe007f374f6ce1520c33094c5733e2d774a15c5
HEAD = 0724714136a36d4331038a61e35048c32534680d
PR   = (открывается после push)
```

## OWNER SENTENCE

На `/operations` можно OBSERVE → DIAGNOSE → ACT&VERIFY без SQLite, SSH и Git-археологии.

## THREE VERTICAL LOOPS

- OBSERVE: PASS — Git StrategyVersion отдельно от runtime Bot; нет активации → `ACTIVATION_GAP`.
- DIAGNOSE: PASS — стадии только по явной identity; close-команда не FILL/EXIT.
- ACT&VERIFY: PASS — пять существующих команд + свежий readback; stale CLOSE_ALL = 0 fanout.

## READ SAFETY

GET `/`, `/research`, `/operations`, `/economics`, `/system` не создаёт PaperPlane.
Absent = `NOT_PRESENT`. Битый файл = `RUNTIME_SOURCE_UNAVAILABLE`. Команда не
открывает writable DDL, пока readonly probe не видит схему.

## REMAINING GAPS

- `ACTIVATION_PATH_GAP` — активация inspectable, не createable.
- `WATCHLIST_SOURCE_GAP` — watchlist не изобретён.
- Нет mark TTL: нет `mark_as_of` → UNKNOWN; timestamped MARK не expire.

## ACTIVATION BOUNDARY

Нет START PAPER / START SHADOW / ACTIVATE STRATEGY. `start_bot()` не стал owner workflow.

## GIT / RUNTIME

Команда меняет только PaperPlane `local/` SQLite. Git StrategyVersion не утверждает,
что BotInstance изменился.

## BEFORE / AFTER

До: `/operations` мог выглядеть как пустой здоровый runtime и бутстрапить store.
После: СЕЙЧАС / ТРЕБУЕТ ВНИМАНИЯ / стратегии-боты / trace / позиции / команды / machine detail.

## SEMANTIC GIT

V2 consumes `OWNER_OPERATIONS_COCKPIT_V1`. Нового semantic route нет:
`SEM-OWNER-LIFECYCLE` + `SEM-AUTHORITY-BOUNDARIES`. README без изменения.

## TESTS / CRITICS / FIT / CI

Vertical A–K + GET immutability + GET-then-command + multi-bot CLOSE_ALL.
Isolated CODE / GOAL / ARCHITECTURE PASS.
`packet_fingerprint_sha256=574708e5c475f61cff177a11813cea2718ca7e7ffeff06c9f7f7619078954a48`
Factory Fit FULL_REVIEW PASS. Exact-head CI после PR.

## NON-CLAIMS

NO ALPHA. NO LIVE. NO REAL MONEY. NO OWNER FCF. NO DEPLOY. NO PROVIDER. NO WALLET.

## ROLLBACK

Обычный revert. Исторические positions/events/commands не переписываются.

## HORIZON

```text
NOW  = TRADING_OPERATIONS_WORKBENCH_V2
WATCH = OWNER_ATTENTION_AND_CHANGE_FEED_V1
```

Move 5 не стартовать.

## OWNER_ATTENTION_GATE_V2

Stop at merge-readiness. Owner never clicks GitHub Merge.
