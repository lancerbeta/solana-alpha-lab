---
contract_id: CONTRACT-T21-RUNTIME-RECOVERY-GATE-001
contract_version: "1.0"
task_id: TASK-21
atom_id: T21-A3_PRE_COLLECTION_RUNTIME_RECOVERY_GATE_V1
status: FROZEN_RUNTIME_RECOVERY_GATE_CONTRACT
as_of: "2026-07-30"
---

# TASK-21 pre-collection runtime recovery gate v1

## Decision

Before any TASK-21 forward byte may be written, one non-secret deterministic
probe must traverse the same remote failure-domain boundary required for future
immutable partitions:

```text
LOCAL_CREATE_ONLY_BYTES
→ PRIVATE_GOOGLE_DRIVE_OBJECT
→ EXACT_RAW_READBACK
→ ISOLATED_EMPTY_RESTORE_ROOT
→ EXECUTABLE_HEALTH_STATE
```

This atom proves the adapter path and the fail-closed health guard. It does not
claim that a future dataset is already backed up, that a scheduler is running,
or that full-dataset recovery has been proven.

## Frozen object and destination

The only uploaded object is the 560-byte non-secret fixture
`tests/fixtures/task21/runtime_recovery_probe_v1.json`, SHA-256
`1a6619d928f426d2b8ffdedc192db67ef0be1ea99c0a9f38b0e66f977f833425`.
Its Drive filename is the exact content-addressed name:

```text
TASK21_RUNTIME_RECOVERY_PROBE_v1_1a6619d928f426d2b8ffdedc192db67ef0be1ea99c0a9f38b0e66f977f833425.json
```

The connector must first establish that the exact root folder
`SOLANA_ALPHA_LAB_TASK21_RECOVERY_V1` is absent. It may then create exactly one
folder and exactly one new file. A collision, update, overwrite, sharing
change, deletion, second upload, or second folder fails closed.

`shared=false` on both folder and file is required. A connector-observed
private `webViewLink` is an object locator, not a public-share claim.

## Exact read-back and isolated restore

Drive metadata must match the expected name, byte count, MIME type and parent.
The stored non-native file must then be fetched as raw bytes. Acceptance
requires SHA-256 and byte count to match the local source exactly.

The fetched bytes are restored under the ignored, empty logical root
`local/task21_recovery/isolated_restore`. Restore is create-only, validates the
probe schema and all zero-authority fields, and records zero source mutation
and zero source deletion.

## Health and alerts

The executable guard inherits `RETENTION-RECOVERY-T20-001`:

- backup target: 24 hours;
- `BACKUP_OVERDUE`: more than 26 hours since the last successful backup;
- new T2 admissions stop after 48 additional overdue hours, at total backup
  age of 74 hours;
- routine sample restore cadence: P7D; older evidence is
  `RESTORE_OVERDUE`;
- failed exact read-back or restore is `EVIDENCE_AT_RISK`;
- byte conflict and storage hard stop remain immediate fail-closed states.

Tests must prove each state emits its owner-facing alert and control effect.
The current gate passes only in `HEALTHY`.

## Acceptance and non-claims

`PASS` requires all six A2 evidence classes:

1. `PRIVATE_SEPARATE_FAILURE_DOMAIN_DESTINATION`;
2. `CREATE_ONLY_CONTENT_ADDRESSED_BACKUP`;
3. `EXACT_REMOTE_READBACK`;
4. `ISOLATED_SAMPLE_RESTORE`;
5. `BACKUP_AND_RESTORE_HEALTH_ALERTS`;
6. `NO_SECRET_MATERIAL_IN_EVIDENCE`.

The receipt is
`docs/evidence/task21/runtime_recovery_gate_receipt_v1.json`.
Catalog registration remains a single TASK-21 A7 transaction.

Authority is exactly `LOCAL_WRITE_PLUS_GOOGLE_DRIVE_WRITE` from the user's
approval. Provider/API/RPC/WSS calls, candidate admissions, collector
execution, forward raw/dataset writes, purchase, credits, dependency changes,
wallet/signer/transaction actions, commit, push, PR, merge, sharing changes,
updates, deletion and destructive cleanup are all zero or false.

The next unapproved boundary is
`T21-A4_THIN_COLLECTOR_AND_OFFLINE_DRY_RUN_V1`.
