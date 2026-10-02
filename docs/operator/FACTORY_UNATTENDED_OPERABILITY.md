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

Первая read-only проверка на хосте из `/opt/solana-alpha-lab`:

```sh
date -u
cat .factory_deploy_sha
systemctl show factory-operability-watch.service factory-collector-owner-pulse.service --property=Result,ExecMainStatus,MemoryPeak,MemoryMax,TimeoutStartUSec
systemctl list-timers factory-operability-watch.timer factory-collector-owner-pulse.timer factory-observation-schedule.timer factory-same-envelope-renewal.timer --no-pager
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
Дополните проверку узким `observation_schedule.py status`
из collector runbook. Не читайте весь ledger и не запускайте старый полный
packet на хосте после OOM. `PROVIDER_STATE_UNKNOWN` означает непроверяемую
диагностику: проверьте scope и clocks, не объявляйте провайдера здоровым.
Watch выдаёт отдельный `CALL_DIAGNOSTICS_UNKNOWN` после 1800s; прежний
`MATERIAL_COVERAGE_DEGRADATION` означает только подтверждённый `DISCOVERY_GAP`.
Heartbeat с настроенным URL и свежим snapshot — реальный HTTPS-запрос;
не используйте его как read-only probe.

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

3. Watch dry-run под лимитом; `oneshot` делает TimeoutStartSec ограничением
   всей команды. Сохраните terminal, wall и memory accounting из вывода `--wait`:

```sh
sudo systemd-run --unit=factory-watch-commissioning --service-type=oneshot --wait --property=MemoryAccounting=yes --property=MemoryMax=768M --property=TimeoutStartSec=180s --property=WorkingDirectory=/opt/solana-alpha-lab /usr/bin/uv run --locked --managed-python python -B scripts/factory_operability_watch.py --mode dry-run --skip-systemd
```

[`systemd-run --wait`](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd-run.xml)
выводит runtime/exit и доступные accounting data; успешно завершённая transient
unit может сразу исчезнуть. Не считывайте её отсутствующий MemoryPeak как ноль.
Если host не отдаёт peak, результат `UNKNOWN` и timer не включать до отдельного
профиля под теми же лимитами. Требуется peak <512 MiB, wall <120s и exit=0.
Git fixture evidence не заменяет host проверку. По read-only dry-run preview
также проверьте snapshot/incident semantics; dry-run snapshot не записывает.

4. Только после PASS включите watch. Подтвердите два последовательных цикла,
   свежий валидный snapshot, MemoryPeak/время, incident/recovery и Telegram
   delivery/retry с отдельно разрешённой проверкой. Collector/renewal продолжаются:

```sh
COMMISSIONING_START=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
sudo systemctl enable --now factory-operability-watch.timer
systemctl show factory-operability-watch.service --property=InvocationID,ExecMainStartTimestamp,ExecMainExitTimestamp,Result,ExecMainStatus,MemoryPeak
journalctl --unit=factory-operability-watch.service --since "$COMMISSIONING_START" --output=short-iso --no-pager
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

5. Отдельно выполните bounded pulse dry-run:

```sh
sudo systemd-run --unit=factory-pulse-commissioning --service-type=oneshot --wait --property=MemoryAccounting=yes --property=MemoryMax=768M --property=TimeoutStartSec=180s --property=WorkingDirectory=/opt/solana-alpha-lab /usr/bin/uv run --locked --managed-python python -B scripts/collector_owner_pulse.py --mode dry-run
```

При тех же PASS-критериях включите pulse и подтвердите его реальный запуск
и daily delivery. Два отчётных timer не включаются одним шагом:

```sh
PULSE_START=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
sudo systemctl enable --now factory-collector-owner-pulse.timer
sudo systemctl start factory-collector-owner-pulse.service
systemctl show factory-collector-owner-pulse.service --property=InvocationID,ExecMainStartTimestamp,ExecMainExitTimestamp,Result,ExecMainStatus,MemoryPeak
journalctl --unit=factory-collector-owner-pulse.service --since "$PULSE_START" --output=short-iso --no-pager
```

В journal нужен `# delivery delivered=True deduped=False` и полученная daily
карточка за тот же UTC day. `delivered=False deduped=True` принимается только
со ссылкой на ранее доказанную доставку этого day; один dedupe не доказывает
её. `delivered=False deduped=False`, отсутствие delivery footer, pending или
failure — `BLOCKED`. Snapshot и exit=0 delivery footer не заменяют.

6. Внешний получатель, URL и Telegram-маршрут требуют отдельного решения
   владельца. До подключения и теста пропущенного heartbeat — `NOT_CONFIGURED`.
   Fresh watch snapshot сам по себе не доказывает Telegram-доставку.

Stop: OOM, timeout, peak >=512 MiB, wall >=120s, stale/invalid snapshot,
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
