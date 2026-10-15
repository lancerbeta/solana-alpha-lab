# I2_BACKUP_LEGACY_STORAGE_V1 — Stage A

**OUTCOME: CODE_READY_RUNTIME_PENDING** при PASS независимых reviews, exact-head
CI и machine merge-readiness, связанных `completion.json`. Это software outcome
всего I2: snapshot, full/delta recovery, cold retirement, physical reclaim и
обычная bounded maintenance. Полного live I2 DONE пока нет.

FACT: base `b3fb9d8ecffbffda468dccabaa81ca3392da6f15`; candidate content связан
implementation inventory в `completion.json`, финальный delivery head — exact
head PR/merge-readiness receipt. Source input SHA256
`a63241c261748dca5a271d0e3f99b7c22400fa72d786c934b6bf68e2989c6b80`.
Observed 15.10.2026: изолированные synthetic native stores, production checkpoint
не загружался. Policy в Git: revision 1 / CURRENT data-age 24h / RPO24h;
maintenance default-off. Frozen A/B, APPLIED profile, grants/shared debits,
C1/C2 и научные bytes production в этой работе не изменялись.

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
сохраняет rollback+intent: 1→3 hot files до отдельного безопасного завершения
recovery. Эти bytes не объявлены освобождёнными. Actual allocated volume/inodes
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
- Mixed STORED-full/DEFLATE-delta reconstruction проверяет actual extracted
  membership/size/SHA каждого шага и final inventory; marker ставится последним.
  Missing/reordered delta, duplicates/path escape/sidecars/inventory mismatch
  отказывают. После restore native writer ждёт reconciliation.
- Immutable pending backup переживает unknown upload/kill; повтор продолжает
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
  cursors и actual sibling/nested data_root identity. Три cutover crash phases
  имеют rollback до resume/new writes; после новых writes только forward repair.
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
