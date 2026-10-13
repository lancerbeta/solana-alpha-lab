<!-- Condensed transcription of the owner-attached chat document
I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1_PRD_SSD.md (13.10.2026, V1): sections 0-7
are kept with light condensation, sections 8-12 are summarized, section 13 sources
are omitted. No original file SHA256 was supplied; the attached document stays
the authority and this copy is only a Git audit reference. -->

# SMIAL — общий бюджет аккаунта при смене activation

**PRD + SSD + самодостаточная передатка исполнителю · 13 октября 2026 · V1**
**Atom:** `I3_EPISODE_SHARED_ACCOUNT_BUDGET_BRIDGE_V1`
**Parent:** `SMIAL_MANAGED_COLLECTION_OPERABILITY_V1`, прежде всего §6, §9–12.
**Entry recommendation:** `START` — один ограниченный вертикальный ремонт общей accounting-границы.
**Режим этого документа:** DESIGN. Стартовая команда в §12 выбирает EXECUTE только данного атома.
**Рекомендуемое усилие:** `SOL_XHIGH` для accounting semantics, compatibility и recovery; обычные проверки исполнитель выбирает сам.

> **Outcome:** новая activation того же управляемого Jupiter-аккаунта не получает «свежий кошелёк запросов». A-tail и B-intake используют общий сохраняемый бюджет, не обходят индивидуальные grants и проходят существующий late-successor путь. Это один используемый в дальнейшем компонент I3, а не новый scheduler, временный ручной перенос counters или вся managed-runtime система сразу.

## 0. Решение для владельца и место в программе

Preflight не остановил рабочий collector и не обнаружил доказанного live перерасхода. Он на изолированном сценарии выявил дефект, который проявляется при смене технической identity: A исчерпала бюджет, B смотрит лишь на свои counters и продолжает разрешать вызовы.

Ремонт нужен до совместной работы A и B. Ранее установленная I1 остаётся принятой: C1+C2 импортированы, 47 episodes / 6533 episode-point pairs; её не воспроизводить заново ради процедуры.

Рекомендуемая последовательность:

1. Исправить общий accounting и доказать прежний late-successor сценарий на production entry point в изоляции.
2. После exact merge — отдельный компактный OPERATE: установить совместимый artifact, включить/bind общий учёт без обнуления A, проверить обычные вызовы A. В тот же план deploy включить уже смерженный V2 capture, если совместимость exact artifact подтверждена; не собирать произвольный hybrid на VPS.
3. Перейти к I2: coherent snapshot/compression и вывод ненужных legacy bodies из HOT. Не ждать 17 октября, чтобы начать эту работу.
4. По новым измерениям выбрать пригодное следующее окно и обеспечить переход отдельным разрешением. Полусуточное B ниже — проверочный/аварийный bridge, не целевая эксплуатационная модель.
5. Остальная I3 сохраняется в плане: runtime limits, TARGET acceptance, автоматическое продолжение в standing grant, operational rollback. Этот атом не объявляет её выполненной.

NOW: общий accounting A+B. WATCH: I2 footprint + пригодная длительность продолжения; producer V2 должен быть установлен до первого нового live capture, заявляющего исправленную snapshot-семантику.

## 1. Что известно; что только предложено

### 1.1. Входное evidence исполнителя [H1]

Preflight завершён `2026-10-13T17:43:58.929873Z` — 20:43:58 МСК, до установленного checkpoint `14.10 03:00 МСК`.

| Область | Полученный результат | Граница вывода |
|---|---|---|
| Изолированный falsifier | A: 1200 calls/day и 2000000 lifetime исчерпаны; B с новой identity и 4 своими calls разрешает ещё вызов | Доказанный software-дефект; не свидетельство фактических 1200/2000000 вызовов на VPS |
| Предпочтительная ветка | Natural ACTIVE→DRAINING A, затем native late-successor B с отдельным envelope | Не zero-gap rollover и не уже выполненная activation |
| Ранний rollover | До cutover теряется predecessor ACTIVE proof; B на границе не получает нужный storage binding | Не исправлять эти две альтернативные границы в данном атоме |
| Default tick overlap | 259 A + 40 B due claims, четыре SEARCH calls, 299 OBSERVED; при response delay 8s sends 16/27/38/49s внутри 60s | Ограниченный сценарий; не универсальный load proof |
| Quotas / pace | Lineage day/rolling/weekly mint semantics и 3s pace сохранены в проверенном сценарии | Наличие pace не исправляет общий количественный budget |
| Collector | На 17:40:53Z: ACTIVE, 65 admissions; 3951 OBSERVED + 5019 future PENDING; backlog/outbox=0 | Readback в моменте, не обещание дальнейшей health |
| Source spot | Одна штатная SEARCH: HTTP 200, request/response/visibility clocks, raw hash, published row совпали | Не scientific readiness; source price event time остался UNKNOWN |
| Model B | 306 active, до 645 calls/day, whole-Factory peak 35.99 GiB; запас до TARGET 4.01 GiB, free 71.72 GiB | MODEL, не successor commissioning PASS; будущая экономия I2 не зачтена |
| Off-host | Последний checkpoint 13.10 00:45Z; свежий full-state coverage UNKNOWN | Перед live commissioning нужны применимые свежие pins |
| Внешние callers | За пределами данного store/account lane — UNKNOWN | Не выдавать local aggregate за provider-side global usage |

### 1.2. Exact anchors и resume

```text
Repository: lancerbeta/solana-alpha-lab
Git design/review anchor: f8edf94f874484e4cecec61fa53cfca1dc77cbd4
Reported deployed producer: 4378c5b82f2dc309ccd629b267affd5d19b34995

A activation: ACT-4744D4017AC4B196
A schedule: 4744d4017ac4b19625c5ee11ce4e20fdd4b36c6744f8c0889467052e2a6ef23c
A authority: c2c937b4462b28f45a423bb42d702c3052f9a996bf4d399e58168d6e378db038
A storage envelope: fa6450ba0fd9da64fa3792c8b5de0c22aacf948589f7e9b1e8e78ae236b8dcad
Protection pin: f70a7f2d82b27bd39b1affbb72be339401bb0d223275965ce68df795112ec3ef
A intake stop: 2026-10-17T00:00:00Z = 17.10 03:00 МСК
A grant expiry: 2026-10-20T01:05:00Z
A modeled final dispatch/availability: 20.10 00:00Z / 00:05Z

Unregistered B PROPOSAL, NOT AUTHORITY:
  starts: 2026-10-17T00:15:00Z
  stops:  2026-10-17T12:00:00Z
  minimum expiry: 2026-10-20T13:05:00Z
  schedule: 9d3327eb9c79126541e80b4ae17f9abd853a0e0886fff297633be7ad5303db7b
  activation: ACT-9D3327EB9C791265
  nominal cap: 100/day; partial-window bound: up to 49 admissions

Preflight directory: local/i3_episode_continuity_preflight_v1/
Preflight receipt: continuity-preflight-receipt.json
Preflight receipt self SHA:
  4f25a20520716dcc2e6121a8ea92d3992c7bc4dd6a2cd9d57791da0aa55744fa
I1 accepted production receipt:
  6f6292d15d1592ce01006391e3c407f8325526fe55ea3c6a5f0f57cfe6c8b248
Parent PRD/SSD SHA256:
  6f3cce30bbea09eeffe286ccb6f9bc3a53dddf46b213dae038be0dc4ab4880e3
```

Parent source copy: `docs/evidence/smial_managed_collection_i1_v1/source-contract.md`. Runtime anchors и результаты [H1] получены из переданного handback. Executor перепроверяет receipt и его нужные evidence bindings, не пересоздаёт всю диагностику.

## 2. Scope и полномочия

### Входит

- Одна account-aware budget boundary для управляемых Jupiter calls через существующие accounting/store и provider-call entry points.
- Правильная агрегация daily calls, daily modeled credits и cumulative/lifetime call debits через A, B, COMPLETE и DRAINING identities внутри явно связанного scope.
- Одновременное сохранение индивидуальных schedule/grant ограничений, pace, deadlines и текущей reservation-семантики.
- Минимальная runtime binding/commissioning операция; наследование того же account scope новым разрешённым successor без ручного переноса counters.
- Проверяемое включение на уже работающем A, restart/restore, no-reset policy revision и безопасный rollback. Live применение — отдельный gate.
- Изолированный late-successor A+B на обычном CLI/tick, согласованность default paths, короткий cold readback, deploy/commissioning packet.
- Контракты, navigation/readout и ровно те регрессии, которые защищают затронутые риски.

### Не входит

Новый scheduler, zero-gap rollover repair, autonomous standing-grant renewal, полный runtime profile engine, повышение 100/day, изменение TARGET/HARD, сжатие/очистка SQLite, новый backup service, новый API/provider, научные просмотры, смена population/grid/seed/protection, повтор I1.

Текущий EXECUTE: локальный code/test/spec, disposable state, штатные Git branch/PR/checks по harness; узкие уже разрешённые read-only production probes допустимы только по необходимости. Не разрешены: live deploy; commissioning/APPLY в production; register/authorize/activate B; новые provider calls; Telegram/Drive writes; timers/settings; destructive actions; merge без exact owner gate. Подготовка такого packet — разрешена, его исполнение — нет.

Не спрашивать владельца о выборе таблицы, индекса, test helper или имени аргумента. Остановиться только при новой material semantics/authority boundary, несовместимом live state или невозможности достигнуть согласованного outcome.

## 3. Подтверждённый root cause и owners

На `f8edf94…` `_Accounting.__init__()` читает `load_accounting(schedule_sha256, activation_id, utc_day)` и `load_lifetime(schedule_sha256, activation_id)`. `gate()` сравнивает эти локальные суммы с budget schedule. Тот же файл имеет одинаковый blob на design anchor и reported deployed `4378c5b…`. [G1]

`opportunity_episode_tick.py` использует этот `_Accounting`; `_prime_account_pace()` уже смотрит на последний вызов в store. Следовательно, общий pace и общий budget сейчас разные вещи. `_call()` выполняет reservation до STARTED/send, сохраняет неопределённый debit и при completion не добавляет второй обычный call debit. [G2]

| Existing owner | Что здесь важно |
|---|---|
| `observation_scheduler.py::_Accounting` | gate/reserve/note; не добавлять независимый конкурентный расчёт рядом |
| `observation_schedule_store.py` | accounting/lifetime counters, call occurrences, writer lease, persistence; минимальные новые bindings здесь |
| `opportunity_episode_tick.py::_call`, `run`, `admission_quota` | все SEARCH и category paths, cross-midnight reservation, recovery, tail vs nomination |
| `observation_provider_pacing.py` | wait/gate и reserved completion; не нарушить clocks/3s spacing |
| `scripts/observation_schedule.py` | обычный default tick, prepare/status/activation integration; не только private helper |
| `observation_schedule_lifecycle.py` | индивидуальная authority, late successor и storage binding; не менять старые hashes |
| `configs/observation_schedule_runtime_v1.yaml` | logical credential slot `JUPITER_FREE_API_KEY`; содержимое ключа не читать/не хэшировать для identity |
| episode/operator contracts, existing backup/retention contracts | status scope, recovery и сохранение бюджетных totals после I2 |

## 4. Семантика бюджета: сначала определить объект, затем считать

### 4.1. Не смешивать три объекта

1. Индивидуальный grant activation: уже разрешённые routes, сроки и caps. Новый общий механизм может только дополнительно ограничить такой вызов, не выдать ему authority.
2. Shared managed-account allocation: совокупный допуск для всех привязанных локальных callers одного логического аккаунта. На нём работают daily call/credit caps и накопленный budget.
3. Фактический тариф/лимит Jupiter: внешняя система; текущие числа 1200/day и 2000000 — не объявляются её универсальными лимитами. Используется утверждённая allocation, без нового исследования тарифов/покупки.

`lifetime` здесь означает накопленные debits в явно названном операционном budget scope, а не бесконечный лимит всего аккаунта на всю жизнь. Смена activation или revision не начинает этот scope заново. Незаметный reset в данном bridge запрещён.

### 4.2. Stable identity и membership

Нужен несекретный logical `account_scope_id`, устойчивый при A→B, restart, смене Git SHA и ротации ключа того же аккаунта. Не использовать schedule/activation, текущую дату, значение ключа или его hash как account identity.

Привязать scope к существующему runtime credential locator + owner-assigned logical account. Один env name сам по себе не доказывает, что исторически под ним всегда был один и тот же аккаунт. Mapping old scopes подтверждается metadata commissioning; неизвестное не угадывается.

Membership включает не только ACTIVE: прошлые COMPLETE/PAUSED scopes того же выбранного budget domain всё ещё потребили бюджет. Но нельзя `SUM(*)` по всей SQLite и приписать Jupiter расход чужого provider/account.

Новый successor через native activation path разрешает account binding автоматически из утверждённого runtime context. Если managed account уже commissioned, отсутствие/порча binding не разрешает тихо вернуться к старому activation-only gate.

Scope применения: контролируемые callers данного store. Внешние scripts/ПК/иные credentials остаются отдельно обозначенной неопределённостью. Не строить distributed limiter; не заявлять `GLOBAL_ACCOUNT_PROVEN` без полного coverage. Existing legacy same-key caller не должен обходить managed policy: либо проходит ту же account boundary, либо отказывается до transport как неподдержанный consumer.

### 4.3. Формула допуска

```text
ALLOW_REQUEST = individual_authority_valid
             AND existing_per_activation_limits_pass
             AND shared_day_calls_used + next_call_debit <= shared_day_call_limit
             AND shared_day_credits_used + next_credit_debit <= shared_day_credit_limit
             AND shared_lifetime_debits + next_call_debit <= shared_lifetime_limit
             AND account_pacing_pass
             AND dispatch_window_pass
             AND required_integrity_and_storage_bindings_pass
```

Для отказа предпочтительно сохранить существующий `BLOCKED_BUDGET` и добавить в native readout область и причину: `budget_scope`, `budget_dimension`, `used`, `requested_debit`, `limit`, `policy_revision`, `next_action`. Caller должен отличать shared exhaustion от своего local cap; status/readback сам не пишет counters.

Shared limits не складываются из limits A+B. Существует один действующий owner-approved shared policy, индивидуальные более узкие caps остаются дополнительными. Per-activation raw/canonical-byte caps и storage reserve сохраняются. Per-tick cap не молча меняет смысл; если existing approved envelope задаёт общий per-tick ceiling, он должен соблюдаться в default A+B invocation.

Изменение чисел shared policy в дальнейшем — OPERATE, не PR. В bridge достаточно малого prepare/apply/status пути со revision/idempotency/authority binding. Повышение shared cap не увеличивает индивидуальные grants. Понижение ниже уже использованного amount оставляет debt неизменным и отказывает новым расходам.

## 5. SSD: минимальный рекомендуемый механизм

### 5.1. Сначала переиспользовать существующие debits

Existing per-activation accounting/lifetime rows остаются первичной историей расхода; единый account resolver и budget gate получают их агрегат по явно привязанному scope. Runtime binding хранится в той же operational SQLite. Lifetime берётся из соответствующего owner; не сумма lifecycle states и не `COUNT(COMPLETED ledger)`. Не вводить Redis, стороннюю БД, очередь, сервис или body replication.

### 5.2. Одна точка разрешения и durable reservation

Общий gate должен стоять на реальном path перед transport для nomination и SEARCH. В managed path окончательный gate читает актуальное состояние под existing writer fence; B, созданный до последнего debit A, не должен сохранить устаревший разрешающий snapshot.

```text
resolve exact existing grant + managed scope
acquire / validate existing writer fence
read authoritative current debit + active budget revision
check local + shared limits
commit durable reservation and its attribution
persist/reuse the same occurrence STARTED via native seam
send once, only after successful reservation
complete/recover without a second ordinary debit
```

Не держать SQLite transaction открытой на HTTP wait. Два sequential `save_*()` не становятся атомарными. Invariant: ни один реально разрешённый расход не исчезает; одно и то же сохранённое reserve/replay не расходуется ещё раз; неизвестная отправка не повторяется.

### 5.3. Не менять принятую reservation-семантику

- `COMPLETED` — lifecycle completion, не обязательно HTTP200.
- Reservation до STARTED/send считается расходом; crash/timeout/429/no-request после reserve не возвращает его.
- Повтор COMPLETED occurrence использует ledger, не HTTP, не новую reservation.
- Тот же request URL/hash с другим occurrence — отдельный вызов.
- Pure `gate()` / preview не пишет counters.
- Completion добавляет bytes/pacing, не ещё один call/credit debit.
- Cross-midnight: сохранить консервативную семантику дополнительного debit дня `request_started_at`, включая влияние на lifetime.
- Новые UTC-сутки открывают новый day bucket, не сбрасывают lifetime. Смена A→B внутри суток не даёт reset.

### 5.4. Tail важнее новых admissions, но не выше реального лимита

Existing committed observations имеют приоритет над optional nomination; B не должен съедать доступный текущий quota, из-за чего уже due A автоматически лишается SEARCH. Если общего лимита не хватает даже на due observations, превышать его нельзя: typed no-request/budget gaps, явный residual, без обнуления debt и автоматического увеличения budget. Ежедневный transient BLOCKED_BUDGET не уничтожает все будущие slots; expired lifetime требует owner decision.

## 6. Включение на уже работающем A, durability и rollback

6.1. Bootstrap без ложного нуля: prepare показывает account_scope, revision, member scopes, day debits/credits/cumulative calls, completeness и excluded/unknown callers, limits, remaining, expected fingerprint и exact action. Не переносить автоматически всё старое и не выбрасывать всё старое; граница периода и inclusion объясняются явно. Если aggregate строится по existing rows, не копировать их «в B». Расход A между rehearsal и APPLY включается при фактическом commissioning. Отсутствие historical attribution — `BUDGET_BASELINE_UNRESOLVED`, не guessed zero; ручной SQL-edit counters — нет.

6.2. State guards: current shared values и bindings — runtime, не Git. Replay versioned apply возвращает прежний результат, stale apply не перезаписывает новый. Missing never-configured и corrupt/missing previously configured различаются. Historical A schedule/grant/storage envelope остаются byte-exact.

6.3. Backup/restore и I2: новые bindings входят в существующий mutable backup за счёт того же store. Restore не обещает zero-RPO; existing restore marker gate сохраняется. Удаление legacy bodies/compaction не уменьшают day/lifetime debt.

6.4. Rollback: до commissioning обычный code rollback допустим. После managed debits нельзя вернуть старую SQLite или старый binary, игнорирующий shared budget. Operational rollback — новая revision без отката счётчиков. При дефекте gate: не запускать B, сохранять safe A/tail; не `UPDATE counters=0`.

## 7. Достаточное evidence

Минимальная матрица рисков: исходный falsifier; daily boundary отдельно; lifetime отдельно; credits отдельно; второй ACCOUNT; COMPLETE A + active B + C без binding; два процесса на последний debit; сбой до/после reserve/STARTED/response; replay и другой occurrence того же URL; UTC rollover внутри STARTED/send; policy lower/raise/rollback; commissioning fresh/повтор/stale/dirty; backup/restart/recovery marker; native late A→B на public default tick. Exhaustion daily/lifetime/credits разделить.

Независимый oracle: заранее заданный trace, отдельная сумма, transport spy. Targeted mutation: вернуть activation-only lookup — контроль обязан падать. Public overlap наследует геометрию 259+40 claims/4 SEARCH/8s delay. Запрет full payload scans на hot path; измерить wall/work/RSS; сравнение production-entry before/after timing.

## 8–12. Последовательность, late-successor, handback, календарь, стартовая команда

A. Восстановить точный reproducer. B. Зафиксировать минимальный контракт и сделать ремонт (без нового singleton cap 1200 в Python; значения из approved binding). C. Закрыть acceptance и подготовить один self-contained OPERATE packet. D. Independent risk-routed review; exact-head CI → machine merge-readiness → owner phrase → guarded merge/post-merge readback. После merge scope ещё `CODE_READY_RUNTIME_PENDING`. E. Будущее OPERATE (здесь не исполнять): bind fresh A state и compatible artifact; применить shared binding/baseline без изменения frozen A; наблюдать штатные A calls без ручного API smoke; подготовить B commissioning; producer V2 в том же проверенном artifact либо одна конкретная несовместимость.

Late-successor: native branch требует natural DRAINING и append-only closure, `starts_at` не раньше, без backdating; zero-gap rollover и renewal timer не открывать. Полусуточное B `17.10 00:15–12:00Z` — rehearsal/fallback, не production default; после I2 пересчитать окно, иначе `SHORT_BRIDGE_ONLY`.

Handback §10: VERDICT, BEFORE→AFTER, ACCOUNT CONTRACT, PROOFS, DELIVERY, NEXT DECISION в одном `OWNER_READOUT.md`.

Стартовая команда §12: общий durable day/credit/lifetime budget управляемого Jupiter account без reset A→B, с сохранением индивидуальных grants, reservation/recovery semantics и native late-successor overlap; existing accounting/store/lease; без scheduler, второго ledger или сервисов; shared values — runtime, не Git constants; A schedule/grant/storage/protection и C1/C2 не изменять; managed scope не включается от merge/deploy; до reviewed exact-head CI и machine merge-readiness; один prepared OPERATE packet. Никаких provider calls, production register/authorize/activate, deploy/APPLY, timers, cleanup, I2, science или merge без exact owner gate. First stop: exact merge gate либо material blocker.
