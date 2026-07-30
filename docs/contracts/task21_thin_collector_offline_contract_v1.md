# TASK-21 thin collector and offline dry-run contract v1

## Purpose

`T21-A4_THIN_COLLECTOR_AND_OFFLINE_DRY_RUN_V1` proves that the frozen
TASK-21 run plan can be bound to the accepted quote model, recovery health and
runtime caps before any live provider is selected. It is a synthetic pipeline
proof, not a live collector, real watchlist admission, scheduler, forward
dataset or research-readiness claim.

## Deterministic population and run

- The fixture contains exactly eight synthetic evaluated candidates: five
  active members, two rejected candidates and one not-evaluable candidate.
- Each active member has three foreground windows separated by 1,801 seconds.
- Every completed window has four USD 10/25/50/100 BUY quotes and four dependent
  reverse SELL quotes. The SELL input is the exact accepted BUY output in atomic
  units.
- The complete base dry run therefore contains 15 panels, 60 quote pairs and
  120 synthetic adapter calls. Provider/API/RPC/WSS calls, credentials, credits,
  cash spend, wallet/signer/transaction actions and forward dataset writes are
  all exactly zero.
- Population fields that look like outcomes, rankings, returns, PnL or a
  hypothesis verdict are rejected. The fixture contains no market data.

## Reuse boundary

The implementation adopts TASK-10 quote projection and its transitive TASK-06
raw envelope, TASK-17A panel semantics, and TASK-12 `SupervisorLimits`. The
TASK-12 process launcher is deliberately not invoked or changed: its executable
allowlist is frozen for TASK-11. A4 composes only its accepted disk-reserve and
health vocabulary around a provider-neutral in-memory adapter.

## Fail-closed acceptance

The pure run is fully assembled before local materialization. Insufficient disk
or call cap, an unhealthy/incomplete recovery receipt, or a population contract
violation therefore leaves no partial output.

- An exact complete restart is byte-read back and deduplicated without
  re-execution.
- An incomplete, extra or conflicting restart fails closed.
- A missed window remains an explicit coverage loss and is never silently
  rescheduled.
- Late evidence remains present and flagged instead of being rewritten away.
- Identical inputs produce byte-identical records, manifest and receipt.
- Materialization is create-only under the ignored
  `local/task21_collector/offline_dry_run` root and is capped at 4 MiB of
  synthetic records.

## Authority and next boundary

A4 is `LOCAL_WRITE_ONLY`. It does not authorize live provider traffic,
credentials, real candidate admission, background execution, Google Drive
operations, dependency changes, commit, push, PR, merge or deployment.

The next atom is `T21-A5_BOUNDED_LIVE_SHAKEDOWN_V1`. It requires a separate
exact provider/API/RPC/WSS and bounded collection-write authority, including
current endpoint read-back and hard caps. A4 does not start or imply A5.
