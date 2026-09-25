# CI wall-clock regression repair — owner readout

Root cause was repeated pure-Python Catalog YAML parse inside every semantic/capability identity call after A5. This atom caches parse trees once per exact file text per process (`CSafeLoader`, private deep copies), streams `module_done` / `slow_module` from shard jobs, and restores CI budgets from temporary A5 headroom.

## Before / after (authoring workstation, alone)

| Probe | Base | Head | Ratio |
| --- | ---: | ---: | ---: |
| `test_corrupt_slot_reservation_remains_unresolved_occupancy` | 57.718 s | 9.492 s | 6.1× |
| `test_g11_capability_change_does_not_free_completed_slot` | 67.009 s | 11.000 s | 6.1× |
| A5 gold (`tests.test_forge_evidence_identity_and_owner_gold_v1`) | ~22 min (pre-fix) | 228 s (54/54) | — |

## Identity (I1)

| Digest | Base | Head | Equal |
| --- | --- | --- | --- |
| `semantic_capability_digest_sha256` | `e20716d1932d81be735aa514235f3666c13c8bc906f57cd9be1ee6f1afd1ecb2` | same | true |
| `capability_epoch_sha256` | `5e448b10d39fca04fd706a52cd55a24f0248280beb896a918f2957d8ce2f9a69` | same | true |

Protected I2 paths are untouched. Loader: `CSafeLoader`. Catalog structural equality vs `SafeLoader`: 7/7 (guard test).

## Budgets

`validate-core` / `validate-execution` 25 min, `validate-tests` 30 min, aggregator 5 min. Soft shard budget warning at 20 min is informational only.

## Remaining gate

Exact-head CI on the PR must show every `validate-tests` shard ≤ 20 min with `module_done` / `slow_module` lines and no soft-budget annotation. Then merge-readiness → owner phrase → guarded merge → post-merge main CI (target ≤ 22 min vs prior 53.2 min).

No CI-optimization chain after this atom. No remote host action. No alpha.
