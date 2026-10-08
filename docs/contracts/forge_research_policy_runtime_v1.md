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
path. Its first explicit extension freezes it there (the proposal carries
`freeze_legacy_defaults`), so an already-used market epoch or journal can be
raised; a scope with neither history nor snapshot is refused
(`RESEARCH_POLICY_RUN_SNAPSHOT_MISSING`). The formulation packet, the draft
validators and the gate read one resolver: an unfrozen journal reads exactly
what its first touch would freeze.

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
`cycle_search_key(search_key, cycle_index)` as its own **execution** identity
(slot, search key, session, operation). Cycle 2 is admitted only when (a) the
market epoch's frozen pool allows it and (b) the owner passed
`--additional-cycle`. The pool is raised only by an explicit epoch-scope
extension; a bare raise of the active defaults does not widen a pool that is
already frozen. The third cycle is refused with `SEARCH_BUDGET_EXHAUSTED`. A
pending cycle resumes under the same flag. The real cycle count comes from the
stored cycle rows (`_auto_cycles`); child representation rows are not counted.

**Accounting lineage.** Execution identity and accounting identity are
separate. A later cycle's operation carries `accounting_root` (the cycle-1
search key, printed in the cycle-2 preflight receipt) and a
`parent_operation_sha256` of an operation of the same lineage. It spends the
root's MAIN/ADAPTIVE/PREVIEW budget: limits are the root's frozen snapshot plus
its extensions, completed and pending spend are the union over the lineage, and
an exact query already saved in any journal of the lineage replays instead of
being a new attempt. So:

- cycle 1 used MAIN 6 of 6 → cycle 2 starts with 0 left, even after AUTO 2 is allowed;
- an explicit shared total (`research-policy-preview --for-operation <cycle-2 operation> --main-total 10`) raises the root, leaving 4;
- a cycle-2 operation is created only against the same market, focus and representation; the parent may be completed (that is how the search continues), never stopped and never with an unresolved reservation; a linked cycle freezes no budget of its own.

BASE and each representation (for example `NORMALIZED_TRAJECTORY_EPISODES_V1`)
keep separate budgets, and neither is merged with another focus, market or
population. Within one representation the continuation is the same search:
the episode child of a cycle-2 BASE session keeps its own execution identity
(journal keyed from the exact parent session's stored search key, its own
payload, scope and cycle slot) but its operation is linked at creation to the
single root operation of the same research line, which is (market, focus,
representation) with a BASE parent in the same or an earlier cycle
(`lineage_kind: REPRESENTATION_CONTINUATION`, `accounting_root` = that
child's journal). Another payload or selector in the same cycle is therefore
the same search too, not a fresh budget. It spends that root's budget: if the
cycle-1 normalized child used 2 of 6, the cycle-2 child sees 4 left, not a new 6;
an explicit normalized total of 10 (`--for-operation <child>`) leaves 8; BASE
is untouched. A new cycle, payload or selector never opens fresh budget by
itself. A stopped member of the lineage or an unresolved reservation refuses a
new segment, and an earlier cycle's child may not be recorded after a later
cycle's (`ORDINARY_OPERATION_LINEAGE_OUT_OF_ORDER`): the continuation runs
forward, so one representation never holds two independent budgets. The child of a cycle-2 parent is not an AUTO cycle, so the AUTO
count stays at the pool. The root decision is serialized by the ResearchStore writer lease: the operation commit re-derives the
representation line under the lease, so two concurrent first variants leave exactly one root, and a stop,
a pending reservation or a competing commit between the decision and the commit refuses or replans the
new segment (no orphan budget can be spent from: spend resolves through the line's root).
A BASE lineage row counts only when its journal is
`cycle_search_key(accounting_root, cycle_index)`: a request naming another root
is refused and can neither borrow nor poison any budget. An exact episode query
already saved anywhere in the lineage is a replay (the episode collection's
single calculation version is current), never a calculation revision. A second cycle must bring materially different
candidates: identical definitions are already recorded hypotheses of cycle 1
and are refused as duplicates.

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
| `RESEARCH_POLICY_MIXED_SET_UNSUPPORTED` / `RESEARCH_POLICY_EXTENSION_SET_DUPLICATE_SCOPE` | a file mixes an active-policy change with extensions, or repeats a scope | apply the policy change and the extensions in separate files, one proposal per scope |
| `ORDINARY_OPERATION_LINEAGE_AMBIGUOUS` / `ORDINARY_OPERATION_LINEAGE_OUT_OF_ORDER` | a research line holds several historical roots, or a first child of an earlier cycle arrives after a later cycle's | owner decision on the surviving root; record children in cycle order |
| `ORDINARY_OPERATION_ACCOUNTING_ROOT_REQUIRED` / `_UNKNOWN` / `ORDINARY_OPERATION_LINEAGE_MISMATCH` | a cycle-2 operation lacks, or names a wrong, accounting root or parent | copy `accounting_root` from the cycle-2 preflight receipt and the cycle-1 operation hash as parent |
| `RESEARCH_POLICY_CONFIRM_REQUIRED` | apply without `--confirm-append-only` | retry with the flag |
| `RESEARCH_POLICY_PRESET_NOT_FOUND` / `RESEARCH_POLICY_PRESET_CONFLICT` | unknown preset, or an explicit field contradicts it | define the preset first or drop the conflicting field |
| `RESEARCH_POLICY_CHAIN_CORRUPT` | present-invalid policy state | stop and restore the store; there is no default fallback |
| `ORDINARY_OPERATION_NOT_FOUND` / `ORDINARY_OPERATION_STOPPED` | `--for-operation` names no open operation | copy the exact operation hash from status |
| `EXTENSION_PARENT_COMPLETED` | the run already completed | request a new segment with its final receipt |
| `EXTENSION_PARENT_HAS_PENDING_RESERVATION` | an action is pending | resume that exact action first |

## Owner authority of apply

`research-policy-apply` is an owner-invoked CLI call, not a separate
authorization artifact: the proposal self-hash proves it was not edited after
preview, `--confirm-append-only` proves an explicit call. The extensions of one
file are applied in **one ResearchStore commit**: under the writer lease every
proposal is re-planned (sequence, stale, legacy freeze) and the live parent
guard runs again (run not stopped, no unresolved reservation, scope belongs to
the run). Either the whole supported set is committed or nothing is, and a
refusal reports `writes: 0` truthfully. An active-policy change is its own
commit; a file that mixes it with extensions, or repeats a scope, is refused
before any write. A repeat of an applied set is idempotent. A hand-written
proposal can still be applied by whoever runs the CLI, as with
`universe-policy-apply`.

## Multiple testing

A limit is a ceiling, not a target. A later AUTO cycle is a linked segment of
the same search and spends the same lineage budget, so a new cycle never opens a
fresh MAIN allowance by itself; only an explicit, owner-previewed raise of the
root does. The packet shows the root's limits and what is left of them.

## Known limits of this delivery

- Records created before this closure may hold several unlinked roots for one research line (separate budgets, never rewritten). A new operation on such an ambiguous line is refused (`ORDINARY_OPERATION_LINEAGE_AMBIGUOUS`), never given a fresh budget; an owner decision is needed to pick the surviving root.
- `episode-normalized-view` now publishes its derived context through the existing context owner (idempotent), so the next writer receives a usable receipt; a conflicting or corrupt context artifact still refuses the lifecycle write.
- Occupancy of the episode representation is per focus and per cycle: another focus's child no longer blocks this focus's child (the legacy NT representation keeps its per-market occupancy).
- Cycle capability for the episode collection covers its AUTO focus (`OPPORTUNITY_EPISODES:AUTO`); other named episode focuses have no additional cycle.
- Each lineage-aware budget read scans the ResearchStore several times; this is paid until the store grows large and is not memoized.
- The four additive schemas are part of the capability fingerprint; `hfic_research_policy.py` and `hfic_ordinary_operation.py` are runtime owners outside it.
- The single unreproduced failure seen once in `research_policy_vertical` during the first regression is not explained; five clean reruns followed. The original trace was not captured by the runner.
- An unparseable policy row is `RESEARCH_POLICY_CHAIN_CORRUPT`; a present-but-invalid `cycle_index` on a stored row still reads as cycle 1.
- A failure after the PREVIEW reservation of an episode view leaves that reservation pending; the identical retry resumes it (RESUME), spends nothing new and lands the payload.
- The epoch history used by preflight includes reservations while the packet and status readouts count sessions only, so a pre-runtime epoch with reservations but no session can display a raised `would freeze` limit while preflight enforces the legacy defaults.
- PREVIEW accounting repair (`FORGE_RELIABILITY_AUDIT_CONTINUATION_V1`): distinct frozen request descriptors each spend one slot even when their landed payload bytes are identical. Journal occupancy and the explicit operation cap use the same request identity. Identical retries remain one charge; pending becomes completed without a second charge. Legacy previews without a descriptor keep their historical payload-based charge in a separate identity namespace; no records or limits are rewritten. The earlier payload collision defect remains recorded in the immutable PR-B evidence and this audit's BASE finding.
- Test strength: raising `distinct_focuses_per_market`, and applying a change while an operation holds a pending reservation, are covered structurally, not by a dedicated end-to-end test.
- `max_generated` below 4 conflicts with the non-ordinary floor of 4 candidates; ordinary drafts use the policy value.
- Numerical replay of a prefix view is covered by the PR-A cold test, not repeated here.
- `repository_git_snapshot` hashes the whole worktree and all refs; external refs created during a run can fail a vertical test.

## Non-goals

No new collector, evaluator, database, service or dependency; no raised
shipped default; no change to VPS, canary, deploy or provider routing; no
scientific claim or strategy promotion from a policy change.
