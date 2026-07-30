# TASK-20 coverage, retention, and recovery policy v1

Status: `FROZEN_POLICY_NO_COLLECTION`

Policy identity: `RETENTION-RECOVERY-T20-001` version `1.0`

Atom: `T20-A3_COVERAGE_RETENTION_AND_RECOVERY_POLICY_V1`

## Decision

The frozen TASK-20 collection specification now has an exhaustive, field-level
coverage matrix for its current version and a bounded retention, backup, and
restore policy. This atom writes policy only. It does not collect data, execute
a backup or restore, select a provider, build a collector, or authorize any
external call.

The policy closes the A2 recovery handoff without turning the lab into a
market-wide recorder. Every included field has a named consumer and a stated
decision impact. Any future field requires a new collection-spec version; it
cannot arrive through an undocumented runtime payload.

## Coverage boundary

The matrix contains exactly 40 fields:

- 17 T0 fields form a thin append-only decision ledger for candidates actually
  evaluated by a named hypothesis.
- 11 T1 fields cover reusable historical minute bars and lifecycle evidence
  hydrated on demand. `PT1M` remains a candidate cadence for a named intraday
  consumer, not a global collection cadence.
- 12 T2 fields cover a triggered live quote only for
  `HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1`, exact watchlist membership,
  and a separately authorized external atom.

The matrix is exhaustive only for `COLLECTION-SPEC-T20-001` version `1.0`.
It neither claims universal Solana coverage nor grants authority to capture all
tokens or all ticks.

Every field binds description, units, natural keys, tier, named consumers,
source/version, decision impact, event/observed/ingested/first-available
semantics, availability class, cadence, retention, revision, quality,
freshness, missingness, and physical cost attribution.

## Retention

Decision lineage and backup receipts are project-lifetime, append-only
evidence. Unique raw evidence has no automatic expiry. It remains until the
hypothesis is retired, all dependent datasets, holdouts, replays, and audits
have released it, a current full restore proof exists, and the owner makes a
separate deletion decision.

Reconstructible content cache may be evicted only when all of these are proven:
the source remains reconstructible, the bytes contain no unique
first-availability evidence, no active named consumer depends on them, a
deterministic cache manifest exists, and separate destructive authority is
granted. A3 itself authorizes no deletion.

Derived datasets remain through their dependent trial, holdout, replay, and
audit lifecycle. Storage pressure never silently weakens evidence retention.
It enters an explicit degraded state and stops new capture when the storage
budget guard rejects the next write.

## Immutable storage and no-clobber

Primary evidence is create-only and content-addressed by the SHA-256 of exact
bytes plus a typed manifest. The same identity with the same bytes is
idempotent. The same semantic identity with different bytes is
`EVIDENCE_CONFLICT`: writes to the affected dataset stop, all conflicting bytes
are preserved, and owner reconciliation is required.

Accepted evidence is never overwritten through a mutable alias. Remote backup
objects are also create-only and hash-named. An existing object may be
deduplicated only after exact remote byte readback proves the same SHA-256.
Successful backup does not authorize deletion of source bytes.

## Backup cadence and degraded operation

Each closed immutable partition must be backed up immediately, or within 24
hours at the latest, whichever occurs first. Every backup requires raw-byte
readback, SHA-256 and typed-manifest agreement, destination identity, and a
timestamp.

At 26 hours since the last successful backup, health becomes
`BACKUP_OVERDUE`. Dataset freeze, promotion, and deletion are blocked, and the
owner escalation deadline is two hours. If the overdue condition lasts 48
hours, new T2 admissions stop. Existing active capture may continue only while
primary storage and integrity remain healthy; this avoids manufacturing a
research gap merely because the remote failure domain is temporarily
unavailable. It does not permit widening the population.

A failed backup or lost redundancy enters `EVIDENCE_AT_RISK` and disables new
T2 admissions. A primary identity/hash conflict enters `EVIDENCE_CONFLICT`.
A storage-budget rejection enters `STORAGE_HARD_STOP`.

## Restore proof

Every backup proves its own object through exact readback. Once per seven days,
an isolated empty restore root must receive a deterministic sample from
content-address-sorted partitions: first, last, and
`manifest_sha256 mod partition_count`, with duplicate indexes removed; all
partitions are selected when fewer than three exist.

The weekly sample proves sampled-object persistence only. It does not prove
full dataset recoverability. A full isolated restore is mandatory before
dataset freeze or promotion, and after a backup/restore incident, policy
change, or runtime change. Only restoration of every manifest object with all
raw hashes, manifest identity, and dataset invariants matching may emit
`DATASET_RECOVERY_PROVEN`.

## Owner pulse

The operating view must expose the last closed partition, last successful
backup and hash, backup age/readback state, restore-proof age and scope,
consecutive failures, local bytes and free disk, active T2 memberships,
requests/credits/response bytes against physical caps, field coverage,
missingness, freshness, and any evidence conflict.

Allowed health states are `HEALTHY`, `BACKUP_OVERDUE`, `RESTORE_OVERDUE`,
`EVIDENCE_AT_RISK`, `EVIDENCE_CONFLICT`, and `STORAGE_HARD_STOP`.

## Authority and non-claims

Authority is `LOCAL_WRITE_ONLY` for the four A3 files. Network, provider,
API/RPC/WSS, Google Drive, credential, collector, raw/dataset, backup, restore,
wallet, signer, transaction, spend, dependency, commit, push, PR, merge, UI,
and destructive actions are all zero or false.

Google Drive remains one possible private separate-failure-domain adapter, not
a hardcoded destination. Adapter choice remains an `ADOPT` or `WRAP` decision
at the external execution boundary.

Catalog registration and task-level acceptance remain pending
`T20-A4_DETERMINISTIC_ACCEPTANCE_CATALOG_AND_FACTORY_FIT_V1`.
