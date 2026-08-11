# TASK-30 A14P — forward-stream execution adapter

## Objective

Close the last offline seam before one possible owner-authorised foreground
Helius `transactionSubscribe` capture. The adapter must publish durable intent
before credential lookup, reuse the accepted TASK-08 WebSocket transport,
retain exact A4 bytes outside Git and fail closed when terminal truth is
missing.

## Consumer and reusable gap

- Consumer: `EXACT_OWNER_FORWARD_STREAM_EXTERNAL_GATE`.
- Reuse decision: `WRAP` the existing TASK-08 `websockets_wss_exchange()`;
  do not fork socket logic or build a generic streaming service.
- Named capability gap: A14 had target and classification truth but no
  create-only attempt state, exact raw sink or guarded foreground runner.
- Next consumer: one bounded TASK-30 technical capture on the frozen pool.

## Bounded deliverable

- strict execution policy, closed schema and synthetic fixture;
- one adapter joining A14 request/classification to TASK-08 `WssCapture`;
- create-only `attempt_started.json`, exact raw objects, hash manifest and
  terminal receipt under ignored `local/task30_forward_stream`;
- unresolved-attempt blocking and no-retry recovery semantics;
- one CLI with `--dry-run` and separately gated `--execute` modes;
- adversarial offline tests, FULL Factory Fit and Catalog bindings.

## Hard boundaries

This atom performs zero provider/API/RPC/WSS calls, credential reads, external
raw writes, retries, reconnects, fallbacks, scheduler actions, dependency
changes, R2/R3 access, wallet/signer/transaction actions, cash spend, trial
opening or Project Sources changes. Synthetic credentials and fake transport
objects exist only inside deterministic tests.

The future owner phrase is a frozen gate, not present authority. The offline
candidate cannot claim interval coverage, empty intervals, zero volume, PIT
admissibility, H07/H01 evidence, alpha, strategy, execution, settlement, PnL,
NetReturn or TASK-30 acceptance.

## Recovery and stop rule

`attempt_started.json` is published before reading `HELIUS_API_KEY`. A valid
terminal receipt closes that attempt without rewriting the marker. Any started
attempt without valid terminal truth is `UNRESOLVED_EXTERNAL_ATTEMPT` and
blocks a second attempt. Transport loss remains `TRANSPORT_LOST_UNKNOWN`;
retention failure becomes `RETENTION_FAILED_STOP` only when that terminal
receipt can itself be durably published.

After offline delivery and exact-main CI, stop before credential lookup or
WebSocket execution. A later external action requires the exact A14P owner
phrase on the merged exact-main bytes.

## Acceptance

Acceptance requires the focused A14P suite, direct A14/TASK-08 compatibility,
Catalog validation, generated-view consistency and one tracked-only full
delivery gate. The design and implementation plan are hash-bound process docs
outside Catalog product assets. Repository delivery does not change canonical
TASK-30 status: `STATE_CHANGE=NONE`.
