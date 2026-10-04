# Forge ordinary operation lifecycle repair

Before this repair a `SCIENTIFIC_TERMINAL` Forge operation could never leave `OPEN`. The research-universe profile cannot be applied while any operation is open, so one such run blocked the 50 holders / $5k activation permanently. On 2026-10-04 the live store showed exactly that: one run already had its owner-final receipt and two unfinished runs needed an active profile to continue.

Now an operation finishes in one of two ways, and neither touches science:

- **Completed.** A run that reached its owner-final releases its operation once `forge-run --persist` has saved the owner-final receipt. Nothing new is recorded; the existing receipt is the proof. The receipt must belong to the same focus, market, slot and journal and be newer than the operation.
- **Stopped by the owner.** `operation-stop-preview` names one exact operation, `operation-stop --confirm-append-only` records the stop. A stop is not a negative result. Saved results stay, spent looks stay spent, an unfinished attempt stays counted, and the operation admits no new look.

`universe-policy-status` lists each operation that still blocks the profile with its exact next step. A coverage preview that must be refused is now refused before any market value is read.

Read-only check against the live store with the new code (no writes): `76b57b42…` (EARLY_DECAY_AVOIDANCE) reads `COMPLETED` from receipt `HFIC-ART-FORGE-RUN-F6BB5F1A43D131A7`; `2d813631…` (EARLY_WINDOW_PATH_STATE_TRANSITION, older market) and `fc74807c…` (AUTO, one unfinished attempt) stay `OPEN` and need an owner stop. Inventory `15ea38b4…` unchanged.

This atom changes no live data, activates no profile and takes no look.
