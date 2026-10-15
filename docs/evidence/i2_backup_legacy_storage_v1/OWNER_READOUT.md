# I2_BACKUP_LEGACY_STORAGE_V1 — Stage A

**OUTCOME: CODE_READY_RUNTIME_PENDING** при PASS независимых reviews, exact-head
CI и machine merge-readiness, связанных `completion.json`. Это software outcome
всего I2: snapshot, full/delta recovery, cold retirement, physical reclaim и
обычная bounded maintenance. Полного live I2 DONE пока нет.

FACT: base `3ff9df44331d8063274132c3da7022e46d859d92`; candidate content связан
implementation inventory в `completion.json`, финальный delivery head — exact
head PR/merge-readiness receipt. Source input SHA256
`a63241c261748dca5a271d0e3f99b7c22400fa72d786c934b6bf68e2989c6b80`.
Observed 15.10.2026: изолированные synthetic native stores, production checkpoint
не загружался. Policy в Git: revision 1 / CURRENT data-age 24h / RPO24h;
maintenance default-off. Frozen A/B, APPLIED profile, grants/shared debits,
C1/C2 и научные bytes production в этой работе не изменялись.

## Review follow-up #407

Owner review `PATCH_BEFORE_MERGE` принят отдельным дополнением к исходному
контракту (`review-follow-up.md`, original SHA256
`778ca30b1be380455720fd4f7f80afb4bce77a0b0df0a2b7eeb14f093ebb91b3`).
Каждый P1 сначала воспроизведён на native disposable stores; подробные команды,
trace и raw readback bindings — `proof.json / review_follow_up`. Новый PR,
production fault injection и повторный аудит I1/I3 не потребовались.

| Finding | Конкретное ДО | Owning repair и независимое ПОСЛЕ |
|---|---|---|
| P1-1 legacy full → new delta | Native ACTIVE/DRAINING и actual full/chain из Git producer `b3fb9d8…`: fresh restore падал `RESEARCH_STORE_NOT_PRESENT` до delta | Raw-link checks сохранены; delta → raw verify → final control verify → marker. Raw SQL31 таблиц/ROWID, 9/11 файлов и исходные events/clocks совпали. Standalone incomplete/final missing event — DENY, marker0 |
| P1-2 DEFERRED | Обычный CLI при native lease: exit0/DEFERRED, после release checkpoint не возникал | Тот же caller автоматически retry busy ≤120min, шаг30s; release завершает checkpoint без второй команды. Backup-lock retry сохраняет exact pending; weekly/daily дают один capture/ZIP/checkpoint. Exhaustion exit2 с incident и exact resume; last-good сохраняется, active owner success снимает incident |
| P1-3 reboot до resume | Kill между rename/intent и ORIGINAL_MOVED: ordinary writer создавал пустой main; NEW/SWITCHED открывал store до WRITER_BUSY; rollback bytes оставались после resume | Intent до allocation, native writable guard; actual fresh collector tick и already-open writers отказывают до mutation, отсутствующий main остаётся absent. Exact resume/rollback сохраняет source UUID, ROWID317, debits19/271. Finalized resume удаляет owned rollback/staging, сохраняет small receipt; после новых writes old rollback запрещён |
| P1-4 policy revision | После child process death на втором candidate progress1/3; approved narrower revision давала 4×FAILED/PLAN_STALE_POLICY с тем же intent | Atomically superseded intent, прежний progress/effect/provenance/cold сохранены; fresh ordinary caller продолжает под новой policy, excluded scope остаётся HOT. Disable/enable и previous-binary policy проходят; candidate/effect corruption остаётся отказом/FAILED |

Production gate для всех четырёх остаётся staged: actual reader/units/drop-ins и
cadence, native ordinary backup/maintenance, protected state и Linux filesystem
readback в exact разрешённом OPERATE. Синтетические kill tests не являются
fault injection на VPS или доказательством power-loss поведения конкретного диска.

На пересечении P1-1/P1-3 воспроизведён дополнительный native дефект: full recursive
backup переносил `FINALIZED` intent с исходным inode; restore проходил, следующий
writer получал `RECLAIM_RECOVERY_REQUIRED`. Теперь backup использует общий native
guard, отказывает до capture при unfinished reclaim и исключает только проверенную
terminal inode-bound квитанцию. Actual nested full и sibling mutable restore
сохраняют raw SQL/ROWID/sequence; после reconciliation новый writer создаёт event89
после old77/sequence88. При rename gap main остаётся absent, capture calls0/ZIP0;
чужой terminal inode также DENY. Production backup после finalized reclaim остаётся
частью того же staged acceptance.

Независимый code review нашёл ещё первую durable `.intent.json.tmp` до публикации:
guard отказывал, recovery получал `FileNotFoundError`. Теперь exact rollback
проверяет plan/roots/source inode/fingerprint и принимает только initial
`ALLOCATING` без staged DB. Отдельный kill-process → обычный collector DENY без
mutation → штатный CLI rollback → writer PASS проверен для первой и следующей
операции. Wrong approval/premature resume отказывают; ручное удаление не требуется.
Torn first JSON также восстанавливается тем же CLI с сохранённым approved
`--plan`: проверяются self-hash/source roots/inode/native fingerprint и отсутствие
stages; без plan — typed `RECLAIM_INITIAL_PLAN_REQUIRED`. Partial-write kill
проверен для первой и следующей операции, исходные UUID/ROWID/counters сохранены.

Тот же review выявил same-second incident race и pending cold-refresh policy
deadlock. Raw JSON/health oracle теперь сохраняет terminal exhaustion поверх
`IN_PROGRESS`; exact same-checkpoint success снимает incident. Реальный pending
checkpoint после narrower revision до ремонта давал 4×COMPLETE при DISABLED
refresh и неизменных HOT bodies. После bounded metadata reconciliation тот же
checkpoint/pins проходят ordinary restore/register и retirement под новой policy.
Disable/enable сохраняет target; несовместимые cold-root/refresh limits дают
`BLOCKED_POLICY/FAILED`, повреждение identity/source/pins остаётся отказом.

Следующий архитектурный falsifier выявил потерю failure до APPLY: native planner
при `max_rows=1` отказывал `CALL_OWNER_SCOPE_BUDGET_REFUSED`, но durable health
оставался старым `READY/COMPLETE`, и watch не создавал incident. Owning boundary
теперь сохраняет typed `FAILED` под lease после проверки актуальных policy/plan.
Fresh ordinary caller → raw reopen → actual operational packet/watch показывает
`MAINTENANCE_FAILED`; prior effect, ROWID/clocks, last-success, cursor, cold pins
и backup last-good сохранены. Отдельно approved revision с `max_rows=2` позволяет
штатно продолжить. Busy/изменившаяся authority дают `YIELD`, unexpected exception
сохраняется как `OPTIONAL_MAINTENANCE_FAILED` без raw sensitive text.

Отдельный independent interleave после actual APPLY обнаружил stale finalizer:
старый caller удалял новый peer plan и заменял новый `FAILED` на `READY`. Успешная
и ошибочная finalization теперь под одной native transaction сверяют approved
policy, exact active plan и pre-apply maintenance state. При расхождении —
`YIELD/POLICY_CHANGED`, `ACTIVE_PLAN_CHANGED` либо `MAINTENANCE_STATE_CHANGED`;
при foreign lease — `WRITER_BUSY`. Новые plan/failure/cursor сохраняются вместе
с уже выполненными effects/progress, ROWID/clocks и cold pins; watch продолжает
видеть peer failure. Проверены separate native peer store и обе finalization
ветки, включая unchanged-policy/same-plan interleave.

Footprint consumer после approved `cold` → `cold-v2` раньше показывал
460998 → 0 bytes, хотя зарегистрированная cache оставалась на диске. Он теперь
считает source-owned current/pending/release/active-plan references вместе с
текущим placement, дедуплицируя пересечения с OPS/RDP/sink и другими cache.
В финальном native fixture actual460997 bytes сохраняются в расчёте до/после revision
и disable; source record/files не меняются. Невалидная, unsafe либо внешняя по
отношению к factory ссылка сохраняет `UNKNOWN`, не превращается в zero footprint.
Это isolated sizing oracle; production topology/runway по-прежнему не измерены.

Owner UX также проверил actual команды единственного OPERATE packet: canonical
JSON digest из existing owner принимается `retire`/`policy`, SHA pretty-file
отказывается. Из документа запускаются обе read-only digest команды и exact
`--input` install argv; raw SQL подтверждает exact documents. Для plan approval
отдельно указан machine `plan_id`, исключающий собственное поле. Это isolated
recipe proof; runtime input hashes и approval остаются отдельной authority.

## Проверенный эффект и предел чисел

| Величина | BEFORE → AFTER | Что именно измерено |
|---|---:|---|
| Whole checkpoint STORED → DEFLATE1 | 2 188 785 → 18 760 bytes, 116,67× | одни captured bytes; намеренно хорошо сжимаемый fixture, не production ratio |
| Native OPS DB-file после retirement/reclaim | 2 494 464 → 397 312 bytes, 6,28× | actual CLI, ROWID313, сохранённый data_root inode |
| Retired decoded body | 2 097 175 → 0 bytes | один exact архивированный synthetic legacy call |
| Call payload → surviving provenance | 2 097 376 → 614 bytes | source status/clocks/IDs сохраняются; это decoded JSON, не исходный HTTP |
| Closed WAL | 0 → 0 bytes | замер при закрытом store; concurrent WAL и counters проверяются другими сценариями |
| Capture staging / staging+ZIP | 2 187 501 / 2 206 261 bytes | 3 staging files включая owner marker; upload-ready staging=0, ZIP=18 760 |
| Actual upload / retained remote bytes | UNKNOWN / UNKNOWN | network заменён exact byte transport; production upload не выполнялся |
| Collector delay / scientific gaps | UNKNOWN | native gapped fixture намеренно сохраняет MISSED; production coverage не измерялась |

Capture+pack+local verify: около 0,07s wall / 0,06–0,08s CPU. Fresh-process peak
RSS compression fixture — 43 970 560 bytes; actual native CLI rehearsal interpreter
около 48 MB, CLI-child peak отдельно измерен до 48 979 968 bytes. Это individual
process peaks, не сумма одновременно работающих процессов и не Linux acceptance.
Plan→apply→reclaim→resume→next writer: около 1,6s wall. Sampled owned-tree peak
capture/restore — 8 822 740 bytes / 10 files; retirement/CLI — 12 555 872 / 15.
2ms sampling даёт observed lower bound, не строгий peak guarantee. Native reclaim
в cutover временно сохраняет rollback+intent: 1→3 hot files; успешный exact resume
теперь финализирует owned cleanup, оставляя DB+small receipt (1→2 hot files).
Отдельный crash fixture подтвердил release389120 bytes original+SHM и отсутствие
rollback/new; это не production volume reclaim. Actual allocated volume/inodes
на production — `LIVE_PENDING_TOPOLOGY_AND_RECLAIM`; DB-file shrink доказан.

Известный benchmark переиспользован: reported OPS 5 165 555 712 bytes,
freelist 122 880 pages, STORED около 5,225 GB и 60–110 минут upload. Это исходная
отбивка/локальный benchmark, не свежий host readback. Его 48MiB sample ratio6,04
не переносится на целый checkpoint. Гипотетические 0,871GB и 10–18 минут network
при 6× остаются моделью; production SLA и «94% reclaim» не заявлены.

## Correctness / automation / recovery

- Один SQLite capture и frozen path membership идут в inventory и ZIP. Native
  authority/state events, open publication jobs и partition manifests входят
  в causal closure. WAL/SHM/journal не могут повторно наложить post-capture bytes.
  Authoritative membership перечисляется внутри writer fences; предварительный
  проход служит только SQL admission. Publication, появившаяся до fence, сохраняет
  исходные manifest ID и availability при более позднем recovery.
- Actual base-producer mutable-only full и новая DEFLATE-delta проверяют extracted
  membership/size/SHA каждого шага и final inventory; marker ставится последним.
  Missing/reordered delta, duplicates/path escape/sidecars/inventory mismatch
  отказывают. После restore native writer ждёт reconciliation.
- Immutable pending backup переживает unknown upload/kill; обычный caller сам
  повторяет transient busy в конечном окне и объединяет weekly/daily overlap;
  exhaustion виден отдельным incident с exact resume. Повтор продолжает
  тот же ZIP/checkpoint. Pointer следует verified checkpoint; last-good отделён
  от failed attempt. A→B→A weekly сбрасывает obsolete deltas.
- Retirement требует exact scope, запрета resume, source-owned cold/raw closure,
  frozen minimum age и candidate/dependency revalidation. Active/tail/UNKNOWN,
  publication/export/capture/account dependencies защищены. Logical retired
  body=0 не подменяется freelist или маленьким ZIP.
- Cold registration один раз заново восстанавливает actual verified objects и
  сравнивает содержимое OPS с регистрируемой копией. Совпадения UUID/integrity
  или самостоятельно пересчитанного inventory недостаточно. Перед reclaim
  fresh independent proof после logical apply должен совпасть с final-current
  causal rows/counters/admissions; старый proof отказывается.
- Native reclaim сохраняет all row values, implicit ROWID gaps, sequence88→89,
  cursors и actual sibling/nested data_root identity. Durable pre-allocation guard
  переживает reboot/rename windows, не даёт bootstrap/reset SQLite и блокирует
  native writes до final recovery. Resume финализирует owned cleanup; после
  durable resume decision и новых writes только forward repair.
- Одна policy установлена до двух будущих managed children. Real public CLI/tick
  довёл их до COMPLETE/TAIL_COMPLETE; ordinary mutable-only backup, source-verified
  HOT90 raw archives и обычный caller после restart дали independent fake-remote
  restore/cold registration и compaction. Без daily IDs, manual backup registration
  или новых timers. Profiles/children/control/shared counters/account membership
  остались byte/row-identical до/после maintenance.
- Rows/bytes/wall, indexed keyset cursors, pressure/due/restore/lock fences;
  bounded cache1 completed+1 pending. Protected prefix и future eligibility не
  теряются после restart; oversized body получает durable refusal и не скрывает
  поздние строки или FAILED health. Crash staging очищается только known-dead
  owner; unknown staging сохраняется и блокирует новую allocation.
- Prune связывает checkpoint reachability, pending/science/cold pins и durable
  independent restore artifact в approved hash. Apply повторяет реальный raw
  reconstruction/SQLite oracle и remote identity, требует отдельного delete gate.

Установленный production caller/policy и next routine run — `LIVE_PENDING_INSTALL`.
Нативные isolated cycles доказаны; production обычный backup/maintenance и
Telegram TEST incident/recovery ещё не выполнялись. Непройденные live части
остаются обязательными стадиями B/C, а не non-goals. Доставка через существующий
watch сохраняет отдельно source/data clocks, last-good, attempt и maintenance.

## Runway 7/30/180 дней

Production estimate на всех трёх горизонтах — **UNKNOWN**: нет свежих измерений
incoming RDP/provenance/cold growth, filesystem allocations, file/inode rate и
retained remote object graph. `MONTHS_RUNWAY_SUPPORTED` не заявлен.

Один измеренный planning scenario: семь native authored calls с 100 000-символьным
decoded field; SQLite рос в среднем на 102 400 bytes/input, incoming call payload
100 224 bytes/input, surviving provenance612 bytes/input. При **одном таком call
в день**, том же body shape и отсутствии extra obligations:

| Горизонт | Incoming payload | Surviving provenance после eligible retirement | Original cold payload, минимум при indefinite pin |
|---|---:|---:|---:|
| 7d | 701 568 | 4 284 | 701 568 |
| 30d | 3 006 720 | 18 360 | 3 006 720 |
| 180d | 18 040 320 | 110 160 | 18 040 320 |

Единицы — bytes. Это sizing при заданном потоке, не runtime/production прогноз.
До native minimum age тела остаются HOT: для fixture31d верхняя добавка call
payload после выхода на steady state примерно `31×100224`; real episode minimum
читается из frozen schedule (в pipeline11d), не заменяется значением fixture31d.
RDP/raw/scientific bytes, indices и backup amplification к этой таблице добавляются.

Рабочая модель: `resident_after + min(t,H)×g_hot + t×g_provenance +
cold_pins(t) + reachable_backups(t) + actual_allowed_overlap(t) + reserve`.
Для каждого filesystem считать отдельно; shared same-volume factory budget
остаётся conservative sum. File model: `N0 + t×f_scientific + retained_graph_objects
+ bounded_cache_files`; все production inputs UNKNOWN. Cache generation count
bounded, однако remote source pins не имеют придуманного TTL. Две retained
weekly points всё ещё требуют их full/delta closure. Prune verification добавляет
одну временную raw copy; cold registration также делает одну временную raw
reconstruction; reclaim — new DB+rollback. Независимые maxima не складываются.

I4 dependency: source-owned disposition/release для scientific raw/export/member
и cold pins, затем exact reachability prune. Пока owner/consumer не доказал конец
retention, cold сохраняется; при линейном доминирующем RDP/pins именно это точный
следующий lifecycle шаг. Нельзя выводить бессрочность из маленькой OPS DB.

AUTHORITY: выполнены только branch code/docs, disposable fixtures/rehearsal,
reviews и GitHub delivery. Не выполнены deploy/upload/live APPLY/reclaim,
maintenance enable, effective freshness/retention change или remote delete.

NEXT: exact owner merge phrase из machine readiness, guarded merge и post-merge
readback; затем один staged `OPERATE_PACKET.md` с exact runtime bindings и
destructive APPLY scope. Не повторять исходный sampling benchmark, I1 production
import, C1/C2 research, ручные collection windows или ежедневный approval.
NEXT_MODEL_EFFORT: ROUTINE_NO_SWITCH для merge/readback; runtime OPERATE требует
своей оценки по фактическому destructive scope.

## Обновлённый main

Main PR #406 (`3ff9df44`) включён обычным merge `8a62062d`; task v1.3
перепривязан к этой базе. Все 54 неагрегатных upstream blobs
сохранены точно, включая List A producer, научные contracts/history/evidence.
Общий Catalog объединён и пересчитан штатным generator. Legacy compatibility
по-прежнему проверяет actual producer b3fb9d8; исторический pin не переносится
на новую базу. Финальные reviews/CI/readiness относятся к новому кандидату.

## Whole checkpoint maintenance authority

Независимый architecture falsifier на `5238677b` показал: actual APPLY
сохранил первый effect, peer установил revision2 и FAILED в 12:00:01Z,
а поздняя ошибка старого refresh записала ARCHIVE_REFRESH_FAILED в 12:00:00Z.
Один native context теперь проходит всю цепочку maintenance → intent →
restore/register → cache release → outcome. Под lease/transaction сравниваются
source incarnation, policy, exact plan/state, pending/current/release checkpoint.
Изменение peer даёт typed YIELD, сохраняя его intent/incident/cursor, prior
effects, ROWIDs/clocks/pins и last-good; сеть не держит OPS lease. Неизменная
authority сохраняет genuine failure в health/watch и допускает ordinary retry.

Partial local cache deletion воспроизведён отдельно. Existing release token
до удаления фиксирует exact checkpoint/root inode/owner-intent SHA; retry
завершает cleanup даже после удаления intent/archive/index, лишь при этом
durable token. Подменённые inode/owner и active consumer отказывают. Pre-delete
scan ограничен approved wall budget и existing16384entry cap; CACHE_RELEASE_BUDGET
ничего не удаляет. Отдельный OS syscall нельзя жёстко прервать по wall clock.

Финальный targeted maintenance/pipeline/offhost набор: 77 tests, PASS,
1 existing skip, 77.561s; health/footprint/watch: 54 PASS, 4.370s; factory
static PASS. Наборы перекрываются с прежними; суммы не являются числом
уникальных tests. Native многопакетный ordinary путь завершил bodies
[3,3,2,2,1,1,0], одновременно retained cache generations=1. Production B/C
и Linux/filesystem/cadence/pressure acceptance остаются обязательными pending.

## Explicit CLI operation mode authority

Независимый OWNER_UX review на `05de45fd` воспроизвёл authority bypass:
explicit CLI `OPERATE` принимал rehearsal retirement, а следующий APPLY
удалял body без independent remote proof. Raw SQL сохранил ROWID313 и подтвердил
исчезновение original body. Режим теперь сверяется с точным approved документом
и применяемой authority до mutation; rehearsal proof не становится OPERATE
из-за выбора флага. Canonical approval digest не переписывается. Actual CLI
отрицательные и положительные native проверки, scope и результаты записаны
в proof.json. Один staged OPERATE packet описывает отказ и точный повтор.
Положительный native refresh/register → OPERATE retire/policy/plan/APPLY
выполнил 2 compactions с сохранением ROWID/source clocks. Семь focused checks
прошли за 8.720s, включая существующий полный CLI rehearsal. Factory static PASS.
Production B/C остаются обязательными pending.
