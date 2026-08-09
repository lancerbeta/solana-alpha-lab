# CONTROL_ONLY_TASK_CLOSE_FAST_PATH_V1 Design

## Goal

Reduce the routine close of a task with an already merged Project Sources
release from two follow-up repository transactions and two local full-suite
runs to one owner terminal, one close PR, one small local deterministic gate,
and the existing exact-head PR/main CI gates.

This changes control-plane throughput only. It does not weaken research,
Source identity, Catalog integrity, GitHub CI, merge, or canonical-DONE truth.

## Measured problem

TASK-28 exposed the repeated path:

1. merge the Source release candidate;
2. owner replaces five mutable Project Sources and reports a seven-role smoke;
3. repository records activation in one transaction;
4. owner separately accepts canonical DONE;
5. repository records close in another transaction;
6. each delivery repeats an approximately seven-minute tracked-only full gate,
   then exact-head PR CI and post-main CI.

The second repository transaction adds no new release bytes or research truth.
Its only material inputs are the already completed owner smoke and the task
acceptance decision. Clean-checkout risk remains independently covered by
GitHub CI on the exact pushed head.

## Chosen design

### 1. One terminal owner phrase

For a future task whose Source candidate is already merged, the owner may
return one exact terminal containing both facts:

```text
TASK<NN>_SOURCE_SMOKE=PASS; OWNER_DONE_ACCEPTANCE
```

The two clauses stay semantically separate: the first activates the exact
seven-role set, the second accepts the exact task outcome. Either missing
clause fails closed. A plain smoke never implies DONE, and a DONE phrase never
activates Project Sources.

### 2. One combined activation-and-close receipt

The repository records both clauses in one append-only receipt and changes the
release registry from candidate to active in the same close PR. The receipt
must bind:

- exact task and release IDs;
- manifest path and SHA-256;
- `OWNER_ATTESTATION` plus smoke `PASS`;
- task status `DONE` and canonical task-DONE boolean `true`;
- `next_task_selected=false`;
- zero provider, credential, R2/R3, wallet, signer, transaction, cash,
  dependency, and Project Sources UI actions by the repository transaction;
- Factory Fit `PASS` or `PASS_WITH_LIMITATIONS`;
- `ACTIVATION_RECEIPT` disposition for the exact active release.

Historical candidate, activation, close, and release bytes remain immutable.
The fast path applies only prospectively.

Prospective combined receipts keep
`schema=smial.project_sources.activation.receipt` and add an exact
`owner_terminal` object with `source_smoke`, `done_acceptance`, and
`reported_terminal`, plus generic `decision.canonical_task_done=true`. This
avoids adding task-number-specific parser branches.

### 3. Machine-classified local fast path

Add a deterministic `CONTROL_ONLY_TASK_CLOSE` validator. It compares the exact
committed candidate with `origin/main`, requires a clean tracked worktree, and
rejects the fast path unless every changed file belongs to the following
closed set:

- one new combined receipt below `docs/evidence/task*/`;
- `docs/project_sources/release_registry_v1.yaml`;
- Catalog hash bindings and generated Catalog consumers required by that
  receipt (`catalog/assets/core.yaml`, `catalog/assets/lifecycle.yaml`,
  `catalog/catalog_manifest.yaml`, `catalog/generated/asset_edges.json`, and
  `docs/PROJECT_MAP.md`).

The close diff may not change product code, tests, schemas, contracts, release
payload bytes, validation policy, dependencies, hooks, workflows, or task
meaning. A diff outside the closed set falls back to the normal tracked-only
delivery preflight; it is never auto-waived.

The local fast-path gate performs diff/identity checks, combined-receipt
semantics, registry semantics, Catalog/hash/generated consistency, secret
scan, and whitespace/diff checks. GitHub PR CI remains the sole full-suite
owner for this exact fast-path head. Post-merge exact-main CI remains
mandatory. No check failure can be overridden by owner attention.

The discoverable command is:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --control-only-task-close
```

The existing `--tracked-only-delivery` command remains the fail-closed fallback.

### 4. Owner and merge flow

The owner is interrupted only for the Project Sources UI replacement and the
combined terminal phrase. After that, LOCAL_WORK_CODEX may create the close
commit/PR and use the existing owner-attention machine gate. An ordinary merge
remains autonomous only after exact-head CI, mergeability, review, write-set,
secret, Factory Fit, branch-preservation, and settings invariants pass.

## Alternatives rejected

1. **Keep the current two receipts/two PRs.** Safest by inertia, but duplicates
   a decision transaction and a seven-minute local gate without adding truth.
2. **Skip all local validation for control-only closes.** Faster, but a typo in
   the receipt, registry, or Catalog would consume remote CI as the first
   falsifier and increase repair churn.
3. **Generic “small diff” shortcut.** Rejected because line count does not
   identify semantic risk; a one-line schema, workflow, or safety-policy change
   can be material.

## Implementation boundary

The implementation may change only:

- `AGENTS.md` and `docs/project_sources/RELEASES.md`;
- one versioned policy under `control/`;
- one focused validator module plus the option wiring in
  `scripts/validate_ci.py`;
- focused tests for classification, receipt semantics, and CLI routing;
- the existing Project Sources release-registry test only to remove the
  current-active-release hard-code while retaining historical assertions;
- one design and one implementation-plan document;
- Catalog records and generated consumers strictly required to register the
  new durable policy/validator/test assets.

No existing receipt, release payload, task contract, research module, provider
route, dependency, hook, or GitHub workflow may change.

## Success, observation, and rollback

Mark the patch effective only if the next three eligible task closes:

- use one combined owner terminal and one close PR each;
- need no repair commit caused by Source/registry/Catalog/clean-checkout drift;
- pass exact-head PR CI and exact-main post-merge CI;
- reduce local close validation to under two minutes per close.

Disable the fast path and return to the normal tracked-only preflight after any
false eligibility classification, missed drift, remote-only failure that the
local gate should have caught, or change to the closed write set. Rollback is a
policy/config reversal; no historical receipts or release payloads are deleted.

## Non-claims

- No provider/API/RPC/WSS, credential, R2/R3, wallet, signer, transaction,
  deployment, release, or cash authority is created.
- The patch does not select or start TASK-29 or any research trial.
- PASS does not make an unactivated Source candidate active and does not make
  an unaccepted task DONE.
- The fast path does not apply to task implementation, Source release creation,
  data collection, schema changes, dependency changes, CI changes, or repairs.

## Factory Fit and Product Horizon

`FACTORY_FIT_REVIEW=FULL_REVIEW` because validation and Source-close policy are
cross-plane controls. Expected verdict is `PASS_WITH_LIMITATIONS`: the design
removes repeated ceremony while retaining independent full CI, but it must earn
continued use over three real closes.

`NOW`: implement only this close-path classifier and combined-receipt contract.

`WATCH`: before the next historical-data route, run an evidence-backed
ADOPT-WRAP-FORK-BUILD review of mature sparse-market ingestion patterns and
official/reusable tools. Trigger: the next data Entry Gate. This design records
the trigger but does not research or adopt a provider/tool itself.
