# Forge research-policy runtime V1

Owner: `FORGE_RESEARCH_POLICY_RUNTIME_V1`.
Consumers: the ordinary-operation MAIN/ADAPTIVE/PREVIEW gate, AUTO-cycle and
distinct-focus admission, temporal-look classification, the candidate draft
and session-receipt schemas, and the `research-policy` CLI surface. This
document grants no scientific, provider, deployment or merge authority. A
policy change is a budget ceiling for new runs; it is never a scientific
look, a return result or strategy promotion.

ResearchStore owns three append-only artifact kinds, one owner module
(`hfic_research_policy.py`), three distinct CAS surfaces:

| Kind | What it is | Moves when |
|---|---|---|
| `FORGE_RESEARCH_POLICY_V1` | the active policy for *new* runs | the owner applies a CAS-checked change; never blocked by an open operation |
| `FORGE_RESEARCH_POLICY_RUN_SNAPSHOT_V1` | one journal's frozen limits | only once, on that journal's first real touch; first-writer-wins |
| `FORGE_RESEARCH_POLICY_RUN_EXTENSION_V1` | an append-only chain on top of a snapshot | an explicit, owner-authorized extension of that exact journal |

A journal's effective limits are its frozen snapshot plus its own extension
chain (`limits_for_frozen_run`). These are three distinct things and must
never be conflated: changing the active policy never moves an existing
journal; freezing a new journal's snapshot never resets what any other
journal has spent; an extension never resets what *this* journal has
already spent, because spend is computed independently, from recorded
looks and reservations, by the ordinary-operation owner — not by this
module. A journal this owner has never touched (legacy, pre-dating this
runtime, or only ever read through a read-only path) reads the shipped
defaults, unchanged, and writes nothing.

## Limits

| Field | Shipped default | Hard fuse | Governs |
|---|---|---|---|
| `auto_cycles_per_market` | 1 | 8 | AUTO sessions admitted per market evidence epoch |
| `distinct_focuses_per_market` | 3 | 32 | distinct non-AUTO focuses admitted per market evidence epoch |
| `main_total` | 6 | 32 | MAIN temporal/query looks per journal |
| `adaptive_total` | 2 | 8 | ADAPTIVE looks per journal |
| `preview_total` | 2 | 8 | feature-preview specs per journal |
| `simple_before_compound` | 3 | 32 | SIMPLE_SCREEN MAINs reserved ahead of any COMPOUND_SCREEN |
| `max_generated` | 6 | 16 | candidates a draft may carry |
| `max_diagnostic_slices` | 8 | 8 | disclosed diagnostic slices; this knob may only be lowered, never raised, in this delivery |

No field may ever exceed its hard fuse, regardless of preset or extension.
This delivery never raises a shipped default itself; `ABSENT` policy state
resolves to exactly these defaults.

## Presets

The active policy may carry up to 16 named presets (`[a-z][a-z0-9_]{0,31}`,
each ≤4KiB, ≤16KiB total), each a partial limits delta an owner can apply by
name instead of spelling out every field. A preset is registered the same
way as any other policy change (`presets_delta`) and may be applied alone or
alongside an explicit `limits_delta`, in which case the explicit delta wins
field-by-field.

## Identity

| Identity | Fixes |
|---|---|
| Active policy head (`policy_head_sha256`) | `limits` + `presets`, CAS-applied against `base_policy_head_sha256`/`base_store_inventory_digest` |
| Run snapshot | one journal's frozen `limits` at first touch, keyed by `journal_scope` |
| Extension | an ordered, CAS-protected delta on top of a snapshot, keyed by `journal_scope` + `extension_sequence` |

A policy's `semantic_sha256` and an extension's `proposal_sha256` never enter
`scientific_body`, a scope rule or market-evidence basis: this is execution
provenance, not scientific identity.

## Consumer wiring

`hfic_ordinary_operation.py`'s `_protocol_remaining`/`owner_allowance`/`_admit`
resolve `limits_for_frozen_run`/`ensure_run_snapshot` for MAIN/ADAPTIVE/
PREVIEW and for `resolve_scientific_admission`'s AUTO/distinct-focus caps.
`record_operation` stamps the journal's snapshot on first creation.
`hfic_temporal_discovery.py`'s `classify_temporal_look` and
`hfic_grounded_discovery.py`'s `classify_query_look` accept an optional
`limits` mapping; omitted, they keep the legacy hardcoded defaults so every
bare pure-function caller is unchanged. `hfic_preflight.py`'s
`decide_preflight_action`/`epoch_search_budget_usage` accept
`auto_sessions_per_market`/`max_distinct_focuses`; their own AUTO counter
counts distinct `search_key_sha256` values in the epoch, not a saturating
`int(any(...))`, so a real AUTO 1→2 raise is actually reachable.
`hfic_session.py`'s candidate-count checks (`freeze_draft`,
`persist_generated_draft`, `apply_revision`) resolve `_max_candidates_for`
from the journal's frozen limits; the additive `packet_version "1.3"` draft
schema and `hypothesis_forge_session_receipt_v1_4.schema.json` carry a wider
structural ceiling for a journal whose policy actually raised
`max_generated`, selected only when a receipt carries more than the shipped
default of 6 candidates. Every existing packet/receipt keeps validating
against its unchanged v1.1/v1.2/v1.3 schema.

## Refusals an operator sees

| Code | Meaning | Next step |
|---|---|---|
| `RESEARCH_POLICY_LIMIT_OUT_OF_RANGE` | a field is negative, non-integer, a bool, or above its hard fuse | correct the value; nothing was written |
| `RESEARCH_POLICY_ALLOCATION_EXCEEDS_MAIN_TOTAL` | `simple_before_compound` exceeds `main_total` | lower the allocation or raise `main_total` first |
| `RESEARCH_POLICY_PREVIEW_STALE` | the active policy moved since this proposal was built | repeat `research-policy-preview` |
| `RESEARCH_POLICY_EXTENSION_STALE` | another extension landed on this journal first | repeat `research-policy-extension-preview` |
| `RESEARCH_POLICY_RUN_SNAPSHOT_MISSING` | an extension was proposed before this journal's first touch | touch the journal once (preflight or an operation), then extend |
| `RESEARCH_POLICY_CONFIRM_REQUIRED` | apply called without `confirm_append_only` | retry with the explicit confirmation |
| `RESEARCH_POLICY_PRESET_NOT_FOUND` | a named preset does not exist on the active policy | register it first, or use an explicit `limits_delta` |

## Non-goals

No new collector, evaluator, database, service or dependency; no raised
shipped default in this delivery; no change to VPS, canary, deploy or
provider routing; no scientific claim or strategy promotion from a policy
change; `max_diagnostic_slices` may only be lowered, never raised, here.
