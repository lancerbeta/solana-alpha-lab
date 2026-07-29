---
evidence_id: EVIDENCE-T18-CONTENT-ADDRESSED-BACKUP-RESTORE-001
evidence_version: "1.0"
task_id: TASK-18
atom_id: T18-A3R_CONTENT_ADDRESSED_BACKUP_RESTORE_PROOF_V1
status: ACCEPTED_LOCAL_CANDIDATE
as_of: "2026-07-29"
verdict: PASS
contains_raw_data: false
contains_secrets: false
---

# TASK-18 content-addressed backup and restore summary v1

## Decision

The three A3 durability limitations are closed for the exact frozen TASK-17A
snapshot.

```text
FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND
```

This is snapshot-specific recovery proof, not a claim that all future data is
automatically backed up or that the dataset supports broader inference.

## Evidence chain

1. The exact 12-file, 179,208-byte source inventory was packaged into a
   deterministic `ZIP_STORED` archive with a content-addressed filename.
2. The 187,756-byte archive has SHA-256
   `8b016b38096d87e182aa7d41e549fd6d97eb7008777e5c9dfe59b3b15178b838`
   and MD5 `5c273debe392d2130e20182c39e3d10c`.
3. One new file was uploaded to the private Google Drive folder
   `Solana Alpha Lab — Content-Addressed Backups`; no existing file was
   replaced and sharing remained disabled.
4. Google Drive raw-byte read-back returned exactly 187,756 bytes with the
   same SHA-256 and MD5.
5. The byte-identical archive exposed the exact 13-entry inventory, restored
   all 12 raw files to isolated ignored storage and reproduced A3
   `FIT_WITH_LIMITATIONS` with zero hard failures.
6. Source mutations and source deletions were both zero.

Machine receipt:
`docs/evidence/task18/content_addressed_backup_restore_receipt_v1.json`.

Private Drive object:
`https://drive.google.com/file/d/1msCdh2niGoh5wcGD7Ofiq9Dz9WBIFifn/view?usp=drivesdk`.

## Reconciliation

The immutable A3 receipt remains a truthful historical snapshot. This A3R
receipt supersedes only:

- `BACKUP_INVENTORY_NOT_OBSERVED`;
- `OVERWRITE_PREVENTION_NOT_PROVEN_BY_CURRENT_HASHES`;
- `RESTORE_TEST_NOT_OBSERVED`.

Replacement evidence:
`RECOVERABLE_CONTENT_ADDRESSED_SNAPSHOT_PROVEN`.

The evidence remains one member, three accepted windows and quote-only. It
does not establish cross-token generalization, provider reliability,
Fillable, RealizedVWAP, NetReturn, signal, strategy, alpha or production
readiness.

TASK-19 is not started or authorized by this repair. The next boundary is
`T18-A4_CATALOG_REPOSITORY_FINALIZATION_V1`.

## Side effects

Exactly one private Drive folder and one new ZIP were created. Drive file
updates, deletions, sharing changes and public links were zero. Provider,
API, RPC and WSS calls were zero; cash spend, provider credits,
wallet/signer/transaction actions, dependency changes, commit, push, PR and
merge were also zero.
