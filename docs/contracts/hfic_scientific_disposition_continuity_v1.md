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
never reserves a look, spends budget, changes admission, market identity, the
search/journal key or the scientific slot. Record ids start with `HFIC-`, so
the existing endogenous classification keeps them out of the market evidence
epoch. `author_role`, `model` and `effort` are declared by the submitter, not
verified identity; `author_role: OWNER` is not an owner decision.

## Commands

All three are safe to run without authority. `forge-run --no-write` is a
read-only readback despite its name; it never starts a run.

```text
# read (exact detail, paging; reads no outcome rows)
uv run --locked --managed-python python -B scripts/hypothesis_forge.py disposition-show --owner-focus <FOCUS> [--journal-scope <sha>] [--subject-key <sha>] [--record-id <ref>] [--offset N] --format json
# preview a write (validates, shows the exact append plan, never writes)
uv run --locked --managed-python python -B scripts/hypothesis_forge.py disposition-record --input <packet.json> --preview --format json
# write (normal path for every new assessment)
uv run --locked --managed-python python -B scripts/hypothesis_forge.py disposition-record --input <packet.json> --format json
```

Use the global `--data-root <store>` when the store is not the default. A
write changes the store inventory: take a fresh preflight afterwards, because
a preflight receipt taken before the write no longer matches the store digest.

## Packet shapes

A packet is the submission, not the stored body: do not resubmit a stored or
previewed `body`. Unknown top-level keys are refused. Text fields must not
contain host paths (`/home/…`, `C:\…`, UNC, `SMIAL_DATA_ROOT`); cite repo-
relative files or plain labels instead.

| subject_kind | allowed verdict | allowed recommendation |
|---|---|---|
| `QUESTION` | `LIMITED_NON_CANDIDATE_FOR_THIS_QUESTION`, `INSUFFICIENT_EVIDENCE` | `STOP_THIS_QUESTION`, `REVIEW_BOUNDED_SCOPE` |
| `BOUNDED_SEARCH_ASSESSMENT` | `NO_WORTHY_SIMPLE_NEXT` (tier `SIMPLE_SCREEN` only) | `PAUSE_CONSIDERED_SIMPLE_SCOPE`, `REVIEW_BOUNDED_SCOPE` |
| `BOUNDED_SEARCH_ASSESSMENT` | `INSUFFICIENT_EVIDENCE` | `REVIEW_BOUNDED_SCOPE` |

Question assessment (values from `forge-run` `ordinary_operation`, from the
`NOT_RECORDED` line, or from `disposition-show` `not_recorded[]`):

```json
{
  "subject": {"subject_kind": "QUESTION", "market_evidence_epoch_sha256": "<64hex>",
              "owner_focus": "<FOCUS>", "journal_scope": "<64hex>",
              "question_spec_sha256": "<64hex>", "question_text": "<short text>"},
  "basis": {"result_refs": [{"result_ref": "HFIC-ART-DISCOVERY-<40HEX>",
                             "result_sha256": "<64hex>", "calculation_version": "HFIC_TEMPORAL_DISCOVERY_CALC_V4"}],
            "saved_results_read": true, "values_loaded": false, "scientific_look_delta": 0},
  "judgement": {"verdict": "LIMITED_NON_CANDIDATE_FOR_THIS_QUESTION", "recommendation": "STOP_THIS_QUESTION",
                "source_wording": "<literal wording>", "rationale": "<why>", "caveats": ["<material caveat>"]},
  "provenance": {"author_role": "MODEL", "model": "UNKNOWN", "effort": "UNKNOWN",
                 "source_episode": "<episode label>", "source_refs": ["<label or repo-relative ref>"]}
}
```

Bounded search assessment (no operation, spec, session or candidate needed):
the same `subject` without `question_spec_sha256`, plus
`"search_scope": {"search_tier": "SIMPLE_SCREEN", "population": "<fixed or UNKNOWN_NOT_FIXED>",
"window": "<fixed or UNKNOWN_NOT_FIXED>", "constraints": ["<real constraint>"]}`; `basis` adds
`"considered_proposals": [{"label", "representation", "disposition_reason"}]` and a compact
`"synthesis_basis"`. The writer records the journal frontier itself.

Successor (corrects the current head): the full new packet plus
`"supersedes": {"record_id": "HFIC-ART-DISP-<40HEX>", "disposition_sha256": "<64hex>"}` of the
current head (both are in `disposition-show` `head_ref` / `head_disposition_sha256`, and in the
`detail` of a `DISPOSITION_SUBJECT_HAS_HEAD` / `DISPOSITION_STALE_PARENT` refusal).

Withdrawal (no current advice afterwards; history kept):

```json
{"entry": "WITHDRAWAL", "subject": {"<same subject as the head>": "..."},
 "withdrawal": {"reason": "<why the assessment was wrong>"},
 "supersedes": {"record_id": "<head ref>", "disposition_sha256": "<head sha>"},
 "provenance": {"author_role": "OPERATOR", "source_episode": "<label>", "source_refs": []}}
```

Historical import: `provenance.mode = "HISTORICAL_IMPORT"`, `source_sha256` of the source
artifact (required; the writer records it and does **not** compare it with source bytes — that
check is the operator's), `source_encoding`, `assessed_at` when verifiable. A bounded search
import must declare the frontier it covered:
`"journal_frontier": {"attempts": [{"attempt_ref", "evidence_ref", "result_sha256", "calculation_version"}]}`.
Each attempt must resolve to a saved result. An import is not current because it was
imported: if the store moved on, it reads `REVIEW_REQUIRED`.

## Applicability (computed on read, never stored)

| Status | Meaning | What to do |
|---|---|---|
| `CURRENT_FOR_BOUND_BASIS` | bound result/frontier unchanged, verified market, current journal | advice active (still only advice) |
| `REVIEW_REQUIRED` | result revised, new attempt in the journal (`FRONTIER_CHANGED`), journal rotated (`JOURNAL_CHANGED`) or market unverified (`MARKET_UNVERIFIED`) | re-assess with a successor, or leave as history |
| `HISTORICAL` | another market, or the bound result is not science-ready | history only |
| `WITHDRAWN` | explicit withdrawal is the head | none; a new assessment may supersede it |
| `CONFLICT` | more than one head (restored fork); never latest-wins | **STOP** for this subject; writes are refused; owner resolution |
| `UNREADABLE` | a record of this subject is corrupt/unsupported, or its bound result is missing | **STOP** for this subject; writes are refused; owner resolution |
| `NOT_RECORDED` | a saved calculation in this focus's journal with no assessment | write one with `disposition-record` |

CONFLICT and UNREADABLE are not repaired by another append; resolving them
(for example restoring the missing result or choosing a head) is an owner
decision outside this capability. Other subjects, numerical results,
candidate paths and `next_action` are unaffected. An unscoped corrupt record
is only counted. A reader failure or a host path found in stored text yields
`scientific_disposition_context.status=UNAVAILABLE` with a typed reason.

`NO_WORTHY_SIMPLE_NEXT` speaks for the considered SIMPLE scope only. A
COMPOUND scope is another subject and stays untested unless named. Literal
source wording (for example an operator's `PARK_FAMILY`) is kept for
provenance; it never becomes a lifecycle state. Unrelated receipts, logs,
operations and the assessment's own append do not change the frontier; the
frontier counts every saved attempt in the journal and does not judge
predicate relevance.

## Consumers

`forge-run --no-write` carries `scientific_disposition_context` as a derived
overlay outside `receipt_sha256` and prints it as `scientific_context
(advisory; not next_action, not authority)`. Preflight adds the same capsule
(at most 4 KiB, inside the unchanged 64 KiB Forge packet budget) to new
`forge_context_packet` bytes only when the focus has assessment history,
separate from `ranked_prior_candidate_ids`; under byte pressure it shrinks to
counts and the detail query before any other section. Omitted entries are
counted with the exact `disposition-show` query.
