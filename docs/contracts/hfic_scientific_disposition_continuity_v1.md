---
contract_id: HFIC_SCIENTIFIC_DISPOSITION_CONTINUITY_V1
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-09-30'
truth_owner: FORGE_SCIENTIFIC_DISPOSITION_CONTINUITY_V1
module: src/solana_alpha_lab/factory/hfic_scientific_disposition.py
schema: catalog/schemas/hfic_scientific_disposition_v1.schema.json
---

# Scientific disposition continuity (ordinary Forge)

## What it is

A durable record of **what someone concluded** about saved ordinary Forge work
and **on which basis**: one `RESEARCH_ARTIFACT` of kind
`ORDINARY_SCIENTIFIC_DISPOSITION_V1` in the existing ResearchStore. A new agent
with only the repository, the store locator and the owner focus can read it —
no sidecar file, host path or chat history.

It is authored advice. It is not owner authority, not a candidate PASS/KILL,
not a search-wide `NO_WORTHY_HYPOTHESIS`, not a family close and not alpha. It
never reserves a look, spends budget, changes admission, market identity or
the scientific slot. Record ids start with `HFIC-`, so the existing endogenous
classification keeps them out of the market evidence epoch.

## Two subject forms

| subject_kind | Binds | Typical verdict |
|---|---|---|
| `QUESTION` | market, focus, journal, `question_spec_sha256`, exactly one saved result (ref, hash, calculation version, input binding, operation) | `LIMITED_NON_CANDIDATE_FOR_THIS_QUESTION`, `INSUFFICIENT_EVIDENCE` |
| `BOUNDED_SEARCH_ASSESSMENT` | market, focus, journal, declared scope (tier, population, window, constraints), considered proposals, compact synthesis basis, journal frontier | `NO_WORTHY_SIMPLE_NEXT` (SIMPLE tier only), `INSUFFICIENT_EVIDENCE` |

`NO_WORTHY_SIMPLE_NEXT` speaks for the considered SIMPLE scope only. A COMPOUND
scope is another subject and stays untested unless named. Literal source
wording (for example an operator's `PARK_FAMILY`) is kept for provenance; it
does not become a lifecycle state. A bounded search assessment needs no
operation, spec, session or candidate; `values_loaded=false` and
`saved_results_read=true` are recorded separately; `scientific_look_delta` is
always 0.

## Applicability (computed on read, never stored)

| Status | Meaning |
|---|---|
| `CURRENT_FOR_BOUND_BASIS` | bound result/frontier unchanged on this market; advice active |
| `REVIEW_REQUIRED` | a calculation revision superseded the bound result, or a new attempt changed the journal frontier |
| `HISTORICAL` | another market, or the bound result is not science-ready |
| `WITHDRAWN` | explicit withdrawal is the lineage head; history kept |
| `CONFLICT` | more than one lineage head (restored fork); never latest-wins |
| `UNREADABLE` | a record of this subject is corrupt/unsupported or its basis ref is missing |
| `NOT_RECORDED` | a saved calculation with no authored assessment |

Unrelated receipts, logs, operations and the assessment's own append do not
change the frontier. A corrupt record is localized to its subject; an
unscoped corrupt record is only counted. Reader failure yields
`scientific_disposition_context.status=UNAVAILABLE`; numerical results,
candidate paths and `next_action` are unaffected.

## Lineage

Append-only. A successor names `supersedes={record_id, disposition_sha256}`
of the current head; the check runs inside the store writer lease. A new
root when a head exists is `DISPOSITION_SUBJECT_HAS_HEAD`; a stale parent is
`DISPOSITION_STALE_PARENT` with the actual head ref. A withdrawal is a
successor with a reason and no basis. An exact repeat returns the saved record
and its original ingestion metadata. Rollback is a successor or withdrawal,
never delete or overwrite.

## Commands

Write (normal path for every new assessment; `--preview` never writes):

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py disposition-record --input <packet.json> [--preview] --format json
```

Read (exact detail, paging, no outcome rows):

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py disposition-show --owner-focus <FOCUS> [--subject-key <sha>] [--record-id <ref>] [--offset N] --format json
```

Ordinary consumers read the same resolver: `forge-run --no-write` carries
`scientific_disposition_context` as a derived overlay outside
`receipt_sha256`; preflight adds the same capsule (at most 4 KiB, inside the
unchanged 64 KiB Forge packet budget) to new `forge_context_packet` bytes,
separate from `ranked_prior_candidate_ids`. Omitted entries are counted with
the exact `disposition-show` query.

`provenance.mode=HISTORICAL_IMPORT` keeps a historical basis: the packet must
declare the journal frontier it covered. It is not current merely because it
was imported; source hashes verify bytes and grant nothing.
