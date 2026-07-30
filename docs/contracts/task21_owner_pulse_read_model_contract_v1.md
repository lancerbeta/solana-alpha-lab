# TASK-21 Owner Pulse Read Model Contract v1.1

## 1. Purpose

`OWNER-PULSE-T21-001` is a local read model over accepted repository evidence.
It answers what needs owner attention now without making the dashboard, CLI or
generated JSON a second truth owner.

This atom also installs one durable project-local reminder:
`control/active_time_gates.json`. The repository `AGENTS.md` requires every
future local agent to read this marker before selecting or starting another
task or parallel atom.

## 2. Time-gate precedence

The active gate is `TASK21-T1-CLOSE-2026-08-06`.

- Before `2026-08-06T16:28:59.084Z`, non-interfering parallel work is allowed.
- At or after that instant, an unresolved marker returns
  `DUE_PREEMPT_PARALLEL_WORK`.
- The exact next atom is
  `T21-A6S_T1_CLOSE_EVALUATION_AND_BOUNDED_PANEL_CAPTURE_V1`.
- The marker does not execute work, schedule a process or grant external
  authority.
- Only the declared resolution owner may close or cancel the marker, and it
  must attach an exact evidence pointer.

This prevents a long conversation or a new thread from silently skipping the
forward-test close while preserving useful parallel work during the wait.

## 3. Truth boundaries

The pulse derives:

- gate state from `control/active_time_gates.json`;
- nomination, replay, backup and current external-consumption facts from
  `real_nomination_source_offline_acceptance_v1.json`;
- restore proof from `runtime_recovery_gate_receipt_v1.json`;
- caps and current hypothesis binding from the TASK-21 run plan;
- the first production hypothesis lifecycle record from
  `docs/evidence/task17/first_bounded_hypothesis_cycle_v1.json`;
- legacy skeleton counts from the hypothesis, research-cycle, strategy and bot
  registries.

The TASK-17 production memory is the immutable machine-readable record for
`HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1`. The pulse verifies its exact
content hash, identity, append-only flag, frozen definition and latest
decision-derived state before declaring the TASK-21 runtime binding
consistent.

The four TASK-03 registries are legacy lifecycle skeletons intentionally
preserved without synthetic history. Their empty counts are not evidence that
production hypothesis memory is absent. The pulse must show both layers
explicitly, must not call the legacy layer the production truth owner, and
must not backfill or promote records between them.

## 4. Recovery and attention

Backup and restore ages are calculated at read time. The pulse surfaces stale
proof and the exact due gate; it does not refresh a backup or restore by
itself. Recovery freshness is a blocker for later freeze/promotion, not
authority to write to Drive.

Attention ordering is deterministic:

1. due unresolved time gate;
2. source/receipt integrity failure;
3. recovery proof at risk or overdue;
4. waiting time gate;
5. informational product gaps.

## 5. Output

The default output is a compact Russian text pulse. `--json` returns the same
facts as canonical JSON. The default text omits mint addresses and raw
payloads. Machine-specific absolute paths and secrets are forbidden.

The clock is injectable for deterministic tests. Production invocation uses
the current UTC clock and performs reads only.

## 6. Fail-closed behavior

The pulse fails closed for:

- absent or duplicate active marker;
- malformed UTC timestamps;
- source receipt hash drift;
- a non-PASS nomination receipt;
- mismatch between marker and receipt T1 close;
- negative counters;
- any attempt to infer external authority from the marker;
- production-memory content, identity or append-only drift;
- a TASK-21 runtime version, definition or state that does not match the
  TASK-17 production memory.

## 7. Non-claims

This atom implements no web UI, truth database, scheduler, collector, provider
adapter, position manager, execution engine or trading system. It establishes
no Fillable, NetReturn, PnL, alpha or production-readiness claim.

## 8. Authority

Authority is exactly
`T21-P2R_OWNER_PULSE_PRODUCTION_MEMORY_BINDING_V1 — LOCAL_WRITE_ONLY`.

The managed write set is limited to the owner-pulse config, this contract,
module, targeted tests and the owner-pulse acceptance receipt. The TASK-17
production memory, four legacy registries, active time-gate marker, `AGENTS.md`
and Catalog are protected read-only inputs. No new TASK-21 asset is registered
before A7 and the Catalog count/version is not advanced by this atom.

Provider/API/RPC/WSS and Drive calls, raw or dataset writes, credentials,
cash, wallet/signer/transaction actions, dependency changes, commit, push, PR,
merge and destructive actions are zero.
