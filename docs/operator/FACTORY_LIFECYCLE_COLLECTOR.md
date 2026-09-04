# Factory lifecycle collector — operator runbook

Канон для ObservationSchedule / Tokens V2 lifecycle collector на Factory VPS.
Читать **вместе с** `FACTORY_REMOTE_HOST.md` (host locator). Этот файл — протокол
collector; host locator не дублировать.

Секреты в Git и в чат не попадают. Это не alpha и не `OPERATIONAL_READY`.

## Historical 2026-09-04 chain (not current health)

These terminals are historical evidence. They do **not** prove current runtime
health; that requires a fresh `doctor` / `status` / operational-packet readback.

| Proven historically | Terminal / interpretation |
|---|---|
| Live publication operability | `OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_LIVE_PASS` |
| Isolated nonempty RDP restore | `NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF_PASS` |
| `legacy_full` reclaim executed | machine terminal **`LEGACY_FULL_RECLAIM_FAIL`** |
| Why FAIL | `RECLAIM_EFFECTIVE` / `ACCEPTANCE_FALSE_NEGATIVE_CONCURRENT_PUBLICATION` |

Project-level interpretation (do not rewrite the machine terminal):
`RECLAIM_EFFECTIVE / ACCEPTANCE_FALSE_NEGATIVE_CONCURRENT_PUBLICATION`.

Reclaim acceptance required exact pre/post scientific fingerprint equality while
the collector stayed `ACTIVE`. Live ticks legally appended publications, so the
hash changed. Exact pre-file inventory was not persisted; do not invent a
retrospective subset proof. Do **not** auto-repeat restore or reclaim from this
runbook. Concurrent append-only operations must preserve the pre-existing
scientific path+hash set as a subset of post-state; full fingerprint equality is
valid only when the writer is frozen.

## Architecture

| Plane | Where | Role |
|---|---|---|
| Live Observation Plane | VPS `/opt/solana-alpha-lab` | moving collector truth (schedule, SQLite, observation_rdp) |
| Research Evidence Plane | canonical local `local/factory_v1/data_plane` | Forge-visible sealed evidence |
| Evidence boundary | Discovery Evidence Release seal → verify → import | only sealed import changes Forge `evidence_epoch` |

**Operational vs scientific storage (do not conflate):**

| Substrate | Path / artifact | Role | Retention |
|---|---|---|---|
| ObservationSchedule SQLite | `local/factory_v1/observation_schedule_state.sqlite` | operational scheduler / call ledger / poll cache / accounting — **not** scientific truth | `raw_retention_days` (campaign default **31**) may compact aged COMPLETED provider **decoded JSON bodies** to provenance metadata |
| Observation RDP / Parquet | `local/factory_v1/observation_rdp` | immutable scientific panel publication | `canonical_panel_retention = IMMUTABLE` — **never** auto-deleted by retention |
| Sealed live releases / LIVE CORPUS | sealed release dirs + corpus lineage | exploratory scientific publication | **never** auto-deleted by retention |

**`raw_retention_days = 31` means:** after 31 UTC days, and only when related due work is scientifically closed, COMPLETED `call_ledger` rows may drop large decoded provider payload fields (`rows` / body) while keeping `call_occurrence_id`, `request_sha256`, `response_sha256`, HTTP class/timing, and identity. It does **not** mean byte-identical original HTTP response retention — the substrate is **decoded/canonical provider JSON** in SQLite.

What may be safely compacted: aged COMPLETED operational provider bodies; aged `poll_slots` cache bodies when they cannot participate in current scheduling/recovery.

What is never automatically deleted: Observation RDP/Parquet, sealed live releases/corpus, candidate/member denominator rows, authority receipts, activation identity, accounting identity, unfinished/STARTED/IN_FLIGHT calls, anything younger than `raw_retention_days`.

- Forge **never** reads moving VPS truth directly.
- Continuous observation alone does **not** change Forge evidence epoch.
- Discovery-only history (`DISCOVERY_ONLY_SECOND_LOOK`) cannot confirm hypotheses
  discovered from it (`confirmatory_reuse_forbidden`).

## Host / runtime

Host identity: `docs/operator/FACTORY_REMOTE_HOST.md` +
`docs/operator/factory_remote_host_v1.yaml` only.

| Item | Canonical value |
|---|---|
| Deploy root | `/opt/solana-alpha-lab` (exact-SHA, **no `.git`**) |
| Producer identity | `.factory_deploy_sha` (40 lowercase hex) after optional config / Git HEAD |
| Runtime config | `configs/observation_schedule_runtime_v1.yaml` |
| Units | `factory-observation-schedule.service` / `.timer` |
| Unit templates | `configs/factory_remote_ops/factory-observation-schedule.*` |
| Production tick env | systemd `EnvironmentFile=-/etc/solana-alpha-lab/secrets.env` (not bare `uv tick`) |
| SQLite | `local/factory_v1/observation_schedule_state.sqlite` |
| Observation RDP | `local/factory_v1/observation_rdp` |
| Service user | systemd oneshot as **root** (no `User=` in unit); paths owned `root:root` |
| Credential env (name only) | `JUPITER_FREE_API_KEY` (compat alias `JUPITER_API_KEY` only if sanctioned unset) |

Producer SHA resolution order (runtime):

1. explicit `producer_git_sha` in runtime config (valid 40 hex)
2. `git rev-parse HEAD` when a valid Git worktree answers
3. `.factory_deploy_sha` on sanctioned no-`.git` exact-SHA root

The deploy-pin value is **identity only** — it grants no ObservationSchedule
authority and no provider calls.

## Routine methods (exact commands)

All host commands: SSH as `factory`, then `cd /opt/solana-alpha-lab`.

### Read-only

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule.py status --runtime-config configs/observation_schedule_runtime_v1.yaml
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule.py doctor --runtime-config configs/observation_schedule_runtime_v1.yaml
```

```
systemctl is-active factory-observation-schedule.timer factory-observation-schedule.service factory-remote-backup.timer
```

```
systemctl is-active factory-remote-backup.timer factory-remote-backup-gdrive.timer factory-remote-backup-gdrive-delta.timer
```

```
systemctl is-active factory-remote-backup.service factory-remote-backup-gdrive.service factory-remote-backup-gdrive-delta.service
```

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py --offhost-status
```

```
sudo stat -c 'mode=%a owner=%U:%G size=%s' /etc/solana-alpha-lab/rclone.conf
```

```
sudo /usr/bin/rclone --config /etc/solana-alpha-lab/rclone.conf about factory-gdrive:
```

Never `cat` `/etc/solana-alpha-lab/rclone.conf` — metadata only.

```
systemctl status factory-observation-schedule.timer --no-pager -n 20
```

```
cat .factory_deploy_sha
```

```
diff -q configs/factory_remote_ops/factory-observation-schedule.service /etc/systemd/system/factory-observation-schedule.service
```

Zero-network campaign preflight (operator workstation or host; **no authorize**):

```
/usr/bin/uv run --locked --managed-python python -B scripts/collector_campaign_preflight.py --starts-at 2026-09-02T00:00:00Z
```

Discovery release seal/verify/import (local RDP; zero network):

```
/usr/bin/uv run --locked --managed-python python -B scripts/discovery_evidence_release.py verify --release-root <RELEASE_ROOT>
```

### Cross owner / deploy / provider authority (do not invent)

| Action | Gate |
|---|---|
| Exact-SHA deploy / rollback | `scripts/factory_live_release.py` + owner deploy atom |
| Place Jupiter key | owner only → `/etc/solana-alpha-lab/secrets.env` (name `JUPITER_FREE_API_KEY`) |
| Independent backup sink | owner decision on `FACTORY_BACKUP_SINK` (absolute other volume) |
| Authorize / activate schedule | exact ObservationSchedule owner phrase from runtime |
| Live provider calls | only after authorize+activate+credential |

### No-live smoke (safe when no activation)

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule.py tick --once --runtime-config configs/observation_schedule_runtime_v1.yaml
```

Expected without live activation:

```json
{"terminal":"TICK_REFUSED_NO_LIVE_DEFAULT","provider_calls":0,"credential_reads":0}
```

Not expected on a healthy exact-SHA root after producer-SHA repair:

```json
{"terminal":"PRODUCER_GIT_SHA_UNAVAILABLE"}
```

## Secrets

| Location | Rule |
|---|---|
| Host | `/etc/solana-alpha-lab/secrets.env` mode `0600` |
| Operator PC | `local/factory_remote_ops/secrets.env` (gitignored) |

Names only (never print values):

- `JUPITER_FREE_API_KEY` — sanctioned
- `JUPITER_API_KEY` — compat alias if sanctioned unset
- `FACTORY_TELEGRAM_BOT_TOKEN` / `FACTORY_TELEGRAM_CHAT_ID`
- `FACTORY_BACKUP_SINK` — absolute other-volume path, or empty → same-volume git-side sink

No wallet / signer / transaction credentials in this collector path.

## Scientific operation (compact)

- Source poll: `/tokens/v2/recent` (survivor-safe stream) + due `/tokens/v2/search`
- Failures are typed (`MISSING_TYPED` / HTTP class); unknown is never zero
- X = eligibility snapshot offset; Y = later horizons on the same member
- Sampling / Free-tier envelope from `collector_campaign_preflight` / oracle
- Retry=false, fallback=false, cash=$0

## How a future agent recovers current state

Do **not** trust chat “current status”. Machine-resolve:

| Question | Command / receipt |
|---|---|
| Deployed SHA | `cat /opt/solana-alpha-lab/.factory_deploy_sha` |
| Activation | `observation_schedule.py status` / doctor collector fields |
| Collector health | `observation_schedule.py doctor` + `factory_remote_doctor.py` |
| Campaign envelope | `collector_campaign_preflight.py` (zero-network) |
| Coverage class | doctor / collector read model `discovery_coverage_class` |
| Backup | doctor `backup` / `backup_domain`; timer `factory-remote-backup.timer` |
| Off-host Google Drive copy | doctor `--offhost-status`; receipt `local/factory_v1/offhost_backup_receipt.json`; timer chain below |
| Latest **historical** A3 discovery release | RDP singleton `DATASET-MANIFEST-DISCOVERY-EVIDENCE-RELEASE-001*` (unchanged) |
| Latest **live** lifecycle corpus | RDP `DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001` current version via lineage `datasets/live_lifecycle_corpus/lineage.json` + HFIC current-version selection |
| Forge evidence epoch | HFIC preflight / `evidence_epoch_sha256` over canonical local RDP |
| Publication-job journal | `scripts/observation_publication_jobs.py status` / `dry-run` |

**Operational vs recovery journal (do not conflate):** `open/` is the only
routine tick repair glob. `completed/` holds compact terminal receipts without
`observations` / `members`. `legacy_full/` historically parked byte-identical
full JSON until the 2026-09-04 restore proof and reclaim. At the 2026-09-04
reclaim post-readback the path was empty (`0` files / `0` B). Current state
requires fresh status/readback. Do not delete remaining science. Do not
re-run restore or reclaim merely because older NEXT prose still mentioned them.

## Publication-job journal migration + live vertical smoke

Repository software close is `OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_SOFTWARE_PASS`.
Live terminal `OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_LIVE_PASS` is a
**separate exact owner gate** after merge/deploy. Do not tick a new SHA until
migration APPLY. Do not resume by intuition after a hard fail — immediately
`PAUSED_OPERATOR` and keep evidence.

Take `schedule_sha256` and `activation_id` from status. Do not invent them.

### A. PAUSED preflight

```
cat /opt/solana-alpha-lab/.factory_deploy_sha
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule.py status --runtime-config configs/observation_schedule_runtime_v1.yaml
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule.py doctor --runtime-config configs/observation_schedule_runtime_v1.yaml
```

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py
```

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py --offhost-status
```

```
systemctl is-active factory-observation-schedule.timer factory-observation-schedule.service
```

```
systemctl status factory-observation-schedule.timer --no-pager -n 20
```

```
/usr/bin/uv run --locked --managed-python python -B -c "import sqlite3; from pathlib import Path; p=Path('local/factory_v1/observation_schedule_state.sqlite'); c=sqlite3.connect(f'file:{p.as_posix()}?mode=ro', uri=True); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print('STARTED', c.execute(\"SELECT COUNT(*) FROM call_ledger WHERE state='STARTED'\").fetchone()[0])"
```

Require: exact deployed SHA; `PAUSED_OPERATOR`; timer/service not running a worker; lease clear/expired; SQLite `ok`; backup/offhost status recorded; disk/resource baseline from doctor/packet.

`observation_schedule.py doctor` while `PAUSED_OPERATOR` is expected to print `DOCTOR_PAUSED` and exit 2. That is the READY signal for this gate, not a reason to resume.

### B. Migration (collector remains PAUSED)

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_publication_jobs.py status --runtime-config configs/observation_schedule_runtime_v1.yaml
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_publication_jobs.py dry-run --runtime-config configs/observation_schedule_runtime_v1.yaml
```

Require `classified_ambiguous=0`. APPLY builds a complete in-memory plan of every unmigrated source and fails **before the first filesystem mutation** on ambiguous payloads, unconstructable compact receipts, destination identity/byte conflicts, or duplicate `content_sha256` with differing source bytes. Peak payload memory is `O(max job bytes)`, not `O(total unmigrated payload)`. If `classified_ambiguous>0`: stay `PAUSED_OPERATOR`, do not APPLY, keep evidence, open a new atom. Then APPLY (same filesystem, no provider calls, no RDP rewrite, no STARTED cleanup, no `legacy_full` deletion):

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_publication_jobs.py apply --runtime-config configs/observation_schedule_runtime_v1.yaml --i-understand-apply
```

Prove scientific Parquet/manifests/RDP inventory excluding the journal (compare before vs after APPLY):

```
/usr/bin/uv run --locked --managed-python python -B -c "from pathlib import Path, hashlib; root=Path('local/factory_v1/observation_rdp'); jobs=root/'datasets'/'publication_jobs'; parts=[];
[parts.append(f'{p.relative_to(root).as_posix()}:{hashlib.sha256(p.read_bytes()).hexdigest()}') for p in sorted(root.rglob('*')) if p.is_file() and 'publication_jobs' not in p.parts]; print(hashlib.sha256('\n'.join(parts).encode()).hexdigest())"
```

Prove `legacy_full` bytes preserved and `publication_jobs_open_count` bounded to genuine incomplete jobs via `status`.

### C. One manual production tick

Stop the timer. Resume the same activation. One canonical tick via the existing
systemd oneshot, which loads `EnvironmentFile=-/etc/solana-alpha-lab/secrets.env`.
The unit does **not** declare `TimeoutStartSec`; the 90s hard cutoff is this
operator procedure (`timeout` of the `systemctl` client, then explicit service
stop). Bare `sudo uv … tick` without that EnvironmentFile is **not** a canonical
production surface: live proof observed `CREDENTIAL_ENV_MISSING`. Do not
change the unit for documentation.

```
sudo systemctl stop factory-observation-schedule.timer
```

Resume uses `--schedule-sha256` and `--activation-id` from status:

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule.py resume --runtime-config configs/observation_schedule_runtime_v1.yaml --schedule-sha256 <schedule_sha256> --activation-id <activation_id>
```

```
sudo /usr/bin/timeout 90s /usr/bin/systemctl start factory-observation-schedule.service
rc=$?
if [ "$rc" -eq 124 ]; then
  sudo /usr/bin/systemctl stop factory-observation-schedule.service
  echo "TICK_HARD_CUTOFF_90S"
  exit 124
fi
test "$rc" -eq 0
```

Hard acceptance: no `TICK_HARD_CUTOFF_90S`; no `LEASE_FENCED`; no leaked worker; no unbounded pre-provider CPU; publication repair with zero open jobs comfortably <2s; tick reaches provider path; new provider occurrence does not remain STARTED; raw call record has request/response/timing/status/hash provenance; no scientific corruption. Ordinary service failure (`rc` not 0 and not 124) stays distinct from timeout. A legitimate market `no eligible rows` is not failure — it must be explicit. `CREDENTIAL_ENV_MISSING` is a credential-surface miss, not a publication-CPU fail.

### D. Three normal timer ticks

If the manual tick PASS, run exactly three ordinary 60s timer cycles / max ~4 minutes.

```
sudo systemctl start factory-observation-schedule.timer
```

```
systemctl is-active factory-observation-schedule.timer factory-observation-schedule.service
```

Require: 3 consecutive bounded completions; no `LEASE_FENCED`; no accumulating STARTED; source poll continues advancing; open publication jobs return to zero or a bounded genuine incomplete state; no CPU/RSS runaway; disk/job counters follow the new lifecycle. If publishable work exists, verify one new RDP publication end-to-end (member/observation → manifest → `.published`) with PIT clocks and identities.

### E. Terminal

If all PASS: `OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_LIVE_PASS`. Leave the same activation `ACTIVE`, timer enabled+active.

If ANY hard criterion fails:

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule.py pause --runtime-config configs/observation_schedule_runtime_v1.yaml --schedule-sha256 <schedule_sha256> --activation-id <activation_id>
```

```
sudo systemctl stop factory-observation-schedule.timer
```

Preserve evidence. No second repair by intuition.

Live PASS, nonempty restore proof, and `legacy_full` reclaim are historical
(see table above). Do not treat them as the next atom.

## Commissioning checklist / open gates

### Live cohort seal / import (zero-provider)

Scientific path (not weekly A3 singleton):

Immutable Observation RDP → `build-live-source` → cohort readiness →
`seal-live-cohort` → `verify-live` → `import-live` → **cumulative** LIVE CORPUS →
evidence_epoch.

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py build-live-source --observation-rdp <OBS_RDP> --schedule-sha256 <64hex> --activation-id <ACT-...>
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py live-status --observation-rdp <OBS_RDP> --cohort-id REL-YYYYMMDDTHHMMSSZ-YYYYMMDDTHHMMSSZ
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py seal-live-cohort --observation-rdp <OBS_RDP> --cohort-id REL-... --release-root <RELEASE>
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py verify-live --release-root <RELEASE>
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py import-live --release-root <RELEASE> --data-root <LOCAL_RDP>
```

Admission clock: `discovery_first_reliable_available_at` on campaign-relative
half-open 7-day windows from schedule `activation.starts_at` /
`stops_admitting_at` (not unix-epoch calendar buckets).
Current corpus version rebinds all accepted cohort partitions without parquet
byte duplication. Live role: `EXPLORATORY_REUSE` with
`confirmatory_reuse_forbidden=true`.
`/recent` is the observable provider discovery stream — not a proven complete
pump.fun universe unless coverage class says otherwise.


## Commissioning checklist / open gates

Machine-resolved; do not freeze ephemeral PASS/FAIL into this prose.

1. Runtime producer-SHA resolution (this repair)
2. Exact-SHA deploy + readback of repaired main
3. Key-only SSH baseline (`PasswordAuthentication no`)
4. Jupiter credential placement (`JUPITER_FREE_API_KEY`)
5. Independent backup decision (`FACTORY_BACKUP_SINK` other volume vs accept same-volume)
6. Off-host Google Drive durability automation (deploy + enable `factory-remote-backup-gdrive.service` chain)
7. Live campaign authority (exact ObservationSchedule phrase)
8. Live commissioning (timer enabled, ticks with authority)
9. Daily owner pulse — product ready; install/enable timer only after this collector/storage closure (not automatic from this runbook)
10. Live cohort seal / sync / import into LIVE CORPUS (product ready; ops after collector commissioning)
11. **`NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF`** — **historically proven** 2026-09-04 (`NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF_PASS`). Isolated restore only for future recovery; never over live Factory state; do not auto-repeat.
12. Forge

## DAILY_COLLECTOR_OWNER_PULSE

One daily Telegram summary (not incident spam). Reuses
`FACTORY_TELEGRAM_BOT_TOKEN` / `FACTORY_TELEGRAM_CHAT_ID` only — **never** Jupiter
credentials. Immediate remote-ops incident alerts remain separate and deduplicated.

Deterministic schedule bytes: `OnCalendar=*-*-* 06:15:00` UTC
(`configs/factory_remote_ops/factory-collector-owner-pulse.timer`). Templates only —
do **not** install/enable in the software baseline atom.

### Dry-run (zero network, zero credential VALUE reads)

```
/usr/bin/uv run --locked --managed-python python -B scripts/collector_owner_pulse.py --mode dry-run
```

### Emit (Telegram only; reads only Telegram env values)

```
/usr/bin/uv run --locked --managed-python python -B scripts/collector_owner_pulse.py --mode emit --record-storage-history
```

### Operational packet + health classes

Composed from collector_read_model + remote-ops disk/backup + live-release fields.
Health classes include: `PROCESS_OK`, `DATA_STALE`, `PROVIDER_AUTH_FAILED`,
`PROVIDER_RATE_LIMITED`, `PROVIDER_FAILED`, `DISCOVERY_GAP`,
`DISCOVERY_COVERAGE_UNKNOWN`, `BACKLOG_RISK`, `BUDGET_BLOCKED`,
`RDP_PUBLICATION_STALE`, `BACKUP_DEGRADED`, `OFFHOST_BACKUP_STALE`, `OFFHOST_BACKUP_FAILED`,
`DISK_WARNING`, `DISK_CRITICAL`,
`RELEASE_BLOCKED`. Zero eligible market supply is **not** provider failure.
Unavailable metrics use `UNKNOWN` / `NOT_APPLICABLE` — never silent zero.

Disk policy (measured % used; does not auto-resize or delete science):

| Threshold | Class |
|---|---|
| <70% | NORMAL |
| ≥70% | EARLY_WARNING (pulse text only; not a hard health class) |
| ≥80% | DISK_WARNING |
| ≥85% | DISK_CRITICAL (remote-ops hard safety reference unchanged) |

### Retention status / dry-run / apply

Default is dry-run. Apply requires exact `--i-understand-apply`. Never deletes
scientific RDP/releases. Safe around scheduler lease (`WRITER_BUSY` if tick holds lease).

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule_retention.py status --raw-retention-days 31
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule_retention.py dry-run --raw-retention-days 31
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule_retention.py apply --raw-retention-days 31 --i-understand-apply
```

VPS retention auto-enable is out of scope until final deploy atom.

### Future agent recovery (read-only first)

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule.py doctor --runtime-config configs/observation_schedule_runtime_v1.yaml
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/collector_owner_pulse.py --mode dry-run
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_schedule_retention.py status --raw-retention-days 31
```

```
/usr/bin/uv run --locked --managed-python python -B scripts/discovery_evidence_release.py live-status --observation-rdp local/factory_v1/observation_rdp --cohort-id <REL-...Z-...Z>
```

Current/live corpus: one stable `DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001` with
versioned manifests; weekly sealed releases import into that corpus — they are not
deleted by operational retention.

## Durability recovery (local + off-host Google Drive)

Fresh agents with **zero chat history** recover durability from Git +
machine readback only. Canonical Git:

- `configs/factory_remote_operations_v1_1.yaml` — `backup.offhost`, `google_drive_role`
- `configs/factory_remote_ops/factory-remote-backup*.service` — systemd chain
- `scripts/factory_offhost_backup_copy.py` — stage-2 copy-only surface
- `src/solana_alpha_lab/factory/offhost_backup.py` — receipt + health/readout

### Two-stage architecture (do not conflate)

| Stage | Mechanism | Output | Scientific truth? |
|---|---|---|---|
| **1 — local** | `factory-remote-backup.timer` (every 12h UTC) → `factory-remote-backup.service` → `factory_remote_doctor.py --backup` | `local/factory_v1_backup_sink/BACKUP_<sha256>.zip` (retain 1 verified) | **No** — operational durability only |
| **2 — off-host** | independent timers: weekly `factory-remote-backup-gdrive.timer` + daily `factory-remote-backup-gdrive-delta.timer` → `factory_offhost_backup_copy.py --mode weekly|daily` | remote `BACKUP_*.zip` / `DELTA_*.zip` + immutable `RECOVERY_CHECKPOINT_<UTC>_<sha256>.json` | **No** — copy-only cold mirror |

- **`FACTORY_BACKUP_SINK`** remains the optional **absolute other-volume** first-stage sink env name. Empty → git-side parent-independent sink under `local/factory_v1_backup_sink` (same volume, different parent). Google Drive is **never** `FACTORY_BACKUP_SINK`.
- **Copy-only:** `rclone copyto` only. **No** delete, move, purge, sync-delete, or FUSE mount.
- **Google Drive outage** must not invalidate a successful local backup artifact; stage 1 stays independently diagnosable.

### Fixed off-host constants (VPS)

| Item | Canonical value |
|---|---|
| rclone binary | `/usr/bin/rclone` |
| rclone config (metadata only) | `/etc/solana-alpha-lab/rclone.conf` (`root:root`, mode `0600`, non-empty) |
| logical remote name | `factory-gdrive` |
| remote folder | `solana-alpha-lab/factory-backups` |
| machine receipt | `local/factory_v1/offhost_backup_receipt.json` |
| google_drive_role | `PROVEN_OFFHOST_DURABILITY` (prior: `OPTIONAL_COLD_COPY_NOT_DOD`) |
| unproven after Git proof | `LIVE_FACTORY_INCREMENTAL_RESTORE_COMMISSIONING` (enable timers on live host; do not restore over live state) |

### Fresh-agent classification (machine JSON)

Read-only — **no Drive writes**, **no token/config body**:

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py --offhost-status
```

Use `agent_classification` booleans (exactly one primary off-host label applies):

| Label | When true |
|---|---|
| `LOCAL_BACKUP_OK` | `local_backup_state` == `OK` (newest local bundle age ≤ 24h) |
| `OFFHOST_BACKUP_OK` | `offhost.offhost_backup_state` == `CURRENT` (verified receipt age ≤ 24h) |
| `OFFHOST_BACKUP_STALE` | off-host state in `DEGRADED` (>24h), `HARD_ATTENTION` (>48h), `MISSING`, or `FAILED` |
| `OFFHOST_NOT_CONFIGURED` | `offhost.offhost_backup_state` == `UNCONFIGURED` (offhost block absent/disabled in Git config) |

Full doctor (local + off-host dimensions + verdict):

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py
```

Key JSON fields: `dimensions.backup_age`, `dimensions.offhost_backup`, `offhost_backup_state`, `offhost_last_verified_at`, `offhost_last_filename`, `offhost_last_sha256`, `durability_domain` (`OFF_HOST_INDEPENDENT` only when off-host `CURRENT`).

Daily pulse dry-run (human Backup section: `local … / offhost … / GOOGLE_DRIVE / …`):

```
/usr/bin/uv run --locked --managed-python python -B scripts/collector_owner_pulse.py --mode dry-run
```

### Off-host freshness / RPO (machine)

From `configs/factory_remote_operations_v1_1.yaml` → `backup.offhost`:

| Class | Age since `verified_at` | Meaning |
|---|---|---|
| `CURRENT` | ≤ 24h | Off-host checkpoint matches ~24h disaster RPO |
| `DEGRADED` | > 24h and ≤ 48h | Visible degradation; local backup may still be OK |
| `HARD_ATTENTION` | > 48h | Telegram path may emit `DEGRADED_OFFHOST_BACKUP_STALE` via doctor |
| `FAILED` | last receipt terminal is failure, **or** Git offhost enabled but rclone config metadata not ready | Typed copy/config conflict |
| `MISSING` | configured but no successful receipt | Never copy-assume from local health alone |

Receipt terminals (success): `DAILY_DELTA_VERIFIED`, `NO_CHANGES_VERIFIED`, `WEEKLY_FULL_VERIFIED`, `FULL_COVERAGE_RECONFIRMED_NO_CHANGE`, plus legacy `COPIED_VERIFIED` / `ALREADY_PRESENT_VERIFIED`. Payload counters `offhost_backup_payload_bytes_30d` / `projected_offhost_backup_payload_bytes_30d` are operational proxies, not Cherry billing. Never contains OAuth tokens.

Last verified bundle fields in receipt / `--offhost-status`: `source_backup_filename`, `source_sha256`, `source_bytes`, `remote_logical_path`, `remote_bytes`, `verified_at`.

### Read-only metadata checks (never print config body)

```
sudo stat -c 'mode=%a owner=%U:%G size=%s' /etc/solana-alpha-lab/rclone.conf
```

```
sudo /usr/bin/rclone --config /etc/solana-alpha-lab/rclone.conf about factory-gdrive:
```

```
systemctl is-active factory-remote-backup.timer factory-remote-backup.service factory-remote-backup-gdrive.timer factory-remote-backup-gdrive-delta.timer
```

### Isolated restore (sanctioned; never into live stores)

After download to an **isolated temp path** outside `/opt/solana-alpha-lab/local/factory_v1`:

```
/usr/bin/uv run --locked --managed-python python -B -c "from pathlib import Path; from solana_alpha_lab.factory.remote_ops import restore_incremental_chain_isolated; print(restore_incremental_chain_isolated(full_bundle=Path('<ISOLATED>/BACKUP_<sha256>.zip'), deltas=[Path('<ISOLATED>/DELTA_<sha256>.zip')], dest_root=Path('<ISOLATED>/restore-staging')))"
```

Requirements: manifest integrity PASS, SQLite integrity PASS, RDP inventory equality, restore markers respected, **no** replacement of live SQLite/RDP, deployed SHA unchanged.

Fresh-host recovery: newest valid `RECOVERY_CHECKPOINT_<UTC>_<sha256>.json` by **immutable filename timestamp**, then validate content hash, then follow referenced full/deltas. Do not use Drive listing order or object mtime.

Pre-live commissioning may prove restore with empty RDP. Live nonempty proof is
historical (`NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF_PASS`, 2026-09-04).
Future restore is recovery-only, never a default NEXT.

### Manual stage-2 copy (commissioning / recovery only)

Owner-authorized; not routine automation:

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_offhost_backup_copy.py --mode daily
```

Exit 0 → receipt updated. Local `--backup` remains separate and must succeed even if this fails.

## Launchpad population contract (2026-09-01 commissioning)

**Broken live schedule (MUST NOT RESUME):**

| Item | Value |
|---|---|
| `schedule_sha256` | `490c21b69a1f8f8f878eb9d909f3fce62e3ffa9891c73d2e85ade9790949f7d8` |
| `activation_id` | `ACT-490C21B69A1F8F8F` |
| Pause reason | `POPULATION_PREDICATE_SCHEMA_MISMATCH_CONFIRMED` |
| Terminal state | `PAUSED_OPERATOR` |

**Root cause:** Jupiter `/tokens/v2/recent` exposes pump.fun membership on top-level
`launchpad`, not on `firstPool.source` or top-level `source`. The authorized schedule
used `FIELD-FIRST-POOL-SOURCE-001 EQ pump.fun`, which projected `MISSING_TYPED` on
every live row, so all candidates became `NOT_SELECTED_PREDICATE` before Bernoulli
sampling.

**Repair:** `FIELD-LAUNCHPAD-001` (explicit launchpad text from `row["launchpad"]`).
`FIELD-FIRST-POOL-SOURCE-001` semantics are unchanged. Replacement campaign requires
**new** `schedule_sha256`, register, owner authorize phrase, and activate — never
resume the broken activation or mutate its registered document in place.

Evidence: `docs/evidence/factory_launchpad_population_contract_repair/`
Task: `docs/tasks/FACTORY_LAUNCHPAD_POPULATION_CONTRACT_REPAIR_V1.md`
