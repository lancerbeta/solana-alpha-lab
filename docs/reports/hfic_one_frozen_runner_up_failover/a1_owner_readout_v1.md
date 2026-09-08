# Owner readout — HFIC_ONE_FROZEN_RUNNER_UP_FAILOVER_V1

## Terminal

Fresh HFIC-V1.2 freeze emits two Critic packets before Critic #1: C1 primary
and C2 runner-up, same session / epoch / search, same `prior_memory` snapshot.
A final primary `KILL_*` parks `RUNNER_UP_AWAITING_CRITIC` and screens that
exact frozen C2 once. C2 is no longer mechanically discarded. This is not
alpha and not promotion.

## What landed

1. Freeze builds the C2 critic packet before Critic #1. Same `session_id`.
   Isolated Critic #1 does not see C2.
2. Final C1 `KILL_*` (including after C1 `REVISE_ONCE`, and classifier-mapped
   KILL while still on C1) persists C1 REJECT and resumes as `RESUME_CRITIC`
   on the frozen C2 packet. Non-KILL does not failover.
3. Receipt v1.3 keeps Forge `selected_candidate_id=C1`. Legacy `critic_*`
   stay C1-bound. C2 lives in additive `runner_up_*` / `final_*`.
   `show_session` exposes `final_session_terminal` and
   `runner_up_critic_terminal`. Do not read C1 KILL as C2's evening result.
4. C2 `REVISE_ONCE` keeps the critic artifact terminal `REVISE_ONCE` and maps
   the session to `PAUSE` / `RUNNER_UP_REVISION_REQUIRED`. No C2 revise, no C3.
5. Missing C2 artifacts fail closed on load and `prove_runtime`. Fresh V1.2
   cannot strip the C2 SHA. Historical stored sessions without that SHA stay
   one-shot KILL.

## Explicit non-claims

- Not scientific DONE. Not alpha.
- No N-candidate tournament. No second AUTO search. No Prompt A. No ranker
  change. Critic packet `1.3` / `prior_memory` semantics unchanged from F2.
- Calibration-memory rebase is still residual.

## NEXT

Exact-head CI, then merge-readiness, then one owner merge phrase. The owner does
not click GitHub Merge.
