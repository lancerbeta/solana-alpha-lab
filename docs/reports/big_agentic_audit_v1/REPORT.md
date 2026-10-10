# BIG_AGENTIC_AUDIT_V1 — owner report

**Audit completion: PARTIAL_BLOCKED.** На Git `90ba76e37515b3d521478a6d05a149fb0f1d2b75` обнаружены два воспроизводимых продуктовых дефекта. Полный путь от Forge-ready до научно обоснованного strategy handoff не доказан. Продуктовые исправления в этом аудите не выполнялись.

**NOW: отдельный repair `BAA-002` — связать реальные DocumentRunner events с ExperimentSpec в owner dossier.** Это постоянный разрыв между успешно выполненной операцией и её следующим потребителем. Проверка ремонта должна показать `execution=COMPLETED` и сохранить `PROMOTE_BLOCKED`, пока настоящих научных доказательств недостаточно.

| Что установлено | Результат |
|---|---|
| Матрица задания | 56/56 charters учтены; 54 имеют хотя бы одно посещённое проверяемое ответвление |
| Полностью закрытые заявленные проверки в указанной fidelity | 35 PASS; 2 FAIL; 17 UNKNOWN; 2 BLOCKED |
| Existing tests | 442 разных test IDs; 441 когда-либо PASS, один разрешённый SKIP |
| Все сохранённые test attempts | 477 PASS, 2 первоначальных HARNESS ERROR, 1 SKIP; в PASS входят 35 тестов до прерывания core-a1 |
| Последовательности | 24 × 12 действий; seeds 4129, 6137, 9011; domain — ResearchStore |
| Приоритетные тройки | 2 PASS, 1 FAIL, 3 UNKNOWN, 1 BLOCKED; отдельные проверки факторов не сложены в тройку |
| Живой actor | AGENT_BEHAVIOR_UNVERIFIED; шесть missions подготовлены |
| Production writes / product repairs / внешние product calls | 0 / 0 / 0 |

Число тестов не является знаменателем продуктовой надёжности. PASS относится к конкретному oracle и fidelity из [coverage](../../evidence/big_agentic_audit_v1/coverage.json). CONTRACT_ONLY проверяет правило на явно поданных промежуточных inputs; SEGMENT_PRODUCT_PATH проводит настоящий участок продукта. Эти участки не складываются в FULL_PRODUCT_PATH.

## Что прошло

На synthetic episode/list inputs выполнены настоящие visibility/scope и grounded discovery, freeze, scripted Critic transport, допустимая revision, frozen runner-up, machine classification, actual fixed-time proxy DocumentRunner и replay. Проверены независимые readbacks, источники denominator, future-poison пары, нормализованный decision prefix, budget reservation до чтения значений, prior exact/related/stale и representation continuation.

Реальные дочерние процессы аварийно остановлены после reservation, после durable append и между primary KILL и frozen runner-up Critic. Восстановление прочитало сохранённую стадию, сохранило исходную попытку/charge, не создало нового поиска. Отдельно проверены competing writer lease и idempotent repeat.

Downstream owner decision, manifest/provenance, explicit execution inputs, collision/replay и существующие CHECK/RENDER/VERIFY прошли из **авторских промежуточных scientific fixtures**. Их producer пропущен явно. Это не доказательство, что Forge/runner самостоятельно создал promotion-eligible evidence или ExecutionEvidenceBinding.

Selection/censoring diagnostics существуют и исполнены на synthetic inputs. Они не установили OOS, независимую репликацию, alpha или исполнимый NetReturn. Пара с одинаковой median и разными tails вернула разные корректные means в соответствии с заявленной metric.

## Что сломано

| Finding | Независимое наблюдение | Последствие |
|---|---|---|
| BAA-002, P2, NOW | Passport RUN_COMPLETED соответствует exact ExperimentSpec hash; dossier показывает NO_RUN. 3/3 graded consumer attempts, включая новый самостоятельный producer store | Следующий owner consumer теряет факт исполнения; связь не чинится checkpoint/restart |
| BAA-001, P2 | Writer committed COMPLETE; обычный readonly SQLite SELECT видит COMPLETE; два продуктовых reader показывают RUNNING. 2/2 свежих stores; после закрытия writer — COMPLETE | Owner readback использует устаревший checkpoint при активном WAL |
| BAA-003, P2, route gap | Для выбранного fixed-time Forge recipe не разрешён bound chronological/OOS successor в текущем accepted capability registry | Научный downstream и полный handoff остаются непроверенными |

Authoritative backlog: [findings.jsonl](../../evidence/big_agentic_audit_v1/findings.jsonl). Для BAA-002 producer сохраняет spec hash без явного experiment ID, а consumer собирает DIRECT run IDs по явной identity. Ремонт следует делать у владельцев этого контракта; не подставлять научные fields и не ослаблять DIRECT joins.

BAA-001 обусловлен `mode=ro&immutable=1` на текущем WAL store. Это отдельная причина; два проявления в OperationalStore и LifecycleProjection объединены в один finding. Не предлагается менять все intentional frozen SQLite snapshots.

## Что осталось неизвестным

Chronological/OOS переход для выбранного recipe и genuine actor lane заблокированы. Текущие collaboration agents получают host tools; их нельзя выдать за OS-confined audit actors. Для actor нужен ограниченный tool broker, fresh context и отдельно разрешённый budget. Новый сервис или account не создавались.

UNKNOWN сохраняют непроверенные части charters: valid singleton без выдуманного runner-up; availability downgrade с downstream readout; late backfill/revision lineage; полный dead/no-route/failed-exit corpus; model/prompt provenance perturbation; semantic paraphrase identity; timed-out Critic; полный CHANGE/DATA route; точный session-terminal/run-terminal стык; heartbeat без progress; synthetic holdout file с phase/role gate; полный falsifier-to-negative-memory путь; executable inventory/correction; физическая недоступность source после manifest. Их locators и уже выполненные subsets перечислены в coverage. Это остаток аудита, а не закрытые возможности.

## Проверяемость и изоляция

Срез включает входящий FORGE_NATIVE_LIFECYCLE_CLOSURE_V1. Исследовательский base приложенного документа используется только как provenance. [Task contract](../../tasks/BIG_AGENTIC_AUDIT_V1.md), [manifest](../../evidence/big_agentic_audit_v1/campaign-manifest.json) и [post-run](../../evidence/big_agentic_audit_v1/post-run.json) фиксируют текущие owners, Git hashes, runtime и ограничения.

Audit processes работали без сети, с readonly source/rootfs/kit, UID1000, dropped capabilities, no-new-privileges, 2 CPU / 2 GiB / 128 PIDs. Дочерний процесс наследует запрет записи; enhanced preflight подтверждает отказ маршрутизации к TEST-NET до внешнего соединения. Docker socket, host credentials и production stores не подключались. После кампании собственных фоновых процессов нет. Native synthetic evidence — 663,709,305 bytes; полные архивы — 129,209,815 bytes. Оба слоя сохранены; удалить sandbox для повторения не требуется.

Первоначальные ошибки source ownership, observer locator, Windows symlink copy и custom accessor сохранены как HARNESS_DEFECT. Interrupted core/spine attempts не стали полными PASS. Полные trace/readback/store artifacts остались в разрешённом локальном evidence root; в Git включены ключевые значения, hashes и [команды воспроизведения](REPLAY.md), а не runtime DB dumps.

Coverage mapping собран после наблюдений по фиксированной матрице документа. Это не preregistered benchmark; phase selectors, runner hash и исходный scope сохранены по каждой попытке. Source-level mocked/hand-bound tests используются только в заявленной CONTRACT_ONLY части. Zero-production-mutation вывод ограничен фактическими mounts, OS guards и scoped Git readback; runtime-health claim не делается.

**Решение владельца:** принять этот PARTIAL_BLOCKED checkpoint и выбрать отдельный BAA-002 repair. Его oracle уже воспроизводится двумя командами; после ремонта должны одновременно сохраниться правильное исполнение, typed scientific refusal и неизменность readonly inventory. WATCH — точный chronological consumer после отдельного выбора научного протокола. NEXT_MODEL_EFFORT: SOL_XHIGH для этого cross-consumer identity repair.
