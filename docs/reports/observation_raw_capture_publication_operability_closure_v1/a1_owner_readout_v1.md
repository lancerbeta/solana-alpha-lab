# Owner readout — OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_CLOSURE_V1

## Outcome

ObservationSchedule publication-job tick hotspot is closed structurally, not as
a local performance tweak. Routine `tick_once` repair now reads only `open/`
jobs. Proven terminals become compact receipts in `completed/` (no
`observations` / `members`). Historical full JSON is moved byte-identical into
`legacy_full/` and is **not** deleted in this atom.

Repository terminal: `OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_SOFTWARE_PASS`.

Live deploy, migration APPLY, one manual tick, and three timer ticks remain a
**separate exact owner gate**:
`OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_LIVE_PASS`.

## What changed

- `observation_publication_jobs.py`: `open/` / `completed/` / `legacy_full/`
  journal; COMPLETE semantics; dry-run/apply migration; 7-day disk projection
- Publisher repair/has-open: glob only `open/`; MARKER crash window completes
  idempotently; exact `content_sha256` replay keeps dataset identity on D+1
- Compact receipts are recovery metadata. Forge/history stay on immutable
  RDP/Parquet/manifests
- Collector operational packet: job counts/bytes, RDP bytes excluding the
  journal, declared schedule raw/day budget, conservative `projected_7d_disk_used_*`
- CLI: `scripts/observation_publication_jobs.py status | dry-run | apply`
  (`apply` requires `--i-understand-apply` and a non-ACTIVE/DRAINING collector)
- Operator live-smoke commands: `docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md`

## Falsifier (this atom)

Deterministic vertical tests: hundreds of completed receipts plus a huge
sentinel are not opened by routine repair; one genuine open job crash-repairs;
terminal jobs compact; D+1 replay keeps identity; Forge rebuild matches after
the job payload is gone; migration dry-run/apply is idempotent; `legacy_full`
bytes are preserved; APPLY refuses a live collector.

## Non-claims

- No VPS deploy / live APPLY / live tick in this atom
- No `legacy_full` deletion
- No Jupiter redesign, HTTP timeout work, retry/fallback, STARTED cleanup,
  backfill, or new campaign
- No byte-identical HTTP archive
- No alpha / NetReturn / canonical DONE

## After merge (separate owner gate)

1. Exact-SHA deploy while collector is `PAUSED_OPERATOR`
2. Journal `dry-run` then `apply` (`classified_ambiguous=0`)
3. One manual tick under ~90s cutoff, then three timer ticks
4. Leave ACTIVE only after live PASS
5. Next atom: `NONEMPTY_RDP_OFFHOST_INCREMENTAL_RESTORE_PROOF`
6. Only after that proof reclaim/compact `legacy_full`
