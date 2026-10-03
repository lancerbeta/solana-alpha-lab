# DELIVERY_SHADOW_PIN_AGGREGATE_SNAPSHOT_V1 evidence (compact, policy part B)

Base: 72330ae1727631cb5c0dacc0ab6bc6f65fee2b80 (after PR #368 and #369).

## Re-measure on base (last 40 first-parent merges)
- changed `catalog/assets/core.yaml`: 38/40
- rewrote `docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json`: 37/40 (182 rewrites in history)
- historical pins to aggregate paths: exactly two, owner_pulse -> core.yaml and
  task34a a3_documentation_foundation -> docs/OPERATOR_NAVIGATION.md; both now covered by the same shared set.

## Fix
`harness_owned_aggregate_paths()` = `harness_sync.MANIFEST_RELATIVE` + `ASSET_REGISTRIES` + `NAV_OUTPUTS`;
`_preflight_shadow_pin_problems` skips pins to those targets. Remaining guard: `harness_sync.check_drift`
(derived drift/Catalog validation) run by preflight on the changed paths. `FROZEN_SEMANTICS_EVIDENCE_FILES` unchanged.

## Real-tree dry run (no Git mutation; blob lookup returns a new sha)
| changed set | base code | candidate code |
|---|---|---|
| core.yaml | SHADOW_PIN_DRIFT:owner_pulse...->core.yaml | [] |
| task21_owner_pulse.py | 10 DENYs | 10 DENYs (unchanged) |

Output sha256 (summary JSON): d89b12c48150252f02ab9c8e235c7f5bec2b3ce154ac027c87dcc49428340ac9
Reproduce: load `scripts/delivery_harness.py` from the base ref and from HEAD, call
`_preflight_shadow_pin_problems(root, head="0"*40, changed={<path>}, blob_sha_lookup=lambda r: "f"*64)`.

## Dogfood
The shadow-pin scan runs only in local `preflight-push`, which executes the candidate worktree code; merge-readiness
and CI do not run it. This diff therefore contains no `owner_pulse_read_model_acceptance_v1.json` change although
it changes the Catalog. Base-policy exception not used.

## Tests
`tests/test_preflight_shadow_pin_drift.py`: 16 tests OK (4 new: catalog registry, nav+manifest, product path still denies,
exempt set equals harness_sync constants).

## Residuals
No test locks the aggregate-target-missing skip; `./`-prefixed pins were never scanned (unchanged).
