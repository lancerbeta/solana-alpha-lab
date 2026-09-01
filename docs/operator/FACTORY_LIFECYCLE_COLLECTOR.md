# Factory lifecycle collector — operator runbook

Канон для ObservationSchedule / Tokens V2 lifecycle collector на Factory VPS.
Читать **вместе с** `FACTORY_REMOTE_HOST.md` (host locator). Этот файл — протокол
collector; host locator не дублировать.

Секреты в Git и в чат не попадают. Это не alpha и не `OPERATIONAL_READY`.

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
systemctl is-active factory-remote-backup.service factory-remote-backup-gdrive.service
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

### Live cohort seal / import (zero-provider)

Scientific path (not weekly A3 singleton):

Observation RDP rebuild snapshot → cohort readiness → `seal-live-cohort` →
`verify-live` → `import-live` → versioned LIVE CORPUS → evidence_epoch.

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py live-status --observation-rdp <OBS_RDP> --cohort-id UTC-YYYYMMDD-YYYYMMDD
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py seal-live-cohort --observation-rdp <OBS_RDP> --cohort-id UTC-YYYYMMDD-YYYYMMDD --release-root <RELEASE>
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py verify-live --release-root <RELEASE>
```

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py import-live --release-root <RELEASE> --data-root <LOCAL_RDP>
```

Admission clock: `discovery_first_reliable_available_at` (7 UTC-day windows).
Live role: `EXPLORATORY_REUSE` with `confirmatory_reuse_forbidden=true`.
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
9. Daily owner pulse — product ready; install/enable timer only at final VPS deploy
10. Live cohort seal / sync / import into LIVE CORPUS (product ready; ops after collector commissioning)
11. **`NONEMPTY_RDP_OFFHOST_RESTORE_PROOF`** — after live observation_rdp is non-empty: prove Drive copy/readback + isolated restore with non-empty RDP inventory (pre-live empty-RDP proof is acceptable; do not claim live RDP restore is already proven)
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
/usr/bin/uv run --locked --managed-python python -B scripts/discovery_evidence_release.py live-status --observation-rdp local/factory_v1/observation_rdp --cohort-id <UTC-YYYYMMDD-YYYYMMDD>
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
| **1 — local** | `factory-remote-backup.timer` → `factory-remote-backup.service` → `factory_remote_doctor.py --backup` | `local/factory_v1_backup_sink/BACKUP_<sha256>.zip` | **No** — operational durability only |
| **2 — off-host** | `factory-remote-backup.service` **OnSuccess** → `factory-remote-backup-gdrive.service` → `factory_offhost_backup_copy.py` | `factory-gdrive:solana-alpha-lab/factory-backups/BACKUP_<sha256>.zip` | **No** — copy-only cold mirror |

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
| unproven after live data | `NONEMPTY_RDP_OFFHOST_RESTORE_PROOF` |

### Fresh-agent classification (machine JSON)

Read-only — **no Drive writes**, **no token/config body**:

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py --offhost-status
```

Use `agent_classification` booleans (exactly one primary off-host label applies):

| Label | When true |
|---|---|
| `LOCAL_BACKUP_OK` | `local_backup_state` == `OK` (newest local bundle age ≤ 24h) |
| `OFFHOST_BACKUP_OK` | `offhost.offhost_backup_state` == `CURRENT` (verified receipt age ≤ 2h) |
| `OFFHOST_BACKUP_STALE` | off-host state in `DEGRADED` (>2h), `HARD_ATTENTION` (>6h), `MISSING`, or `FAILED` |
| `OFFHOST_NOT_CONFIGURED` | `offhost.offhost_backup_state` == `UNCONFIGURED` (no enabled offhost config or rclone config not ready) |

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
| `CURRENT` | ≤ 2h | Off-host copy matches campaign RPO target |
| `DEGRADED` | > 2h and ≤ 6h | Visible degradation; local backup may still be OK |
| `HARD_ATTENTION` | > 6h | Telegram path may emit `DEGRADED_OFFHOST_BACKUP_STALE` via doctor |
| `FAILED` | last receipt terminal is failure | Typed copy/config conflict |
| `MISSING` | configured but no successful receipt | Never copy-assume from local health alone |

Receipt terminals (success): `COPIED_VERIFIED`, `ALREADY_PRESENT_VERIFIED`. Never contains OAuth tokens.

Last verified bundle fields in receipt / `--offhost-status`: `source_backup_filename`, `source_sha256`, `source_bytes`, `remote_logical_path`, `remote_bytes`, `verified_at`.

### Read-only metadata checks (never print config body)

```
sudo stat -c 'mode=%a owner=%U:%G size=%s' /etc/solana-alpha-lab/rclone.conf
```

```
sudo /usr/bin/rclone --config /etc/solana-alpha-lab/rclone.conf about factory-gdrive:
```

```
systemctl is-active factory-remote-backup.timer factory-remote-backup.service factory-remote-backup-gdrive.service
```

### Isolated restore (sanctioned; never into live stores)

After download to an **isolated temp path** outside `/opt/solana-alpha-lab/local/factory_v1`:

```
/usr/bin/uv run --locked --managed-python python -B -c "from pathlib import Path; from solana_alpha_lab.factory.remote_ops import restore_backup_isolated; print(restore_backup_isolated(bundle=Path('<ISOLATED>/BACKUP_<sha256>.zip'), dest_root=Path('<ISOLATED>/restore-staging')))"
```

Requirements: manifest integrity PASS, SQLite integrity PASS, restore markers respected, **no** replacement of live SQLite/RDP, deployed SHA unchanged.

Pre-live commissioning may prove restore with `rdp_inventory.count = 0`. **`NONEMPTY_RDP_OFFHOST_RESTORE_PROOF`** remains mandatory once live observation data exists — do not claim non-empty live RDP off-host restore is already proven.

### Manual stage-2 copy (commissioning / recovery only)

Owner-authorized; not routine automation:

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_offhost_backup_copy.py
```

Exit 0 → receipt updated. Local `--backup` remains separate and must succeed even if this fails.
