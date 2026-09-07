# System Operability Surface V2

Owner-facing `/system` composition over existing Factory machine sources.
Does not own collector truth, backup/durability, incidents, deploy, or Visual OS.

Catalog document: `DOC-SYSTEM-OPERABILITY-SURFACE-001`
Semantic route: `SEM-REMOTE-OPS-RECOVERY` (reused; no `SEM-SYSTEM`)
Canonical binding remains `ACTIVE-FACTORY-REMOTE-OPERATIONS`
(13 live bindings; a 14th `ACTIVE-SYSTEM-OPERABILITY-SURFACE` is
`NO_CHANGE_REQUIRED`).

```text
collector packet + ObservationSchedule (readonly)
+ systemd readback + deploy marker + incident JSON + env class
        → SYSTEM_OPERABILITY_SURFACE_V2
        → /system + scripts/show_system_operability.py
        → System-local attention → OWNER_ATTENTION_AND_CHANGE_FEED_V1
```

```text
authority_granted = false
OWNER_FACING_LANGUAGE = RU
CANONICAL_MACHINE_LANGUAGE = EN
GET /system = non-mutating
HEALTHY is forbidden
process_alive=True is never inferred from Git config + OperationalStore
REVIEWED != RESOLVED
current health is never Git truth
```

## 1. Owner questions

```text
Можно ли сейчас оставить Factory технически работать без меня?
Если нет — что сломано / DEGRADED / UNKNOWN, почему это важно,
и по какому recovery path это проверять?
```

Normal success: `OK_OBSERVED` with explicit coverage, or an honest
`UNKNOWN`/`DEGRADED`/`ACTION_REQUIRED` plus one next safe recovery route.

## 2. Owner vocabulary

```text
ACTION_REQUIRED | DEGRADED | OK_OBSERVED | UNKNOWN
```

Coverage is separate from state. Alive HTTP + stale data ≠ `OK_OBSERVED`.
Unavailable evidence ≠ zero/clean.

## 3. Truth planes

```text
WORKBENCH_HTTP_SELF     this GET proves SERVING_NOW only
MANAGED_WORKBENCH_UNIT  systemd factory-v1-workbench.service
REQUIRED_TIMERS         existing watch timer set
COLLECTOR               ObservationSchedule + collector packet
DATA_FRESHNESS          packet health classes
STORAGE / RUNWAY        packet DISK_RUNWAY_*
MUTABLE_BACKUP          packet BACKUP_*
OFFHOST_BACKUP          packet OFFHOST_*
IMMUTABLE_ARCHIVE       packet IMMUTABLE_ARCHIVE_*
DEPLOY_IDENTITY         .factory_deploy_sha vs local Git HEAD
ALERTING                FACTORY_TELEGRAM_* present (CONFIGURED ≠ DELIVERY_PROVED)
OUT_OF_BAND_HOST_REACHABILITY  FACTORY_EXTERNAL_HEARTBEAT_URL (NOT_CONFIGURED ≠ P1)
CHANGE_HISTORY          STATE_ONLY (no system_events.sqlite)
```

Git config `deploy_version` is capability inventory, not current deployed proof.

## 4. GET purity

`/`, `/system`, `/research`, `/operations`, `/economics` gain no new mutations.
`/system` performs zero SQLite create/migrate/WAL, zero incident write,
zero Telegram/Drive/provider/Git mutation, and never prints secret values.

Allowed: filesystem stat, readonly SQLite, readonly JSON/YAML,
`systemctl is-active` without sudo, local Git HEAD, deploy marker file.

Absent ObservationSchedule → `SOURCE_NOT_PRESENT` without mkdir.

## 5. Non-claims

```text
NO ALPHA
NO LIVE
NO REAL MONEY
NO OWNER FCF
NO DEPLOY
NO PROVIDER CALL
NO DRIVE WRITE
NO TELEGRAM SEND
NO WALLET
NO SYSTEM HEALTH FROM GIT
NO MONITORING PLATFORM
NO CANONICAL DONE
```
