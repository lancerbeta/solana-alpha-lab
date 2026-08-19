# Fresh OOS baseline vs friction veto — owner readout

Live Free-key campaign completed. This closes the exact median-X veto
family. It is not alpha, not MOVE 3, and not `FACTORY_V1_OPERATIONAL_READY`.

## Packet

| Field | Value |
| --- | --- |
| QUESTION | Does a frozen t0-friction veto improve H900 quoted-exit median and right tail versus the same eligible baseline on a fresh outcome-blind cohort? |
| ESTIMAND | baseline eligible H900 quoted liquidation recovery versus same baseline after `VETO_IF_X_LT_SAMPLE_MEDIAN` |
| POPULATION | new live 6 RECENT + 6 TRADED, excluding A1, MOVE 2 and commissioning mints |
| DATA | capture policy + three exclusion receipts; runtime and acceptance now hash-bound |
| RESULT | `CLOSE_EXACT_FRICTION_VETO_FAMILY` (`STRATUM_UNSTABLE`: kept arm is TRADED-only) |
| UNCERTAINTY | screening hint, not OOS confirmation |
| ROBUSTNESS | H3600 predeclared robustness, not searchable Y |
| FAILURE | audition sign still `DIRECTIONAL_HINT_NOT_CONFIRMATION`; veto fails the both-strata keep rule |
| DECISION | close this exact veto family; no post-hoc threshold search; no recapture suffix |
| NEXT | do not extend to paper/shadow on this veto; do not start MOVE 3; VPS remains later external authority |

## What the numbers say

Audition on the fresh sample again gave a directional hint, not confirmation.
The frozen veto kept 6 of 11 complete-XY cells. Median and p90 of the kept
arm look better than the baseline, but every kept cell is TRADED. The pass
rule requires both RECENT and TRADED in the kept arm, so the family closes.

## Non-claims

No alpha, NetReturn, MOVE 3, VPS, paid plan, second provider, `/execute`,
wallet, signer, transaction, or operational-ready milestone.
