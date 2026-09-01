# COLLECTOR_OPERABILITY_RETENTION_AND_OWNER_PULSE_V1 — owner readout

## Verdict

Software baseline for unattended multi-week Factory lifecycle collection is ready
for merge. No VPS deploy/enable in this atom.

## Final daily pulse example (dry-run shape)

```
FACTORY / DAILY

Collector: ACTION_REQUIRED
Cohort: UNKNOWN/UNKNOWN

Candidates 24h: 0
Sampled: 0
X eligible: UNKNOWN

4h/24h closure: observations=0 typed_missing=0 censored_late=0
Coverage: <coverage class>
Gap incidents: 0

Provider:
401 0 / 403 0 / 429 0 / 5xx 0 / timeout 0

Backlog: pending=0 in_flight=0 budget_blocked=0
Oldest due: 0s

Storage:
Disk: <measured %>%
Growth 24h: disk_pp=UNKNOWN data_bytes=UNKNOWN
SQLite: <bytes or UNKNOWN>
Observation RDP: <bytes or UNKNOWN>
Projected 80% disk: UNKNOWN

Backup:
age UNKNOWN
domain <domain or UNKNOWN>

Release:
state=UNKNOWN sealed=UNKNOWN corpus_v=UNKNOWN

Owner action:
Run independent backup (`factory_remote_doctor.py --backup`) and verify FACTORY_BACKUP_SINK domain.
```

(Empty store without backup → `BACKUP_DEGRADED` / `ACTION_REQUIRED`. Live host with
healthy backup and ACTIVE schedule renders OK/DEGRADED accordingly.)

## Exact storage metrics available

- `filesystem_disk_used_pct`, `filesystem_disk_free_bytes`
- `observation_sqlite_bytes` (+ WAL when present)
- `observation_rdp_bytes`, `backup_sink_bytes`
- `disk_growth_24h_pct_points`, `data_growth_24h_bytes` when history exists; else UNKNOWN
- `projected_disk_80pct` only with enough measured history; else UNKNOWN
- Policy: <70 NORMAL, ≥70 pulse EARLY_WARNING text, ≥80 DISK_WARNING, ≥85 DISK_CRITICAL
  (remote-ops hard max 85% unchanged)

## Actual raw-retention substrate

Decoded/canonical provider JSON inside ObservationSchedule `call_ledger.payload_json`
(+ `poll_slots` cache). **Not** byte-identical original HTTP response bytes.

## Retention enforcement model

After `raw_retention_days` (campaign default 31), under exclusive scheduler lease:
compact aged COMPLETED bodies to provenance metadata (`response_sha256`, HTTP class,
timing fields, identity). Poll-slot bodies may clear under the same gate.
Dry-run default; apply requires `--i-understand-apply`. Does not bump `updated_at`.

## Forever immutable (never auto-deleted by this path)

- Observation RDP / Parquet (`canonical_panel_retention=IMMUTABLE`)
- Sealed live releases / LIVE CORPUS
- Candidate/member denominator scientific rows
- Authority receipts / activation / accounting identity
- Call occurrence identity + required provenance hashes/classes
- STARTED / IN_FLIGHT / unresolved dues / younger than retention window

## Future SQLite growth

Bounded/reusable: completed provider bodies become compactable after the window;
SQLite freelist reuse without VACUUM (`SQLITE_FREELIST_REUSE_WITHOUT_VACUUM`).
File size may not shrink on disk until OS reclaim — growth is no longer forced by
retained bodies forever.

## False roadmap assumptions closed

- Daily pulse was “future-only” — now implemented (timer templates not installed).
- `raw_retention_days=31` was declarative-only — now enforceable via compaction.
- Silent zero for missing backup/disk growth — replaced with UNKNOWN + BACKUP_DEGRADED.

## Final VPS deploy

Can proceed with **no further product code** for this operability surface: deploy
repaired main, enable observation timer, optionally install daily pulse timer,
optionally schedule retention dry-run/apply. Separate ops atom; not this PR.
