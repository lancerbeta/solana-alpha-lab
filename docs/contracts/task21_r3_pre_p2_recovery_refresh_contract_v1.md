# TASK-21 R3 pre-P2 recovery refresh contract v1

## Decision

Before R3 P2 may use Jupiter, preserve the exact frozen R3 P0 and P1 evidence in a new content-addressed ZIP, prove byte-identical Google Drive read-back, and restore every archived file into an isolated create-only location.

## Frozen source

- P0: `local/task21_forward/final_cohort/r3/run=r3-20260801T134014806103Z-ac917cf4f972`
- P1: `local/task21_forward/final_cohort/r3/p1/run=p1-20260801T142017719450Z-8bb3c0961780`
- Expected inventory: 18 files and 237983 stored bytes.

The archive manifest binds every repository-relative path, byte size, SHA-256, the ordered source roots, and a hash of the complete inventory. Packaging and restore must not mutate or delete source evidence.

## Recovery proof

1. Create a deterministic ZIP under `local/task21_recovery/pre_r3_p2/package` using exclusive create and a SHA-256 filename.
2. Restore the local bytes under an isolated content-addressed root and verify all entries.
3. Confirm the exact filename is absent in Drive folder `1EISgmsB8nt2pkU4uBUO6Sav1Fzbo6Hw3`.
4. Upload one new private file; do not update sharing or existing bytes.
5. Read back the remote object, prove exact size and SHA-256 identity, then restore those bytes under a separate isolated root.

Any collision with different bytes, missing entry, path escape, hash mismatch, source drift, overwrite, deletion, or archive size above 16 MiB fails closed before P2.

## Boundary

This proof authorizes no provider call by itself. R3 P2 remains bounded to the user's combined gate: exact two frozen members, Jupiter calls at most 16, retries 0, concurrency 1, create-only local evidence at most 16 MiB, and no credentials, cash, scheduler, deploy, Catalog, Sources, wallet, signer, transaction, delete, overwrite, or merge action.
