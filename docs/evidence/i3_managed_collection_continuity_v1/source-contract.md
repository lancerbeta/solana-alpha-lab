# I3 — сбор без ручных активаций

**Самодостаточный PRD + SSD и контракт исполнения · 14 октября 2026**
**Atom:** `I3_MANAGED_COLLECTION_CONTINUITY_V1`
**Program:** `SMIAL_MANAGED_COLLECTION_OPERABILITY_V1`
**Mode этого документа:** DESIGN. Передача исполнителю с командой из §16 выбирает EXECUTE; не разрешает merge, deploy, новый live grant или удаление production-данных.
**Entry:** START — завершить managed collection, переиспользуя принятые I1 и shared-account bridge. Не повторять их разработку.

> **Outcome:** Пётр один раз утверждает понятный режим. VPS сам продолжает разрешённый сбор, создаёт и обслуживает внутренние schedules, переживает обычные отказы и сообщает о существенных проблемах. Пётр не регистрирует очередные B/C/D, не держит открытый компьютер, не согласовывает каждый JSON. Изменение поддерживаемой нагрузки и возврат прежних настроек — операции, а не новые PR.

## 0. Решение, границы и что читать

**Рекомендуемый путь:** небольшой управляемый режим поверх существующих CLI, SQLite, lifecycle, scheduler, shared-account accounting и уведомлений. Один control owner, один provider lane. Внутренние конечные schedules остаются frozen; долговременное разрешение на их выпуск принадлежит родительскому grant. Новая платформа, второй collector, Redis, очередь задач и LLM в runtime не нужны.

Это уточнение **§6 исходного плана**, а не его замена. Нужный ему минимум §7 — сообщения об отказах и работа после reboot — входит в данный outcome. I2 остаётся владельцем упаковки backup и retirement legacy; полный cold catch-up/I4 и научный запуск/I5 не включаются автоматически.

### 0.1. Что изменено относительно исходного плана

1. По последнему решению владельца штатный режим не должен регулярно истекать ради очередного подтверждения. Предлагается `UNTIL_REVOKED` для **нового** standing grant, ограниченного provider routes, количественными/ресурсными бюджетами и обязательствами. Finite `UNTIL_DATE` также поддерживается. Это проектное изменение authority-контракта, **не сегодняшнее бессрочное разрешение** и не продление A/B задним числом.
2. Долгий grant, техническое окно дочернего schedule и горизонт прогноза — три разные вещи. Можно иметь revocable grant, суточные дочерние schedules и rolling forecast на 180 дней. Не надо резервировать 180 дней ещё не разрешённых admissions как уже принятый 72h tail.
3. Для данной поставки default — сохранение уже взведённого B и takeover после него. Не подменять его таймер новым manager без отдельного согласованного handover.
4. «Месяцы эксплуатации» требуют не только autorenew, но и достаточных backup/retention. I3 должна явно назвать и проверить эту зависимость, а не пройти короткие windows до неизбежного заполнения диска.

### 0.2. Источники и приоритет

- **[O]** Последняя отбивка владельца: A работает; B зарегистрирована, авторизована и взведена persistent timer. Это reported runtime, не новый live readback Project Chat.
- **[P]** Приложенный `SMIAL_Managed_Collection_Operability_PRD_SSD_V1_2026-10-13 (1).md`; его Git-копия: `docs/evidence/smial_managed_collection_i1_v1/source-contract.md`. Цели, исходные I2/I3/I4/I5 и общая policy сохранены; изменение срока grant явно описано выше.
- **[G]** Git design anchor: `07c81a99f2d0f385df66de2e1a5254e224c6b3b3`, проверен 14.10.2026. `AGENTS.md` → semantic routes → exact owners. Он новее reported deployed SHA; новый main сам по себе не требует deploy.
- **[E]** Первичные технические источники в §17. Ни они, ни Git не доказывают live host health.

При старте executor перепроверяет relevant current Git и фактическое состояние. Не перечитывает весь чат, не ищет «самую новую задачу» и не создаёт параллельную систему истины. Этот файл сохраняется как один source-contract; не дублировать его отдельными PRD, SSD, task-plan и списком из сотен пунктов с тем же содержимым.

## 1. Контрольная точка: что уже сделано

### 1.1. Reported production, перепроверить узко

| Объект | Последний подтверждённый в отбивках статус / pin |
|---|---|
| Deployed | `94b391d658b52035ae88e2da05f1ea25ff17b0f8`, merge #400; source→SEARCH→publication после deploy принят |
| Shared account | `JUPITER-MANAGED-ACCOUNT-1`, MANAGED; 1200 calls/day, 1200 modeled credits/day, 2 000 000 cumulative; история сохранена |
| A | `ACT-4744D4017AC4B196`, schedule `4744d4017ac4b19625c5ee11ce4e20fdd4b36c6744f8c0889467052e2a6ef23c` |
| A intake / authority expiry | До `2026-10-17T00:00:00Z`; grant до `2026-10-20T01:05:00Z` |
| A authority | `c2c937b4462b28f45a423bb42d702c3052f9a996bf4d399e58168d6e378db038` |
| A storage envelope | `fa6450ba0fd9da64fa3792c8b5de0c22aacf948589f7e9b1e8e78ae236b8dcad` |
| Frozen protection | `f70a7f2d82b27bd39b1affbb72be339401bb0d223275965ce68df795112ec3ef` |
| B | `ACT-A26CF9B0815A36F2`, schedule `a26cf9b0815a36f2f67589b7c1db5da429d617ab048ff9676ad7df64ad2cc063` |
| B interval | `2026-10-17T00:15:00Z` → `2026-10-18T00:00:00Z`; максимум 99 admissions; не касается admission day 18.10 |
| B authority / expiry | Receipt prefix `78acdcb7…` — полный hash получить из runtime; expiry `2026-10-21T01:05:00Z` |
| B launch | `factory-i3-b-activate.service/.timer`; 17.10 `00:20:30Z` и `00:50:30Z`; persistent, включён; ожидаемый dry-run BEFORE_START |
| B operational artifacts | VPS `local/factory_v1/commissioning_20261014_b/`; исходный local locator `local/i3_b_readiness_v1/B_READINESS_PACKET.md` — проверить, не предполагать одинаковые относительные roots |
| Corpus C1+C2 | 47 episodes, 6533 episode-point pairs; exact replay, cold restore и независимая Drive-копия приняты |
| I1 V2 | Producer capture V2 установлен; C1/C2 повторно не импортировать ради этой задачи |
| Legacy renewal | `factory-same-envelope-renewal.timer` выключен; не включать неизменённым |
| Backup/I2 | SQLite около 5.17 GB; reported ~94% объёма в крупных legacy tables; sample compression ~6× zlib / 13.6× lzma, **не whole-backup production proof** |

A и B — действующие обязательства, а не disposable fixtures. Reported B `ARMED` не равен будущему `ACTIVE`; граница 17 октября ещё должна реально пройти.

### 1.2. Проверено в Git, что влияет на дизайн

- `same_envelope_renewal.py` переводит документ через legacy `schedule_from_observation_request`, затем `_phrase()`/authorize/rollover. Это не готовый managed episode путь и не основание для автоматической подписи новых прав. [G2]
- `activate_schedule()` требует собственную authority и storage commissioning; late successor допускается после доказанного NON_ADMITTING DRAINING, с запретом backdating. Запись activation и ResearchEvent — отдельные шаги, требующие восстановления после crash. [G3]
- `_tick_candidates_as_of()` выбирает DRAINING перед ACTIVE, но CLI перечисляет activations и может завершить весь tick на отказе одной из них. Наличие multi-activation loop не равно доказанной долгой эксплуатации. [G4]
- Дневная cohort не может содержать несколько `(schedule, activation)` scopes. Селектор проверяет это глобально и сейчас отказывает всей выдаче при фрагментации. [G5]
- Shared budget суммирует прежние per-activation counter rows; они остаются authoritative debit history. I2 не вправе удалить их вместе с legacy payload. [G6]
- Storage V1 принимает только `factory_storage_gate=PASS` и exact root identity/hash. TARGET=40 GiB, HARD=50 GiB; структурная проверка ссылок не аутентифицирует backup/owner evidence. [G7]
- Pressure в episode tick закрывает intake в DRAINING. Повторный `resume` такой activation не является поддержанной штатной компенсацией. [G8]
- Watch, owner pulse, Telegram и heartbeat hook уже существуют; здоровье snapshot не доказывает доставку сообщения или внешний контроль смерти VPS. [G9]

### 1.3. Исходная нагрузка и научная семантика

Сохраняются: Jupiter category sources, период nomination 900s, stable sampling seed/lineage, weekly mint dedup, один active episode/mint; baseline100/day и rolling100, active cap400, batch≤100, pace≥3s, per-tick20, общие 1200/1200/2000000, zero cash, no retry/fallback провайдерских наблюдений. 139 точек: E0 + 72 через5min до6h +66 почасовых до72h. Holders≥50, liquidity USD5000…1000000, price>0; protection/asset exclusions остаются прежними.

Фильтры, seed, T0/availability, плотность наблюдений и missingness нельзя менять ради того, чтобы прошла capacity. Объект науки — все committed admissions, а не только выжившие или успешно доставленные.

## 2. Product acceptance: что изменится для Петра

### 2.1. Единственный нормальный owner journey

> «Продолжай текущий сбор до моей отмены. Те же100/day и ограничения. Сам обслуживай разрешённые переходы; при реальной проблеме напиши, что произошло, что сохранилось и что нужно от меня».

После будущего exact commissioning:

- система сама создаёт внутренние windows, связывает их с grant и включает допустимый intake;
- reboot, закрытый ПК, законченный чат и смена coding agent не требуют действий;
- обычное окончание child schedule — внутреннее событие, не owner gate;
- просьба «500/day» даёт обоснованный plan, а не PR на замену литерала;
- «верни100» даёт prospective rollback/drain, а не откат базы;
- сообщения только при material incident/recovery и реальном исчерпании права/ресурса; согласованный digest опционален;
- «забери готовое» остаётся явным действием на ПК через существующий delivery path. Наука автоматически не запускается.

### 2.2. Не путать четыре результата

| Результат | Достаточное evidence |
|---|---|
| `CODE_READY_RUNTIME_PENDING` | Реализация и offline vertical proof, review/CI; live ещё не применён |
| `MANAGED_CONTINUITY_LIVE_PROVEN` | Отдельно разрешённое применение; штатные реальные переходы, tail и публикации; понятные инциденты/восстановление |
| `MONTHS_RUNWAY_SUPPORTED` | Дополнительно измеренная retention/backup модель и реальный обычный backup; нет заведомо близкого заполнения storage. Это прогноз, не прошедшие полгода |
| Вся программа / scientific fit | I2/I4/I5 выполнены в своих scopes. I3 и timer не доказывают alpha |

**DoD I3 не допускает** ответа «создан ещё один one-shot для C» или «автопродление умеет запускаться, но раз в сутки Пётр создаёт storage receipt». Недостаточный storage может честно блокировать новое физическое потребление, но не возвращает ручную регистрацию как нормальный UX.

## 3. Scope и свобода реализации

### Входит

Единый runtime profile/grant/apply; производная child authority через существующий owner; auto continuity и cohort ownership; plan/apply/rollback/stop; автоматический capacity/backup gate; bounded recovery; совместимость с A/B и V1; alerts необходимой полноты; semantic propagation; проверка production входа и последующий OPERATE packet.

Для полного количественного контракта — снятие искусственных100/400 у **нового managed пути**, с проверяемой capacity вместо неограниченного допуска. Физические/протокольные пределы, например route batch100, не ослаблять. Первое live применение остаётся100/day.

### Не входит автоматически

Полный I2 retirement/reclaim, новый архивный backend, миграция всей science history, новый data lake, отдельный Telegram bot/UI, live cap increase, покупка тарифа/новые ключи, trading, Forge looks, массовый deploy unrelated функциональности. Неподтверждённые часы/денежные права не выводить из эмоций владельца.

### Выбор архитектуры

1. **Выбрано:** короткие frozen child windows + один durable profile/grant и reconciliation в существующем execution lane. Небольшой новый модуль управляющей логики допустим; второй сервис-провайдер нет.
2. Изменять stops/expiry старой activation — отвергнуто: разрушает frozen identity и reproducibility.
3. Cron, генерирующий human phrase для каждого B/C — отвергнуто: обход authority и новая ручная/непроверенная state machine.
4. Отдельный management oneshot допустим **только** если измеренный controller-time иначе нарушает deadline collector. Он не вызывает Jupiter, использует тот же lease/owners и не становится вторым collector. По умолчанию — интеграция с existing tick.

Executor самостоятельно выбирает helpers/SQL/индексы/форму CLI, разумный batching, конкретные fixture и механизмы recovery. Каждое решение должно сохранять outcomes и authoritative ownership. Новый слой оправдан измеренным выигрышем, не будущей симметрией.

## 4. Profile, grant и одна операция владельца

### 4.1. Минимум durable state

Разместить в существующем operational owner, не в Git-runtime:

- profile revisions + указатель действующей revision;
- exact owner-approved parent grant и его revoke/expiry;
- append-only command/transition intent с идемпотентным ключом;
- active/current-day intake claim и linkage child→parent;
- маленькие capacity/incident readouts, если существующие поля/receipts не покрывают их.

Не копировать existing accounting rows, не создавать второй truth ledger расхода. Не дублировать source observations и большие response bodies в profile/events. Authority принадлежит одному расширенному owner; operational projection не выдаёт право сама.

### 4.2. Логическая схема, имена можно адаптировать

```yaml
kind: managed-episode-collection
version: 1
revision: 1
previous_revision: null
collection_lineage_id: <derived from existing lineage, not a new sampling identity>
desired_state: RUN
validity:
  mode: UNTIL_REVOKED                 # либо UNTIL_DATE с точным intake_until
  planning_horizon_days: 180          # прогноз, не expiry
semantics:
  fingerprint: <source/filter/grid/seed/protection-policy meaning>
  legacy_compatibility: <explicit managed adapter version>
limits:
  admissions_per_utc_day: 100
  rolling_24h_admissions: 100
  active_episode_cap: 400
  shared_account_scope: JUPITER-MANAGED-ACCOUNT-1
  provider_calls_per_utc_day: 1200
  modeled_credits_per_utc_day: 1200
  cumulative_calls: 2000000
  cash_usd_max: 0
resource_policy:
  target_bytes: 42949672960
  hard_bytes: 53687091200
  physical_floor_and_tail_model: <bound existing model and measured evidence>
  target_acceptance: null             # отдельная exact принятия риска, не force
  retention_policy_ref: <existing approved owner>
  backup_health_policy_ref: <existing owner + measured cadence/RPO>
continuation:
  automatic: true
  child_boundary: UTC_ADMISSION_DAY
  bootstrap_not_before: 2026-10-18T00:00:00Z
  protected_bridge: ACT-A26CF9B0815A36F2
recovery:
  transient_retry_budget: <bounded non-provider operations>
  resume_after_temporary_hold: SAME_SEMANTICS_ONLY
  resource_profile_rollback: LAST_APPROVED_SAFE_REVISION
notifications:
  incidents_and_recovery: true
  healthy_digest: <existing preference until explicitly changed>
```

Это **schema sketch**, не YAML для production. Полные byte/role/grant/evidence bindings создаёт actual CLI. `UNTIL_REVOKED` не продлевает route entitlement или оплаченный сервис; исчезнувший credential/403/истёкшее внешнее право остаются настоящими отказами. Cumulative2M также не обнуляется: его исчерпание — реальное owner budget decision, не техническая дата.

### 4.3. Изменения срока и полномочий

Новый subtype standing grant принимает exact policy/semantics и право выпускать ограниченные children. Human approval относится к профилю и покрывает **все перечисленные технические действия** внутри него, включая автоматическое формирование storage evidence, register, derivative authorization, activate и разрешённый recovery.

Дочерний grant содержит parent id/revision, policy fingerprint, child schedule/время, approved routes/лимиты, expiry не раньше конца собственного tail и доказательство subset-of-parent. Генерация ожидаемой строки `_phrase()` не является owner consent. Не применять такой shortcut к V1 human authorization.

Finite parent: последний новый admission строго до `intake_until`; до его принятия обеспечено заранее разрешённое право дописать tail. Revocation по умолчанию прекращает **новый intake**, а не делает уже выданное tail-разрешение невалидным. Отдельный emergency revoke-all возможен только как явный сильный scope; физически отозванный API-ключ может оборвать и tail — это инцидент, не скрытый backfill.

Изменение профиля при том же source meaning не требует нового научного look, но меняет будущую scientific population и должно быть явно видно в release/census. Никаких owner подписей на каждую сгенерированную JSON-версию.

### 4.4. CLI и реальные authority boundaries

Один discoverable набор команд, предпочтительно под `observation_schedule.py`:

```text
collection-status
collection-plan <desired changes>
collection-apply --proposal <id/hash> --expected-revision <N>
collection-reconcile --once
collection-stop-intake
collection-rollback --to-revision <N> --expected-revision <M>
```

Названия — рекомендуемый интерфейс. `status/plan` используют безопасный read-only binding: не создают БД/таблицы/ResearchEvents, не добывают ключ, не делают API/Drive/Telegram calls. Отсутствующий OPS_STORE — SOURCE_MISSING, не новая пустая «здоровая» система.

При одобрении одного exact profile proposal ребёнок не запрашивает ещё три gates. Отдельные **первоначальные** merge, deploy/settings и live grant сохраняются; подготовить один согласованный OPERATE packet с exact artifact/scope/recovery. Допустимые его действия можно разрешить одним осмысленным owner approval, если current authority policy это поддерживает; не дробить простой supported apply на approval каждого файла. В этом DESIGN/EXECUTE scope live permission ещё нет.

## 5. Автоматическое продолжение: ключевой vertical path

### 5.1. Рекомендуемая единица управления

Default child — один UTC admission day. Внутри дня максимум одна фактически принявшая admissions пара `(schedule, activation)` на lineage/collection. Каждый child заканчивает intake **на UTC-полуночи**, а его tail продолжает исполняться. Несколько дней в одном child допустимы только если это проще и не создаёт избыточных materialized future obligations; смысл непрерывного режима не зависит от длины child.

Это техническое окно, не ограничение родительского grant. В переходе B→managed: B владеет17.10; первый managed child владеет18.10. Владение cohort вычисляется existing canonical cohort resolver, не новым форматом ID.

### 5.2. Обработка одного tick

Рекомендуемая схема, не требование конкретных функций:

```python
# Logical flow: all operations bounded; provider transport remains existing.
ctx = load_verified_runtime_context_readonly()
service_due_committed_obligations(ctx)       # no freeze of A-tail while managing
if manager_step_is_due(ctx):
    plan = reconcile_current_control_state(ctx)
    if plan.can_progress:
        apply_one_idempotent_transition_step_under_existing_fence(plan)
service_due_committed_obligations_with_fresh_clock(ctx)
if verified_current_intake_is_permitted(ctx):
    admit_via_existing_nomination_owner(ctx)
publish_pending_results_and_operability(ctx)
```

Внутри одного normal tick нет heavy backup, remote verification, полной истории, ожидания часами и sleep до завтра. Если step не помещается в remaining deadline budget — сохранить intent и продолжить следующим tick. Writer lease/CAS короткие; не удерживать SQL transaction или control lock во время HTTP, LLM, upload и внешнего verifier.

Default selection больше не обрывает все независимые tails из-за blocked optional successor. Shared-account/integrity corruption, действительно общая для всех, блокирует соответствующие calls; проблема отдельного child не должна ни спрятаться, ни выдать остальные scopes healthy. Отчёт PARTIAL показывает кто продолжает работать.

### 5.3. Binding и crash-safe transition

Один unique transition key, например `(collection_lineage, UTC_day)` плюс ссылка на **одну** выбранную profile revision. Не позволять двум revision создать двух владельцев дня. Пересмотр proposal до первого admission — отдельное idempotent supersession событие; после первого admission владельца дня не заменять.

Recommended progression:

`PLANNED → REGISTERED → AUTHORIZED_DERIVED → ACTIVATED → INTAKE_COMPLETE → TAIL_COMPLETE`.

Имена существующих terminal использовать, где возможно. Дополнительные persisted состояния нужны только для реальных разрывов между durable writes; не universal workflow engine.

После каждого process kill повтор должен:

1. Найти сохранённый intent по ключу, не придумать новые часы/SHA.
2. Прочитать authoritative OPS/authority/ResearchEvent, определить уже committed effects.
3. Дописать недостающую publication/event из **сохранённых точных bytes** через existing idempotent owner.
4. Не запросить источник заново и не записать второй admission/debit.

Особенно проверить crash после OPS activation commit до append ResearchEvent: существующий `ACTIVATE_REPLAY` сам по себе не гарантирует восстановление missing event. Нужно исправить owning recovery path, а не бесконечно получать «уже активно» при отказе следующего tick.

### 5.4. Время, потерянные запуски и отсутствие backdating

Не использовать сломанный ранний rollover как prerequisite. Начальная реализация может использовать проверенный natural DRAINING + late successor. Child proposal финализируется в допустимое forward время после доступности closure proof; никакого утверждения, что он работал ночью, если машина была выключена.

Управляющий reconcile должен устранять причину ежедневного фиксированного20-минутного разрыва: обычно он продолжает на ближайшем доступном штатном tick. Обязательство — измеренный интервал и отсутствие скрытой дыры; нулевую latency не обещать. При нормальной нагрузке целевой bridge overhead — в пределах одного nomination round и без целого потерянного UTC-дня. Более строгую границу executor выводит из actual dispatch/lease времени.

После нескольких пропущенных дней не создавать фиктивные пустые activations за каждый день и не выполнять прошлые provider requests. Записать точный operation gap, завершить missed historical slots typed, восстановить ещё доступные obligations и открыть законный будущий/current-day intake в разрешённых рамках.

Clock rollback, несинхронизированные UTC или скачок через boundary не позволяют задним числом менять receipt/admission. Таймауты — по monotonic clock; event/admission/grant — по проверенным UTC. Host clock uncertainty блокирует новые temporal commitments до восстановления; уже известные data bytes не терять.

### 5.5. Временный HOLD против окончательного DRAIN

Критическая новая развилка: краткий writer busy, TEMP_NETWORK, PACE_WAIT или короткая пауза service **не должны** необратимо закрывать весь child и делать новый fragment того же дня.

- Пока нет permanent stop и scientific meaning тот же, managed intake может быть временно HELD в рамках того же child. Восстановление — в том же scope, с сохранением missed rounds; без замены SHA.
- Настоящее сокращение нагрузки, owner stop, отозванный intake grant или исчерпание physical reserve используют native terminal stop-intake/drain. Уже DRAINING не «воскрешать».
- После terminal stop в занятом UTC-дне новый child с другим profile ждёт ближайшей допустимой границы. Система сама ставит pending continuation; Пётр не регистрирует новый schedule.
- После полной утраты store/root — recovery, а не новый пустой child, даже если календарь новый.

## 6. Совместные budgets, capacity и качественное масштабирование

### 6.1. Один реальный account budget

Переиспользовать принятый `observation_account_budget.py` и current counters. Все current/complete/paused historical members остаются в cumulative sum. Новая lineage, child, policy revision, день, reboot или alias не обнуляют расход. External callers того же ключа остаются UNKNOWN, пока нет отдельного доказательства; не притворяться полным учётом провайдера.

Каждый реальный send проходит existing reservation-before-send, свежий shared gate и один pacing lane. AMBIGUOUS outcomes сохраняют debit. Daily и lifetime reservation atomic; existing midnight semantics сохраняются. Provider failure ≠ разрешение повторить старый point.

### 6.2. Не съедать бюджет хвоста optional intake

Порядок DRAINING-first полезен, но сам по себе не резервирует **будущий** tail. Для очередного admission и child plan проверить обязательства по UTC-дням: already spent + pending committed call groups + prospective tail + необходимые nominations. Cumulative allowance должен покрывать обязательства на весь хвост, не только сегодняшний `remaining>=200`.

Модель использует native assigned times, группировку batch/activation, credits и неизвестные исходы. Не складывать grant A1200 + B1200 в2400 и не считать future call debt уже потраченным; сохранённое намерение и spend — разные поля.

Если текущий реальный quota/credential outage всё равно не позволяет исполнить хвост, система сохраняет typed gaps и incident, не нарушает внешний лимит «ради полноты». При новом plan такая ситуация должна предупреждаться раньше принятия дополнительных admissions.

### 6.3. Capacity — по совместной форме работы

У суточных children может быть3–4 draining scopes плюс intake; число provider batches зависит от того, объединяет ли existing transport scopes. Нельзя брать доказательство «до4 batches» от одной activation и молча переносить его на4 activations. Проверить реальные assigned-time groups, serial prelude/recovery cost, idle gap и суммарные calls всего default path.

Начать с existing dispatcher. Если он проходит measured100/day A/B/C/D tail, сохранить. Если earliest-deadline нарушение реально возникает, исправить existing dispatch selection, а не запустить второй provider worker. Global work ordering — обязательства по deadline прежде optional nomination; объединение разных scopes в один HTTP batch не обязательно и требует отдельного корректного debit/response ownership.

### 6.4. Количественные изменения без PR

В новом managed interface запрос принимает любое representable положительное количество; admission зависит от фактического capacity и разрешённых budgets, не от исторического литерала100. Сохранить старую V1-схему/validator, добавить один явно versioned managed adapter и propagated consumers. Не править прежний release hash или считать старый fixture доказательством нового range.

Полный путь проверки:

`request → semantic compatibility → native workload geometry → resource/provider evidence → exact proposal → owner apply → next supported boundary → measured live readback`.

Положительное утверждение за пределами измеренного диапазона требует нового **операционного измерения**. Новый code нужен только при недостаточности алгоритма/протокола. «В allowlist только100» не является окончательным verdict managed plan.

Для sanity-check, не production forecast:

| D admissions/day | Примерно active=3D | Post-T0 points/day=138D | Идеальный lower bound calls/day: 288+ceil(138D/100) |
|---:|---:|---:|---:|
|100|300|13800|426|
|200|600|27600|564|
|500|1500|69000|978|
|1000|3000|138000|1668|
|2000|6000|276000|3048|

Lower bound не учитывает незаполненные/раздельные batches, timing, scope и overhead. Например60 send при pace3s требуют минимум177s между первым/последним — не помещаются в60s dispatch window. Точный отказ должен назвать эту ось или daily budget, а не просто «слишком много». Volume/grid/latency менять скрытно нельзя.

## 7. Resource policy: без вымышленных STOP и без заполненного диска

### 7.1. Три независимые проверки

1. **Semantics/integrity/protection/authority:** не override.
2. **Физическая исполнимость:** free space, нужный pending tail, CPU/RAM/IO, inodes, actual deadlines и route/entitlement. Неподтверждённое critical condition запрещает новый intake, не все независимые reads.
3. **Owner policy:** TARGET, HARD, quantitative budgets. TARGET допускает точную risk acceptance; действующий HARD остаётся hard. Его explicit пересмотр — отдельный plan/apply с проверкой физики, не `--force`.

V1 storage envelope остаётся читаемым и неизменным. Новый versioned managed decision может хранить:

```text
storage_health = DEGRADED_TARGET
hard_constraints = PASS
physical_tail_reserve = PASS
target_acceptance = VALID_FOR_THIS_PROFILE_AND_RANGE
decision = ALLOW_WITH_ACCEPTED_TARGET_RISK
```

Не присваивать `factory_storage_gate=PASS` ради compatibility. Единственная семантика в validator/runtime/CLI/readout; без bool bypass.

### 7.2. Fresh evidence без ежедневной подписи владельца

Evidence относится к environment/dependency/workload fingerprint, а не ко всякому Git SHA. Unrelated docs change не требует нового rehearsal. Изменения batching/schema/root/account/retention/binary path, способные повлиять на outcome, требуют scoped revalidation.

Managed controller сам формирует производные commissioning receipts из существующих проверенных sources. Не верифицирует каждый tick гигабайты по сети: background backup/archive owners публикуют trusted timestamp/hash/coverage; hot path читает компактный receipt с ограниченным возрастом. Перед авторизацией child проверяются реальные evidence refs, не только формат64hex и не строка `UNKNOWN` в разрешающем поле.

Плановый timer и self-hash не доказывают remote content или восстановимость. Политику свежести нужно выразить измеренной cadence/duration/RPO и источником receipt. Не требовать «remote checkpoint новее последнего debit» от непрерывно пишущей системы. Начальный ориентир30h при daily checkpoint берётся из reported B guard, но вводится только как явно одобренная operational policy, не универсальный закон.

Stale backup сначала даёт ограниченное ожидание/инцидент в пределах уже принятого риска; если safety margin/максимальный RPO исчерпаны — закрыть новые admissions, продолжить допустимый tail, не delete. После восстановления зависимость снимается автоматически в законной границе и той же согласованной семантике.

### 7.3. Прогноз на месяцы

По каждому реальному filesystem:

`peak(t) = непересекающийся resident + удерживаемые новые bytes(t) + фактически одновременные transient peaks + uncertainty reserve`.

Отдельно: future pending commitments относительно **current free space**. Не двойной учёт tail как уже resident и ещё раз как расход; не считать ПК дополнительной копией на VPS; не суммировать несовместимые во времени maxima.

Rolling forecast должен видеть finite HOT/COLD retention, backup generation chains, новые2–4 scopes хвоста, metadata/индексы, file count, upload/catch-up time и shared calls. Грант до отмены не означает бесконечное хранение всех raw в HOT.

Reported I2 ratio — предварительное основание, не экономия в production модели. Пока I2 не применена, экономия=0. Если текущие receipts показывают близкое exhaustion, controller показывает дату/интервал и один конкретный минимальный ресурсный action, а не выпускает сотни «PASS24h» до аварии.

## 8. I2-зависимость и минимальная долговременная эксплуатация

**I3 без приемлемого backup footprint не объявляется готовой на месяцы.** Это не повод отложить managed code до полного compactor; код и физическая устойчивость проверяются как разные результаты с явной связью.

Первый обязательный reconciliation/output I3 показывает:

- пять метрик parent I2: resident HOT, новые полезные bytes/day, upload/day, remote retained bytes, peak transient;
- фактический runway без ещё не выполненного cleanup;
- один рекомендуемый I2 action, если runway не покрывает эксплуатационный горизонт;
- точный budget/semantic boundary, который после I2 снимается повторным измерением **без нового I3 PR**.

Порядок работ при bottleneck:

1. Довести shared policy/continuity и offline vertical acceptance.
2. Если ресурс уже не допускает meaningful startup, выполнить ближайший независимо проверяемый I2 упаковочный этап через существующего owner: один consistent snapshot, modest DEFLATE, reuse immutable archive на retry. Из parent плана можно сформировать узкий implementation scope в этом же delivery, **если это materially сокращает путь и не превращает атом в большой compactor**. Иначе передать один exact I2 next action, а не suffix ремонты manager.
3. Полный legacy retirement/reclaim — parent I2. Разрушительный APPLY отдельно по exact affected scope и verified rollback. Нельзя просто удалить `call_ledger` целиком: новые episode calls тоже могут жить там.
4. Во время исходного I3 EXECUTE production backup/retention не меняются без разрешения.

Для legacy сохраняются quota/tickets, authority, policy revisions, shared-account members и **компактные counters**, current/tail/UNKNOWN attempt/publication/export deps. Статусы PAUSED/ABORTED не превращать в COMPLETE для уборки. Удалять ненужные bodies, а не смысл и debit history.

Если только compressed packaging уже даёт достаточный runway — это usable improvement, но parent I2 retirement остаётся открытым, не исчезает из отчёта. Нельзя назвать whole-file replacement настоящей page delta.

## 9. Отказы и recovery: не только happy path

| Ситуация | Требуемое действие | Запрещено |
|---|---|---|
| Процесс умер до/после register/authorize/activate/event append | Reconcile exact persisted intent; продолжить оставшийся шаг | Новый child SHA от текущих часов при каждом retry |
| Tick/lease busy | Короткий bounded defer; очередной штатный запуск | Многоминутный sleep под writer fence |
| Неопределённый HTTP send/result | Existing conservative debit и typed unknown; следующий point по своей сетке | Повторить старый call «пока получится» |
| Reboot до boundary | После загрузки current-time reconcile, actual closure/authority check | Backfill missed admissions или вера в один timer timestamp |
| Reboot после activation до первой publication | Восстановить binding/event/outbox, обслужить ещё доступные due | Создать второй intake-owner |
| Shared budget исчерпан | Нет нового расхода, reason+reset time; остановить optional intake до нехватки для tail | Смена activation/account id или refund unknown |
| Низкий physical reserve | Stop new intake/лишний maintenance, сохранить данные и lawful tail; incident | Автоматически удалить protected/source deps |
| TARGET exceeded, acceptance valid | Продолжить в разрешённом диапазоне с честным DEGRADED | Врать PASS или каждый день запрашивать новое approval |
| Некорректный profile/grant/child linkage | Block dependent new intake, показать exact conflict | Молчаливый переход в unmanaged legacy mode |
| Restore старой базы | RESTORE_RECONCILIATION_REQUIRED; rebind root и reconcile authority/debit before live use | Вернуть меньше потраченных calls и считать лимит свободным |
| Telegram outage | Durable dedup/outbox, bounded retries, не тормозить source; отдельная delivery health | Считать записанный JSON доставленным сообщением |
| Нет пригодных mint / no due | Честный idle по desired state и supply | Alert «всё сломалось» или auto-raise cap |
| Блокирован один child/fragment | Tails независимых scopes продолжаются; exact affected scope visible | Ни скрытый skip из науки, ни падение всего runtime без причины |
| Полностью потерян VPS | Existing off-host deadman либо HOST_LOSS_ALERT_UNPROVEN | Обещать, что умерший сервер сам пошлёт Telegram |

### 9.1. Restore и rollback

Обычный restart с сохранившейся SQLite — автоматический. Восстановление устаревшей копии/нового тома — иной риск: потерянный промежуток расхода, newer revoke/profile, root identity и pending writes. Поддержанный restore обязательно ставит guard; включение нового intake запрещено до reconciliation. Автоматический restore допустим только при заранее одобренном точном recovery contract, иначе одно actionable owner сообщение.

Не требовать distributed zero-RPO для pet. Требовать честный RPO, последнее проверенное remote state и fail-closed расход после неопределённого восстановления. Сырые timestamps и receipt hashes не восстанавливают сами по себе потерянные дебиты.

Operational rollback profile = новая revision прежних settings, долг и новые episodes сохраняются. После managed commissioning release tooling должен отказать несовместимому binary/schema downgrade либо использовать заранее проверенный совместимый rollback. Откат 100←500 не делает active≤400 мгновенно; `DRAINING_TO_LIMIT` — нормальное состояние, а не удаление jobs.

### 9.2. Уведомления

Минимум: incident + recovery + one-shot warning о реальном budget/expiry/runway risk. Dedup по причине/collection/состоянию, escalation только при изменении воздействия или согласованном интервале. Не присылать success на каждого ребёнка.

Сообщение: «Новые admissions остановлены из-за X; N уже принятых продолжают наблюдаться; автоматическое действие Y; следующий шаг Z; as-of ...». Числа актуальные; не пачка внутренних enum.

`desired RUN && expected intake owner missing` — incident, даже если timer/service alive. Watch должен замечать stale controller state, отсутствие нужного timer, source/publication lag и невозможность доставки сообщений; новые metadata reads bounded. Для приемки после разрешения нужен настоящий Telegram incident/recovery test с пометкой TEST и readback transport delivery, без намеренного повреждения текущего collector.

Внешний watcher — не обязательная новая подписка. Сначала проверить существующий hook/receiver. Если receiver отсутствует, честно ограничить гарантию и вынести один конкретный commissioning choice, не ставить «HOST_DOWN_PROTECTED» из local heartbeat config.

## 10. Bootstrap поверх уже взведённого B

**Default:** не менять A/B и не отменять одноразовый B timer во время разработки. Управляемый takeover начинается **после B**: earliest18.10 `00:00Z`/03:00 МСК, с actual late start после доказанной closure. B receipt, original grants, day ownership и tail остаются как есть.

В initial managed proposal явно записать protected bridge B, handover-not-before, ожидаемые pins и действующую standalone timer identity. При boot/reconcile до этой границы manager ничего конкурирующего не создаёт. Если B не стартовала, manager не заявляет, что она запущена; видит incident. Принять управление раньше default можно только отдельным exact takeover scope с guard против второго владельца17.10.

После commissioning текущий generator/manager и standalone timer не должны одновременно производить новые competing children. B-backstop может дать идемпотентный replay, но удаление unit выполнять только после подтверждённого исхода B и readback принятого ownership; не убрать последнюю страховку до работоспособности replacement. Unit artifacts удалить отдельно разрешённым узким operational cleanup, не Git PR на дату.

Если deploy происходит после18.10, не воспроизводить старый календарь: прочитать действующие admissions/cohort owner и продолжить только forward. Наличие уже registered/authed child не равно занятому admission day, но его intent нужно reconcile/supersede явно, не создавать ambiguities.

## 11. Sizing, схемы и agent-context propagation

### 11.1. Bounded routine path

Работа normal tick должна масштабироваться с current/near-future obligations, не со всеми payload за100 недель. Использовать existing indexed queries; bounded projection active/draining, current day claim и next pending command. Сумма компактных исторических counters через индекс допустима, пока measured budget проходит; отдельный materialized total/второй ledger заранее не вводить.

Не писать одинаковое событие на каждый15s tick. Persist изменения control/incident/usage через их owners; routine no-op дешевый и не раздувает5-GB store дальше. Нельзя держать reader transaction часами на backup/status и блокировать WAL checkpoints. Physical SQLite version/journal settings и build входят в environment fingerprint; не менять их автоматически.

Steady no-op reconciliation ориентировочно≤1s на целевом VPS; hard scheduling allowance согласовать с существующим≤5s local prelude и60s dispatch. При превышении — defer heavyweight work/offline plan, не расширять observation window. Размер и команды evidence выбирать пропорционально; synthetic100-week history моделирует metadata, не миллионы ненужных raw HTTP bodies.

### 11.2. Compatibility closure

Все consumers нового managed schedule и authority должны распознавать subtype через единый decoder/validator. Проверить compile/register/lifecycle/default+explicit tick, row resolver, closure/export/seal/import, corpus labels, Forge metadata input и status/recovery. Зелёный managed producer при неподдержанном exporter — FAIL.

Old V1 human grants, schedule hashes, C1/C2 release source и labels не переинтерпретировать. Поле provenance managed child добавляется prospective/versioned. Не объявлять разные SHA времени разных child несовместимой clock semantics, если point-grid/availability meaning те же; и наоборот, одинаковое имя не маскирует другой grid.

Durable update в том же атоме: owning collection/authority/storage contracts; CLI/help; operator recovery и migration; schemas; current Catalog routes/generated projections. Известные ложные next-action `REGISTER_AUTHORIZE_ACTIVATE` должны стать «inspect managed state/automatic retry/real owner limit» на managed пути. Старое поведение сохраняется для genuinely unmanaged legacy.

## 12. Достаточное доказательство внутри реализации

Не обязательны TDD, 100% coverage и новые файлы на каждую строку. Начать с existing episode harness, shared-budget tests, lifecycle/release proofs, watch scenarios. При необходимости расширить один набор fixtures. Новый durable regression оправдан именно непокрытым material failure.

### 12.1. Cheapest falsifier до больших переделок

На disposable store выполнить реальный CLI/owner flow:

`approved parent → native generated child → source stub + actual admission → natural close → generated next child → mixed tails → mature export → local verify/import`.

Одна fixed config, два+ UTC days, ни одной owner phrase внутри. Provider/network fake на границе, но admissions, authorization, counters, lifecycle, closure и exporter — настоящие owners. Если end-to-end требует per-child исключения, исправить source owner до написания «completed» evidence.

### 12.2. Матрица проверок

| Риск / сценарий | Oracle и ожидаемый результат |
|---|---|
| Happy path100/day через минимум5 UTC boundaries и weekly boundary | Один первоначальный grant; единственный intake owner; actual point/debit sets и cohort membership; tails от нескольких children |
| Old A/B bootstrap, B armed и later active | Нет competing child17.10; B неизменна; next lawful18.10; restart до/после B tick |
| Crash после каждого durable шага, включая OPS ACTIVE до ResearchEvent | Сохранённая identity/event дописана; no duplicate admission/authorization/debit; следующий штатный tick работает |
| Two reconcilers / apply и timer одновременно | CAS/lease/unique constraint определяет одного владельца; второй получает replay/defer, не второй child |
| Missed days / reboot / clock jump | Нет старых provider calls/fictional rows; forward resume; gap отражён; expired/revoked grant не возрождается |
| A exhausted, B new identity; midnight; lifetime; credits | Shared accounting сохраняет debits/reservations; independent raw SQL sum; grants не складываются |
| Long-tail pressure / lower cap | Сначала прекращается optional intake; принятый denominator неизменён; `DRAINING_TO_LIMIT`, не cap reset |
| Short HOLD recovery vs permanent drain | Same child resumes allowed temporary work; terminal stop не creates fragment внутри занятого дня |
| TARGET-only / HARD / free reserve / forged refs / stale acceptance | Только exact scoped TARGET acceptance допускает DEGRADED; остальные failures не маскируются |
| Runtime100→больше→rollback | Git fingerprint неизменён; positive supported capacity либо numerically correct refusal; old data unchanged |
| New managed child → V2 capture→seal/import→metadata preflight | Публикуемые данные доступны существующим consumers; no silent schema fallback; replay original C1/C2 по сохранённым pins |
| Backup stale/failed; root restore | Старый checkpoint не превращается в свежий; no reset spend/revocation; new intake gate с точной причиной |
| Telegram down / repeated same incident / recovery | Один durable incident; bounded retry; source не ждёт; транспортная доставка отдельно от JSON |
| Large old history, routine hot path | Реальные SQL plan/read counts/RSS/wall; нет всех5GBpayload на каждый тик, нет растущего event spam |
| Old timer / old binary after manager commissioned | Нет конкурирующего ownership; supported incompatible rollback отказывает до нарушения состояния |
| Finite grant и UNTIL_REVOKED | Expiry прекращает новый intake и сохраняет разрешённый tail; until-revoked не renews own budgets/entitlements |

Независимость oracle: expected timeline/sets считать отдельным маленьким расчётом или literal fixture, не вызовом той же helper-функции. Membership/counters читаются raw SQL; release bytes другим reader/process. Test-side ручное заполнение managed activation/grant/backup PASS вместо production владельцев не считается end-to-end.

### 12.3. Реалистичная нагрузка и историческая глубина

- Полноценная multi-scope geometry при100/day: all due groups/latency/time budgets; shared queue не ограничивать happy-path двумя scopes.
- Числа200/500/2000 пройти через plan с existing constraints: есть истинные отказы, не требование всех PASS.
- Time-advanced180d/100weeks — проверить rollover, expiry и bounded metadata. Это не soak180дней. History metadata можно увеличить отдельно, а full139-point trajectory проверить на достаточном малом контрольном наборе.
- Full-load, backpressure, long backup reader и writer contention — targeted scenario; с отсутствующим memory/time envelope вернуть численную границу, не фиктивный proof на сверхмощном CI.

## 13. Исполнение: три этапа, не серия новых задач

### Этап A — реализация и software gate

Самостоятельно materialize один canonical task contract из этого input; reuse принятый parent и code owners. Закрыть §§4–12, подготовить one-shot->managed migration, применимый rollout и explicit I2 dependency. Внутри безопасных code/fixture шагов не спрашивать owner на каждую идею.

First stop: exact-head review/CI/merge-readiness либо material blocker. Не делать отдельный PR на каждый error code, таблицу, timer или полученную цифру. При действительно независимом большом I2 fork указать WHY и outcome; не умалчивать scope и не проводить deletion через I3.

### Этап B — разрешённое применение

После guarded merge и post-merge readback — один prepared OPERATE packet:

- exact deploy artifact и compatible rollback; current A/B pins и standalone timer;
- additive schema/index/bootstrap rehearsal без giant lock на live tick;
- actual parent profile/grant limits, срок/UNTIL_REVOKED, I2 evidence/runway, target acceptance если нужна;
- parent-only approval; child register/authorization/activation идут самостоятельно;
- units installed/reboot semantics, restoration of previous armed units;
- настоящие source→publication и account/metadata readbacks;
- exact initial Telegram test и expected bounded operational message scope.

Разрешения на code install, runtime authority и destructive maintenance различимы; собрать их в понятный packet, чтобы не превращать один profile apply в Gate1/Gate2/Gate3 каждого child. Если current canonical boundary запрещает объединение, показать один конкретный остаток, а не отменять safety молча.

### Этап C — живая эксплуатационная приёмка

До первой реальной managed boundary — `LIVE_PENDING_FIRST_CUTOVER`, не DONE. После первого перехода проверить A/B tails, новый intake и source publication; после следующей UTC-границы подтвердить, что не потребовалось повторное разрешение и expiry/backup не стали новым ручным тупиком. Минимум один ordinary backup/archive cycle после применения и доступная следующая mature cohort входят в длительную приёмку, без повторения всех old imports.

Дальнейшая работа I2/I4/Forge не обязана ждать календарного live soak, если scope независим. Но `MONTHS_RUNWAY_SUPPORTED` без I2/retention evidence не ставить.

## 14. Время и порядок после B

**Начать EXECUTE сразу после получения этой постановки, 14 октября вечером. Не ждать17-го.** B уже страховка; проверка её фактического запуска17.10 остаётся readback, не условие начала разработки.

| Контрольная точка, МСК | Что требуется |
|---|---|
|15 октября, вечер / раньше при готовом candidate|Отбивка software результата или earliest material blocker; не новый общий план|
|16 октября, до12:00|Понятно, готов ли exact artifact и безопасный commissioning до B stop; если нет — назвать limitation и реальную альтернативу, не обещать чудо|
|17 октября03:20:30; резерв03:50:30|Работает уже взведённый B timer. Новый код не трогает его без approved handover|
|17 октября утром|Проверка B `ACTIVE`, shared membership, source→publication, хвост A; не ждать только наличия pulse|
|18 октября03:00|B intake закрывается; рекомендуемая первая managed takeover boundary, если code/runtime gates приняты|
|Следующая managed boundary + первый ordinary backup|Фактический результат автономности и longevity dependency; scopes acceptance разделены|

Это контрольные точки, не обещание сроков реализации. При позднем resume actual live state важнее старой даты. Если до18.10 mechanism не готов, заранее показать gap; не выдавать очередной вручную созданный C timer за исполнение I3 и не обходить gates из-за календаря.

После I3: I2 довести до устойчивого HOT/backup; I4 — late-PC archive/hydration/alerts closure; I5 — metadata readiness и один отдельно разрешённый научный результат. Уже готовые47 episodes не требуют ждать идеального6-месячного soak ради preflight. Не превращать операционку в вечный research без использования данных.

## 15. Отбивка, которую вернёт исполнитель

Один `OWNER_READOUT` + существующие machine receipts/locators, не набор конкурирующих сводок.

```text
I3 / EXACT_SCOPE / CODE_HEAD / DEPLOYED / OBSERVED_AT
OUTCOME: CODE_READY_RUNTIME_PENDING | LIVE_PENDING_* | MANAGED_CONTINUITY_LIVE_PROVEN | BLOCKED
Для Петра: что больше не нужно делать вручную (2–3 предложения).

PROFILE/AUTHORITY: intent; validity; approved/effective rate; budgets; true next owner boundary.
CONTINUITY: current intake; protected B; next day owner; outstanding tails; last actual transition.
EVIDENCE: native flow, exact fail cases, raw counter/set oracle, exporter/old replay, CI/review.
CAPACITY: measured/model; current+tail; 180d runway; limiting axis; I2 dependency, экономия only if applied.
RECOVERY: restart/partial effect result; restore limitation; compatible rollback.
ALERTS: incident/delivery/recovery scope; external host-loss coverage or UNKNOWN.
BURDEN: сколько approvals было на первый профиль, сколько на следующие children; remaining manual actions.
NEXT: один owner action либо одна конкретная зависимость.
RESUME: один path/command; что не повторять.
```

В завершённой операционной версии ожидаем формулировку: «Сбор работает в режиме X; новые окна создаются автоматически; повторное действие понадобится только при отмене/изменении режима либо настоящем ограничении Y». Не писать «вечная работа доказана».

## 16. Единственная стартовая команда

```text
SMIAL — EXECUTE I3_MANAGED_COLLECTION_CONTINUITY_V1.

Основание: приложенный I3_MANAGED_COLLECTION_CONTINUITY_V1_PRD_SSD.md.
Исполни его как одну цельную итерацию исходной программы; AGENTS → semantic owners → exact contract.

Outcome: один owner-approved managed режим; автоматические lawful children,
общие budgets, recovery/alerts и operational plan/apply/rollback без ручных B/C/D.
Parent desired RUN до отмены — новый явно реализованный и отдельно commissioned
контракт, не расширение существующих grants.

I1 и shared-account bridge не повторять. A и взведённый B не изменять;
default takeover после B, 18.10, либо фактически ближайшая законная граница.
Не создавать новый timer на каждую activation, не генерировать human approval
самому себе, не менять historical identities и scientific semantics.

Внутри итерации сам выбирай минимальную корректную архитектуру, код, tests и evidence.
Проверь production vertical path с несколькими UTC children, crashes, shared tail,
ресурсной деградацией и downstream V2 export. Новый тест только по material риску.
Достаточное proof включено в outcome; полный TDD/coverage не являются целью.

Сразу покажи и учитывай зависимость длительного runway от I2; savings до actual
APPLY не засчитывай. Full legacy cleanup/новый provider/наука вне этого scope.

Доведи до exact reviewed head, CI и machine merge-readiness. Подготовь один
согласованный последующий OPERATE packet с actual deployment/profile/authority,
B takeover, recovery/rollback и Telegram evidence.
Первый STOP — exact merge gate либо material blocker, не промежуточная техника.
Production deploy/APPLY, новый live grant, deletion, timers, provider expansion
и scientific looks без отдельного scope не выполнять.

Отбивка — §15, одно следующее owner action. Усилие: SOL_XHIGH.
```

## 17. Источники и границы уверенности

**[P]** Parent PRD+SSD V1 от13.10, приложен владельцем целиком. В частности §§2,3,5–7,9–12.
**[O]** Owner handbacks в этом треде, включая B REGISTERED/AUTHORIZED/ARMED и I1/shared-account live acceptance. Нового VPS readback Project Chat в этой design-сессии не делал; local receipts читает executor.

Все Git-ссылки ниже закреплены на design anchor `07c81a99f2d0f385df66de2e1a5254e224c6b3b3`, не на плавающем main:

- [G0: AGENTS / authority](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/AGENTS.md), [semantic map](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/docs/FACTORY_SEMANTIC_MAP.md), [time gates](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/control/active_time_gates.json).
- [G1: parent source-contract](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/docs/evidence/smial_managed_collection_i1_v1/source-contract.md).
- [G2: legacy renewal](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/same_envelope_renewal.py).
- [G3: lifecycle, authority, activation/replay](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/observation_schedule_lifecycle.py).
- [G4: public CLI/default tick](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/scripts/observation_schedule.py).
- [G5: release/cohort scopes](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/opportunity_episode_release.py).
- [G6: shared-account owner](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/observation_account_budget.py), [store](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/observation_schedule_store.py).
- [G7: storage owner](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/hot90_storage_admission.py).
- [G8: episode tick / sticky pressure drain](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/src/solana_alpha_lab/factory/opportunity_episode_tick.py), [operator](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md).
- [G9: unattended operability](https://github.com/lancerbeta/solana-alpha-lab/blob/07c81a99f2d0f385df66de2e1a5254e224c6b3b3/docs/operator/FACTORY_UNATTENDED_OPERABILITY.md).

Первичные внешние технические источники, проверены14.10.2026:

- [E1: systemd.timer, upstream manual source](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.timer.xml): timer не заменяет reconciliation; already-active service не запускается повторно; Persistent относится к OnCalendar и пропущенным trigger, не к восстановлению прикладных операций. Применимость конкретных опций сверять с установленным systemd.
- [E2: SQLite Online Backup API](https://www.sqlite.org/backup.html): consistent backup, bounded stepping и возможность перезапуска backup под concurrent writer. Один snapshot не делает несколько БД/файлов атомарной транзакцией.
- [E3: SQLite WAL](https://www.sqlite.org/wal.html), [isolation](https://www.sqlite.org/isolation.html): reader snapshots, один writer, WAL входит в persistent DB state. Не копировать голый live DB без корректного backup/recovery механизма.

**Дополнительная точечная проверка среды, не автоматический upgrade:** официальный WAL doc сообщает о WAL-reset bug, исправленном в3.51.3, с backports3.44.6/3.50.7. При выборе изменений checkpoint/concurrency executor фиксирует фактический `sqlite3.sqlite_version`/build и выясняет применимость, а не объявляет установленную БД повреждённой. Если действительно затронутая сборка и concurrency path — один material environment blocker; нельзя молча заменить runtime зависимость. [E3]

**Итоговая граница:** подготовлена архитектура и bounded execution input. Live grants, deployment, продолжение после B, retention и Telegram delivery в этой сессии не выполнялись. UNTIL_REVOKED, новые CLI/schema/recovery — предложенная реализация, не уже существующая capability.
