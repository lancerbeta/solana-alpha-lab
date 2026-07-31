# TASK-21 Owner Pulse Read Model Contract v1.8

## 1. Purpose

`OWNER-PULSE-T21-001` is a local read model over accepted repository evidence.
It answers what needs owner attention now without making the dashboard, CLI or
generated JSON a second truth owner.

This atom also installs one durable project-local reminder:
`control/active_time_gates.json`. The repository `AGENTS.md` requires every
future local agent to read this marker before selecting or starting another
task or parallel atom.

## 2. Time-gate precedence and correction

The original `TASK21-T1-CLOSE-2026-08-06` gate is preserved as historical
evidence. After H6 gap close, the pulse selects exactly one unresolved
`ACTIVE_WAITING` gate; the current gate is
`TASK21-H24-2026-08-01T07-50-34Z`.

- Before `2026-08-01T07:50:34.414367Z`, non-interfering parallel work is
  allowed.
- At or after that minimum age, the marker returns
  `DUE_PREEMPT_PARALLEL_WORK` until the owner resolves the exact next atom.
- There is no narrow expiry. A later capture records exact elapsed seconds;
  operator lateness by itself is not converted into a data gap.
- The exact next atom is `T21-A6S_H24_FOREGROUND_CAPTURE_V1`; it captures one
  frozen outcome-blind sentinel only under separate provider authority.
- The marker does not execute work, schedule a process or grant external
  authority.
- Only the declared resolution owner may close or cancel the marker, and it
  must attach an exact evidence pointer.

The original gate is preserved as historical evidence. The forward-only
`T21-A6S_T1_HORIZON_GATE_CORRECTION_V1` supersedes P7D as the exclusive start
gate because no observations occur during that wait. P7D remains one horizon
in a multi-horizon measurement grid.

After exact H0/H1 evidence and the explicit H6 gap are attached, the pulse
reports three admissions and six captured panels, retains three missing H6
panels without backfill, accounts for calls and bytes, and routes H24. The
pre-H24 recovery refresh is now proven by an exact content-addressed Drive
read-back and full isolated restore. It still grants zero provider or
later-horizon authority.

The pulse shows H24 as a minimum-age active gate and H72/H168 as
`DEFERRED_TRIGGER_ONLY`. Their offsets remain visible candidate ages, but they
have no active gate, deadline, reserved calls or mandatory run. Activation
requires a named need, fresh whole-task budget proof and separate provider
authority. The projection never grants authority or starts a scheduler. UTC
remains machine truth and default text adds deterministic MSK timestamps.

## 3. Truth boundaries

The pulse derives:

- gate state from `control/active_time_gates.json`;
- the forward-only horizon correction from
  `observation_horizon_policy_acceptance_v1.json` and
  `task21_observation_horizon_policy_v1.yaml`;
- the post-H6 sentinel and timing rebase from
  `task21_post_h6_gap_sentinel_value_rebase_v1.yaml`;
- nomination, replay and current external-consumption facts from
  `real_nomination_source_offline_acceptance_v1.json`;
- real admissions, H0/H1 panel totals and the H6 gap from
  `h0_admission_capture_runtime_acceptance_v1.json` and
  `h1_foreground_capture_runtime_acceptance_v1.json` and
  `h6_foreground_capture_runtime_acceptance_v1.json`;
- current backup and restore proof from
  `pre_h24_recovery_refresh_acceptance_v1.json`, bound by the active H24
  marker;
- the H24 minimum age and H72/H168 trigger-only candidates from the latest
  immutable H0 trigger, cross-checked against the active H24 marker;
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

1. due unresolved minimum-age gate;
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
- more than one unresolved active marker;
- malformed UTC timestamps;
- source receipt hash drift;
- a non-PASS nomination receipt;
- mismatch between marker and receipt T1 close;
- correction receipt or observation-horizon policy hash drift;
- H0, H1 or H6 runtime receipt pointer, hash or status drift;
- frozen horizon offsets, H0 anchor or active H24 marker schedule drift;
- post-H6 sentinel value-rebase drift;
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

This v1.8 projection is updated by the explicitly approved
`T21-A6S_POST_H6_GAP_SENTINEL_VALUE_REBASE_V1` local-write atom.

The managed write set is limited to the owner-pulse config, this contract,
module, targeted tests and a new multi-horizon schedule acceptance receipt.
The current observation-horizon consumer reconciliation receipt advances to
bind this owner-pulse version; prior atom acceptances stay historical. TASK-17
production memory, four legacy
registries, `AGENTS.md` and Catalog remain protected read-only inputs. The
active time-gate marker is consumed after the recovery atom satisfies its
recovery prerequisite.
No new TASK-21 asset is registered before A7 and the Catalog count/version is
not advanced by this atom.

This atom performs zero network, provider/API/RPC/WSS or Drive calls and leaves
all raw market evidence unchanged. Credentials, cash,
wallet/signer/transaction actions, dependency changes, commit, push, PR, merge
and destructive actions remain zero.
