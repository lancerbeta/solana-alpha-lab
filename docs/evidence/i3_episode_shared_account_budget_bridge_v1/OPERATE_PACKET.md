# I3 shared-account budget — OPERATE packet

Status: `PREPARED_NOT_EXECUTED`. A software merge does not authorize any step
below. Each numbered phase needs the exact separate OPERATE authority named in
it. Host paths stay logical (`SOURCE_REPO`, `DATA_ROOT`, `OPS_STORE`); see the
existing remote-ops runbook for the transport.

## 0. Preconditions (read-only, fail-closed)

1. Exact artifact `M` = the guarded merge commit of this PR on `main`, with green
   post-merge CI. No hybrid tree, no cherry-picked files.
2. Fresh read-only production readback (sqlite `mode=ro`, `query_only`):
   - A `ACT-4744D4017AC4B196` state (`ACTIVE` before 2026-10-17T00:00Z,
     `DRAINING` after), last transition id, authority `c2c937b4…`;
   - due backlog `0`, outbox `0`, latest admission/publication times;
   - restore marker resolved; timer active; renewal timer disabled;
   - today's `accounting_counters` and `lifetime_counters` for every
     `(schedule_sha256, activation_id)`; save this as `before.json` outside Git.
3. Fresh backup coverage bound to a checkpoint newer than the last debit
   (the preflight saw only an older off-host checkpoint; residual is open).
4. Collector-path files changed between installed `4378c5b8` and `M` are known:
   `observation_schedule_store.py`, `observation_scheduler.py`,
   `opportunity_episode_tick.py`, `observation_account_budget.py`,
   `scripts/observation_schedule.py`, `observation_schedule_compiler.py`,
   `research_store.py`, `live_cohort_vanilla_path.py`,
   `opportunity_episode_release.py`, `live_cohort_source_bundle.py`,
   `live_cohort_to_forge.py`, `trading_runtime_policy.py`. Record their SHA256 at
   `M` in the deploy receipt (runtime dependency fingerprint).

STOP if any item is UNKNOWN, if A is not ACTIVE/DRAINING, or if a backlog or
unresolved restore exists.

## 1. Deploy `M` (authority: exact producer deploy)

Ordinary canonical-forward release between timer ticks (bundle to
`SOURCE_REPO`, ff-only, `factory_live_release.py --mode canonical-forward`). The
release restores the prior timer state. No pause of A.

Acceptance:
- the first post-deploy tick returns `TICK_COMPLETE` with normal provider calls;
  A counters advance as before;
- `observation_schedule.py account-budget-status` returns
  `ACCOUNT_BUDGET_UNMANAGED` (live proof that the bridge is default-off);
- the three new empty tables exist (created by the collector's own open).

Producer V2 capture: `M` already contains the merged I1 V2 exporter. Verify
installed `live_cohort_vanilla_path.py` = `b9f5d0f5…` and
`opportunity_episode_release.py` = `ba60fdc1…` (this PR does not touch them).
Only then may a new mature C3+ capture/export claim V2 semantics. Saved C1/C2
consumption needs nothing. If the hashes differ: one named incompatibility, no
capture.

## 2. Prepare commissioning (read-only)

```text
observation_schedule.py account-budget-prepare \
  --account-scope-id JUPITER-MANAGED-ACCOUNT-1 \
  --provider-calls-per-utc-day-max 1200 \
  --modeled-credits-per-utc-day-max 1200 \
  --provider-calls-lifetime-max 2000000
```

The limits copy A's already approved schedule budgets. They are the approved
allocation, not a new provider entitlement. The owner confirms the logical
account id and these numbers in the OPERATE gate. Raising them is a later
`account-budget-revise`, never part of this packet.

Inspect:
- the three limits equal the frozen A schedule budgets read from the registered
  A document (`provider_calls_per_utc_day_max`,
  `modeled_provider_credits_per_utc_day_max`, `provider_calls_lifetime_max`);
  any difference stops the packet;
- `terminal=ACCOUNT_BUDGET_PLAN_READY`,
  `credential_locator=JUPITER_FREE_API_KEY`;
- `member_debits`: every activation of the store (A plus historical canary or
  legacy scopes; `COUNTER_SCOPE_WITHOUT_ACTIVATION` must be explained). Including
  history is the conservative period boundary;
- `shared_usage_at_prepare` equals the sum of `before.json` plus spend since then;
- `over_limit` is empty; cumulative use is far below 2000000;
- `coverage.external_callers=UNKNOWN`: other machines or scripts with the same
  key are outside this proof.

## 3. Apply (authority: exact commissioning)

```text
observation_schedule.py account-budget-apply <same args> --expected-plan-sha256 <plan_sha256>
```

Run between ticks. `WRITER_BUSY` means retry after the tick.
`ACCOUNT_BUDGET_PLAN_STALE` means prepare again (membership changed). A repeat
with identical arguments returns `ACCOUNT_BUDGET_ALREADY_APPLIED`; different
arguments return `ACCOUNT_BUDGET_REPLAY_MISMATCH`.

Acceptance:
- `terminal=ACCOUNT_BUDGET_APPLIED`, `mode=MANAGED`, `policy_revision=1`;
- A is bound as `COMMISSIONING`;
- `baseline_at_apply` equals an independent ro SQL sum over members, including
  A-tail spend made after prepare;
- frozen A schedule, grant, storage envelope and protection rows are unchanged
  byte for byte.

## 4. Live readback over ordinary ticks (read-only observation)

Watch the next ordinary A SEARCH/nomination ticks. Do not run a manual API smoke.
- per-activation counters and `account-budget-status.shared_usage` grow by the
  same amount;
- no duplicate `call_occurrence_id`; no `budget_denial`; publication backlog
  returns to `0`;
- the operability readout `account_envelope.status=MANAGED`.

## 5. Future B gates (NOT authorized by this packet)

- B needs its own exact register/authorize/activate authority, a fresh storage/
  backup commissioning, and a provider envelope with expiry >= its tail.
- Native late successor only: A reached natural `DRAINING` with append-only
  closure, `starts_at` >= closure, `activate` not before `starts_at`, no backdating.
- Readback after B activation: B member row `binding_source=NATIVE_ACTIVATION`.
  The mixed default tick lists A (DRAINING) before B. The shared limit is NOT
  raised for B.
- The half-day B proposal (`ACT-9D3327EB9C791265`, 2026-10-17 00:15–12:00Z,
  ≤49 admissions) is a rehearsal/fallback (`SHORT_BRIDGE_ONLY`), not the target
  operating model. Recompute one sustainable window after I2 measurements.

## 6. Rollback

| Moment | Allowed | Forbidden |
| --- | --- | --- |
| Before apply | ordinary code rollback to `4378c5b8` via the release tool (new tables stay empty and are ignored) | — |
| After apply | forward fix on `M`'s successor; policy rollback = `account-budget-revise` with the prior limits (debt kept) | binary or SQLite older than `M` (the old binary ignores the shared gate and the reset defect returns); restoring an older store over a newer one; any `UPDATE` of counters |
| Shared gate wrongly refuses A | stop B; keep A on compatible code; reconcile binding under exact OPERATE | resetting counters; silent decommission |

Decommissioning (removing the scope/policy/member rows to return to
`UNMANAGED`) has no supported command. It is an explicit owner decision with
exact authority, because it reopens the reset defect.

## 7. Stop conditions

Any UNKNOWN precondition, `CORRUPT` status, `unbound_live_activations` not empty,
a shared total above a limit, a changed frozen pin, a non-zero backlog after
deploy, or a first post-deploy tick that is not `TICK_COMPLETE`.
