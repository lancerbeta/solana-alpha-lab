# FORGE_TRUST_CLOSURE_V1

Технический маршрут Forge requalified в synthetic scope: current WAL read,
native producer → exact-spec execution → новый dossier/API/HTTP Workbench,
legacy compatibility без backfill, fail-closed identity и recovery. Полный
положительный science-to-strategy путь остаётся BLOCKED_SCIENTIFIC_PROTOCOL_C;
AGENT_BEHAVIOR_UNVERIFIED сохраняется. Это разные verdicts, а не общий PASS.

Основание: product base `90ba76e37515b3d521478a6d05a149fb0f1d2b75`,
PR393 audit head `ea4afb52b9d188c378d2a9850ba1b26c85496821` (OPEN при Entry).
На Entry audit ещё не был main. Перед frozen review PR393 merged с final head
`d1e66ede07ff2586580a74f2b8e35fa0c5f9308d` в main
`96eb087224f012ccb028ba468d4e0a7cd7ca1506`; добавлено уточнение audit stop semantics,
product source не изменён. Task branch включила этот main обычным merge, без
history rewrite. Audit bytes сохранены; исторический PARTIAL не повышен. Owner PRD+SSD hash:
`8c614c82e29969f5428ae498f47a28d22c7dc9c81d2aaafdc3d4445c73308215`.

| Граница | До ремонта, фактический baseline | После ремонта, фактический readback |
|---|---|---|
| BAA-001/D07 | writer уже commit COMPLETE; два current readers видят RUNNING | независимый mode=ro, OperationalStore и lifecycle видят COMPLETE до закрытия writer |
| BAA-002/F08 | native exact-spec RUN_COMPLETED существует; dossier NO_RUN | native exact-spec records DIRECT, execution COMPLETED в новом процессе API и HTTP Workbench |
| legacy | completion без experiment_id не связан с dossier | только validated passport с exact canonical spec hash; historical bytes сохранены |
| конфликт identity | чужая/невалидная строка могла оставить общий run/trial seed | противоречивый execution или trial key quarantined до seeding; слабая scientific metric не наследует DIRECT |
| science | proxy completion не закрывает научные obligations | PROMOTE_BLOCKED; execution COMPLETED не повышает scientific status |

Canonical document hash отличается от hash YAML-файла. Он включает experiment ID
и machine definition; prose `what_changed` исключён согласно прежнему run-key
контракту. Native RUN_STARTED, COMPLETED passport и INVALID получают producer
identity. Trial/run key, бюджет, транзакции и прежние records не переписаны.
Чужой однозначный experiment не объявляется unresolved own execution. Неясный
legacy с общей hypothesis остаётся видимым gap; по нему не угадывается связь.

Isolated review нашёл и воспроизвёл обход quarantine по trial ID: отброшенный
TRIAL ещё мог seed слабую metric, открывая scientific guard. `b50a4a95df48`
вычисляет run/trial quarantine до seeding; regression проверяет общий конфликтный
run, чужой trial и старый spec hash. Native joint повторён на этой версии: PASS.
Тот же review нашёл successful shell exit при missing harness evidence. Реальный
WAL container завершился с exit=0; intentional отказ extraction summary дал
HARNESS_ERROR_NO_TERMINAL_EVIDENCE и launcher exit=2. `--verify` отдельно
показывает integrity PASS и исходный failed replay_status. Это наблюдательный
canary стенда, а не product/scientific failure или genuine actor.

Readonly означает отсутствие business/SQL/durable DB/WAL writes. Живой SQLite WAL
использует SHM как volatile coordination; обещания неизменности всех SHM bytes
нет. В joint proof реальные права запрещают запись в DB, WAL и каталог, writer
остаётся открыт, SQL mutation отдельно refused, durable hashes совпадают.
`mode=ro` с `query_only` сохраняет текущую WAL truth; `immutable=1` оставлен только
как заведомо неправильный observer canary. Семантика подтверждена также
[SQLite URI](https://www.sqlite.org/uri.html) и [SQLite WAL](https://www.sqlite.org/wal.html).

Проверки по разным revisions не складываются в «все тесты final head PASS»:

- `19ffd3e87775`: native producer PASS, исходный WAL route PASS, 155 selected
  source/contract/CLI tests PASS. Consumer identity позднее усилена.
- `0fe35ffafa5e`: новый standalone producer PASS; 44 closure/consumer tests PASS,
  включая pending × new epoch × safe STOP recovery; baseline native records
  читаются новым bridge без дополнительных evidence records.
- `7a3361b3e1dc`: joint native consumer/permissions PASS; 14 local current guards
  PASS, включая настоящие FAST/CHANGE/DATA terminals → persisted cold consumer.
- `f64d275717cc`: финальный reusable entry WAL PASS; intentional one-second
  timeout остановил owned producer и вернул TIMEOUT/nonzero. Неверная identity,
  stale observer, изменённый artifact и чужой mount дают реальные отказы.
- `b50a4a95df48`: повторённый linked joint PASS; 47 closure/consumer tests PASS,
  включая trial quarantine и правильный shell verdict. Intentional missing-summary
  canary сохраняет HARNESS_ERROR, container exit=0 / launcher exit=2.

Source equivalence и requalification изменённого consumer лежат в
[dependency_closure.json](../../evidence/forge_trust_closure_v1/dependency_closure.json).
Полный run/attempt/hash index: [run_index.json](../../evidence/forge_trust_closure_v1/run_index.json).
Исходные 56 IDs и 35 PASS / 17 UNKNOWN / 2 BLOCKED / 2 FAIL сохранены в
[charter_ledger.json](../../evidence/forge_trust_closure_v1/charter_ledger.json).
Здесь нет автоматического переименования UNKNOWN в PASS и общего full-path claim.

Материальные residuals проверены по obligations: public singleton, synthetic
publication/PIT future poison, native classifier downgrade и FAST/CHANGE/DATA
→ persistence/readback, two-cycle lifecycle, lost-reply cold resume, STOP × late
landing × changed profile, calc correction без нового MAIN, физический protected
holdout до value read, исчезновение source parquet и восстановление прежнего
manifest. Historical decision parquet не изменился; пока source отсутствует,
consumer fail-closed и не обещает successful source revalidation.

У negative SIMPLE есть реальный computed PAUSE. Путь scripted critic KILL →
native DECISION_EVENT → следующий prior доказывает transport и сохранение reason,
но не независимое научное заключение actor. Семантические синонимы не входят в
accepted canonical identity. Для dead/no-route/failed-exit realizable NetReturn
нет принятого estimator выбранного proxy recipe; арифметический missing не стал
нулём. У Forge нет accepted heartbeat scientific-health contract: stage/next
readout не назван «здоровой наукой».

Все шесть genuine actor missions M01–M06 — NOT_RUN / AGENT_BEHAVIOR_UNVERIFIED.
Доступная collaboration наследует host tools, tool-less actor surface отсутствует;
для adapter loop нет разрешённого model transport/budget. Новый provider/runtime
не подключён. Изолированные readonly critics — review, scripted replay — product
evidence; ни то ни другое не confined actor. Проверен HTTP HTML/API, pixel/browser
UX не проверен. Точная science boundary и один следующий owner decision —
[SCIENTIFIC_DECISION.md](SCIENTIFIC_DECISION.md).

Первый joint attempt ошибочно требовал отсутствия любых legacy gaps в store.
Он сохранён как HARNESS_ERROR_ORACLE_OVERSCOPED. Исправленный oracle требует,
чтобы actual exact-spec producer IDs были DIRECT и отсутствовали в gaps; другие
legacy gaps остаются видны. Setup misses (неверные CLI command/JSON field,
fixture import/path, whitespace hook) исправлены до grading; это не product
регрессии. Никакой scientific oracle не был ослаблен.

Linux product runs: существующий pinned runtime, UID1000, root/source/kit readonly,
network none, no socket/home/credentials, cap-drop ALL, no-new-privileges,
2CPU/2GiB/128PIDs. Новые stores принадлежат этой campaign. Volumes/raw traces
сохранены вне Git; одних hashes недостаточно, чтобы сделать их доступными на
другом host. Как воспроизвести и где readback: [REPRODUCE.md](REPRODUCE.md).
Cleanup readback: 0 running campaign containers, 17 retained owned volumes,
584980092 accounted evidence bytes (<2GiB). Новых generated state sequences: 0.

Factory Fit: FULL_REVIEW, narrow project-owned repair; WRAP существующий audit
kit/runtime. Product Horizon NOW — этот current-read/execution/guard loop;
WATCH — ровно frozen protocol выбранного List A recipe. CAPABILITY_RADAR_NOW=NONE.
Rollback обычным owner-gated revert не меняет records/budget, но вернёт известные
дефекты freshness/lineage. Deploy и production acceptance не выполнялись.

Delivery завершается проверенным PR и exact-head merge-readiness. Merge, canonical
DONE и post-merge acceptance требуют отдельной точной owner phrase и guarded
readback; этот документ не выдаёт разрешение.

Upstream reconciliation выявил связанный mechanical blocker: обычный precommit
whitespace check сравнивал весь incoming accepted audit с прежним task HEAD,
включая две исторические строки SPEC. Audit не переписан, hook не обходился.
Для pending merge exact `origin/main` новый helper проверяет весь staged candidate
delta относительно incoming main; ordinary/non-main merge сохраняет прежнюю
границу. Три реальные Git проверки PASS: accepted history сохраняется; новый
candidate whitespace и non-main incoming whitespace дают nonzero. Эта узкая
инженерная корректировка включена в contract write set и независимый review.

Первый exact-head CI PR394 (`f658c897329f`, workflow38046484381) получил core
FAILURE: legacy validate_baton ожидал inline whitespace command в PowerShell,
хотя он уже перенесён в strict helper. Downstream execution job SKIPPED по этой
зависимости; оставшиеся test jobs на момент диагностики IN_PROGRESS, их PASS
не предполагается. Validator теперь проверяет actual delegated wrapper/helper
boundary, ordinary staged Git command и nonzero propagation; focused validator
и три реальные Git regressions PASS. Product source/science не изменены.
Failure/retry сохранены в ci_repair.json; новый head требует fresh review/bind/CI.

В том же первом CI test shard3 выявил два связанных test defects: pending
no-commit merge требует committer identity даже без commit, а current-byte pin
Workbench оставался до разрешённого lineage readout. Реальный replay с отключёнными
global/system Git configs воспроизвёл два merge errors (exit128); явная synthetic
identity только на test command и LF fixtures дают 3/3 PASS без изменения Git
config. Workbench pin обновлён к actual source; все 13 ordinary-market behavior
tests PASS, assertions не удалены. Product source/science остаются прежними.
