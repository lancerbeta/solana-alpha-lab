# HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC_V1 — Owner readout

Date: 2026-09-17 · Route: DIRECT_CURSOR_DELIVERY

## What landed

Reusable offline capability `CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001`.
It tests whether census `censored_late` looks selected on a frozen X300 Block A
surface. It does not certify MAR, ignorability, identification or alpha.

CLI requires explicit `--census` and `--observations`. There is no active-RDP
default. This atom did **not** run the diagnostic on canonical live parquet.

## Frozen denominator (census labels, no Y, not a diagnostic run)

| Class | Count |
| --- | --- |
| discovered in observation partition | 610 |
| `X_ELIGIBLE` + `observed` | 148 |
| `X_ELIGIBLE` + `censored_late` | 327 |
| comparable X300 subset | **475** |
| `ADMITTED` + `censored_late` (no X300 anchor) | 35 |
| `X_POPULATION_INELIGIBLE` | 100 |

475 is census `candidate_state=X_ELIGIBLE`. Census `observed` is not proof of
complete X→Y pairs. The 35 stay visible as
`CENSORING_NO_COMPARABLE_X300_ANCHOR_UNRESOLVED`. Counts are bound to parquet
SHA-256 and grouping SQL in the denominator receipt; they are not a live
diagnostic result.

## Terminals

- `CENSORING_OBSERVED_X_SHIFT_DETECTED` — frozen-X distribution shift
  detected; complete-case remains `RANDOM_SAMPLE_UNPROVEN`
- `CENSORING_OBSERVED_X_SHIFT_NOT_DETECTED` — still
  `IGNORABILITY_UNPROVEN` / `IDENTIFICATION_UNPROVEN` /
  `RANDOM_SAMPLE_UNPROVEN`
- `CENSORING_DIAGNOSTIC_INCONCLUSIVE` — coverage / n / unknown census /
  duplicate mint or X300 / value_kind / mixed dataset-session / integrity fail

CLI and capability `terminal` is the atomic pair
`scientific_terminal|population_scope`. Canonical scope requires frozen
dataset/session identities plus census/observations SHA-256 pins; this
spec has no such pins, so this atom cannot emit
`CANONICAL_COMPARABLE_X_SUBSET`. Block A `value_kind` is enforced.
Typed values are materialized only for Block A.

Runtime loads only `configs/hfic_censoring_ignorability_diagnostic_v1.yaml`
bytes pinned as `FROZEN_SPEC_SHA256`. A mutated spec cannot self-declare a
canonical population.

Synthetic tests cover shift, no-shift, Y-point unread, coverage floor,
unknown census, duplicate mint/X300 including non-Block-A fields, mixed
cohort fail-closed, frozen-spec hash pin, admitted coverage class, latency
tautology kept out of the omnibus, seeded repeat, zero provider budget, and
explicit-path CLI. X_ELIGIBLE mints missing from
observations are INCONCLUSIVE.

## Next (separate atom)

Canonical scope cannot emit from this merge. Live census/observations parquet
and `CENSUS_RELEASE_SCHEMA` / `OBS_RELEASE_SCHEMA` lack `dataset_id` and
`scientific_context_session`. The frozen spec has no census/observations
SHA-256 pins. Counts in the denominator receipt are bound to those parquet
hashes and grouping SQL; they are not a `CANONICAL_COMPARABLE_X_SUBSET`
diagnostic result.

The next atom must add those identity columns and pin the file hashes before
any run can emit canonical scope. Explicit paths alone are not enough. This
merge does not authorize a scientific diagnostic against canonical active RDP.
