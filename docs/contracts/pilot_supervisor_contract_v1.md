---
contract_id: CONTRACT-T12-PILOT-SUPERVISOR-001
contract_version: "1.0"
task_id: TASK-12
atom_id: T12-A2_OFFLINE_SUPERVISOR_CONTRACT_V1
status: FROZEN_OFFLINE_CONTRACT
as_of: 2026-07-28
provider_calls: 0
cash_spend_usd: 0
contains_secrets: false
---

# TASK-12 offline pilot-supervisor contract v1

## 1. Purpose and accepted claim

This contract freezes the smallest supervisor boundary needed before a local
24–48 hour collection pilot can be considered. Atom 2 accepts only:

`OFFLINE_SUPERVISOR_CONTRACT_FROZEN`

It does not claim that a supervisor has been implemented, that a collector has
run, or that unattended collection is safe. The cheapest falsifier is one
offline child process with deterministic success, failure, timeout, duplicate
and disk-pressure cases.

The first consumer is the TASK-11 launcher:

`SCRIPT-T11-ENTITY-INPUT-PROBE-001`

It is invoked without `--execute` and without `--replay-run`, so it performs
only its existing offline preflight. Its success marker is
`TASK11_ENTITY_PROBE_PREFLIGHT: PASS`.

## 2. Reuse decision

TASK-12 applies `ADOPT -> WRAP -> FORK -> BUILD`:

- `ADOPT` `REUSE-T04-LOGGING-001`, Python process/filesystem primitives and
  the accepted offline TASK-11 launcher;
- `WRAP` no third-party runtime in the first slice;
- `FORK` nothing;
- `BUILD` only the thin repository-local coordinator already accepted by
  `REUSE-T04-COORDINATOR-001`.

Docker Compose remains an accepted later packaging option, not the first
falsifier. APScheduler, Celery, Temporal, Prometheus server and OpenTelemetry
remain deferred or rejected according to their existing reuse records.
`prometheus-client` is already installed but is not required by this atom.
There is no dependency change.

## 3. Process and run identity

Every attempt has a supervisor `run_id` derived from canonical JSON containing:

- contract version;
- consumer asset ID;
- child plan SHA-256;
- logical target scope;
- UTC window start;
- attempt sequence.

The identity algorithm is SHA-256 with the visible prefix `t12-`. Duration and
timeout decisions use a monotonic clock. Human timestamps use UTC RFC 3339.
Wall-clock changes must not extend or shorten a timeout.

The duplicate key is:

```text
consumer_asset_id
+ child_plan_sha256
+ logical_target_scope
+ utc_window_start
```

At most one active process may hold this key. Lock acquisition must be atomic.
A lock cannot be stolen because it is old: the supervisor must reconcile the
recorded process identity and start token first. A duplicate attempt emits
`BLOCKED_DUPLICATE` and does not spawn a child.

## 4. State machine

Supervisor states are:

- `CREATED`;
- `STARTING`;
- `RUNNING`;
- `SUCCEEDED`;
- `FAILED`;
- `TIMED_OUT`;
- `STOPPED`;
- `BLOCKED_DUPLICATE`;
- `BLOCKED_DISK`.

Terminal states never transition. `CREATED` can be blocked before spawn.
`STARTING` becomes `RUNNING` only after a child process exists. A zero exit
code is not sufficient for success: the exact offline success marker must also
be present within the output caps.

Typed terminal reasons include:

- `CHILD_EXIT_NONZERO`;
- `EXPECTED_MARKER_MISSING`;
- `CHILD_OUTPUT_LIMIT_EXCEEDED`;
- `CHILD_LINE_LIMIT_EXCEEDED`;
- `CHILD_WALL_TIMEOUT`;
- `ACTIVE_DUPLICATE`;
- `INSUFFICIENT_DISK_BEFORE_START`;
- `DISK_GUARD_BREACHED`;
- `STOP_REQUESTED`;
- `CHILD_SPAWN_FAILED`;
- `INVALID_CHILD_OUTPUT`.

These reasons are operational evidence. None may be rewritten to empty data,
`NO_ROUTE`, a strategy result or a provider probability.

## 5. Health and silence

The first slice observes:

- supervisor process state;
- child process liveness and exit code;
- last bounded stdout/stderr activity;
- elapsed monotonic time;
- disk guard;
- lock ownership;
- terminal marker and terminal reason.

Health states are `STARTING`, `HEALTHY`, `DEGRADED`, `UNHEALTHY` and
`STOPPED`. The offline child has five seconds to spawn, thirty seconds of
maximum silence and sixty seconds of total wall time. Polling is no faster than
200 milliseconds.

An alive process beyond the silence threshold is `DEGRADED`; it is then stopped
as `TIMED_OUT` with `CHILD_WALL_TIMEOUT` no later than the total wall cap.
An exited process without a valid terminal marker is not healthy.

## 6. Retry and stop policy

The offline first slice has:

```text
retry_count_max = 0
concurrency = 1
child_wall_seconds_max = 60
graceful_stop_seconds = 5
```

There is no automatic restart and no retry storm surface. A later retry policy
requires a new contract version and must create a new attempt sequence while
retaining the parent run identity.

On stop, the supervisor:

1. records `STOP_REQUESTED`;
2. requests graceful child termination;
3. waits at most five monotonic seconds;
4. uses bounded forced termination only if the child remains alive;
5. records the exact final exit disposition;
6. releases only the lock it owns.

Stopping the child must not delete raw data, manifests, receipts or another
run's lock.

## 7. Output and structured event limits

Supervisor events are newline-delimited canonical JSON with these mandatory
fields:

- `schema_version`;
- `event_type`;
- `run_id`;
- `consumer_asset_id`;
- `attempt_sequence`;
- `state`;
- `observed_at`;
- `monotonic_elapsed_ms`;
- `reason`;
- `child_exit_code`;
- `stdout_bytes`;
- `stderr_bytes`;
- `disk_free_bytes`;
- `provider_calls`;
- `cash_spend_usd_cents`.

Required event types are `SUPERVISOR_STARTED`, `CHILD_STARTED`,
`CHILD_ACTIVITY`, `HEALTH_CHANGED`, `STOP_REQUESTED`, `CHILD_EXITED` and
`SUPERVISOR_FINISHED`.

One line is capped at 16,384 bytes. Combined child stdout and stderr are capped
at 262,144 bytes. One sanitized supervisor run log is capped at 1,048,576
bytes and seven days of local retention. Secrets, environment dumps, request
headers, provider bodies, wallet identifiers and machine-specific absolute
paths are forbidden.

## 8. Disk guard

Disk space is checked before spawn and on every health sample. For the offline
falsifier, predicted durable child writes are zero. The minimum start reserve
is:

```text
2 * predicted_child_write_bytes_max + 536870912
```

The runtime stop reserve is:

```text
predicted_remaining_write_bytes_max + 268435456
```

Insufficient start space yields `BLOCKED_DISK` without a child. Crossing the
runtime threshold requests a bounded stop and yields `BLOCKED_DISK` with
`DISK_GUARD_BREACHED`. Missing disk telemetry fails closed.

These constants are safety reserves, not a forecast for a future 24–48 hour
run. A sustained pilot needs measured bytes per minute and separately approved
runtime, provider and storage caps.

## 9. Raw lineage and PIT invariants

The supervisor may reference child artifacts but must not rewrite them. It
retains:

- parent and child run identities;
- exact consumer asset ID and repository-relative launcher path;
- child plan SHA-256;
- exact argv without credentials;
- child start, observation and availability timestamps;
- terminal exit disposition;
- hashes of any accepted child receipt or manifest.

TASK-06 raw identity, revision links, immutable envelopes and manifest hashes
remain authoritative. Event, observed, first-reliable-available, strategy-
available and ingested timestamps retain their existing meanings. Restart does
not backdate availability; missing output is not zero. Provider failure is not
`NO_ROUTE`, success or an empty observation.

## 10. Offline authority and exclusions

Atom 2 permits local writes only to:

- `docs/contracts/pilot_supervisor_contract_v1.md`;
- `tests/fixtures/task12/pilot_supervisor_contract_v1.json`;
- `tests/test_task12_pilot_supervisor_contract.py`;
- `catalog/assets/core.yaml`.

This atom permits zero:

- network, provider/API/RPC/WSS or credentialed calls;
- collector execution or raw-data writes;
- cash, credits, purchase or deployment;
- dependency changes;
- wallet, signer, transaction build/simulation/send or real money;
- commit, push, PR, merge, settings, force or destructive actions.

The cash cap remains `USD 0`.

The Catalog target is authorized but intentionally unchanged in Atom 2:
complete registration would also require the manifest, generated navigation
and count-test propagation outside this exact write set. The three new outputs
remain `CATALOG_TRANSACTION_PENDING_TASK12_FINAL_RECONCILIATION`; this blocks
TASK-12 `DONE`, not the bounded contract freeze.

## 11. Atom-2 Definition of Done and next boundary

Atom 2 passes only when deterministic tests prove:

- exact fixture identity and managed write set;
- one offline consumer and no execution flags;
- finite state and failure semantics;
- atomic duplicate prevention;
- monotonic timeout and UTC evidence separation;
- zero retry, provider call, raw write, spend and wallet actions;
- disk guards and bounded output/retention;
- raw lineage and PIT meanings remain unchanged;
- Catalog deferral is explicit rather than silently claimed complete;
- no secret or absolute machine path appears in tracked artifacts.

After PASS, stop before production implementation. The next candidate atom is
`T12-A3_THIN_OFFLINE_SUPERVISOR_IMPLEMENTATION_V1`, requiring a separately
bounded write set. External collection remains a separate authority boundary.
