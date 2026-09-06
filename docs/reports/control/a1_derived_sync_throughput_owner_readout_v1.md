# Owner readout — DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1

`DERIVED_SYNC_THROUGHPUT_PASS` evidence packet. Not canonical DONE. Not alpha.

## What changed

Catalog derived-sync HASH_SCOPE now follows proof obligation, not registry membership.
`--apply --base-ref` and `--check --paths-from-staging` use the same classifier.
`HARNESS_SYNC_PLAN` is on stderr before the first `desired_sha256`.

Live probe on this branch vs `expected_base`:

```text
HARNESS_SYNC_PLAN: class=SOURCE_REHASH hashed=1 nav=0 fallback=none
registered_sha_assets_total=1572
```

Protocol pin repaired in seconds. Unscoped `--check` remains the fail-closed backstop.

## Cheapest falsifier

Fixture ≥200 sha256 members. Unique `desired_sha256` paths (spy `HARNESS_SYNC_SHA256_SPY`) equal HASH_SCOPE (`affected ∪` cataloged NAV_OUTPUTS, ≤8) for RECORD_ADD_OR_MOVE apply+check, existing-path sibling, and SEMANTIC_NAV. Stale pin still fail-closed.

## Isolated critics

CODE_REVIEWER PASS. GOAL_DOD_CRITIC PASS. ARCHITECTURE_CRITIC PASS.

Residual (non-blocking): scoped check still runs nav/checkpoint against the worktree; unscoped CI remains the backstop.

## Radar

NOW=NONE. WATCH: later optional skill sentence that HASH_SCOPE is classified before review, not after critics.

## Stop

No merge until exact-head CI and merge-readiness, then owner phrase. Owner does not click GitHub Merge.
