---
adr_id: ADR-001
title: Project Asset Catalog baseline
status: ACCEPTED_FOR_FOUNDATION
as_of: 2026-07-21
owner_task: TASK-03
contains_secrets: false
---

# ADR-001 — Project Asset Catalog baseline

## Decision

Use versioned YAML records validated by JSON Schema Draft 2020-12, rooted at
`catalog/catalog_manifest.yaml`. Git remains the byte truth; specialized
registries remain lifecycle truth; the Catalog owns stable discovery,
locations, relations, access recipes, and validation evidence.

## Adopted components

| Component | Version | Decision | Purpose | License |
|---|---:|---|---|---|
| PyYAML | `6.0.3` | ADOPT | Parse repository-controlled YAML through `yaml.safe_load` only | MIT |
| jsonschema | `4.26.0` | ADOPT | Validate standalone Draft 2020-12 schemas and instances | MIT |

Versions are exact in `pyproject.toml` and `uv.lock`. No package is allowed
to resolve network references during Catalog validation.

## Safety model

- `yaml.safe_load`; never `yaml.load`.
- Standalone local JSON Schemas; no remote `$ref` resolution.
- Repository-relative paths only; Windows and POSIX absolute paths fail.
- Secrets and raw/canonical data bytes are forbidden in Catalog metadata.
- Query recipes are read-only, bounded, and declare network/write effects.
- Self-referential Catalog files do not contain their own hashes. They are
  bound by an accepted Git commit/tree and external receipt.
- SHA-256 is required for non-self-referential Git-file asset records.
- Missing mandatory outputs are `CATALOG_GAP`, not a Library search.

## Scope of Atom 3A

Implement only schemas, one core asset registry, one query registry, the
root resolver, CLI, validators, tests, and this ADR. Pre-Git TASK-01/02
import, generated project map/edges, lifecycle registries, remote/CI,
clean-clone evidence, and Codex pilot remain deferred.

## Graph database decision

Deferred. Stable ID edges plus deterministic validators are sufficient at
current scale. A graph database requires a measured-need ADR with query
workload, operational cost, failure modes, migration, and exit plan.

## Rejection log

- Custom YAML parser: rejected; no value over PyYAML and higher maintenance.
- Custom JSON Schema engine: rejected; `jsonschema` already implements the
  specification.
- Graph database: rejected for current scope; no measured bottleneck.
- Cataloging raw bytes: rejected; Catalog stores metadata and read recipes,
  not duplicated datasets.
