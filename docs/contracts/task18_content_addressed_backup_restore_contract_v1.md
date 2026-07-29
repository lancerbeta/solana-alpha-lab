---
contract_id: CONTRACT-T18-CONTENT-ADDRESSED-BACKUP-RESTORE-001
contract_version: "1.0"
task_id: TASK-18
atom_id: T18-A3R_CONTENT_ADDRESSED_BACKUP_RESTORE_PROOF_V1
status: FROZEN_REPAIR_CONTRACT
as_of: "2026-07-29"
contains_raw_data: true
contains_secrets: false
---

# TASK-18 content-addressed backup and restore contract v1

## Purpose

Close the three durability limitations from the accepted A3 quality audit
without changing the 12 source files or weakening its fail-closed checks.

The repair creates one deterministic ZIP snapshot, uploads it once to a private
Google Drive folder, reads the stored file back, restores it to an isolated
local directory and reruns the TASK-18 auditor against restored bytes.

## Frozen inputs

- A2 quality contract SHA-256:
  `1842df2ef349d9506ff612c3faf3c943a1a218f6c6a7e266c5af5f0f5578b3a6`;
- A3 quality audit SHA-256:
  `52a4585364930ca4a62e12a06cf196af14309f34ab3d46c75f2c00a168e40403`;
- raw inventory: exact 12 files, 32 JSONL rows and 179,208 bytes from the
  A2 contract;
- accepted A3 verdict: `FIT_WITH_LIMITATIONS`.

No source raw file may be edited, moved, renamed or deleted.

## Deterministic archive

The archive contains:

1. `BACKUP_MANIFEST.json`;
2. the 12 frozen raw files under their repository-relative paths.

Entries are sorted, stored without compression, use a fixed ZIP timestamp and
fixed file mode. The manifest contains only relative paths, exact byte counts,
SHA-256 values and the hashes of its frozen tracked inputs.

The output filename is:

```text
TASK18_RAW_BACKUP_v1_<full archive SHA-256>.zip
```

The local output and restore directories live under ignored `local/` storage.
They are not Git candidates.

## Google Drive boundary

Create or reuse the private folder:

```text
Solana Alpha Lab — Content-Addressed Backups
```

Upload one new non-native ZIP. Do not replace an existing Drive file, change
sharing, create a public link or move unrelated items. Record only observed
folder/file IDs, URL, name, size, MIME type, checksum metadata and read-back
hashes.

## Restore proof

The Drive read-back must:

- return the same complete ZIP bytes;
- match archive size, SHA-256 and MD5;
- expose the exact expected entry set;
- restore all 12 raw files with exact hashes and sizes;
- combine them only with the Git-tracked A2 inputs;
- reproduce the A3 coverage and hard-check result;
- perform no source mutation.

If any step fails, retain A3 `FIT_WITH_LIMITATIONS` and stop before A4.

If every step passes, the repair reconciliation may supersede:

- `BACKUP_INVENTORY_NOT_OBSERVED`;
- `RESTORE_TEST_NOT_OBSERVED`;
- `OVERWRITE_PREVENTION_NOT_PROVEN_BY_CURRENT_HASHES`;

with `RECOVERABLE_CONTENT_ADDRESSED_SNAPSHOT_PROVEN`, yielding
`FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND`.

## Authority

Authorized:

- bounded local archive/restore writes under ignored `local/`;
- tracked repair contract, code, tests and sanitized receipts;
- one private Google Drive folder creation if absent;
- one ZIP upload plus metadata and raw-byte read-back.

Not authorized:

- provider/API/RPC/WSS calls;
- source raw mutation or deletion;
- credentials, sharing changes, public links or Drive cleanup;
- dependency changes, purchases, deployment, wallet, signer or transactions;
- commit, push, PR or merge.

The next atom remains `T18-A4_CATALOG_REPOSITORY_FINALIZATION_V1` only after
the exact repair receipt passes.
