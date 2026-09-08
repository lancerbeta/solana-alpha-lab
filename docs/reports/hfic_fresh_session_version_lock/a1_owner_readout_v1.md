# Owner readout — HFIC_FRESH_SESSION_VERSION_LOCK_V1

## Terminal

`FRESH_SESSION_DRAFT_VERSION_MISMATCH` on current `START_NEW_SESSION` / `HFIC-V1.2` plus a newly generated V1.1 draft. AUTO slot remains `START_NEW_SESSION`. Historical V1.1 freeze without that preflight stays readable.

## What landed

Fresh-session protocol identity only:

1. Machine guard `_reject_stale_fresh_session_draft` on the real freeze path (`freeze_draft` and `bind_preflight_receipt`). Current `START_NEW_SESSION` with `prompt_version=HFIC-V1.2` requires `packet_version=1.2` and `generator_prompt_version=HFIC-V1.2`. No auto-upgrade.
2. Canonical START_NEW_SESSION instructions (Forge SKILL step 3, operator Prompt A fallback / A13 / A14) now emit the V1.2 draft schema. Critic Prompt B remains `HFIC-V1.1`.
3. T1–T6: typed denial; rejected freeze does not persist session/candidate records; V1.2 freeze keeps grounding; historical V1.1 readable; instruction regression; current happy-path tests use V1.2.

## Explicit non-claims

- No rewrite of historical V1.1 RDP records.
- No Critic V1.1 identity redesign.
- No change to prior recall, runner-up lifecycle, classifier, experiment, providers, or active RDP.
- Residual F2 prior-recall blind spot and F3 runner-up gap remain out of scope.

## NEXT

Exact-head CI, then merge-readiness, then one owner merge phrase. The owner does not click GitHub Merge.
