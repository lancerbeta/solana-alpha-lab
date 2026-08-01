# TASK-21 bounded panel checkpoint contract v1.0

`T21-A7A_BOUNDED_PANEL_CHECKPOINT_AND_EXTEND_EVIDENCE_V1` preserves the
current TASK-21 live evidence before any decision to collect more. It is a
checkpoint, not the research-grade dataset freeze promised by TASK-21.

## Decision boundary

The accepted run plan requires at least five complete members, fifteen
complete panels, three distinct admission dates, three distinct admission
weeks and evidence from multiple observed market states. The current owner
pulse reports three real admissions and seven captured panels. Even the most
favourable arithmetic upper bound is below the member and panel minima, while
multiple market states have not been established.

The only honest current disposition is therefore `EXTEND_EVIDENCE`. The
checkpoint must not claim `DATASET_READY`, open TASK-22, unseal hypothesis
outcomes or convert elapsed time into evidence. H72 and H168 remain
`DEFERRED_TRIGGER_ONLY`; neither is required merely because its clock offset
exists.

## Frozen evidence

The local package contains the exact live shakedown, T1 nomination/replay,
H0, H1, explicit H6 gap and H24-plus evidence roots. Every file is inventoried
by relative path, byte count and SHA-256. The ZIP uses fixed metadata,
uncompressed deterministic entries and a canonical manifest. Creation and
isolated restore are create-only; accepted source bytes are never replaced or
deleted.

The archive is a local recovery candidate only. Until the exact archive is
copied to an independent destination, read back and restored there, its status
is `REMOTE_RECOVERY_PENDING`. Catalog finalization, canonical Sources,
product-vision reconciliation and TASK-21 DONE remain outside this atom.

## Next decision

Further collection requires a new bounded information-sufficiency plan. It
must choose either:

- more independently nominated members and decision-relevant observed states;
- a narrower, explicitly conditional estimand;
- `COLLECTION_NOT_JUSTIFIED`, `REDESIGN_DATA` or `STOPPED_SAFELY`.

That decision cannot be replaced by automatic H72/H168 captures or by waiting
for an arbitrary number of days.

## Authority and non-claims

This atom is local-write-only. Provider/API/RPC/WSS calls, Drive actions,
credentials, cash spend, deployment, scheduler/background work,
wallet/signer/transaction actions, Git transport, merge, destructive cleanup
and Project UI changes are zero or forbidden.
