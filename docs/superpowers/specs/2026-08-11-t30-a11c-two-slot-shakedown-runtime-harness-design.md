# T30-A11C Two-slot shakedown runtime harness — Design

**Status:** owner design approved (`A11C_DESIGN_APPROVED`)

## Decision

Build one narrow, fail-closed foreground runner for the already approved
TASK-30 A11B technical shakedown.  It proves only whether one named public
GeckoTerminal OHLCV route can return the expected closed 15-minute interval at
two independently started observation slots.  It does not collect a research
panel, admit a trial, select a provider, or authorize a 24-hour capture.

## Alternatives considered

1. **One-slot runner invoked twice — selected.**  Each foreground invocation
   owns exactly one closed 900-second slot and at most four GETs.  A separate
   invocation for slot two must read and validate slot one's receipt.  This
   directly enforces the A11B recovery boundary and avoids an unattended
   15-minute process.
2. One long two-slot process.  Rejected: it makes monitoring loss and recovery
   less explicit, and it resembles a scheduler before the route is proven.
3. Four manual commands per slot.  Rejected: it has no deterministic cap,
   time-window guard, raw-manifest chain, or reproducible negative result.

## Scope and non-goals

In scope:

- exactly two separately started slots, each with offsets 0, 15, 30 and 60
  seconds after `slot_end_utc`;
- exactly one public keyless GeckoTerminal OHLCV GET per offset;
- immediate immutable local raw and health artifacts under retention A4;
- a local receipt chain that blocks slot two until slot one is healthy;
- deterministic tests using a fake transport only.

Out of scope:

- provider calls during implementation or acceptance;
- retries, fallback, credentials, scheduler/background process, R2/R3;
- continuous collection, data-panel construction, PIT admissibility, a TASK-30
  trial, strategy, execution, PnL, NetReturn or cashflow claim;
- wallet, signer, transaction, spend, dependency or Project Sources changes.

## Runtime shape

The tracked policy contains only invariant terms: TASK-30/A11C identity,
frozen pool, GeckoTerminal HTTPS endpoint, 15-minute USD/base OHLCV request,
four offsets, response and timeout caps, retention root, and the strict
no-retry/no-fallback rule.

The runner accepts one slot at a time.  Before it can make a request, it must
receive a later owner-approved plain-text authorization binding all material
terms:

```text
T30-A11C_TWO_SLOT_SHAKEDOWN_EXECUTION_V1;
pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S;
slot_starts_utc=<SLOT_1>,<SLOT_2>;
monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND;
max_gets=8; retention=A4; retry=false; fallback=false
```

The future phrase is not a secret.  Its exact two slot timestamps are selected
only after this offline harness is delivered and immediately before the
external-read gate.  `LOCAL_WORK_CODEX_FOREGROUND` means the current agent
observes the single foreground process; loss of that process is a stop, never
a background restart.

For a slot with start `S`, the runner derives `slot_end = S + 900`.  It starts
before the boundary and waits only for that slot's four offsets.  If the
foreground start is already late for an offset, it records `STOP_RUN` before
any compressed or catch-up request.  It sends only:

```text
GET https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute
  ?aggregate=15&currency=usd&token=base&include_empty_intervals=false
  &limit=1&before_timestamp=slot_end
```

The transport permits HTTPS, the exact host and path, response-size and
timeout caps, no redirects, and one request per planned offset.  No code path
can retry or call another provider.

## Evidence and recovery model

After every response, before the next offset, the runner writes outside Git:

1. immutable raw JSON (or received error body);
2. `raw_manifest_<ordinal>.json`, listing every raw byte retained so far and
   its SHA-256;
3. `health_receipt_<ordinal>.json`, recording request timing, HTTP status,
   safe headers, raw/manifest hashes and the current health state.

After the fourth response it writes `slot_receipt_v1.json`.  This contains the
authorization fingerprint, slot start/end, four response classifications,
artifact hashes and terminal state.  Slot two must validate slot one's exact
receipt, its hash chain, first-slot identity and healthy terminal state before
opening transport.  Any malformed prior receipt, missing manifest, write
failure, timing breach, route mismatch, monitoring loss or transport error
stops the current slot; no hidden retry, fallback, restart or second slot is
allowed.

A received row is only a technical retained observation when its interval
start equals the requested slot start.  A missing/malformed row remains a
typed gap; it never becomes zero, flat activity or evidence about H07/H01.

## Interfaces and files

- Create `docs/contracts/task30_two_slot_live_shakedown_runtime_contract_v1.md`
  — executable boundary, authority phrase grammar, outputs, recovery and
  explicit non-claims.
- Create `configs/task30_two_slot_live_shakedown_runtime_v1.yaml` — frozen
  non-time policy.
- Create `catalog/schemas/task30_two_slot_live_shakedown_runtime.schema.json`
  — closed policy schema.
- Create `tests/fixtures/task30/two_slot_live_shakedown_runtime_v1.json` —
  canonical synthetic success and failure inputs.
- Create `src/solana_alpha_lab/task30_two_slot_live_shakedown_runtime.py` —
  pure validation, authority parsing, request plan, receipt verification and
  a dependency-injected bounded transport.
- Create `scripts/run_task30_two_slot_live_shakedown.py` — one-slot CLI with
  explicit dry-run or future execute mode.
- Create `tests/test_task30_two_slot_live_shakedown_runtime.py` — behavioral
  and adversarial tests.
- Create `docs/evidence/task30/a11c_two_slot_live_shakedown_runtime_offline_acceptance_v1.json`
  — hash-bound offline receipt, Factory Fit and zero-side-effect counters.
- Update only the required Catalog owners/generated views for these artifacts.

The A11B owner-packet artifacts stay historical and unchanged.  Project Sources
disposition is `NO_CHANGE`.

## Test-first acceptance

Tests are written before production code and must demonstrate:

- a valid first-slot plan has exactly four permitted requests and zero calls in
  dry-run;
- bad/missing authority, host/path/query drift, non-aligned slot time, a late
  start and a fifth request all fail before network I/O;
- fake healthy responses create four raw files, four immutable manifests, four
  health receipts and one healthy slot receipt;
- an invalid row, transport failure, write failure or monitoring loss stops
  without an extra request;
- slot two rejects an absent, altered, unhealthy or differently authorized
  first-slot receipt before network I/O;
- a typed gap is preserved as unknown and grants no research, execution or
  24-hour authority.

Targeted validation will run the new test plus direct A10/A11/A11B consumers.
One tracked-only delivery preflight will validate the committed candidate; CI
will independently validate the exact PR head.

## Completion and next boundary

This atom is technically complete only after the offline runner, tests,
Catalog propagation, tracked-only gate, PR and exact-head CI pass.  It still
does not execute a provider request.

Only then will the owner receive one compact, time-bound phrase with two exact
UTC slots.  A successful two-slot run yields only
`SHAKEDOWN_PASSED_TECHNICAL_ONLY`, `SHAKEDOWN_FAILED_ROUTE`, or
`SHAKEDOWN_INCONCLUSIVE`; none authorizes 24-hour collection automatically.
