# Episode-native required outcomes: результат ремонта

Закрыт конкретный product contract gap из аудита #402: исходный E1800→E14400
recipe теперь выражается через **ExperimentSpec 1.4** и доходит до настоящей
сохранённой HFIC-классификации. Population, episode identity, native часы,
estimand, пороги и protection сохранены. Старые Spec 1.0–1.3 не менялись.

Позитивный witness: 24 admissions, D=20, M=10, C=10 для LIST_CONTRAST;
coverage E14400 — 20/20, terminal `FAST_LANE_READY`, session
`SYNTHESIS_COMPLETE`. Для MIXED_LIST_NUMERIC native comparator C=D=20;
разрешённое пересечение с M сохраняется. Точные IDs и masks совпали с отдельной
таблицей входных меток, записанной до discovery. Два эпизода одного mint не
схлопнулись в один.

Вариант с одним typed-missing outcome штатно сохранён как `BLOCKED_DATA` /
`EPISODE_OUTCOME_COVERAGE_UNRESOLVED`: 19/20 при том же D=20. Новые процессы
прочитали оба receipts без изменения committed inventory. Exact repeat READY
не создал новых записей. Изменение текущей protection блокирует новое действие,
включая replay; historical readback остаётся доступен.

Проверки: **16/16 native**, без skips, и **84 selected legacy**, все PASS.
Reader oracle наблюдал реальные запросы Parquet: значения только exact prefix
episode/point/field с availability filter, future target values — 0.
Намеренно небезопасный reader и испорченный membership mask обнаружены.
Source/query/definition/schedule/publication conflicts, UNKNOWN list coverage,
подсунутый COMPLETE и current DENY/unresolved дают защитный отказ.

| Evidence | Что можно проверить |
|---|---|
| [baseline](../../evidence/episode_native_required_outcomes_v1/baseline.json) | Whole valid 1.3 X/Y control и точный прежний E-pattern refusal |
| [positive](../../evidence/episode_native_required_outcomes_v1/positive.json) | Настоящий stored READY, source-bound membership/coverage, cold inventory |
| [blocked](../../evidence/episode_native_required_outcomes_v1/blocked.json) | Настоящий stored 19/20 blocker без сокращения D |
| [coverage](../../evidence/episode_native_required_outcomes_v1/coverage.json) | T1–T11 и точная fidelity каждой проверки |
| [focused checks](../../evidence/episode_native_required_outcomes_v1/focused-checks.json) | Фактические команды, tested head, результаты и бюджеты |
| [campaign](../../evidence/episode_native_required_outcomes_v1/campaign.json) | Все сохранённые worlds, setup looks и неуспешные попытки |
| [science guard](../../evidence/episode_native_required_outcomes_v1/science-guard.json) | Native PROMOTE_BLOCKED после распознанного Spec; qualifying evidence отсутствует |
| [footprint](../../evidence/episode_native_required_outcomes_v1/footprint.json) | Измеренный размер retained repair worktree, без удаления |

Это полный proof **внутри repair boundary**: loader → native sources/prefix →
classifier → authoritative persist → cold readback. Critic scripted и служит
входом теста; научное принятие гипотезы этим не установлено. Direct runner
проверен до своей ближайшей границы: настоящий positive lineage handoff и
реальный отказ `start_document` на повреждённом schedule до evaluator/writes.
Численный эксперимент не запускался. Replay использует явный stored completed-run
fixture, а не заявленный новый научный результат. Conflicting duplicate admission
проверен test-only reader fault после binding; late/censored — native metadata
и clock cases, без заявления о полном перепубликованном late/censored world.

Подготовка одиннадцати сохранённых native worlds выполнила **22 MAIN looks**;
они учтены отдельно. Classify/projection/repeat/readback добавили 0. Предыдущие
worlds и их trial history сохранены, scientific KILL из аудита не переписан.
Новый benchmark не стирает старую кампанию.

Независимое architecture review обнаружило и закрыло P1: отсутствие текущей
protection раньше позволяло использовать admission-time completeness как
текущее разрешение. Теперь новая ветка отдельно требует native current
completeness proof до объединения с frozen protection. Missing/empty/unreadable/
incomplete inventory блокирует READY, новое persisted action и replay до values.
В новом fixture protection owner явно зарегистрировал complete-empty inventory;
реальные неизвестные источники так подменять нельзя. Предыдущие worlds/receipts
остались историческими, их положительный terminal не даёт fresh authority.

Delivery preflight обнаружил отдельный старый pin List A на общий temporal owner.
В прежний main-refresh receipt добавлена только датированная запись изменения
implementation с current hash и Git ref/hash исходного receipt целиком. Все
старые поля, checks, pins и scientific result сохранены. Это не повтор List A
проверок и не подтверждение его совместимости с новым модулем; прежнее owner
authorization не даёт merge authority этому repair. Machine policy не менялась.

Repair worktree со всеми retained worlds и proof занимает **509 443 512 байт
allocation — 485,84 MiB / 0,474 GiB** на момент измерения. Из них synthetic/proof
— 438 093 624 байта; checkout/harness — 71 349 888. Это ниже cap 512 MiB.
Измерена фактическая NTFS allocation, hard links дедуплицированы. Новых venv,
dependencies, containers и images — 0; существующие runtime/cache переиспользованы.
Ничего не удалено. Старый audit footprint **0,763 GiB** — отдельный historical
snapshot из #402; repair его не перемерял. Shared cache growth остаётся UNKNOWN
без исходного baseline, common Git objects и directory metadata исключены.

Следующий самостоятельный вопрос — accepted chronological validation
producer/consumer для того же estimand. Здесь не доказаны qualifying DIRECT,
scientific acceptance, blind Actor, StrategyVersion, activation, PAPER или полный
lifecycle. Их запуск требует отдельного exact task/Science authority.
Рекомендация на этом checkpoint: следующий analysis — SOL_XHIGH; Git delivery
этого кандидата — ROUTINE_NO_SWITCH.

Восстановление: читать сохранённый receipt штатным `load_session_bundle`;
новое действие revalidates immutable sources и current protection. Rollback —
ordinary revert новых schema/code/docs с сохранением всех научных receipts.
Выбор версии и recovery NEXT закреплены в canonical contract, Forge/Critic skills
и operator guide. Reproduce procedure — [REPRODUCE.md](REPRODUCE.md).
