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
Ни UI, ни plan-apply не создают protection documents. При unresolved inventory
включение блокируется; выключение остаётся доступным.

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
Потеря процесса после result восстанавливает CHECK-ссылку без evaluator/списания.
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
