# Owner readout — OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_CLOSURE_V1

## Outcome

ObservationSchedule publication-job tick hotspot is closed structurally, not as
a local performance tweak. Routine `tick_once` repair now reads only `open/`
jobs. Proven terminals become compact receipts in `completed/` (no
`observations` / `members`). Historical full JSON is moved byte-identical into
`legacy_full/` and is **not** deleted in this atom.

Repository terminal: `OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_SOFTWARE_PASS`.

Predecessor merge: PR #259 / `891191881c7a4255d9fc4b1e13b0340f2f9e23c4`. This
PATCH does **not** treat that merge as live APPLY/tick proof.

Live deploy, migration APPLY, one manual tick, and three timer ticks remain a
**separate exact owner gate**:
`OBSERVATION_RAW_CAPTURE_PUBLICATION_OPERABILITY_LIVE_PASS`.

## PATCH after post-merge review

- APPLY plan peak payload memory is `O(max_job_bytes)`, not
  `O(total unmigrated payload bytes)`. Plan items keep source paths, size,
  streaming sha256, classification, and compact receipts. They do not retain
  raw bodies, observations, or members.
- Duplicate `content_sha256` with identical bytes/identity is coalesced;
  differing sources claiming the same identity fail before mutation
  (`CONTENT_IDENTITY_COLLISION`).
- APPLY revalidates each source size/hash before mutating that file
  (`SOURCE_CHANGED_AFTER_PLAN`). Destination equality is streaming-hash, not a
  second in-memory copy.
- PR #259 preflight-before-mutation and 7d UNKNOWN fail-closed remain.
- Hot path remains `O(open jobs)`. Forge/RDP history is unchanged.

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
  (`apply` requires `--i-understand-apply`; refuses ACTIVE/DRAINING; missing
  ops store is `COLLECTOR_STORE_MISSING`; `classified_ambiguous>0` fail-closes)
- Operator live-smoke commands: `docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md`

## Falsifier (this atom)

Deterministic vertical tests: hundreds of completed receipts plus a huge
sentinel are not opened by routine repair; one genuine open job crash-repairs;
terminal jobs compact; D+1 replay keeps identity; Forge rebuild matches after
the job payload is gone; migration dry-run/apply is idempotent; `legacy_full`
bytes are preserved; APPLY refuses a live collector and a missing store.
Preflight: later unconstructable PROVEN_COMPLETED, incompatible completed
receipt, and incompatible `legacy_full` fail with zero source moves; identical
destinations stay idempotent; prefix-applied state converges on rerun.
Plan items contain no raw/full payload; `Path.read_bytes` on unmigrated jobs
is forbidden during plan; duplicate content identity with different bytes
fails before mutation; a source changed after preflight fails closed. 7d:
declared budget can PASS or FAIL ≥70%; missing filesystem or missing
history+declared cannot PASS.

## Isolated review

ARCHITECTURE_CRITIC, CODE_REVIEWER, and GOAL_DOD_CRITIC re-review this PATCH
on the new HEAD after evidence bind. Not canonical DONE. Not live PASS.

Non-blocking residuals (not this write set):
- `observation_schedule.py doctor` while paused still emits `next_action=RESUME`;
  the live playbook says do not resume/tick until APPLY. Follow the playbook.
- Daily pulse text still reports total RDP including the journal; science-only
  bytes live on the operational packet, not Telegram copy.
- `pass_70=false` for UNAVAILABLE is fail-closed, not a measured ≥70% disk fail;
  read `projection_basis`.
- Live APPLY remains a separate owner gate. APPLY still `json.load`s one
  source at a time during inspect; it does not retain historical bodies across
  plan items.

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

Do not tick a new SHA until APPLY. Unmigrated flat jobs are invisible to routine
repair until APPLY; that is the hotspot fix, not a live PASS.
