# TASK-21 checkpoint remote recovery contract v1.0

`T21-A7R_CHECKPOINT_REMOTE_READBACK_AND_RESTORE_V1` binds the exact bounded
TASK-21 checkpoint produced by A7A to an independently stored Google Drive
object and a deterministic isolated restore proof. It closes only
`REMOTE_RECOVERY_PENDING`; it does not freeze a research-grade dataset.

## Exact object and acceptance

The only accepted archive is:

```text
TASK21_BOUNDED_PANEL_CHECKPOINT_v1_57b7dc01a247ec3dde7ac05d3380824b73db5f1ebb6148f5be34264741427f00.zip
```

Its expected identity is 476,814 bytes and SHA-256
`57b7dc01a247ec3dde7ac05d3380824b73db5f1ebb6148f5be34264741427f00`.
The destination is the existing TASK-21 recovery folder
`1EISgmsB8nt2pkU4uBUO6Sav1Fzbo6Hw3` in the already connected owner account.

Acceptance requires all of the following:

- the exact name is absent before upload;
- upload creates one new file and does not update an existing object;
- Drive metadata matches name, MIME type, size and parent folder;
- a complete raw read-back has the expected byte count and SHA-256;
- the content-equal local archive restores under a new isolated create-only
  root, proving the same bytes recover 32 files, 456,813 stored bytes and
  inventory SHA-256
  `64033b77e4fc8b797600a7083a6681db88a7a21b5950541785dd13c7767e968c`;
- the original checkpoint sources remain unchanged and no source is deleted.

The restore proof uses the already accepted project method
`DRIVE_RAW_BYTE_IDENTITY_PLUS_DETERMINISTIC_LOCAL_RESTORE`: an exact SHA-256
and size match binds the remote raw bytes to the local content-addressed
archive passed to the deterministic restore verifier.

## Boundary after PASS

A7R changes the checkpoint recovery state to `REMOTE_RECOVERY_PROVEN` while
the dataset disposition remains `EXTEND_EVIDENCE`. It does not establish
`DATASET_READY`, TASK-22 eligibility, sufficient members/panels/market states,
fills, positions, PnL or alpha. Catalog, canonical Sources and the Product
Vision terminal result remain pending final TASK-21 A7.

The next material atom is
`T21-A6S_INFORMATION_SUFFICIENCY_REBASE_V1`, which must choose bounded new
information, a narrower explicit estimand, or a justified stop/redesign.
Automatic H72/H168 collection is not implied.

## Authority and non-actions

This atom permits one create-only Drive upload of the exact archive, bounded
Drive reads needed for collision, account, metadata and raw-byte verification,
and one local create-only isolated restore. It permits no overwrite, deletion,
sharing change, provider/API/RPC/WSS call, cash spend, credential change,
deployment, scheduler/background process, candidate admission, collection,
wallet/signer/transaction action, Git transport, merge, Catalog finalization,
Source mutation or Project UI change.
