# LIVE_COHORT_DISCOVERY_RELEASE_SERIES_V1 — owner readout

## Corpus identity / version model

| Field | Value |
|---|---|
| logical `dataset_id` | `DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001` |
| `dataset_version` | `corpus-v{N}-{cohort_id}` |
| `dataset_manifest_id` | `compute_dataset_manifest_id(...)` (content-addressed) |
| historical A3 | untouched singleton `DATASET-MANIFEST-DISCOVERY-EVIDENCE-RELEASE-001` |

## Cohort timestamp

Frozen: **`discovery_first_reliable_available_at`** — 7 UTC-day non-overlapping windows (`UTC-YYYYMMDD-YYYYMMDD`). Never cohorts by later Y outcomes.

## Readiness states

`COLLECTING` → `MATURING` → `READY_VALID` / `READY_VALID_WITH_COVERAGE_LIMITATION` / `READY_LOW_YIELD`; blocked: `RELEASE_BLOCKED_*` / `RELEASE_INVALID_SOURCE_INTEGRITY`. Only sealable READY_* seal.

## HFIC current-version resolution

`select_current_datasets_for_forge`: one entry per logical `dataset_id` (highest `corpus_version` / `is_current_corpus_version`). Then `MAX_DATASETS=8` cap. Not lexicographic first-eight weekly manifests.

## 12-release proof

`tests/test_live_cohort_discovery_release_series.py::test_twelve_weekly_imports_no_context_explosion` — 12 imports, 12 manifests on disk, HFIC packet sees 1 current corpus, epoch bumps 12 times, reimport no bump.

## False roadmap assumption cleared

Repeating weekly seal as A3 singleton `DATASET-MANIFEST-DISCOVERY-EVIDENCE-RELEASE-001` was unsustainable under HFIC `MAX_DATASETS=8`. Live path is a versioned corpus.

## Future weekly seal/import product code?

**Zero further product code** for the scientific bridge after collector commissioning. Ops: RDP rebuild snapshot → live-status → seal-live-cohort → verify-live → import-live.

## Non-claims

No provider/VPS/Forge/activate/A3 mutation/second platform/daily pulse.
