# HFIC_CENSORING_CANONICAL_BINDING_V1 — Owner readout

Date: 2026-09-17 · Route: DIRECT_CURSOR_DELIVERY

## What landed

A fail-closed canonical-input gate for
`CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001`. Canonical Block A X300
`typed_value` read is allowed only after lineage, DatasetManifest,
PartitionManifest, streaming SHA-256, and row `release_id`/`cohort_id` match
the frozen spec pins.

This merge is the gate, not a live frozen-cohort scientific result. It did
**not** add parquet `dataset_id` or `scientific_context_session`, did **not**
rewrite release bytes, and did **not** run the real 148-vs-327 diagnostic.

## Frozen durable pins

These live in `configs/hfic_censoring_ignorability_diagnostic_v1.yaml`:

- dataset: `DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001`
- cohort: `REL-20260902T111900Z-20260909T111900Z`
- release: `633a57088a5eb16dcc75a56aa2eb2521bbc76d1874aeb75aceb1ecc795bf1154`
- census SHA-256: `cfa7d8404dc5400c4e223c4d5303193ad2209f92cac3af2d61862e384ebfd5bf`
- observations SHA-256: `7b26425c69cc95baf8a9e0b9ea506de1042b98b83d48a2dae07f5a33a7d66d7d`
- session provenance: `HFIC-SESS-560C4E1A72B4F9E6` (spec/receipt only, and only
  when the bound file hashes equal those pins)

`dataset_manifest_id` and PartitionManifest ids are runtime provenance. They
are resolved and reported, not frozen.

## Modes

Canonical imported LIVE CORPUS `data_root` must contain
`datasets/live_lifecycle_corpus/lineage.json`. Do not pass Observation RDP.
There is no RDP default.

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <LIVE_CORPUS_data_root> censoring-ignorability-diagnostic
```

`--data-root` is a parent flag. Bind PASS permits
`CANONICAL_COMPARABLE_X_SUBSET` plus the existing scientific terminal. Bind
FAIL is a typed `CANONICAL_*` token and does not fall back to parquet paths.
Empty invocation fails as `CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED`.

Explicit census/observations paths remain
`SYNTHETIC_OR_NONCANONICAL_POPULATION` even if their bytes accidentally equal
canonical pins:

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py censoring-ignorability-diagnostic --census <path> --observations <path>
```

Mixing `--data-root` with `--census`/`--observations` fails as
`CANONICAL_MODE_EXPLICIT_PATH_CONFLICT`.

## What this does not mean

A green merge here is not a scientific result. MAR, ignorability,
identifiability, alpha and canonical DONE remain unproven. The next intended
action is a separately bounded read-only canonical diagnostic run against an
imported LIVE CORPUS `data_root`.
