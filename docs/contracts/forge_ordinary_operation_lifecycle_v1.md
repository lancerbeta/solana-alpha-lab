# Forge ordinary operation lifecycle V1

Owner: `FORGE_ORDINARY_OPERATION_LIFECYCLE_REPAIR_V1`.
This document grants no scientific, provider, activation, or merge authority.

An ordinary operation is one explicit owner request bound to one journal,
market epoch, focus and scientific slot. Its execution state is separate from
any scientific result. `hfic_ordinary_operation.operation_lifecycle` is the
only owner of the effective state; readback, admission and the
research-universe policy gate all read it.

## States

| Effective state | Source | Holds the universe gate |
|---|---|---|
| `OPEN` | persisted `OPEN`, no proven completion | yes |
| `PAUSED_CAP` | persisted; `LIMITED_RESULT` cap spent | no |
| `STOPPED` | persisted owner stop of this exact operation | no |
| `COMPLETED` | derived, never written | no |

`COMPLETED` applies only to `requested_completion=SCIENTIFIC_TERMINAL`. It is
proven by the run's own persisted `FORGE_RUN_RECEIPT` and nothing else:

- same focus, market epoch and scientific slot as the operation;
- recorded at or after the operation was opened;
- the latest such receipt has `owner_class=OWNER_FINAL` and `owner_final` in
  `OWNER_CANDIDATE`, `SEARCH_EXHAUSTED_CURRENT_EVIDENCE` or
  `NON_SCIENTIFIC_STOP`;
- its BASE stage session carries the operation's journal.

A focus name, a UI terminal word, a missing process, an older-market
receipt or an in-progress receipt is not completion. `NON_SCIENTIFIC_STOP`
completes the operation but is labelled `scientific=false`. Completion adds
no record and no verdict; the receipt already is the owner-final.

When the run is owner-final but its receipt is not saved,
`forge-run --no-write` shows `next=PERSIST_OWNER_FINAL`. The idempotent
reconcile is `forge-run --persist --owner-focus <FOCUS>`; it writes nothing
when the same receipt already exists. An unfinished run writes no
owner-final, so it stays `OPEN`.

## Owner stop

```text
operation-stop-preview --operation-sha256 <hex> --owner-request-text "<text>"
operation-stop --proposal <file> --confirm-append-only
```

The preview is read-only. The proposal binds the exact operation, its latest
record, the owner text and the unresolved reservations. Apply re-checks them
under the ResearchStore writer lease; any change is
`OPERATION_STOP_PREVIEW_STALE` and writes nothing. A repeat on a stopped
operation is `NO_CHANGE`. A `COMPLETED` operation is refused with
`OPERATION_ALREADY_COMPLETED`; read its saved result instead. No active
research-universe profile is required.

A stop ends execution. It records no scientific verdict, never creates
`NO_WORTHY` or `SEARCH_EXHAUSTED`, keeps every saved result, and keeps every
reservation and look spent. An unresolved reservation is listed in the stop
record as an UNKNOWN attempt, not erased.

After a stop no new look, preview or resume is admitted
(`ORDINARY_OPERATION_STOPPED`). Saved results still replay, and an explicit
calculation revision of a saved result stays available. A writer already past
the last admission check finishes under the profile snapshot it captured; it
cannot switch to a later profile. Every operation-state append is
compare-before-append, so a late landing or fingerprint stamp cannot turn a
stopped operation back into `OPEN`.

## Research-universe gate

`universe-policy-status` and `universe-policy-preview` list
`blocking_operations`: operation id, focus, requested completion, persisted
and effective state, completion gap, unresolved reservations and the next
action (`FINISH_RUN_THEN_PERSIST_OWNER_FINAL_OR_STOP_OPERATION`,
`RUN_AUTHORIZED_LOOK_OR_STOP_OPERATION` or `STOP_OPERATION` when the bound
owner-final predates the operation). Apply re-checks the pending state and the
policy head under the writer lease.

`universe-policy-preview --decision-point` decides a preview-allowance refusal
from metadata before any market value is read. A refusal after values were
read reports `values_loaded=true`.

## Rollback

Before any live stop record, an ordinary revert. Afterwards keep a reader: the
previous code already treats `STOPPED` as not `OPEN`. Never delete data-plane
history.
