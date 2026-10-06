# ResearchStore prepared write lookup V1

Owner: `MODULE-FACTORY-V1-RESEARCH-STORE-001`. Task:
`OPPORTUNITY_EPISODES_BOUNDED_OPERABILITY_V1`. Optional derived artifact:
`research/write_lookup_v1`. Canonical truth remains the manifest-last
ResearchEvent Parquet partitions. The artifact contains identities and exact
canonical pointers, never scientific values or a second research ledger.

The frozen-base falsifier uses the real public tick, complete physical HTTP/
clock overrides, real publication, lease and filesystem reads. Its normal tick
opened 30/190/670 canonical partitions at 0/32/128 irrelevant transactions.
An analytical DuckDB projection has different authority and refresh semantics;
a process cache disappears at oneshot restart. WRAP ResearchStore and BUILD
only this derived pointer trie; no dependency, engine, DB or service is added.

Explicit preparation takes the writer lease, bypasses packet snapshot caches,
reads every current manifest and verifies every partition, transaction and
global record identity. It writes the final content-addressed trie nodes and
publishes a self-hashed root only after a stable canonical namespace stamp.
Preparation is O(history), separately measured, and never happens implicitly
inside a normal tick, startup or deploy. The CLI requires an existing absolute
root and exactly one mode: `--isolated-copy` for a measured rehearsal, or
`--production-commissioning` directly on the canonical root under separately
approved OPERATE authority. Production mode requires `--operate-authority-ref`,
`--verified-backup-sha256`, `--copy-rehearsal-sha256`, `--quiesced-writers` and
`--ops-store` naming the exact existing producer OPS database. These are operator
attestations/references, not a new authority grant or independent backup verifier.
The owner must verify backup, measured copy rehearsal and writer/timer quiescence
before this command. Do not point it at an unrelated OPS database.

Production mode acquires the existing global OPS lease and holds an OPS write
transaction through the full audit, then takes the ResearchStore writer lease.
A competing OPS writer cannot acquire the lease even after its ordinary TTL;
a competing canonical writer is refused by ResearchStore. Both fences release
after preparation/refusal. No schema, lease TTL or timer settings change.
Copy preparation remains supported. The lookup binds filesystem identity/stat:
never copy its prepared artifact onto production. Prepare production explicitly
in place, then the ordinary writer uses it. A moved/restored root needs its own
explicit preparation before returning to the new writer.

Transactions and records use persistent SHA256 radix tries, leaf limit 16,
node limit 64KiB. A lookup verifies hashes on its bounded route; a hit loads
the named canonical manifest and verifies its exact Parquet/content hashes,
schema, rows and IDs. Replay compares proposed bytes with that canonical
transaction; conflicts and duplicate record IDs are refused. Lifecycle proof
can request only this schedule's state-event pointers. Scientific/full legacy
readers retain their canonical inventory and integrity checks.

Per append: writer fencing, current source namespace binding, authenticated
lookup route, global identity exclusion, proposed canonical serialization and
the involved canonical transaction/partition. Full audit: arbitrary historical
payload/manifest corruption and whole-store inventory validation. The old
implementation happened to read unrelated history while checking identity;
this was not an independent guarantee of instant detection of every historical
byte on every append. V1 does not make that guarantee. In-place historical
corruption is detected on a hit or full audit, not necessarily on an unrelated
append. No PIT field, scientific reader or admissibility gate is weakened.

The root's directory stat stamp binds a preparation to ordinary append-only
namespace operations on this filesystem. It is a local operational fence, not
cryptographic proof against an attacker who can forge files and filesystem
metadata. Source directories must preserve ordinary rename/create stat
semantics. Network filesystems, timestamp restoration and a copied root require
an explicit audit/repreparation. SHA256 here proves integrity against
accidental corruption, not secret-key authentication.

Write/recovery order:

1. Verify/stage and publish immutable Parquet; no manifest means no visibility.
2. Write immutable derived nodes, then fsynced pending prior/next roots naming
   one exact transaction; only then publish its immutable canonical manifest.
3. Record the published namespace stamp durably, then atomically publish the
   root and remove pending. Lookup files and their immediate parent directory
   are fsynced on Linux. Canonical manifest/Parquet directory entries and newly
   created ancestor directories do not have a proven power-loss durability
   guarantee here. Windows tests establish process-crash behavior; Linux
   power-loss durability remains UNVERIFIED.

Pending before manifest: a fenced writer verifies the unchanged source stamp
and restores the prior root. Pending after durable published stamp: it verifies
the exact canonical partition and installs the next root. A crash between
manifest and stamp is `WRITE_LOOKUP_PENDING_RECONCILIATION_REQUIRED`, with all
canonical bytes readable. Preserve those bytes and first verify a measured copy.
Returning the canonical writer requires explicit in-place full audit/repreparation
with `--production-commissioning`, separate OPERATE authority, verified backup,
measured copy rehearsal and quiesced writers/timer, under both existing fences.
A copy-prepared lookup cannot transfer to production. Repreparation repairs only
the lookup; it does not rebind an immutable activation storage envelope. No guess,
hidden scan, retry/provider send or false absence occurs.
Missing/stale/corrupt prepared state, nodes or pointer shapes refuse with typed
`WRITE_LOOKUP_*` errors. Absence of the entire artifact means uncommissioned
legacy mode with the original full verification cost.

Rollback does not delete the artifact or evidence. The actual frozen-base
writer can append and read canonical records while ignoring it. Its namespace
change invalidates the new writer's preparation; return to new code requires
explicit full audit/repreparation. Moving/restoring a root also requires this
operation before new writes; read-only canonical replay needs no index.
Nodes are immutable and obsolete nodes are retained; the physical model must
include their growth. There is no eviction or destructive cleanup in V1.
Commissioning WATCH records node-file count, bytes and inode growth. This is an
explicit measurement, never an extra inventory in a normal tick; no optimization
or retention policy follows without measured evidence.
