# INCREMENTAL_HARNESS_SYNC_V1 — owner readout

## Capability

Routine Catalog derived sync is incremental versus an exact task/control
base. Bare `--apply` remains the full oracle.

## Commands

Routine FINISH:

```text
uv run --locked --managed-python python -B scripts/harness_sync.py --apply --base-ref <exact expected_base>
```

Full oracle / recovery:

```text
uv run --locked --managed-python python -B scripts/harness_sync.py --apply
```

or `--apply --full`.

## Observed local probe

On this branch before PR, a representative protocol/harness source delta hashed
2 of 1422 registered sha assets, ran navigation 0 times, and finished in about
8 seconds. Full check after incremental remained PASS.

Benchmark receipt:
`docs/evidence/incremental_harness_sync/a1_benchmark_receipt_v1.json`.

## Non-claims

No alpha, no provider/credential authority, no persistent hash-cache truth
owner, no CI wall-clock assertion.

## STOP

After exact-head CI: merge phrase only. Do not click GitHub Merge.
After merge: return to Factory / Hypothesis Forge / evidence acquisition.
