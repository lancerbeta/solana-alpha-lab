# I3 — общий бюджет аккаунта при смене activation: readout

```text
VERDICT: CODE_READY_RUNTIME_PENDING
ATOM:    I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1
BASE:    f8edf94f874484e4cecec61fa53cfca1dc77cbd4
HEAD:    exact candidate head is bound in completion.json / PR
ROUTE:   DIRECT_CLAUDE_CODE_DELIVERY
```

## Что было и что стало

**Было.** Исходный falsifier preflight (receipt self SHA `4f25a205…`): A
израсходовала 1200 calls за день и 2000000 lifetime, а B с новой identity видела
только свои 4 вызова и разрешала следующий. Причина: `_Accounting` читал
counters только по паре `(schedule, activation)`. Pace уже был общим на store,
а количественный бюджет — нет.

**Стало.** У store есть один управляемый аккаунт: логический `account_scope_id`,
привязанный к имени credential-слота `JUPITER_FREE_API_KEY` (значение ключа не
читается). При каждом `gate()` под writer lease общий расход считается заново
как сумма уже существующих per-activation строк по явному membership:
calls за день, credits за день и накопленные calls. Счётчики не копируются и не
переносятся. Новая activation в commissioned store привязывается в том же
commit. Индивидуальные caps (grant, per-tick, bytes, pace, окно dispatch)
продолжают действовать как дополнительный предел.

| Сценарий | До | После (commissioned) |
| --- | --- | --- |
| A 1200/2000000, B 4 → B gate | разрешает | `BLOCKED_BUDGET`, `SHARED_DAY_PROVIDER_CALLS` 1204/1200 |
| A 1199 + B 0 | — | ровно один вызов любой identity, дальше отказ |
| lifetime у предела, новые сутки/activation/revision | новый бюджет | отказ, `OWNER_DECISION_REQUIRED` |
| B исчерпан shared → transport | — | 0 отправок, нет STARTED в ledger |
| restart/backup-копия | — | тот же долг, отказ сохраняется |

Без commissioning поведение прежнее (default-off). Сам merge или deploy ничего
не включает.

## Account contract

- **Scope:** один ops store = один runtime credential locator = максимум один
  управляемый аккаунт. Повторный scope с другим именем не создаётся
  (`ACCOUNT_BUDGET_ALREADY_COMMISSIONED`).
- **Граница периода:** при commissioning в members входят все activations и
  counter scopes store, включая историю canary/legacy. Это консервативная
  граница: прошлый расход не выбрасывается и не угадывается.
- **Единицы:** provider calls/UTC day, modeled credits/UTC day (стоимость из
  registry), накопленные provider calls. Это local allocation; фактические
  тарифы Jupiter здесь не утверждаются.
- **Revision:** append-only; есть expected revision и идемпотентный command.
  Понижение лимита ниже уже потраченного оставляет долг и запрещает новый
  расход. Rollback политики делается новой revision, а не откатом счётчиков.
- **Source of truth:** существующие `accounting_counters`/`lifetime_counters`.
  Новые таблицы — только scope, policy и membership. Второго ledger нет.
- **Покрытие:** только контролируемые callers этого store. Внешние callers —
  `UNKNOWN`. `GLOBAL_ACCOUNT_PROVEN` не заявляется.
- **Состояния:** `UNMANAGED` (не настроено) / `MANAGED` / `CORRUPT` и
  `NOT_MEMBER` (было настроено, а binding потерян). Последние два —
  fail-closed `ACCOUNT_BINDING` до transport.

## Доказательства

- 16 адресных тестов (`tests/test_observation_shared_account_budget_v1.py`):
  отдельно daily, credits, lifetime, midnight, crash/atomic commit, конкурентный
  последний вызов со stale snapshot, replay против нового occurrence, commissioning
  fresh/stale/restore, backup-копия, старая readonly-схема, native late A→B на
  публичном tick. Oracle — заранее заданный trace и raw SQL, а не production
  helper.
- Targeted mutation: если отключить shared gate, падают 5/5 контрольных тестов;
  если вернуть порядок по hash, падает native-тест.
- Регрессия прямых потребителей: 23 модуля, 374 теста, PASS.
- Native late-successor: A естественно уходит в DRAINING, затем B через обычный
  lifecycle (`NATIVE_ACTIVATION`). Mixed default tick обслуживает A-хвост первым.
  Когда в shared остаётся 1 вызов, его получает due SEARCH A; nomination B
  получает typed `budget_denial` без отправки.
- Геометрия preflight (259+40 claims, 4 SEARCH, задержка 1s/8s): времена отправки
  совпадают байт в байт (16/20/24/28s и 16/27/38/49s), `PACE_WAIT` и
  восстановление на следующем tick сохранились. Shared day = числу отправок
  (7 и 6). Накладной расход managed-режима ≈0.015s на tick, ≈115µs на gate.
- Pins A (schedule `4744d401…`, grant `c2c937b4…`, storage `fa6450ba…`,
  protection `f70a7f2d…`) и C1/C2 не тронуты. Shared control — внешний
  операционный слой, frozen V1 не меняется.
- Peak RSS в production: `UNKNOWN`. Измерения синтетические.

## Остаточные риски и честные ограничения

- Per-tick cap остаётся индивидуальным, как его задаёт существующий envelope;
  общего per-tick ceiling в нём нет. Aggregate видно в multi-activation отчёте.
- Прямого резерва на будущие due-слоты нет. Приоритет хвоста обеспечивается
  порядком DRAINING→ACTIVE и тем, что process_slots идёт раньше nomination. Пик
  модели — 645 calls/day при shared 1200.
- После managed debits нельзя откатываться на binary или SQLite старше этого
  кода: старый код игнорирует shared gate. В packet это записано как запрет.
- Legacy X/Y lane проходит тот же gate, но `budget_denial` в его отчёт не
  добавлен (lane неактивен).

## Delivery

- Exact-head CI и machine merge-readiness — в PR. После review код не меняется
  без повторного review и rebind.
- Подготовлен `OPERATE_PACKET.md`: deploy точного merge-артефакта `M`,
  live-проверка default-off, prepare/apply без reset на работающем A, live
  readback, gates для B, rollback.
- V2 capture уже входит в `M` (I1 смержен раньше). Перед первым новым C3+
  capture нужно сверить хэши двух файлов. Отдельный «V2 PR» не нужен.
  Deployed код этим не заявляется.

## Следующее решение

1. **Рекомендация:** после merge — один компактный OPERATE: deploy `M`, проверка
   `UNMANAGED`, затем prepare/apply для `JUPITER-MANAGED-ACCOUNT-1` с лимитами
   1200/1200/2000000 и readback на обычных ticks. Нужна точная authority на
   deploy и на commissioning.
2. **Окно B:** `SHORT_BRIDGE_ONLY` — полусуточное B лишь rehearsal/fallback;
   sustainable window пока `NOT_YET_ESTIMATED` и зависит от I2 (footprint и
   compression).
3. **Дедлайн непрерывности:** intake A заканчивается 17.10 03:00 МСК; хвост A
   продолжается по своему grant до 20.10 01:05Z. Без безопасного successor —
   честный planned gap при сохранённом хвосте.
4. **Resume:** этот task contract; полная I3 не завершена.
