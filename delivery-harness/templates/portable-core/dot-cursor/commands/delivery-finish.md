# Delivery finish

Bind targeted evidence, run `--merge-readiness`, and stop for exact PR/head
approval only after `ready_for_owner_phrase: true`. Order:
`CI -> merge-readiness PASS -> owner phrase -> guarded-merge -> post-merge-readback`.
The owner never clicks GitHub Merge. Product work uses `--contract`.
`context --pr` (`LIVE_PR_HEAD`) is refused with `IDENTITY_MODE_MISMATCH` when a
changed path is outside `harness_control_write_prefixes`. Do not widen those
prefixes. Control work with a task contract still uses `--contract`.
Then let `scripts/owner_attention_gate.py --guarded-merge` execute the elected
project-bound gate once, consume existing exact-head PR CI and re-read live
merge facts before one standard merge; do not supply
pre-asserted green booleans. Treat its `merge_commit` as the expected default-branch head and
persist the self-hashed submission and finish only after
`scripts/owner_attention_gate.py --post-merge-readback --submission-receipt
<GUARDED_SUBMISSION_JSON>` emits a hash-bound receipt for that exact head,
ordered frozen-base/approved-head
parents and successful push CI.
CI propagation may be polled read-only; it never needs another owner approval.
Require `delivery_gate_ready=true` before opening the finish gate. Null or
invalid project validation bindings are a stable
`PROJECT_VALIDATION_BINDING_REQUIRED` stop, never a reason to trust a local
PASS file or substitute generic tests.
Validate the selected `DELIVERY_EVIDENCE` against
`catalog/schemas/delivery_harness_completion_evidence.schema.json`; project-only
checks belong in its `project_checks` list rather than widening the portable
contract.
