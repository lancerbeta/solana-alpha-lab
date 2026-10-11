# PR #396 — review handoff: сохранить штатный отказ admission

**Рекомендация:** PATCH текущего PR → обновлённое evidence/review → штатные merge gates. Версионный lifecycle — отдельное продолжение, не расширять им #396.

**Review verdict для проверенного head: REQUEST_CHANGES — один P1 в поддерживаемом V1-пути.** Это рекомендация Project Chat, не опубликованный GitHub review и не merge authorization.

## 1. Scope, identity и предел доказанности

- Repository: `lancerbeta/solana-alpha-lab`.
- PR: `#396`, `Repair offline V1 trading continuity with preserved V2 gate`.
- Reviewed head: `37e1285ef7c5a9273f0fc16e7b0097305831ecd0`.
- Base: `d244af69bfd7ddc2850b9e5e5823323956e325c4`.
- Branch на review: `codex/smial-trading-continuity-v1`; target: `main`.
- Existing contract: `docs/tasks/SMIAL_TRADING_CONTINUITY_AUDIT_REPAIR_V1.md`.
- Existing PRD/SSD: `docs/evidence/smial_trading_continuity_v1/source-contract.md`.
- Report: `docs/reports/smial_trading_continuity_v1/REPORT.md`.

Проверены actual head/base, changed-file inventory, ключевой source→decision→admission/result/exit code, transaction owner, handoff identity, выборочные сценарии и сохранённые receipts. Это независимое направленное review, не повтор всего исходного аудита.

В Git сохранены fresh 41/41 PASS и original S00–S23 denominator. S08/S13 остаются PARTIAL_BLOCKED. Независимые reviews относятся к content head `4f66ec3fb8756ccf22517dcf6fc450df7ff0a83e`; сравнение с review head показывает изменения только `completion.json`, `factory-fit.json`, `independent-review.json`. Полный repository E2E в Project Chat не запускался.

Найденный ниже механизм установлен прямым чтением трёх production boundaries и отдельно воспроизведён на реальном изолированном SQLite с тем же порядком transaction/call/raise. Эта структурная проверка не заменяет repository-native before/after. Исполнитель начинает с неё на существующем `OrdinarySourceTests` fixture; при расхождении исследует причину, а не подгоняет oracle.

Текст становится заданием на PATCH, когда owner передаёт его исполнителю как команду. Сам документ не разрешает merge, deployment, provider calls, новую научную или риск-политику.

## 2. P1 — штатный отказ откатывает собственное durable evidence

### Механизм

1. `TradingContinuityRunner.episode` открывает `with store.immediate_write()`.
2. Внутри сохраняет `SOURCE_DECISION_PRODUCED` и вызывает `accept_signal_decision(..., skip_fill=True)`.
3. `accept_signal_decision` тоже использует `immediate_write`. На обычном risk-denial он записывает `PRE_TRADE_RISK_SNAPSHOT`, выходит из своего блока и затем исполняет `if block_code: raise PaperPlaneError(block_code)`.
4. `PaperPlaneStore.immediate_write` при ненулевой глубине не создаёт отдельный commit/savepoint: только `yield; return`.
5. Поэтому исключение доходит до внешней транзакции runner; она делает `ROLLBACK`. Исчезают source packet и risk-denial snapshot. CLI печатает BLOCKED, но долговечная история не содержит этого решения и отказа.

Тот же composition defect затрагивает повтор уже зарезервированного, но не отправленного `WATCHED`: `_resume_block` обнаруживает stale/pause/disable, engine записывает `CANCELLED`, затем поднимает штатный отказ. Внешний rollback возвращает прежний `WATCHED` и теряет cancellation event. Для первого reproducer удобнее stale: он не зависит от подробностей поведения operator pause.

### Почему это P1 именно текущего PR

Это не недостающая V2-функция. Проблема находится в новом обычном caller и проявляется на валидном V1 negative/recovery path. Нарушаются explainability, source/admission denominator и durable stop/cancel semantics. Сам запрет входа не обходится; обнаружение не доказывает совершение запрещённой сделки. Однако merge с известным дефектом того самого failure path, который ремонтирует PR, неоправдан.

### Структурное наблюдение

Изолированная проверка на свежих SQLite connections, два повторения:

| Вызов | Сохранённые события/состояние после отказа |
|---|---|
| Engine-level risk denial, владеющий outer transaction | `PRE_TRADE_RISK_SNAPSHOT:BLOCK` сохранён |
| Тот же control flow внутри runner transaction | source и risk events отсутствуют |
| Resume/cancel внутри runner transaction | состояние вновь `WATCHED`, cancellation event отсутствует |

Это proof механизма вложенного transaction, **не отчёт о запуске исходного repository fixture**.

## 3. Outcome текущего PATCH

**Штатный отказ — наблюдаемый результат обработки, а не аварийный rollback.** Валидное исходное решение и результат admission сохраняются согласованно; резерв отменяется долговечно; реальные ошибки по-прежнему не оставляют частично принятой сделки.

Consumers: ordinary runner/CLI, existing engine callers, операторский readback, denominator/replay/recovery probes, следующий агент.

Scope: transaction/outcome boundary в `trading_runner.py` / `paper_plane.py`, прямо затронутые tests/contracts/readback, existing report/evidence/generated navigation. Не создавать новый event store, сервис или отдельный audit framework.

### Инварианты

- Source action `ENTER` и admission outcome `DENIED/BLOCKED` — разные факты; не переписывать scientific/source decision в `NO_ENTER`.
- Штатный denied admission сохраняет source identity/provenance, точную причину, scope и использованную policy binding там, где policy участвовала.
- При отказе нет новой позиции, разрешённого send или фиктивного modeled result.
- У ранее допустимого unattempted reservation завершившаяся отмена остаётся `CANCELLED` после выхода из API и открытия новой connection.
- `ATTEMPTING/UNKNOWN` не объявляются CANCELLED без evidence, что effect не было. Этот PATCH не меняет reconciliation policy.
- Same source identity/body не создаёт второй source packet. Replay отказа в одинаковом evaluation context не дублирует accounting/state effect.
- Если существующий contract допускает новый admission evaluation после изменения policy, прежний отказ не стирается. Новая оценка различима; не вводить вечный запрет повторной оценки молча.
- Corrupt source, conflicting identity, неизвестная ошибка, SQLite failure не маскируются под штатный deny и не приводят к commit частичного admission.
- Успешный путь сохраняет атомарность reservation, source binding и frozen amount/fee/revision.

## 4. Рекомендуемое решение — адаптировать outcome, не дублировать логику

Предпочтение: существующий admission owner должен уметь вернуть типизированный штатный результат в orchestration path; при необходимости совместимый exception-oriented wrapper сохраняет привычный API для прежних callers и поднимает отказ после корректной границы commit.

Точная реализация — за исполнителем после проверки актуальных consumers. Допустимо другое более простое решение, если оно сохраняет перечисленные invariants и реально проходит normal caller.

Не исправлять это широким `except Exception: commit`, подавлением `PaperPlaneError` целиком или механическим удалением outer transaction без проверки source/reservation atomicity. Не дорисовывать потерянный отказ задним числом в projection. Не переносить admission policy в runner.

## 5. Repository-native proof до и после

Переиспользовать `OrdinarySourceTests` / `EpisodeScenario` в `tests/test_trading_continuity_v1.py`, реальные SQLite owners и штатный runner/CLI. Не передавать готовый `SignalDecision` напрямую в engine как единственное evidence.

### A. Новый source ENTER, admission запрещён policy

Подготовить валидный source-shaped положительный V1 scenario. В disposable runtime применить существующую policy с `new_entries_enabled=false` либо реально исчерпать capacity. Вызвать ordinary `episode`.

Проверить отдельным readonly store после возврата/исключения:

- exact source packet сохранён один раз;
- outcome admission и reason/policy binding сохранены и доступны для объяснения;
- positions/attempts/results не увеличились;
- повтор того же входа не создаёт дубликатов эффекта;
- положительный сосед при разрешающей policy проходит без изменения source semantics.

Разрешения для fixture policy не распространяются на operational runtime.

### B. Существующий WATCHED → stale replay

Получить `WATCHED` через ordinary positive episode. Не начинать attempt. Повторить тот же episode после `decision_at + max_age_seconds`.

На новом readonly connection должны оставаться `CANCELLED` и trace причины `SIGNAL_EXPIRED` согласно actual owner. Позиция не остаётся в open-entry count. Повтор не оживляет reservation. Дополнительно пройти pause/disabled-policy branch, если он отличается по control flow.

### C. Denominator, который действительно различает отказы admission

Расширить существующий independent source/action/admission/terminal test хотя бы одним source `ENTER`, отклонённым admission. Ожидаемые множества задавать независимо:

- processed valid sources;
- source actions;
- admitted decisions;
- denied admission evaluations с reason;
- positions, attempts, terminal outcomes.

Больше нельзя использовать `admitted == все source ENTER` как универсальный oracle. Для нового fixture `admitted` — строгое подмножество source `ENTER`; разность объясняется сохранёнными отказами, не пропусками.

### D. Настоящая ошибка и concurrency

Fault перед commit: никакого частичного reservation/accounting и фиктивного штатного отказа. Existing real-SQLite admission concurrency не теряет сериализацию. Positive V1 PAPER mixed/list-only и SHADOW mixed, UNKNOWN reconciliation, exit и literal accounting сохраняются.

Сначала сохранить фактические red probes на исходном head. Если repository-native результат опровергает finding, вернуть exact command, state readback и объяснение, на какой boundary оказался неверным вывод. Не ремонтировать опровергнутый дефект.

## 6. DoD и доставка

PATCH завершён, когда:

- A–D доказаны в normal caller; критичные результаты читаются новой connection, не только из return/log.
- Existing callers сохранили совместимость или обновлены согласованно.
- Нет новых provider/dependency/deploy/credential/wallet/real-data действий.
- Report содержит новый finding и before/after; original S00–S23 и V2 gaps сохранены, старые receipts не выданы за проверку нового кода.
- Обновлены реально затронутые contracts и generated bindings санкционированным способом; duplicate truth owners не появились.
- Fresh supported journey и impacted regressions выполнены на новом candidate; binding/reviews/CI refreshed по existing Git policy. Старые PASS не перенесены на изменённый код без проверки.
- Temporary owned roots удалены после evidence; посторонние caches/окружения/данные не удалены.

Не повторять весь discovery/audit и не запускать локальный full gate на каждую правку. Использовать current Delivery Harness: exact-head CI → merge-readiness PASS → отдельная machine-rendered owner phrase → guarded merge → post-merge readback. Настоящий FAILED gate не обходить.

До отдельного разрешения не merge. `REPAIR_PARTIAL_BLOCKED` остаётся допустимым честным результатом этого инженерного среза; не превращать его в `OFFLINE_CHAIN_VERIFIED`, canonical DONE, operational commissioning или alpha.

Handback: updated head, root cause, before/after A–D, impacted checks, remaining scope, cleanup, точный readiness state. При changed head сначала сверить фактический diff; не возвращать branch на старый anchor.

## 7. Отдельное продолжение после безопасного принятия #396

**Предлагаемый outcome: непрерывная работа при смене допущенной стратегии без потери старой позиции, её правил выхода и evidence.** Рабочее обозначение `STRATEGY_SUCCESSOR_CONTINUITY_V1` — предложение, не существующий READY contract.

Не начинать с «заменить V1 на Vn». Current `promotion_handoff.py` строит `strategy_id` из `experiment_id` и материализует `V1`. Поэтому новый frozen experiment естественно получает другую strategy identity. Отказ произвольной `V2` ещё не доказывает, что нужен generic same-ID versioning.

Рекомендуемая начальная семантика для отдельного design:

- restart того же frozen executable → новая activation epoch, не новое scientific evidence;
- изменившийся научный смысл/recipe/execution regime → новый frozen experiment и собственный допустимый PROMOTE; без автоматического наследования допуска;
- сначала проверить минимальный successor path: `A@V1` с незакрытой позицией, `B@V1` из независимого exact handoff, запрет новых входов A и сохранение originating exit/reconciliation A;
- разрешение новых входов B всё ещё подчиняется действующей risk policy и отдельной activation;
- разные strategy IDs не должны смешивать provenance/accounting или скрыто обходить соответствующие shared risk limits;
- same-ID `V2` проектировать только при подтверждённом самостоятельном consumer/смысле, а не ради номера в тесте.

Это material correction исходного слишком буквального V2 scenario, а не разрешение молча вычеркнуть S08/S13. Подготовить короткое согласованное решение для owner: оставить same-ID versioning обязательным или принять другой scientific identity path как intended successor behavior. До такого решения original S08/S13 остаются незакрытыми; успешный A→B scenario учитывается отдельно.

Automatic exit после STOP/deactivation и admission против residual inventory — отдельные policy questions. В design показать, требуется ли их изменение для successor path или существующий `PAUSE_NEW_ENTRIES` с продолжающимся originating exit достаточен. Не менять risk/exit semantics лишь для зелёного теста. Админка, actual provider commissioning и live execution не входят.

NOW: устранить transaction/outcome defect и безопасно завершить #396. WATCH: successor lifecycle с trigger «#396 принят; выбран и зафиксирован точный смысл смены стратегии». Не запускать WATCH автоматически по этому review.

## 8. Точные Git опоры

Все пути ниже читаются на reviewed head из §1:

- `src/solana_alpha_lab/factory/trading_runner.py`: `episode`, `attempt`, `result`, `exit`.
- `src/solana_alpha_lab/factory/paper_plane.py`: `immediate_write`, `accept_signal_decision`, `_resume_block`, `resolve_activation_epoch`.
- `scripts/trading_continuity.py`: `main`, обработка BLOCKED.
- `tests/test_trading_continuity_v1.py`: `OrdinarySourceTests`, `test_independent_source_action_admission_terminal_sets`, ordinary full-chain и before/after fixtures.
- `src/solana_alpha_lab/factory/promotion_handoff.py`: `strategy_id_from_experiment`, `_science_lineage_matches`, `check_materialization`.
- `docs/contracts/episode_decision_continuity_v1.md`: durability, supported runtime и status table.
- `docs/evidence/smial_trading_continuity_v1/{fresh,completion,independent-review,factory-fit,cleanup}.json`.

Repo/readback имеют приоритет над этим review при изменении head. Никаких новых прав этот список не предоставляет.
