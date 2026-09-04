# FACTORY_97D_STORAGE_ARCHITECTURE_PRD_SSD_V1

Status: `DESIGN_FROZEN_CAPACITY_PROVED`
Contract: `FACTORY_97D_STORAGE_ARCHITECTURE_PROOF_V1`
Base: `52be82091af859171de2c062b1a08e05f5eb325e`
Terminal of this atom: `STORAGE_97D_ARCHITECTURE_READY`
As of: `2026-09-04`

This document is the PRD+SSD for a **later** implementation atom. It does **not**
implement the architecture. It does **not** authorize retention APPLY, Drive
write, local Factory-data delete, deploy, or capture change. Implementation is
not started from this PR; merge of this research/design is the handoff.

Predecessor `FACTORY_STORAGE_DATA_ECONOMY_AND_CONTEXT_CLOSURE_V1` terminal
`NO_STORAGE_ARCHITECTURE_CHANGE_REQUIRED` remains historically true under the
then-current 31d operational raw + immutable-forever local RDP contracts. This
atom is a **new owner product requirement** (90d local residency of all material
RAW + science, 40/50 GiB inclusive data budget). It does not rewrite that
predecessor terminal.

## 0. Entry / outcome

- `DECISION_DELTA`: which standard ADOPT/WRAP architecture keeps 90d of RAW +
  scientific evidence on the current ~100 GiB VPS without periodic disk upgrades.
- `UNCERTAINTY_REMOVED`: live byte attribution after post-reboot coherence;
  same-`st_dev` backup sink; ~2.96 d publication span; SNAPPY live footers;
  ZSTD3 live ratios; 97d typical 21.47 GiB / conservative stress 42.84 GiB.
  rclone/Drive SHA256 and isolated hydration remain **design-selected
  contracts** (this atom made 0 Drive hash calls).
- `CAPABILITY_OR_EVIDENCE`: this PRD+SSD plus filled §4 tables. Historical
  `HOST_UNREACHABLE` after a `/opt` walk is recorded; it does not remain the
  capacity terminal.
- `STOP`: no architecture implementation, deploy, retention APPLY, Drive write,
  local delete, capture change, or merge from this handoff.
- `NEXT`: merge gate of this research PR, then
  `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1`. Destructive eviction stays a
  later gate. `STORAGE_97D_ARCHITECTURE_READY_WITH_TARGET_MARGIN` is **not**
  the terminal (conservative stress exceeds 40 GiB).

`SPEC_ROUTE`: `BOTH`
`MODEL_EFFORT_RECOMMENDATION`: `SOL_XHIGH`
`NEXT_MODEL_EFFORT`: `LUNA_MAX` for bounded implementation after merge;
`SOL_XHIGH` if IMPL changes schema, availability clocks, or PIT.

## 1. Product requirement (frozen)

Local residency: latest 90 days of all material RAW + transformed/scientific
Factory data. Weekly age-based eviction is acceptable.
`capacity_horizon_days = 97` (`hot_window_days=90` + `archive_cadence_days=7`).

VPS data budget, inclusive of everything on the **same filesystem** that is
Factory data (HOT raw, HOT science, SQLite/WAL, journals, same-volume backup,
archive/compaction staging peak, indexes/manifests):

- TARGET: `TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D <= 40 GiB`
- HARD: `TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D <= 50 GiB`

OS, application code, services and ordinary logs are outside 40/50. Whole-host
projection must still preserve headroom vs existing 70/80/85 disk policy
(`DISK_WARNING_EARLY_PCT=70`, `DISK_WARNING_PCT=80`, `DISK_CRITICAL_PCT=85`).

Cold history older than 90d remains losslessly available on the existing Google
Drive route. 90d is a **residency** policy, not a scientific research-window
policy.

Semantic transition (do not silently reinterpret `canonical_panel_retention=IMMUTABLE`):

- `CONTENT_IMMUTABILITY` = canonical bytes never mutate; identity is content hash.
  The existing schema const `canonical_panel_retention: IMMUTABLE` **keeps this
  meaning**. It does **not** become “delete after 90d”.
- `LOCAL_RESIDENCY` requires a **new** versioned field, proposed name
  `hot_local_residency_days` (value `90`). Add it in
  `catalog/schemas/observation_schedule_v1.schema.json` (and the duplicate
  `experiment_spec_v1_2` panel block if still required) **before** any HOT
  scientific eviction. Companion operator sentence in
  `docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md` must change from “never
  auto-deleted by retention” to “content immutable; HOT local copy 90d after
  COLD SHA256 verify”.
- `COLD_DURABILITY` = indefinite on Drive after exact SHA256 verify.

Until that schema + operator + domain-policy write exists:

`SCIENTIFIC_RDP_LOCAL_EVICTION_FORBIDDEN_UNDER_CURRENT_IMMUTABLE_CONST`

A successor must not evict Observation RDP while YAML/schema still only say
`IMMUTABLE` and the collector runbook still says never auto-deleted.

Versioned names:

- `canonical content = immutable forever`
- `hot local residency = 90d`
- `cold durability = indefinite`

## 2. Current contracts reconciled

1. Live Observation Plane on VPS is moving collector truth
   (`local/factory_v1/observation_schedule_state.sqlite`,
   `local/factory_v1/observation_rdp`).
2. Forge consumes sealed Research Evidence Plane
   (`local/factory_v1/data_plane`) via Discovery Evidence Release
   seal → verify → import. Moving VPS bytes do not change Forge
   `evidence_epoch`.
3. LIVE cohort sealing reads Observation RDP. A 90d residency does not break
   current campaign seal/release if the cohort window (`COHORT_WINDOW_DAYS=7`)
   and any in-flight publication remain HOT. Historical >90d replay hydrates
   into an isolated temp `data_root`.
4. Raw substrate is decoded/canonical provider JSON in SQLite payload bodies,
   hashed by `canonical_sha256(body)` — **not** byte-identical wire HTTP.
5. Operational raw retention default `raw_retention_days=31`.
6. Scientific RDP `canonical_panel_retention=IMMUTABLE` currently means never
   auto-deleted (`catalog/schemas/observation_schedule_v1.schema.json` const +
   collector runbook). The new design does **not** reuse that const for 90d
   residency. Residency is a new field `hot_local_residency_days`. Eviction
   under the current const is forbidden.
7. Local backup includes `observation_rdp` recursively in a 12h ZIP_STORED full,
   retain 1.
8. Off-host: daily delta + weekly standalone full. Copy verification is
   **size-only** (`_remote_size` vs local bytes) in
   `src/solana_alpha_lab/factory/offhost_backup.py`. Size equality is not
   sufficient for destructive eviction.

## 3. Phase A — live byte forensics

### 3.1 Last successful machine readback (not this atom's second probe)

`docs/evidence/factory_storage_data_economy_and_context_closure_v1/a1_storage_baseline_v1.json`
`observed_at=2026-09-04T14:17:55Z` on `factory-remote-ops`, deploy
`af1ad23ac4a97d4f63108abd8446ad3dc6b1960c`.

| Substrate | Bytes | Notes |
|---|---:|---|
| Filesystem size | 103 079 215 104 | ~96 GiB visible; SKU ~100 GiB-class |
| Used / free | 16 192 004 096 / 86 679 314 432 | ~16% used |
| ObservationSchedule SQLite | 167 993 344 | WAL 0 |
| operational_state.sqlite | 4 096 | |
| paper_plane_state.sqlite | 53 248 | |
| Scientific RDP excl. publication_jobs | 612 857 483 | |
| publication_jobs completed | 479 870 | 456 files; open 0; `legacy_full` 0 |
| Local backup sink | 11 114 155 120 | pre-reclaim leftover; not steady-state |
| Off-host 30d payload | 22 139 072 972 | class `NORMAL`; separate from VPS disk if remote |
| collector_storage_history | absent | empirical 24h/30d/90d UNKNOWN |
| Protected SQLite payload | 59 198 098 | 2353 calls; eligible compaction 0 |

Disk policy at observation: well below 70/80/85.

`FACTORY_BACKUP_SINK` other-volume identity was **not** machine-proven in that
baseline (git-side `local/factory_v1_backup_sink` on the same disk class). Until
a device-id readback proves otherwise, same-volume backup bytes stay inside the
40/50 GiB budget.

### 3.2 Historical HOST_UNREACHABLE (not the capacity terminal)

At ~2026-09-04T16:48:51Z a read-only forensics script walked `/opt` looking for
`BACKUP_*.zip`. The VPS then became unreachable: SSH banner timeout and ICMP
100% loss from the operator host. This process issued no Drive write and
printed no secrets to Git/chat (`credential_values_read: false`). Post-hang
VPS mutation and whether secrets were read on the host are
`NOT_OBSERVED_AFTER_HOST_UNREACHABLE` — not proven negatives. Root cause is
`NOT_PROVEN_WITHOUT_SPECULATIVE_REPAIR`.

### 3.3 Post-reboot bounded forensics (2026-09-04T19:23:34Z)

SSH recovered after Cherry power cycle of instance `973818`. New boot proven
(`boot_id=e3645da3-2e1b-4d22-bcaf-20b9648f22d4`, `uptime -s` 2026-09-04 22:12:07
EEST). Deploy SHA unchanged `af1ad23ac4a97d4f63108abd8446ad3dc6b1960c`.
Walked only `local/factory_v1` and the git-side backup sink. Telegram not
invoked. Drive writes 0.

| Substrate | Bytes | Notes |
|---|---:|---|
| Filesystem size / used / avail | 102 888 095 744 / 16 461 918 208 / 86 409 400 320 | ~17% used |
| ObservationSchedule SQLite | 192 040 960 | WAL 0; `integrity_check=ok` |
| Scientific RDP excl. publication_jobs | 842 194 811 | grew from 612 857 483 at 14:17Z; no rollback |
| publication_jobs completed | 557 794 | 530 files; open 0; `legacy_full` 0; unmigrated 0 |
| members.parquet | 824 754 961 | 530 files; SNAPPY; exact SHA dups 0 |
| observations.parquet | 6 121 537 | 530 files; 1856 rows |
| call_ledger COMPLETED payload_json | 67 669 069 | 2106 rows; `$.rows` 60 899 842; `$.body` 0 |
| poll_slots payload_json | 65 735 633 | same JSON shape as call_ledger; do not add as extra raw |
| Local backup sink | 11 114 155 120 | same `st_dev=64769` as factory_v1; leftover ZIP |
| Research DuckDB | 0 | ABSENT |
| publication span | 2.9636 days | `first_reliable_available_at` min/max |

`collector_storage_history.jsonl` remains `HISTORY_ABSENT`. Do not wait 90 days;
do not invent a run-rate from the 1 GiB/day contractual cap. Do not use the
~5.1h post-outage RDP catch-up as typical.

## 4. Phase B — structural 97d model (live numbers)

Let:

- `S_day` = measured scientific HOT bytes/day (closed publications, current layout)
- `R_day` = measured canonical raw body bytes/day (unique `response_sha256`)
- `M_day` = operational metadata/SQLite/journals growth/day after split
- `A_layout` = lossless layout factor (ZSTD + batching + member/raw dedup), measured
- `B_same_vol` = same-volume recovery artifact factor (1.0 if mutable-only snapshot;
  ~2.0 if current full RDP ZIP_STORED copy)
- `P_stage` = archive/compaction staging peak (closed daily unit + zip)

```
PRIMARY_HOT_97D = 97 * (S_day + R_day + M_day) * A_layout
SAME_VOLUME_BACKUP_97D = PRIMARY_HOT_97D * (B_same_vol - 1)   # extra copy
STAGING_PEAK = P_stage
TOTAL_97D = PRIMARY_HOT_97D + SAME_VOLUME_BACKUP_97D + STAGING_PEAK
```

Report separately, never as measured run-rate:

- contractual `raw_bytes_per_utc_day_max = 1 GiB` → 97 GiB raw-only theoretical
  bound. This already exceeds HARD 50 GiB. It is an admission cap, not empirical
  growth.

From live forensics (19:23Z), selected architecture `B_same_vol=1.0`,
`A_layout=0.725` (members SNAPPY→ZSTD3 + HOT raw JSON→ZSTD3 parquet):

| Term | Bytes | GiB |
|---|---:|---:|
| `S_day` (live SNAPPY science) | 284 178 196 | 0.265 |
| `R_day` (unique `$.rows` JSON) | 20 503 703 | 0.019 |
| `M_day` (sqlite overhead) | 19 717 661 | 0.018 |
| typical `PRIMARY_HOT_97D` | 22 813 412 187 | 21.25 |
| typical `STAGING_PEAK` | 235 189 816 | 0.22 |
| typical `TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D` | 23 048 602 003 | 21.47 |
| conservative stress (members p95/mean) | 46 000 455 406 | 42.84 |
| contractual 1 GiB/day × 97 (not measured) | 104 152 956 928 | 97 |

Typical passes TARGET 40 and HARD 50. Conservative stress misses TARGET and
passes HARD. Current topology with `B_same_vol=2.0` is still REJECT: it would
put 97d over HARD.

A design does **not** PASS if HOT is 40 GiB and a same-volume full backup makes
80 GiB. Current topology (`recursive observation_rdp` in 12h ZIP_STORED retain-1
**and** weekly off-host full of the same immutable bytes) is the amplification
to remove. Same-volume identity is now machine-proven (`st_dev=64769`).

## 5. Phase C — format benchmark (CI corpus + live tmp rewrite)

Live corpus rewrite used `/tmp` only; no live Factory bytes committed.
Footer on live observations/members: **SNAPPY**, `parquet-cpp-arrow version 25.0.0`.
Median members file: SNAPPY 2 167 088 → ZSTD3 1 607 686 (0.74×). p95-ish members:
SNAPPY 3 126 661 → ZSTD3 2 275 791 (0.73×). 80 COMPLETED raw JSON rows
(3 909 820 B) → ZSTD3 parquet 597 114 B (0.15×). Exact member file-SHA
duplicates = 0; WRAP content-addressed members remains optional, not required
to meet HARD. Overlapping 7d member snapshots are already inside `S_day`.

Proven on nested observation rows with `event_time`,
`first_reliable_available_at`, typed values, missingness, `request_sha256`,
`call_occurrence_id`:

- `pq.write_table` with unspecified compression, `none`, `zstd` 1/3/7, `snappy`
  all round-trip with exact semantic fingerprint.
- ZSTD 3 and 7 are strictly smaller than uncompressed on this corpus.
- Concatenating batches does not rewrite historical
  `first_reliable_available_at`.
- Canonical raw JSON bytes stored as Parquet binary, including
  `response_sha256` dedup across call occurrences, extract to the exact
  `canonical_json_bytes(body)` Factory already defines.

Note: `observation_panel_publisher._write_parquet` calls `pq.write_table(table, tmp)`
with **no** explicit codec. PyArrow 25 default compression is **snappy**, not
uncompressed. `research_store` explicitly writes `compression="NONE"`. Do not
call current observation files "uncompressed" without reading footer metadata
on the live corpus.

Member/denominator: live exact file-SHA duplicates = 0. The publisher still
writes a new `members.parquet` per `dataset_manifest_id`; overlapping cohort
windows inflate `S_day` without identical files. Content-addressed member
objects remain optional WRAP, not required for HARD 50.

## 6. Phase D — split retention

Do **not** solve 90d RAW by `raw_retention_days` 31→90 in SQLite unless live
measurement shows that is best. Current evidence says SQLite bodies are tens of
MiB; scientific RDP is hundreds of MiB and growing. Bloating the operational DB
is the wrong lever.

Split:

| Class | What | Local residency | Compact/evict |
|---|---|---|---|
| A. Operational inline raw | unresolved STARTED/IN_FLIGHT; crash recovery; near-term repair | until scientifically closed + HOT raw materialized | never compact STARTED/unresolved by age |
| B. Canonical HOT raw | lossless `canonical_json_bytes(body)` + occurrence metadata | 90d | after COLD verify |
| C. Scientific RDP HOT | immutable parquet + manifests for closed units | 90d | after COLD verify |
| D. COLD raw/science | Drive archive units | indefinite | no query-in-place |

A COMPLETED SQLite body may leave SQLite only after:

1. canonical raw evidence durably materialized;
2. `response_sha256` matches extracted canonical bytes;
3. no unresolved due/call recovery dependency;
4. scientific publication dependency closed where applicable.

## 7. Phase E — backup vs immutable archive

Selected: separate **mutable-state durability** from **immutable-data durability**.

Immutable scientific/raw closed partitions:

- upload-once soon after terminal/closed;
- content-addressed remote identity;
- exact remote SHA256 == local SHA256;
- no weekly full retransmission of the same bytes.

Mutable SQLite/state:

- keep bounded consistent snapshots (`SQLITE_BACKUP_API`) on 12h local retain-1;
- off-host daily delta of **changed mutable files only**;
- weekly operation = coverage/inventory checkpoint + cold durability audit +
  age-based local eviction, not re-upload of HOT.

Disaster RPO ~24h remains: the unclosed/unarchived tail is in the mutable
snapshot plus the newest open partition. Isolated restore stays
"restore into isolated dest, never into live `factory_v1` stores".

Do not weaken durability to save disk. Local eviction is forbidden until exact
cold SHA256 verify.

## 8. Phase F — cold archive unit

Google Drive is existing COLD storage. Do not add GCS/S3. Do not query-in-place
against Drive.

Prefer a small number of immutable time units: **closed UTC-day bundles** if live
file counts support it (current publisher already keys `utc-day-YYYY-MM-DD`).

Use existing ZIP_STORED + manifest machinery (`BACKUP_MANIFEST.json` /
logical inventory SHA256). Do not invent a custom binary archive format.

Each unit:

- preserves exact source bytes (ZIP_STORED);
- manifest: per-source path, size, SHA256;
- bundle filename `ARCHIVE_<sha256>.zip` content-addressed;
- never overwrite.

## 9. Phase G — remote verification

Current off-host copy checks **size only**. That is insufficient for eviction.

Selected smallest standard mechanism:

1. `rclone hashsum sha256 remote:path` — Google Drive API exposes
   `sha256Checksum` (rclone drive backend `partialFields` includes it).
2. If native SHA256 is missing for an object, `rclone hashsum sha256 --download`
   (download-and-hash fallback).
3. Compare to local file SHA256. Equal → `REMOTE_CONTENT_SHA256_VERIFIED`.

No local eviction from: filename, listing presence, mtime, size-only, or upload
return code.

This atom performed **zero** Drive hash calls. Tests may mock the contract.

## 10. Phase H — eviction age

Never use filesystem mtime as scientific retention truth.

For a closed unit, eligibility clock is the **maximum** of the unit's
availability/closure clocks. Required members:

- `first_reliable_available_at`
- `max_available_to_strategy_at` — required; if missing on a closed unit, the
  unit is **ineligible** for eviction (fail-closed), not skipped
- partition/archive closure time

Never use the **minimum** of those clocks. Never use filesystem mtime.
Using only `first_reliable_available_at` when a later
`max_available_to_strategy_at` exists can evict rows still inside the
availability window.

Eligibility:

```
age > 90d
AND terminal/closed
AND no unresolved due/call
AND no open publication dependency
AND exact cold coverage verified (local SHA256 == remote content SHA256)
AND source path/hash unchanged since archive plan
```

Weekly eviction ⇒ plan capacity at 97d.

Concurrency:

1. lock → plan exact immutable set;
2. unlock → package/upload/verify;
3. lock → TOCTOU revalidate;
4. exact-file eviction (no wildcard / parent recursive delete);
5. post-readback.

Do not hold a global lock during a long Drive upload.

## 11. Phase I — consumers and hydration

| Consumer | Reads | HOT/COLD awareness |
|---|---|---|
| Collector / ObservationSchedule | SQLite operational + open jobs | no; keep unresolved locally |
| Observation RDP enumeration / panel rebuild | VPS `observation_rdp` manifests | no; only HOT tree present |
| LIVE cohort seal/release | moving Observation RDP, 7d window | no if window ⊂ HOT |
| Discovery Evidence Release import | sealed release → `data_plane` | Forge never reads moving VPS |
| Forge/HFIC `evidence_epoch` | imported ResearchStore + catalog hashes | unchanged |
| Historical >90d experiment | hydrated isolated `data_root` | operator path only |
| PathRisk/live | current schedule/RDP | no |
| Backup/restore | mutable snapshot + archive units | restore isolated |

Preferred compatibility boundary:

`cold archive → hydrate exact original subtree into isolated temporary data_root → existing readers unchanged`.

Prove on implementation: dataset identity, manifest/path relationships, exact
raw bytes, historical release/experiment reproduce, hydration never writes live
Factory state.

`projections/research_memory.duckdb` is a **derived** global index. Do not
partially evict parquet that the projection still names. After HOT eviction,
rebuild the projection from remaining HOT events, or keep a bounded metadata
segment locally. Canonical truth is event parquet + manifests, not DuckDB.

## 12. Phase J — future month / storage admission

Extend `DATA_RESOLUTION_ECONOMY` (domain policy, implementation atom) with
storage planning evidence for any new material capture:

```
incremental compressed bytes/day
→ incremental 97d resident bytes
→ total projected data footprint
→ retention class
```

- projected total > TARGET 40 GiB → `DEGRADED` / optimization required
- projected total > HARD 50 GiB → `ACTION_REQUIRED` before enabling additional
  broad capture

Do not silently downsample an admitted experiment to protect disk.
Already-admitted scientific due observations must not disappear due to a
storage budget event.

If lossless layout cannot meet HARD 50 GiB and sampling / candidate-capacity /
temporal-resolution must change:

`STORAGE_TARGET_REQUIRES_CAPTURE_POLICY_CHANGE` and STOP for owner/science.

## 13. Phase K — ADOPT / WRAP / REJECT

| Candidate | Decision | Why |
|---|---|---|
| Current SQLite + RDP unchanged | **REJECT** | 90d residency + recursive ZIP_STORED full copy of immutable RDP makes same-volume footprint ~2× HOT; weekly off-host full re-sends immutable bytes; size-only remote verify cannot authorize eviction |
| PyArrow Parquet ZSTD + batching | **WRAP** | already a locked dependency (`pyarrow==25.0.0`); semantic equality proven on schema-faithful corpus; default unspecified write is snappy, research_store is NONE |
| DuckDB multi-file / partitioned Parquet | **WRAP** | already locked (`duckdb==1.5.5`); `read_parquet` over HOT tree; no new service |
| Split operational DB from bulk raw | **WRAP** | SQLite remains the operational ledger; bulk canonical raw becomes time-partitioned Parquet with `response_sha256` identity |
| Upload-once immutable + lifecycle eviction | **WRAP** | standard object-lifecycle pattern on existing Drive; matches 90d residency |
| Current repeated full-backup topology | **REJECT as HOT data plane** | keep only for mutable SQLite/journals/unclosed tail |
| Simple zlib CAS files for raw | **REJECT unless** live Parquet shows a correctness/operability disadvantage | Parquet already preserves exact canonical bytes + occurrence metadata; CAS adds many tiny Drive objects |
| rclone Drive SHA256 | **ADOPT** (existing bin `/usr/bin/rclone`) | native `sha256Checksum` + `--download` fallback; no new provider |
| Existing ZIP_STORED + manifest | **WRAP** | exact source bytes; inventory SHA256 already exists |
| Apache Iceberg / Delta / Hudi / lakehouse catalog | **REJECT** | needs a catalog service or new operational plane; scale is tens of GiB not PB; current consumers are file+manifest; complexity larger than the problem |
| MinIO / GCS / S3 / new cloud | **REJECT** | Drive already exists; new provider/credential/cost |
| PostgreSQL / Kafka / Redis | **REJECT** | SQLite is not the bulk; no streaming bus requirement |

Expected bias honored: mature Parquet / DuckDB / rclone; no new table platform.

## 14. Selected architecture

Name: `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_V1`

1. **HOT scientific**: keep immutable Parquet identity; write ZSTD (level 3
   unless live encode-time forbids); close UTC-day partitions; optional member
   content-address if live duplicates are material.
2. **HOT raw**: lossless time-partitioned Parquet of canonical JSON bytes +
   occurrence metadata; `response_sha256` unique-body table; SQLite drops
   COMPLETED bodies only after materialize+hash+no unresolved dependency.
3. **COLD**: closed daily ZIP_STORED bundles on existing Drive; SHA256 verify;
   no query-in-place.
4. **Mutable durability**: SQLite snapshot 12h retain-1; off-host delta of
   mutable files; do not full-copy HOT RDP locally or weekly.
5. **Eviction**: 90d from canonical availability/closure clock; lock/plan/
   upload/verify/TOCTOU/exact-delete.
6. **Hydration**: isolated temp `data_root`.
7. **Admission**: extend `DATA_RESOLUTION_ECONOMY` with 97d footprint math.

## 15. Capacity acceptance

`hot_window_days=90`, `archive_cadence_days=7`, `capacity_horizon_days=97`.

Selected architecture typical `TOTAL_DATA_RELATED_LOCAL_FOOTPRINT_AT_97D`
= 23 048 602 003 bytes (21.47 GiB) ≤ TARGET 40 GiB and HARD 50 GiB.
Conservative measured stress = 46 000 455 406 bytes (42.84 GiB) ≤ HARD and
> TARGET. Terminal: `STORAGE_97D_ARCHITECTURE_READY`.

Limitation: denominator is a ~3-day LIVE cohort, linearly scaled. Mix shift
toward p95 member files is the stress case. Contractual 1 GiB/day saturation
remains a separate theoretical bound (97 GiB) and must not be treated as
expected fill.

The archive→verify→evict path must still be executable and fail-closed before
any age policy is called "runway". Whole-host at 19:18Z: ~17% used; leftover
same-volume ZIP is current disk, not the selected 97d term.

## 16. Implementation atom (not this PR)

Do **not** start automatically. Destructive eviction is a **later** gate.

Suggested later task id: `FACTORY_HOT90_IMMUTABLE_DRIVE_ARCHIVE_IMPL_V1`
Precondition: this atom terminal `STORAGE_97D_ARCHITECTURE_READY` and merge of
the research PR. Do not start IMPL from an unmerged working copy as production
mutation. Destructive eviction remains a later gate after IMPL write-only
commissioning.

Write set (bounded; eviction still a later destructive gate after IMPL):

- `catalog/schemas/observation_schedule_v1.schema.json` — keep
  `canonical_panel_retention` const `IMMUTABLE`; add
  `hot_local_residency_days`
- `catalog/schemas/experiment_spec_v1_2.schema.json` if it still duplicates
  the panel retention block
- `docs/operator/FACTORY_LIFECYCLE_COLLECTOR.md` — **Observation RDP / Parquet
  row only**: replace “never auto-deleted by retention” with content-immutable
  + 90d HOT residency after COLD SHA256 verify. Do not widen that replace to
  sealed live releases, identity, or receipts.
- `delivery-harness/policies/solana-alpha-lab.md` storage-admission extension
- `src/solana_alpha_lab/factory/observation_panel_publisher.py` (explicit ZSTD;
  optional closed-day batching; do not change availability clocks)
- `src/solana_alpha_lab/factory/research_store.py` (explicit ZSTD on new events;
  projection rebuild after eviction)
- `src/solana_alpha_lab/factory/observation_schedule_retention.py` + store
  (split A vs B; no 31→90 as the design)
- new `src/solana_alpha_lab/factory/raw_evidence_plane.py` (Parquet HOT raw)
- `configs/factory_remote_operations_v1_1.yaml` backup source lists (mutable
  vs immutable)
- `src/solana_alpha_lab/factory/offhost_backup.py` SHA256 verify; upload-once
  archive copyto
- archive packager WRAP of existing `package_backup` ZIP_STORED+manifest
- eviction planner (lock/plan/TOCTOU/exact paths) — must refuse if
  `hot_local_residency_days` is absent
- tests for compression equality, raw extract, verify-before-evict, hydration
  isolation, max availability clock, no mtime age, no eviction under
  IMMUTABLE-only schema
- Catalog/docs

Migrations / compatibility:

- old uncompressed/snappy parquet remains readable;
- readers stay HOT-tree unaware;
- SQLite schema: no bulk raw column required; bodies optional.
- Do not rewrite historical RDP bytes in place.

Deployment sequence:

1. write-only HOT ZSTD + raw plane beside current files;
2. archive closed days (verify SHA256) **without** eviction;
3. mutable-only local backup cutover;
4. commissioning proof: isolated hydrate of one archived day;
5. STOP. Eviction gate is a separate owner/destructive atom.

Rollback: revert writers to current `pq.write_table`; keep archived objects
(append-only); SQLite still has bodies until compaction is enabled.

Commissioning proof: one closed day archived, SHA256 verified, isolated
hydrate equals source tree, live Factory state unchanged.

## 17. Owner readout answers (index)

See `docs/reports/factory_97d_storage_architecture_proof_v1/a1_owner_readout_v1.md`.
