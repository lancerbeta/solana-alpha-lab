# EXECUTION_DOMAIN_MODULARITY_AND_FAST_CI_V1 — owner readout

## Decision delta

PAPER/SHADOW execution now has a machine-checked dependency boundary and an
exactly-once fast CI lane (alidate-execution), while the final merge gate
remains one alidate over core + execution + four general shards.

## Local E2E

- Boundary: EXECUTION_DOMAIN_BOUNDARY: PASS
- Fast lane: EXECUTION_DOMAIN_FAST_TESTS: PASS (~15–18s / 76 cases)
- Coverage: 7 execution + 355 general = 362 modules; 76 + 4073 = 4149 cases;
  overlap 0
- Ordinary projected max ~438s after one diagnosis calibration; balance ratio 1.00
- Product runtime source diff: 0 files under src/solana_alpha_lab/factory/

## Exact-head CI

- Head: 23d82b33537783fdef25855d7ece904694e3c3cb
- Run: 33797983306
- alidate-execution job wall: 31s (hard <=180)
- Ordinary shard test elapsed: 381 / 422 / 457 / 444
- critical_path_seconds: 550 (hard <=630, target <=600)
- Diagnosis: one CI-elapsed scale calibration after first green run at 652s

## Terminal

EXECUTION_DOMAIN_MODULARITY_FAST_CI_PASS after guarded merge + post-merge read-back.

## Non-claims

No live authority, no second repository, no path-based suite skip, no alpha.

## Next

STOP_THIS_CHAIN after merge read-back; wait for selected research or
market-evidence gate.
