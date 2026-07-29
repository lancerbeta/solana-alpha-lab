---
evidence_id: EVIDENCE-T18-NARROW-DATA-QUALITY-SUMMARY-001
evidence_version: "1.0"
task_id: TASK-18
atom_id: T18-A3_DETERMINISTIC_OFFLINE_QUALITY_AUDIT_V1
status: ACCEPTED_LOCAL_CANDIDATE
as_of: "2026-07-29"
verdict: FIT_WITH_LIMITATIONS
contains_secrets: false
---

# TASK-18 narrow data-quality summary v1

## Decision

The exact TASK-17A bytes are fit for the frozen one-member, three-window,
quote-only replay estimand, with explicit durability limitations.

```text
FIT_WITH_LIMITATIONS
```

The result is not `FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND` because no backup
inventory or successful restore test was observed, and current matching hashes
cannot prove that overwrite prevention exists.

## Evidence

Machine receipt:
`docs/evidence/task18/narrow_data_quality_audit_v1.json`,
SHA-256
`52a4585364930ca4a62e12a06cf196af14309f34ab3d46c75f2c00a168e40403`.

- 12 of 12 frozen files matched exact size and SHA-256;
- 32 of 32 attempts reconciled;
- 24 accepted and eight excluded-retained attempts remained distinct;
- 32 unique composite identities, quote-attempt IDs, raw-event IDs and
  content hashes;
- zero PIT-order violations;
- zero latency mismatches;
- minimum within-window request gap: 2.200048 seconds;
- accepted trigger separations: 3599.993664 and 1818.792805 seconds;
- zero revision conflicts;
- 51,958 received bytes and 179,208 stored bytes reconciled;
- all provider, schema, route, receipt and tracked-audit checks passed.

## Limitations

- `BACKUP_INVENTORY_NOT_OBSERVED`;
- `RESTORE_TEST_NOT_OBSERVED`;
- `OVERWRITE_PREVENTION_NOT_PROVEN_BY_CURRENT_HASHES`.

These limitations do not manufacture missing rows or alter PIT semantics. They
mean the current bounded replay input is usable locally but its recovery
durability is not proven.

## Non-claims

This audit does not establish cross-token generalization, provider
reliability, Fillable, RealizedVWAP, NetReturn, signal, strategy, alpha or
production readiness. It neither reclassifies `T17A-WINDOW-02` nor authorizes
new collection.

TASK-19 is only `ELIGIBLE_CONDITIONAL_ON_TASK18_ACCEPTANCE`. A3 does not start
or authorize replay.

## Side effects

Provider/API/RPC/WSS calls, collector executions, raw writes, credentials,
cash spend, provider credits, wallet/signer/transaction actions and dependency
changes were all zero.
