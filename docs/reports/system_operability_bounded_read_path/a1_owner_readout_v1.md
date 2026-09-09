# SYSTEM_OPERABILITY_BOUNDED_READ_PATH_V1 — owner readout

Petr открывает HOME и `/system` как текущее техническое здоровье, не
пересчитывая Observation RDP / backup tree / operational history на каждый
GET. Тяжёлый collector packet считает существующий
`factory-operability-watch` раз в 15 минут и кладёт bounded snapshot в
`operability_collector_snapshot.json` (и extra key в incident-state,
который GET не читает).

## VERDICT

```text
START_WITH_PATCH
SYSTEM_OPERABILITY_BOUNDED_READ_PATH_CANDIDATE
INTERACTIVE_BOUNDED_READ
```

Канонический `DONE` и live latency не следуют из тестов, PR, CI или merge.
Deploy в этом атоме запрещён.

## OWNER SENTENCE

Интерактивный GET читает свежий derived snapshot плюс живые O(1) сигналы.
Нет snapshot / битый JSON / старше 1080s / нет source `observed_at` →
честный UNKNOWN, без синхронного rebuild и без подмены времени часами watch.
HOME/`/system` получают attention `COLLECTOR_SNAPSHOT_*` (MISSING →
подождать один watch cycle), а не «всё чисто».

## DECISION_DELTA

До: ordinary `compose_system_operability()` без `collector_packet=` один раз
вызывал `build_collector_operational_packet`, когда sqlite ObservationSchedule
существует; TTFB рос с объёмом данных.
После: GET не импортирует и не вызывает packet/read-model builder; producer —
тот же watch timer.

## FRESHNESS

```text
cadence = 900s (OnCalendar=*-*-* *:0/15:00 UTC)
grace   = 180s
fresh   <= 1080s
two missed cycles (1800s) cannot stay collector-derived OK_OBSERVED
```

STALE сохраняет исходный `observed_at` для диагностики, но
collector-derived coverage не `AVAILABLE`, overall не `OK_OBSERVED`,
и stale packet не классифицирует текущие incidents / ACTION_REQUIRED.

## FIRST DEPLOY (design only)

После будущего owner-gated deploy snapshot отсутствует → `NOT_PRESENT` /
`MISSING`. Ждать один watch cycle. `--mode emit` не warmup кэша.

## VERTICAL LOOPS

- OBSERVE: GET spies = zero `build_collector_operational_packet`, zero
  `build_collector_read_model`, zero recursive RDP/backup walk.
- DIAGNOSE: MISSING / INVALID / STALE fail-closed; allowlist ≠ `dict(packet)`.
- ROUTE & VERIFY: live HTTP_SELF / systemd / deploy marker / Git HEAD / env
  presence остаются live; recovery routes не менялись.

## /system SURFACE

HTML `/system` уже dumps `collection`; туда попадает
`collector_snapshot` freshness без redesign Workbench.
`scripts/show_system_operability.py` использует тот же composer.

## TESTS / CRITICS / FIT / CI

84 targeted tests PASS. Isolated CODE / GOAL / ARCHITECTURE after product
freeze. Factory Fit `FULL_REVIEW`. `CAPABILITY_RADAR_NOW=NONE`.

## NON-CLAIMS

```text
NO ALPHA
NO LIVE
NO REAL MONEY
NO OWNER FCF
NO DEPLOY
NO PROVIDER CALL
NO DRIVE WRITE
NO TELEGRAM SEND
NO WALLET
NO SYSTEM HEALTH FROM GIT
NO MONITORING PLATFORM
NO CANONICAL DONE
NO LIVE_VPS_LATENCY_REPAIR
NO REDIS_DAEMON_OR_SECOND_STORE
```

## ROLLBACK

Revert the PR merge. Extra `collector_snapshot` key ignored by predecessor.
No runtime DB migration. No host mutation in this atom.

## PRODUCT HORIZON

```text
NOW   = NONE
WATCH = LEAST_PRIVILEGE_SMIAL_OPERATOR_VPS_OBSERVER
        after merge + owner-gated deploy + fresh snapshot + live /system proof
SECONDARY WATCH = FAST_OPERABILITY_SIGNAL_PLANE
        only if PAPER/SHADOW needs faster than the 15-minute heavy cycle
CAPABILITY_RADAR_NOW = NONE
```
