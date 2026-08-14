# Delivery finish

For the exact task contract and candidate fingerprint under
`DELIVERY_HARNESS_V1`, run
`scripts/delivery_harness.py check`, proportional Factory Fit, Product Horizon,
capability radar, exact inventory and targeted checks. Prepare the PR/read-back.
Stop once for exact PR/head owner approval; only then let the guarded merge
execute the elected project-bound gate once via
`scripts/owner_attention_gate.py --guarded-merge`. It reads live PR/check/review
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
