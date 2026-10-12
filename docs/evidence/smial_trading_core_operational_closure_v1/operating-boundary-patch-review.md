---
artifact_id: SMIAL_PR398_OPERATING_BOUNDARY_PATCH_V1
artifact_type: EXACT_HEAD_REVIEW_AND_EXECUTOR_HANDOFF
as_of: '2026-10-12'
repository: lancerbeta/solana-alpha-lab
pull_request: 398
reviewed_head: d8ee540f1f89626629912ec2e6769265a3228057
reviewed_base: ba87f8e339d5cc3aa55322801ae56e3f92369446
parent_task: SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1
review_verdict: PATCH_BEFORE_MERGE
finding_evidence: EXACT_SOURCE_CONTROL_FLOW_REVIEW_NATIVE_REPRO_REQUIRED
product_mutations_performed_by_reviewer: false
merge_authority_granted: false
---

# PR #398: закрыть operating-boundary без новой большой итерации аудита

## 0. Решение и результат для владельца

**Рекомендация: исправить два P1 в самом #398, затем завершить существующую delivery.** Размер PR сам по себе не блокер; обнаруженные расхождения затрагивают обещания уже заявленного обычного торгового пути. Перенос этих расхождений за merge не делает результат `READY_FOR_PAPER_SHADOW_COMMISSIONING` корректным.

Нужен один связный PATCH: **правила ordinary runtime действуют независимо от входной команды, а локальный отказ нового входа не прекращает обслуживание уже принятых обязательств**. Это не новый торговый движок, не развитие науки, не третья система рисков и не переписывание всего coordinator.

Что будет истинно после PATCH:

- На managed PAPER/SHADOW state нельзя обойти действующие mode envelope, active-entry scope и restore fence через legacy CLI/API или опущенный аргумент.
- Недоступный/истёкший grant новой B либо невалидный входной объект не прекращает обычный процесс, обслуживающий здоровый старый EXIT A. Истинно глобальный отказ хранилища не маскируется как здоровое продолжение.
- Отказ до attempt, неизвестность после committed attempt и definitive result не смешиваются. Нет повторной отправки, выдуманного nonfill, потери позиции или снятия паузы.
- Existing #396/#398 regressions, независимые оракулы, gates, cleanup и точные evidence bindings сохранены.

**Этот MD — review/handoff, не уже выполненный ремонт.** Выполнение начинается после явной передачи владельцем команды PATCH из §12. Merge, deploy, provider/credential/financial actions этим текстом не разрешаются.

### Сила и пределы review

Прочитаны exact PR metadata, список изменённых файлов, accepted task, runbook, отчёт, selected native source owners, source-shaped tests и final review receipt. Оба finding основаны на прослеженном коде producer → caller → общий guard → persistence/continuous loop на указанном head. Это не сообщения о произошедшем production-инциденте.

**Новые native product probes в этой review-сессии не исполнялись.** Программную копию checkout получить не удалось; source чтение через Git connector работало. Не выдавать этот документ за red/green transcript. Первое действие исполнителя — воспроизвести нижеописанные случаи на native fixtures и сохранить фактические before-results. Если гипотеза опровергнута, показать реально достигнутый guard и корректный committed outcome; фиктивное исправление не требуется.

P0 в изученных путях не установлен. Оба кандидата имеют P1 impact в обещанном software scope: обход operating safety и потеря непрерывного обслуживания. Реальные деньги, signer и live execution здесь не проверены и severity ими искусственно не усилена.

## 1. Anchor, объём и delivery

| Поле | Проверенное значение |
|---|---|
| Head | `d8ee540f1f89626629912ec2e6769265a3228057` |
| Base | `ba87f8e339d5cc3aa55322801ae56e3f92369446` |
| Branch | `codex/smial-trading-core-operational-closure-v1` |
| PR | OPEN, not draft, mergeable на readback |
| Объём | 90 files; +31,182 / −244; 11 commits |
| Saved reviews | CODE, GOAL_DOD, ARCHITECTURE, OWNER_UX: PASS для ранее проверенного inventory |
| CI при завершении review | Run `38233152025`: FAILURE; `validate-execution`, `validate-tests (4)`, итоговый `validate` — failure |

Минимум **19,014 additions, около 61% всего прироста**, относятся к evidence JSON/MD в той части file statistics, которая была достоверно доступна. Это нижняя граница, не полный category accounting. Большой объём создают в том числе `interim-before-*`, `review-*`, покейсные receipts, исходная постановка и история ремонтов. Не считать остальные 39% автоматически product code или tests: точное разложение требует native `git diff --numstat`.

При этом product surface тоже существенный: новые `trading_coordinator.py` и `trading_adapters.py`, изменения PaperPlane, runner, risk owner и CLI. Поэтому «всё из-за тестов» — неверный вывод. Не требуется перед merge переписывать историю, дробить уже согласованный outcome на произвольные PR или стирать отрицательное evidence ради размера.

CI отдельно от findings: execution log сообщает `IndexError` в `test_C21_native_source_stream_over_virtual_two_weeks` при `self.source.admissions()[0]` внутри `prepare`; фактически 341 cases, 1 error, 2 skips. Корневая причина не установлена этим review. Строка `EXECUTION_DOMAIN_FAST_TESTS: PASS` внутри того же лога не отменяет внешний failure. Не лечить это retries/skip/ослаблением oracle; воспроизвести failure в его исходном порядке/окружении и исправить причину. Причина failure другого shard пока не анализировалась.

На entry заново получить head/base/checks и проверить, не выполнен ли эквивалентный ремонт. Changed head → сверить именно изменившиеся owners. Если #398 к этому времени уже merged, применить **тот же PATCH как один follow-up от фактического main**; не повторять весь Closure и не считать текущую рекомендацию разрешением предварительного merge.

## 2. P1-A — operating safety зависит от caller flag, а не от durable scope

### 2.1. Прослеженный механизм

1. `scripts/trading_continuity.py` создаёт один и тот же `TradingContinuityRunner` для legacy `activate/episode/attempt` и новых `operating-activate/switch/tick/run`. Operating root не исключает старые команды.
2. `TradingContinuityRunner.episode(... ordinary_operating=False)` передаёт в `accept_signal_decision_outcome` operating flag только если caller явно указал True. Сам source packet производится через тот же frozen recipe.
3. `accept_signal_decision_outcome` проверяет новый shared outstanding envelope только в ветке `if ordinary_operating ...`. Новый position получает `ordinary_operating=1` также только при этом флаге.
4. `begin_modeled_attempt` включает shared envelope, если caller передал ordinary flag либо position уже имеет `ordinary_operating == 1`. Legacy-admitted position без этого признака обходит оба условия.
5. Restore fence проверяется в `TradingCoordinator._dispatch`, но не в `TradingContinuityRunner.attempt` / `begin_modeled_attempt`. Legacy API доступен на той же восстановленной DB.

Суть не в злонамеренной подделке SQL. Достаточно обычного ранее документированного API/CLI, который не знает о новых caller-specific checks.

### 2.2. Независимый контрпример: один слот, две позиции

Переиспользовать `OperatingDriverTests.test_C07_C08_C09_positive_successor_and_old_exit`:

- Начальный declared mode envelope — `max_outstanding_positions=1`, cost basis cap `$30`.
- A@V1 через настоящий ordinary path открывает позицию `$30`.
- B@V1 имеет самостоятельный valid scientific handoff и отдельную activation; switch сохраняет A и блокирует её новые входы.
- Новый timely B episode даёт валидный ENTER. Ordinary coordinator корректно отказывает `OUTSTANDING_POSITION_LIMIT`.
- Подать **тот же frozen B episode и тот же своевременный as-of** в публичный `runner.episode` с default kwargs / CLI `episode`, затем `attempt` при созданной reservation.

Ожидаемый invariant: дополнительной B reservation/attempt/effect нет; A остаётся исходным единственным обязательством. Отказ может сохраниться как отдельная evaluation, source ENTER не переписывается.

Предсказываемый по текущему коду before: B попадает в generic bot-local admission без shared envelope; появляется второй `WATCHED` с operating flag 0, затем разрешённая attempt. Mode liabilities могут достигнуть `$60` при cap `$30`.

Это **не фактический результат выполненного здесь теста**. Исполнитель должен получить native before или опровержение. Нельзя использовать в качестве fixture уже записанный руками B position: тогда обход входного guard не проверяется.

### 2.3. Независимый контрпример: restore fence только у coordinator

- Через обычные producer/adapter создать OPEN A; native backup.
- Восстановить backup в настоящий новый marked root через `restore_native_backup`; убедиться новым readonly connection, что `restore_guard=1`, entries paused, reconciliation/ACK ещё нет.
- Создать разрешённый operator close intent для исходной позиции, не утверждая, что продажа состоялась.
- Попытаться создать **новую EXIT attempt** через legacy публичный `attempt` и напрямую через существующий shared attempt owner. Вызов не отправляет настоящие запросы.

Ожидается restore refusal без нового `MODELED_ATTEMPT_STARTED`, adapter request, quota claim или `send_permitted=true`. Readback и original result reconciliation должны оставаться доступны.

Предсказание текущего кода: generic attempt owner проверяет origin/state/quantity, но не ordinary restore fence, поэтому может разрешить новый attempt. Это не доказательство live duplicate transaction; это обход запрета новых effects в восстановленном software state.

### 2.4. Минимальный design ремонта

**Один существующий authoritative operating-context/guard owner должен выводить effective scope из durable state.** Caller flag может запрашивать более строгий путь, но не выключать уже действующий managed scope. Не вводить новый registry, signer, entitlement service или вторую DB.

Рекомендуемый подход:

- Различать genuine legacy scope, managed scope и повреждённый/неполный managed scope. Признаки брать у existing mode activation/profile/state owners, а не из имени файла или одного bool caller.
- Не использовать наличие `OPERATING_BINDING_COMMITTED` само по себе как единственный discriminator: runner сохраняет такой binding и для совместимых legacy activations. Сопоставить реальный lifecycle `ordinary_state`, profile/switch и envelope в одном consistent read/transaction.
- Если managed scope был установлен, missing/corrupt его части — typed refusal, не fallback к permissive legacy. Не «ремонтировать» flags всех исторических rows без происхождения.
- Shared admission owner проверяет действующий entry-enabled scope и shared outstanding envelope на всех входных путях. Shared attempt owner проверяет restore fence на обоих sides и проверяет entry safety перед новой ENTRY attempt.
- Дополнительный CLI запрет/маршрутизация несовместимых legacy stage commands в managed scope полезен для ясности, **но одного CLI запрета недостаточно**, если direct consumer остаётся обходом.
- New activation managed mode не должна проходить мимо one-entry-enabled/CAS semantics через legacy `activate/start_bot`; восстановление/чтение прежнего bot не считать новой activation. Установить actual supported entry surfaces, не запрещать harmless internal getter из-за похожего имени.

Проверки выполняются до нового durable admission/attempt/quota/effect, а relevant state перечитывается под existing `BEGIN IMMEDIATE`. Не переносить authoritative decision в предварительный status, который успевает устареть.

### 2.5. Что важно не сломать

| Операция при restore fence | Ожидаемое поведение |
|---|---|
| Новая ENTRY attempt | Запрещена |
| Новая EXIT attempt | Запрещена до установленного recovery/ACK |
| Exact replay уже сохранённой attempt | Без новой отправки; existing identity можно вернуть с `send_permitted=false` |
| Достоверный original result / cut reconciliation | Разрешён в соответствующем recovery path; не новая попытка |
| Readback, pause, stop/drain, close intent | Сохраняют безопасные controls; close intent не даёт implicit send |
| ACK | Только exact current-snapshot cut/inventory, без снятия owner pause |
| Отдельная genuine legacy DB | Прежняя совместимость; no new unsolicited operating activation |

Связанная проверка clock: OBSERVED restriction сейчас явно применяется к `status/check/tick/run`, а manual stages принимают `--as-of`. Новые effects managed OBSERVED не должны получать historical time обходом другого command. Сохранить точные исторические clocks original results, activation receipts и replay; не заменить их все wall clock. Эта проверка относится к тому же ingress invariant, не к отдельному проекту «часы».

## 3. P1-B — отказ entry lane завершает `run` и теряет будущие old EXIT

### 3.1. Прослеженный механизм

`_tick_owned` локализует ошибки при обслуживании старых exit obligations, но не симметрично локализует новые входы:

- `_quote_for_origin`, quota/grant checks и `_inputs` поднимают typed exceptions;
- pending entry `bound.episode(...)` и subsequent `_dispatch(..., 'ENTRY', ...)` вызываются без ограничивающего обработчика;
- `run()` вызывает `_tick_owned()` без классификации recoverable lane outcomes;
- outer CLI возвращает ошибку, continuous process завершается.

Правильное «старые выходы первыми внутри одного tick» не помогает позиции, чей выход наступит **на следующем tick после остановки процесса**.

### 3.2. Контрпример, который реально достигает отказа grant

Для этой проверки **не брать envelope=1/$30**: он раньше остановит B admission, grant seam окажется недостигнутым.

Использовать явно заданный synthetic envelope `2 positions / $60` с валидными A/B strategy scopes:

1. A открыта штатным SHADOW path; её frozen exit ещё не наступил. A grant валиден и имеет quota для выхода.
2. Switch на B; актуальная source B, timely membership/PRICE, свободный второй слот.
3. В том же обычном процессе присутствует separately scoped B grant, но его validity истекает **до нового B dispatch**; либо B grant отсутствует, тогда valid A grant остаётся переданным.
4. Валидный B ENTER доходит до grant preclaim check и получает предусмотренный отказ. Нельзя мокировать `_dispatch` так, чтобы он просто бросал exception: исполнить настоящую проверку grant.
5. Управляемое время переходит через exit deadline A. Процесс не перезапускать; внешний A quote response доступен на нижнем fake transport.

Ожидается: тот же process продолжает ticks, A EXIT/result/reconciliation выполняются ровно один раз; B имеет retained scoped reason и не создаёт forbidden quote/attempt/quota claim. Истёкший B grant не переносит расход на A grant и не останавливает A.

Передаваемый в constructor `transport` может специально обходить authority validation. Поэтому для этого witness использовать existing granted-adapter test seam и подменить **нижний `http_quote`/wire**, оставив реальный grant checker и `transport=None` либо другую уже предусмотренную production-faithful injection. Fake grant/credential sentinel относится только к disposable synthetic world; реальные credentials/network запрещены.

В before ожидается propagation ошибки из `_dispatch` в `run`; after должен выполнить обещанное продолжение в том же процессе. Clock/provider ответы контролируются, orchestration и core guards — настоящие.

### 3.3. Design: локализовать сбой по стадии, не «catch Exception → continue»

| Момент/класс отказа | Нужное поведение |
|---|---|
| До durable attempt: отсутствующий/expired grant, exhausted cap, missing funding | Scoped entry blocker; нет send/quota/attempt. Reservation отменяется или удерживается по явной existing intent policy; не выдумывать возможный fill до submission boundary |
| Source record identity/shape conflict в entry scan/evaluation | Typed entry/source issue, сохранённое evidence; не терять плохой record тихим cursor advance; проверенные независимые old exits продолжаются |
| После committed attempt, до подтверждённого result | Сохранить исходные ID/request/quota/pending; reconciliation, не resend с новым ключом и не automatic nonfill |
| Definitive original result | Existing atomic accounting/final marker; exact replay без duplicate |
| Genuine shared-store failure, при котором нельзя доказать scope/integrity | Честный fatal/unavailable outcome; не маскировать «здоровым» tick и не продолжать эффекты на непроверяемом store |

Выбрать минимальное место преобразования expected failures в typed outcomes: per-entry loop / adapter boundary / небольшой existing coordinator helper. Не плодить catch во всех функциях и не создавать exception taxonomy без consumer. Unexpected typed errors сохранять с диагностикой и исходной стадией, не менять transaction semantics ради продолжения.

**Progress и recovery обязательны:**

- Наличие scoped blocker не означает successful entry, completed work или реализованный PnL.
- Нет tight retry loop: использовать existing polling и подходящее повторное рассмотрение при смене зависимости; неизменная ошибка не создаёт event storm.
- После восстановления разрешённой зависимости допустимый путь реально продолжается; stale admission не оживает и old owner PAUSE не снимается.
- `entries_enabled`, process progress, конкретные entry blockers и здоровье old exit должны соответствовать фактам. Текущий `exit_blocked = any(active incident not SOURCE-...)` не должен автоматически объявлять здоровый old EXIT сломанным из-за нового entry-only incident. Исправлять лишь реально затронутую projection, не всю админку.
- Если old exit сам не может получить funding/route, сохранить его obligation и честный blocker; это не разрешает придумать ликвидацию.

## 4. Доказательство: узкие оракулы плюс два настоящих сквозных пути

Не нужен ещё один Big Agentic Audit всего 04. Нужен небольшой набор проверок **границ**, которых не покрывает количество предыдущих PASS.

### Группы обязательств

| ID | Проверяемое обещание | Минимальное достаточное evidence |
|---|---|---|
| A1 | Managed envelope одинаков для ordinary и legacy/public admission | Native A/B scenario, одинаковый source ENTER, separate readback по обеим командам; A одна, B не создаёт reservation/attempt |
| A2 | Shared owner не доверяет caller flag | Direct public owner вызов с default/False на managed mode: тот же refusal; valid managed neighbour проходит |
| A3 | Restore fence покрывает ENTRY/EXIT, но не запрещает recovery | Настоящий native backup/restore; no new attempt/quota/effect до ACK; original result/cut/ACK живы; после ACK и допустимых controls old EXIT проходит |
| A4 | Scope/current clock/legacy compatibility не имеют fallback-обхода | Missing/corrupt managed-state guard; stale current epoch/new activation check; OBSERVED new-effects historical clock refusal; unchanged legacy replay |
| B1 | Expected entry preclaim refusal не убивает continuous process | Один реальный `run`/subprocess, A open → B grant refusal → A due exit → reconciled, без restart/ручного trade-stage glue |
| B2 | Postclaim failure сохраняет uncertainty и не resend | Native attempt, fault у нижнего adapter после claim; сохраняются identity/quota/request; original callback закрывает ту же attempt; соседний healthy EXIT не starves |
| B3 | Entry/source poison не блокирует весь old-exit service | Contract-valid fixture достигает именно source identity/shape guard; old obligations unaffected; quarantined work не исчезает из denominator |
| B4 | Новые outcomes не скрывают fatal failures и не создают ложную readiness | Injected shared-store failure остаётся fatal/unavailable; scoped entry blocker отличается от exit fault; recovery приводит к правильному readback |

Это восемь **обещаний**, не требование ровно восьми test functions или новых files. Параметризованные existing cases могут закрыть несколько. Положительные и отрицательные соседи должны достигать нужного seam; ранний отказ schema не доказательство risk/restore/authority guard.

### Независимый oracle и before/after

До production edits сохранить native before для A1/A3 и B1. Возможен один минимальный case для нескольких симптомов; не запускать одинаковую диагностику ради числа повторов. Исходный broken fingerprint и before outputs неизменны. Появление нового reason на changed head не называть результатом старого head.

Проверять факты отдельным соединением/процессом:

- exact position IDs и их originating epoch/strategy;
- множество новых `MODELED_ATTEMPT_STARTED`, `ADAPTER_REQUEST_BOUND`, `QUOTE_CALL_CLAIMED`, captures/results/finals;
- raw source identity/action и retained admission refusal;
- restore flag, cut/snapshot identity, owner pauses, envelope content/hash;
- before/after quantities, remaining cost basis и affected/unaffected states;
- actual external fake wire call count/IDs, а не только `send_permitted`;
- process PID остаётся тем же между entry failure и старым exit, либо наблюдается настоящий fatal исход в специально fatal case.

Для cap `$30` independent arithmetic — A obligation `$30` плюс B `$30` превысили бы cap на `$30`; expected admitted B set пуст. Не использовать `obligation_summary()` как единственный oracle для проверки его же влияния: сопоставить raw rows, original receipts и отдельный простой расчёт.

Не менять oracle на «так ведёт себя код». Не включать уже вручную исправленный bool/position/source в fixture — это скрывает R1. Для B1 предусловия свободного второго слота и действующего A grant обязательны, иначе тест не достигнет искомого места.

## 5. Existing fixtures, файлы и техническая свобода

### Сначала использовать

- `tests/test_trading_core_operational_closure_v1.py::OperatingDriverTests` — методы `start_operating`, `invoke`, source A/B сценарий, clock/subprocess helpers.
- `test_C07_C08_C09_positive_successor_and_old_exit` — исходный setup A→B, ordinary denial, originating A exit.
- `test_C05_C12_real_loss_after_quote_effect_no_resend` и `test_C05_C06_real_loss_after_capture_no_duplicate_effect` — исходные pending/callback proofs.
- `tests/test_trading_operational_recovery_v1.py` — реальные backup/restore/ACK sequences.
- `tests/test_trading_operational_adapters_v1.py` — exact granted quote path, no real HTTP/credential.
- `tests/test_trading_operational_obligations_v1.py` — shared inventory semantics.
- `tests/test_trading_continuity_v1.py` — сохранённые #396 A–D, genuine error rollback и provenance.

Точное имя теста/fixture заново разрешить на candidate; не копировать helper в новую альтернативную фабрику tests. Тестовые наборы уже позволяют настоящее SQLite и source-shaped data. Большая Docker/agent simulation здесь не нужна без нового доказанного препятствия.

### Предполагаемый change surface

| Owner | Что может потребовать изменения |
|---|---|
| `factory/paper_plane.py` | Admission/attempt guards, durable managed-scope derivation; сохранение normal refusal vs true exception semantics |
| `factory/trading_runtime_policy.py` | Переиспользуемая узкая проверка существующего envelope/scope, если правильное место именно здесь |
| `factory/trading_runner.py` | Все публичные stages получают same effective operating rules; controls/replay/recovery не отрезаны |
| `factory/trading_coordinator.py` | Scoped error continuation, correct postclaim recovery, meaningful progress/status |
| `scripts/trading_continuity.py` | Explicit supported command semantics, no caller-controlled bypass, truthful error/status |
| `factory/trading_adapters.py` | Только если необходимо distinguish preclaim vs postclaim result; не менять provider economics или grants |
| Existing tests/docs/evidence | Регрессии и реально затронутый semantic propagation |

Все module paths выше имеют prefix `src/solana_alpha_lab/`. `paper_shadow_commands.py` — лишь если shared control boundary этого требует; не менять смысл pause/close без необходимости.

**Не входит:** #397/List A, новый scientific protocol/holdout look, promotion, provider registry, новые packages/services, admin redesign, same-ID V2, trading policy tuning, live signer, wallet, RPC, real funding updates, force push/history/settings. Никакого «заодно перепишем coordinator на framework».

Разрешённые решения исполнителя: названия внутренних функций/reason codes с соблюдением existing vocabulary; место небольшого common guard; loop/catch structure; parameterization/test placement; rollback-compatible additive state только если без него нельзя доказать durable scope. Любое добавление новой durable semantics должно иметь named consumer и попадать в текущий contract/doc, а не существовать только в тесте.

**Запрещённые shortcuts:** всегда возвращать DENIED; отключить legacy целиком без анализа scope; очистить uncertainty/fence ради progress; обернуть всё в catch-and-continue; commit нормального error partial state; увеличить caps/TTL; resend UNKNOWN; автоматически переоформить grant; считать новый green local receipt старым exact-head evidence.

## 6. Порядок исполнения

### P0 — зафиксировать факты, не повторять большое исследование

AGENTS → exact parent task → relevant contract/runbook → actual head/base/checks. Сверить репозиторий и working tree, не трогать чужие изменения. Посмотреть native numstat по этому diff; размер не является отдельным blocker.

Прочитать указанные caller/guard paths и существующие regression fixtures. Добавить этот review к parent task как bounded PATCH с F-A/F-B, а не копировать исходную 100 KB постановку по всем evidence. Если scope уже merged — отдельный маленький canonical repair task на те же promises.

### P1 — получить native failure/опровержение

A1, A3 и B1 на неизменном исходном head; остановить соответствующий verdict, если fixture/guard недостигнут. При существующем working fix использовать frozen source checkout через нормальный policy, не подменять его отдельной копией функции. Сохранить actual environment/fingerprint, critical raw end-state и trace. Если finding опровергнут, нужен positive/negative control и конкретный другой owner, закрывающий обход.

### P2 — устранить earliest shared boundary

Сначала caller-independent operating rules; затем scoped entry failure continuation. Ремонтировать источник правила, не добавлять flags во все будущие callers. Проверять affected atomicity/compatibility маленькими native checks по мере изменений.

### P3 — доказать взаимодействие и recovery

Исполнить группы §4, включая настоящий continuous process, native restore and original callback. Rerun materially affected old C01–C24 proof/consumers по действующей policy. Не повторять полный repository gate после каждого микропатча; ни один старый PASS не переносить на изменённые inputs автоматически.

### P4 — финализировать тот же outcome

Обновить существующий report/readout/contracts и C-coverage: final evidence относится к новому candidate; before/failed receipts остаются историческими. Сделать четыре required isolated reviews на exact inventory по parent task и full Factory Fit. Новые отказы должны иметь короткий понятный next action; review restricted to material P0/P1 не означает игнорирование требуемого producer/consumer.

Починить реальные CI failures на правильном owner; подтвердить точный новый head CI SUCCESS → readiness PASS. **На этой границе остановиться за owner phrase.** Никакого merge на основании «предыдущий reviewer уже сказал да».

После отдельной owner phrase: guarded merge → current main/post-merge CI readback → завершить cleanup. Merge/CI не меняют статус scientific confirmation или живой эксплуатации.

## 7. DoD и stop conditions

PATCH готов к merge recommendation, когда:

1. F-A/F-B имеют native before/after либо убедительное source-backed и native опровержение. Нельзя закрыть только чтением этого MD.
2. Managed envelope/current-entry/restore rules действуют на всех поддержанных new-effect ingress; нет False/default downgrade; valid legacy соседи работают.
3. В одном continuous process scoped B preclaim refusal не лишает A будущего originating exit. Postclaim uncertainty не resend и не теряет original reconciliation.
4. Genuine exception/storage failures сохраняют atomic rollback/typed failure. Normal denials и их committed evidence не откатываются случайно.
5. Новые entry incidents не создают ложный EXIT failure или readiness PASS; recovered conditions действительно позволяют допустимое продолжение.
6. A/B, pause/drain, partial quantity/cost, restored tighter controls, original clocks, quota и #396 regressions не ослаблены. Targeted tests и final relevant outcome proof bound к изменённым байтам.
7. C01–C24 не обнулены и не сокращены; affected rows явно обновлены; actual cold command/API path проверен. `known critical gaps=0` допустимо только после evidence, а не после изменения prose.
8. Четыре required роли, bindings, security/CI/readiness соблюдены. Current failing CI не считается формальностью, разрешающей обход gate.
9. Собственная временная среда удалена после сохранения компактного reproduction/evidence; final handback содержит один next step — exact gate, не обещание продолжить research позже.

Ноль новых функций продукта за пределами named fixes. Нет лимита «две попытки»: safe dependent engineering продолжается до доказательства. Если повторяется тот же root seam или solution разрастается, пересмотреть размещение **общего** правила внутри этого scope, не заводить suffix cascade. Новая material policy/authority fork, невозможность изоляции, real data contamination или unknown truth owner → остановить зависимый участок, завершить независимое.

Наличие новой P1 в обязательном пути не переносится под ярлык commissioning. Отказ внешнего сервиса/недоступность реального host не подменяется synthetic PASS.

## 8. Cleanup и rollback

Scratch, fake-wire files, temporary DB/WAL/SHM, subprocesses и canary roots принадлежат конкретному запуску. Сначала сохранить minimal fixtures/reproducer + exact source and output hashes; затем удалить принадлежащие работе ресурсы и проверить absence/non-target preservation.

Не удалять чужие worktrees/caches/DB, реальные журналы, scientific exposure, историю отрицательных результатов и branch. Active worktree/toolchain можно оставить до merge/readback — это конкретный текущий consumer. После terminal delivery убрать только созданную этим PATCH временную environment/worktree по native safe cleanup; не force/remove history. Глобальный Docker prune запрещён.

Rollback code — обычный revert/follow-up по Git policy. Нельзя откатывать durable inventory/accepted results, ослаблять restored fence или сбрасывать grant quota, чтобы старый binary выглядел работоспособным. При incompatible rollback запретить новые entries и сохранить reconciliation/readback до совместимого repair. Реальных runtime действий в этом task нет.

## 9. Финальный handback исполнителя

В начале одна таблица: finding → native before → repair owner → independent after → residual. Далее exact head/base, changed paths, test commands/results и status CI/readiness. Отдельно указать:

- где новых effects стало 0 и чем это доказано;
- какой old EXIT прошёл после scoped entry failure без restart;
- что осталось UNKNOWN и почему;
- какая shared state/rollback/legacy semantics не менялась;
- cleanup inventory, exact evidence refs и сохранённая failure history.

Не суммировать два segment tests в whole-loop proof. Не приписывать этой проверке live trading или научную пригодность стратегии. Не заявлять PASS всех старых tests, если выполнен только targeted subset.

## 10. Source index — exact head, не память чата

Все ссылки ниже относительно `lancerbeta/solana-alpha-lab@d8ee540f1f89626629912ec2e6769265a3228057`, кроме AGENTS/base policy. Native line ranges — locator проверенного фрагмента; при изменённом head искать function, а не слепо номер строки.

| Ref | Path / function / прочитанный участок | Что устанавливает |
|---|---|---|
| S01 | `AGENTS.md` на base | Roles, current Git authority, review и merge gates |
| S02 | `docs/tasks/SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1.md` | D1–D4, scope, C01–C24 и четыре review роли |
| S03 | `scripts/trading_continuity.py`, L1–240 | Общий runner для manual/ordinary stages; command routing; current clock subset |
| S04 | `src/solana_alpha_lab/factory/trading_runner.py`, L1–235 | Root/load/frozen state; `_store` не делает caller-wide restore gate |
| S05 | `.../trading_runner.py`, L235–470 | `episode(...ordinary_operating=False)`, `attempt`, activation, result/recovery |
| S06 | `.../paper_plane.py`, L2160–2570 | Outcome API; shared envelope и row marker включаются по caller flag |
| S07 | `.../paper_plane.py`, L2580–2765 | Полный `begin_modeled_attempt`; positional flag/argument guard, replay, нет restore-state check |
| S08 | `.../trading_runtime_policy.py`, L820–1060 | Mode envelope vs legacy bot-local admission, explicit limits |
| S09 | `.../trading_coordinator.py`, L280–500 | `_inputs`, `_dispatch`, restore gate и stage/claim/quote |
| S10 | `.../trading_coordinator.py`, L495–930 | Recovery/old exit isolation vs unhandled new entry; source/current readiness |
| S11 | `.../trading_coordinator.py`, L1220–1459 | Cut/ACK, `run`, actual native restore fence |
| S12 | `.../trading_adapters.py`, L1–330 | Real grant preclaim checks, expiry/quota/request validation и dispatch |
| S13 | `tests/test_trading_core_operational_closure_v1.py`, L1–430 | Actual A/B fixture, commands, process-fault/recovery witnesses |
| S14 | `docs/operator/TRADING_CONTINUITY_OFFLINE_V1.md`, L1–140 | Обещания run, controls, grant scopes и operator setup |
| S15 | `docs/reports/smial_trading_core_operational_closure_v1/REPORT.md` | Сохранённые claims/154 tests/99 consumers и история ремонтов; не fresh review execution |
| S16 | `docs/evidence/smial_trading_core_operational_closure_v1/independent-review.json`, L160–230 | Ранее сохранённые четыре role PASS и fingerprint |
| S17 | GitHub PR #398 / Actions run `38233152025` | Head/base/diff stats и CI failure; live state перепроверить на entry |

Исходная Closure постановка находится в repo `docs/evidence/smial_trading_core_operational_closure_v1/source-contract.md` и связана parent task. Она нужна для спорного meaning, не для повторного раздувания пакета.

## 11. Почему этот PATCH до merge, а не большой redesign после

F-A и F-B — две конкретные причины, но один законченный owner outcome: **безопасный managed operating path независимо от входной команды и локального отказа**. Existing architecture позволяет исправить обе в её собственных owners. Добавление новых framework, mode registry, broker engine, services или научных требований не улучшает это доказательство.

Историческая масса JSON объясняет размер, но не является причиной дефекта. Не следует платить за косметическое уменьшение PR ценой удаления useful failure evidence. Следует закрыть конкретный guard gap и error boundary, один раз переоценить изменённый candidate и завершить delivery.

## 12. Команда для передачи

> PATCH PR #398 по `SMIAL_PR398_OPERATING_BOUNDARY_PATCH_V1`. Сначала native воспроизведение F-A/F-B на existing source-shaped A/B, adapter и native restore fixtures. Затем устрани caller-controlled обход operating envelope/active scope/restore fence и локализуй entry failures так, чтобы тот же continuous process продолжал здоровые originating exits. Сохрани legacy compatibility, original reconciliation, no-resend, normal-denial atomicity, clocks/controls/quota и текущие authority gates. Не расширяй science, strategy semantics, provider grants, dependencies или live scope. Доведи affected C01–C24 evidence, четыре review роли, CI/readiness и cleanup до результата. Если PR уже merged, этот же bounded repair оформи отдельным follow-up от фактического main. При опровержении finding покажи достигнутый native guard и независимый state readback; не чини выдуманную проблему. Merge, deploy, credentials, реальные calls и деньги этим сообщением не разрешены; перед merge верни exact machine-rendered owner phrase после PASS.
