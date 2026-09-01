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
6. Live campaign authority (exact ObservationSchedule phrase)
7. Live commissioning (timer enabled, ticks with authority)
8. Daily owner pulse — **next named consumer, not this atom**
9. Live cohort seal / sync / import into LIVE CORPUS (product ready; ops after collector commissioning)
10. Forge

## DAILY_COLLECTOR_OWNER_PULSE (named future consumer)

Do **not** implement here unless already supported by existing health/Telegram
with config only. Desired future daily (non-spam) summary:

- collector state
- candidates / sampled / X-eligible 24h
- 4h/24h closure
- discovery coverage class / gaps
- provider 401/403/429/5xx/timeout
- oldest due / backlog
- backup age / domain
- disk
- current cohort / release state

Immediate incident alerts remain separate from this daily pulse.
