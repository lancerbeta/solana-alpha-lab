---
contract_id: CONTRACT-T16-HYPOTHESIS-LIFECYCLE-RESEARCH-MEMORY-001
contract_version: "1.0"
schema_id: repo://docs/contracts/hypothesis_lifecycle_research_memory.schema.json
task_id: TASK-16
atom_id: T16-A3_FROZEN_HYPOTHESIS_LIFECYCLE_RESEARCH_MEMORY_CONTRACT_V1
status: FROZEN_OFFLINE_CONTRACT
as_of: 2026-07-29
cash_cap_usd: 0
provider_calls_in_atom: 0
contains_secrets: false
---

# TASK-16 hypothesis lifecycle and research memory contract v1

## 1. Owner decision

Before opening or repeating a trial, the owner must be able to answer:

```text
where did this hypothesis come from
→ which immutable definition was tested
→ which data, tools, methods and search budget were used
→ what passed, failed, was inconclusive or was invalid
→ why the decision was made
→ which later idea, epoch or strategy derives from it
→ what materially changed enough to justify another trial
```

The contract is a durable research-memory boundary, not a research platform.
Its consumer is the owner decision to start, avoid, revise, promote, pause,
retire or reactivate a hypothesis with less repeated work and less hindsight
distortion.

## 2. Logical records and truth boundaries

The machine schema
`hypothesis_lifecycle_research_memory.schema.json` defines one logical snapshot.
Its records may later be distributed across the existing lifecycle registries;
the snapshot is not a second mutable truth owner.

The minimum record graph is:

```text
research_cycle
→ hypothesis_family
→ immutable hypothesis_version
→ hypothesis_origin
→ research_artifact
→ completed trial
→ append-only decision_event
→ optional activation_epoch
→ optional hypothesis_derivation_edge
```

The entities stay separate:

- `hypothesis_family` is the persistent mechanism identity.
- `hypothesis_version` is one frozen testable definition. Editing rules,
  features, labels, mechanism or falsifier creates another version.
- `hypothesis_origin` preserves how the candidate appeared. Origin prestige
  never substitutes for evidence.
- `research_cycle` freezes the problem contract: question, estimand,
  population and controls, available data, output, error cost and caps.
- `research_artifact` points to content-addressed data, query, code, notebook,
  configuration, sanitized prompt, model output, report or decision evidence.
- `trial` is a completed immutable test with PIT cutoff, split, holdout use,
  search budget, cost assumptions and one typed outcome.
- `decision_event` changes the derived lifecycle state without editing prior
  evidence.
- `activation_epoch` marks a distinct research, shadow, paper or separately
  authorized live period. It is not a position and grants no authority.
- `hypothesis_derivation_edge` states what a child reused, contradicted,
  refined, recombined or reformulated.

Strategy, watchlist, signal, execution, position and cashflow remain separately
versioned future consumers. Their IDs may be linked; this contract does not
implement or authorize them.

## 3. Stable identity and version rules

Stable identities use typed uppercase IDs:

- `HYP-FAMILY-*`;
- `HYP-VERSION-*-V<n>`;
- `HYP-ORIGIN-*`;
- `RESEARCH-CYCLE-*`;
- `RESEARCH-ARTIFACT-*`;
- `TRIAL-*`;
- `DECISION-EVENT-*`;
- `HYP-DERIVATION-*`;
- `ACTIVATION-EPOCH-*`.

An ID is never reused for different meaning. `version_ordinal` is monotonic
inside one family and must agree with the `-V<n>` suffix. The immutable
definition has `definition_state=FROZEN` and a `definition_sha256`.

`definition_sha256` is deterministic. Hash the UTF-8 JSON object containing:

```text
family_id
version_ordinal
research_cycle_id
origin_id
statement
mechanism
falsifier
expected_regime_terms
feature_definition_asset_ids
label_definition_asset_ids
named_consumer_ids
data_requirement_asset_id, when present
supersedes_hypothesis_version_id, when present
```

Object keys are lexicographically sorted, JSON separators are `,` and `:`
without extra whitespace, Unicode is not ASCII-escaped, and set-valued arrays
are lexicographically sorted before serialization. This canonical payload does
not include timestamps, evidence pointers or the hash itself.

A changed conclusion does not mutate a version. It creates a new
`decision_event`. A changed hypothesis definition creates a new version with
`supersedes_hypothesis_version_id`. Corrections create a new record with an
explicit `supersedes_*` link and retain the incorrect record as evidence of
what was known at the earlier decision.

## 4. Append-only lifecycle and closure

The root invariants are:

```text
append_only = true
history_rewrite_policy = CORRECT_WITH_NEW_RECORD_AND_SUPERSEDES_LINK
current_state_is_projection = true
```

Current lifecycle state is derived as-of from ordered decision events. It is
not a mutable `status` field on the hypothesis version.

For an as-of projection, first exclude events whose
`first_reliable_available_at` or `effective_at` is after the cutoff. Apply the
remaining events in ascending `(effective_at, first_reliable_available_at,
decision_event_id)` order. A future event cannot alter an earlier projection.

- `REJECT`, `REVISE`, `PROMOTE`, `PAUSE`, `MARK_DORMANT`, `RETIRE`,
  `REACTIVATE`, `CLOSE_RESEARCH_CYCLE` and `REOPEN_RESEARCH_CYCLE` are events.
- Dormancy retains all versions, trials, negative results and prior epochs.
- Reactivation requires a new decision event and a new activation epoch with
  named regime evidence. It never reopens an old epoch in place.
- Retirement closes future use by policy; it does not delete research memory.
- A completed trial never returns to pending. A new run gets a new `trial_id`.

Every record has `first_reliable_available_at`. An as-of projection or query
must exclude records that were not reliably available at its cutoff.

## 5. Reproducible provenance and PIT evidence

Every hypothesis version binds to one origin and one research cycle. The
reconstructable chain retains:

- origin kind, originator, observed and recorded times, source references and
  the initial observation;
- mechanism, falsifier and expected regime terms;
- exact content hashes and governed logical locations for data, query,
  notebook, code, configuration, sanitized prompt, model output and report;
- tool name/version, capability ID and configuration hash when applicable;
- dataset as-of, availability cutoff, population, controls, exclusions, split
  and holdout-consumption IDs;
- estimand, test kind, search budget, cost assumptions, outcome, limitations
  and conclusion;
- decision owner, rationale, time, evidence and the next condition;
- parent/child derivation rationale and evidence.

Raw chat transcripts are not a default artifact. Store the minimum sanitized
reproducible prompt, conclusion or content hash at a governed logical URI.
`contains_sensitive_raw_conversation` is therefore fixed to `false`.

Historical hydration may reconstruct market facts but cannot backdate
`first_reliable_available_at` or pretend that a strategy knew them earlier.

## 6. Trial truth and negative memory

Trials have exactly one completed outcome:

- `POSITIVE`;
- `NEGATIVE`;
- `INCONCLUSIVE`;
- `INVALID`.

`PENDING` is excluded from the immutable trial record. A plan is a research
artifact; a trial record appears only when the bounded run has a result.

Negative, inconclusive and invalid outcomes are first-class. They retain the
same data, method, PIT, search-budget and evidence obligations as positive
results. Invalid evidence must not be silently converted to a negative market
result.

## 7. Bounded prior-work query contract

Before a new trial, the deterministic query introduced in A4 must accept:

- an exact `as_of` timestamp;
- at least one bounded predicate over stable IDs, normalized mechanism terms,
  falsifier terms, regime terms, origin kinds, dataset artifacts, tool
  capabilities, trial outcomes or decision kinds;
- `max_results` from 1 through 50.

It must:

1. Exclude records with `first_reliable_available_at > as_of`.
2. Search versions, origins, artifacts, trials, decisions and derivation
   parents/children without a network service or vector database.
3. Return stable hypothesis-version IDs, explicit `matched_by` reason codes,
   supporting trial/decision/derivation IDs and content-addressed evidence.
4. Use a deterministic score and stable-ID tie break.
5. Preserve negative, inconclusive, invalid and dormant evidence.
6. State `what_changed` before a repeated or extended trial can proceed.

Similarity is advisory. It cannot automatically reject, promote, activate or
change a hypothesis.

## 8. Migration without historical rewrite

Existing TASK-03 registries remain valid inputs:

- `research_cycles.yaml`;
- `hypotheses.yaml`;
- `global_trial_ledger.yaml`;
- `decisions_negative_results.yaml`;
- linked feature, holdout, strategy and bot registries.

Migration in A5 is forward-only:

1. Existing bytes and historical receipts are not rewritten.
2. Empty registries migrate as empty; no synthetic history is invented.
3. A legacy record is preserved by exact source path, record ID and source
   hash.
4. Missing required semantics produce an explicit unresolved migration record,
   not fabricated mechanism, falsifier, PIT cutoff or result.
5. Migrated records become reliably available no earlier than the migration
   evidence that established them.
6. Legacy schema v1 remains valid while the new contract is added through an
   explicit schema/Catalog transaction.

Rollback before acceptance is removal of the new uncommitted TASK-16 files.
After acceptance, correction is forward-only through a new schema or record
version.

## 9. Cross-record semantic validation

JSON Schema validates record shape. A4/A5 deterministic validation additionally
must fail closed on:

- duplicate IDs within or across record families;
- missing references;
- family/version suffix or ordinal mismatch;
- self-supersession or derivation cycles;
- child derivation equal to any parent;
- timestamps or PIT availability that violate as-of ordering;
- a decision or epoch referring to unknown evidence;
- a `LIVE` epoch without an explicit authority-receipt asset;
- an epoch ordinal that is reused or does not increase for a hypothesis;
- a reactivation without a prior dormant/pause event and named regime evidence;
- trial search-budget counts or holdout lineage that do not reconcile.

## 10. Explicit non-authority

A3 authorizes zero:

- provider/API/RPC/WSS, web, account or dashboard calls;
- historical or live data collection;
- AI hypothesis-mining service, vector database or research platform;
- dependency adoption, scheduler, deployment or unattended process;
- strategy activation, watchlist engine, position manager or trading engine;
- wallet, signer, transaction or real-money action;
- commit, push, pull request, merge, settings, force or destructive action.

The presence of a `LIVE` enum or authority-receipt reference models future
evidence; it never creates that authority.

## 11. A3 acceptance and next boundary

A3 passes only when:

- the JSON Schema is valid Draft 2020-12;
- a minimal in-memory example validates;
- immutable definitions, append-only state, typed completed outcomes,
  sanitized artifacts and future live-evidence requirements fail closed;
- contract files are UTF-8 without BOM, LF-only, final-newline clean and contain
  no machine-specific path or secret;
- existing registries and historical receipts are unchanged;
- Catalog registration is explicitly deferred.

The next atom is
`T16-A4_DETERMINISTIC_PRIOR_WORK_QUERY_AND_FIXTURE_V1`. It may create one
fixture, one thin offline query/validator and targeted tests. Migration,
Catalog version change, generated navigation, external calls and Git delivery
remain outside A4.
