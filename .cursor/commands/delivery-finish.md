# Delivery finish

For the exact task contract and candidate fingerprint under
`DELIVERY_HARNESS_V1`, run
`scripts/delivery_harness.py check`, proportional Factory Fit, Product Horizon,
capability radar, exact inventory and targeted checks. Prepare the PR/read-back.
Stop once after exact-head CI **and** `--merge-readiness`
`ready_for_owner_phrase: true` for exact PR/head owner approval; the owner never
clicks GitHub Merge. Order:
`CI -> merge-readiness PASS -> owner phrase -> guarded-merge -> post-merge-readback`.
Product work uses `--contract`. `context --pr` is `LIVE_PR_HEAD` only inside
`harness_control_write_prefixes`; a product path is `IDENTITY_MODE_MISMATCH`.
Do not widen those prefixes. Control work with a task contract still uses
`--contract`. Last content commit then `bind-evidence --apply` then
`--merge-readiness` then phrase.
Only then let the guarded merge execute the elected
project-bound gate once via
`scripts/owner_attention_gate.py --guarded-merge`.
It reads live PR/check/review
state and bound Factory-Fit evidence itself; never pass hand-asserted green
booleans. Verify the profile's exact default branch plus post-merge CI afterward.
Require `delivery_gate_ready=true`; the guard executes the project-profile
commands, requires a base-bound exact PR-CI identity and never trusts an
already-written local PASS receipt.
The guarded-merge receipt's `merge_commit` is the expected default-branch head.
Persist that self-hashed receipt and pass it back through
`--submission-receipt <GUARDED_SUBMISSION_JSON>`; completion requires a
successful hash-bound `--post-merge-readback` receipt for that exact head and
ordered frozen-base/approved-head parents; poll CI read-only without
another owner interruption.
