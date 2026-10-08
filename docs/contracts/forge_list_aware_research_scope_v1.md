# Forge list-aware research scope V1

Owner: `FORGE_LIST_AWARE_RESEARCH_SCOPE_V1`.
Consumers: the Forge formulation context, temporal query 1.2, candidate freeze,
the independent Critic, classification, `DocumentRunner`, prior memory and replay.
This document grants no scientific, provider, deployment or merge authority.

Lists (the Jupiter nomination categories and any registered local list) are a
shared research dimension. One owner, `hfic_research_scope`, parses a list
selector, proves membership of an admitted episode at its `T0`, and turns a rule
into per-episode masks. No representation, evaluator or Critic parses list JSON.

## Roles

| Role | Meaning | Field |
|---|---|---|
| Universe | Which episodes the mechanism is studied in | `research_scope.universe_selector` |
| Signal | Membership is the explanatory condition (list-only or mixed) | `list_condition` |
| Diagnostic slice | A fixed group of the pooled result, disclosed before outcomes | `diagnostic_slices` (at most 8) |

`hypothesis_kind` is `NUMERIC_IN_SCOPE`, `LIST_CONTRAST` or `MIXED_LIST_NUMERIC`.
A `LIST_CONTRAST` carries no numeric condition (`features=[]`, `all=[]`); a fake
price predicate is refused. The comparator of a contrast is the decision-eligible
complement of the matched group (`MATCHED_VS_ELIGIBLE_COMPLEMENT`); a mixed
hypothesis defaults to the existing `SAME_DECISION_ELIGIBLE` baseline. A signal
selector equal to the universe selector is `NON_DISCRIMINATING_CONDITION`.
Membership is observational: the result never claims causality or interaction.

## Membership

`ADMISSION_FRAME_V1`: membership of an episode means the mint was present in the
list received by the round that admitted it. The join key is
`(round_id, frame_sha256, episode_id, mint)`, never `mint` alone; the next episode
of the same mint has its own membership. `witness_source_id` is the freshest-source
technical choice and is never membership.

States: `TRUE` (present), `FALSE` (list received, mint absent), `UNKNOWN` (not
observed or not covering this episode; never `FALSE`), `INVALID` (hash, identity or
clock conflict; blocks). The default `REQUIRE_KNOWN_REFERENCED` refuses with
`SCOPE_COVERAGE_UNRESOLVED` before any market value is read. A covered subset may be
declared first through `evidence_selection.cohort_ids` (part of the question
identity); unknown cohorts are never dropped silently.

`LOCAL_MEMBERSHIP_SNAPSHOT_V1`: one public registration path
(`hypothesis_forge.py list-snapshot-register`) stores a content-addressed JSON in
`<data root>/research_lists/snapshots`. An identical repeat is exact; a conflicting
interval or definition refuses. Reliable availability is
`max(declared available_at, registered_at)`, so a list registered today is never
historically known yesterday. Membership is evaluated at `EPISODE_T0`; a post-`T0`
or dynamic membership is `UNSUPPORTED_BASIS`.

## Selector grammar

Strict JSON: clauses are OR-ed (at most 8), inside a clause `all_of`, `any_of`,
`none_of` and `count{of,min,max}` are AND-ed, at most 32 distinct lists. Aliases
resolve to the canonical `list_id` before freeze; two aliases of one list are not
"2 of 2". `required_observed_lists` is fixed before any simplification, so a
tautological count still requires its lists to be observed. No `eval`, SQL,
imported code or power-set enumeration. `two of three` is ambiguous and must be
stated as exactly 2 (`min=max=2`) or at least 2 (`min=2,max=3`).

## Identity

| Identity | Fixes |
|---|---|
| Scope/hypothesis rule | selectors, roles, definition hashes, time basis (`research_scope_rule_sha256`) |
| Applied evidence/result | release/snapshot bindings, mask digest (`applied_sha256`, `evidence_sha256`) |
| Policy/run | budgets and disclosure (PR-B) |

Aliases and display names never enter identity. A changed selector is a new
question in the same accounting domain, not a new market epoch.

## Query 1.2 and propagation

`smial.hfic-temporal-query` 1.2 is query 1.1 plus a mandatory `research_scope`.
Query 1.1 refuses scope fields (`SCOPE_FIELDS_REQUIRE_QUERY_1_2`); an unscoped
executor refuses injected masks (`RESEARCH_SCOPE_BINDING_MISMATCH`). The same rule
digest is bound through: the result (`research_scope` block with per-side
`target_observed_n` / `target_missing_n`, `disclosed_comparisons`), the
claim identity (`research_scope_rule_sha256` + machine `research_scope_statement`
that the card must echo), the candidate identity hash, the Critic packet, the
classification guard (`RESEARCH_SCOPE_RECIPE_MISMATCH`), the frozen recipe
(`research_scope_evidence` closure, rebuilt from the frozen releases and exact
snapshots, `RESEARCH_SCOPE_EVIDENCE_DRIFT` on mismatch) and prior-memory scope axes.
A reader that does not know query 1.2 refuses instead of computing a pooled result.

## Formulation context

### Raw and canonical public ingress

`research-scope-resolve` and `episode-normalized-view` accept a raw query or
the complete canonical query emitted by the resolver. Reserved
`definition_refs`/`required_observed_lists` anywhere in the scope, signal or
diagnostic slices select strict canonical validation. Mixed or corrupted
canonical input never falls back to raw re-resolution. Existing structural
validators check the full nested closure and pins against the verified
membership definitions before market values. Canonical pins are preserved;
`N(N(raw)) == N(raw)`, and rule/applied bindings stay identical on the same
evidence. `none_of` and tautological counts retain observed-list requirements:
UNKNOWN never becomes FALSE. Frozen replay uses saved closure, not today's
active definitions. Spelling changes create no second scientific attempt.

Fresh card/context transfer follows `forge_grounded_handoff_closure_v1.md`.

`preflight` adds `list_dimension_context` (metadata only, no outcome): definitions,
aliases, counts of `TRUE/FALSE/UNKNOWN/INVALID`, overlap signatures (at most 16 plus
the omitted count), examples, and the representation scope support table. Owner or
vendor label text is data, bounded and never an instruction channel.

## Episode normalized profile

`NORMALIZED_TRAJECTORY_EPISODES_V1` is an additive representation; the frozen
newborn `NORMALIZED_TRAJECTORY_V1` (X/Y points, Y1800 cutoff, CONTROL protocol)
stays unchanged and is reported `UNSUPPORTED_POPULATION` for episodes. The profile
reads `E300/E900/E1800` of PRICE, LIQUIDITY and HOLDERS through the episode point
resolver, per `episode_id` and within the research scope, applied before
aggregation. Each channel gives two transitions `U/D/F/M`; a joint motif is a
description, not an executable feature. At most 8 motifs per panel
(`BASE`, and `SIGNAL`/`COMPARATOR` when a signal exists) with exact omitted counts.
It enters the existing ladder as an episode-only representation (registry
`populations`), is pinned by its own payload hash and journal
(`representation_search_key`), and keeps the ordinary freeze/Critic lifecycle.

## Refusals an operator sees

| Code | Meaning | Next step |
|---|---|---|
| `SCOPE_COVERAGE_UNRESOLVED` | a referenced list is UNKNOWN for some episodes (universe, signal or slice) | declare `evidence_selection.cohort_ids` from `covered_cohort_ids` before any outcome, or wait for coverage |
| `SCOPE_EVIDENCE_INVALID` | frame/snapshot evidence conflicts | restore the exact release or snapshot; never heal |
| `RESEARCH_SCOPE_BINDING_MISMATCH` | masks do not belong to this exact rule or episode set | rebuild through `research-scope-resolve`; never inject masks |
| `LOOK_SCOPE_CONTRADICTION` | the card does not echo the computed rule/statement | copy them from `temporal_holder_claim_identity` |
| `RESEARCH_SCOPE_RECIPE_MISMATCH` | classification got an experiment of another (or no) scope | classify the frozen recipe of the same look |
| `RESEARCH_SCOPE_EVIDENCE_DRIFT` | replay evidence differs from the frozen closure | restore the frozen releases/snapshots |
| `EPISODE_PAYLOAD_SCOPE_MISMATCH` | the episode profile was built for another scope | rebuild the view with the candidate's rule |
| `REGISTERED_AT_OVERRIDE_FORBIDDEN` | a caller-chosen registration time | register now; availability is never backdated |

A result on a declared covered subset (`cohort_ids`) is a local result for those
cohorts, not a statement about the list in general. A `NO_WORTHY` on the episode
profile is a scoped stage outcome; it does not close the list family.

## Non-goals

No new collector, evaluator, database, service or dependency; no change to the
Jupiter capture population, caps, grid or `T0`; no dynamic post-`T0` membership;
no causal or factorial machinery; no live action.
