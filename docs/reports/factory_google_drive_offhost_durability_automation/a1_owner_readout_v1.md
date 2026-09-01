# Owner readout — FACTORY_GOOGLE_DRIVE_OFFHOST_DURABILITY_AUTOMATION_V1

## What landed

Stage-2 Google Drive **copy-only** durability after unchanged local hourly backup:

- `factory-remote-backup.timer` → local `BACKUP_<sha256>.zip`
- `OnSuccess` → `factory-remote-backup-gdrive.service` → `factory_offhost_backup_copy.py`
- Receipt: `local/factory_v1/offhost_backup_receipt.json`
- Doctor: `--offhost-status` fresh-agent recovery
- Pulse: `local … / offhost … / GOOGLE_DRIVE / …`
- Semantics: `PROVEN_OFFHOST_DURABILITY` (prior `OPTIONAL_COLD_COPY_NOT_DOD` preserved)

## Not in this atom

- VPS deploy / enable of gdrive oneshot
- Jupiter credential
- Campaign activate
- `NONEMPTY_RDP_OFFHOST_RESTORE_PROOF`

## Fresh-agent status

```
sudo /usr/bin/uv run --locked --managed-python python -B scripts/factory_remote_doctor.py --offhost-status
```
