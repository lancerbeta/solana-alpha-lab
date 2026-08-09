# Project Sources releases

Start here when a task needs to understand, prepare or activate permanent
Project Sources. `release_registry_v1.yaml` is the only discovery index for
repository-authored releases; do not choose a bundle by directory name or
recency.

The registry keeps two intentionally different facts:

- `active_ui_release_id` is the Source set actually activated in the cloud UI;
- `latest_candidate_release_id` is a repository-validated set that still
  requires the owner's separate UI replacement and seven-role smoke.

Git, a pull request and CI can validate a candidate but cannot activate cloud
Project Sources. A release becomes active only after the owner records the
exact manifest-first smoke in a follow-up activation receipt.

## Prospective combined close

After a release candidate is merged and the owner has replaced the five
mutable Project Sources, one exact terminal may carry both owner-owned facts:

```text
TASK<NN>_SOURCE_SMOKE=PASS; OWNER_DONE_ACCEPTANCE
```

The clauses remain independent: a smoke PASS never implies task DONE, and
`OWNER_DONE_ACCEPTANCE` never activates an unverified Source set. Either
missing clause fails closed. Both facts may be recorded in one combined activation-and-close receipt
and one close PR only when
`CONTROL_ONLY_TASK_CLOSE_FAST_PATH_V1` admits the exact committed write set.
Any broader or failed candidate returns to the tracked-only delivery preflight.
Historical releases and receipts are never rewritten into the combined form.

## Working rule

At Entry Gate, read the registry before relying on permanent Sources. At Finish
Gate, each new or changed acceptance receipt declares one disposition:

- `NO_CHANGE` — no permanent Source update;
- `RELEASE_CANDIDATE` — one registered candidate with an exact release ID; or
- `ACTIVATION_RECEIPT` — the separate owner smoke has activated a release.

Historical release bytes are retained for rollback. Do not create loose
directories below `releases/`, overwrite a release, or delete a superseded
release. If the registry reports `COMPACTION_REVIEW_REQUIRED`, design a
separate retention change before moving or deleting anything.
