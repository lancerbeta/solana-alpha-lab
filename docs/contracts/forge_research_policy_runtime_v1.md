# Forge research-policy runtime V1

Owner: `FORGE_RESEARCH_POLICY_RUNTIME_V1`.
Consumers: the ordinary-operation MAIN/ADAPTIVE/PREVIEW gate, AUTO-cycle and
distinct-focus admission, temporal-look classification, the candidate draft
and session-receipt schemas, the `episode-normalized-view` PREVIEW gate, the
formulation packet and the `research-policy-*` CLI surface. This document
grants no scientific, provider, deployment or merge authority. A policy change
is a budget ceiling; it is never a scientific look, a return result or
strategy promotion.

## Three owners

| Owner | What it holds | Moves when |
|---|---|---|
| Git | shipped defaults, ranges and hard fuses (`DEFAULT_LIMITS`, `FIELD_RANGES`) | only by a reviewed code change |
| ResearchStore active policy `FORGE_RESEARCH_POLICY_V1` | limits and presets for **new** runs | the owner applies a CAS-checked change; never blocked by an open operation |
| ResearchStore frozen scope `FORGE_RESEARCH_POLICY_RUN_SNAPSHOT_V1` + `FORGE_RESEARCH_POLICY_RUN_EXTENSION_V1` | one scope's limits at its first real touch, plus an explicit append-only extension chain | snapshot: once, first writer wins; extension: only an explicit owner-authorized change of exactly that scope |

Changing the active policy never moves a scope that is already frozen.
Freezing a scope never resets what any other scope has spent. An extension
never resets what *this* scope has already spent: spend is computed
independently, from completed looks and pending reservations, by the
ordinary-operation owner (`hfic_ordinary_operation.py`), not by the policy
module. A scope with history that predates this runtime freezes at the shipped
defaults (`LEGACY_DEFAULTS_V1`) and writes no policy artifact on a read-only
path.

## Scopes

| Scope | Key | Fields |
|---|---|---|
| `JOURNAL` | the search key | `main_total`, `adaptive_total`, `preview_total`, `simple_before_compound`, `max_generated`, `max_diagnostic_slices` |
| `EPOCH` | `EPOCH:<market evidence epoch>` | `auto_cycles_per_market`, `distinct_focuses_per_market` (one shared pool per market) |

A field offered to the wrong scope is refused (`RESEARCH_POLICY_FIELD_NOT_IN_SCOPE`).

## Limits

| Field | Default | Hard fuse | Governs |
|---|---|---|---|
| `auto_cycles_per_market` | 1 | 8 | AUTO cycles per market evidence epoch |
| `distinct_focuses_per_market` | 3 | 32 | distinct non-AUTO focuses per market epoch |
| `main_total` | 6 | 32 | MAIN looks per journal |
| `adaptive_total` | 2 | 8 | ADAPTIVE looks per journal |
| `preview_total` | 2 | 8 | PREVIEW looks (feature previews and value-bearing episode views) per journal |
| `simple_before_compound` | 3 | 32 | SIMPLE MAINs reserved before any COMPOUND |
| `max_generated` | 6 | 16 | candidates a draft may carry (minimum 1) |
| `max_diagnostic_slices` | 8 | 8 | disclosed diagnostic slices; may only be lowered |

`0` forbids new actions of that kind; it is not unlimited. No field may exceed
its hard fuse, regardless of preset or extension. This delivery raises no
shipped default; an absent policy resolves to exactly these defaults.

## Presets

Up to 16 named selector presets (`[a-z][a-z0-9_]{0,63}`, each ≤4 KiB, ≤16 KiB
policy total) are stored in the active policy. A preset carries
`population`, `hypothesis_kind` (`NUMERIC_IN_SCOPE`, `LIST_CONTRAST`,
`MIXED_LIST_NUMERIC`) and `research_scope`, optionally `representation_id`,
`list_condition`, `diagnostic_slices`, `label`. A preset is expanded
into a complete selector before it enters a draft; it never nests, never
enters the scientific identity, and a display name is never an identity.

## CLI

- `research-policy-status [--for-operation OP | --journal-scope K | --epoch-scope E]`: effective policy, frozen scopes, occupancy and open operations. Reads no market value and writes nothing.
- `research-policy-preview [limit flags] [--proposal-input FILE]`: a change of the active defaults for **new** runs (`applies_to: NEW_SCOPES_ONLY`).
- `research-policy-preview --for-operation OP [limit flags]`: an extension of the exact journal and market-epoch scopes of that open operation (`applies_to: THESE_SCOPES_ONLY`).
- `research-policy-apply --proposal FILE --confirm-append-only`: appends exactly the previewed change. Re-applying an already applied proposal returns `ALREADY_APPLIED`. A stale proposal is refused (`RESEARCH_POLICY_PREVIEW_STALE` / `RESEARCH_POLICY_EXTENSION_STALE`); a writer-busy store is retried a bounded number of times.
- `preflight --additional-cycle`: the one explicit way to start AUTO cycle 2. A plain preflight never starts a cycle.
- `episode-normalized-view --operation-sha256 OP`: a value-bearing prefix view is a PREVIEW. Its request descriptor is reserved before any value is read, the payload hash lands on the same reservation, and the identical request again spends nothing.

## AUTO 1 → 2

Cycle 1 is unchanged and keeps `SCIENTIFIC_SLOT_V1`. An explicit additional
cycle (`cycle_index` ≥ 2) adds `cycle_index` to the slot hash and uses
`cycle_search_key(search_key, cycle_index)` as its own journal, so it has its
own MAIN/ADAPTIVE/PREVIEW budget. Cycle 2 is admitted only when (a) the
market epoch's frozen pool allows it and (b) the owner passed
`--additional-cycle`. The pool is raised only by an explicit epoch-scope
extension; a bare raise of the active defaults does not widen a pool that is
already frozen. The third cycle is refused with
`SEARCH_BUDGET_EXHAUSTED`. A pending cycle resumes under the same flag. The
real cycle count comes from the stored cycle rows (`_auto_cycles`); child
representation rows are not counted. A second cycle must bring materially
different candidates: identical definitions are already recorded hypotheses
of cycle 1 and are refused as duplicates.

## Identity and integrity

The policy head hash, snapshots and extensions are an append-only chain.
Present-but-invalid state (broken chain, bad hash, wrong shape) is a typed
refusal (`RESEARCH_POLICY_CHAIN_CORRUPT` / `RESEARCH_POLICY_INVALID`), never a
silent fallback to defaults. Only an **absent** policy resolves to defaults.
Policy hashes and extension proposal hashes never enter `scientific_body`, a
scope rule or a market-evidence basis: this is execution provenance.

## Refusals an operator sees

| Code | Meaning | Next step |
|---|---|---|
| `RESEARCH_POLICY_LIMIT_OUT_OF_RANGE` | value is negative, not an integer, a bool, or above its hard fuse | use a value inside the range named in the refusal |
| `RESEARCH_POLICY_ALLOCATION_EXCEEDS_MAIN_TOTAL` | `simple_before_compound` exceeds `main_total` | lower the allocation or raise `main_total` in the same preview |
| `RESEARCH_POLICY_FIELD_NOT_IN_SCOPE` | an epoch field offered to a journal scope or the reverse | see `allowed` in the refusal |
| `RESEARCH_POLICY_CHANGE_EMPTY` | no limit flag and no proposal input | give at least one change |
| `RESEARCH_POLICY_PREVIEW_STALE` / `RESEARCH_POLICY_EXTENSION_STALE` | the policy or the scope moved since the preview | repeat the preview |
| `RESEARCH_POLICY_RUN_SNAPSHOT_MISSING` | the scope is not frozen yet | run preflight or create the operation, then preview again |
| `RESEARCH_POLICY_CONFIRM_REQUIRED` | apply without `--confirm-append-only` | retry with the flag |
| `RESEARCH_POLICY_PRESET_NOT_FOUND` / `RESEARCH_POLICY_PRESET_CONFLICT` | unknown preset, or an explicit field contradicts it | define the preset first or drop the conflicting field |
| `RESEARCH_POLICY_CHAIN_CORRUPT` | present-invalid policy state | stop and restore the store; there is no default fallback |
| `ORDINARY_OPERATION_NOT_FOUND` / `ORDINARY_OPERATION_STOPPED` | `--for-operation` names no open operation | copy the exact operation hash from status |
| `EXTENSION_PARENT_COMPLETED` | the run already completed | request a new segment with its final receipt |
| `EXTENSION_PARENT_HAS_PENDING_RESERVATION` | an action is pending | resume that exact action first |

## Known limits of this delivery

- A cycle-2 journal does not share cycle 1's MAIN spend; it has its own budget by design.
- Child representation of an additional cycle is not supported.
- A NO_WORTHY receipt for more than 6 candidates is still capped at 6.
- `max_generated` below 4 conflicts with the non-ordinary floor of 4 candidates; ordinary drafts use the policy value.
- Numerical replay of a prefix view is covered by the PR-A cold test, not repeated here.
- `repository_git_snapshot` hashes the whole worktree and all refs; external refs created during a run can fail a vertical test.

## Non-goals

No new collector, evaluator, database, service or dependency; no raised
shipped default; no change to VPS, canary, deploy or provider routing; no
scientific claim or strategy promotion from a policy change.
