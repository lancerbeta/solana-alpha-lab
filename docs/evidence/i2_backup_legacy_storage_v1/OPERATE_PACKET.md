# I2 — staged OPERATE packet

Статус: PREPARED, NOT_AUTHORIZED. Единственный execution contract:
`docs/tasks/I2_BACKUP_LEGACY_STORAGE_V1.md`; единый PRD/SSD — `source-contract.md`.
Этот пакет поставляется вместе с reviewed code и completion binding. Конкретный
producer SHA берётся из успешного guarded merge/post-merge receipt, а не из даты
или имени ветки. Каждая runtime запись остаётся в operational plane.

## 1. Первое разрешение: установка и доказательство обычного backup

После merge сформировать exact OPERATE scope: target merged SHA, actual live SHA,
host/root identity, разрешённые deploy/backup units, независимый sink и upper
bounds времени/IO/места. Сохранить состояния всех участвующих services/timers;
отдельно считать armed B и её activation timer. Установку проводить существующим
`scripts/factory_live_release.py` по `docs/operator/FACTORY_REMOTE_HOST.md`.

До install выполнить bounded metadata readback:

- protected A/B: schedules, authority/storage envelopes, activation/tail state;
- APPLIED profile/control/revision/revoke; managed children, shared account
  membership, daily/rolling/lifetime debits; никаких новых grants или ручных окон;
- исходные DB/WAL/RDP и staging/sink на каждом filesystem, last-good checkpoint,
  source-owned current/pending/release/active-plan cold cache references, pending
  backup intent, foreign lock, actual due/rollover/B timing;
- текущие installed unit hashes/cadence, effective freshness/retention и версия
  reader. Старый бинарник после managed child не является rollback-кандидатом.

Если измеренная capture/reclaim щель пересекает due или фактическую B/rollover
границу, перенести техническую операцию. Не останавливать business intake ради
deploy и не менять frozen root/envelopes. При unresolved writers/backup дождаться
штатного завершения либо вернуть конкретный blocker.

Deploy сохраняет baseline policy revision 1: CURRENT data-age 86400s, RPO 24h;
maintenance без approved policy выключена. Затем разрешённый обычный caller:

```sh
cd /opt/solana-alpha-lab
uv run --locked --managed-python python -B scripts/factory_offhost_backup_copy.py --mode daily
```

Штатный daily/weekly caller автоматически повторяет `WRITER_BUSY` с шагом 30s
в пределах 120 минут ожидания. Это покрывает известный weekly upload до 110 минут
при weekly00:30/daily00:45 UTC, сохраняя прежние timers, transport budget и
RPO24h. Capture/upload время считаются отдельно; постоянный CURRENT не обещается.
Ожидающий daily проверяет actual bytes нового завершённого weekly checkpoint и
durable pointer и принимает его без второго capture/upload. Pending operation
всегда продолжается с прежними identity/ZIP. Чужой lock не снимать.
При исчерпании — exit2, `COPY_FAILED / OFFHOST_BUSY_RETRY_EXHAUSTED` и точный
resume argv/pending SHA в одном из двух ограниченных scheduler receipts рядом
с existing receipt. Last-good сохраняется; последующее завершение active owner
снимает incident. До install проверить actual unit/drop-in timeout и cadence.
При failed/unknown upload следующий запуск продолжает тот же pending
operation/ZIP; ручное удаление intent запрещено.
Проверить реальные entry compression, logical inventory, snapshot/start/upload/
verify clocks, actual attempted/verified upload bytes и last-good/attempt health.

Исторический mutable-only full от producer `b3fb9d8…` может не содержать control
ResearchEvents. Новый reader проверяет hashes/membership каждого raw звена, но
final control closure — после всех deltas. Upgrade сохраняет old bytes/hashes;
обычный новый daily доставляет closure. Приёмка ниже обязана восстановить actual
legacy full + новую delta. Неполный standalone full или final missing event
получает отказ без marker; один STORED-repack нового I2 full это не доказывает.

Первоначальная независимая приёмка использует точный скачанный checkpoint JSON
и **новый** явно выделенный isolated root с учтённым filesystem peak:

```sh
uv run --locked --managed-python python -B scripts/factory_offhost_backup_copy.py \
  --mode verify-remote-restore --checkpoint "$EXACT_CHECKPOINT_JSON" \
  --isolated-root "$NEW_ISOLATED_RESTORE_ROOT"
```

Значения переменных — exact artifacts этой операции; отсутствие любого binding
блокирует запуск. Проверить raw inventory до marker, final unresolved marker,
profile/revoke/counters/children/authority events, publication recovery и OPEN
operational/paper obligations. Не запускать восстановленный stale collector до
штатной reconciliation. Это разрешает принять только `PACKAGING_LIVE_PROVEN`.

## 2. Подготовка exact destructive APPLY

На consistent изолированной копии уточнить известный benchmark: exact legacy
scope и body bytes; retained membership/denominator/accounting/provenance;
actual source-owned release/export/raw/member closure и exclusions. Unknown
ownership остаётся protected. Оригинальные decoded JSON bytes сохраняются до
изменения; это не исходный HTTP response.

Native entry для bounded чтения:

```sh
uv run --locked --managed-python python -B scripts/observation_schedule_retention.py status \
  --store "$EXACT_OPS_STORE" --max-rows 256 --max-bytes 8388608 --max-wall-seconds 1
uv run --locked --managed-python python -B scripts/observation_schedule_retention.py plan \
  --store "$EXACT_OPS_STORE" --policy "$PROPOSED_POLICY_JSON" --output "$NEW_PLAN_JSON"
```

Status/plan открывают существующий store read-only с WAL-aware чтением. Metadata
commissioning, создание cold artifact и independent upload являются отдельными
явно перечисленными разрешёнными действиями OPERATE scope. `archive` создаёт
только LOCAL_REHEARSAL proof; оно не заменяет independent remote readback.

Перед предложением APPLY пакет должен содержать exact source/schema/root
identity, policy revision/hash, cutoff/high-watermarks/cursor, retirement hashes,
candidate hashes/bytes и protected exclusions; source-owned closure; immutable
cold locator/object hashes и независимый restore proof; retained checkpoint
reference graph. Cold archive находится вне routine source selection и остаётся
pinned до отдельного доказанного source/I4 disposition. Срок не выводится из
возраста папки, факта download на ПК или маленького нового ZIP.

Reclaim rehearsal на recent copy измеряет DB/WAL и filesystem bytes, wall/CPU/
RSS/phase peak, все material key/ROWID/sequence/cursor fingerprints, неизменный
real data_root device/inode и следующий native writer. В production OPS обычно
является sibling observation_rdp; нельзя подменять frozen data_root его parent.
Составить finite maintenance window и rollback boundary.

## 3. Второе разрешение: exact retirement, reclaim и одна policy

Одно согласованное решение может покрыть совместимые действия ниже, только если
их exact hashes, scopes, targets, budgets и остановки уже связаны в runtime packet.

1. Установить exact disallow-resume retirement и policy по их approved SHA256.
   Сохранить original provider/scientific states, clocks, occurrence IDs,
   membership/denominator, accounting и A/B/managed authority.
2. Применять только exact archive-bound plan bounded chunks через `apply
   --plan ... --approved-sha256 ... --i-understand-apply`. Candidate/dependency/
   policy drift даёт отказ и новое чтение; unrelated active writes не разрешают
   расширить scope. Durable progress продолжается после restart без двойного effect.
3. До physical switch quiesce всех actual writers/publication owners, сохранив
   prior timer/service states. Не использовать `collection-stop-intake` как
   техническую остановку. Снять **final current** pre-maintenance recovery set
   и rebind plan к фактическим новым counters/children/cursors.
4. `reclaim-plan` связывает actual source и real data_root. `reclaim-apply`
   требует exact plan hash, independent recovery proof, подтверждённый quiesce
   и explicit apply flag. Rehearsal DB никогда не заменяет live DB. Native
   rebuild сохраняет implicit ROWID, sequences, schema/indices и all row values.
5. При interrupted switch использовать `reclaim-resume`/`reclaim-rollback` с
   exact plan identity при остановленных writers. Возврат old DB допустим лишь
   до durable resume decision. После неё — forward recovery того же решения;
   old rollback запрещён, даже если cleanup был прерван до возврата services.
6. Проверить source/control/accounting/root bindings и восстановить прежние
   services/timers. Подтвердить штатный tick → SEARCH → publication, source
   clocks, calls/debits и coverage/gaps. Никакого backfill новыми market calls.
7. Создать один новый компактный weekly/full baseline через existing caller,
   независимо восстановить exact checkpoint и подтвердить: retired bodies
   отсутствуют в logical routine payload, DB-file физически уменьшен.

Для `retire` и `policy` approved SHA256 — digest **всего JSON document** после
канонизации existing owner: UTF-8, `sort_keys=True`, `separators=(",", ":")`,
`ensure_ascii=False`. SHA исходного pretty-printed файла не подходит. Эти
read-only команды из repository root печатают digest exact inputs; значения включаются в runtime
packet для отдельного approval, сам расчёт разрешения не даёт:

```sh
uv run --locked --managed-python python -B -c 'import json,sys;from pathlib import Path;sys.path.insert(0,"src");from solana_alpha_lab.factory.observation_schedule_retention import policy_sha256;print(policy_sha256(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))))' "$EXACT_RETIREMENT_JSON"
uv run --locked --managed-python python -B -c 'import json,sys;from pathlib import Path;sys.path.insert(0,"src");from solana_alpha_lab.factory.observation_schedule_retention import policy_sha256;print(policy_sha256(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))))' "$PROPOSED_POLICY_JSON"
```

После exact approval установить документы через существующие native commands.
Оба используют `--input`; `--policy` служит только для чтения proposed policy
командой `plan` выше:

```sh
uv run --locked --managed-python python -B scripts/observation_schedule_retention.py retire \
  --store "$EXACT_OPS_STORE" --operation-mode OPERATE \
  --input "$EXACT_RETIREMENT_JSON" --approved-sha256 "$APPROVED_RETIREMENT_SHA256" --i-understand-apply
uv run --locked --managed-python python -B scripts/observation_schedule_retention.py policy \
  --store "$EXACT_OPS_STORE" --operation-mode OPERATE \
  --input "$PROPOSED_POLICY_JSON" --approved-sha256 "$APPROVED_POLICY_SHA256" --i-understand-apply
```

Для `apply` и `reclaim-apply` approved SHA256 — machine `plan_id` exact plan:
owner хеширует каноническое содержимое **без поля `plan_id`**. Полный file SHA
или digest документа вместе с `plan_id` не подставляются. `apply` дополнительно
проверяет установленную approved policy/revision.

Обязательный physical-path блок после разрешённого quiesce. `FINAL_CURRENT_PROOF_JSON`
создан независимым restore **последнего current capture после остановки writers**;
старый rehearsal proof не допускается. Все roots берутся из проверенного live
runtime/config, а не из defaults CLI. `APPROVED_RECLAIM_PLAN_SHA256` равен
`plan_id` прочитанного exact plan и входит в отдельно утверждённый APPLY scope.

Сначала получить native cold record из независимого remote restore — без
ручного конструирования proof JSON. `FINAL_REMOTE_RESTORE_PROOF_JSON` — exact
durable `.remote-restore-proof.json` нового final-current isolated cache:

```sh
uv run --locked --managed-python python -B scripts/observation_schedule_retention.py register-checkpoint-archive \
  --store "$EXACT_OPS_STORE" --factory-root "$EXACT_FACTORY_ROOT" \
  --isolated-root "$FINAL_CURRENT_ISOLATED_CACHE" --input "$FINAL_REMOTE_RESTORE_PROOF_JSON" \
  --output "$FINAL_CURRENT_PROOF_JSON" --i-understand-apply
```

Команда повторно реконструирует verified objects во временный owned scratch,
сравнивает actual SQLite contents с cold copy и регистрирует source-owned pin.
Учесть ещё одну raw copy в phase peak этой отдельной операции. Подмена standalone
SQLite при прежних ZIP/checkpoint и пересчёт собственного inventory отказываются.
Отсутствующий source UUID или несовпадение current business rows/counters/
admissions означает refusal и новый final-current checkpoint; старый до retirement
или до последнего writer proof не подходит. Mechanical registration/restore-marker
bytes не подменяют causal comparison. После этого строится exact reclaim plan:

```sh
uv run --locked --managed-python python -B scripts/observation_schedule_retention.py reclaim-plan \
  --store "$EXACT_OPS_STORE" --operation-mode OPERATE \
  --factory-root "$EXACT_FACTORY_ROOT" --data-root "$EXACT_FROZEN_DATA_ROOT" \
  --max-wall-seconds 60 --output "$NEW_RECLAIM_PLAN_JSON"
uv run --locked --managed-python python -B scripts/observation_schedule_retention.py reclaim-apply \
  --store "$EXACT_OPS_STORE" --operation-mode OPERATE \
  --factory-root "$EXACT_FACTORY_ROOT" --data-root "$EXACT_FROZEN_DATA_ROOT" \
  --plan "$NEW_RECLAIM_PLAN_JSON" --input "$FINAL_CURRENT_PROOF_JSON" \
  --approved-sha256 "$APPROVED_RECLAIM_PLAN_SHA256" --writers-quiesced --i-understand-apply
```

На обычном успехе `SWITCHED_AWAITING_NATIVE_READBACK` services всё ещё остановлены.
Read-only native fingerprint, keys/ROWID/sequence/cursors, control/accounting и
data_root identity должны совпасть с plan. Затем обязательный explicit переход:

```sh
uv run --locked --managed-python python -B scripts/observation_schedule_retention.py reclaim-resume \
  --store "$EXACT_OPS_STORE" --operation-mode OPERATE \
  --factory-root "$EXACT_FACTORY_ROOT" --data-root "$EXACT_FROZEN_DATA_ROOT" \
  --plan "$NEW_RECLAIM_PLAN_JSON" \
  --approved-sha256 "$APPROVED_RECLAIM_PLAN_SHA256" --i-understand-apply
```

`reclaim-resume` самостоятельно проверяет native fingerprint и file identities,
durably фиксирует необратимое решение, удаляет только точные owned rollback/new
DB и их sidecars по сохранённому cleanup manifest и завершает `FINALIZED`.
Квитанция содержит actual byte disposition; небольшой terminal intent остаётся,
старые DB не образуют бессрочный HOT-хвост. Повтор того же resume после interruption
дозавершает cleanup идемпотентно. После rollback аналогичный terminal —
`ROLLBACK_FINALIZED`. Unknown/changed staging не удаляется.

Следующий backup повторно проверяет тот же native reclaim guard перед selection,
writer fences и SQLite capture. Unfinished intent, orphan staging либо чужой
terminal inode дают `BACKUP_RECLAIM_RECOVERY_REQUIRED` до capture/ZIP. Проверенная
terminal квитанция привязана к inode этого host и в portable payload не входит;
исключение не разрешает пропустить произвольный файл. В production acceptance
после finalized reclaim включить ordinary backup → independent restore → native
reconciliation → следующий writer с сохранением UUID/ROWID/sequence/counters.

Durable `ALLOCATING` intent записывается до выделения new DB. Native writable
entrypoints, включая reboot collector tick и уже открытые writers, проверяют
reclaim guard до SQLite creation/mutation. При незавершённом switch они получают
`RECLAIM_RECOVERY_REQUIRED`; исчезнувший existing source не bootstrap-ится.
Это техническая блокировка до exact recovery, без изменения RUN/profile/grants.
Только после successful finalized resume возвращаются prior services/timers и
проверяется следующий native writer. До resume rollback доступен тем же CLI
`reclaim-rollback` с exact roots/hash и explicit apply flag. После новых записей
нельзя откатить old DB; forward repair сохраняет current.

| Durable phase после interruption | Допустимый следующий шаг при quiesced writers |
|---|---|
| первая fsynced intent.tmp, final ещё отсутствует либо относится к прошлой terminal operation | exact rollback проверяет plan/roots/source inode/native fingerprint, публикует initial ALLOCATING и завершает штатный cleanup; resume до allocation отказывает |
| первая intent.tmp содержит torn/неполный JSON | `reclaim-rollback --plan "$NEW_RECLAIM_PLAN_JSON"` с теми же exact roots/hash; self-hashed plan и current native fingerprint восстанавливают initial intent только без new/rollback stages. Без plan — `RECLAIM_INITIAL_PLAN_REQUIRED`; ручное удаление не требуется |
| ALLOCATING / owned incomplete new | exact rollback; original current, unfinished new удаляется только после проверки ownership |
| PREPARED | exact resume завершает switch либо exact rollback сохраняет original |
| между rename и intent update / ORIGINAL_MOVED | exact recovery определяет phase по inode identities; resume либо rollback |
| SWITCHED | read-only invariants → resume либо exact rollback |
| RESUMED / cleanup interrupted | только тот же resume; native writers всё ещё заблокированы, cleanup дозавершается |
| FINALIZED / есть новые записи | writers разрешены; old rollback запрещён, small receipt сохраняется |

Recurring policy разрешает конкретные legacy scopes и/или managed lineages,
classes, terminal retirement conditions, реальные frozen minimum ages,
source/cold proofs, max rows/bytes/wall/cadence, pressure/due/restore fences,
retained restore points и pause/resume. Её hash/revision утверждаются один раз;
будущие children проходят те же source-owned predicates автоматически. Нет
ежедневного списка IDs, ручного агента или `record-backup`.

Изменение policy требует нового approved SHA и монотонной revision. Install
атомарно проверяет старый bounded intent, candidates, cold proofs и выполненные
effects; сохраняет прежний progress как `SUPERSEDED_POLICY` и original provenance/
ROWIDs/pins, отменяет только неприменённый остаток и перезапускает bounded scan по
новой policy. Disable → enable не применяет старый remainder. Ordinary caller
также восстанавливает stale plan, оставленный предыдущим бинарником. Настоящий
candidate/archive/effect conflict остаётся FAILED/refusal; автоматического
пересоздания вокруг него нет. Возраст, clocks и approvals не сбрасываются.

Pending cold refresh также переходит на approved policy после bounded metadata/
source/pin checks, без deep ZIP IO под install lease. Exact checkpoint и pins
сохраняются; restore/register по новым limits остаётся обязательным byte oracle.
Disable приостанавливает тот же target, enable продолжает под новым scope.
Несовместимый cold root или refresh budget сохраняет target как `BLOCKED_POLICY`
с FAILED, без новой cache generation. Исправление — допустимая exact policy
revision; не удалять pending/pins вручную. Повреждение identity/source/pins даёт
refusal. Same-second backup terminal failure также виден через existing watch;
снять его может подтверждённый success того же checkpoint.

Перед сменой/disable policy учитывать actual retained cold cache по durable
current/pending/release/active-plan references, включая прежний root. Новый
placement не освобождает old bytes. Пересечения с OPS/RDP/sink/cache считаются
один раз; unsafe/внешняя/unresolvable ссылка даёт `UNKNOWN` и блокирует выдачу
численного capacity допуска до разрешения topology, без ручного обнуления refs.

Caller — existing daily/weekly offhost backup command после завершения checkpoint;
native maintenance вновь берёт backup-plane lock до OPS fence и уступает due,
foreign writer, restore, RAM/IO/CPU pressure. Ошибка optional maintenance
сохраняет backup/last-good и источники, создаёт один incident через existing watch.
Отказ bounded selection до APPLY также сохраняет typed `FAILED/last_reason`:
например, `CALL_OWNER_SCOPE_BUDGET_REFUSED` требует разбора source consumer links
и отдельно approved policy revision, а не автоматического расширения бюджета.
Last-success/cursor, prior effects и pins сохраняются; transient busy или смена
policy/plan дают `YIELD` без перезаписи более нового состояния. Проверить этот
durable outcome через fresh operational packet/watch и TEST incident/recovery.
После APPLY caller повторно сверяет policy, exact plan и durable maintenance
state под native transaction. Если другой caller уже изменил их, старый outcome
уступает с `POLICY_CHANGED`, `ACTIVE_PLAN_CHANGED` или `MAINTENANCE_STATE_CHANGED`;
новые intent/incident/cursor и выполненные effects остаются сохранены. Продолжать
обычным caller, не удалять новый plan и не сбрасывать health вручную.
Включение caller/policy требует installed readback; Git template не доказывает
commissioning. Daily VACUUM не включать.

## 4. Freshness decision внутри commissioning

Рекомендуемый вариант после измерения package/upload/verify: policy revision 2,
CURRENT **data-age 108000s (30h)**, RPO **30h**, existing daily cadence;
DEGRADED upper bound остаётся 172800s. Допустимо лишь если измеренные 24h cadence
+ work + margin укладываются в 30h. Поля конфигурации должны согласованно
измениться после exact approval; schema отвергает 30h freshness с RPO24h.
APPLIED managed profile и его grant hash не редактируются. Его собственный
max-age продолжает ограничивать effective threshold вместе с backup owner.

При сохранении owner hard24h выбрать одну измеренную более частую cadence и
посчитать дополнительный traffic/IO; расписание без approval не менять.
IN_PROGRESS не омолаживает last-good и не даёт бесконечной grace. Failed/stalled,
skipped day, reboot retry, future clock, weekly/daily overlap и UTC boundary
проверяются отдельно. Длительности используют monotonic clock.

## 5. Pruning и финальная приёмка

Перед remote deletion использовать `factory_offhost_backup_copy.py --mode
plan-prune` с bounded exact object inventory, retained checkpoints и source-owned
cold/scientific/pending pins. Новая компактная delta старой full не отменяет
зависимость от этой full. Удаление требует exact plan hash, независимого remote
restore retained chains и dedicated `--authorize-remote-delete`; обычные callers
остаются copy-only. Ни wildcard, ни `sync --delete` не применяются. Первый
remote cleanup можно отложить лишь при доказанном runway; pins сохраняются.
`--restore-proof-json` и для plan, и для apply указывает на durable
`cache/.remote-restore-proof.json`, созданный actual independent restore.
Его SHA256 входит в approved plan; подстановка JSON с `verified:true` не
принимается. Apply заново реконструирует retained bytes и проверяет SQLite;
дополнительная временная raw copy в `.prune-verify` входит в phase peak.

Итог I2: один ordinary backup cycle и один ordinary bounded maintenance cycle
после restart при работающем collector, сохранённые A/B/profile/counters/C1/C2,
actual DB/WAL/volume reduction, no retired routine bodies, new last-good и
verified restore, delivery incident/recovery через existing TEST path при
изменённых watch consumers. Пока natural cycle не произошёл — точный
`LIVE_PENDING_*`/`AWAITING_ROUTINE_BACKUP`, полного I2 DONE нет.

Отбивка — один `OWNER_READOUT.md` по §14. Модель 7/30/180d использует измеренный
incoming growth и HOT/COLD/checkpoint retention, реальные overlaps и file/inode
counts. Непокрытые I4 pins не считать удалёнными. Что не повторять: baseline
sampling benchmark, I1 production import, C1/C2 research, ручные окна или daily
owner approval.
