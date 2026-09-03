# EXECUTION_DOMAIN_MODULARITY_AND_FAST_CI_V1 — owner readout

## Decision delta

PAPER/SHADOW execution now has a machine-checked dependency boundary and an
exactly-once fast CI lane (`validate-execution`), while the final merge gate
remains one `validate` over core + execution + four general shards.

## Local E2E

- Boundary: `EXECUTION_DOMAIN_BOUNDARY: PASS`
- Fast lane: `EXECUTION_DOMAIN_FAST_TESTS: PASS` (~15–18s / 76 cases)
- Coverage: 7 execution + 355 general = 362 modules; 76 + 4073 = 4149 cases;
  overlap 0
- Ordinary projected max ~438s after one diagnosis calibration; balance ratio 1.00
- Product runtime source diff: 0 files under `src/solana_alpha_lab/factory/`

## Exact-head diagnosis

First green exact-head run `33790086715` at `3a1b59f7…` had
`critical_path_seconds=652` (>630) because the Windows profile under-weighted
HFIC/pathrisk modules on ubuntu-24.04. One allowed repair: scale module weights
by observed CI test elapsed per shard, then replan once. No second architecture
and no test weakening.

## Terminal (after re-run exact-head CI)

Pending repaired exact-head GitHub CI for final
`EXECUTION_DOMAIN_MODULARITY_FAST_CI_PASS`.

## Non-claims

No live authority, no second repository, no path-based suite skip, no alpha.

## Next

`STOP_THIS_CHAIN` after merge read-back; wait for selected research or
market-evidence gate.
