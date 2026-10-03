# CI throughput repair — owner readout

Atom `CI_THROUGHPUT_AND_IMPACT_SHADOW_V1` v1.1: full-suite throughput repair only. Part B (shadow impact selector) is stopped, see below. Exact-head after-state numbers are recorded on the PR and in the handback after the run, never in a bound file.

## What changed

- `configs/ci_test_shards_v1.json`: 4 stale shards (projected 438 s each, real 1200+ s) replaced by 6 shards planned from fresh `module_done` telemetry. The plan embeds `profile` provenance (4 successful exact-head runs, per-module median) and `module_seconds`, so it is reproducible: `plan_shards(module_seconds, count)` equals the committed shards (test).
- `scripts/ci_test_partition.py`: CI shard range 4-6 (`SHARD_COUNT_MIN/MAX`, also read by `validate_ci.py`), profile built straight from CI shard logs (`--module-done-log`, `--source-run`), `--compare-counts`, equal-load tie-break by module count.
- `scripts/render_ci_workflow.py` was stale (no resource-proof job, wrong tests timeout); it now reproduces `ci.yml` byte for byte (test).
- `ci.yml`: matrix 0..5, `max-parallel: 6`, `--count 6`. Coverage semantics untouched: `run_ci_test_shard.py` still proves each module runs once, reserved execution modules never enter general shards, loaded cases equal canonical discovery.

Reprofile command (event-driven, not scheduled):

```text
uv run --locked --managed-python python -B scripts/ci_test_partition.py --module-done-log <shard.log> ... --source-run <run_id> ... --reserved-manifest configs/execution_domain_v1.json --shard-count 6 --output configs/ci_test_shards_v1.json
```

## Why 6 shards

Fresh profile: 448 general modules, 4146 s of test time, longest module 276 s. Baseline exact-head PR runs `37137684221`, `37131300645`, `37129255347` (4 shards, stale plan, different heads): run wall 1271 / 1229 / 1200 s (20.0-21.2 min), max shard test elapsed 1245 / 1202 / 1175 s (mean 1207 s), setup 10-13 s per job, queue 1-2 s.

Real shards vary about 14 % around the profile (16 observed shard factors, 0.63-1.12). Two noise models (resampling those observed factors; independent lognormal sd 0.14) bracket the expected slowest shard, excluding about 15 s per-job setup:

| shards | projected max | modelled real max | gain vs 1207 s | P(<= 15 min) |
| ---: | ---: | ---: | ---: | ---: |
| 4 (fresh plan) | 1037 s | 1107-1204 s | 0-8 % | about 0 |
| 5 | 829 s | 885-982 s | 19-27 % | 0.2-0.5 |
| 6 | 691 s | 759-828 s | 31-37 % | 0.8-1.0 |

5 reaches the 25 % bar only in the optimistic model; 6 clears it in both. The exact-head run confirms or refutes this; if the extra runners only queue, the plan is reduced rather than timeouts or the model tuned.

## Part B terminal: `NO_MATERIAL_SELECTION_VALUE`

Replay of a fail-closed affected-test selector over the last 45 merges: 9 hard-FULL, eligible denominator 36, bounded candidates 6/36 (all FORGE_HFIC), 0/6 under the 70 % time cap, median selected time about 83 %, FORGE_HFIC floor about 53.5 % of suite time. Main FULL reasons: unclassified test 18, unknown source path 7, unproven Catalog propagation 4. Details and the rebuild condition are in the task contract. No selector code ships.

## Residual / WATCH (not optimised here)

Top modules by profile: `test_harness_sync` 276 s, `test_hfic_scientific_disposition_continuity_v1` 217 s, `test_forge_runtime_discovery_binding_v1` 197 s, `test_harness_sync_bindings` 182 s, `test_forge_evidence_identity_and_owner_gold_v1` 161 s. Top 10 modules are 41 % and top 20 are 58 % of suite time. Trigger to look again: a measured exact-head critical path above about 15 min after this change, or a single module above about 300 s.

Stale-profile warning (`CI_SHARD_PROFILE_STALE_REBALANCE_RECOMMENDED`) is unchanged; reprofile only when it fires.

## Non-claims

No test deleted, skipped or weakened; no timeout change; no new dependency, service, cache or scheduled profiler; no product, science or runtime change; no selector.
