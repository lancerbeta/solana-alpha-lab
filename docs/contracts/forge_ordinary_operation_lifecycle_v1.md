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

- same focus and market epoch as the operation; the aggregate's active slot names an included stage;
- recorded at or after the operation was opened;
- `owner_class=OWNER_FINAL` and `owner_final` in `OWNER_CANDIDATE`,
  `SEARCH_EXHAUSTED_CURRENT_EVIDENCE` or `NON_SCIENTIFIC_STOP`;
- the operation's own stage carries its scientific slot and journal. A BASE
  operation retains legacy missing-stage-slot compatibility. A representation
  operation requires an exact slot, version, payload, completed session and its
  declared BASE parent among the same aggregate's stages.

The earliest such bound receipt is the proof. Completion is monotone: a later
in-progress or blocked receipt of the same slot does not reopen the operation.

A focus name, a UI terminal word, a missing process, an older-market
receipt or an in-progress receipt is not completion. `NON_SCIENTIFIC_STOP`
completes the operation but is labelled `scientific=false`. Completion adds
no record and no verdict; the receipt already is the owner-final.

When the run is owner-final but its receipt is not saved,
`forge-run --no-write` shows `next=PERSIST_OWNER_FINAL`. The idempotent
reconcile is `forge-run --persist --owner-focus <FOCUS>`; it writes nothing
when the same receipt already exists. An unfinished run writes no
owner-final, so it stays `OPEN`.

## Ordinary representation readback

Ordinary BASE is the parent of episode representation stages without becoming
CONTROL. Discovery checks exact parent, focus, market and slot; a saved BASE
draft cannot stand in for an unstarted child. A validated child draft resumes
its own stage, and a pending child cannot authorize an owner-final.

A capability-epoch change does not rewrite or reopen completed science. The
aggregate may historically read back a wholly completed ordinary chain only
when its stages retain one source capability epoch, their market/slot/parent
bindings are valid, their representation versions still agree, and the existing
transition owner derives a final. Missing or pending children do not qualify.
The source epochs/results remain frozen; current readback provenance is not a
new scientific execution, readiness attestation, look or budget reset.

The same persisted owner-final can complete BASE and its bound representation
operations even if its active slot points to a later candidate. Completion
remains derived and monotone; no status append, artificial owner-stop, history
rewrite, new look or quota refund is introduced. A repeat native persist is
idempotent. Code acceptance alone does not append a real owner-final: use the
existing authorized forge-run --persist only after merge and exact-state
revalidation, then cold-read both operations and the universe gate.

Every ACTIVE representation's START/RESUME action selects its own slot and
passes the existing scientific-admission owner. A pending child with a different
source capability is blocked, never replaced by a fresh START or BASE resume.
A computed owner-final is displayed as NEXT / PERSIST_OWNER_FINAL until native
append. Only the writer or committed readback supplies persisted_receipt; a
computed receipt hash alone is not persistence or operational DONE.

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

A stop ends this operation's ordinary looks and previews; it does not gate
forge-run freeze, Critic or `--persist`, and a later scientific owner-final
receipt of the same slot is not erased by it. It records no scientific verdict, never creates
`NO_WORTHY` or `SEARCH_EXHAUSTED`, keeps every saved result, and keeps every
reservation and look spent. An unresolved reservation is listed in the stop
record as an UNKNOWN attempt, not erased.

After a stop no new look, preview or resume is admitted
(`ORDINARY_OPERATION_STOPPED`); the same holds for a `COMPLETED` operation
(`ORDINARY_OPERATION_COMPLETED`), so no look can land under a later profile
than the run was frozen with. Saved results still replay, and an explicit
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
`RUN_AUTHORIZED_LOOK_OR_STOP_OPERATION` or `STOP_OPERATION` when no profile is active, the receipt is unbound, or the
bound owner-final predates the operation). Apply re-checks the pending state and the
policy head under the writer lease.

`universe-policy-preview --decision-point` decides a preview-allowance refusal
from metadata before any market value is read. A refusal after values were
read reports `values_loaded=true`.

## Rollback

Before any live stop record, an ordinary revert. After a live stop record,
forward-fix only: the previous code treats `STOPPED` as not `OPEN` for the gate
but does not refuse admission, so reverting would re-admit looks on stopped
operations. Never delete data-plane history.

The public run's operation readout is narrowed to its active scientific slot.
A paused BASE journal cannot replace a child-slot START with additional BASE
look authority. Same-slot caps and the universe gate remain enforced by their
existing owners; display selection never closes, refunds or hides an operation
from effective_open_operations. A previously unmatched completed-child
review/technical terminal (including KILL_STATISTICALLY_UNIDENTIFIABLE) uses
BASE's existing semantic owner and ends non-scientifically with a saved stage
reference. Legacy registered known-negative routing stays unchanged. Unknown
terminal, pending state or missing reference cannot establish the new fallback final.
