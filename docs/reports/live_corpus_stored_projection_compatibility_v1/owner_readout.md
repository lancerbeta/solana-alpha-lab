# LIVE corpus stored-projection compatibility

The defect was logical identity drift, not unreadable or corrupted parquet.
The moving OBS-24 writer projection added three null JSON keys to historical
OBS-21 rows. All other saved claims remained unchanged.

`live_corpus_logical_rows.select_stored_partition_projection` now owns exact
frozen CENSUS-20, OBS-21 and OBS-24 layouts. Names/types/nullability are checked
before row projection; unsupported layouts return a typed STOP. Repair passes
claims from the root already verified on its own stored contract into the
measurement owner. Existing final claim equality and publication checks remain.
The LIVE descriptor lists supported mixed projections separately from the
writer fields; its digest uses the existing deterministic V2 metadata revision.

Evidence: an independently pinned physical OBS-21 fixture was RED before the
patch and GREEN afterwards. OBS-24 with explicit null columns retains its
independently pinned current hash. Three physical historical scratch cohorts
repair at v3 with unchanged claims/PIT/epoch/full budget. Production
seal/verify/import adds OBS-24 with null and non-null clock fields at v4. A
cold subprocess selects the current root, binds Forge input and executes the
actual temporal read/evaluator over mixed files. Old rows remain byte-value
equivalent, including absent clock keys and typed missing values. Mixed repair
is idempotent; ordinary v5 append measures only the new cohort's two partitions.
Existing V2 interruption/retry/immutable-target tests are reused unchanged.

The narrow owner-authorized real read-only measurement reproduced all six
saved claims, including historical OBS hashes. Hash/size/mtime/path inventory
before and after matched. Detailed machine evidence is stored outside tracked
Git and the canonical data root; this report contains no runtime identities,
epochs, rows or operation results. No real repair/import was performed.

Unsupported names/types/nullability, altered file bytes and mismatched stored
content/PIT claims are fail-closed. No data rewrite, clock inference, budget
key, publication state machine, harness change or consumer science change.
No provider/deploy or real next-cohort access; no real Forge/scientific write.

Limit: supported physical contracts are exactly the three frozen layouts.
Writer extensions require old/new/mixed tests in the same PR. Metadata repair
remains serialized with import under V2; this patch adds no concurrency or
power-loss guarantee. Revert code ordinarily; never delete historical roots.

Factory Fit is FULL_REVIEW. Capability radar NOW=NONE; WATCH=separate OPERATE
after approved merge/post-merge readback. Delivery stops at the unchanged green
exact PR head and machine-rendered owner merge phrase. The next runtime step
requires separate authority: historical repair, exact verified next import,
cold readback and STOP_BEFORE_FORGE.
