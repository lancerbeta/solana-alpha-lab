# FACTORY HOT90 leftover full-RDP ZIP cleanup preconditions (prepare only)

Status: `PREPARED_NOT_EXECUTED`
As of: `2026-09-05`
This is not a delete grant. Do **not** execute this document after IMPL merge.
The existing same-volume `BACKUP_*.zip` (~11.1 GiB) must remain untouched until
a later exact destructive owner gate identifies the exact path/hash/size on the
VPS. This file does not name a host path.

90d age eviction is a separate lifecycle behavior. It is not permission to
mass-delete current data or to bundle historical deletion with this ZIP.

## Later cleanup gate must prove before delete

- new mutable-only backup is verified and restorable;
- immutable closed data is covered by a verified cold archive
  (`local SHA256 == remote content SHA256`);
- no full-RDP local backup producer remains active
  (`activation_stage` is `DURABILITY_CUTOVER` or later, and
  `includes_full_observation_rdp` is false);
- exact old ZIP path/hash/size is identified;
- deletion affects only that approved artifact;
- post-delete disk readback exists;
- collector / science / backup remain coherent.

## Non-goals

- no wildcard or parent recursive delete;
- no SQLite live compaction;
- no HOT 90d scientific eviction;
- no Drive write from this document.
