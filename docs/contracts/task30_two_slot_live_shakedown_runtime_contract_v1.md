# TASK-30 A11C Two-slot live shakedown runtime contract v1

## Purpose

Этот контракт определяет только локальный, однократный runtime-harness для
будущей технической проверки одного keyless GeckoTerminal OHLCV route. Он не
собирает исследовательскую панель и не выполняет внешний запрос при своей
офлайн-приёмке.

## Exact future authority

`--execute` допустим только после отдельного owner gate с единственной
грамматикой фразы:

```text
T30-A11C_TWO_SLOT_SHAKEDOWN_EXECUTION_V1;pool=<FROZEN_POOL>;
slot_starts_utc=<SLOT_1>,<SLOT_2>;
monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND;max_gets=8;
retention=A4;retry=false;fallback=false
```

`SLOT_1` и `SLOT_2` — два последовательных UTC начала 15-минутных интервалов.
Один foreground invocation обслуживает только один slot и максимум четыре GET
после закрытия его границы на offsets `0,15,30,60` seconds. Второй slot не
стартует без здорового hash-bound receipt первого.

## Immutable outputs and recovery

Каждый ответ записывается вне Git under A4: raw bytes, затем cumulative raw
manifest и health receipt. Любая ошибка записи, опоздание, нарушение маршрута,
неизвестный прошлый receipt, monitoring loss или transport error останавливает
slot. Нет retry, fallback, hidden restart, scheduler или сжатия пропущенных
вызовов.

## Non-claims

Результат — только `SLOT_TECHNICAL_HEALTHY`,
`SLOT_TECHNICAL_INCONCLUSIVE` либо `STOP_RUN`. Он не утверждает PIT
admissibility, H07/H01 evidence, trial, execution, settlement, PnL,
NetReturn, выбор provider или authority на 24-hour capture.
