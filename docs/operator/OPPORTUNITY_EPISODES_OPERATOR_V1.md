# OPPORTUNITY_EPISODES operator runbook V1

Contract: `docs/contracts/opportunity_episodes_jupiter_v1.md`.
Live lane: **DISABLED**. Nothing below activates collection; that is a separate
OPERATE commissioning decision (real protection assignment inventory pinned in
the schedule, host envelope, canary budget). Program and phase order:
`docs/design/SMIAL_JUPITER_OPERATING_BLUEPRINT_RUNBOOK_V1.md`; it grants no
authority for any later phase. Canary, deploy, provider calls, retention and
cleanup authority stay separate OPERATE decisions.

Route evidence: `CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-011` records the
parser/route qualification of the three category 5m routes and the single-object
search. It does not prove shared-account pace discipline, the batch-of-100
search shape, a memecoin mix or the absent/missing-mint path, and it grants no
call. Every observed route carries the pace overlap as a `known_failures` entry. The V1 validator and schema cap the
admission ceiling at 100 per UTC day; a higher ceiling is a future capacity
extension, not a supported profile.

## What it is

An episode is one committed admission of a Jupiter-nominated mint into the
collection. Its anchor `T0` is the admission commit instant (`NOMINATION_T0`),
not birth or pool creation. Each episode has a frozen 139-point schedule
(`E0` witness, 5-minute grid to 6 h, hourly to 72 h). Every committed
admission stays in the denominator; gaps stay explicit and never become zero.

## Capture host (producer) — OPERATE commissioning gate only, not an owner step in this slice

The schedule kind `smial.opportunity-episode-schedule` runs inside the ordinary
`scripts/observation_schedule.py tick --once` lane after register / authorize /
activate. Template: `configs/opportunity_episodes_jupiter_core_v1.yaml`; its
protection source is a deliberate placeholder, so admissions stay
`UNRESOLVED_SCOPE` until commissioning registers real assignment documents under
`<data_root>/protection/assignments/`.

* Stop intake early (safe drain), without waiting for `stops_admitting_at`:

```text
uv run --locked --managed-python python -B scripts/observation_schedule.py stop-intake --schedule-sha256 <sha> --activation-id <id> --runtime-config <runtime-config> --data-root <rdp>
```

  It closes new admissions at that instant through the same ACTIVE → DRAINING
  transition the natural boundary uses. Already committed episodes keep
  collecting and publishing, and the activation completes once every obligation
  is terminal. Rerun the same command after a crash: it is idempotent and
  repairs a missing evidence event. A paused activation must be resumed first.
  `pause` is not a stop-intake: it also stops the committed obligations. The
  schedule sha and activation id come from `observation_schedule.py status`;
  if a tick holds the writer lease the command answers `WRITER_BUSY`: retry.
* Activation ahead of `starts_at`: authorize and activate may precede the window and
  the ordinary observation timer may run meanwhile. Until `starts_at` every tick returns
  `NOT_YET_ACTIVE` (exit 0, zero provider calls, zero credential reads, no admission);
  the ACTIVE transition proof stays reachable and the first tick at or after the boundary
  proceeds with no pause/resume. `TICK_REFUSED_ACTIVE_TRANSITION_PROOF_UNAVAILABLE` still
  means the committed transition event is missing, foreign or unreadable.
* Recovery: the next tick republishes the outbox, recovers completed calls from
  the call ledger and turns intent-without-result into
  `ATTEMPT_OUTCOME_UNKNOWN`; it never re-requests a past slot.
* Scheduled dispatch uses the live clock at each due checkpoint, including
  checkpoints around publication/recovery and each category call. The canonical
  ordinary timer runs 15s after service exit, with `AccuracySec=1s` and zero
  randomized delay; changing code alone while keeping the old 60s unit does not
  commission this repair. No overlapping worker is required.
  Supported coverage assumes a stable UTC clock, one account lane, local
  cleanup/preflight/prelude each <=5s and batch bookkeeping <=1s. The maximum
  idle checkpoint gap is `15+1+3*5=31s`; during category work it is at most
  `15+3+5=23s`. Both are strictly less than the frozen 60s dispatch window.
  Episode calls use at most 15s of the existing bounded-response waiter;
  SEARCH shares remaining window time across remaining same-assigned batches,
  reserving their 3s account pace and local bookkeeping. Coverage is proved for
  canonical max_batch_size=100 and active cap <=400 (at most four batches);
  a smaller batch profile needs its own capacity proof. An insufficient reserved
  allowance never means the real window is closed: positive remaining time gives
  a bounded best-effort allowance, with the actual deadline guard still decisive.
  This is a conditional
  runtime guarantee: the waiter cannot preempt a host/GIL stall, and exhausted
  account/pace budgets are real typed failures. Reported
  `max_dispatch_checkpoint_gap_seconds` measures only gaps within one tick;
  it resets at process entry and cannot prove the idle/wake interval. Check
  the installed unit bytes and use journal service exit -> next start times
  to prove the ordinary idle gap <=16s (15s plus 1s accuracy), along with
  preflight/prelude/cleanup each <=5s. Use actual request timestamps, not only
  stored ledger intent, to prove in-window dispatch. Excessive actual work is
  visible inside the tick;
  a recurring >=60s gap is a material runtime blocker, not a clean tick proof.
  A final worker-side guard forbids early/late sends. A refusal after durable
  STARTED is completed as `NO_REQUEST` with no transport timestamp; a process
  death keeps the existing conservative unknown-attempt recovery. Reservations
  are not refunded. No retry, late catch-up, gap backfill or activation change.
  After a separately authorized deploy, record a naturally future PENDING slot
  and ledger max rowid before its window; observe ordinary SEARCH, typed state,
  outbox/publication, >=3s previous account-call gap and no duplicate occurrence.
  Prefer two consecutive slots within a 20-minute bound. `REPAIR_LIVE_PROVEN`
  requires exact merged/deployed SHA, installed timer/model evidence and at
  least one successful HTTP SEARCH parsed through normal batch publication.
  If no eligible window occurs in that bound, return
  `REPAIR_DEPLOYED_AWAITING_LIVE_SLOT` and leave the existing lane running.
  A recurrence, unresolved recovery or incompatible required action is
  `MATERIAL_BLOCKER`. Neither a provider's typed missing result nor a process
  exit alone is operational/scientific acceptance.
* Round crash recovery: a nomination round that died after its slack is
  reconciled by the next tick from durable evidence only (no provider call, no
  late admission). A partial round keeps what was committed and blocks its
  cohort from capture; a round with no admission is an honest gap.
* Freeze one mature cohort (UTC admission day, all slots terminal, outbox
  published):

```text
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py capture-freeze-export --collection OPPORTUNITY_EPISODES --observation-rdp <rdp> --ops-store <ops.sqlite>
```

## Workstation (consume)

```text
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py unpack-next-live-cohort --collection OPPORTUNITY_EPISODES --max-cohorts 1 --data-root <explicit-data-root>
```

Default path: SSH capture on the remote host, transfer of only missing verified
files, local seal (release 1.2) → verify → import into
`datasets/opportunity_episodes_corpus/`. With a capture packet already on disk:
add `--capture-packet <packet.json> --source-rdp <rdp> --mirror-rdp <mirror>`.
A repeated import of identical bytes returns `PASS_ALREADY_PRESENT_EXACT`. The
command never starts Forge; it prints the generated population card.

## Ordinary Forge

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <data-root> preflight --collection OPPORTUNITY_EPISODES --owner-focus <FOCUS>
```

The focus becomes `OPPORTUNITY_EPISODES:<FOCUS>` (`--owner-focus
OPPORTUNITY_EPISODES:<FOCUS>` without `--collection` is equivalent; the default
focus is `AUTO`). Then:

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <data-root> forge-run --collection OPPORTUNITY_EPISODES --owner-focus <FOCUS>
```

A query whose `population` differs from the focus collection stops before any
value with `FOCUS_POPULATION_MISMATCH`. Questions use `smial.hfic-temporal-query` 1.1 with
`population=OPPORTUNITY_EPISODES`, E-points, at most 8 points, the universe
policy owner for holders/liquidity minima and `lte` predicates for ceilings.
CONTROL mode is not supported for this collection. Saved readback loads no
values; registered replay recomputes from the frozen recipe and release files.

## If a command fails

| Code | Meaning | Next |
| --- | --- | --- |
| `EPISODE_BATCH_NOTHING_MATURE` (PASS) | no mature unimported cohort yet | wait for the next UTC day |
| `ROUND_STARTED_UNRESOLVED`, `ROUND_PARTIAL_ADMISSION`, `ROUND_RECOVERY_REFUSED`, `ROUND_FRAME_CORRUPT`, `ROUND_ROW_MISSING` in the blocking reasons of `EPISODE_BATCH_NOTHING_MATURE` | a nomination round crashed: still unreconciled, partially admitted, or its durable evidence is invalid, unreadable or missing | while the activation is active an ordinary tick reconciles an unresolved round (a paused/aborted/completed activation does not); a partial, refused, corrupt or missing round stays blocked: do not capture, report the `reason_code` from `episode_rounds` |
| `MIRROR_INCOMPLETE` | transfer interrupted | rerun the same command |
| `MARKET_EVIDENCE_BASIS_INCOMPLETE` at preflight | an import was interrupted after labels, before lineage | rerun the same unpack command (not preflight); it reuses the recorded import instant |
| `RELEASE_HASH_MISMATCH`, `MIRROR_CONFLICT`, `CLOSURE_COHORT_MISMATCH` | bytes differ from the sealed or captured identity | stop; do not import |
| `COLLECTION_PACKET_MISMATCH` | packet from another collection | use an OPPORTUNITY_EPISODES capture packet |
| `CAPTURE_PACKET_REQUIRES_SOURCE_AND_MIRROR_RDP` | packet given without its transport roots | add `--source-rdp` and `--mirror-rdp` |
| `FROZEN_PROTECTION_*` (missing, unreadable, hash/identity/set mismatch) at export, seal or verify | the protection assignment frozen at admission is absent, damaged or differs from its pin | stop; restore the exact registered assignment file (never regenerate it) and rerun |
| `ACTIVATION_NOT_ACTIVE` at stop-intake | the activation is paused (run `observation_schedule.py resume` with the same ids, then repeat stop-intake) or aborted (nothing to stop) | see meaning |
| `STOP_INTAKE_ALREADY_DRAINING` / `STOP_INTAKE_COMPLETE_REPLAY` | intake is already closed | no action |
| `STOP_INTAKE_EPISODE_SCHEDULE_ONLY` | the ids point at a non-episode schedule | check `--schedule-sha256` |
| `STOP_INTAKE_CLOCK_BEFORE_LAST_ADMISSION` / `STOP_INTAKE_ROLLOVER_PENDING` | the clock is earlier than an existing admission, or a rollover cutover is pending | fix the clock / wait for the cutover, then repeat |
| `FOCUS_POPULATION_MISMATCH` | question population differs from the focus collection | use `population=OPPORTUNITY_EPISODES` with an episode focus |

## Not here

No provider smoke, deploy, live activation, real science, retention/eviction or
volume features. The category 5m routes carry parser qualification only in
registry 011; account pace discipline stays `UNPROVEN_FAILED_OVERLAP_WITH_LEGACY`
until a later exclusive-lane observation.
# Bounded operability commissioning

Для нового campaign сначала нужен отдельный OPERATE gate. Локальный PR не
разрешает deploy, timer/settings changes, вызовы Jupiter, actual protection
installation, production import или науку. Commissioning packet находится вне
Git; runtime timestamps и host state не становятся постоянной product truth.

На проверенной изолированной копии явно выполнить `scripts/prepare_research_write_lookup.py
--data-root <absolute-copy> --isolated-copy`, сохранив wall/RSS и canonical
inventory до/после. Сверить результат с
`docs/contracts/research_write_lookup_v1.md`. Prepared lookup с копии не переносится:
он привязан к filesystem identity/stat. После отдельного OPERATE разрешения,
verified backup, measured copy rehearsal и подтверждённой остановки всех writers/
timer выполнить подготовку прямо на canonical root:

```text
uv run --locked --managed-python python -B scripts/prepare_research_write_lookup.py --data-root <absolute-canonical-root> --production-commissioning --ops-store <exact-existing-producer-ops.sqlite> --operate-authority-ref <approved-OPERATE-ref> --verified-backup-sha256 <verified-backup-sha256> --copy-rehearsal-sha256 <measured-copy-rehearsal-sha256> --quiesced-writers
```

Флаги подтверждают утверждённые prerequisites; сама команда не выдаёт OPERATE и
не доказывает backup. OPS и ResearchStore fences отказывают concurrent writer;
OPS write-lock действует весь audit, включая фазу длиннее TTL lease. После
успешной подготовки ordinary writer использует lookup. Deploy/tick/startup
автоматически его не создают. Restore/moved root и возврат после old-writer append
требуют explicit reprepare на целевом root под соответствующей authority.

Рекомендуемый canary — один immutable profile: ceiling 24/UTC day, 48h intake,
72h tail плюс grid rounding/grace, cap 48 admissions за два полных UTC дня.
Это cap, yield неизвестен. Calendar window, SHA, authority expiry на весь drain,
approved account allocation, Factory/disk/drain reserve и assignments фиксируют
непосредственно перед commissioning. Normal population/caps не снижаются для
получения PASS. Canary DoD включает реальные первые SEARCH batches: bulk, absent и
missing-mint путь, которых single-object USDC probe не доказывает; без них
search-путь остаётся `UNPROVEN`, а pace дисциплина проверяется на эксклюзивной lane. Existing legacy intake сначала штатно завершается либо отдельно
останавливается с разрешением владельца; старые obligations и datasets остаются.
Перед canary нужны две вещи, а не COMPLETE всей истории: (1) эксклюзивная
provider/workload lane — legacy collector и его same-envelope renewal не
запускаются, а exact legacy activation исполнено поставлена на `PAUSED_OPERATOR`
(или завершена; `DRAINING` legacy-scope пока не пауза и не завершение, его сначала
доводят до `COMPLETE`); (2) подтверждённая quiescence, не один случайный
`lease free`: exact schedule SHA и activation ID из `mode=ro` readback,
`factory-observation-schedule.timer` и `factory-same-envelope-renewal.timer`
отключены штатным systemd и не активны, ни один observation/renewal worker не
работает, а повторный readback не раньше чем через три collector tick (минимум 3 мин) показывает
`PAUSED_OPERATOR`, неизменные counters и ни одного нового admission, call или
publication этой activation.
Эксклюзивность относится к аккаунтному ключу, а не к одной activation: до включения lane
не существует другого `ACTIVE`/`DRAINING` scope, ни один другой процесс, timer, quote-capture
campaign или ручной probe не использует Jupiter-ключ в течение canary, а legacy не
возобновляется, пока lane включена. Pace дисциплина считается доказанной только по
request-логам всех caller'ов этого ключа: зазор между любыми двумя запросами не меньше
принятой паузы (3 s); без логов callers вне хоста (ПК, скрипты, usage-вид провайдера)
или до этого `account_pace_discipline` остаётся `UNPROVEN`, даже если все host-проверки пройдены.
Поле `operation: FREE_API_KEY_BULK_TOKEN_SEARCH` — ярлык v10, а не область наблюдения.
Исторические `PAUSED_OPERATOR`/`ABORTED` строки не требуют COMPLETE, repair или
resume и не входят в новую научную популяцию. Default tick при нескольких
ACTIVE/DRAINING scopes требует exact selection, поэтому остановленный legacy
обязан быть `PAUSED_OPERATOR` или `COMPLETE` до включения новой lane. Не создавать параллельный
постоянный collector для обхода этой границы.

Осознанная остановка legacy оставляет recorded gaps: ещё не снятые obligations
остаются `PENDING` без backfill и не выдаются за COMPLETE или за scientific
SUCCESS. Потерянные слоты не восстанавливаются через resume: пауза обратима как
control, потеря будущих observations — нет.

Bootstrap protection для canary и первого обычного batch (до отдельного решения
владельца) — `EXPLORATORY_REUSE`: новый holdout ими не объявляется, существующие protected
assignments других гипотез не отменяются. Исполнитель сначала читает metadata
канонических owners (ResearchStore и split/assignment records, Git registries и
experiment specs, dataset labels, `protection/assignments` в producer root) без
outcomes и protected values. Найденные scopes входят в один frozen document;
доказанно пустой inventory допустим с перечнем проверенных owners и границей
completeness; неразрешимая полнота возвращает один `PROTECTION_SCOPE_UNRESOLVED`
с точным missing owner и держит широкую exploratory exposure и activation закрытыми.
Нечитаемый owner — не пустой owner: список проверяемых owners берётся из Git/Catalog, а не
выбирается исполнителем. Экспозиция прежних probes фиксируется; при существенности holdout
уже не untouched, а `EXPLORATORY_REUSE` cohorts не объявляются задним числом holdout или
confirmatory. Владелец не вспоминает mint-адреса вручную. Новая версия
документа не перезаписывает прежний pin.

Protection sources создаются только как metadata projection полного известного
canonical assignment inventory: owner/scope/role/identity, source fingerprint,
completeness provenance и UNKNOWN при пробеле. Не загружать protected values.
Пустой actual список с выдуманным complete запрещён. Synthetic fixtures явно
называют synthetic inventory; они не доказывают actual completeness. Новая
версия не перезаписывает старый pin; frozen export несёт прежние dependencies.

До activation нужен exact `EPISODE_PRODUCER_STORAGE_COMMISSIONING_V1` JSON:
root device/inode, schedule SHA/activation ID, OPERATE ref, verified backup/copy
hashes, actual volume bindings/whole-Factory PASS receipt и утверждённые producer-local
byte limits. Передать `activate --episode-storage-commissioning <json>`. Поля и
canonical self-hash описаны в контракте. Все local raw/OPS/WAL/publication/research/
manifest/lookup effects должны входить в per-call bound; terminal metadata — в
per-slot bound. UNKNOWN topology блокирует commissioning до ACTIVE. Прогноз шести
копий — отдельный whole-Factory MODEL, не runtime kill-switch на producer free space.

Точный шаблон ниже намеренно невалиден до commissioning: каждый UNKNOWN заменяется
проверенным значением отдельного OPERATE packet. Не подставлять synthetic test limits
как approved envelope. `factory_storage_gate` становится PASS только после проверки
реальной topology/footprint на всех actual volumes, backup и measured copy rehearsal.

```json
{
  "kind": "EPISODE_PRODUCER_STORAGE_COMMISSIONING_V1",
  "schedule_sha256": "UNKNOWN",
  "activation_id": "UNKNOWN",
  "producer_root_identity": {"device": "UNKNOWN", "inode": "UNKNOWN"},
  "factory_storage_gate": "UNKNOWN",
  "verified_backup_sha256": "UNKNOWN",
  "copy_rehearsal_sha256": "UNKNOWN",
  "factory_storage_receipt_sha256": "UNKNOWN",
  "volume_bindings_sha256": "UNKNOWN",
  "operate_authority_ref": "UNKNOWN",
  "search_call_local_bytes_max": "UNKNOWN",
  "nomination_call_local_bytes_max": "UNKNOWN",
  "slot_metadata_local_bytes_max": "UNKNOWN",
  "fixed_local_reserve_bytes": "UNKNOWN",
  "local_safety_bytes": "UNKNOWN",
  "envelope_sha256": "UNKNOWN"
}
```

Дополнительные поля запрещены. Device/inode — целые >= 0, byte limits — целые
от 1 до 2^63−1, не bool. Четыре proof hashes и envelope hash — 64 lowercase hex;
schedule SHA и activation ID должны точно совпадать с выбранным schedule/activation.
Формат OPERATE ref проверяется по `[A-Za-z0-9_.-]{1,128}`. Эта проверка допускает
literal `UNKNOWN`; она не устанавливает, что ссылка указывает на approved authority.
В lookup preparation и storage envelope оператор заменяет такой placeholder реальной
проверенной ссылкой на отдельное OPERATE. Structural PASS не подтверждает разрешение.
Self-hash — `canonical_sha256` всего объекта без `envelope_sha256`, с теми же правилами
canonical JSON, что у schedule owner. Эти проверки не верифицируют содержимое receipts
и не выдают authority: оператор сначала проверяет их и утверждает byte limits.

Offline recipe: сохраните этот фрагмент локально, запустите repository Python с пятью
аргументами: exact canonical data root, заполненный approved JSON, exact schedule SHA,
activation ID и новый output JSON вне data root. Он читает только stat указанного root
и локальный JSON; записывает новый локальный файл, не открывает OPS или provider.
Root identity и self-hash вычисляются здесь; остальные поля уже должны быть утверждены.
После restore/move lookup требует explicit target-root reprepare с прежними
prerequisites и отдельной OPERATE authority. Это восстанавливает lookup, а не
перепривязывает storage envelope существующей activation. При изменившейся root
identity её intake остаётся закрыт для новых nominations; changed envelope получает
`EPISODE_STORAGE_REPLAY_CONFLICT`. Сохранить original IDs, frozen envelope, ledger и
canonical evidence; не повторять activate и не править OPS вручную.

Canonical recovery/продолжение committed tail требует отдельного OPERATE/repair gate
с проверенным запасом на target volume. Если оно разрешено, штатно закрыть intake
через stop-intake и довести существующий tail до COMPLETE/unpublished_backlog=0.
Новый envelope относится к новой activation на отдельно утверждённой поддерживаемой
profile/UTC cohort boundary; не создавать intraday fragments. R4 доказывает detached
read/replay/import, а не возобновление ACTIVE intake на root с изменённой identity.

```text
uv run --locked --managed-python python -B <local-preflight.py> <absolute-canonical-root> <approved-body.json> <exact-schedule-sha256> <activation-id> <new-output-json-outside-data-root>
```

```python
import json
import sys
from pathlib import Path
from solana_alpha_lab.factory.observation_schedule import canonical_sha256
from solana_alpha_lab.factory.hot90_storage_admission import (
    producer_root_identity, validate_episode_storage_commissioning,
)

data_root = Path(sys.argv[1]).resolve(strict=True)
body = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
body.pop("envelope_sha256", None)
body["producer_root_identity"] = producer_root_identity(data_root)
body["envelope_sha256"] = canonical_sha256(body)
validate_episode_storage_commissioning(
    body, data_root=data_root, schedule_sha256=sys.argv[3], activation_id=sys.argv[4],
)
destination = Path(sys.argv[5]).resolve()
if destination.is_relative_to(data_root):
    raise ValueError("OUTPUT_MUST_BE_OUTSIDE_CANONICAL_ROOT")
with destination.open("x", encoding="utf-8") as output:
    output.write(json.dumps(body, indent=2) + "\n")
print("VALIDATED_STRUCTURE_ONLY_NOT_OPERATE_AUTHORITY")
```

На текущем PREPARE gate эти поля остаются UNKNOWN, activation запрещена. При
неподходящем legacy schedule параметр отказывает `EPISODE_STORAGE_SCHEDULE_ONLY`
до ACTIVE и canonical state append. Обычный tick связывает reserve и nomination
одним current decision instant после pacing; смена round не добавляет обязательства,
для которых не проверен локальный запас. `slot_states` остаётся источником backlog.

При `DRAIN_RESERVE_PRESSURE`/`DRAIN_RESERVE_UNKNOWN` из bound LOCAL control intake уже закрыт штатным
переходом DRAINING. Повторить status, сохранить ledger и frozen dependencies,
довести obligations; pause/resume для DRAINING отказываются. Не обходить отказ,
не backfill прошлые slots и не удалять evidence. `LOCAL_HEADROOM` означает только
headroom утверждённого producer envelope, не HOST_PASS всей Factory. При
`PRODUCER_LOCAL_ENVELOPE_REQUIRED` новые nominations заблокированы, tail сохраняется,
state не меняется по unbound MODEL; нужен exact commissioning binding до activation.
При `WRITE_LOOKUP_*` сначала сохранить canonical evidence и проверить
копию; автоматический expensive rebuild и повтор неизвестной отправки запрещены.

При `TICK_REFUSED_ACTIVE_TRANSITION_PROOF_UNAVAILABLE` / NEXT
`RECONCILE_ACTIVE_TRANSITION_PROOF` сначала сохранить исходные activation IDs,
ledger, lookup journal/root и canonical evidence; прекратить ручные retry и обход
proof gate. Этот общий terminal не устанавливает причину и сам по себе не разрешает
reprepare. На verified isolated copy различить missing lifecycle evidence и
pending/corrupt/changed-binding lookup. Только подтверждённый lookup pending
reconciliation вести через существующий `--production-commissioning`: отдельный
OPERATE, verified backup, measured copy rehearsal, quiesced writers/timer и оба
fences. Copy lookup на canonical root не переносить; immutable activation storage
envelope не перепривязывать. Missing evidence или unresolved reason остаётся
BLOCKED до отдельного repair gate; восстановленный proof без evidence не объявлять.

После mature closure повтор обычного capture с новым as-of сохраняет frozen
identity. При fragmented cohort — явный отказ до partial export; V1 canary
без intraday profile switches. Public import точного release не расходует новый
look; real first question/MAIN budget фиксируются отдельно после canary.

При `EPISODE_COHORT_FRAGMENTED_UNSUPPORTED` сохранить оба activation ledger,
canonical RDP и уже frozen dependencies. Прекратить capture/import retry:
ожидание maturity не объединит два activation/profile в один cohort. Нужен
отдельный owner gate на поддерживаемую границу cohort/export; не менять cohort ID,
не исключать одну часть и не удалять evidence. Общий CLI NEXT
`STOP_INSPECT_FAIL_CODE` для этого кода означает именно этот terminal stop.

При `CLOSURE_FROZEN_UNREADABLE` сохранить frozen closure, canonical evidence и
dependencies; прекратить capture/import retry. На изолированной копии проверить
точный closure из verified backup с прежними hash/dependencies. Изменение
canonical producer требует отдельного repair gate. Не удалять и не
регенерировать closure ради обхода отказа; ожидание maturity повреждённые bytes
не исправляет. Общий `STOP_INSPECT_FAIL_CODE` означает этот terminal stop.

Owner counters `admitted_episodes`, `open_episodes`, `terminal_episodes` считают
episodes; due-slot backlog читается из `slot_states`. WATCH commissioning: число/
bytes lookup node files и inode growth, wall operational packet против фактических
due rows. Это измерение; lookup GC/retention и оптимизация здесь не разрешены.
