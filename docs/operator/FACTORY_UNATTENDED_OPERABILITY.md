# Factory unattended operability

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
| Daily owner pulse | `factory-collector-owner-pulse.timer` | `*-*-* 06:15:00 UTC` |
| Local operability watch | `factory-operability-watch.timer` | every 15 minutes UTC |
| External heartbeat (local half) | `factory-external-heartbeat.timer` | every 5 minutes UTC |

Archive, Telegram and heartbeat failures must not stop the collector.
Collector death must still be visible to the local watch while the VPS is alive.

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
`FACTORY_EXTERNAL_HEARTBEAT_URL`. Unconfigured is a typed no-op. No URL,
account, or provider is in Git.

## WHAT MESSAGE SHOULD THE OWNER EXPECT?

- One daily card at 06:15 UTC: `FACTORY / DAILY — OK | DEGRADED | ACTION`.
- One `INCIDENT` when a material fail persists past the owned grace.
- One `RECOVERED` when it clears.
- No routine PENDING / historical STARTED / single transient transport spam.

Parser footer fields: `MESSAGE_TYPE`, `STATE`, `INCIDENT`, `COLLECTOR_STATE`,
`LIFECYCLE_STATE`, `ARCHIVE_LAST_VERIFIED_DAY`, `ARCHIVE_BACKLOG_DAYS`,
`MUTABLE_BACKUP_STATE`, `PROJECTED_97D_BYTES`, `OWNER_ACTION`.

## WHAT IS SAFE TO READ?

- `scripts/hot90_activation.py show`
- `scripts/collector_owner_pulse.py --mode dry-run`
- `scripts/factory_operability_watch.py --mode dry-run --skip-systemd`
- `scripts/hot90_closed_day_durability.py` (no-op unless runtime is
  `DURABILITY_CUTOVER`/`RETENTION_ACTIVE` with Drive writes enabled)
- `scripts/factory_external_heartbeat.py` (no-op unless URL is configured)
- `scripts/factory_remote_doctor.py` status/offhost-status surfaces from the
  collector runbook (do not pass `--backup` unless that exact OPERATE atom
  is named)

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

Disable only the new units (`factory-hot90-closed-day-archive`,
`factory-operability-watch`, `factory-external-heartbeat`). Keep receipts,
source RDP, and HOT90 runtime activation. Restore a previous exact deploy
SHA if required. Do not “rollback” by deleting runtime truth.

## Commissioning (future OPERATE, not this Git change)

1. Fresh host readback (SHA, HOT90 runtime, services, disk, backup).
2. Exact live SHA vs exact merged-target SHA review.
3. Owner-gated exact-SHA deploy.
4. Post-deploy HOT90 runtime continuity readback.
5. Owner-gated install/enable of only the new units.
6. One real eligible closed-day archive → Drive → exact SHA → receipt.
7. Next scheduled or one real DAILY delivery.
8. Deterministic incident dry proof.
9. Collector/source progression and mutable backup unchanged.
10. External heartbeat remains `NOT_CONFIGURED` until separately authorized.
