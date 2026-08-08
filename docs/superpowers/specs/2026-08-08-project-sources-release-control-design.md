# Project Sources Release Control v1 — design

## Decision

Turn the TASK-27 A0-A5 source candidate into the first repository-tracked
Project Sources release (`PSR-0001-T27-A0-A5`) and add a deterministic CI gate
for source-release discoverability and task-level disposition.

This is a control-plane repair for repository-authored Source candidates.  It
does not activate cloud Project Sources, reconstruct missing historical
bundles, grant any provider or wallet authority, or alter TASK-27 research
scope.

## Problem

The A5 candidate is complete enough to be copied into the cloud UI, but its
current standalone directory has no durable answer to three questions:

1. which source set is actually active in the cloud UI;
2. which candidate is the next one the owner may activate; and
3. how a later task must explicitly decide whether it changes permanent
   Sources at all.

Without those answers, independently valid folders would accumulate while a
new operator or agent inferred recency from a path or filename.  That is not a
safe release process.

## Chosen design

Repository-authored candidates live only below one explicit release root:

```text
docs/project_sources/
  RELEASES.md
  release_registry_v1.yaml
  releases/
    PSR-0001-T27-A0-A5/
      canonical_manifest.yaml
      roadmap.md
      current_system_state.md
      task_archive_P0_P1_v37.md
      task_27_public_history_feasibility.md
      CHECKSUMS_SHA256.txt
      FRESH_CHAT_SMOKE.md
```

The existing A5 bytes are moved with Git history preserved.  `RELEASES.md` is
the human entry point; `release_registry_v1.yaml` is the machine-readable
discovery point.  No unregistered candidate directory is valid below
`docs/project_sources/releases/`.

The registry deliberately keeps two distinct pointers:

- `active_ui_release_id`: a release becomes active only after an exact owner
  UI replacement and seven-role smoke receipt is recorded;
- `latest_candidate_release_id`: the one validated candidate that may be
  activated next, but is not active merely because it is in Git or passed CI.

At this first release, `active_ui_release_id` is `null`.  The prior cloud
state is declared `PRE_REGISTRY_EXTERNAL_STATE`, because it cannot honestly be
reconstructed from absent historical release bytes.  The first candidate is
`PSR-0001-T27-A0-A5`; it starts in
`VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING`.

## Lifecycle and non-claims

Allowed release transitions are:

```text
VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING
  -> ACTIVATED_BY_OWNER_SMOKE
  -> SUPERSEDED

VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING
  -> INVALIDATED_BEFORE_ACTIVATION
```

There may be zero or one candidate, and zero or one repository-tracked active
release.  A superseded release remains byte-addressable and is never displayed
as current. Its `superseded_by_release_id` must name the active successor,
which in turn names it as `supersedes_release_id`. A candidate cannot be
described as active, and a repository or CI receipt cannot substitute for the
owner cloud smoke.

No automatic deletion is part of this design.  These are small text snapshots,
not raw provider data; their retained bytes provide rollback and explain why a
cloud Source set changed.  If aggregate release payloads exceed 50 MiB, the
registry reports `COMPACTION_REVIEW_REQUIRED`; that is a future explicit
design review, not permission to delete history.

## Mandatory task disposition

Semantic relevance of a task to permanent Sources cannot be inferred safely
from changed filenames.  It is therefore a required explicit decision in every
new or modified task acceptance receipt in a pull request:

- `NO_CHANGE`: the task does not change Project Sources; it may not add or
  alter a release payload or release registry;
- `RELEASE_CANDIDATE`: the task creates or changes exactly one registered
  candidate and binds its release ID, manifest and checksum hashes;
- `ACTIVATION_RECEIPT`: the owner has performed the separate UI replacement
  and seven-role smoke, and the registry records that receipt.

The check is deliberately limited to acceptance receipts changed after the
registry's `enforcement_start_commit`. On ordinary later PRs that is the PR
merge base; on this first transition PR it is the first policy commit, so
earlier A2–A4 receipts are not rewritten retroactively. The gate fails closed
if that baseline cannot be resolved in a delivery context.

## CI invariants

The deterministic release-registry test must reject:

- a payload directory absent from the registry, or a registry entry whose
  directory, manifest or checksums do not match;
- more than one pending candidate or more than one active release;
- an active pointer without an activation receipt;
- an invalid lifecycle transition or a candidate presented as active;
- a changed acceptance receipt without `project_sources_disposition`;
- `NO_CHANGE` alongside a source-release change; and
- `RELEASE_CANDIDATE` without the matching registered candidate.

The test uses only repository bytes, the Git merge base and synthetic
mutations.  It makes no cloud, provider, credential, wallet, signer,
transaction or cash action.

## Operating rule and recovery

`AGENTS.md` and the execution-router protocol will make the release registry a
mandatory Entry/Finish Gate read.  The obsolete rule that repository Source
completion bundles stay outside Git is replaced narrowly: repository-authored
release candidates belong in this registry; cloud UI activation remains outside
Git and is proven only by the owner smoke.

To recover from an unsuitable candidate, mark it
`INVALIDATED_BEFORE_ACTIVATION` with its reason.  To restore an activated
release, select its exact manifest/checksums, replace the five mutable cloud
roles, retain immutable roles unchanged, and run the seven-role smoke.  No
release bytes are rewritten or deleted.

## Scope

This patch moves the A5 candidate into the release layout, adds the registry,
schema/fixture/test, the current A5 receipt disposition, and the two protocol
rules. Their existing hash-bound Catalog records and generated navigation views
are propagated as a direct integrity repair. It does not backfill 27 historical
tasks, alter Project Sources in the cloud, or begin the next external-read
task.
