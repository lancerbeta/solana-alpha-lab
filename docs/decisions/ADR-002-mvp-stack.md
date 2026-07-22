---
adr_id: ADR-002
title: Bounded MVP stack and reuse boundaries
status: IMPLEMENTED_UNVERIFIED
owner_task: TASK-04
as_of: 2026-07-22
based_on_repository_commit: f8ff483dbcf00454852a9638466eb4123e2c5809
prototype_gate: CLOSED_PASS
contains_secrets: false
---

# ADR-002 — Bounded MVP stack and reuse boundaries

> Staged architecture candidate. Work/control plane retains canonical acceptance and task status; this ADR grants no provider, signer, commit, push, deployment, or spend authority.

## 1. Naming patch

The TASK-04 contract asks for `ADR-001-mvp-stack.md`, but the accepted repository already contains
`ADR-001-project-asset-catalog-baseline.md` with `adr_id: ADR-001`. Reusing ADR-001 would corrupt
decision identity. The correct future repository artifact is therefore:

```text
docs/decisions/ADR-002-mvp-stack.md
asset_id: ADR-MVP-STACK-002
```

Atom 5 must patch the TASK-04 repository/control references accordingly.

## 2. Context

TASK-03 established the private repository, exact CPython/uv baseline, CI/security controls, Project
Asset Catalog and empty typed registries at accepted commit `f8ff483dbcf00454852a9638466eb4123e2c5809`. TASK-04 must freeze the
minimum shared MVP spine before TASK-05 schema implementation. The decision optimizes PIT/replay,
operator simplicity, low cash cost and reversible adapters—not tool count or novelty.

`ARCH-INTENT-001` remains direction only: the data spine and orchestration foundation support a future
hypothesis factory, but no bot, provider runtime, strategy or signer is implemented by this ADR.

## 3. Decision

Adopt a single-host, replay-first architecture:

```text
CPython 3.13.14 + uv 0.11.29 + uv.lock
→ solana-py adapter + solders types
→ exact external Pump/PumpSwap source snapshot + pure project decoder
→ immutable Parquet dataset pieces + versioned manifests via PyArrow adapter
→ rebuildable embedded DuckDB projection under a single-writer coordinator
→ JSON Schema 2020-12 + Pydantic v2 + tracked DuckDB DDL
→ thin repository-local migration ledger
→ Docker Compose + thin local coordinator/retry policy
→ stdlib structured logs + Prometheus-compatible metrics
→ golden fixtures + deterministic replay/receipt profile
→ guarded pip-audit + validated preview CycloneDX SBOM receipt
```

No candidate is forked. `FORK` count is zero because no evidence justifies taking ownership of a
third-party divergence.

## 4. Primary decisions by area

| Area | Accepted direction | State before prototype |
|---|---|---|
| Runtime/dependencies | Retain CPython 3.13.14, uv 0.11.29, uv.lock and disposable uv-managed `.venv` | ACCEPTED |
| Solana ingestion | Wrap solana-py 0.40.1 and solders 0.28.0 behind read-only adapters | CONDITIONAL_ACCEPT |
| Pump/PumpSwap decoding | External exact source snapshot + project-owned pure strict decoder | CONDITIONAL / BUILD |
| Raw storage | Immutable Parquet pieces + manifest; PyArrow behind ParquetPort | PROTOTYPE_GATE |
| Analytical query | Embedded persistent DuckDB, one writer, deny extension auto-load/install | PROTOTYPE_GATE |
| Schema/models | JSON Schema 2020-12 + Pydantic v2 + DuckDB DDL | Pydantic PROTOTYPE_GATE |
| Migrations | Thin immutable migration ledger with checksums and rebuild receipts | PROTOTYPE_GATE |
| Orchestration | Docker Compose 5.3.1 + thin local coordinator/retry policy | ACCEPTED |
| Observability | stdlib structured logs + prometheus-client; server/OTel deferred | CONDITIONAL_ACCEPT |
| Quote boundary | Project QuoteProviderPort; Jupiter Swap V2 `/order` without taker as primary future adapter | CONTRACT_ACCEPT / RUNTIME_DEFER |
| Replay/testing | unittest + immutable golden fixtures + deterministic project receipts | ACCEPTED / BUILD |
| Supply chain | uv lock, guarded pip-audit 2.10.1, validated CycloneDX 1.5 preview export | CONDITIONAL_ACCEPT |

The full component-by-candidate matrix is supplied separately in CSV and JSON.

## 5. Custom BUILD justifications

Only thin project truth boundaries are built:

1. **Pump/PumpSwap decoder** — official source may lag; the project needs strict protocol/version/quote-mint
   semantics, deterministic offline decoding and unknown-layout hard failure.
2. **ParquetPort + dataset manifest writer** — no external writer owns the project's file naming, staging,
   first-availability, dataset fingerprint and no-in-place-mutation contract.
3. **Migration ledger** — reviewed general migration tools do not provide a first-party canonical
   DuckDB/Parquet replay contract with the required receipts.
4. **Local coordinator/retry policy** — generic schedulers do not own run identity, single-writer locking,
   checkpoints, idempotency or point-in-time retry semantics.
5. **QuoteProviderPort** — vendor-neutral no-route/error/timestamp/cost semantics are project truth.
6. **Golden fixtures, replay harness and receipt profile** — these encode the project's falsification and
   evidence rules and remain reusable if third-party implementations change.

These are narrow adapters/contracts, not a generic platform.

## 6. Rejected and deferred paths

### Rejected now

- pip-tools or Poetry as a second dependency authority;
- fastparquet as canonical writer;
- multiple independent writers to one native DuckDB file;
- sqlalchemy-migrate;
- Celery for the single-host MVP;
- Hummingbot Gateway as the initial quote/execution spine;
- custom route-finding engine;
- legacy Jupiter `/swap/v1/quote` as the primary contract.

### Deferred behind measured triggers

- AnchorPy, Yellowstone/Vixen, Quack, DuckLake/PostgreSQL, Alembic, APScheduler, Temporal;
- standalone Prometheus server and OpenTelemetry;
- pytest and Hypothesis;
- Raptor beyond bounded TASK-07 comparison;
- Jupiter build/execute paths;
- GitHub Dependabot automation claims until settings read-back;
- Sigstore/in-toto/SLSA until an external artifact distribution boundary exists.

## 7. Prototype verdict and accepted pins

`PASS`; Atom 4R prototype gate is `CLOSED`.

The accepted runtime/default pins are PyYAML 6.0.3, jsonschema 4.26.0,
DuckDB 1.5.5, PyArrow 25.0.0, Pydantic 2.13.4, solana 0.40.1,
solders 0.28.0 and prometheus-client 0.25.0. Pydantic resolves
pydantic-core 2.46.4 transitively. The separate PEP 735 `security` group pins
pip-audit 2.10.1 and is not installed in the runtime-only environment.

The prototype passed Windows x64 and Linux glibc x86-64 resolution/import,
PIT filtering, immutable Parquet/manifest, two fresh DuckDB rebuilds, unsafe
narrowing rejection, extension deny policy, and cross-platform deterministic
receipt checks. No provider/API/RPC, wallet, signer, transaction or live-data
call occurred.

The retained CycloneDX 1.5 export is PREVIEW. Its raw SHA-256 is
`4db108ab39ea41339949ca4fc74383e80aa040855b5222f6b9892f257f81aeb6`;
the normalized component/dependency graph digest is
`e970bdc62a01229b926f7e734acfcd2deefb56addb0807641729962e151a772f`.
Raw exports may differ only in generated timestamp and serial number.

Atom 5A also exported the exact repository lock with the security group. That
tracked PREVIEW export has raw SHA-256
`6502eda8930d46db5e754f4f1b8fb406acde435f0bf410d4c0edb766f981cba7`
and normalized graph SHA-256
`075a98c8514352f60c75eb374b374c76f3d5a3df95ecd37eda1537c80fb1a484`
after removing only generated timestamp and serial number.

Exact artifact license metadata is missing for `jsonalias==0.1.1` and
`solders==0.28.0`. Accepted evidence records only a project-level MIT claim for
jsonalias; it does not promote that claim to exact-artifact evidence. The
handoff contains no stronger official solders project-level claim, so the gap
remains explicit and must be resolved before any license-sensitive distribution.

## 8. Security and authority boundaries

- No third-party component receives signer, wallet or real-money authority.
- RPC and quote adapters are read-only in P1.
- Jupiter `/order` is used without `taker` for quote-only validation; build/execute/submit remain deferred.
- Pump decoder is pure and network-free.
- DuckDB extension auto-install/auto-load and community/network extensions are deny-by-default.
- Logs, metrics, SBOMs and receipts contain no secrets, raw dumps or absolute machine paths.
- Provider runtime remains TASK-07; this ADR performs no provider calls.

## 9. PIT/replay invariants

- Raw/provider bytes are append-only and retained before normalization.
- `event_time`, `observed_at`, `available_to_strategy_at`, `ingested_at`,
  source/version and revision identity survive every boundary.
- Missing is never coerced to zero.
- Parquet manifests own file inventory, hashes, schema and time bounds.
- DuckDB is rebuildable derived state.
- Retry, restart and migration history cannot rewrite prior evidence.
- The same fixture/config/input must produce the same receipt digest.

## 10. TCO and lock-in posture

The stack deliberately concentrates custom work in thin truth boundaries while keeping data and
contracts portable. Native dependencies add supply-chain review, but Parquet, JSON Schema, raw bytes,
tracked DDL and adapter ports preserve exit options. Distributed orchestration, shared catalogs and
low-latency streams are deferred until measured evidence can pay their operating cost.

## 11. Repository/Catalog transaction impact

Atom 5A records this ADR, the 52-row matrix, the accepted research/prototype
evidence, the backward-compatible reuse registry 1.1 contract, exact dependency
lock, and Catalog 0.3.0 as one staged candidate. Historical schema 1.0
registries remain valid; the eight non-reuse registries remain empty and
byte-semantic 1.0. Mutable task/stage/catalog markers are removed from
`pyproject.toml`; Work and the Catalog remain their respective truth owners.

## 12. Consequences

### Positive

- low cash and operator burden;
- no premature distributed stack;
- strong replay/PIT and provider exit paths;
- one bounded integration prototype before dependency adoption;
- future hypothesis/orchestrator layer can reuse stable data and control contracts.

### Negative

- the project owns several thin but important adapters and receipts;
- native package/wheel review is mandatory;
- single-writer DuckDB constrains concurrency until a measured trigger;
- Pump source licensing and Raptor terms remain unresolved, therefore vendoring/adoption is restricted.

## 13. Non-decisions

This ADR does not:

- implement TASK-05 schemas or TASK-06 storage;
- call providers or validate live quotes;
- choose paid plans or VPS;
- implement a bot, strategy, transaction builder or signer;
- authorize low-latency infrastructure;
- claim TASK-04 DONE.

## 14. Next gate

Work acceptance of this staged candidate is the next gate. A separate explicit
authorization is required before commit or push. TASK-05 is the next consumer
of the accepted ADR, matrix, lock and prototype boundaries; TASK-05 is not
active and no TASK-05 implementation is included here.
