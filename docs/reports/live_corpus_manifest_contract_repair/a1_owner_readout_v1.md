# LIVE_CORPUS_MANIFEST_CONTRACT_REPAIR_V1 — Owner readout

Date: 2026-09-17 · Route: DIRECT_CURSOR_DELIVERY

## What landed

LIVE CORPUS metadata publication now goes through TASK-06
`build_partition_manifest` / `build_dataset_manifest` and verifiers. The
current scientific composition can be republished as a canonical metadata
root without rewriting census/observations parquet or sealed release bytes.
Future `import-live` emits the same TASK-06-valid cumulative root.

This merge is the mechanism. It did **not** mutate
`local/factory_v1/data_plane`.

## How to republish after merge

Separate OPERATE action, not this atom:

```
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py repair-live-corpus-manifests --data-root local/factory_v1/data_plane
```

CLI `status` `PASS` carries operational `result.status` `REPAIRED` or
`IDEMPOTENT_REPAIR`. That means the metadata root is published. It is not
parquet proof and not a scientific DONE.

If `import-live` was blocked with `CURRENT_CORPUS_LEGACY_METADATA_REQUIRES_REPAIR`
(`next` = `REPAIR_LIVE_CORPUS_METADATA_FIRST`), paste the exact same
`import-live` command after repair. If repair itself is interrupted or
`.published` is missing/corrupt, rerun the same repair command.
`DATASET_PUBLICATION_INCOMPLETE` uses the same repair next.
`LIVE_CORPUS_PARQUET_SYMLINK` / `CORPUS_PARQUET_SHA_MISMATCH` are stop codes,
not a second repair loop.

Then retry the canonical censoring diagnostic. Do not run Forge
between this merge and that retry merely because Git catalog hashes moved
the evidence epoch.

## What this does not mean

A green merge here is not a scientific result. MAR, ignorability,
identifiability, alpha and canonical DONE remain unproven. Historical
malformed manifests stay on disk as superseded provenance.

## Evidence epoch (read-only)

HFIC `evidence_epoch` with the current local data_plane, measured on this
implementation candidate, is
`061ded4e08255ad7897864c8f69713cab198d591e93f720c6d1f461a6e334e4b`.
The only `_EPOCH_FILES` byte change versus `4ff632e0` is
`catalog/catalog_manifest.yaml`. Treat that as Git semantic/capability
metadata, not new market evidence, and do not run Forge because of it.
After the later OPERATE metadata republish, expect another explicit epoch
change from the new `dataset_manifest_id` / `dataset_fingerprint`.
