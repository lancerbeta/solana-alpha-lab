# I3 — сбор без ручных активаций: readout

```text
I3 / I3_MANAGED_COLLECTION_CONTINUITY_V1 / BASE 07c81a99f2d0f385df66de2e1a5254e224c6b3b3
CODE_HEAD: exact candidate head bound in completion.json / PR
DEPLOYED: not deployed by this atom   OBSERVED_AT: 2026-10-14 (local synthetic evidence only)
OUTCOME: CODE_READY_RUNTIME_PENDING
ROUTE:   DIRECT_CLAUDE_CODE_DELIVERY
```

**Для Петра.** После одного утверждённого профиля обычный `tick --once` сам создаёт,
авторизует и включает «дочернее окно» на каждые UTC-сутки и продолжает обслуживать
хвосты предыдущих окон. Больше не нужны ручные регистрации B/C/D, отдельные таймеры и
JSON на каждое окно. Это код, проверенный на одноразовых хранилищах с синтетическим
транспортом: на VPS ничего не включено, A и взведённый B не тронуты.

## PROFILE/AUTHORITY

- Один профиль = один grant: `UNTIL_REVOKED` (новая семантика, не продление A/B) или
  `UNTIL_DATE`; те же 100/day, rolling 100, active cap 400, общие 1200/1200/2 000 000,
  cash 0, без retry/fallback. Точная фраза привязана к хэшу профиля и показывается
  `collection-plan` только если ничто не отказывает.
- Дочерний authority выводится из grant (`authority_basis=STANDING_GRANT`), а не из
  фразы: child обязан совпадать с утверждённым шаблоном (протекция, исключения, сетка,
  фильтры, лимиты). Выдача требует текущей revision и отсутствия отзыва; отзыв/окончание
  останавливает только **новый** intake, уже выданное право на хвост остаётся.
- Следующая граница, где нужен владелец: изменение профиля, отзыв, реальное исчерпание
  бюджета/права. Повышение выше 100/day код отказывает с числовыми осями (ceiling V1).

## CONTINUITY

- Порядок tick: хвосты (draining first) → один ограниченный reconcile (0 provider calls,
  0 чтений ключа) → первый tick нового child. Отказ одного child больше не обрывает
  остальные.
- Один владелец на UTC-день; окно child открывается в первый законный forward-момент
  (не backdated). После пропущенных дней — один child на сегодня, без фиктивных строк и
  старых вызовов. Закрытый до конца дня владелец не заменяется; новый child — на
  следующей границе (инцидент).
- Защищённый мост: `--bootstrap-not-before` ≥ stop взведённого B; `plan` отказывает
  `HANDOVER_BEFORE_PEER_STOPS`, контроллер ничего не создаёт на 17.10.
- Краткая нехватка места = HOLD раунда в том же child (не необратимый drain и не
  осколок дня); owner stop/revoke/abort по-прежнему закрывают intake.

## EVIDENCE

- 35 целевых тестов + seam-тест релиза: 3 UTC-границы с одной фразой и 3 производными receipts, raw-SQL
  oracle владельца дня; handover/plan-отказы; crash после activation до event и после
  register до authorize; конкурирующий reconciler; tamper grant (derive и tick); stop/
  re-apply/rollback; finite validity; матрица storage/backup/TARGET/HARD; weekly dedup и
  lineage через child; пропущенные дни; reconcile без записей в steady state; HOLD против
  sticky drain; alerts через существующий watch; release-селектор принимает daily scopes.
- Targeted mutation: 7/7 контролей убивают тесты (воспроизведение: см. proof.json) (child вне grant, backdated окно,
  storage не блокирует, нет repair события, нет HOLD).
- Регрессия прямых потребителей: 47 модулей, 735 тестов; единственные красные — 5 Windows/cgroup ошибок, идентичных на чистом origin/main (не связаны с изменением); vertical-сьют зелёный на чистом дереве.

## CAPACITY

- Геометрия (нижняя оценка, не прогноз): 100/day → 300 активных, 13 800 точек/день,
  ≥426 calls/день; 500/day → ≥978; 2000/day → ≥3048 и PACE_DISPATCH_WINDOW. Лимит V1
  100/day не ослаблен.
- Runway: `status/plan` показывают 5 метрик I2 (resident HOT, новые bytes/day, upload/day,
  remote retained, peak transient); без измеренного роста — `UNKNOWN_GROWTH_NOT_MEASURED`
  и одно действие I2. Ожидаемая экономия I2 = 0 до фактического APPLY.
  `MONTHS_RUNWAY_SUPPORTED` не заявляется.

## RECOVERY

- Рестарт/kill на любом шаге: следующий tick продолжает сохранённый intent; недописанное
  ResearchEvent активации чинится из committed transition. Лимит: один lineage на store.
- Restore: unresolved marker блокирует reconcile и tick. Откат профиля — новая revision
  (без фразы только если ничего не ослабляется); откат бинарника ниже этой сборки после
  первого managed child запрещён — forward fix.

## ALERTS

- Инциденты `MANAGED_INTAKE_BLOCKED|HELD|OWNER_MISSING`, `MANAGED_GRANT_INVALID`,
  `MANAGED_CHILD_STEP_FAILED`, `MANAGED_RECONCILE_ERROR` идут в существующий watch
  (один incident, один recovery, pending retry); штатное окончание managed child не даёт
  ложный `CAMPAIGN_SUCCESSOR_REQUIRED`.
- Не доказано здесь: фактическая доставка в Telegram и внешняя детекция потери VPS
  (`HOST_LOSS_ALERT_UNPROVEN`) — приёмка в OPERATE.

## BURDEN

- Утверждений на первый профиль: 1. На каждый следующий child: 0. Остаточные ручные
  действий нет: свежесть backup читается из существующих backup-владельцев, footprint
  меряется самим tick; ничего ежедневного ни для owner, ни для агента.

## NEXT / RESUME

- NEXT: одно действие владельца — exact merge phrase после CI и machine merge-readiness;
  затем отдельный OPERATE по `OPERATE_PACKET.md` (deploy, plan→apply одного профиля, B
  takeover 18.10 или ближайшая законная граница).
- Зависимость: I2 packaging (runway) и измеренный managed adapter, если нужен rate > 100.
- RESUME: `docs/tasks/I3_MANAGED_COLLECTION_CONTINUITY_V1.md`, ветка
  `claude/i3-managed-collection-continuity-v1`; не повторять I1, bridge, историю.

## Остаточные риски (названы, не скрыты)

- Утверждение профиля — целостность, а не происхождение: фраза выводится из профиля, поэтому
  доступ на запись в store = право grant (как у V1-фраз). Происхождение обеспечивает процесс
  OPERATE и owner-attention gate.
- HOLD-раунд и окно, открывшееся посреди дня, не пишут per-round ResearchEvent: потребители
  обязаны считать пропуски nomination UNKNOWN, а не «нет возможностей», и опираться на окно
  child, а не только на дату UTC.
- Не доказано здесь: ≥5 UTC-границ и недельная граница (доказаны 3 дня), 180d/100w масштаб,
  seal/import/preflight managed child, тест отказа старого бинарника (правило: после первого
  managed child бинарник не откатывать), Telegram retry/health.
- Если сам tick-timer мёртв, срабатывают только общие stale/timer алерты.
- Свежесть backup — это то, что сообщают существующие владельцы (off-host CURRENT или
  опубликованный bundle); содержимое архива код не проверяет.

- `LOCAL_BUNDLE` как источник backup не даёт off-host гарантии (нужен `OFFHOST_VERIFIED`);
  откат с off-host на local требует фразу. Событие authority, восстановленное после падения,
  несёт время восстановления; время выдачи берётся из receipt.

## Что код не утверждает

Нет deploy/коммишенинга/новых grants/provider calls; нет доказательства live Telegram;
нет claim работы месяцами; нет изменения A, B, C1/C2, исторических identity и научной
семантики; нет alpha/cashflow.
