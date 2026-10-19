# Исследовательские фрагменты V1

Карточка сохраняет роль и exact ссылки на native candidate/definition/result.
Формула остаётся у исходного query owner. Это research advisory, не стратегия.
Полка: `/research?kind=fragments`; detail открывается по locator карточки.
UI GET ничего не пишет, не измеряет рынок и не запускает due checks.

Все команды запускаются установленным locked runtime:
`uv run --locked --managed-python python -B scripts/research_fragments.py ACTION --data-root ABSOLUTE_ROOT`.
`read` возвращает ту же source snapshot, что projection и обычный Forge.

| ACTION | Вход / эффект |
|---|---|
| `registration-preview` | `--input request.json`; exact source validation, zero writes/looks |
| `register` | тот же request + `--confirm-append-only`; idempotent карточка |
| `plan-preview` | request с RFV, root identity, fixed future windows/caps/rules и owner scope; zero writes/looks |
| `plan-apply` | полный сохранённый preview + `--confirm-append-only`; CAS головы плана |
| `protection-status` | текущий local status, exact reason/owner, source refs; zero writes/values |
| `protection-preview` | source assessment и exact metadata-only installation proposal; zero canonical writes |
| `protection-apply` | `--input preview.json --authority scope.json --confirm-append-only`; versioned proof + CAS pointer |
| `run-due` | `--confirm-append-only`; максимум одно новое измерение, либо metadata recovery |

Registration request: `title`, declared `role` (`CONTEXT_FILTER`, `ENTRY`, `EXIT`,
`RISK_CONSTRAINT`), exact `session_id`, `candidate_id`, full `definition_sha256`,
`result_ref`, `result_sha256`; optional explicit `supersedes`. Другая формула или
роль — новая версия, прежние результаты не переносятся как evidence новой.
Exact repeat не добавляет карточку/MAIN; изменение metadata под тем же RFV
отклоняется. `read` сообщает `data_root_identity_sha256` для plan request.

Plan request задаёт `enabled`, 1..16 непересекающихся окон UTC admissions
`{start,end,input_closed_at}`, `execution_deadline`, `max_evaluations` (1..16),
`max_input_rows` (1..20M), `information_rule` (`min_matched`, `min_days`,
`min_tail_mass`, `adverse_es10_delta`), `owner_scope_ref`, root identity и RFV.
`source_roles=[EXPLORATORY_REUSE]`, `scientific_use=EXPLORATORY_MONITORING`.
Access boundary: Forge/Scout `EXPOSED_OR_UNKNOWN`, `confirmatory_claims=false`,
`protected_holdouts=EXCLUDE`. План не поддерживает confirmatory grant.

Input closure не раньше end+72h плюс native dispatch/availability grace;
deadline не позже end+14d. Первый proposal оставляет час на drain.
План фиксирует execution capability: изменение кода не переводит его
автоматически на новый evaluator и не возвращает budget. До первого значения
должны присутствовать все суточные cohorts окна, exact release/manifest/schedule,
current complete protection и совместимый frozen universe profile. Пропущенный
день не выкидывается из знаменателя. Отсутствие current inventory не равно
complete-empty; historical admission pin не заменяет current completeness.
Один owner `episode_current_protection` проверяет explicit source set из
`configs/episode_current_protection_sources_v1.yaml`: оба ResearchStore,
local assignment namespace, consumption registry, принятый TASK-22 v2,
experiment policies и List A protocol. Producer/release pins и labels выбранных
inputs проверяются отдельно как frozen dependencies. TASK-22 R3 остаётся DENY
в его TASK-21 dataset; это не global mint ban. UNBOUND у List A не выдаёт
confirmatory grant; advisory `holdouts_not_touched` не назначает reservation,
его referent UNKNOWN не подменяется доказанной пустотой.

Рабочий порядок: `protection-status` → `protection-preview` → отдельное exact
разрешение metadata-only scope → `protection-apply` → cold `protection-status`
и `read` → existing `plan-preview`. Сохранить полный stdout preview в файл,
а не только поле proposal. Installation authority JSON содержит
`proposal_sha256`, `read_scope` (точно из proposal),
`source_frontier_sha256` (canonical SHA256 массива source_frontier),
`mutation=VERSIONED_PROTECTION_METADATA_ONLY`, `owner_scope_ref` точного согласия.
Executor готовит эти файлы; ручное редактирование policy JSON владельцем не нужно.
Scope связывает actual root identity, exact source frontier и inventory hash.
Перед apply все mutable metadata перечитываются. Неизменный retry возвращает
исходный receipt; CAS conflict не перезаписывает прежнюю голову.

Current pointer `protection/current_research.json` находится вне assignment glob.
Сначала native atomic writer публикует immutable backward-readable assignment
receipt, затем меняется pointer под существующим ResearchStore writer lease.
Manifest/receipt не являются первичными assignment sources. `read`/GET/status
ничего не устанавливают. Старый `complete=true`, новая папка или копия bootstrap
не лечат `CURRENT_PROTECTION_NOT_INSTALLED`. Нечитаемый/unknown owner даёт
UNRESOLVED с причиной; это не inventory с нулём ограничений.

`checked_at` — provenance без TTL. Source-specific fingerprints не зависят от
CHECK/log/card, часов или whole-store inventory. Обычная совместимая cohort
перепроверяет свои frozen inputs; известная metadata delta переоценивается перед
действием без PR, переустановки proof и ежедневного approval. Новая версия owner,
неизвестная policy/authority link или неоднозначный scope закрывает новое чтение.
Metadata change никогда не возвращает MAIN budget и не меняет старый result.
Current gate повторяется под native reservation и непосредственно перед values;
поздний deny сохраняет reservation и блокирует loader. UI GET не делает apply.

План, scientific grant и новое измерение остаются отдельными уровнями authority.
При unresolved inventory включение блокируется; выключение и saved seed read
остаются доступны. Старый Scout native pin читает тот же assignment envelope,
но не доказывает исполнение новых current rules. Нет Scout-wide/untouched-holdout
гарантии, source event times UNKNOWN и confirmatory reuse forbidden сохраняются.
Rollback: выключить зависимый план, сохранить current restrictions и receipts;
не возвращать permissive current parsing и не переписывать historical pins.

Первичный caller — `opportunity_episode_release.import_episode_release`, общий
для штатного workstation consume/unpack, duplicate import и replay. Он сначала
завершает импорт и затем возвращает отдельный `fragment_refresh`. Ошибка refresh
не отменяет импорт. Explicit `run-due` использует тот же owner для cold resume.
Это запуск по локальному импорту/команде, не новый scheduler и не гарантия работы
при выключенном ПК. Реальные enablement/production-readback подтверждаются отдельно.

Scientific execution идёт через ordinary operation/reservation и
`run_recorded_discovery_query`. Журнал один на RFV, общий для revisions и epochs;
native policy и plan выбирают более строгий cap. Строки/файлы считаются до values;
loader читает только native dependency points. Нет автоматических абляций,
тюнинга, generation/LLM или торговли. INCONCLUSIVE также расходует look.
Pending input set сохраняется в native operation и не расширяется новым импортом.
`read`, полка и Forge показывают exact `attempts_without_result`, native status,
резервации и удержание universe gate даже при DISABLED / EXPIRED. Пауза и expiry
сами не завершают OPEN и не освобождают бюджет. Для непригодной попытки используйте
существующий `scripts/hypothesis_forge.py --data-root ABSOLUTE_ROOT
operation-stop-preview --operation-sha256 EXACT_SHA --owner-request-text REASON`,
затем `operation-stop --proposal PREVIEW_PROPOSAL_JSON --confirm-append-only`.
Сохраняется именно поле `proposal` preview. Native STOP append-only закрывает
execution без CHECK, INCONCLUSIVE или refund. Следующий run-due выбирает следующее
разрешённое окно; остановленное окно не переоткрывается. Его pending reservation
остаётся в native occupied и plan cap. После разрешения хвоста OPEN gate снят.
Новый plan-apply с новым execution binding не делает прежнюю operation совместимой:
либо запускайте исходный совместимый executor в пределах исходного контракта,
либо явно завершайте попытку native STOP. Binding guard не ослабляется.
Оба выбора остаются явными; sign результата не участвует в выборе окна.

Общий snapshot сохраняет native bounded by_cohort / by_calendar_block (до четырёх
каждого, с total/included/truncated), источник result_ref, native markers зависимости
и episode_counts/repeated_mint_n, где они сохранены. UNKNOWN не достраивается.
Для CHECK показаны observed/required/met/reason по каждому information_rule из
исходного плана. Исторические CHECK не переписываются: основание читается из
сохранённых native result и plan. `discovery-show --result-ref EXACT_REF --offset 0
--limit 20` даёт существующий bounded detail-read; это чтение без нового look.
Поиск исходного плана проверяет тип PLAN, exact inner hash и единственность.
Если план повреждён или недоступен, basis остаётся UNKNOWN, выполнение BLOCKED,
а hash-verified result summaries сохраняются в полке и обычном Forge prior.
Потеря процесса после result восстанавливает CHECK-ссылку без evaluator/списания.
До восстановления read/полка показывают DUE / FRAGMENT_RECOVER_LANDED_RESULT,
а не COMPLETE; run-due связывает уже сохранённый результат даже при paused plan.
Ошибка плана/accounting блокирует следующую проверку, но не скрывает уже
проверенное evidence из карточки и Forge prior. Причина важнее будущей даты trigger.
Pause/resume/revoke — новый preview/apply с `enabled`; cadence/lifetime меняются
только prospectively, started windows и information rule не переписываются.
Новые технические caps не возвращают уже занятый native budget.

Положительный descriptive contrast не означает alpha или OOS. Окна выводятся
отдельно; ES10 не усредняется. FALSE — отсутствие условия, UNKNOWN сохраняется.
Adverse/inconclusive evidence остаётся в памяти; автоматического PROMOTE/KILL нет.
Материальный RFV/artifact/result ref цитируется в `prior_work_refs`; ordinary
prior/context-view/freeze сохраняют source closure и исходный cutoff.
Price↓ + USD-liquidity-return≥0 не является Scout holders↓ + absolute-liquidity H/L.
Известная широкая adaptive Scout exposure остаётся ограничением источника.

Owner readback отдельно сообщает CAPABILITY_DELIVERED, SEED_REGISTERED,
PLAN_ENABLED, NEW_EVIDENCE_OBSERVED как FACT/WAITING/BLOCKED с источником.
Это четыре вопроса приёмки, не новые domain states. До exact post-merge scope
реальные registration/plan/new values не выполняются.

Protection apply JSON читается с настраиваемым локальным memory bound:
`--protection-metadata-max-bytes` (default 16777216). При реальном росте metadata
можно явно поднять этот bound без PR или смены scientific scope. Это защита памяти
CLI, не freshness, срок годности или научное исчерпание. Остальные native caps
не изменены. Unknown authoritative source/schema не лечится увеличением bound.

При PROTECTION_SOURCE_CHANGED (owner SOURCE_SET) или PROTECTION_HEAD_CHANGED
(owner LOCAL_ASSIGNMENTS): сначала cold protection-status. Если тот же proposal
уже установлен, повтор исходного apply возвращает exact receipt без нового effect.
Иначе создать новый protection-preview и запросить exact metadata-only scope для
нового proposal hash; старое согласие не переносится. Не повторять старый пакет
вслепую. Missing baseline source/removed restriction требует восстановления у
указанного owner, а не установки нового empty proof. Unknown owner/version/link
сначала разрешается у владельца источника. JSON ошибки включает next_action.

Текущие native assignments и committed declarations предполагаются append-only.
Installation baseline refs и restrictions сохраняются при revalidation. Read-only
resolver не ведёт историю transient источника, удалённого после installation;
несанкционированная правка namespace не входит в гарантию completeness. Это не
защита от потери истории или враждебного администратора; новый журнал не создаётся.

Current source interpretation узнаёт native envelope по producer capability,
record kind, wrapper/body form и поддержанной версии. Opaque/unknown owner или
новый packet version даёт UNRESOLVED; observed record count не является whitelist.
Таблица форм связана с существующими native owner modules. Обычные новые записи
той же формы не требуют ручного обновления. Producer schedule records остаются
frozen admission metadata, advisory packets не становятся assignment operations.
Legacy LIVE loader проверяет только Parquet footer/schema до values: episode_id
в native episode bytes нельзя скрыть переименованием dataset/population binding.

`context_sha256` описывает полный проверенный frontier источников; он может
измениться при новой допустимой declaration. `inventory_sha256` связывает root,
source interpretation и действующие restrictions. При неизменной protection
semantics новые native receipts не меняют scientific binding и не ломают exact
repeat. Это не cache допуска: каждый value entry всё равно перечитывает current
источники; missing/unknown/conflict и новые применимые restrictions закрывают его.

Current protection интерпретирует формы active policy / frozen snapshot / scope
extension из констант native `hfic_research_policy`, не из списка наблюдавшихся
записей. Лимиты и accounting остаются у native policy/operation owners.
`configs/experiment_specs` — перечисляемый namespace экземпляров. Каждый файл
проходит native schema validation и проверку поддержанного protection meaning;
новое имя и новый вопрос с известной семантикой не требуют переустановки.
Legacy prose сравнивается с конечными буквальными шаблонами, без NLP. Baseline
refs и fingerprints сохраняются: удаление или замена уже принятого файла закрывают
admission; неизвестные role/policy/authority binding тоже остаются UNKNOWN.

При отказе `protection-status`, CLI и fragment runner сохраняют `source_reason`,
`owner`, безопасный `source_ref`, известные `observed_form`/`observed_version` и
`next_action`. `RESTORE_OR_REPAIR_NAMED_SOURCE_THEN_RETRY` — восстановить названный
источник; `RESOLVE_NAMED_AUTHORITY_INTERPRETATION` — разрешить конкретную неизвестную
authority semantics; `REFRESH_SOURCE_STATUS_AND_PREVIEW` — перечитать изменившийся
CAS/source vector. Эти действия сами по себе не требуют нового owner scope.
`PREPARE_EXACT_METADATA_INSTALLATION_PROPOSAL` означает отсутствие current proof;
только `REQUEST_AUTHORITY_FOR_EXACT_METADATA_PROPOSAL` запрашивает отдельную
installation authority для уже подготовленного exact proposal.
