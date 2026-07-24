# Storage budget contract v1

Status: TASK-06 Atom 5 local candidate. This contract adds a fail-closed
logical and physical storage guard around the accepted immutable Parquet port.
It does not select production limits, create a dataset or authorize provider
access.

## 1. Boundary and policy ownership

Production storage uses `write_budgeted_raw_event_partition()`. The caller must
supply an explicit `StorageBudgetPolicy` with:

- maximum bytes for one Parquet piece;
- maximum bytes for the complete logical dataset root;
- minimum filesystem free-space reserve after the write;
- a dataset-utilization warning threshold in integer basis points;
- a bounded same-size partition count for forward growth alerts.

There is no implicit unlimited policy and no project-chosen production cap.
The user or a later deployment contract owns concrete capacity and cash
limits. Integer bytes and basis points avoid float-dependent decisions.

`write_raw_event_partition()` remains the lower-level deterministic Parquet
primitive used by isolated adapter tests. Runtime ingestion must use the
budgeted operation; retaining the primitive does not authorize bypassing the
guard.

## 2. Inventory truth

The gate derives the dataset root from the first segment of the already
validated dataset-relative Parquet location. It recursively inventories only
regular `.parquet` files below that root and sums exact filesystem byte sizes.

The measurement fails closed on:

- root, dataset or descendant symlinks;
- an unreadable directory or file;
- non-regular entries;
- unexpected non-Parquet files, including stale temporary files;
- a target whose existing size or SHA-256 differs from the incoming bytes;
- a path that resolves outside the explicit data root.

An absent dataset root means zero existing pieces. A byte-identical target is
an idempotent replay with zero incremental bytes, so it is not charged twice.
The complete dataset total still includes that existing piece.

## 3. Hard stops and warning forecast

Before publication the gate rejects:

- an incoming piece above `max_partition_bytes`;
- a projected dataset total above `max_dataset_bytes`;
- a write that would leave less than `min_free_bytes` on the filesystem.

An allowed write returns a sanitized `StorageBudgetSnapshot` with counts,
logical dataset name, current and projected bytes, integer utilization,
remaining capacity, free-space measurements and alerts. It contains no
physical path.

`WARNING` is returned, without blocking the current in-budget write, when:

- dataset utilization reaches the configured basis-point threshold;
- the configured count of same-size future pieces would exceed the dataset
  cap;
- that same forecast would cross the filesystem reserve.

The forecast is an intentionally simple sentinel, not a statistical estimate.
Its purpose is to trigger operator review before a hard stop. It does not claim
future traffic, compression ratio or provider cadence.

## 4. Atomic integration and concurrency

The budgeted writer:

1. prepares exact deterministic Parquet bytes and manifest in memory;
2. runs the budget/inventory gate before creating destination directories;
3. performs the existing atomic no-clobber publication and full read-back;
4. measures the accepted inventory again;
5. rolls back only its newly created piece if the post-publication gate fails.

The second check closes the common two-writer race where both observed the same
initial capacity and one pushes the total over budget. The immutable hard-link
publication remains the overwrite boundary.

This is not a distributed quota service. Correct deployment still requires one
writer/coordinator per dataset root; an unrelated process can consume disk or
publish after the final snapshot. The snapshot is measurement evidence, not a
reservation.

## 5. Validation and non-goals

Atom 5 tests use temporary directories and mocked free-space measurements.
They cover policy validation, allowed writes, replay accounting, partition and
dataset hard stops, physical reserve, warning forecasts, unexpected inventory,
conflicting targets, pre-write zero effect and post-write rollback.

Atom 5 does not:

- choose production byte limits or retention periods;
- persist metrics, alerts, manifests or receipts;
- implement backup, deletion, compaction or a distributed lock;
- write a permanent project dataset;
- update Catalog or generated navigation;
- stage, commit or push;
- change dependencies;
- call a provider, API, RPC, wallet, signer or transaction path.
