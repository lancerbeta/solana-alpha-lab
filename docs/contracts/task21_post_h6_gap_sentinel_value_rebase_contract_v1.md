# TASK-21 post-H6-gap sentinel value rebase contract v1

`T21-A6S_POST_H6_GAP_SENTINEL_VALUE_REBASE_V1` is a forward-only repair of the
current TASK-21 execution plan. It does not rewrite H0, H1, the explicit H6
gap, or any historical acceptance receipt.

## Why the repair is required

The accepted admission reconciliation permits exactly one outcome-blind
sentinel and budgets 24 quote calls across H24, H72 and H168. The prepared H24
and future-core implementations instead model three members at every
supplemental horizon: 24 calls per horizon and 72 calls in total.

At the repair point TASK-21 has used 52 external requests: 4 source requests
and 48 quote requests. After the H6 gap, the five remaining T2/T3 members need
up to 120 calls to satisfy the unchanged five-complete-member target. One H24
sentinel needs up to 8 more calls. The bounded worst case is therefore
`52 + 120 + 8 = 180` under the immutable outer cap of 192, leaving 12 requests
of operational headroom. Mandatory H72/H168 calls do not fit that proof.

## H24 becomes a minimum-age observation

H24 keeps one sentinel selected before quote outcomes by
`first_reliable_available_at`, `observed_at`, `nomination_event_id`. Capture is
forbidden before the latest immutable H0 trigger plus 86,400 seconds. There is
no ten-minute expiry: a later foreground run records its exact elapsed seconds
and remains an H24-plus supplemental observation.

Reaching the minimum age creates owner attention, not provider authority. The
exact H24 atom still requires a separate user provider gate and fresh recovery
health. If recovery is stale when the owner returns, recovery is refreshed
first; operator lateness alone is not converted into a fake data gap.

## H72 and H168 are not mandatory timers

H72 and H168 remain historical candidate horizons and the previously accepted
offline core remains available as non-runtime-bound evidence. Neither horizon
has an active gate, reserved calls, scheduler, deadline or required foreground
run after this repair.

Either horizon may be reconsidered only when a named hypothesis or consumer
needs persistence evidence, a fresh whole-task budget proof leaves headroom,
and the owner separately authorizes provider execution. The default timing
contract is minimum age plus recorded actual elapsed time. A narrow expiry
window is allowed only when the estimand causally requires a fixed clock band,
the width is justified, and the cost of missing it is accepted before capture.

## Scientific boundaries retained

The repair does not lower the five-complete-member target, the three-tranche
requirement, outcome blindness or the no-backdating/no-historical-rewrite
rules. Because all five future T2/T3 base members may now be needed, another
incomplete base member leads to `EXTEND_EVIDENCE_OR_REDESIGN_DATA`; it is not
silently excused by a supplemental sentinel.

## Authority and non-actions

This atom is `LOCAL_WRITE_ONLY`. It performs zero network, provider/API/RPC/WSS
or Drive calls; zero admissions, live capture, provider credits or cash spend;
zero credential, scheduler, deployment, wallet, signer or transaction actions;
and zero commit, push, PR, merge, UI or destructive actions. Catalog remains
unchanged pending `T21-A7`.
