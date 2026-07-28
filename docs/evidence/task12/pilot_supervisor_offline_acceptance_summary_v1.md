# TASK-12 deterministic offline supervisor acceptance v1

## Result

`T12-A5_CATALOG_REPOSITORY_FINALIZATION_V1` publishes the accepted
`T12-A4_DETERMINISTIC_OFFLINE_ACCEPTANCE_V1` claim:

`THIN_OFFLINE_SUPERVISOR_DETERMINISTIC_CONTROL_ACCEPTANCE`

The thin supervisor executes its one allowlisted consumer in offline-preflight
mode and fails closed across the six remaining frozen control vectors. This
accepts the current A2/A3 bytes as an offline falsifier and registers all
mandatory TASK-12 outputs. It does not establish that unattended collection or
a sustained pilot is safe.

## Acceptance matrix

The deterministic matrix contains seven vectors:

- real TASK-11 offline preflight: `SUCCEEDED`;
- zero exit without the exact marker: `FAILED /
  EXPECTED_MARKER_MISSING`;
- non-zero child exit: `FAILED / CHILD_EXIT_NONZERO`;
- active duplicate: `BLOCKED_DUPLICATE / ACTIVE_DUPLICATE`, no spawn;
- insufficient start disk: `BLOCKED_DISK /
  INSUFFICIENT_DISK_BEFORE_START`, no spawn;
- wall timeout: `TIMED_OUT / CHILD_WALL_TIMEOUT`, bounded stop;
- runtime disk breach: `BLOCKED_DISK / DISK_GUARD_BREACHED`, bounded
  stop.

The suite uses cross-platform exit classes for terminated processes and
excludes volatile timestamps, disk readings, byte counts and platform-specific
termination codes from the stable projection. It still validates UTC evidence
timestamps, monotonic elapsed ordering, event fields, lineage, output hashes
and bounded line size on every execution.

## Evidence

- Frozen acceptance fixture:
  `tests/fixtures/task12/pilot_supervisor_offline_acceptance_v1.json`
- Fixture SHA-256:
  `d94fa0721774906084b943d1a8abf197ee96508633ddd7a9f1fdfa07c07cfd61`
- Machine-readable receipt:
  `docs/evidence/task12/pilot_supervisor_offline_acceptance_receipt_v1.json`
- Acceptance test:
  `tests/test_task12_pilot_supervisor_acceptance.py`
- Contract SHA-256:
  `f65f068746f9239e13b30707ef99a6b8c2713d4635f926dd4d6fd7c61028848f`
- Supervisor module SHA-256:
  `a398379711eb5f6b9799d0029b1cf882676492229838ac07c42a523fe12865f7`
- CLI SHA-256:
  `fb85b2e0a9fc60a01dc01f80817ae1458471861728ef4635eb5a0893d434405f`

Validation:

- Atom-4 acceptance suite: `7/7 PASS`;
- Atom-5 Catalog finalization check: `1/1 PASS`;
- TASK-12 contract, implementation and acceptance suite: `42/42 PASS`;
- full repository unit suite: `904/904 PASS`;
- Catalog transaction:
  `0.15.0 / 252 assets / 4 shards / 4 schemas / 7 queries PASS`;
- generated navigation: `PASS`;
- secret scan and file hygiene: `PASS`.

The direct repository-policy validator was rerun and failed only at the
expected `repository_topology: INVALID_GIT_TOPOLOGY`: the accepted A2-A5
candidate remains untracked on `main` under the stricter `LOCAL_WRITE_ONLY`
boundary. The aggregate `validate_ci.py` gate was therefore not duplicated.

## Authority and non-claims

Each acceptance-suite execution makes seven supervisor attempts and spawns
five local child processes: one real allowlisted offline preflight and four
synthetic controls. The duplicate and start-disk vectors spawn nothing.

Network, provider/API/RPC/WSS calls, credentials, collector executions, raw
data writes, cash, credits, dependency changes and wallet/signer/transaction
actions are all zero. No raw child body or machine-specific absolute path is
retained in tracked evidence.

The acceptance does not validate retries, automatic restart, 24-48 hour
operation, production packaging, provider execution, strategy behavior,
trading or owner cashflow.

## Status and next boundary

TASK-12 remains `IN_PROGRESS`. All ten mandatory outputs are registered in
Catalog `0.15.0`; generated navigation and repository-policy consumers agree
on `252` assets.

`T12-A5` is a technical publication candidate, not canonical `DONE`. The next
boundary is repository delivery: exact task branch/commit, non-force push,
draft PR and CI read-back. Merge still requires its separate exact user gate.
