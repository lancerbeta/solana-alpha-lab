# Forge temporal operability repair — operator runbook

Capability: `FORGE_TEMPORAL_OPERABILITY_REPAIR_V1`.
Repair capability id: `CAP-HFIC-TEMPORAL-OPERABILITY-REPAIR-001`.

## What changed

1. Bound schedules may declare per-point `(due_offset, allowed_lateness)`.
   The query scalar remains the **X300 envelope**; other points may differ.
2. Temporal queries may set
   `schedule.observation_clock_policy: PROVIDER_REPORTED_SNAPSHOT_V1`.
   Exits then use request/response/availability clocks. Member anchor is not a
   market-event timestamp. Source price event time stays `UNKNOWN` unless
   proven.
3. Result / readout carry `observation_clock_policy` and
   `target_exclusion_reasons` (pooled + by_cohort).
4. After a completed `NO_WORTHY` without selected candidate, an owner-authorized
   append-only repair continuation may resume the same slot on the **spent**
   look ledger. Plan is no-write; apply is separate and idempotent.

## Snapshot clock invariant (`PROVIDER_REPORTED_SNAPSHOT_V1`)

For an exit snapshot to count:

`exit due ≤ request_started_at ≤ response_received_at ≤ first_reliable_available_at ≤ exit deadline`

and `request_started_at > entry`, where `entry = decision_deadline + assumed_latency`.

Required fields on the observation row: `request_started_at`,
`response_received_at`, `first_reliable_available_at`. Missing clocks →
`MISSING_ACQUISITION_CLOCK` (UNKNOWN), not a negative return.

Reference must already be available by both decision cutoff and its own point
deadline. Do not invent `source_price_event_time`; default is `UNKNOWN`.

## Target exclusion glossary

| Code | Meaning | Owner recovery |
|---|---|---|
| `REQUEST_NOT_AFTER_ENTRY` | Request did not start after entry | Check assumed latency / exit horizon |
| `ACQUISITION_BEFORE_POINT_DUE` | Request before point due | Do not use early scrape as later Y |
| `AVAILABILITY_AFTER_DEADLINE` | Availability after point deadline | Data gap or later schedule |
| `CLOCK_ORDER_INVALID` | Order due≤request≤response≤availability broken | Inspect occurrence timing |
| `MISSING_ACQUISITION_CLOCK` | Missing request/response/availability | UNKNOWN; not family kill |
| `SOURCE_PRICE_EVENT_STALE` | Proven source event outside deadline or not after entry | Keep fail-closed |
| `SOURCE_PRICE_EVENT_MALFORMED` | Non-empty source event unparsable | Fail closed; not UNKNOWN |
| `SNAPSHOT_OCCURRENCE_UNBOUND` | Exit lacks PRIM-* / request / occurrence | Bind occurrence lineage |
| `EVENT_NOT_AFTER_ENTRY` | Legacy EVENT_TIME path; often anchor | Prefer snapshot policy |
| `REFERENCE_NOT_AVAILABLE` | Reference missing by cutoff | Check reference point clocks |
| `EXIT_ABSENT` / `EXIT_NOT_OBSERVED` | No usable exit row | Data / schedule gap |

Empty observed target with these reasons is a **technical or data gap**, not a
modeled negative return and not an automatic family ban.

## Repair continuation — owner commands

`--data-root` is a **parent** flag. Put it before the subcommand.

### Field map from `show-session` (no guessing)

| Draft field | Source on `show-session` / store |
|---|---|
| `parent_session_id` | `session_id` |
| `scientific_slot_sha256` | `scientific_slot_sha256` |
| `terminal_receipt_sha256` | `terminal_receipt_sha256` (= `session_receipt_sha256`) |
| `journal_scope` | `journal_scope` (= `search_key_sha256`) |
| `parent_run_id` | resolved from store `FORGE_RUN_RECEIPT` for session/slot |
| `spent_*_looks` | discovery journal under `journal_scope` (MAIN/ADAPTIVE/PREVIEW) |
| `owner_authorization_id` | owner-supplied authority token |
| `technical_gap_code` | owner-supplied gap id (e.g. `PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP`) |

### 1) Build draft (no-write)

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <store> repair-continuation-draft --parent-session-id <HFIC-SESS-...> --owner-authorization-id <OWNER-AUTH-...> --technical-gap-code <GAP> --output <draft.json>
```

Spent looks default from the discovery journal. Optional overrides:
`--spent-main-looks`, `--spent-adaptive-looks`, `--spent-preview-looks`,
`--parent-run-id`, `--terminal-receipt-sha256`, `--journal-scope`.

Draft JSON fields (exact): `parent_run_id`, `parent_session_id`,
`scientific_slot_sha256`, `terminal_receipt_sha256`, `journal_scope`,
`technical_gap_code`, `repair_capability_id`
(`CAP-HFIC-TEMPORAL-OPERABILITY-REPAIR-001`), `allowed_look_ids`,
`spent_main_looks`, `spent_adaptive_looks`, `spent_preview_looks`,
`owner_authorization_id`, `parent_terminal=NO_WORTHY_HYPOTHESIS`.

### 2) No-write plan

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <store> repair-continuation-plan --draft <draft.json>
```

### 3) Apply (separate authority; append-only; does not refresh budget)

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <store> repair-continuation-apply --draft <draft.json> --confirm-append-only
```

### 4) After a new terminal — close the disposition (append-only)

Save `disposition_sha256` from apply/plan readout. After the ordinary
continuation run reaches a new terminal:

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <store> repair-continuation-close --disposition-sha256 <64-hex> --confirm-append-only
```

Close is required so AUTHORIZED cannot reopen the slot. Idempotent replay
returns `ALREADY_CLOSED` / `owner_status=DONE`.

### Plan/apply/draft/close owner terminals

| Machine `status` | `owner_status` | Meaning | `next_step` |
|---|---|---|---|
| `READY` | `READY` | Disposition/draft valid; not written | plan → `APPLY_WITH_EXPLICIT_CONFIRM_APPEND_ONLY`; draft → `REPAIR_CONTINUATION_PLAN_WITH_DRAFT` |
| `ALREADY_APPLIED` | `DONE` | Idempotent replay | `ORDINARY_TEMPORAL_QUERY_WITHIN_REMAINING_BUDGET` |
| `APPLIED` | `DONE` | Disposition appended | ordinary query in remainder |
| `CLOSED` / `ALREADY_CLOSED` | `DONE` | Disposition consumed after new terminal | `STOP_CONTINUATION_CONSUMED` |
| `NOT_APPLICABLE` | `BLOCKED` | Wrong parent / missing field / selected candidate / slot / spent mismatch | see `reason_code` + `owner_readout.next` |
| `CONFLICT` | `BLOCKED` | Competing active disposition | resolve or stop |

Draft/apply failures also print JSON on stdout with `owner_status=BLOCKED`
(not stderr-only codes). Common draft codes:

| `reason_code` | `next_step` |
|---|---|
| `PARENT_SESSION_MISSING` | `SHOW_SESSION_THEN_REPAIR_CONTINUATION_DRAFT` |
| `PARENT_RUN_REQUIRED` | `PROVIDE_PARENT_RUN_ID_OR_ENSURE_FORGE_RUN_RECEIPT` |
| `TERMINAL_RECEIPT_REQUIRED` | `ENSURE_SESSION_RECEIPT_SHA256_ON_SHOW_SESSION` |
| `SPENT_BUDGET_INVALID` | `PASS_SPENT_LOOKS_OR_ENSURE_DISCOVERY_JOURNAL` |
| `REPAIR_CONTINUATION_CONFIRM_REQUIRED` | `ADD_CONFIRM_APPEND_ONLY_WITH_OWNER_AUTHORITY` |

Ordinary temporal discovery after a READY/DONE continuation uses the same
`/hypothesis-forge` discovery path and inherited look counts. Do not open a
new session to refresh quota.

## Compatibility

- Legacy uniform `schedule_lateness_seconds` without point maps still requires
  scalar equality.
- Default / omitted clock policy keeps prior `EVENT_TIME_V1` identity bytes.
- Raw observation `event_time` is not globally rewritten for other consumers.
- Unknown disposition / policy must stop explainably; it must not silently
  return the old DONE as a free new search.

## Live parent (post-merge, separate authority)

1. No-write `repair-continuation-draft` then `repair-continuation-plan` against
   the exact parent run/session/slot/terminal hashes and remaining budget.
2. Only after explicit apply authority: `repair-continuation-apply
   --confirm-append-only` on that parent (not part of the delivery atom that
   only proves the mechanism).
3. One ordinary temporal query inside the inherited remainder, with
   `PROVIDER_REPORTED_SNAPSHOT_V1` and mixed point clocks as needed.
4. After the new terminal: `repair-continuation-close --disposition-sha256
   <from-apply> --confirm-append-only`.
5. Readback. Do not promise a worthy candidate.
