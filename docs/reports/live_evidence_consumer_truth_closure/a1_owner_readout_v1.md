# LIVE_EVIDENCE_CONSUMER_TRUTH_CLOSURE_V1 — owner readout

## What closed

1. **Real RDP → live source** via `build_live_observation_source_from_rdp` /
   CLI `build-live-source` (no SQLite; producer SHA from RDP events).
2. **Campaign-relative 3×7d cohorts** from schedule activation clock
   (`REL-…` half-open windows). C4 exact windows proven in tests.
3. **Cumulative LIVE CORPUS** current version rebinds all cohort partitions;
   Forge still sees one logical dataset; no O(N²) parquet copy.

## Proof keys

```text
REAL_RDP_TO_LIVE_SOURCE = PASS
SQLITE_REQUIRED = false
C4_COHORT_WINDOWS = CAMPAIGN_RELATIVE_3X7_PASS
CURRENT_CORPUS_CUMULATIVE_ROWS = PASS
LATEST_ONLY_FALSE_POSITIVE = KILLED
12_COHORT_CURRENT_VIEW = ALL_12_PRESENT
FORGE_CURRENT_DATASET_COUNT = 1
PARQUET_HISTORY_DUPLICATION = NO
HISTORICAL_VERSIONS_IMMUTABLE = PASS
CONFIRMATORY_REUSE_FORBIDDEN = true
PROVIDER_CALLS = 0
CREDENTIAL_READS = 0
VPS_MUTATIONS = 0
```

## Non-claims

- C4 collector left untouched (no pause/deploy/authorize/provider).
- No live C4 seal/import/Forge run in this atom.
- Confirmatory reuse remains forbidden (`EXPLORATORY_REUSE`).
