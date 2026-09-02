# FACTORY_OFFHOST_TRAFFIC_BOUNDED_BACKUP_V1 — owner readout

Git topology for Factory durability, not alpha and not Cherry billing.

## What changed

Hourly full zip to Google Drive is replaced by:

- local full every **12h UTC**, retain **one** verified `BACKUP_<sha256>.zip`;
- daily incremental Drive checkpoint (`DELTA_*` when bytes changed);
- weekly standalone full (Sunday UTC), or `FULL_COVERAGE_RECONFIRMED_NO_CHANGE` if inventory is unchanged;
- immutable remote `RECOVERY_CHECKPOINT_<UTC>_<sha256>.json` after payloads are verified.

No-change days still upload the tiny checkpoint. Application payload counters are **not** Cherry billed egress.

## How a fresh agent recovers (no chat)

1. Git + rclone config.
2. Newest valid `RECOVERY_CHECKPOINT_*` by **filename timestamp**, then content hash.
3. Download the referenced `BACKUP_*` and ordered `DELTA_*`.
4. Isolated restore only — never into live `local/factory_v1`.

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py --offhost-status
```

Required Git terminal name:

```
FACTORY_DAILY_DELTA_WEEKLY_FULL_OFFHOST_BACKUP_PASS
```

## Traffic posture

- Owner target: 300 GB / 30d (portal remains billing truth).
- Internal planning budget: 240 GB application payload.
- Planning fixture (2 GB start, +2 GB/day): about **202 GB < 240 GB**.
- Missing/corrupt local ledger → `UNKNOWN`, not a fake 0.

## Limits

- Git-side isolated nonempty RDP restore is proven. Live Factory commissioning of the new timers is the next host step (`LIVE_FACTORY_INCREMENTAL_RESTORE_COMMISSIONING`).
- No rclone sync/delete. No restore over live stores. No secrets in Git or receipts.
- `CAPABILITY_RADAR_NOW=NONE`.
