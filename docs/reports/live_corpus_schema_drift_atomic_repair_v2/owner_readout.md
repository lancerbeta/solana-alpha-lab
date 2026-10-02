# LIVE_CORPUS_SCHEMA_DRIFT_ATOMIC_REPAIR_V2

ENTRY_DECISION: START_WITH_PATCH. OWNER_LOOP: unchanged C1-C3 metadata repair,
later exact cohort import, readback, STOP_BEFORE_FORGE.
SEMANTIC_ROUTE: SEM-LIVE-EVIDENCE-TO-FORGE.

The scratch v3 incident reproduced both defects before implementation:
already-canonical schema drift collided with CANONICAL_TARGET_CONFLICT, and
pre-publication interruption changed old current labels. The new LIVE-local
dataset_version suffix binds composition and the effective schema contract while TASK-06 keeps
its unchanged identity algorithm. It changes metadata identity, not corpus_version.

AUTHORITATIVE_CURRENT_OWNER: datasets/live_lifecycle_corpus/lineage.json,
current_dataset_manifest_id. Prepare candidate labels (current=false), frozen
clock, partitions, validation receipt, dataset and published marker. Verify
manifest integrity, exact receipt/publication/labels, parquet bytes and measured
logical content/PIT bounds against unchanged cohort/release bindings. Only then
atomically replace lineage. Current selection receives the lineage authority;
historical flags cannot outrank it. Derived labels reconcile after visibility.

Existing repair-live-corpus-manifests supports built, compatible partial,
complete reused and current idempotent outcomes. Conflicting immutable bytes,
invalid current publication, parquet drift, unreconstructible rows and unsafe
paths STOP. It does not delete historical roots or regenerate broken current
metadata. First import uses the same publication boundary; a retry reuses its
frozen clock. Run repair/import serially; no new multi-writer infrastructure.

Fixture-only verticals prove metadata v3 -> repaired v3, unchanged scientific
MARKET_EVIDENCE_BASIS_V2 epoch, consumed AUTO and distinct-focus occupancy/history,
pre-switch old visible inventory, post-switch NEW despite stale labels, retry,
actual next verified synthetic import -> v4/four cohorts once/duplicate zero,
and existing CLI REPAIRED -> IDEMPOTENT_REPAIR. Parquet and sealed fixture
release bytes stay unchanged. Current row reads use only their validated root,
so malformed uncommitted partitions cannot poison current rows.

Scientific owner paths: factory/hfic_evidence_identity.py (V2 projection),
factory/hfic_preflight.py (enumeration/budget), factory/live_cohort_discovery_release.py
(current selection/rows) and factory/forge_input_receipt.py (owner receipt).
No V2 redesign or ResearchStore rewrite. SCOPE_SPLIT_REQUIRED: false.

Scratch readback (not runtime truth): market epoch before and after repair is
`5c2381201999efb0a8a8e46027f46032e2fa50ba748b4e40b52cdd2a4d44ca51`.
AUTO used remains 1/1; distinct-focus used remains 2/3, remaining 1. Complete
occupancy and history compare equal in the regression. Corpus version is 3
before and after repair; actual fourth synthetic cohort import produces 4.
Repair returns BUILT, metadata_identity_changed=true, lineage_switched=true,
scientific_epoch_changed=false and epoch_bump=false; rerun is IDEMPOTENT_REPAIR.
Compatible B -> C -> B metadata roots reuse immutable historical provenance.
The owner P1 regression also covers A -> partial B -> C -> B, interrupted after
receipt and dataset construction: B MID and existing immutable candidate bytes
stay identical, no conflict/manual deletion/restore, epoch and occupied budgets
remain unchanged. Repair generation_run_id derives from target MID; candidate
receipt predecessor is null and labels omit it. Lineage/readback retain the
actual transition predecessor. The LIVE-local identity explicitly binds schema,
logical profile, receipt schema/version, commit/clock contract, generation
constants and static required labels. Receipt-version-only drift gets a new
metadata identity and remains idempotent without creating a scientific epoch.
That drift is detected on an imported canonical root as well as on an already
repaired root: same schema is not sufficient to skip receipt-contract repair.
The new imported-root regression reproduced IDEMPOTENT_REPAIR incorrectly before
the fix and now proves REPAIRED, unchanged science and idempotent retry.
Missing canonical current clock/publication blocks consumers; damaged non-current
dataset/labels/partitions do not poison old current market or rows.

REAL_DATA_PLANE_MUTATED: false. REAL_C4_ACCESSED: false. C4_IMPORTED: false.
FORGE_RUN: false. Tests and faults run on isolated fixture directories only.

Focused validation: 142 tests PASS (one skipped), including the V2 vertical suite,
predecessor repair tests, scientific-identity assertions, 12-import series and
shared censoring/selection fixture consumers; two previously failing operational
closure tests also PASS. Old synthetic LIVE helpers lacked canonical version,
full receipt/clock/marker or valid TASK-06 identity. Fixtures now use existing
production builders/publication; current-root checks remain unchanged. Another
CI failure compared equal partitions in different orders: exact model comparison
now uses canonical partition-id order, retaining every integrity check and
original composition/receipt order. Both original temporal oracle/saved-result
verticals PASS on unchanged source. Total: 146 focused tests, one skipped.
After independent review findings, all 63 repair/import/scientific verticals
PASS again. They include imported-root same-schema receipt drift, corrupted
non-current logical grouping without poisoning old current/epoch/receipt, and
valid TASK-06 roots whose generation or receipt bytes violate their repair target.
Complete reuse/current idempotence now compare exact builder-derived dataset
and receipt using the saved target clock; conflicts STOP without writes.
Semantic search readback via existing catalog_cli search-assets: all four owner
questions return the intended owner as the sole result (rank 1):
"how does live RDP get into Forge" -> MODULE-LIVE-COHORT-TO-FORGE-001;
"where did my imported cohort land" -> MODULE-LIVE-COHORT-DISCOVERY-RELEASE-001;
"how do I repair LIVE corpus metadata" and "what owns current LIVE corpus" ->
MODULE-LIVE-CORPUS-MANIFEST-PUBLISH-001. Publication owner now points to this
task's recovery contract. Existing ACTIVE binding and semantic route are retained;
generated navigation comes from harness_sync, with no redundant route.
Residuals: metadata repair scans current parquet to prove logical reconstruction;
immutable conflicts need inspection, not automatic overwrite. Atomic lineage
replacement assumes serialized owner operations; power-loss/multi-writer
durability is not a new guarantee. Runtime success awaits separately authorized
OPERATE after delivery. No scientific candidate or look was created here.

NEXT_AFTER_MERGE: OPERATE C1-C3 repair -> exact C4 import -> canonical readback -> STOP_BEFORE_FORGE.
