# TASK-21 Future Sentinel Capture Core Contract v1.0

## Purpose

`TASK21-FUTURE-SENTINEL-CAPTURE-CORE-001` is one provider-neutral foreground
runtime core for the future H72 and H168 TASK-21 quote panels. It prevents two
more horizon-specific copies of the H24 implementation while preserving the
same point-in-time, recovery, cap, create-only and explicit-gap behavior.

This parallel atom validates reusable code only. It does not create an H72 or
H168 runtime config, active time gate, provider authority or scheduled job.

## Reuse decision

The decision is `WRAP_EXISTING_PRIMITIVES_THEN_BUILD_THIN_CORE`:

- reuse Jupiter request, projection and dependent-sell primitives;
- reuse the bounded transport only behind its existing exact execution gate;
- reuse TASK-21 recovery freshness validation and canonical hash helpers;
- keep accepted H24 code and configuration unchanged before its live window;
- parameterize only the horizon identity, predecessor, frozen H0 offset,
  output root and next boundary.

Importing private H24 functions was rejected because their atom and horizon
identity is embedded in durable evidence. Refactoring H24 immediately before
its window was rejected because it would invalidate already accepted bytes.

## Runtime binding contract

A later H72 or H168 binding atom must create a separate runtime config that
pins all of the following by repository-relative path and SHA-256:

1. accepted H0 runtime evidence;
2. the immutable H0 admission population;
3. the immediately preceding horizon runtime-or-gap acceptance;
4. exactly one `ACTIVE_WAITING` marker owned by the selected runtime atom;
5. a current healthy recovery receipt supplied at execution time.

The core derives each window from the latest immutable H0 trigger plus the
frozen offset. A declared gate that differs by even one microsecond fails
closed. The population must contain exactly the three configured members in
the same order. The predecessor receipt must be `PASS`, belong to TASK-21 and
name the exact predecessor runtime atom; a hash-valid failed or unrelated
receipt is rejected.

## Runtime behavior

- Before `earliest_at`: fail before transport or output.
- Inside the ten-minute window: require the exact horizon-specific execution
  phrase, healthy recovery, sufficient disk and the frozen caps.
- After `latest_at`: forbid provider transport and create one explicit
  create-only gap receipt with no backfill or reschedule.
- A successful panel stores raw envelopes, a content-addressed manifest and a
  receipt. A successful horizon contains exactly three panels and at most 24
  calls.
- H72 projects H168 as waiting but unauthorized. H168 returns a bounded
  follow-up-selection boundary; it does not invent TASK-21 acceptance or A7
  eligibility.

## Safety and non-claims

The core grants no authority. Runtime binding and exact user approval remain
separate. It creates no scheduler, daemon, deployment, provider account,
purchase, Drive action, credential, wallet, signer, transaction, trade,
position, PnL, NetReturn or alpha claim.

Offline tests use an injected fake transport and temporary create-only roots.
They make zero network/provider/API/RPC/WSS calls and write no raw or dataset
bytes to the repository.

## Acceptance and Catalog

Acceptance requires deterministic H72 and H168 profiles, before/during/after
window tests, cap/authority/recovery/time-drift adversarial tests, exact
create-only behavior, sanitized receipts and a zero-side-effect acceptance
record. New TASK-21 assets remain pending the single A7 Catalog transaction.
