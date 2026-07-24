# Dataset manifest identity contract v1

Status: TASK-06 Atom 3 local candidate. This contract defines pure,
deterministic identity only. It performs no filesystem, Parquet, DuckDB,
Catalog, provider, API or RPC operation.

## 1. Purpose and boundary

`DatasetManifest` is the immutable root for one `(dataset_id,
dataset_version)`. `PartitionManifest` binds each logical Parquet partition to
its exact file bytes, logical row content, row count and point-in-time bounds.
The Pydantic models in `contracts/schema_v1.py` remain the field and type truth;
this contract finalizes how their IDs and hashes are derived.

The caller, not this module, must produce and validate Parquet bytes. It supplies:

- `file_sha256`: SHA-256 of the exact immutable Parquet file bytes;
- `content_sha256`: SHA-256 of the canonical logical rows before file-format
  encoding;
- exact row count and UTC bounds;
- SHA-256 of a separate sanitized validation receipt.

Claiming either content hash without measuring the named bytes is invalid
evidence.

## 2. Canonical encoding

All identity claims use UTF-8 JSON with lexicographically sorted object keys,
no insignificant whitespace and no ASCII escaping. Timestamps are normalized
to UTC and rendered with six fractional digits plus `Z`. Hashes are lowercase
64-character SHA-256 hex strings.

The versioned domain separators are:

- `smial-manifest-identity-v1`;
- `smial-dataset-fingerprint-v1`;
- `smial-dataset-manifest-content-v1`.

A profile change creates a new contract version; it never silently rewrites an
accepted manifest.

## 3. Acyclic identity chain

The derivation order is deliberately one-way:

1. `dataset_manifest_id = "dataset-" + SHA256(profile, dataset_id,
   dataset_version)`;
2. each `partition_manifest_id = "partition-" + SHA256(profile, parent
   dataset_manifest_id, partition identity and integrity fields)`;
3. `dataset_fingerprint = SHA256(profile, schema identity, ordered exact
   partition projections)`;
4. the independent validation receipt may bind the stable dataset identity,
   schema and dataset fingerprint, then its exact bytes are hashed;
5. `DatasetManifest.content_sha256 = SHA256(profile, all dataset-manifest
   fields except content_sha256 itself)`.

The validation receipt must not embed `DatasetManifest.content_sha256`. This
rule prevents a receipt-manifest hash cycle. The dataset ID is semantic and
stable for one immutable dataset version; a second, conflicting fingerprint
under the same ID is an integrity conflict, not a new revision.

## 4. Partition projection and ordering

The partition identity projection includes:

- parent dataset manifest ID and `partition_id`;
- repository-independent `logical_location`;
- exact file and logical-content hashes;
- row count;
- nullable event-time and strategy-availability bounds;
- `created_at` and `first_reliable_available_at`.

The dataset fingerprint includes every full partition projection plus its
derived partition manifest ID. Input order is irrelevant: partitions are
sorted by `(partition_id, logical_location, partition_manifest_id)` before
hashing. Duplicate partition IDs, manifest IDs or logical locations fail
closed.

An empty partition inventory is representable and receives a deterministic
fingerprint. It does not, by itself, prove a useful or accepted dataset.

## 5. Location and time controls

`logical_location` is a POSIX-style, dataset-relative `.parquet` name. Absolute
paths, drive prefixes, backslashes, URLs, query strings, fragments, empty
segments and `.` or `..` segments are forbidden.

All timestamps must be timezone-aware. Equivalent instants normalize to the
same identity. Nullable min/max pairs remain governed by the TASK-05 Pydantic
contract. `first_reliable_available_at` cannot predate `created_at`; it is
evidence availability, not a license to backdate row availability.
Partition creation cannot predate its maximum strategy-availability bound.
Dataset creation cannot predate any included partition's
`first_reliable_available_at`.

## 6. Verification and consumers

Builders immediately verify their own output. Independent consumers must:

1. verify every partition ID;
2. verify unique inventory and the expected parent dataset ID;
3. recompute the dataset fingerprint;
4. recompute the dataset manifest content hash;
5. separately verify the referenced validation receipt bytes and the Parquet
   file/content hashes when those bytes are available.

`canonical_manifest_bytes()` serializes the complete model, including its
stored hash field, for a future durable writer. The stored dataset
`content_sha256` is intentionally computed from the canonical preimage that
omits only itself.

## 7. Atom 3 non-goals

This atom does not write Parquet, read files to measure hashes, allocate
storage, update Catalog, create DuckDB projections, call providers, collect
data, add dependencies or authorize staging, commit or push.
