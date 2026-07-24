# Raw Parquet store contract v1

Status: TASK-06 Atom 4 local candidate. This contract implements the accepted
PyArrow adapter boundary; it does not create a production dataset or authorize
provider access.

## 1. Purpose and accepted reuse decision

The port persists already redacted and verified `RawApiEvent` rows as immutable
Parquet pieces. It follows the accepted TASK-04 direction:

- ADOPT Apache Parquet as the durable piece format;
- WRAP pinned PyArrow 25.0.0;
- BUILD only the thin project-owned `ParquetPort` because naming, PIT bounds,
  atomic publication and manifest identity are project truth.

The TASK-05 Pydantic models remain row and manifest truth. DuckDB remains a
rebuildable consumer and is not used by this write path.

## 2. Public operation

`write_raw_event_partition()` receives:

- an explicit existing absolute data root that is not a symlink;
- stable dataset/version and partition identities;
- one dataset-relative `.parquet` logical location;
- one or more verified `RawApiEvent` objects;
- explicit partition creation and first-reliable timestamps.

It returns a sanitized `RawParquetWriteResult` containing only the verified
`PartitionManifest`, file size and either `CREATED` or `REPLAY_IDENTICAL`.
Physical machine paths are not retained in the result or manifest.

`verify_raw_event_partition()` independently reads the file and verifies its
file hash, Arrow schema and metadata, canonical row order, strict row
contracts, logical content hash, row count and time bounds.
UTC read-back uses exact signed microseconds from the Unix epoch and stdlib
`timezone.utc`; it does not require an unpinned host timezone database.

## 3. Deterministic bytes and identities

Rows are sorted by `raw_event_id`; duplicate raw IDs or idempotency keys fail.
The Arrow schema has explicit string, binary, `int64` and UTC-microsecond
timestamp fields plus the profile `smial-raw-api-events-parquet-v1`.

The pinned writer uses:

- no compression;
- no dictionary encoding;
- Parquet format 2.6 and data page 1.0;
- stored Arrow schema and statistics;
- UTC timestamps coerced to microseconds without truncation.

`file_sha256` measures exact Parquet bytes. `content_sha256` separately measures
canonical sorted logical rows encoded as compact UTF-8 JSON; redacted bodies
are represented as lowercase hex. This distinction allows a future compatible
writer to change physical encoding without pretending logical content changed.

If any row lacks `event_time`, both partition event-time bounds are null rather
than presenting incomplete known values as full coverage. Strategy-availability
bounds always cover every row. The manifest layer rejects backdated partition
creation and reliability claims.

## 4. Atomic append-only publication

The complete Parquet file is encoded in memory before the filesystem is
modified. Publication then:

1. creates a temporary file in the exact destination directory;
2. writes, flushes and file-syncs all bytes;
3. creates the final name using a same-filesystem atomic hard link that fails
   if the destination already exists;
4. removes the temporary name;
5. performs full read-back verification.

An existing byte-identical file is an idempotent replay. An existing different
file is an immutable conflict and is never replaced. There is deliberately no
rename/replace fallback because it could clobber accepted evidence.

If the filesystem cannot provide atomic no-clobber linking, the operation fails
closed. A failed new publication removes its temporary file, any newly
published final file and empty logical directories created by that attempt.
Existing files are never removed by failure recovery.

This is atomic visibility and file-data flush, not a claim of power-loss-safe
directory metadata on every filesystem. Storage-level durability and backup
remain deployment concerns.

## 5. Path and security boundary

The data root exists before the operation and is supplied at runtime. Logical
locations inherit the manifest contract: relative POSIX-style `.parquet`
names, with no drive prefixes, URLs, backslashes, empty segments or traversal.
Every resolved parent must remain under the resolved data root. Root, parent
and final-file symlink escapes fail closed.

Only `RawApiEvent.redacted_body` crosses the durable boundary. Every row is
reverified by the Atom 2 redaction/integrity gate immediately before encoding
and again after read-back. Empty failure bodies, error states, revisions,
nullable event time and all four operational timestamps remain rows rather
than being dropped.

## 6. Atom 4 validation and non-goals

Tests use bounded temporary directories only and remove them automatically.
They cover deterministic bytes, reversed input, exact round-trip,
byte-identical replay, conflicting overwrite denial, tamper detection,
temporary-file cleanup, empty/duplicate rejection, nullable event-time bounds
and path containment.

Atom 4 does not:

- write a permanent project dataset;
- publish dataset-manifest or validation-receipt files;
- update Catalog or generated navigation;
- enforce storage budgets, retention, backup or disk alerts;
- use DuckDB;
- add or change dependencies;
- stage, commit or push;
- call a provider, API, RPC, wallet, signer or transaction path.
