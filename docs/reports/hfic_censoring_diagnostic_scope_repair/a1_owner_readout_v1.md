# HFIC_CENSORING_DIAGNOSTIC_SCOPE_REPAIR_V1 — Owner readout

Date: 2026-09-17 · Route: DIRECT_CURSOR_DELIVERY

## What landed

The canonical censoring diagnostic still binds the full LIVE CORPUS files
first. After bind it projects the diagnostic census to rows whose mint appears
on frozen X300 observation keys (not Y-only rows). Four-way classification,
unknown-state, empty-mint, duplicate-census, admitted coverage and comparable
membership run on that population only.

Receipt schema is `1.1`. These two fields keep their 1.0 meaning:

- `counts["census_rows"]` — all loaded census rows
- `counts["other"]` — unexpected states on the **full** census file

`UNKNOWN_CENSUS_STATE` keys off `other_in_scope` (unexpected states inside
the X300 diagnostic population). Out-of-scope pre-X exclusions are
`out_of_scope_census_rows`. They are not unknown.

Historical receipt
`2ce8af5008e0038741c77fa292886b8da2520c733c3d4c491e03b23bdded0de2` is
untouched. Its 1.0 `counts["other"]` is the full-census unexpected bucket
(138234). That is **not** 1.1 `other_in_scope`. Frozen spec YAML/SHA, pins,
parquet and LIVE CORPUS are untouched. This atom did **not** run the real
scientific diagnostic.

## Receipt counts to read

| Field | Meaning |
| --- | --- |
| `census_rows` / `census_rows_total` | all loaded census rows |
| `census_distinct_mints_total` | distinct nonempty census mints |
| `discovered_in_observation_partition` | distinct nonempty mints in the observations **file** (any point) |
| `diagnostic_population_census_rows` | census rows whose mint appears on X300 keys |
| `diagnostic_population_distinct_mints` | distinct mints in that projection |
| `out_of_scope_census_rows` | full-file census rows outside the X300 projection |
| `other` | 1.0: unexpected states on the full census file |
| `other_in_scope` | unexpected states **inside** the X300 projection |

Pinned production expectation (not a live rerun):

- `census_rows_total` = 138844
- `census_distinct_mints_total` = 138844
- `discovered_in_observation_partition` = 610
- `diagnostic_population_census_rows` = 610
- `diagnostic_population_distinct_mints` = 610
- `out_of_scope_census_rows` = 138234
- `other_in_scope` = 0

Do not call 138234 unknown. On that historical 1.0 receipt it was stored as
`other`; after this repair it is `out_of_scope_census_rows`.

A dedicated fail-closed reason `OBSERVATION_MINT_MISSING_FROM_CENSUS` covers
an **X300** observation mint with no census row. Y-only membership does not
open that gate. It is not collapsed into `UNKNOWN_CENSUS_STATE`.

## Historical SQL gap

`docs/evidence/hfic_censoring_ignorability_diagnostic/a1_denominator_closure_v1.json`
is not edited. Its grouping SQL is incomplete relative to the observation-mint
denominator: it groups the full census. Interpret 148/327/35/100/475 against
the observation-mint population, not the 138844-row discovery file.

## What this does not mean

A green merge here is not a scientific result. MAR, ignorability,
identifiability and alpha remain unproven.
`CENSORING_OBSERVED_X_SHIFT_NOT_DETECTED` still means only that the frozen
omnibus did not detect shift on comparable X.

## Next (separate atom)

READ-ONLY OPERATE scientific rerun of
`CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001` against the already-repaired
LIVE CORPUS. This merge does not authorize that run.
