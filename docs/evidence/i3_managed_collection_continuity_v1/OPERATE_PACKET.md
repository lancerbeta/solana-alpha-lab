# I3 managed collection continuity — OPERATE packet

Status: `PREPARED_NOT_EXECUTED`. A software merge authorizes nothing below. Phases 1-3
need one exact owner OPERATE decision each (deploy, profile apply, B handover cleanup);
phases 0, 4 and 5 are read-only. Host paths stay logical (`SOURCE_REPO`, `DATA_ROOT`,
`OPS_STORE`); transport is the existing remote-ops runbook. Nothing here deletes data,
changes provider entitlement, raises a cap or touches A, the armed B timer, C1/C2.

## 0. Preconditions (read-only, fail-closed)

1. Exact artifact `M` = guarded merge commit of this PR on `main`, green post-merge CI.
2. Fresh ro readback of the live store (`mode=ro`): A `ACT-4744D4017AC4B196` state and
   authority `c2c937b4…`; B `ACT-A26CF9B0815A36F2` registration, authority (full hash
   from runtime; the prefix `78acdcb7…` alone is not enough) and the
   `factory-i3-b-activate.timer` armed state; shared account `JUPITER-MANAGED-ACCOUNT-1`
   `MANAGED` with 1200/1200/2,000,000; restore marker resolved; due backlog 0.
3. A compact backup health receipt source exists: the latest verified remote checkpoint
   timestamp, artifact SHA256 and coverage label from the existing backup owner. If there
   is none, STOP: new intake would be blocked `BACKUP_MISSING` by design.
4. `account-budget-status` `unbound_live_activations` is empty.

## 1. Deploy `M` (authority: exact producer deploy)

Ordinary canonical-forward release between ticks; the release restores the prior timer
state. No pause of A or B; no unit or timer is created or modified.

Acceptance (all read-only): first post-deploy tick `TICK_COMPLETE` for the live
activations with unchanged provider-call behaviour; `collection-status` returns
`MANAGED_UNMANAGED` (default-off proven live); the four empty `managed_*` tables exist;
B timer still armed with the same identity.

Compatible rollback: before the first managed child exists, redeploy the previous artifact
(the tables are additive and unused). After managed children exist the binary must not go
below `M`: older code rejects derived child authority; use a forward fix. Policy rollback
is `collection-rollback`, never a binary downgrade.

## 2. Plan (read-only) — the parent proposal

Template = B's registered schedule (same family as A; read its full hash from the store).
Storage basis = A's frozen commissioned envelope (or B's after it activates).

```text
observation_schedule.py collection-plan \
  --template-schedule-sha256 <B schedule sha256> \
  --account-scope-id JUPITER-MANAGED-ACCOUNT-1 \
  --storage-basis-activation-id ACT-4744D4017AC4B196 \
  --protected-bridge-activation-id ACT-A26CF9B0815A36F2 \
  --bootstrap-not-before 2026-10-18T00:00:00Z \
  --validity UNTIL_REVOKED --planning-horizon-days 180
```

Defaults reproduce the running numbers: 100/day (the template ceiling), rolling 100, active
cap 400, calls/credits 1200/1200 per UTC day, cumulative 2,000,000, cash 0, no retry, no
fallback. Inspect before asking for the phrase:

- `terminal=MANAGED_PLAN_READY`, `refusals=[]`, `authority_status=PROPOSED_NOT_AUTHORITY`;
- `capacity.provider_calls_per_day_lower_bound=426`, `steady_state_active_episodes=300`
  (a lower bound, not a measured forecast);
- `bootstrap_not_before` is at or after the stop of B (`HANDOVER_BEFORE_PEER_STOPS` would
  refuse otherwise); the controller therefore creates nothing on 17.10;
- the profile limits equal the frozen A/B budgets; any difference stops the packet;
- `validity.mode=UNTIL_REVOKED` is a **new** standing-grant semantic, not an extension of
  the A/B grants; the owner sees it in the phrase text.

Show the owner, next to the phrase, the values the phrase only binds through its hash:
`bootstrap_not_before`, `hard_bytes`/`target_bytes`, `backup_max_age_seconds`, the protected
bridge and the template schedule hash (all printed in `profile` by `collection-plan`). The
owner approves numbers, not a hash.

Resource inputs that must be decided in the same gate: the target acceptance (none by
default: the controller then blocks new intake at TARGET 40 GiB and never forges PASS),
the backup receipt maximum age (default 30 h) and the measured growth bytes/day (unknown
until measured; runway then reports `UNKNOWN_GROWTH_NOT_MEASURED` and recommends the I2
action).

## 3. Apply (authority: exact owner phrase for this one profile revision)

```text
observation_schedule.py collection-apply <same args> \
  --expected-proposal-sha256 <proposal_sha256> --phrase "<exact_owner_phrase>"
observation_schedule.py collection-record-backup --checkpoint-at <UTC> \
  --artifact-sha256 <hex> --coverage <label>
```

This is the single owner approval for every technical step inside the profile: derived
child register, authorize, activate, recovery and tails. There is no further approval per
child. Re-record the backup receipt after every verified remote checkpoint (daily). A step
that wires this record call into the existing backup unit is a unit change and needs its
own OPERATE decision; until then the OPERATE agent runs it.

Acceptance: `MANAGED_APPLIED revision=1`; `collection-status` shows `grant.state=VALID`,
`current_intake=null`, no open incident, `RECONCILE_WAIT_BOOTSTRAP_NOT_BEFORE` on the next
tick. A, B, their authority receipts and the armed timer are byte-identical to the
readback of phase 0.

## 4. First managed boundary (read-only observation)

17.10 03:20:30 MSK: B runs on its existing timer (readback only: `ACTIVE`, member of the
shared account, source to publication, A tail). 18.10 00:00 UTC (03:00 MSK): B stops
admitting; the next ordinary tick drains B and then derives, authorizes and activates the
first child in the same invocation. Acceptance:

- one `managed_children` row for `2026-10-18`, state `ACTIVATED`, one derived receipt
  (`authority_basis=STANDING_GRANT`), `starts_at` within one tick of the B closure;
- A and B tails keep ticking; shared usage equals the independent sum of member counters;
- no incident; no manual registration; the next UTC boundary (19.10) repeats this without
  any owner action: the second boundary is the real autonomy acceptance;
- `LIVE_PENDING_FIRST_CUTOVER` until then; `MANAGED_CONTINUITY_LIVE_PROVEN` only after the
  19.10 boundary and one ordinary backup cycle.

## 5. Alerts acceptance (authority: the existing operability watch)

Use the existing TEST path of the unattended operability runbook
(`docs/operator/FACTORY_UNATTENDED_OPERABILITY.md`, incident/recovery proof) to send one
message marked TEST and read the transport delivery back. Do not damage the collector to
prove an alert. Managed incident codes reaching the watch: `MANAGED_INTAKE_BLOCKED`,
`MANAGED_INTAKE_HELD`, `MANAGED_INTAKE_OWNER_MISSING`, `MANAGED_GRANT_INVALID`,
`MANAGED_CHILD_STEP_FAILED`, `MANAGED_RECONCILE_ERROR`. A lost VPS stays
`HOST_LOSS_ALERT_UNPROVEN` unless an external receiver is separately commissioned.

## 6. B stand-alone timer cleanup (authority: separate narrow operational decision)

Only after B's outcome is confirmed `ACTIVE` then closed and the first managed child holds
the day: the one-shot `factory-i3-b-activate.service/.timer` may be removed. It is an
idempotent replay source until then. This is not a Git change.

## Stop, resume and rollback (commands)

```text
observation_schedule.py collection-stop-intake --expected-revision R    # new intake only; tails continue
observation_schedule.py collection-rollback --to-revision N --expected-revision R [--phrase "<exact>"]
observation_schedule.py collection-plan/apply ...                       # resume = a new approved revision
```

`--expected-revision` is mandatory (read `collection-status`). A rollback needs no phrase only
when nothing it restores is wider than the current revision (limits, end date, routes, hard/
target bytes, backup age, acceptance); otherwise the exact phrase of the new revision.
`collection-record-backup` makes the OPERATE agent the attester: read the checkpoint time, hash
and coverage from the existing backup owner's verified output; any 64-hex value would be
accepted by the code.

## Stop conditions

Any of: a refused plan axis, an unresolved restore marker, a backup receipt that cannot be
produced, B not started when expected (the controller reports it; it never claims it
started), a same-family window the controller did not create overlapping a managed day,
`RECONCILE_BLOCKED_MANAGED_GRANT_*`, or any request to raise limits, lift the 100/day
ceiling, change provider entitlement or delete data. Each needs a new exact owner decision.

## Runway dependency

I3 does not apply I2 packaging. `MONTHS_RUNWAY_SUPPORTED` is not claimed. The plan and
status report resident bytes, new bytes/day (unknown until measured), upload per day,
remote retained bytes and peak transient bytes, with expected I2 savings counted as zero.
One next I2 action is named by the runway block when growth is unknown or short of the
horizon.
