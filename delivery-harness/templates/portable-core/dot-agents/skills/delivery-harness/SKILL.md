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
After the exact PR/head owner phrase, use the repository-owned grounded merge
entrypoint; never replace its live checks with caller-supplied booleans.
The owner never clicks GitHub Merge. Harness or control PRs use
`scripts/delivery_harness.py context --pr` (`LIVE_PR_HEAD`) instead of a
product task contract.
Persist the self-hashed submission returned by guarded merge. FINISH is terminal
only after `scripts/owner_attention_gate.py --post-merge-readback
--submission-receipt <GUARDED_SUBMISSION_JSON>` emits a hash-bound receipt for
the same repository, PR, approved head, context route and merge commit.
