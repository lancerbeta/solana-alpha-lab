# OPPORTUNITY_EPISODE_DISPATCH_WINDOW_REPAIR_V1

Status: deterministic RED and GREEN proved; isolated reviews and exact-head CI pending.

Exact base: `77eb427afbc9bb687c6a1fe3a7f3ca4ad2cf3417`, independently fetched
again after the owner expanded merge/deploy authority. The canonical VPS
deploy pin and installed timer were read back: same SHA, 60s active cadence.
No live provider request, activation change or scientific look occurred in repair.

Root: frozen tick-start due claims, one pre-intake sweep, 60s timer phase versus
60s dispatch window, and a blocking call ceiling of 60s. Whole-second episode
grid cutoffs also avoid SQLite TEXT ordering `...00Z` after `...00.178825Z`.
The exact send guard must run after pace/persistence and in the transport worker.

RED through exact-base owner + public production CLI, real admission/E0/store/
ledger/outbox/publication, only physical clock/transport authored:
entry `T-1.372118`, initial due scan pre-T, normal headroom work crosses
`T+0.178825`; first tick `TICK_COMPLETE`, E300 still PENDING, SEARCH=0.
Next pass `T+60.389428`: CENSORED/SLOT_NOT_EXECUTED, SEARCH=0, outbox=0.
Reproduce offline: `uv run --locked --managed-python python -B
docs/evidence/opportunity_episode_dispatch_window_repair_v1/red_replay.py`.

GREEN: same trace dispatches exactly one SEARCH in-window, publishes OBSERVED,
and the historical next late wake sends zero requests. Dedicated 13-test suite
also covers canonical timer-driven worst phase, exact deadline equality,
early/late no-send, no backfill, nomination-phase crossing, max-batch splitting,
durable STARTED and COMPLETED crash recovery, absent mint/HTTP500/TIMEOUT,
budget no-request gaps, pace crossing and worker start at deadline. Real worker
refusal completes a NO_REQUEST ledger row; a genuine crash stays UNKNOWN.
An out-of-model 63s clock jump stays visible and produces an honest typed gap.

Chosen invariant (conditional on finite ordinary runtime, never unbounded OS
latency): idle checkpoint gap `15s idle +1s accuracy +3*5s local=31s <60s`;
category-work gap `15s waiter +3s pace +5s local=23s <60s`. Same-assigned
batches share remaining deadline time, reserving 1s bookkeeping and 3s pace
for each remaining batch. Model test checks four max100 batches under worst
phase and strict send-start deadline. The existing waiter is not GIL preemption;
actual host stalls, insufficient budgets or capacity are genuine typed failures.
`max_dispatch_checkpoint_gap_seconds` exposes actual excessive in-tick work.

Changed operational semantics: 60s active timer becomes 15s after oneshot exit,
tight 1s accuracy and no random delay; episode call ceiling becomes 15s and
SEARCH allowance can be smaller to preserve other batches. This may classify
slow provider responses as TIMEOUT earlier. No retries/fallbacks. Nominations
retain the same 15m round identity, three sources, lottery/quota and E0 witness;
more idle wakes do not multiply category requests or admission budgets.

Compatibility: no store schema migration or frozen schedule mutation; producer
code SHA is lineage metadata, not activation identity. Deploy onto existing
ACT-2BFB07B6862365DF is compatible, but exact timer bytes must also be installed
and reloaded. Prior real E300 gap remains immutable; no backfill.

Validation so far: 81 focused production/episode/recovery/pre-start/remote-ops
tests passed; after final anti-happy-path additions, dedicated 13 tests passed.
Reproduce: `uv run --locked --managed-python python -B -m unittest
tests.test_opportunity_episode_dispatch_window_repair_v1
tests.test_opportunity_episodes_producer_v1
tests.test_opportunity_episode_round_recovery_v1
tests.test_episode_activation_before_start_v1 tests.test_observation_schedule_remote_ops -q`.
Full suite belongs to exact-head GitHub CI; no pre-PR local full gate.

Owner supplied live evidence: EP-95f653990f809a77b0f823ec95b0a3d5,
E300 [2026-10-07T00:55:00Z,00:56:00Z), missed at 00:56:00.389428Z.
The expanded authority permits guarded merge only on unchanged-head readiness
and its exact machine phrase, then canonical-forward deploy, exact timer reload,
and up to 20 minutes of naturally scheduled live proof. No manual probe,
new activation, legacy resume, renewal, credential/route change or cleanup.

Rollback: owner-authorized canonical rollback/revert of code plus installed timer;
preserve local/ and all durable evidence. Returning to the old cadence reopens
the known window coverage defect; no automatic rollback is warranted by a
provider's truthful missing result. Factory Fit FULL_REVIEW, radar NOW=NONE.
