# Factory unattended operability

За минуту проверьте три независимых факта:

| Слой | Что подтверждает работу | Что ещё не доказано |
|---|---|---|
| Collector пишет | растут source-poll clocks; при наличии due появляется новая научная публикация | работа watch и доставка Telegram |
| Watch сообщает | два завершённых запуска; свежий валидный `operability_collector_snapshot.json`; подтверждённая доставка incident/recovery | внешний наблюдатель замечает смерть VPS |
| Внешнее наблюдение настроено | выбранный владельцем off-host получатель заметил намеренно пропущенный heartbeat | без этого статус `NOT_CONFIGURED`, даже если локальный timer включён |

Симптом OOM watch: collector работает, а snapshot стареет и сообщения замолкают.
Heartbeat посылается только при свежем snapshot watch: возраст <=1080 секунд;
missing/stale/invalid → `NO_PING` с typed reason и нулём сетевых вызовов.
Snapshot доказывает выполнение watch, но не доставку Telegram.

Ремонт `FACTORY_OPERABILITY_LIVE_RESOURCE_GATE_REPAIR_V1`: для уже заполненного
store индекс `idx_call_ledger_operability_time` строится явной командой
`sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_prepare_operability_index.py --db <absolute-ops-store-path>`
в отдельном разрешённом commissioning после проверенного backup и короткой
приостановки collector. Обычный старт collector индекс не строит. До этого watch/pulse
показывают `UNKNOWN` вместо полного прохода старых вызовов или ложного нуля.
В commissioning сначала проверьте backup и запас места, дайте индексу
построиться этой командой и подтвердите `EXPLAIN QUERY PLAN` с этим именем
индекса. Команда проверяет запас места, берёт ограниченный по ожиданию lock,
отказывается при несовпадающем индексе и печатает только итог/размер/время.
При `STORE_BUSY` не повторяйте построение в цикле: восстановите collector и
остановите commissioning до устранения конкурирующего writer. При
`INDEX_PREPARATION_DEADLINE` transaction откатывается: восстановите collector,
оставьте report timers off и пересмотрите бюджет подготовки на копии базы.
При другом отказе также восстановите collector и остановитесь с typed reason;
не удаляйте индекс и не запускайте полный watch как запасной путь.
Индекс использует только встроенные функции SQLite: старый collector после
отката сохраняет возможность записи. Immutable proof внутри одного packet читается повторно
из уже проверенного снимка; следующий packet проверяет его заново. Никакой
научный факт не кэшируется между циклами. Watch/pulse timers остаются
выключенными до успешного отдельного post-merge canary по реальным unit env,
MemoryPeak <512 MiB и wall <120 s; затем нужны два обычных watch-цикла и
реальная подтверждённая доставка дневного Telegram перед включением pulse.
External heartbeat остаётся выключенным до отдельной настройки получателя.

Первая read-only проверка на хосте из `/opt/solana-alpha-lab`:

```sh
date -u
cat .factory_deploy_sha
systemctl show factory-operability-watch.service factory-collector-owner-pulse.service --property=Result,ExecMainStatus,MemoryPeak,MemoryMax,TimeoutStartUSec
systemctl list-unit-files factory-operability-watch.timer factory-collector-owner-pulse.timer factory-observation-schedule.timer factory-same-envelope-renewal.timer --no-pager
systemctl show factory-operability-watch.timer factory-collector-owner-pulse.timer factory-observation-schedule.timer factory-same-envelope-renewal.timer --property=Id,LoadState,UnitFileState,ActiveState,SubState,LastTriggerUSec,NextElapseUSecRealtime
systemctl list-timers --all factory-operability-watch.timer factory-collector-owner-pulse.timer factory-observation-schedule.timer factory-same-envelope-renewal.timer --no-pager
journalctl -k --since '24 hours ago' --grep='oom-kill|Out of memory|Killed process' --no-pager -n 20
stat -c 'snapshot bytes=%s modified=%y' local/factory_v1/operability_collector_snapshot.json
df -h /opt/solana-alpha-lab
```

Snapshot можно проверить этой bounded read-only командой из того же каталога:

```sh
PYTHONPATH=src uv run --locked --managed-python python -B - <<'PY'
import json
from datetime import UTC, datetime
from pathlib import Path
from solana_alpha_lab.factory.operability_watch import (
    SNAPSHOT_RELATIVE, evaluate_collector_snapshot_freshness, load_collector_snapshot_file,
)
status, snapshot = load_collector_snapshot_file(Path(SNAPSHOT_RELATIVE))
age = None
if snapshot is not None:
    status, age = evaluate_collector_snapshot_freshness(snapshot['observed_at'], now=datetime.now(UTC))
print(json.dumps({'snapshot_state': status, 'age_seconds': age,
                  'observed_at': snapshot['observed_at'] if snapshot else None}))
PY
```

Результат — `FRESH`, `STALE`, `MISSING` или `INVALID` и возраст. Команда читает
не более 65536 байт, не открывает collector store и не отправляет ping/Telegram.
Отключённые installed timers видны в `list-unit-files` и в явном `show`;
`list-timers --all` дополняет их расписанием загруженных units. Пустой список
срабатываний не означает, что unit отсутствует.

До deploy используйте SQLite probe ниже. `observation_schedule.py status`
не входит ни в pre-deploy, ни в read-only проверку: predecessor может пройти
весь call ledger, а CLI открывает store с возможностью schema/write операций.
После deploy этот CLI также не является доказанным read-only probe; данный
runbook его не запускает. Не читайте весь ledger и не запускайте старый полный
packet на хосте после OOM. `PROVIDER_STATE_UNKNOWN` означает непроверяемую
диагностику: проверьте scope и clocks, не объявляйте провайдера здоровым.
Watch выдаёт отдельный `CALL_DIAGNOSTICS_UNKNOWN` после 1800s; прежний
`MATERIAL_COVERAGE_DEGRADATION` означает только подтверждённый `DISCOVERY_GAP`.
Heartbeat с настроенным URL и свежим snapshot — реальный HTTPS-запрос;
не используйте его как read-only probe.


## Узкий pre-deploy SQLite readback

Задайте точные `<SCHEDULE_SHA256>` и `<ACTIVATION_ID>` из уже принятого
campaign envelope; не выбирайте latest activation. Путь ниже соответствует
`ops_store_relative` в runtime config: при другом effective path остановитесь
и подставьте подтверждённый путь, не создавайте новую базу.

```sh
/usr/bin/uv run --locked --managed-python python -B - '<SCHEDULE_SHA256>' '<ACTIVATION_ID>' <<'PY'
import json
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

scope = (sys.argv[1], sys.argv[2])
database = Path('local/factory_v1/observation_schedule_state.sqlite').resolve()
if not database.is_file():
    print(json.dumps({'probe_state': 'UNKNOWN', 'reason': 'STORE_MISSING'}))
    raise SystemExit(2)
deadline = time.monotonic() + 5
try:
    connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=2)
except sqlite3.Error:
    print(json.dumps({'probe_state': 'UNKNOWN', 'reason': 'STORE_OPEN_FAILED'}))
    raise SystemExit(2)
connection.row_factory = sqlite3.Row
connection.execute('PRAGMA query_only=ON')
connection.execute('PRAGMA cache_size=-2048')
connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
queries = {
    'activation_and_authority_raw': ("""SELECT a.schedule_sha256, a.activation_id,
        a.state, a.starts_at, a.stops_admitting_at, a.updated_at,
        a.transition_sequence, a.last_transition_event_id,
        a.authority_receipt_sha256, r.expires_at AS authority_expires_at
        FROM schedule_activations AS a
        LEFT JOIN authority_receipts AS r
          ON r.receipt_sha256 = a.authority_receipt_sha256
        WHERE a.schedule_sha256=? AND a.activation_id=? LIMIT 1""", scope),
    'today_accounting_raw': ("""SELECT provider_calls, canonical_bytes, last_provider_call_at, updated_at
        FROM accounting_counters
        WHERE schedule_sha256=? AND activation_id=? AND utc_day=? LIMIT 1""", (*scope, datetime.now(UTC).date().isoformat())),
    'lifetime_raw': ("""SELECT provider_calls, canonical_bytes, updated_at FROM lifetime_counters
        WHERE schedule_sha256=? AND activation_id=? LIMIT 1""", scope),
    'due_states_raw': ("""SELECT state, count(*) AS rows, min(due_at) AS first_due_at
        FROM due_observations WHERE schedule_sha256=? AND activation_id=?
        GROUP BY state LIMIT 16""", scope),
    'call_tail_raw': ("""SELECT rowid, primitive_id, state, created_at, updated_at
        FROM call_ledger ORDER BY rowid DESC LIMIT 32""", ()),
    'publication_tail_raw': ("""SELECT rowid, batch_content_sha256, created_at
        FROM publication_batches ORDER BY rowid DESC LIMIT 8""", ()),
    'restore_marker_raw': ("""SELECT resolved FROM restore_markers WHERE marker_id='UNRESOLVED' LIMIT 1""", ()),
}
try:
    result = {name: [dict(row) for row in connection.execute(sql, parameters)]
              for name, (sql, parameters) in queries.items()}
    found = bool(result['activation_and_authority_raw'])
    print(json.dumps({'probe_state': 'RAW_READBACK' if found else 'UNKNOWN',
                      'source_http_success': 'UNKNOWN', 'scientific_publication': 'UNKNOWN',
                      **result}, sort_keys=True))
    if not found:
        raise SystemExit(2)
except sqlite3.Error:
    print(json.dumps({'probe_state': 'UNKNOWN', 'reason': 'SQL_READ_FAILED_OR_BUDGET'}))
    raise SystemExit(2)
finally:
    connection.close()
PY
```

Запросы не выбирают `payload_json`, не вызывают Factory store/CLI и не меняют
schema/SQLite. Primary keys ограничивают activation, authority и counters;
существующий `(schedule_sha256, activation_id, state, due_at, deadline_at)`
index обслуживает due aggregate. Call/publication tails ограничены 32/8
строками в порядке insertion `rowid`, без сортировки всей истории.
5s SQL budget и 2s lock timeout завершают неуспешное чтение как `UNKNOWN`.

Повторите readback через один collector interval: advancement counters и
source-primitive timestamps в tail — свидетельства оперативной активности.
Tail не гарантирует присутствия выбранной campaign, не упорядочен по UTC и
не доказывает `HTTP_OK`; accounting clock не равен source success.
Raw activation state не заменяет as-of transition/authority/rollover proof.
`canonical_bytes` и publication ledger не доказывают доступность научного RDP:
для неё нужен точный сохранённый publication receipt/manifest и scientific
lineage. Если нужного source/RDP/continuity доказательства нет, оставьте
соответствующий пункт `UNKNOWN` и остановите rollout; не расширяйте этот
probe до полного ledger, recursive RDP scan или writable `status`.

Если два отчётных timer временно отключены, collector и same-envelope renewal
продолжают свои циклы; incident/recovery и ежедневной Telegram-карточки нет.
Snapshot становится stale, heartbeat не пингует. Без внешнего получателя
смерть watch/VPS не даёт доказанного оповещения. Git не фиксирует текущее
enablement: эти факты устанавливает только датированный VPS readback.

Canonical operator entrypoint for ordinary unattended Factory operations.
Git owns capability and procedure. The live VPS owns current runtime. This
file never claims current disk %, archive day, HOT90 stage, or Telegram
liveness.

Host locator: `docs/operator/FACTORY_REMOTE_HOST.md`.
Collector protocol: `docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md`.
HOT90 activation contract: `docs/operator/FACTORY_HOT90_COMMISSIONING_V1.md`.
Semantic discovery: `SEM-REMOTE-OPS-RECOVERY` via
`scripts/catalog_cli.py search-routes`.

Status: `ACTIVE_BOUNDARY_CONTRACT`.
Runtime truth: `RUNTIME_STATE_EXTERNAL_READBACK_REQUIRED`.
This Git PR does not deploy, enable units, write Drive, send Telegram, or
activate an external heartbeat provider.

## WHAT RUNS AUTOMATICALLY?

After a later owner-gated commissioning (not this Git change):

| Loop | Unit templates | Cadence (UTC) |
|---|---|---|
| Lifecycle collection | existing `factory-observation-schedule.timer` | existing collector cadence |
| Mutable-state backup | existing `factory-remote-backup*.timer` | existing backup cadence |
| Closed-day immutable archive | `factory-hot90-closed-day-archive.timer` | `01:15 / 07:15 / 13:15 / 19:15 UTC`, max 3 days/run |
| Daily owner pulse | `factory-collector-owner-pulse.timer` | `*-*-* 06:20:00 UTC` |
| Local operability watch | `factory-operability-watch.timer` | every 15 minutes UTC |
| External heartbeat (local half) | `factory-external-heartbeat.timer` | every 5 minutes UTC |

Archive, Telegram and heartbeat failures must not stop the collector.
Collector death must still be visible to the local watch while the VPS is alive.
One `DATA_STALE` health class emits one owner incident: `SOURCE_DATA_STALE`.
It does not also emit `COLLECTOR_STALLED`. A true collector stoppage still
surfaces through source freshness, required timers, or service failure.
Watch cadence stays every 15 minutes UTC; do not treat a slower watch as
the fix for a long oneshot tick.

## WHAT DOES GIT OWN?

Supported capability, policy, allowed HOT90 stages, schemas, systemd
templates, operator procedure, Catalog/semantic routes, tests.

Git does not own: current activation stage, whether today's timer fired,
disk usage, backup/archive freshness, Telegram liveness, VPS reachability.

## WHAT DOES VPS RUNTIME OWN?

Preserved under `local/factory_v1` (and the independent backup sink):

- `hot90_activation_runtime.yaml`
- closed-day archive receipts `hot90_archive_receipts/{YYYYMMDD}.json`
- derived archive staging `hot90_archives/` (automation-owned ZIPs only)
- cohort closure receipts `hot90_cohort_closure_receipts/{cohort_id}.json`
  (staging `hot90_cohort_closures/` is empty after every run)
- operability incident/dedup state
- collector SQLite / Observation RDP
- systemd enablement and timer last-run

Ordinary HOT90 `SET`s stay operational SETs, not PRs.

## WHAT DOES DRIVE OWN?

Two distinct durability channels:

- `MUTABLE_STATE_BACKUP` — SQLite / operational mutable state (and the
  pre-cutover `FULL_RDP_BACKUP` profile when runtime says so).
- `IMMUTABLE_RDP_ARCHIVE` — closed UTC-day scientific ZIP, copied with
  rclone `copyto` only. Upload/filename/listing/mtime/size are not proof.
  Only exact remote content SHA256 equality is `REMOTE_CONTENT_SHA256_VERIFIED`.

Git describes both profiles. Runtime activation selects which backup
profile is live. Drive prune and scientific HOT90 delete are out of this
capability.

## WHAT DOES THE EXTERNAL WATCHER OWN?

A future off-host watchdog owns “can anything outside the VPS still hear
from it?”. This repository provides only a provider-neutral HTTPS GET to
`FACTORY_EXTERNAL_HEARTBEAT_URL`, conditional on valid fresh watch evidence.
Snapshot reads are bounded to 65536 bytes; no collector store or operational
packet is imported. Unconfigured is a typed no-op. No URL,
account, or provider is in Git.

## WHAT MESSAGE SHOULD THE OWNER EXPECT?

- One daily card at 06:20 UTC: `FACTORY / DAILY — OK | DEGRADED | ACTION`.
- One `INCIDENT` when a material fail persists past the owned grace.
- One `RECOVERED` when it clears.
- No routine PENDING / historical STARTED / single transient transport spam.

Parser footer fields: `MESSAGE_TYPE`, `STATE`, `INCIDENT`, `COLLECTOR_STATE`,
`LIFECYCLE_STATE`, `ARCHIVE_LAST_VERIFIED_DAY`, `ARCHIVE_BACKLOG_DAYS`,
`MUTABLE_BACKUP_STATE`, `PROJECTED_97D_BYTES`, `OWNER_ACTION`.

## WHAT IS SAFE TO READ?

До deploy после OOM используйте только bounded snapshot/SQLite/systemd probes
выше. Тяжёлые watch/pulse dry-run ниже допустимы после deploy только в canary
с проверенным окружением и caps. Generic status/doctor не заменяет pre-deploy
probe: read-only эффект и ресурсный предел должны быть доказаны отдельно.

- `scripts/hot90_activation.py show` — no mutation.
- `scripts/collector_owner_pulse.py --mode dry-run` — zero network, zero
  Telegram credential VALUE reads.
- `scripts/factory_operability_watch.py --mode dry-run --skip-systemd` —
  no Telegram send and no incident-state write. Owner cards are in
  JSON `preview_messages`. `--mode emit` persists local incident JSON
  and may send Telegram.
- `scripts/hot90_closed_day_durability.py` is an operator **action** when
  runtime is `DURABILITY_CUTOVER`/`RETENTION_ACTIVE` with Drive writes
  enabled; otherwise typed no-op. Do not use it as a read-only probe.
- `scripts/factory_external_heartbeat.py` — no-op unless URL is configured.
  With a URL it can send a real ping; missing/stale/invalid watch snapshot
  returns `NO_PING` with zero network calls.
- `scripts/factory_remote_doctor.py` status/offhost-status surfaces from the
  collector runbook (do not pass `--backup` unless that exact OPERATE atom
  is named).

## WHAT REQUIRES OWNER AUTHORITY?

Deploy, unit install/enable, Drive/Telegram live send, HOT90 `SET`,
external heartbeat URL, retention/eviction, scientific delete, Drive prune,
wallet/signer/real money, new provider purchase.

## HOW DO I RECOVER AFTER REBOOT?

Persistent timers resume. Receipts and incident state stay on disk.
Archive catch-up processes oldest eligible unverified UTC day first, up to
3 days per run, four times per UTC day, so a 7-day outage can converge
without a Git PR.

## HOW DO I RECOVER AFTER DRIVE FAILURE?

Source RDP is untouched. Local archive staging is reused. Later runs retry
copy/verify. A persistent Drive fail becomes one incident, then one
`RECOVERED`. Do not overwrite or delete a remote object on hash mismatch.

## HOW DO I VERIFY AN ARCHIVE?

Exact remote content SHA256 must equal the local archive SHA256. A verified
receipt records both hashes, the remote object identity, and
`REMOTE_CONTENT_SHA256_VERIFIED`. A receipt cannot substitute for the
content hash.

## HOW IS A FUTURE EPISODE COHORT PROTECTED WITHOUT THE WORKSTATION?

A day ZIP does not hold the cohort export (closure receipt, frames, schedule,
protection, exporter-frozen `capture_metadata`) nor completed publication jobs.
After the days, the same closed-day run protects up to two mature, not yet
protected `OPPORTUNITY_EPISODES` cohorts (from
`REL-20261013T000000Z-20261014T000000Z`; earlier cohorts were captured by the
workstation route). It calls the native `capture_freeze_export` the workstation
used over SSH, then uploads one content-addressed
`COHORT_CLOSURE_<sha256>.zip` = `packet.json` + `source/<transfer_path>` for
every manifest entry (each byte hash-checked, ≤2 GiB, `copyto` only), verifies
the exact remote SHA and writes
`hot90_cohort_closure_receipts/<cohort_id>.json`. Local staging is deleted in
every outcome (leftovers of a killed run are swept at the next run); a failed
cohort is retried next run. A failure stays visible: HASH_MISMATCH raises
`IMMUTABLE_ARCHIVE_HASH_MISMATCH`, any other failure older than 24 h raises
`IMMUTABLE_ARCHIVE_STALE` (existing watch incidents). Maturity stays the native
closed obligations/publications/integrity rule. "Protected" means an offhost
closure exists; it does not mean imported. The object name addresses one
capture (its packet); a Drive outage keeps that exact archive and the next run
resumes it without a new capture, while a cohort-local failure is recorded and the
next cohort proceeds. Each receipt carries `shared_call_proof` (from the closure
bytes: every response-body call the cohort claims, with all claiming cohorts);
an incomplete or unverifiable proof keeps the bytes protected but raises the same
archive health class instead of passing silently.

Late consumer, with only the Drive object and Git (no VPS access). Download
`COHORT_CLOSURE_<sha256>.zip` from Drive folder `solana-alpha-lab/factory-backups`
into `local/cold_consume/`, then (PowerShell):

```text
$z = "local/cold_consume/COHORT_CLOSURE_<sha256>.zip"
(Get-FileHash $z -Algorithm SHA256).Hash.ToLower()   # must equal <sha256> in the name
Expand-Archive $z -DestinationPath local/cold_consume/<sha256>
# rehearsal into a separate restore root first
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py unpack-next-live-cohort --collection OPPORTUNITY_EPISODES --max-cohorts 1 --capture-packet local/cold_consume/<sha256>/packet.json --source-rdp local/cold_consume/<sha256>/source --mirror-rdp local/cold_consume/rehearsal/mirror --data-root local/cold_consume/rehearsal/data_plane
# then the same command with --mirror-rdp local/factory_mirror/observation_rdp --data-root local/factory_v1/data_plane
```

Several cohorts: one extraction directory and one run each, oldest first.
Repeating an import of the same release returns `PASS_ALREADY_PRESENT_EXACT`.
After a verified import delete exactly `local/cold_consume/` (it holds only the
downloads, extractions and the rehearsal root); the sealed release, mirror
capture view and corpus are the retained consumers.

Check collection or stop new admissions while tails finish: see
`docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md` → `collection-status`
(read-only; shows `revision`) and `collection-stop-intake --expected-revision <revision>`.

## WHAT DOES A DELIVERY LEAVE BEHIND?

Each operation records its heavy outputs as `disposable`, `resume` or
`canonical` in its own operation receipt and deletes disposable outputs once
their consumer has verified them (exact files, containment checked, no links,
no recursive wildcard over canonical roots). A development worktree is removed
with `git worktree remove` once nothing scheduled or readback-bound points into
it; resume material moves to a stable operation root first.

## HOW DO I ROLLBACK THE NEW AUTOMATION?

Disable only the new **timers** (oneshot services have no `[Install]`):

```
sudo systemctl disable --now factory-hot90-closed-day-archive.timer
```

```
sudo systemctl disable --now factory-operability-watch.timer
```

```
sudo systemctl disable --now factory-collector-owner-pulse.timer
```

```
sudo systemctl disable --now factory-external-heartbeat.timer
```

Keep receipts, source RDP, and HOT90 runtime activation. Restore a previous
exact deploy SHA if required. Do not “rollback” by deleting runtime truth.

## Commissioning (future OPERATE, not this Git change)

Это отдельный owner-gated deploy после merge. До него нужен датированный
readback SHA, backup/archive receipt и exact remote verification, диска,
collector/source/RDP progression, timer/service state и campaign continuity.
Неизвестный backup/archive, отсутствующая continuity или остановившийся
collector — blocker. Авторизация кампании не входит в ремонт отчётов.

1. Сохраните `PREVIOUS_SHA`, точный merged `TARGET_SHA`, подтверждённый
   `MAIN_SHA` и prior unit state. SHA — 40 lowercase hex. `<SOURCE_REPO>` —
   существующий source Git repository на host с этими objects; deploy root
   `/opt/solana-alpha-lab` не содержит `.git`. Отчётные timer оставьте выключенными.
2. После отдельного разрешения владельца выполните existing release; затем
   установите только затронутые unit templates:

```sh
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_live_release.py --repo <SOURCE_REPO> --deploy-root /opt/solana-alpha-lab --target-sha <TARGET_SHA> --main-sha <MAIN_SHA> --live-sha <PREVIOUS_SHA> --mode canonical-forward
sudo install -m 0644 configs/factory_remote_ops/factory-operability-watch.service /etc/systemd/system/factory-operability-watch.service
sudo install -m 0644 configs/factory_remote_ops/factory-collector-owner-pulse.service /etc/systemd/system/factory-collector-owner-pulse.service
sudo install -m 0644 configs/factory_remote_ops/factory-operability-watch.timer /etc/systemd/system/factory-operability-watch.timer
sudo install -m 0644 configs/factory_remote_ops/factory-collector-owner-pulse.timer /etc/systemd/system/factory-collector-owner-pulse.timer
sudo systemctl daemon-reload
```

3. Memory canary запускается **после deploy** и до включения report timers.
   Он должен получить effective окружение реальных watch/pulse, включая
   `FACTORY_BACKUP_SINK`: без env file packet может измерить другой sink и
   дать ложный resource PASS. Не используйте bare `sudo uv`, `source`, `env`,
   `systemctl cat` или вывод `Environment`: они не являются безопасным
   доказательством совпадения и могут раскрыть значения секретов.

Для canonical templates ниже проверьте effective settings **обеих** units:

```sh
check_report_environment() {
    sudo /usr/bin/uv run --locked --managed-python python -B - "$1" <<'PY'
import json
import os
import stat
import subprocess
import sys

expected = {'LoadState': 'loaded', 'WorkingDirectory': '/opt/solana-alpha-lab',
            'EnvironmentFiles': '/etc/solana-alpha-lab/secrets.env (ignore_errors=yes)',
            'NoNewPrivileges': 'yes', 'Slice': 'system.slice',
            **{name: '' for name in ('Environment', 'PassEnvironment', 'UnsetEnvironment',
                                     'DropInPaths', 'User', 'Group', 'RootDirectory', 'RootImage')}}
state = 'UNKNOWN'
try:
    read = subprocess.run(['systemctl', 'show', sys.argv[1],
                           '--property=' + ','.join(expected)],
                          capture_output=True, text=True, timeout=5, check=False)
    values = dict(line.split('=', 1) for line in read.stdout.splitlines() if '=' in line)
    env_file = '/etc/solana-alpha-lab/secrets.env'
    if (read.returncode == 0 and expected.keys() <= values.keys()
            and all(values[name] == wanted for name, wanted in expected.items())
            and stat.S_IMODE(os.stat(env_file).st_mode) == 0o600
            and os.access(env_file, os.R_OK)):
        state = 'MATCH'
except (OSError, subprocess.SubprocessError):
    pass
print(json.dumps({'report_environment_state': state}))
raise SystemExit(0 if state == 'MATCH' else 2)
PY
}
check_report_environment factory-operability-watch.service && check_report_environment factory-collector-owner-pulse.service
sudo stat -c 'env_file_metadata=%d:%i:%s:%Y mode=%a' /etc/solana-alpha-lab/secrets.env
```

Проверка сравнивает inline environment в памяти только с пустой строкой;
значения не выводятся, не сохраняются и не передаются в argv. Env file читает
только service manager. При nonzero/неизвестном property, другом env file,
drop-in или effective User/Group окружение = `UNKNOWN`: остановитесь и
разберите конкретное отличие в отдельном OPERATE scope. Не копируйте
секреты в команду. Не меняйте env file между canary и обычными запусками;
повторите проверку метаданных перед enablement. Обе команды ниже используют
тот же manager, root identity, working directory и env file и повторяют
соответствующий production CLI. Это доказывает совпадение canary с конкретной
unit; одинаковый env file не доказывает общий физический sink двух consumers.
Watch передаёт окружение в packet и использует `FACTORY_BACKUP_SINK`.
Существующий pulse CLI не передаёт окружение в packet: dry-run и emit читают
git-side default sink. Canary сохраняет этот фактический путь; не объявляйте
его проверкой env-selected sink. Если принятый production backup envelope
требует другой sink, соответствие pulse = `UNKNOWN`, rollout остановить до
отдельной коррекции этого consumer. Dry-run не читает Telegram credential VALUE,
не отправляет сообщения и не записывает snapshot/incident/storage history.
Следующие canary команды разрешены только после двух `MATCH` и сохранённых
метаданных env file; любая ошибка этой проверки останавливает rollout.

```sh
WATCH_CANARY="factory-watch-canary-$(date -u +%Y%m%dT%H%M%SZ)"
sudo systemd-run --unit="$WATCH_CANARY" --service-type=oneshot --remain-after-exit --property=MemoryAccounting=yes --property=MemoryMax=768M --property=TimeoutStartSec=180s --property=WorkingDirectory=/opt/solana-alpha-lab --property=EnvironmentFile=-/etc/solana-alpha-lab/secrets.env --property="ExecStartPost=/usr/bin/python3 -B scripts/factory_cgroup_peak.py" --property=NoNewPrivileges=yes /usr/bin/uv run --locked --managed-python python -B scripts/factory_operability_watch.py --mode dry-run
```

`Type=oneshot` завершает start job после команды. `--remain-after-exit`
сохраняет завершённую unit для readback: не добавляйте несовместимый `--wait`,
`--pipe` или `--collect`, не останавливайте unit до получения measurement.
Эти свойства описаны в [systemd-run](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd-run.xml)
и [systemd.service](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.service.xml).
Уникальное имя исключает reuse старого пика. Получите результат функцией ниже:

```sh
canary_readback() {
    /usr/bin/uv run --locked --managed-python python -B - "$1" "${2:-canary}" <<'PY'
import json
import re
import subprocess
import sys

properties = ('ActiveState', 'SubState', 'Result', 'ExecMainStatus', 'MemoryPeak',
              'ExecMainStartTimestampMonotonic', 'ExecMainExitTimestampMonotonic', 'MemoryMax', 'InvocationID')
try:
    read = subprocess.run(['systemctl', 'show', sys.argv[1],
                           '--property=' + ','.join(properties)],
                          capture_output=True, text=True, timeout=5, check=False)
except (OSError, subprocess.SubprocessError):
    print(json.dumps({'resource_state': 'UNKNOWN', 'memory_peak_bytes': None, 'wall_seconds': None}))
    raise SystemExit(2)
values = dict(line.split('=', 1) for line in read.stdout.splitlines() if '=' in line)
state = 'UNKNOWN'
peak = wall = None
if read.returncode == 0:
    if values.get('Result') not in (None, '', 'success') or values.get('ExecMainStatus') not in (None, '', '0'):
        state = 'BLOCKED'
    elif values.get('Result') == 'success' and values.get('ExecMainStatus') == '0':
        try:
            raw_peak = values.get('MemoryPeak', '')
            peak = int(raw_peak) if raw_peak.isdecimal() else 0
            invocation = values.get('InvocationID', '')
            if not re.fullmatch('[0-9a-f]{32}', invocation):
                raise ValueError('RESOURCE_INVOCATION_UNAVAILABLE')
            journal = subprocess.run(['sudo', 'journalctl', '-u', sys.argv[1],
                                      '_SYSTEMD_INVOCATION_ID=' + invocation, '-o', 'cat',
                                      '--no-pager', '-n', '30'], capture_output=True,
                                     text=True, timeout=5, check=False)
            saved = [json.loads(line) for line in journal.stdout.splitlines()
                     if line.startswith('{') and '"cgroup_memory_peak_bytes"' in line]
            if journal.returncode != 0 or len(saved) != 1:
                raise ValueError('RESOURCE_PEAK_UNAVAILABLE')
            saved_peak = saved[0].get('cgroup_memory_peak_bytes')
            if (type(saved_peak) is not int or not 0 < saved_peak <= 768 * 1024**2
                    or saved[0].get('cgroup_memory_max_bytes') != 768 * 1024**2
                    or values.get('MemoryMax') != str(768 * 1024**2)):
                raise ValueError('RESOURCE_PEAK_UNAVAILABLE')
            peak = max(peak, saved_peak)
            started = int(values['ExecMainStartTimestampMonotonic'])
            ended = int(values['ExecMainExitTimestampMonotonic'])
            if 0 < peak < 2**64 - 1 and 0 < started < ended:
                wall = (ended - started) / 1_000_000
                terminal = (values.get('ActiveState'), values.get('SubState'))
                expected_terminal = ('inactive', 'dead') if sys.argv[2] == 'ordinary' else ('active', 'exited')
                if terminal == expected_terminal:
                    state = 'PASS' if peak < 512 * 1024**2 and wall < 120 else 'BLOCKED'
        except (KeyError, ValueError, OSError, subprocess.SubprocessError):
            pass
print(json.dumps({'resource_state': state, 'memory_peak_bytes': peak, 'wall_seconds': wall}))
raise SystemExit(0 if state == 'PASS' else 2)
PY
}
canary_readback "$WATCH_CANARY.service"
```

`ExecStartPost` сохраняет kernel `memory.peak` через stdlib script сразу после oneshot до удаления
cgroup. Ubuntu может вернуть `MemoryPeak=[not set]` уже после завершения;
тогда используется единственная числовая запись из journal той же уникальной
unit/InvocationID с совпавшим `memory.max=768 MiB`. Штатные service templates
используют тот же helper; он не читает operational store или environment values. Это cgroup peak всех дочерних процессов; это не sampling RSS одного
Python PID. Positive numeric peak, monotonic duration, успешное завершение и
пороги <512 MiB / <120s обязательны. Неподдерживаемый/пустой/infinity/нулевой
пик, пропавшая unit или отсутствующий clock → `UNKNOWN`, rollout остановить.
OOM/timeout/nonzero exit или превышение порога → `BLOCKED`.
Сохраните только этот минимальный resource readback; journal preview отдельно
проверяет snapshot/incident semantics, но не доказывает Telegram delivery.
Только после readback остановите **canary**, сохранив обычные report timers off:

```sh
sudo systemctl stop "$WATCH_CANARY.service"
```

4. Только после PASS включите watch. Подтвердите два последовательных цикла,
   свежий валидный snapshot, MemoryPeak/время, incident/recovery и Telegram
   delivery/retry с отдельно разрешённой проверкой. Collector/renewal продолжаются:

```sh
COMMISSIONING_START=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
if ! sudo systemctl start factory-operability-watch.service || ! canary_readback factory-operability-watch.service ordinary; then
    sudo systemctl disable --now factory-operability-watch.timer
    exit 2
fi
systemctl show factory-operability-watch.service --property=InvocationID,ExecMainStartTimestamp,ExecMainExitTimestamp,Result,ExecMainStatus
journalctl --unit=factory-operability-watch.service --since "$COMMISSIONING_START" --output=short-iso --no-pager
```

Первый цикл выполняется обычной service командой `systemctl start`, которая
ждёт завершения start job под TimeoutStartSec=180s; включение timer само по
себе не является завершением watch. Второй цикл — следующий timer tick.
Первый ordinary запуск и его resource readback выполняются при выключенном
timer. Любой nonzero/UNKNOWN выключает timer явной командой; включение
разрешено только после успешного завершения, свежего snapshot и проверки
отсутствия pending/transport error (для pulse дополнительно реальная daily delivery).
Для ordinary readback unit должна завершиться в `inactive/dead`; пик берётся
из journal только её сохранённого InvocationID. При отсутствии ровно одной
числовой записи helper результат UNKNOWN, rollout остановить.
До включения watch timer должны отдельно пройти первый ordinary resource
readback, свежий валидный snapshot и отсутствие pending/transport error.
При здоровом состоянии без incident сообщение не обязано создаваться: это
допускает enable, но не устанавливает доказательство incident/recovery delivery.
UNKNOWN любого обязательного входа оставляет timer выключенным. Только после
этих PASS выполняется отдельная команда:

```sh
sudo systemctl enable --now factory-operability-watch.timer
```

После каждого из двух обычных 15-минутных запусков сохраните этот readback и
результат snapshot probe выше. Нужны два разных InvocationID/start times и
два завершения после deploy, exit=0, peak <512 MiB, wall <120s, продвижение
snapshot `observed_at`. Текущая строка `Result=success` доказывает только
последний процесс. Проверьте JSON каждого запуска в journal:
`pending_count > 0` или transport error — `BLOCKED`, даже при exit=0.
`pending_count=0` без созданного сообщения не доказывает отправку Telegram.
Incident/recovery считается проверенным только по соответствующим
`MESSAGE_TYPE`/incident key и реально полученным карточкам с теми же clocks.
Если incident/recovery не было, этот пункт остаётся `UNKNOWN` до отдельно
разрешённой контрольной проверки; не создавайте сбой collector/provider ради неё.
Сохраняйте минимальную датированную выжимку, не публикуйте секреты из journal.

5. Отдельный pulse canary использует ту же проверку окружения/метаданных,
   тот же backup sink и функцию `canary_readback`; не подставляйте другой sink:

```sh
check_report_environment factory-collector-owner-pulse.service
PULSE_CANARY="factory-pulse-canary-$(date -u +%Y%m%dT%H%M%SZ)"
sudo systemd-run --unit="$PULSE_CANARY" --service-type=oneshot --remain-after-exit --property=MemoryAccounting=yes --property=MemoryMax=768M --property=TimeoutStartSec=180s --property=WorkingDirectory=/opt/solana-alpha-lab --property=EnvironmentFile=-/etc/solana-alpha-lab/secrets.env --property="ExecStartPost=/usr/bin/python3 -B scripts/factory_cgroup_peak.py" --property=NoNewPrivileges=yes /usr/bin/uv run --locked --managed-python python -B scripts/collector_owner_pulse.py --mode dry-run --record-storage-history
canary_readback "$PULSE_CANARY.service"
sudo systemctl stop "$PULSE_CANARY.service"
```

При тех же PASS-критериях выполните первый ordinary pulse с выключенным
timer и подтвердите его реальную daily delivery. Два отчётных timer
не включаются одним шагом:

```sh
PULSE_START=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
if ! sudo systemctl start factory-collector-owner-pulse.service || ! canary_readback factory-collector-owner-pulse.service ordinary; then
    sudo systemctl disable --now factory-collector-owner-pulse.timer
    exit 2
fi
systemctl show factory-collector-owner-pulse.service --property=InvocationID,ExecMainStartTimestamp,ExecMainExitTimestamp,Result,ExecMainStatus
journalctl --unit=factory-collector-owner-pulse.service --since "$PULSE_START" --output=short-iso --no-pager
```

В journal нужен `# delivery delivered=True deduped=False` и полученная daily
карточка за тот же UTC day. `delivered=False deduped=True` принимается только
со ссылкой на ранее доказанную доставку этого day; один dedupe не доказывает
её. `delivered=False deduped=False`, отсутствие delivery footer, pending или
failure — `BLOCKED`. Snapshot и exit=0 delivery footer не заменяют.
Только после PASS первого ordinary resource readback, snapshot и доказанной
реальной daily delivery включите pulse отдельной командой; UNKNOWN
оставляет timer выключенным:

```sh
sudo systemctl enable --now factory-collector-owner-pulse.timer
```

6. Внешний получатель, URL и Telegram-маршрут требуют отдельного решения
   владельца. До подключения и теста пропущенного heartbeat — `NOT_CONFIGURED`.
   Fresh watch snapshot сам по себе не доказывает Telegram-доставку.

После enable любой non-PASS обязательного для данного цикла входа
(ресурсы, свежий InvocationID/snapshot, pending/transport error или отказ
фактически созданного сообщения) немедленно выключает только
соответствующий report timer; не оставляйте его повторять проблемный запуск.
Watch без incident/recovery сообщения не выключается из-за UNKNOWN его
непроизошедшей delivery. Для pulse реальная daily delivery обязательна:

```sh
sudo systemctl disable --now factory-operability-watch.timer
# Для отказа pulse вместо watch:
# sudo systemctl disable --now factory-collector-owner-pulse.timer
```

Stop: UNKNOWN обязательного входа, OOM, timeout, peak >=512 MiB, wall >=120s, stale/invalid snapshot,
неустраняемый delivery failure или регрессия collector/source/RDP. Остановите
только проблемный отчётный timer и его service, если он ещё работает.
Collector и same-envelope renewal сохраните. Откат — exact SHA:

```sh
sudo systemctl disable --now <FAILED_REPORT_TIMER>
sudo systemctl stop <FAILED_REPORT_SERVICE>
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_live_release.py --repo <SOURCE_REPO> --deploy-root /opt/solana-alpha-lab --target-sha <PREVIOUS_SHA> --main-sha <MAIN_SHA> --live-sha <CURRENT_LIVE_SHA> --mode canonical-rollback
```

Повторно установите обе service templates от rollback tree и выполните
`daemon-reload`. Если predecessor template не содержит caps, сохраните
MemoryMax=768M/TimeoutStartSec=180s отдельным операционным drop-in; отчётные
timer остаются выключенными до повторной commissioning. Подтвердите deploy
pin и сохранённые состояния collector/renewal. Release дожидается текущего
oneshot и восстанавливает prior unit state; не убивайте collector и не удаляйте
`local/`, SQLite, RDP, dedupe, snapshots или receipts. `UNRESOLVED_RECOVERY`
требует отдельного recovery gate из host runbook; unit вслепую не запускать.

## Проверка результата через 7 и 30 дней

Один датированный readback на каждом рубеже: OOM/service failures; MemoryPeak
watch/pulse против роста ledger; source clocks и RDP progression при наличии
due; backup/archive verification; очередной same-family rollover; факт
доставки daily и incident/recovery. Это контроль после commissioning, а не
новая ежедневная ручная процедура или новая automation.
# Episode preparation boundary

Episode commissioning also requires `docs/operator/OPPORTUNITY_EPISODES_OPERATOR_V1.md`
and `docs/contracts/research_write_lookup_v1.md`. The existing metadata-only host
recipes do not authorize recursive RDP scans, prepared-index work, backup,
status/doctor schema paths, deploy or timer changes on production. Those remain
separate OPERATE actions. Explicit preparation is measured on a verified copy;
its filesystem-bound lookup cannot be transferred onto production. Under separate
OPERATE, verified backup, measured copy rehearsal and quiesced writers/timer,
`prepare_research_write_lookup.py --production-commissioning` prepares the canonical
root in place with the exact producer OPS store and both writer fences. Ordinary
deploy/tick/startup never prepare it. Restore/moved-root/code rollback preserve
canonical history and require explicit preparation on the target root before
returning to new writer code. Whole-Factory storage UNKNOWN blocks activation;
runtime reserve uses the exact commissioned producer-local envelope. Windows process proof is not Linux unit
or power-loss acceptance. Notification freshness is not proof of off-host
delivery; an absent receiver remains NOT_CONFIGURED.

Episode tick `TICK_REFUSED_ACTIVE_TRANSITION_PROOF_UNAVAILABLE` with NEXT
`RECONCILE_ACTIVE_TRANSITION_PROOF` has the diagnostic/recovery route in
`OPPORTUNITY_EPISODES_OPERATOR_V1.md`. Preserve activation IDs, ledger, journal
and canonical bytes; diagnose on a verified isolated copy. The generic terminal
does not authorize reprepare: confirmed lookup reconciliation uses the existing
separate OPERATE commissioning prerequisites/fences; missing evidence or an
unresolved cause requires a repair gate. Do not bypass the proof gate or copy a
prepared lookup to production.

## I2 bounded maintenance

Native owner — `observation_schedule_retention.py`, CLI —
`scripts/observation_schedule_retention.py`. Exact task/readout/rollout находятся
в `docs/evidence/i2_backup_legacy_storage_v1/`. Без commissioned policy maintenance
выключена. Одобренный hash фиксирует scopes или managed lineages, terminal
predicate, реальные frozen minimum ages, source/cold closure, rows/bytes/wall,
cadence и pressure/due guards. Future managed children не требуют новых IDs.

Одобренные `max_run_chunks` и `max_run_wall_seconds` позволяют одному запуску
обработать конечный backlog несколькими chunks; без этих полей сохраняется
старый single-step режим. Все locks/leases отпускаются между chunks. Приоритет
due/pressure и CAS повторяются на каждом шаге; краткий YIELD ждёт без writer,
исчерпанный run сохраняет durable cursor до следующего штатного caller.
Archive refresh использует тот же отсчёт времени, суммарные effects и остаток
chunk budget; завершённый chunk перед refresh также расходует лимит. Cadence
допускает новый RUN и сама по себе не создаёт таймер или дополнительные вызовы.

COMPLETED occurrence и request-keyed poll-cache проверяются отдельно. Совпадение
request с другим STARTED не объединяет ответы; UNKNOWN остаётся без изменений.
Poll body требует точного native occurrence, COMPLETED source с тем же request
и response hash, однозначного lifecycle owner и всех consumer/pin/cold guards.
Request-only, stale или неоднозначная ссылка защищается. DISCOVERY ownership
восстанавливается штатным deterministic identity, а не альтернативной наукой.
Commissioned policy создаёт индекс существующего poll occurrence pointer один
раз; ordinary startup/history не сканирует. Full recovery fingerprint сохраняет
прежние bytes/ROWIDs/schema/sequences; bounded small cells читаются одним SQL,
large cells по-прежнему хешируются потоково.

Обычный existing daily/weekly offhost caller после verified checkpoint запускает
maintenance, вновь беря backup-plane lock перед OPS fence. Independent remote
restore получает собственный hash-bound policy budget в пределах existing reader3h;
бывший300s ceiling был меньше измеренного449.54s restore на production-sized copy.
Это допустимость новой approved policy, не автоматическое увеличение production
лимита. Recurring closure может содержать9обычных weekly/daily объектов плюс
raw archives, поэтому single-full8objects/600s не являются гарантией. Signed
policy отдельно фиксирует native ceilings и фактическую required closure;
registration измеряется отдельно и не объявляется бесплатной. Source-verified HOT90 raw day archives дают exact cold proof. Один
completed cache и один pending admission ограничивают local overlap; remote
scientific pins сохраняются до отдельного source/I4 disposition. Нет нового
timer, daily agent или ежедневного `record-backup`. Daily physical reclaim
не включается: это отдельная quiesced операция из staged OPERATE packet.

`status`/`plan` открывают existing SQLite read-only и учитывают WAL. `apply`
проверяет approved plan/candidate/dependencies и сохраняет cursor с каждым chunk.
Active/tail/UNKNOWN, незакрытые publication/export/raw dependencies защищены.
Возраст сам по себе не даёт retirement. Oversized body остаётся protected с
durable refusal; bounded cursor продолжает другие записи, health не рисует READY.
FAILED создаёт incident через existing watch; disabled policy молчит, yields
по cadence/pressure/due не являются failure. Backup success не скрывает failure
maintenance или последней попытки upload.

При approved policy revision существующий active plan проходит bounded identity/
candidate/cold/effect checks и помечается SUPERSEDED_POLICY; только неприменённый
остаток отменяется. Выполненные effects, ROWIDs, clocks, provenance и cold pins
сохраняются; новая policy получает свежую bounded selection. Disable/enable и
stale intent предыдущего бинарника продолжаются через обычный caller. Настоящий
candidate/integrity conflict остаётся FAILED/refusal и не вызывает автоматический
replan. Ни SQL-редактирование, ни ежедневный owner action для обычной смены
approved policy не требуются.

Pending cold refresh также reconciles approved revision: exact checkpoint и pins
сохраняются, допустимый target получает новую policy binding и проходит обычный
restore/register. Disable приостанавливает target; после enable действует новая
selection/scope. Несовместимый cold root/refresh budget виден как BLOCKED_POLICY/
FAILED и требует точной допустимой revision; false COMPLETE и новая cache
generation не создаются. Повреждённые identity/source/pins остаются отказом.

Local-full сохраняет отдельную 12h local recovery obligation; daily offhost
24h source-clock gate её не заменяет. Его ordinary scheduled caller повторяет
только typed `WRITER_BUSY` теми же ≤120min/30s, без нового daemon, изменения
units/cadence/RPO или правки offhost last-good/pending. Исчерпание видно как
`LOCAL_BACKUP_BUSY_RETRY_EXHAUSTED`; другие отказы не маскируются retry.

Backup contention автоматически повторяется существующим caller ≤120min/30s;
weekly/daily overlap объединяется по verified bytes и durable pointer. Exhausted
wait даёт COPY_FAILED/OFFHOST_BUSY_RETRY_EXHAUSTED в bounded scheduler receipt,
точный pending/resume и existing watch incident; last-good остаётся прежним.
Успех active backup owner снимает incident. Timers/RPO24h не меняются.
При одинаковой секунде timestamps terminal failure имеет приоритет над
IN_PROGRESS; success снимает такой incident только для того же checkpoint.
