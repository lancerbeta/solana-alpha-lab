# TASK-21 final dataset recovery contract v1

## Decision

This atom proves that the complete physical TASK-21 dataset required by the A7
freeze can be reconstructed from a separate-failure-domain object. It combines
the accepted 32-file bounded checkpoint with the accepted 59-file R2/R3 final
cohort extension. Neither component may be inferred from a broad parent folder
or silently replaced by a newer run.

The exact full dataset identity is 13 source roots, 91 files, 1,263,895 stored
bytes and source-inventory SHA-256
`aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae`.
The old checkpoint must independently remain
`32 / 456813 / 64033b77...968c`; the extension must remain
`59 / 807082 / 49ecbd1a...a850`.

## Required proof

The recovery proof passes only when all of these hold:

1. Every protected tracked input matches its exact SHA-256.
2. Both component inventories and the combined inventory match before packing.
3. One deterministic content-addressed ZIP is created locally with exclusive
   create semantics; existing unequal bytes fail closed.
4. The exact Drive folder contains no object with the same filename before
   upload.
5. Upload creates one new private stored file; it performs no update, move,
   sharing change or deletion.
6. Drive metadata read-back confirms exact name, size and parent.
7. Raw-byte read-back matches local size, MD5 and SHA-256.
8. Those independently downloaded bytes restore into a new isolated directory;
   all 91 entries, stored-byte sum and inventory hash match.
9. A post-restore source inventory proves zero source mutation or deletion.

Local reconstruction from the local ZIP is a packaging check, not remote
recovery proof. The accepted remote proof must materialize the bytes returned
by Google Drive and restore that materialization.

## Safety and non-claims

Authority is limited to local create-only package/restore materialization and
at most eight Drive reads plus one new-file upload to folder
`1EISgmsB8nt2pkU4uBUO6Sav1Fzbo6Hw3`. Provider/API/RPC/WSS calls, provider
credits, cash, credential or permission changes, candidate admission,
collection, Catalog or Source mutation, commit, push, PR, merge,
wallet/signer/transaction actions, overwrite and deletion remain zero.

Passing this atom proves recoverability only. It does not open hypothesis
outcomes, freeze the dataset canonically, accept TASK-21, authorize TASK-22 or
establish trade, fill, position, PnL, NetReturn, alpha, market-wide or
cross-regime claims. Those decisions remain at the separate A7 boundary.
