# CI_RECOVERY_TRIGGER_V1 — Design

## Purpose and decision

GitHub Actions lost the `push` and `pull_request` webhook for merge commit
`4a807afddc183241781479d9595a038d60411073` during the GitHub Actions outage
of 2026-08-06. The workflow is active and its normal triggers are correct, but
no run exists to retry. The project needs a narrowly scoped recovery path that
does not add a no-op commit or weaken the validation job.

The selected design adds a parameterless `workflow_dispatch` trigger to the
existing Repository validation workflow. It lets an authorized repository
operator start exactly the same read-only validation job after a lost GitHub
event. It is a CI recovery control, not a release, deployment, or task-status
mechanism.

## Considered approaches

1. Add one parameterless manual trigger to the existing workflow and extend
   the fail-closed workflow validator to admit exactly that shape. This is
   selected.
2. Create an empty commit solely to produce a `push` event. Rejected: it adds
   meaningless repository history and leaves the next outage unresolved.
3. Add scheduled or repository-dispatch automation. Rejected: both broaden
   the event surface and create executions that are unrelated to a specific
   recovery need.

## Workflow contract

The only trigger addition is:

```yaml
workflow_dispatch:
```

It has no inputs, secrets, environment selection, token override or privileged
permissions. `pull_request` and `push` on `main` remain unchanged. The single
`validate` job, immutable action pins, `contents: read`, disabled credential
persistence, full fetch depth, timeout, concurrency behaviour and existing
validation command remain byte-for-byte equivalent apart from the accepted
trigger set.

GitHub limits manual dispatch to actors with repository write access. The job
itself still receives only read contents permission and has no project secret,
provider, wallet, transaction, deployment or cash capability.

## Validator and test contract

`scripts/validate_ci.py` will change from a blanket prohibition of
`workflow_dispatch` to an exact expected workflow that permits the one empty
manual trigger. It continues to reject:

- `pull_request_target`;
- any `workflow_dispatch.inputs` mapping or additional trigger;
- secrets references, write or id-token permissions;
- unpinned or additional actions, caches and artifacts;
- checkout, timeout or concurrency drift.

Tests use the real workflow validator. The first regression test will prove
that the current validator rejects the desired parameterless dispatch; the
minimal implementation then admits it. Separate negative mutations prove that
inputs and the existing dangerous patterns remain rejected.

The repository-state validator also has a runtime contract. A manual Actions
dispatch checks out its selected feature branch rather than the detached
pull-request merge ref. It therefore admits this third checkout shape only
when the checkout is clean, belongs to the expected repository, its Git ref
and local branch agree exactly, its SHA agrees with `HEAD`, and
`GITHUB_EVENT_NAME` is exactly `workflow_dispatch`. It uses the same current
dependency contract as main and pull-request CI. A feature-branch checkout
from any other event remains rejected.

## Catalog and generated consumers

`CI-WORKFLOW-001` and `CI-VALIDATOR-001` are durable, hash-bound assets. Their
record versions, purpose text, `as_of` fields and integrity hashes must be
updated together with the modified files. The Catalog version is incremented
and the generated project map and edge projection are regenerated rather than
edited manually.

No Project Sources role changes, schemas, dependencies, provider calls,
credentials, spend, wallet/signer activity, deployment or strategy logic are
in scope.

## Validation and recovery

The delivery candidate must pass targeted CI-workflow and Catalog tests, the
Catalog validator and generated-navigation check, followed by the tracked-only
delivery preflight. Its Draft PR provides the ordinary `pull_request` CI
evidence. After CI is healthy, one parameterless manual dispatch on the PR
branch proves the recovery path without touching `main`. Merge remains a
separate exact owner confirmation. If the manual dispatch does not create a
run, stop and report the GitHub-side gap; do not add empty commits or broaden
the workflow. A failure caused specifically by the baseline validator rejecting
the clean manual feature-branch checkout is an in-scope control defect: cover
it with deterministic baseline tests, extend only that exact runtime contract,
rebind its Catalog asset and repeat the same manual-dispatch proof.

Rollback is a normal revert of this small PR. It removes the manual entrypoint
and restores the previous exact validator contract without affecting data,
wallets, providers, deployment state or task truth.
