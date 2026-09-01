---
name: delivery-harness
description: Use for bounded Git-native repository delivery from exact task context through guarded merge read-back.
---

# Delivery Harness

Run `CHECK -> CONTEXT -> EXECUTE -> REVIEW -> FINISH -> MERGE GATE -> READ-BACK`.
Require one exact task contract and explicit missingness. Keep routine work
autonomous; stop only for material authority or the exact PR/head merge gate.
Use targeted checks during work. After bootstrap, guarded merge is the sole
project-bound gate executor per unchanged fingerprint and consumes existing
exact-head PR CI; do not duplicate a pre-PR local full gate.
Git is project memory; cloud export is optional and owner-managed.
Require `delivery_gate_ready=true` before FINISH. Null project validation
bindings or an unbound PR-CI identity deny merge; bootstrap must bind existing
project-owned commands and the live workflow/job identity first.
Order: `CI -> merge-readiness PASS -> owner phrase -> guarded-merge -> post-merge-readback`.
Stop for the exact PR/head phrase only after
`scripts/owner_attention_gate.py --merge-readiness` reports
`ready_for_owner_phrase`. Product work uses `--contract`; `context --pr`
(`LIVE_PR_HEAD`) is refused with `IDENTITY_MODE_MISMATCH` when any changed path
is outside `harness_control_write_prefixes`. Do not widen those prefixes.
Control-shaped work with a task contract still uses `--contract`.
After cataloged script changes, repair derived hashes incrementally before commit:
`scripts/harness_sync.py --apply --base-ref <task expected_base>`.
Bare `--apply` is recovery/full oracle only.
Task-contract merge may land drifted `CONTROL_RUNTIME_PATHS` listed in that
task `managed_write_set`; unlisted runtime drift stays `CONTROL_RUNTIME_CHANGED`.
Last content commit then `bind-evidence` then `--merge-readiness` then phrase.
After the exact PR/head owner
phrase, use the repository-owned grounded merge
entrypoint; never replace its live checks with caller-supplied booleans.
The owner never clicks GitHub Merge.
Persist the self-hashed submission returned by guarded merge. FINISH is terminal
only after `scripts/owner_attention_gate.py --post-merge-readback
--submission-receipt <GUARDED_SUBMISSION_JSON>` emits a hash-bound receipt for
the same repository, PR, approved head, context route and merge commit.
