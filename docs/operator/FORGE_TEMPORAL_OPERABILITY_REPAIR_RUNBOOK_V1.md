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
| `SNAPSHOT_LINEAGE_UNINTERPRETABLE` | Policy column absent and retained transport/occurrence/acquisition lineage incomplete | Metadata/data blocker — do not invent clocks; not a false empty population or family kill |
| `SNAPSHOT_POLICY_MISMATCH` | Row policy disagrees with query policy | Align query/corpus clock policy |
| `EVENT_NOT_AFTER_ENTRY` | Legacy EVENT_TIME path; often anchor | Prefer snapshot policy |
| `REFERENCE_NOT_AVAILABLE` | Reference missing by cutoff | Check reference point clocks |
| `EXIT_ABSENT` / `EXIT_NOT_OBSERVED` | No usable exit row | Data / schedule gap |

Empty observed target with these reasons is a **technical or data gap**, not a
modeled negative return and not an automatic family ban. When the whole required
input scope is lineage-uninterpretable, discovery stamps `technical_stop` /
`technical_failure=true` (reason e.g. `SNAPSHOT_LINEAGE_UNINTERPRETABLE`). Those
looks do **not** authorize scientific `SEARCH_EXHAUSTED` / `READY_TO_FREEZE`
(including the compound-inapplicable shortcut). Owner recovery: fix metadata /
occurrence lineage, then re-query — do not treat the stop as family kill.
Census rows that never enter the eligible population (e.g. `NOT_X_ELIGIBLE`)
must not cancel that technical stop. Predicate fitness (X300 / decision /
required features) and matched-outcome fitness (reference / exit) are separate:
feature lineage that leaves every eligible member `feature_unknown` is a
technical stop; exit/reference lineage on **unmatched** members must not turn a
valid false-predicate zero-match into `TECHNICAL_STOP`. Matched-scope outcome
lineage remains visible in `target_exclusion_reasons` and can still stop.

Repair `close` takes the owner-final from `effective_control_terminal` +
`resolve_next_action` (final session terminal wins over primary critic). Close
requires a completed cycle **bound to this disposition** and new vs the parent
receipt. Apply → immediate close on parent `NO_WORTHY` / foreign marker /
awaiting critic / classification / runner-up fails with
`REPAIR_EXECUTION_NOT_COMPLETE` and writes nothing (`AUTHORIZED` retained).

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
| `repair_continuation_disposition_sha256` | stamped on `show-session` / list after authorized repair freeze or NO_WORTHY repair terminal — use for `repair-continuation-close` if apply JSON was lost |
| `critic_terminal` | primary-cycle critic verdict (`NO_WORTHY_HYPOTHESIS`, `KILL_*`, …). After runner-up failover this may still show the primary KILL while the **owner-final** terminal is elsewhere — do not steer close/readback on this alone |
| `final_session_terminal` | canonical session terminal after F3/failover (`effective_control_terminal`). Prefer this over `critic_terminal` for close readiness and expected `forge-run` owner_final |
| `runner_up_failover_used` | true when the surviving candidate is the runner-up; survivor id is `final_survivor_candidate_id` on the session receipt |

Close readiness: `session_state=SYNTHESIS_COMPLETE` **and** a non-empty
`final_session_terminal` (PASS/CASE_A/KILL/NO_WORTHY…) **and**
`repair_continuation_disposition_sha256` equal to the AUTHORIZED disposition
**and** `session_receipt_sha256` different from the disposition's parent
`terminal_receipt_sha256`. Apply alone (parent DONE still visible) must not
close. Pending `AWAITING_CLASSIFICATION` / `RUNNER_UP_AWAITING_CRITIC` /
revision pause must not close either — CLI returns
`REPAIR_EXECUTION_NOT_COMPLETE` with
`COMPLETE_DISPOSITION_BOUND_REPAIR_EXECUTION_THEN_CLOSE` (disposition stays
`AUTHORIZED`; do not rerun apply).

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

Save `disposition_sha256` from apply/plan readout (or recover
`repair_continuation_disposition_sha256` from `show-session` after a repair
freeze/terminal). After the ordinary continuation reaches a **new** terminal
— either NO_WORTHY or selected→critic→finalize — close is still required:

```
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <store> repair-continuation-close --disposition-sha256 <64-hex> --confirm-append-only
```

`show-session` `session_state=SYNTHESIS_COMPLETE` with a completed
`final_session_terminal` (≠ parent `NO_WORTHY` when repair produced a new
cycle) means the research cycle finished; it does **not** mean the AUTHORIZED
disposition is consumed. Trust `final_session_terminal` /
`effective_control_terminal` for the owner-final cue — after runner-up failover,
`critic_terminal` may still name the primary KILL while the survivor PASS is on
`final_session_terminal`. Until close, AUTHORIZED can still overlay admission.
Close is required so AUTHORIZED cannot reopen the slot; idempotent close replay
returns `ALREADY_CLOSED` / `owner_status=DONE`.

Close also appends a repair-marked `FORGE_RUN_RECEIPT` (same parent
`run_identity_sha256`, `repair_continuation_disposition_sha256` set) without
rewriting the historical exhausted parent receipt. After close (and after store
reopen), ordinary `forge-run --no-write` must show the **repair** terminal —
e.g. `KILL_*` → `NON_SCIENTIFIC_STOP`, PASS/CASE_A → `OWNER_CANDIDATE`, repair
`NO_WORTHY` → `SEARCH_EXHAUSTED_CURRENT_EVIDENCE` — not the parent
`SEARCH_EXHAUSTED` and not `SCIENTIFIC_IDENTITY_CONFLICT`. Close JSON carries
`forge_run_receipt_sha256` when persist succeeds. `ALREADY_CLOSED` crash
recovery may still append a missing repair receipt; trust
`forge_run_receipt_sha256` / subsequent `--no-write` readback, and `writes=true`
when that recovery actually wrote.

### Plan/apply/draft/close owner terminals

| Machine `status` | `owner_status` | Meaning | `next_step` |
|---|---|---|---|
| `READY` | `READY` | Disposition/draft valid; not written | plan → `APPLY_WITH_EXPLICIT_CONFIRM_APPEND_ONLY`; draft → `REPAIR_CONTINUATION_PLAN_WITH_DRAFT` |
| `ALREADY_APPLIED` | `DONE` | Idempotent replay | `ORDINARY_TEMPORAL_QUERY_WITHIN_REMAINING_BUDGET` |
| `APPLIED` | `DONE` | Disposition appended | ordinary query in remainder |
| `CLOSED` / `ALREADY_CLOSED` | `DONE` | Disposition consumed after new terminal | `STOP_CONTINUATION_CONSUMED` |
| `NOT_APPLICABLE` | `BLOCKED` | Wrong parent / missing field / selected candidate / slot / spent mismatch | see `reason_code` + `owner_readout.next` |
| `CONFLICT` | `BLOCKED` | Competing active disposition | `CLOSE_COMPETING_DISPOSITION_THEN_STOP` using competitor `disposition_sha256` from plan JSON |

Draft/apply failures also print JSON on stdout with `owner_status=BLOCKED`
(not stderr-only codes). Common draft codes:

| `reason_code` | `next_step` |
|---|---|
| `PARENT_SESSION_MISSING` | `PROVIDE_PARENT_SESSION_ID_FROM_SHOW_SESSION` |
| `PARENT_RUN_REQUIRED` | `PROVIDE_PARENT_RUN_ID_OR_ENSURE_FORGE_RUN_RECEIPT` |
| `PARENT_RUN_MISMATCH` / `PARENT_RUN_UNPROVEN` | `ALIGN_DRAFT_PARENT_RUN_ID` / `OMIT_CALLER_RUN_ID_AND_USE_DERIVED_BINDING` — a caller `--parent-run-id` is not proof; omit it and re-draft |
| `PARENT_RECEIPT_CONFLICT` | `INSPECT_CONTRADICTING_FORGE_RUN_RECEIPT` — a partial or damaged aggregate blocks fallback |
| `PARENT_BINDING_MISMATCH` | `ALIGN_DRAFT_LEGACY_PARENT_BINDING` |
| `CORPUS_BINDING_UNPROVEN` / `CORPUS_BINDING_CONFLICT` | `RESTORE_JOURNAL_CORPUS_BINDING` / `RESOLVE_JOURNAL_CORPUS_BINDING` |
| `REPRESENTATION_SCOPE_UNPROVEN` / `SLOT_IDENTITY_UNPROVEN` / `FOCUS_IDENTITY_UNPROVEN` / `MARKET_IDENTITY_UNPROVEN` | restore the durable admission/session hashes; do not guess provenance |
| `SPENT_BUDGET_EXHAUSTED` | `STOP_LOOK_BUDGET_EXHAUSTED` |
| `REPAIR_RESULT_UNREADABLE` | `RETRY_CLOSE_UNTIL_REPAIR_RESULT_IS_READABLE` — close did not consume the authorization |
| `PARENT_TERMINAL_RECEIPT_MISSING` | `PROVIDE_TERMINAL_RECEIPT_FROM_SHOW_SESSION` |
| `TERMINAL_RECEIPT_REQUIRED` | `ENSURE_SESSION_RECEIPT_SHA256_ON_SHOW_SESSION` |
| `SPENT_BUDGET_INVALID` | `PASS_SPENT_LOOKS_OR_ENSURE_DISCOVERY_JOURNAL` |
| `SPENT_BUDGET_MISMATCH` | `ALIGN_DRAFT_SPENT_LOOKS_TO_JOURNAL` (or `…_TO_PARENT` from plan JSON when store has no looks) |
| `DISPOSITION_ALREADY_CLOSED` | `STOP_CONTINUATION_ALREADY_CONSUMED` |
| `REPAIR_EXECUTION_NOT_COMPLETE` | `COMPLETE_DISPOSITION_BOUND_REPAIR_EXECUTION_THEN_CLOSE` — finish pending critic/classification/runner-up **or** run a new repair freeze/finalize bound to this disposition (apply alone / parent DONE is not enough); disposition stays AUTHORIZED; do not rerun apply |
| `COMPETING_ACTIVE_DISPOSITION` / `COMPETING_DISPOSITION_APPLIED` | `CLOSE_COMPETING_DISPOSITION_THEN_STOP` — plan or apply-blocked JSON `disposition.disposition_sha256` (and `owner_readout.competing_disposition_sha256` on apply) is the competitor to `repair-continuation-close` |
| `REPAIR_CONTINUATION_CONFIRM_REQUIRED` | `ADD_CONFIRM_APPEND_ONLY_WITH_OWNER_AUTHORITY` |

Ordinary temporal discovery after a READY/DONE continuation uses the same
`/hypothesis-forge` discovery path and inherited look counts. Do not open a
new session to refresh quota.

## Legacy parent without an aggregate receipt

A completed `NO_WORTHY` session can lack a stored `FORGE_RUN_RECEIPT`. Draft
then derives `evidence_mapping.legacy_parent_binding` with
`provenance=ESTABLISHED_NOW` and `aggregate_receipt=ABSENT`. `parent_run_id`
is `LEGACY-PARENT-` plus the binding digest prefix. That id is not a
historical `FORGE-RUN-*` and is not accepted from `--parent-run-id` unless it
equals the derivation.

The binding uses the session receipt, journal scope, slot, market epoch,
journal corpus hash, and the single representation on the slot admission.
It does not mark the current ACTIVE ladder as already executed and does not
fill missing model or execution provenance. A contradicting or only partially
matching aggregate receipt is `PARENT_RECEIPT_CONFLICT`; fallback does not
override it.

Plan, apply, and close use that same check. Close writes a repair result
receipt whose `run_identity_sha256` is the pinned binding digest, reads it
back, then appends `CLOSED`. `CLOSED`/`DONE` without that readable result is
refused and the authorization stays open. Retry is idempotent.

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
