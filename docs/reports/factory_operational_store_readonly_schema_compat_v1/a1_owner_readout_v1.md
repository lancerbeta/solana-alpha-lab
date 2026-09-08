# FACTORY_OPERATIONAL_STORE_READONLY_SCHEMA_COMPATIBILITY_V1 — owner readout

## Decision unlocked

Can Petr open Workbench GET after an upgrade when the preserved
`local/factory_v1/operational_state.sqlite` is a valid SQLite file without an
OperationalStore `jobs` table?

**Answer: YES** in Git. GET stays pure. This is not product DONE, not alpha,
and not a Factory deploy.

## What landed

Readonly OperationalStore now probes `sqlite_master` / `PRAGMA table_info`
before any `SELECT FROM jobs`.

- `SOURCE_NOT_PRESENT` — file absent; GET remains renderable; no DB created.
- `LEGACY_UNINITIALIZED` — valid SQLite, no `jobs`; GET 200; job state absent;
  file SHA256/schema/rows unchanged.
- `READY` — required columns present; existing job payload is read as before.
- `INCOMPATIBLE` / `UNAVAILABLE` — fail closed as `UNAVAILABLE` with
  `OPS_STORE_INCOMPATIBLE`; not `NOT_STARTED`; no raw sqlite3 to HTTP.

Writable `OperationalStore(readonly=False)` still does additive
`CREATE TABLE IF NOT EXISTS` and keeps unrelated legacy tables/rows. Same-name
incompatible `jobs` fails closed before DDL.

## Proof

`tests/test_factory_operational_store_readonly_schema_compat_v1.py` covers the
exact production shape, missing file, incompatible columns, ready job
payload, GET purity (SHA256/schema/rows), writable additive init, and the
upgrade boundary (GET then later writable init). Isolated critics PASS.
Exact-head CI is the remaining machine gate. No VPS mutation.

## Non-claims

- No production deploy
- No GET-time CREATE/ALTER/WAL checkpoint/init
- No Alembic / schema registry / version table
- No collector / HOT90 / PaperPlane / research-store / systemd change
- No canonical DONE / alpha / NetReturn

## Stop

Owner merge phrase after exact-head CI and `ready_for_owner_phrase=true`.
Deployment is a later OPERATE decision against a chosen target SHA, not
«latest main».

## Rollback

Ordinary Git revert of this branch. Live Factory stays on its current
deployed SHA until a separate deploy atom.

## Residuals

- `/market` still does not probe the operational store (pre-existing isolation).
- `UNAVAILABLE` connect failure currently reuses blocker `OPS_STORE_INCOMPATIBLE`.
- Next: OPERATE deploy of the merge commit; do not treat GET as commissioning.
